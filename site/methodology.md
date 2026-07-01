---
layout: base.njk
title: Methodology
nav: methodology
---
<div class="prose">

# Methodology

StackWatch infers which organizations show public evidence of investing in agentic AI
infrastructure. It is not a security scanner, a product review site, or a vendor
self-disclosure registry — every signal here is inferred from **public** sources, and
every claim is traced back to the evidence that produced it.

## What counts as a signal

- **Dependency file hits** — an AI agent framework (LangGraph, CrewAI, LlamaIndex, etc.)
  or model provider SDK found in a public `requirements.txt`, `pyproject.toml`, or
  `package.json`.
- **Agent config files** — presence of `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, or
  similar deliberate agent-configuration files in a public repo.
- **Job postings** — public job listings (currently sourced from Greenhouse boards)
  mentioning agentic AI skill terms.
- **HuggingFace model cards** — fine-tuned models published by non-lab organizations.

## Confidence levels

| Signal type | Confidence | Rationale |
|---|---|---|
| Dependency file hit | High | Explicit declared dependency |
| Agent config file present | High | Deliberate agent configuration |
| GitHub repo topic tag | Medium | Self-applied but intentional |
| Job posting skill term | Medium | Leading indicator; doesn't prove deployment |
| HuggingFace model card | Medium | Proves model work; not necessarily agentic |

Every signal displayed carries a confidence level and links to the exact source
evidence — never present an inferred signal as a confirmed fact.

## Known limitations

1. **Coverage bias.** The pipeline has good coverage of tech companies and startups
   with an active public GitHub presence. Coverage of defense, healthcare, and finance
   is thin by design — profiles in those sectors are not currently displayed without a
   coverage disclaimer, and organizations outside our public-signal-rich scope may be
   under- or entirely un-represented.

2. **Production ≠ public.** Detecting a framework in a public repo does not prove it's
   running in production. An org may have experimented in a public repo and deployed
   something entirely different internally.

3. **Org attribution is ambiguous.** A repo owned by an individual contributor at
   Company X is not the same as Company X's official infrastructure. StackWatch favors
   org-owned repos over individual repos when mapping signals to organizations.

4. **Freshness lags removal.** Signals are refreshed on a nightly cadence at most, and
   an org dropping a framework is harder to detect than an org adding one — profiles
   may lag behind real-world deprecations.

5. **Model provider inference is indirect.** Detecting `anthropic` or `openai` in a
   dependency file means the SDK is present, not that it's the primary model used in
   production.

## Data & attribution

All data is stored as flat JSON/JSONL files in this repository's `data/` directory and
is fully open. Every org profile links back to the exact source file or job posting
used as evidence.

</div>
