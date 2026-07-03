"""Shared helpers for StackWatch collectors: GitHub API client, JSON data-store
read/write, and idempotent signal-feed appending.

Every collector reads/writes the same flat-file store under `data/`, so the
dedupe rules live here once rather than being re-implemented per collector.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ORGS_DIR = DATA_DIR / "orgs"
SIGNALS_DIR = DATA_DIR / "signals"
FRAMEWORKS_DIR = DATA_DIR / "frameworks"
SECTORS_DIR = DATA_DIR / "sectors"

GITHUB_API = "https://api.github.com"


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# JSON data store
# ---------------------------------------------------------------------------

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_org(slug: str) -> dict | None:
    return read_json(ORGS_DIR / f"{slug}.json")


def save_org(org: dict) -> None:
    write_json(ORGS_DIR / f"{org['slug']}.json", org)


def new_org_profile(slug: str, display_name: str, github_org: str, sector: str = "unclassified") -> dict:
    """Skeleton org profile matching the schema in data/orgs/_schema-example.json."""
    return {
        "slug": slug,
        "display_name": display_name,
        "github_org": github_org,
        "sector": sector,
        "first_detected": today(),
        "last_updated": today(),
        "frameworks": {},
        "model_providers": {},
        "job_signals": [],
        "hf_models": [],
        "signal_count": 0,
        "signal_history": [],
    }


def _evidence_exists(evidence_list: list[dict], url: str) -> bool:
    return any(e.get("url") == url for e in evidence_list)


def add_framework_evidence(org: dict, framework_slug: str, confidence: str, evidence: dict) -> bool:
    """Adds a framework signal + evidence to an org profile if not already present.
    Returns True if this changed the profile (used to decide whether to log a signal-feed entry).
    """
    entry = org["frameworks"].setdefault(
        framework_slug,
        {"confidence": confidence, "first_seen": evidence.get("detected", today()), "evidence": []},
    )
    if _evidence_exists(entry["evidence"], evidence["url"]):
        return False
    entry["evidence"].append(evidence)
    if evidence.get("detected", today()) < entry["first_seen"]:
        entry["first_seen"] = evidence["detected"]
    return True


def add_model_provider_evidence(org: dict, provider_slug: str, confidence: str, evidence: dict) -> bool:
    entry = org["model_providers"].setdefault(provider_slug, {"confidence": confidence, "evidence": []})
    if _evidence_exists(entry["evidence"], evidence["url"]):
        return False
    entry["evidence"].append(evidence)
    return True


def add_agent_config_evidence(org: dict, confidence: str, evidence: dict) -> bool:
    """Agent config file presence (CLAUDE.md/AGENTS.md/...) is its own signal
    type per CLAUDE.md's signal taxonomy -- distinct from a framework
    dependency hit, so it lives in its own `agent_config` field rather than
    being keyed into `frameworks` (which is iterated as framework slugs
    elsewhere, e.g. build_aggregates.py's per-framework rollup).
    """
    entry = org.setdefault("agent_config", {"confidence": confidence, "evidence": []})
    if _evidence_exists(entry["evidence"], evidence["url"]):
        return False
    entry["evidence"].append(evidence)
    return True


def add_job_signal(org: dict, job: dict) -> bool:
    """Adds a job-posting signal to an org profile, deduping by posting URL."""
    if any(j.get("url") == job.get("url") for j in org["job_signals"]):
        return False
    org["job_signals"].append(job)
    return True


def add_hf_model(org: dict, model: dict) -> bool:
    """Adds a HuggingFace model-card signal to an org profile, deduping by model id."""
    if any(m.get("id") == model.get("id") for m in org["hf_models"]):
        return False
    org["hf_models"].append(model)
    return True


def add_signal_history(org: dict, date: str, type_: str, **fields: Any) -> bool:
    record = {"date": date, "type": type_, **fields}
    if record in org["signal_history"]:
        return False
    org["signal_history"].append(record)
    org["signal_count"] = len(org["signal_history"])
    return True


def touch_org(org: dict) -> None:
    org["last_updated"] = today()


# ---------------------------------------------------------------------------
# Signal feed (JSONL, one file per UTC day)
# ---------------------------------------------------------------------------

def _signal_key(entry: dict) -> tuple:
    return (entry.get("org"), entry.get("type"), entry.get("framework"), entry.get("repo"), entry.get("url"))


def append_signals(entries: Iterable[dict], date: str | None = None) -> int:
    """Appends signal-feed entries for `date` (default: today), skipping any
    entry that already exists in that day's file. Returns count actually written.
    """
    date = date or today()
    path = SIGNALS_DIR / f"{date}.jsonl"
    existing_keys = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    existing_keys.add(_signal_key(json.loads(line)))

    to_write = []
    for entry in entries:
        key = _signal_key(entry)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        to_write.append(entry)

    if not to_write:
        return 0

    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for entry in to_write:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(to_write)


# ---------------------------------------------------------------------------
# GitHub API client (stdlib-only, since requests isn't a hard requirement)
# ---------------------------------------------------------------------------

class GitHubError(RuntimeError):
    pass


class GitHubClient:
    """Minimal REST + GraphQL client with auth and secondary-rate-limit backoff.

    Uses urllib rather than `requests` to keep the pipeline dependency-free for
    this collector; `requests` in requirements-pipeline.txt remains available
    for future collectors that want it.
    """

    def __init__(self, token: str | None = None, min_interval: float = 1.0):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise GitHubError("GITHUB_TOKEN environment variable is required")
        self.min_interval = min_interval
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_ts = time.monotonic()

    def _request(self, method: str, url: str, headers: dict | None = None, body: bytes | None = None,
                 retries: int = 3) -> dict:
        req_headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "stackwatch-collector",
        }
        req_headers.update(headers or {})

        for attempt in range(retries):
            self._throttle()
            req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise
                if e.code in (403, 429) and attempt < retries - 1:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else 2 ** (attempt + 1) * 5
                    time.sleep(wait)
                    continue
                raise GitHubError(f"GitHub API error {e.code} for {url}: {e.read().decode('utf-8', 'ignore')}") from e

        raise GitHubError(f"GitHub API request failed after {retries} retries: {url}")

    def get_repo(self, full_name: str) -> dict | None:
        return self.get_optional(f"/repos/{full_name}")

    def get_contents(self, full_name: str, path: str) -> dict | None:
        return self.get_optional(f"/repos/{full_name}/contents/{path}")

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{GITHUB_API}{path}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        return self._request("GET", url)

    def get_optional(self, path: str) -> dict | None:
        """Like get(), but returns None instead of raising on a 404."""
        try:
            return self.get(path)
        except urllib.error.HTTPError:
            return None
        except GitHubError:
            return None

    def search_code(self, query: str, per_page: int = 30) -> list[dict]:
        try:
            result = self.get("/search/code", {"q": query, "per_page": per_page})
        except GitHubError:
            return []
        return result.get("items", [])

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        return self._request(
            "POST", f"{GITHUB_API}/graphql", headers={"Content-Type": "application/json"}, body=body
        )
