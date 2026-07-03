"""HuggingFace collector: scans model cards published under orgs already
present in our data store (i.e. orgs the GitHub collector already found
public agentic-AI signal for) for evidence of fine-tuned/base-model work.

Scope call (mirrors github_collector's org-attribution reasoning): rather
than crawling all of HuggingFace Hub for arbitrary orgs -- which has no
reliable "is this an organization vs. an individual" signal the way GitHub
does -- this collector only queries HF namespaces that match a `github_org`
login already on file. That's a real coverage gap (an org's HF namespace can
differ from its GitHub login) but it keeps the collector bounded and tied to
orgs we've already corroborated via a GitHub signal, per CLAUDE.md's
"Production != public" and "Org attribution" caveats.

Per CLAUDE.md's signal taxonomy, a HuggingFace model card is a "medium"
confidence signal -- it proves model work, not necessarily agentic-AI
deployment.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

from utils import (
    ORGS_DIR,
    add_hf_model,
    add_signal_history,
    append_signals,
    read_json,
    save_org,
    today,
    touch_org,
)

HF_API = "https://huggingface.co/api/models"
MIN_INTERVAL = 1.0
MAX_MODELS_PER_ORG = 10


def _get(url: str) -> list | dict | None:
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


def load_all_orgs() -> list[dict]:
    if not ORGS_DIR.exists():
        return []
    orgs = []
    for path in sorted(ORGS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        orgs.append(read_json(path))
    return orgs


def base_model_from_tags(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.startswith("base_model:") and not tag.startswith("base_model:finetune:") and not tag.startswith("base_model:quantized:"):
            return tag.split(":", 1)[1]
    for tag in tags:
        if tag.startswith("base_model:"):
            return tag.split(":", 2)[-1]
    return None


def fetch_org_models(namespace: str) -> list[dict]:
    time.sleep(MIN_INTERVAL)
    result = _get(f"{HF_API}?author={namespace}&limit={MAX_MODELS_PER_ORG}&full=true")
    return result or []


def process_org(org: dict, new_signals: list[dict]) -> bool:
    namespace = org.get("github_org", org["slug"])
    models = fetch_org_models(namespace)
    changed = False

    for m in models:
        model_id = m.get("id") or m.get("modelId")
        if not model_id:
            continue
        tags = m.get("tags", [])
        evidence = {
            "id": model_id,
            "name": model_id,
            "library": m.get("library_name"),
            "base_model": base_model_from_tags(tags),
            "confidence": "medium",
            "url": f"https://huggingface.co/{model_id}",
            "detected": today(),
        }
        if not add_hf_model(org, evidence):
            continue
        changed = True
        add_signal_history(org, today(), "hf_model", model=model_id)
        new_signals.append({
            "ts": f"{today()}T00:00:00Z",
            "org": org["slug"],
            "type": "hf_model",
            "framework": None,
            "confidence": "medium",
            "repo": model_id,
            "url": evidence["url"],
        })

    if changed:
        touch_org(org)
        save_org(org)
    return changed


def main() -> int:
    orgs = load_all_orgs()
    new_signals: list[dict] = []
    orgs_touched = 0

    for org in orgs:
        if process_org(org, new_signals):
            orgs_touched += 1

    written = append_signals(new_signals)
    print(f"huggingface_collector: {len(orgs)} orgs checked, "
          f"{written} new signal-feed entries written, {orgs_touched} orgs touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
