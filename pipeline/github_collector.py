"""GitHub collector: finds orgs with public evidence of agentic-AI framework
adoption via GitHub code search, and writes/updates their org profiles.

Signal sources (see CLAUDE.md "Signal taxonomy"):
  - dependency file hits (requirements.txt / pyproject.toml / package.json)
  - presence of an agent config file (CLAUDE.md, AGENTS.md, .cursorrules, ...)

Org attribution (CLAUDE.md "Known limitations" #3): a repo owned by an
individual GitHub user is NOT treated as evidence of organizational
investment, even if the account looks corporate-affiliated. We only create/
update an org profile when the repo owner's GitHub account type is
"Organization". This intentionally undercounts orgs that publish through
personal accounts -- that's a coverage gap, not a bug.

Scope enforcement (CLAUDE.md "Explicitly out of scope"): a small denylist of
known defense/healthcare/finance GitHub orgs is skipped outright as a safety
net. This list is NOT exhaustive -- it exists to catch obvious cases
automatically; anything else out-of-scope must be caught at editorial review
before merging data/orgs/*.json.
"""

from __future__ import annotations

import sys

from utils import (
    GitHubClient,
    add_framework_evidence,
    add_model_provider_evidence,
    add_signal_history,
    append_signals,
    load_org,
    new_org_profile,
    save_org,
    today,
    touch_org,
)

# See CLAUDE.md "Signal taxonomy" -- keep these in sync with that document.
FRAMEWORK_SIGNALS = {
    "langgraph": ["langgraph"],
    "openai_agents_sdk": ["openai-agents", "openai_agents"],
    "autogen": ["pyautogen", "autogen-agentchat", "autogen-core"],
    "crewai": ["crewai"],
    "llamaindex": ["llama-index", "llama_index", "llama-index-core"],
    "dify": ["dify-client"],
    "pydantic_ai": ["pydantic-ai"],
    "smolagents": ["smolagents"],
}

# Searched only against package.json.
FRAMEWORK_SIGNALS_JS = {
    "mastra": ["@mastra/core"],
    "n8n": ["n8n"],
}

MODEL_PROVIDER_SIGNALS = {
    "anthropic": ["anthropic"],
    "openai": ["openai"],
    "google": ["google-generativeai", "google-genai", "vertexai"],
    "mistral": ["mistralai"],
    "self_hosted": ["ollama", "vllm", "llama-cpp-python"],
    "deepseek": ["deepseek"],
}

AGENT_CONFIG_FILES = [
    "CLAUDE.md", "AGENTS.md", ".cursorrules", "AGENT_CONFIG.md", "agent.yaml", "agent.yml",
]

PYTHON_DEP_FILES = ["requirements.txt", "pyproject.toml"]
JS_DEP_FILES = ["package.json"]

# Non-exhaustive safety net -- see module docstring.
ORG_DENYLIST = {
    "lockheedmartin", "raytheon", "northropgrumman", "boeing", "generaldynamics",
    "epicsystems", "cerner", "jpmorgan", "jpmorganchase", "goldmansachs", "bankofamerica",
}

MAX_REPOS_TOTAL = 150
MAX_RESULTS_PER_QUERY = 20


def search_dependency_hits(client: GitHubClient, terms_by_slug: dict[str, list[str]], filenames: list[str]):
    """Yields (slug, filename, code_search_item) for each match."""
    for slug, terms in terms_by_slug.items():
        for filename in filenames:
            for term in terms:
                query = f'"{term}" filename:{filename}'
                items = client.search_code(query, per_page=MAX_RESULTS_PER_QUERY)
                for item in items:
                    yield slug, filename, item


def repo_owner_org(client: GitHubClient, full_name: str) -> dict | None:
    """Returns the owning GitHub org's repo metadata dict, or None if the repo
    doesn't exist, is owned by an individual user, or is denylisted.
    """
    repo = client.get_repo(full_name)
    if repo is None:
        return None
    owner = repo.get("owner", {})
    if owner.get("type") != "Organization":
        return None
    if owner.get("login", "").lower() in ORG_DENYLIST:
        return None
    return repo


def check_agent_config(client: GitHubClient, full_name: str) -> list[str]:
    found = []
    for filename in AGENT_CONFIG_FILES:
        if client.get_contents(full_name, filename) is not None:
            found.append(filename)
    return found


def slugify(login: str) -> str:
    return login.lower().replace("_", "-")


