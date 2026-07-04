# StackWatch — Development Plan

Execution plan for Claude Code agents working this repo. Read `CLAUDE.md` first — it is
the source of truth for scope, data model, and design tokens. This file sequences the
work into agent-sized tasks with explicit done-criteria so a session can pick up a phase
cold and know when to stop.

Repo currently contains only `CLAUDE.md` and a standalone prototype `index.html`
(light-cream palette). Everything else below is greenfield.

Design tokens: light cream palette (`#FDFAF5` bg, `#C4793A` accent, DM Sans /
IBM Plex Mono / Instrument Serif), matching `index.html`. CLAUDE.md's design
section has been updated to match — both documents are in sync. `index.html`
remains the visual reference for layout and information density.

---

## Working agreements for agents

- Every phase ends with something runnable/checkable — don't leave partial scaffolding.
- Flat-file JSON/JSONL only. No database, no ORM, no ".env for a database URL."
- Never fabricate org/signal data outside of the explicitly hand-curated seed set in
  Phase 1. Phases 2+ pull from real APIs only.
- Every signal displayed on the site must carry a confidence level and a link to
  source evidence (see CLAUDE.md's "Confidence scoring" table). Treat this as a hard
  constraint on templates, not a nice-to-have.
- Respect scope boundaries in CLAUDE.md ("Explicitly out of scope") — do not add
  defense/healthcare/finance org profiles, vuln scoring, or authenticated scraping.
- Keep pipeline scripts idempotent: re-running a collector against unchanged upstream
  data should not duplicate signal feed entries or corrupt org JSON.
- Commit data and code separately where practical so `data/**` diffs stay reviewable.

---

## Phase 0 — Repo scaffolding

Goal: empty directories and config files exist so later phases don't need to invent
structure mid-task.

- [x] Create directory skeleton per CLAUDE.md's "Repo structure":
      `pipeline/`, `data/orgs/`, `data/signals/`, `data/frameworks/`, `data/sectors/`,
      `site/_data/`, `site/_includes/`, `site/org/`, `site/tech/`, `site/sectors/`,
      `site/signals/`, `static/`
- [x] `.gitignore` for Python (`__pycache__`, `.venv`) and Node (`node_modules`, `_site`)
- [x] `requirements-pipeline.txt` (start empty or with `requests`, `PyGithub`/raw REST,
      `huggingface_hub` — add as each collector actually needs them)
- [x] `package.json` + `.eleventy.js` minimal 11ty config (input `site/`, output `_site/`,
      passthrough copy for `static/`)
- [x] `README.md`: one paragraph pointing readers to CLAUDE.md and PLAN.md — don't
      duplicate content that already lives there

Done when: `npx @11ty/eleventy` runs against an empty `site/` without erroring. ✅ Verified.

---

## Phase 1 — Data model + static prototype

Goal: a working static site rendering hand-curated data, no pipeline yet. This proves
the data model and templates before automating collection.

- [x] Finalize org profile JSON schema as a documented example at
      `data/orgs/_schema-example.json` (copy of the CLAUDE.md example, kept in sync)
- [x] Hand-curate 3-5 seed org profiles in `data/orgs/{slug}.json` for real companies
      with genuinely public, verifiable GitHub signals (e.g. check actual
      requirements.txt/package.json contents before writing evidence URLs — do not
      invent evidence links). Seeded 5: SambaNova Systems, Cisco Outshift, Glean, Block,
      Scale AI — all evidence verified live via `gh api` / raw GitHub content / the
      Greenhouse public jobs API before being written into JSON.
- [x] `site/_data/orgs.js`: 11ty global data file that reads all `data/orgs/*.json`
      (also added `site/_data/signals.js`, `frameworks.js`, `sectorCounts.js` as
      supporting aggregation data files — not in the original plan but needed since
      Nunjucks lacks a `merge` filter for computing counts in-template)
- [x] `site/index.njk`: homepage — aggregate stats (org count, framework count) +
      last N signals, built from the seed data
- [x] `site/org/org.njk` (11ty pagination template) — one page per org profile,
      rendering frameworks/model_providers/job_signals with confidence dot indicators
      and evidence links. Also added `site/org/index.njk` (org directory), and minimal
      `site/tech/index.njk`, `site/sectors/index.njk`, `site/signals/signals.njk` so the
      nav bar has no dead links ahead of their full Phase 3/4 builds.
- [x] `site/methodology.md`: adapt CLAUDE.md's "Known limitations" section into
      user-facing prose
- [x] `static/style.css`: light cream terminal palette per CLAUDE.md, adapted from
      `index.html`'s token set (served from `/static/style.css` — passthrough copy
      preserves the `static/` prefix, template links account for that)
