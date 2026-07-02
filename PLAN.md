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

- [ ] `pipeline/huggingface_collector.py`: HF Hub API scan for model cards with org
      affiliation + base model + framework metadata; write into org profiles' `hf_models`
- [ ] `pipeline/jobs_collector.py`: start with Greenhouse's public API (structured JSON,
      no auth) against a curated list of employer boards; match `AGENTIC_JOB_TERMS`;
      write into org profiles' `job_signals`
- [ ] Wire both into `collect.yml` alongside the GitHub step
- [ ] `site/signals/signals.njk`: filterable feed page reading last 7 days of
      `data/signals/*.jsonl`, filterable by signal type / confidence / framework

Done when: signal feed page shows a mix of dependency, model-card, and job-posting
signal types with correct confidence badges.

---

## Phase 4 — Sector view + framework tracker

Goal: aggregate views on top of the by-now-real data store.

- [ ] `site/sectors/sectors.njk`: sector explorer reading `data/sectors/*.json` —
      per-sector org counts and top frameworks. Apply the coverage disclaimer from
      CLAUDE.md's "Known limitations" #1 wherever a thin-coverage sector is shown
- [ ] `site/tech/tech.njk` (paginated per framework): adoption-over-time view reading
      `data/frameworks/{slug}.json`'s signal history — simple SVG/canvas sparkline or
      table, no charting library dependency unless one is already justified
- [ ] Cross-link: org profile -> framework pages -> sector pages

Done when: navigating homepage -> sector -> framework -> org and back works with no
dead links, using real pipeline-generated data.

---

## Phase 5 — EU AI Act registry (blocked until Aug 2026)

Goal: placeholder now, real collector once the registry ships.

- [ ] `pipeline/eu_aiact_collector.py`: stub that no-ops with a clear TODO and a comment
      linking to where the registry announcement should be checked
- [ ] Do not build scraping logic against a registry structure that doesn't exist yet —
      wait for the actual launch and inspect the real API/site before writing code

Done when: stub exists and is excluded from the nightly workflow (or runs as a no-op
without erroring) until reactivated.

---

## Cross-cutting / ongoing

- [ ] `/methodology` page must stay in sync with CLAUDE.md's "Known limitations" as
      new collectors are added — treat this as part of the done-criteria for Phase 2/3,
      not a separate task
- [ ] Confidence levels and evidence links are a hard requirement on every new signal
      type added by any collector — verify at code review time, not just at UI time
- [ ] Before adding a new sector or org, check CLAUDE.md's "Explicitly out of scope"
      list first