def process_hit(client: GitHubClient, slug: str, filename: str, item: dict, signal_type: str,
                 seen_repos: dict[str, dict], new_signals: list[dict]) -> None:
    full_name = item["repository"]["full_name"]

    if full_name in seen_repos:
        repo = seen_repos[full_name]
        if repo is None:
            return
    else:
        repo = repo_owner_org(client, full_name)
        seen_repos[full_name] = repo
        if repo is None:
            return

    owner_login = repo["owner"]["login"]
    org_slug = slugify(owner_login)
    org = load_org(org_slug) or new_org_profile(org_slug, owner_login, owner_login)

    evidence = {
        "type": "dependency_file",
        "repo": full_name,
        "file": filename,
        "url": item.get("html_url", f"https://github.com/{full_name}/blob/main/{filename}"),
        "detected": today(),
    }

    if signal_type == "framework":
        changed = add_framework_evidence(org, slug, "high", evidence)
        history_kwargs = {"framework": slug}
    else:
        changed = add_model_provider_evidence(org, slug, "high", evidence)
        history_kwargs = {"framework": slug}

    if changed:
        add_signal_history(org, today(), "dependency", **history_kwargs)
        touch_org(org)
        save_org(org)
        new_signals.append({
            "ts": f"{today()}T00:00:00Z",
            "org": org_slug,
            "type": "dependency",
            "framework": slug,
            "confidence": "high",
            "repo": full_name,
            "url": evidence["url"],
        })


def process_agent_configs(client: GitHubClient, seen_repos: dict[str, dict], new_signals: list[dict]) -> None:
    for full_name, repo in seen_repos.items():
        if repo is None:
            continue
        owner_login = repo["owner"]["login"]
        org_slug = slugify(owner_login)
        found_files = check_agent_config(client, full_name)
        if not found_files:
            continue

        org = load_org(org_slug) or new_org_profile(org_slug, owner_login, owner_login)
        changed_any = False
        for filename in found_files:
            evidence = {
                "type": "agent_config",
                "repo": full_name,
                "file": filename,
                "url": f"https://github.com/{full_name}/blob/main/{filename}",
                "detected": today(),
            }
            key = f"agent_config:{filename}"
            entry = org["frameworks"].get(key)
            if entry and any(e.get("url") == evidence["url"] for e in entry["evidence"]):
                continue
            org["frameworks"].setdefault(key, {"confidence": "high", "first_seen": today(), "evidence": []})
            org["frameworks"][key]["evidence"].append(evidence)
            changed = add_signal_history(org, today(), "agent_config", framework=None, repo=full_name)
            changed_any = changed_any or changed
            new_signals.append({
                "ts": f"{today()}T00:00:00Z",
                "org": org_slug,
                "type": "agent_config",
                "framework": None,
                "confidence": "high",
                "repo": full_name,
                "url": evidence["url"],
            })

        if changed_any:
            touch_org(org)
            save_org(org)


def main() -> int:
    client = GitHubClient()
    seen_repos: dict[str, dict] = {}
    new_signals: list[dict] = []

    for slug, filename, item in search_dependency_hits(client, FRAMEWORK_SIGNALS, PYTHON_DEP_FILES):
        if len(seen_repos) >= MAX_REPOS_TOTAL:
            break
        process_hit(client, slug, filename, item, "framework", seen_repos, new_signals)

    for slug, filename, item in search_dependency_hits(client, FRAMEWORK_SIGNALS_JS, JS_DEP_FILES):
        if len(seen_repos) >= MAX_REPOS_TOTAL:
            break
        process_hit(client, slug, filename, item, "framework", seen_repos, new_signals)

    for slug, filename, item in search_dependency_hits(client, MODEL_PROVIDER_SIGNALS, PYTHON_DEP_FILES):
        if len(seen_repos) >= MAX_REPOS_TOTAL:
            break
        process_hit(client, slug, filename, item, "model_provider", seen_repos, new_signals)

    # Agent-config check is scoped to repos already discovered above, rather
    # than a separate broad search, to keep API usage bounded.
    process_agent_configs(client, seen_repos, new_signals)

    written = append_signals(new_signals)
    orgs_touched = len({s["org"] for s in new_signals})
    print(f"github_collector: {len(seen_repos)} org repos inspected, "
          f"{written} new signal-feed entries written, {orgs_touched} orgs touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
