# StackWatch — AI Supply-Chain Intelligence Dashboard
## Claude Code Project Brief

---

## What this is

StackWatch is a living, automated dashboard that tracks which organizations show evidence of investing in agentic AI infrastructure, inferred entirely from public signals. It is **not** a security scanner, a product review site, or a vendor self-disclosure registry. It is a technology adoption intelligence tool — answering the question:

> *"Which organizations show public evidence of moving fast on agentic AI, and what does the signal trail look like?"*

The closest analogues are:
- **Similarweb** (infer web stack from passive signals) — but for AI infrastructure
- **Stackshare** (technology choices by org) — but automated from OSINT rather than self-reported
- **Stanford AI Index** (ecosystem-level AI trends) — but queryable at the org level and continuously updated

---

## Scope decisions (intentional)

### In scope
- Tech companies, startups, universities, research labs — orgs with rich public GitHub footprints
- Signal types: GitHub dependency files, repo metadata/topics, CLAUDE.md/AGENTS.md configs, HuggingFace model cards, job postings, EU AI Act filings (Aug 2026+)
- Framework detection: LangGraph, AutoGen, CrewAI, OpenAI Agents SDK, LlamaIndex, Dify, n8n, Mastra, and emerging frameworks
- Model provider inference: Anthropic, OpenAI, Google, Mistral, self-hosted (Ollama/vLLM)
- Output: org profiles, sector views, framework adoption tracker, raw signal feed

