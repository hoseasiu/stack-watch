"""Rolls up per-org signals into per-framework and per-sector aggregate files.

Sector assignment starts as a manual lookup table (CLAUDE.md's model-provider
and framework detection is automatable from dependency files; sector is not,
since there's no reliable public signal for "what industry is this org in").
Orgs with no lookup-table entry stay "unclassified" until curated manually.
"""

from __future__ import annotations

import sys

from utils import FRAMEWORKS_DIR, SECTORS_DIR, ORGS_DIR, read_json, save_org, write_json

# Manual lookup table, keyed by github_org login (lowercase), applied only to
# orgs the collector left "unclassified" (see apply_sector_overrides below --
# hand-curated seed profiles already carry their own sector and are never
# touched here). Extend as new orgs are discovered and reviewed. CLAUDE.md's
# out-of-scope sectors (defense/healthcare/finance) must never appear as
# values here.
SECTOR_OVERRIDES: dict[str, str] = {}

# Safety net: if a lookup-table entry (or a previously hand-curated org file)
# ever names one of these, refuse to aggregate it rather than surface
# out-of-scope org profiles. See CLAUDE.md "Explicitly out of scope".
OUT_OF_SCOPE_SECTORS = {"defense", "healthcare", "finance"}


def load_all_orgs() -> list[dict]:
    if not ORGS_DIR.exists():
        return []
    orgs = []
    for path in sorted(ORGS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        orgs.append(read_json(path))
    return orgs


def apply_sector_overrides(orgs: list[dict]) -> list[dict]:
    """Only fills in a sector for orgs the collector left "unclassified" --
    never overwrites a sector that's already been set (hand-curated seed
    profiles included), since that could silently reclassify a curator's
    editorial judgment call.
    """
    updated = []
    for org in orgs:
        if org.get("sector") != "unclassified":
            updated.append(org)
            continue
        override = SECTOR_OVERRIDES.get(org.get("github_org", "").lower())
        if override:
            org["sector"] = override
            save_org(org)
        updated.append(org)
    return updated


def build_frameworks(orgs: list[dict]) -> int:
    frameworks: dict[str, dict] = {}
    for org in orgs:
        if org.get("sector") in OUT_OF_SCOPE_SECTORS:
            continue
        for slug, info in org.get("frameworks", {}).items():
            fw = frameworks.setdefault(slug, {"slug": slug, "orgs": [], "signal_history": []})
            fw["orgs"].append({
                "slug": org["slug"],
                "display_name": org["display_name"],
                "confidence": info.get("confidence"),
                "first_seen": info.get("first_seen"),
            })
            for hist in org.get("signal_history", []):
                if hist.get("framework") == slug:
                    fw["signal_history"].append({"date": hist["date"], "org": org["slug"]})

    for slug, fw in frameworks.items():
        fw["orgs"].sort(key=lambda o: o["first_seen"] or "")
        fw["signal_history"].sort(key=lambda h: h["date"])
        fw["org_count"] = len(fw["orgs"])
        write_json(FRAMEWORKS_DIR / f"{slug}.json", fw)

    return len(frameworks)


def build_sectors(orgs: list[dict]) -> int:
    sectors: dict[str, dict] = {}
    for org in orgs:
        sector = org.get("sector", "unclassified")
        if sector in OUT_OF_SCOPE_SECTORS:
            continue
        sec = sectors.setdefault(sector, {"sector": sector, "orgs": [], "framework_counts": {}})
        sec["orgs"].append({"slug": org["slug"], "display_name": org["display_name"]})
        for slug in org.get("frameworks", {}):
            sec["framework_counts"][slug] = sec["framework_counts"].get(slug, 0) + 1

    for sector, sec in sectors.items():
        sec["orgs"].sort(key=lambda o: o["slug"])
        sec["org_count"] = len(sec["orgs"])
        sec["top_frameworks"] = sorted(
            ({"slug": k, "count": v} for k, v in sec["framework_counts"].items()),
            key=lambda f: f["count"],
            reverse=True,
        )
        del sec["framework_counts"]
        write_json(SECTORS_DIR / f"{sector}.json", sec)

    return len(sectors)


def main() -> int:
    orgs = load_all_orgs()
    orgs = apply_sector_overrides(orgs)
    fw_count = build_frameworks(orgs)
    sector_count = build_sectors(orgs)
    print(f"build_aggregates: {len(orgs)} orgs, {fw_count} framework files, {sector_count} sector files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