- [x] `.github/workflows/build.yml`: build 11ty + deploy to GitHub Pages on push to main

Done when: `npm run build` produces a `_site/` with a working homepage and at least 3
org profile pages, deployed via Pages (or deployable — confirm before enabling Pages
if repo visibility/settings aren't already decided). ✅ Build verified (5 org pages) and
visually checked in a local preview server. GitHub Pages deploy itself not yet
triggered — needs Pages enabled in repo settings first.

---

## Phase 2 — GitHub collector

Goal: automate org/framework discovery from real GitHub data, replacing hand-curation.

- [x] `pipeline/utils.py`: shared helpers — stdlib-only GitHub REST/GraphQL client
      (auth token from `GITHUB_TOKEN` env, backoff on 403/429), JSON read/write helpers
      for the `data/` store, idempotent signal-feed appender (dedupe by
      org+type+framework+repo+url before appending to `data/signals/{date}.jsonl`),
      and org-profile helpers (`add_framework_evidence`, `add_model_provider_evidence`,
      `add_signal_history` — each dedupes by evidence URL / full record before mutating)
- [x] `pipeline/github_collector.py`:
      - GitHub code search (`/search/code`) to find repos with dependency-file hits
        against `FRAMEWORK_SIGNALS` and `MODEL_PROVIDER_SIGNALS` (see CLAUDE.md),
        searching `requirements.txt`/`pyproject.toml` for Python frameworks + model
        providers and `package.json` for JS frameworks (mastra, n8n)
      - Checks for presence of `AGENT_CONFIG_FILES`, scoped to repos already
        discovered via dependency search (bounds API usage vs. a separate broad scan)
      - Maps repo owner -> org slug; only creates/updates a profile when the GitHub
        API reports the owner's account `type` as `"Organization"` (individual-
        contributor repos are skipped) — see module docstring for the ambiguity
        call, per CLAUDE.md's "Org attribution" limitation. Also carries a small,
        explicitly non-exhaustive denylist of known defense/healthcare/finance
        GitHub orgs as a scope safety net.
      - Rate limiting: single stdlib HTTP client throttles to >=1s between requests
        and backs off on `Retry-After`/403/429; caps total repos inspected per run
        (`MAX_REPOS_TOTAL`) to keep nightly runtime bounded
      - Write/update `data/orgs/{slug}.json`, append to signal feed — idempotency
        verified (re-running against the same hits produces zero new evidence/signal
        entries)
- [x] `pipeline/build_aggregates.py`: rolls up org signals into `data/frameworks/*.json`
      and `data/sectors/*.json`. Sector assignment uses a manual lookup table
      (`SECTOR_OVERRIDES`) applied only to orgs left `"unclassified"` by the
      collector — hand-curated Phase 1 seed profiles' sectors are never overwritten
- [x] `.github/workflows/collect.yml`: nightly cron + workflow_dispatch, runs collector
      then `build_aggregates.py`, auto-commits `data/**` via git-auto-commit-action
- [x] `site/_data/` sourcing already reads `data/orgs/*.json` dynamically from disk
      (Phase 1), so no changes were needed for it to pick up pipeline-written profiles
      the same way it read hand-curated ones — confirmed via a full `npm run build`

Done when: a manual `workflow_dispatch` run populates `data/orgs/` with 50+ orgs from
live GitHub data and the site rebuilds correctly from that output. Collector logic
verified locally (mocked GitHub client — real run requires a `GITHUB_TOKEN` and has
not yet been executed against the live API; a `workflow_dispatch` run against the
real API is the remaining step to hit the 50+ org target).

---

## Phase 3 — HuggingFace + jobs collectors

Goal: broaden signal types beyond GitHub; light up the signal feed page.

- [x] `pipeline/huggingface_collector.py`: HF Hub API scan for model cards, scoped to HF
      namespaces matching a `github_org` login already on file (no reliable "org vs.
      individual" signal on HF the way GitHub has one, so this stays bounded to orgs
      already corroborated by the GitHub collector — a real coverage gap, documented in
      the module docstring). Writes `id`/base_model/library into `hf_models`, confidence
      `medium` per CLAUDE.md's confidence table.