### Explicitly out of scope
- Defense primes, federal agencies, healthcare/finance (public signal coverage is too thin to be credible — don't overclaim)
- Vulnerability scoring or security posture assessment
- Self-reported or survey data
- Any data requiring authentication, scraping behind login walls, or paid APIs (initially)

---

## Architecture

### Data pipeline (nightly GitHub Actions)

```
Collectors (Python scripts)
    │
    ├── github_collector.py
    │     - GitHub Search API: find repos with AI SDK dependencies
    │     - Parse requirements.txt, pyproject.toml, package.json for framework deps
    │     - Parse CLAUDE.md, AGENTS.md, .cursor/rules for agent config signals
    │     - Extract org from repo owner; map to org profile
    │     - Rate limit: 5000 req/hr authenticated; use GraphQL for batching
    │
    ├── huggingface_collector.py
    │     - HuggingFace Hub API: scan model cards for org affiliation, base model, framework
    │     - Focus: fine-tuned models from non-lab orgs (evidence of internal AI investment)
    │
    ├── jobs_collector.py
    │     - Target: publicly accessible job board APIs / structured feeds
    │     - Initially: Greenhouse API (many startups use it, structured JSON)
    │     - Parse for agentic AI skill terms (see SIGNAL_TERMS below)
    │     - Map employer → org profile
    │
    └── eu_aiact_collector.py  (placeholder — registry goes live Aug 2026)
          - EU AI Act public registry scraper (when available)

Signal Store (JSON files in /data/)
    │
    ├── orgs/         {org_slug}.json  — org profile + signal history
    ├── signals/      {YYYY-MM-DD}.jsonl — raw signal feed, one per line
    ├── frameworks/   {framework_slug}.json — framework adoption over time
    └── sectors/      {sector_slug}.json — sector aggregate views

Static Site (11ty)
    │
    ├── Homepage / dashboard (live stats + signal feed)
    ├── /org/[slug]   — individual org profiles
    ├── /tech/[slug]  — per-framework adoption view
    ├── /sectors      — sector explorer
    ├── /signals      — full filterable signal feed
    └── /methodology  — transparency page
```

### Technology choices
- **Pipeline**: Python, GitHub Actions (nightly cron)
- **Data storage**: JSON/JSONL flat files committed to repo (no database needed at this scale)
- **Site framework**: 11ty (matches ACW stack you're already familiar with)
- **Hosting**: GitHub Pages
- **Styling**: Vanilla CSS, no framework — the design is intentional and doesn't need Bootstrap

---

## Signal taxonomy

### Framework signals (dependency file hits)

```python
FRAMEWORK_SIGNALS = {
    "langgraph":          ["langgraph"],
    "openai_agents_sdk":  ["openai-agents", "openai_agents"],
    "autogen":            ["pyautogen", "autogen-agentchat", "autogen-core"],
    "crewai":             ["crewai"],
    "llamaindex":         ["llama-index", "llama_index", "llama-index-core"],
    "dify":               ["dify-client"],
    "mastra":             ["@mastra/core"],
    "n8n":                ["n8n"],  # package.json only
    "pydantic_ai":        ["pydantic-ai"],
    "smolagents":         ["smolagents"],
}

MODEL_PROVIDER_SIGNALS = {
    "anthropic":  ["anthropic"],
    "openai":     ["openai"],
    "google":     ["google-generativeai", "google-genai", "vertexai"],
    "mistral":    ["mistral", "mistralai"],
    "self_hosted":["ollama", "vllm", "llama-cpp-python", "ctransformers"],
    "deepseek":   ["deepseek"],  # geopolitical risk flag
}

AGENT_CONFIG_FILES = [
    "CLAUDE.md", "AGENTS.md", ".cursorrules", ".cursor/rules",
    "AGENT_CONFIG.md", "agent.yaml", "agent.yml"
]
```

### Job posting skill terms

```python
AGENTIC_JOB_TERMS = [
    "LangGraph", "LangChain", "AutoGen", "CrewAI", "agentic AI",
    "AI agent", "multi-agent", "MCP server", "Model Context Protocol",
    "OpenAI Agents SDK", "Claude Code", "tool use", "function calling",
    "RAG pipeline", "vector database", "AI orchestration",
]
```

### Confidence scoring

| Signal type | Confidence | Rationale |
|---|---|---|
| `requirements.txt` / `pyproject.toml` hit | High | Explicit declared dependency |
| `package.json` hit | High | Explicit declared dependency |
| `CLAUDE.md` / `AGENTS.md` present | High | Deliberate agent config |
| GitHub repo topic tag | Medium | Self-applied but intentional |
| Job posting skill term | Medium | Leading indicator; doesn't prove deployment |
| HuggingFace model card | Medium | Proves model work; not necessarily agentic |
| PR commit pattern (fingerprinting) | Low | Inferred; can misattribute |

Every org profile page must display confidence levels and link to source evidence. Never present an inferred signal as a confirmed fact.

---

## Data model

### Org profile (`/data/orgs/{slug}.json`)

```json
{
  "slug": "acme-corp",
  "display_name": "Acme Corp",
  "github_org": "acme-corp",
  "sector": "saas",
  "first_detected": "2025-11-03",
  "last_updated": "2026-06-27",
  "frameworks": {
    "langgraph": {
      "confidence": "high",
      "first_seen": "2025-11-03",
      "evidence": [
        {
          "type": "dependency_file",
          "repo": "acme-corp/agent-platform",
          "file": "requirements.txt",
          "url": "https://github.com/acme-corp/agent-platform/blob/main/requirements.txt",
          "detected": "2025-11-03"
        }
      ]
    }
  },
  "model_providers": {
    "anthropic": { "confidence": "high", "evidence": [...] },
    "openai": { "confidence": "medium", "evidence": [...] }
  },
  "job_signals": [
    {
      "title": "Senior AI Engineer",
      "terms_matched": ["LangGraph", "multi-agent"],
      "posted": "2026-05-12",
      "url": "..."
    }
  ],
  "hf_models": [],
  "signal_count": 4,
  "signal_history": [
    { "date": "2025-11-03", "type": "dependency", "framework": "langgraph" },
    { "date": "2026-03-18", "type": "job_posting", "terms": ["LangGraph"] }
  ]
}
```

### Signal feed entry (`/data/signals/{YYYY-MM-DD}.jsonl`)

```json
{"ts": "2026-06-27T02:14:33Z", "org": "acme-corp", "type": "dependency", "framework": "langgraph", "confidence": "high", "repo": "acme-corp/agent-platform", "url": "..."}
```

---

## Site pages

| Route | Template | Data source |
|---|---|---|
| `/` | `index.njk` | Aggregated stats + last 50 signals |
| `/org/[slug]/` | `org.njk` | `/data/orgs/{slug}.json` |
| `/tech/[slug]/` | `tech.njk` | `/data/frameworks/{slug}.json` |
| `/sectors/` | `sectors.njk` | `/data/sectors/*.json` |
| `/signals/` | `signals.njk` | `/data/signals/` (last 7 days) |
| `/methodology/` | `methodology.md` | Static markdown |

---

## Visual design

See `index.html` (the companion prototype) for the visual direction.

Design language: **research terminal** — light cream background, monospaced data, proportional prose for narrative content, a single precise burnt-orange accent (`#C4793A`). Feels like a Bloomberg terminal crossed with a research journal, printed on paper rather than lit on a dark screen. No stock photo hero, no gradient blobs, no card-grid startup aesthetic.

Key design decisions to preserve in 11ty templates (see companion prototype `index.html` for the full token set and reference layout):
- Background: `#FDFAF5`
- Surface: `#F5F0E6`
- Surface 2 (nested/hover): `#EDE8DA`
- Border: `#DDD6C4`
- Border 2 (stronger): `#CFC7B2`
- Text primary: `#1C1A17`
- Text secondary: `#6B6358`
- Text tertiary: `#A09488`
- Accent: `#C4793A` (burnt orange — signal/alert color), accent-dim wash: `#F0E4CC`
- Status colors: green `#3D8C5E` (bg `#E6F2EC`), red `#B84040`, blue `#3A6EA8` (bg `#E6EEF7`)
- Monospace font: `IBM Plex Mono` (data, framework names, signal types)
- Body font: `DM Sans` (prose, labels)
- Display font: `Instrument Serif` italic (wordmark only)
- Confidence indicators: colored dots, never just text

---

## GitHub Actions workflow

```yaml
# .github/workflows/collect.yml
name: Nightly collection
on:
  schedule:
    - cron: '0 2 * * *'   # 2am UTC nightly
  workflow_dispatch:        # manual trigger

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements-pipeline.txt
      - run: python pipeline/github_collector.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - run: python pipeline/huggingface_collector.py
      - run: python pipeline/jobs_collector.py
      - run: python pipeline/build_aggregates.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "data: nightly collection [skip ci]"
          file_pattern: "data/**"
```

---

## Repo structure

```
stackwatch/
├── CLAUDE.md                  ← this file
├── README.md
├── .github/
│   └── workflows/
│       ├── collect.yml        ← nightly data pipeline
│       └── build.yml          ← 11ty build + deploy to GitHub Pages
├── pipeline/
│   ├── github_collector.py
│   ├── huggingface_collector.py
│   ├── jobs_collector.py
│   ├── eu_aiact_collector.py  (stub)
│   ├── build_aggregates.py
│   └── utils.py
├── data/
│   ├── orgs/
│   ├── signals/
│   ├── frameworks/
│   └── sectors/
├── site/
│   ├── _data/
│   ├── _includes/
│   ├── org/
│   ├── tech/
│   ├── sectors/
│   ├── signals/
│   ├── methodology.md
│   └── index.njk
├── static/
│   └── style.css
├── .eleventy.js
├── requirements-pipeline.txt
└── package.json
```

---

## Phase plan

### Phase 1 — Data model + static prototype (Week 1)
- [ ] Finalize org profile JSON schema
- [ ] Build 3–5 hand-curated seed org profiles (well-known tech companies with rich public signals)
- [ ] Ship the 11ty site with static data (no pipeline yet)
- [ ] Homepage, one org profile page, methodology page

### Phase 2 — GitHub collector (Week 2)
- [ ] `github_collector.py`: GitHub Search API → dependency file hits
- [ ] `build_aggregates.py`: roll up org signals to summary stats
- [ ] Wire nightly GitHub Action
- [ ] Target: 50+ orgs in data store

### Phase 3 — HuggingFace + jobs (Week 3)
- [ ] `huggingface_collector.py`: HF Hub API → model card signals
- [ ] `jobs_collector.py`: Greenhouse API → job posting signals
- [ ] Signal feed page live

### Phase 4 — Sector view + framework tracker (Week 4)
- [ ] Sector aggregation + sector explorer page
- [ ] Per-framework adoption page with time series

### Phase 5 — EU AI Act registry (August 2026+)
- [ ] Monitor EU AI Act public registry launch
- [ ] Build `eu_aiact_collector.py` once structure is known

---

## Known limitations (document on /methodology page)

1. **Coverage bias**: the pipeline has good coverage of tech companies and startups with active public GitHub presence. Coverage of defense, healthcare, and finance is thin by design — don't display org profiles for those sectors without a coverage disclaimer.

2. **Production ≠ public**: detecting a framework in a public repo does not prove it's in production. An org may have experimented in a public repo and run something different internally.

3. **Org attribution**: GitHub repo → org mapping can be ambiguous. A repo owned by an individual contributor at Company X is not the same as Company X's official infrastructure.

4. **Freshness**: nightly pipeline means signals are at most 24 hours stale. Framework removal (an org stops using a dependency) is harder to detect than addition — profiles may lag deprecations.

5. **Model provider inference is indirect**: detecting `anthropic` in `requirements.txt` means the SDK is present, not that it's the primary model in production.
