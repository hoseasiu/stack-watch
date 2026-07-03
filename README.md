# StackWatch

AI supply-chain intelligence dashboard — tracks public evidence of agentic AI
adoption across organizations. See [CLAUDE.md](CLAUDE.md) for project scope,
architecture, and data model, and [PLAN.md](PLAN.md) for the phased build plan.

**Live site:** https://hoseasiu.github.io/stack-watch/

## Development

```
npm install
npm run build   # build the static site to _site/
npm run serve   # local dev server with live reload
```

## Data pipeline

The `pipeline/` scripts collect public signals (GitHub dependency files, repo
metadata, etc.) into `data/`, which the site reads at build time.

```
pip install -r requirements-pipeline.txt
python pipeline/github_collector.py     # requires GITHUB_TOKEN env var
python pipeline/build_aggregates.py
```

A nightly GitHub Actions workflow ([`.github/workflows/collect.yml`](.github/workflows/collect.yml))
runs collection and commits updated data; a second workflow
([`.github/workflows/build.yml`](.github/workflows/build.yml)) builds and
deploys the site to GitHub Pages on every push to `main`.