- [x] `pipeline/jobs_collector.py`: Greenhouse's public board API (structured JSON, no
      auth) against `CURATED_BOARDS` — a small, manually verified list (7 boards,
      HTTP-200-checked before being hardcoded), same pattern as build_aggregates.py's
      `SECTOR_OVERRIDES`. Matches `AGENTIC_JOB_TERMS` against job title + HTML-unescaped
      description; writes matches into `job_signals`, confidence `medium`.
- [x] Wired both into `collect.yml` alongside the GitHub + build_aggregates steps
- [x] `site/signals/signals.njk`: client-side filter controls (type / confidence /
      framework dropdowns, framework options sourced from `_data/frameworks.js`) over
      the existing last-7-days feed list; verified in-browser that combined filters
      narrow the visible count correctly
- [x] `site/org/org.njk`: `hf_models` section upgraded from a bare name to the same
      confidence-dot + evidence-link pattern as frameworks/model_providers/job_signals
      (was a placeholder from Phase 1 that predated this signal type existing)

Done when: signal feed page shows a mix of dependency, hf_model, and job-posting
signal types with correct confidence badges. ✅ Verified locally: both collectors run
idempotently against live APIs (zero new entries on a second run), `npm run build`
succeeds, and the signals page was checked in a local preview server with filters
tested end-to-end (type+framework combo narrowed 449 entries to 12 correctly).

---

## Phase 4 — Sector view + framework tracker

Goal: aggregate views on top of the by-now-real data store.

- [x] `site/sectors/sectors.njk`: paginated per-sector detail page (one per
      `data/sectors/{slug}.json`) — org count, top frameworks (linked to `/tech/{slug}/`),
      full org list (linked to `/org/{slug}/`). Carries the same coverage-notice bar as
      the sector index for every sector, since the disclaimer applies across the board
      (all tracked sectors reflect GitHub-presence bias, not just visibly thin ones).
      `site/sectors/index.njk` (the existing listing page) now links each sector row to
      its detail page.
- [x] `site/tech/tech.njk` (paginated per framework, reading `data/frameworks/{slug}.json`):
      adoption-over-time view as an inline SVG bar sparkline (monthly signal counts,
      computed in `site/_data/frameworkDetails.js` from `signal_history` — no charting
      library) plus a table of detected orgs (confidence + first-seen, linked to
      `/org/{slug}/`). `site/tech/index.njk` now links each framework row to its detail
      page.
- [x] Cross-link: org profile's sector badge -> `/sectors/{slug}/`; each framework name
      in org profile's evidence cards -> `/tech/{slug}/`; framework/sector detail pages
      link back to org profiles.

Done when: navigating homepage -> sector -> framework -> org and back works with no
dead links, using real pipeline-generated data. ✅ Verified in a local preview server:
`/tech/langgraph/` and `/sectors/saas/` render correctly with working sparkline/tables,
and `/org/glean/` cross-links resolve to the correct `/tech/crewai/` and `/sectors/saas/`
detail pages.

---

## Phase 5 — EU AI Act registry (blocked until Aug 2026)

Goal: placeholder now, real collector once the registry ships.

- [x] `pipeline/eu_aiact_collector.py`: stub that no-ops, printing a status line, with a
      module docstring pointing to where the registry announcement should be checked
      (digital-strategy.ec.europa.eu AI Act page) and an explicit note not to build
      scraping logic until the real structure is known
- [x] Do not build scraping logic against a registry structure that doesn't exist yet —
      confirmed still unpublished as of 2026-07-04; left as a no-op
- [x] Wired into `collect.yml` as a no-op step (runs, prints, exits 0) so the workflow
      shape doesn't need to change again when the registry goes live — just swap the
      module body

Done when: stub exists and is excluded from the nightly workflow (or runs as a no-op
without erroring) until reactivated. ✅ Verified `python pipeline/eu_aiact_collector.py`
runs cleanly and prints its no-op status.

---

## Cross-cutting / ongoing

- [ ] `/methodology` page must stay in sync with CLAUDE.md's "Known limitations" as
      new collectors are added — treat this as part of the done-criteria for Phase 2/3,
      not a separate task
- [ ] Confidence levels and evidence links are a hard requirement on every new signal
      type added by any collector — verify at code review time, not just at UI time
- [ ] Before adding a new sector or org, check CLAUDE.md's "Explicitly out of scope"
      list first
