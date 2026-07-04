"""Stub for the EU AI Act public registry collector.

The registry itself does not exist yet. Per the EU AI Act implementation
timeline, providers of high-risk AI systems become subject to registration
obligations from August 2026, and the Commission has not yet published the
public-facing registry structure or API.

Do not build scraping/parsing logic against a schema that doesn't exist —
once the registry goes live, check its actual structure (REST API vs. CSV
export vs. HTML-only portal) at https://digital-strategy.ec.europa.eu/en/policies/ai-act
before writing real collection logic here.

This module is intentionally a no-op so it can be wired into collect.yml
ahead of time without erroring, and swapped for real logic later without
touching the workflow.
"""

from __future__ import annotations


def main() -> None:
    print("eu_aiact_collector: registry not yet live (expected Aug 2026+); no-op.")


if __name__ == "__main__":
    main()
