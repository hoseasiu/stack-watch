"""Jobs collector: scans a curated list of public Greenhouse job boards for
postings matching CLAUDE.md's AGENTIC_JOB_TERMS, and writes matches into the
relevant org profile's `job_signals`.

Greenhouse's board API (`boards-api.greenhouse.io`) is public, unauthenticated
JSON -- no scraping behind a login wall, per CLAUDE.md's scope constraints.

CURATED_BOARDS is a small, manually verified list (board token checked to
return HTTP 200 before being added here), the same "manual lookup table,
extend as reviewed" pattern build_aggregates.py uses for SECTOR_OVERRIDES.
This is NOT a broad crawl -- Greenhouse has no public directory of which
companies use it, so there's no way to discover boards automatically without
guessing tokens, which we don't do.

Per CLAUDE.md's confidence table, a job posting skill-term match is a
"medium" confidence signal: a leading indicator, not proof of deployment.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

from utils import (
    add_job_signal,
    add_signal_history,
    append_signals,
    load_org,
    new_org_profile,
    save_org,
    today,
    touch_org,
)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"
MIN_INTERVAL = 1.0

# See CLAUDE.md "Job posting skill terms".
AGENTIC_JOB_TERMS = [
    "LangGraph", "LangChain", "AutoGen", "CrewAI", "agentic AI",
    "AI agent", "multi-agent", "MCP server", "Model Context Protocol",
    "OpenAI Agents SDK", "Claude Code", "tool use", "function calling",
    "RAG pipeline", "vector database", "AI orchestration",
]

# org_slug: reuse an existing data/orgs/{slug}.json if one exists (keeps
# job signals attached to the same profile the GitHub collector built);
# otherwise a new profile is created with this slug/display_name/sector.
CURATED_BOARDS = [
    {"board_token": "scaleai", "org_slug": "scale-ai", "display_name": "Scale AI",
     "github_org": "scaleai", "sector": "ai-infra"},
    {"board_token": "block", "org_slug": "block", "display_name": "Block",
     "github_org": "block", "sector": "fintech"},
    {"board_token": "anthropic", "org_slug": "anthropic", "display_name": "Anthropic",
     "github_org": "anthropics", "sector": "ai-lab"},
    {"board_token": "sambanovasystems", "org_slug": "sambanova", "display_name": "SambaNova Systems",
     "github_org": "sambanova", "sector": "ai-infra"},
    {"board_token": "togetherai", "org_slug": "together-ai", "display_name": "Together AI",
     "github_org": "togethercomputer", "sector": "ai-infra"},
    {"board_token": "fireworksai", "org_slug": "fireworks-ai", "display_name": "Fireworks AI",
     "github_org": "fw-ai", "sector": "ai-infra"},
    {"board_token": "vercel", "org_slug": "vercel", "display_name": "Vercel",
     "github_org": "vercel", "sector": "dev-tools"},
]

TAG_RE = re.compile(r"<[^>]+>")


def _get(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "stackwatch-collector"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None


def fetch_board_jobs(token: str) -> list[dict]:
    time.sleep(MIN_INTERVAL)
    result = _get(f"{GREENHOUSE_API}/{token}/jobs?content=true")
    if not result:
        return []
    return result.get("jobs", [])


def matched_terms(title: str, content_html: str) -> list[str]:
    text = f"{title}\n{TAG_RE.sub(' ', html.unescape(content_html or ''))}".lower()
    return [term for term in AGENTIC_JOB_TERMS if term.lower() in text]


def process_board(board: dict, new_signals: list[dict]) -> bool:
    jobs = fetch_board_jobs(board["board_token"])
    org = load_org(board["org_slug"]) or new_org_profile(
        board["org_slug"], board["display_name"], board["github_org"], board["sector"]
    )
    changed = False

    for job in jobs:
        terms = matched_terms(job.get("title", ""), job.get("content", ""))
        if not terms:
            continue

        posted = (job.get("first_published") or job.get("updated_at") or today())[:10]
        signal = {
            "title": job.get("title", ""),
            "terms_matched": terms,
            "posted": posted,
            "url": job.get("absolute_url", ""),
        }
        if not add_job_signal(org, signal):
            continue
        changed = True
        add_signal_history(org, today(), "job_posting", terms=terms)
        new_signals.append({
            "ts": f"{today()}T00:00:00Z",
            "org": org["slug"],
            "type": "job_posting",
            "framework": None,
            "confidence": "medium",
            "repo": None,
            "url": signal["url"],
        })

    if changed:
        touch_org(org)
        save_org(org)
    return changed


def main() -> int:
    new_signals: list[dict] = []
    orgs_touched = 0

    for board in CURATED_BOARDS:
        if process_board(board, new_signals):
            orgs_touched += 1

    written = append_signals(new_signals)
    print(f"jobs_collector: {len(CURATED_BOARDS)} boards checked, "
          f"{written} new signal-feed entries written, {orgs_touched} orgs touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
