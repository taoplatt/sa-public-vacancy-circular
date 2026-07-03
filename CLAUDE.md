# CLAUDE.md

Guidance for working in this repository.

## What this is

A pipeline + static site that turns the weekly **DPSA Public Service Vacancy
Circular** (a 300+ page PDF, ~575 posts) into a fast, mobile-first,
low-bandwidth job-search site with a browsable archive. See `README.md` for the
user-facing overview.

Data flow: `fetch → segment → parse → (enrich) → build → deploy`.

## Commands

```bash
# One-time setup
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # requires poppler's `pdftotext` on PATH

# Run the pipeline (writes data/circulars/*.json, then builds site/)
python run.py --pdf "PSV CIRCULAR 23 of 2026.pdf"   # process a local PDF
python run.py                                        # fetch the newest circular from DPSA
python run.py --enrich                               # + Claude Batch enrichment (needs API key)
python run.py --enrich --sync-limit 5                # enrich 5 jobs synchronously (quick check)
python run.py --build-only                           # re-render site/ from existing data/

# Preview
python -m http.server -d site 8099                   # http://localhost:8099
```

There is no test suite yet. Validate changes by running the pipeline on the
bundled PDF and eyeballing counts + a few records, e.g.:

```bash
python -c "from pipeline.segment import segment_pdf; from pipeline.parse import parse_all; \
jobs=parse_all(segment_pdf('PSV CIRCULAR 23 of 2026.pdf')); print(len(jobs),'jobs')"
```

## The API key

The Anthropic SDK reads `ANTHROPIC_API_KEY` from the environment. Two places:

- **Local:** copy `.env.example` to `.env` and paste the key. `run.py` auto-loads
  `.env` (git-ignored). Or `export ANTHROPIC_API_KEY=sk-ant-...` in your shell.
- **CI:** repo **Settings → Secrets and variables → Actions → New repository
  secret**, named `ANTHROPIC_API_KEY`. The workflow already references it.

Without a key, `pipeline/extract.py` skips enrichment and the site still builds
fully from the deterministic parse.

## Architecture

| File | Role |
|---|---|
| `pipeline/schema.py` | `Job` / `Circular` Pydantic models, category & province vocab, LLM output schema |
| `pipeline/fetch.py` | Discover + download the newest circular PDF from DPSA |
| `pipeline/segment.py` | `pdftotext -layout` → one raw text block per post (+ inherited dept context) |
| `pipeline/parse.py` | Raw block → complete `Job` (deterministic; no API call) |
| `pipeline/extract.py` | Optional Claude Haiku 4.5 Batch enrichment, merged onto parsed jobs |
| `pipeline/build.py` | Jinja2 → static `site/` (index, per-job, per-circular, archive, about, 404) |
| `run.py` | Orchestrator + `.env` loader |
| `templates/`, `static/` | Jinja2 templates; `style.css` + `filter.js` |

## Conventions & gotchas

- **Deterministic-first extraction.** The parse produces complete records on its
  own; the LLM only refines `category`, `city`, salary band, ISO date, and
  `summary` (`_apply()` merges, never replaces wholesale). Keep this property:
  the site must build correctly with no API key.
- **Python 3.9 locally.** Use `from __future__ import annotations`; no
  `match`/`case`. (CI uses 3.12.)
- **Segmentation invariant:** in `pdftotext -layout` output, **field labels
  (POST/SALARY/CENTRE/…) sit at column 0**; continuations and headings are
  indented. Department-level `CLOSING DATE`/`APPLICATIONS`/`NOTE` before the
  first POST inherit to that department's posts. If parsing regresses, re-check
  this first.
- **DPSA discovery:** the index links to per-circular **sub-pages**
  (`/newsroom/psvc/circular-<n>-of-<year>/`); the combined PDF on that page is
  named like `PSV CIRCULAR 23 of 2026.pdf` (per-annexure splits are `a.pdf`…).
- **Source of truth vs generated:** `data/circulars/*.json` is committed (the
  archive). `site/` and `data/raw/` are git-ignored and regenerated.
- **Design = Hillian system.** Green `#1E3A2B` / cream `#F4EEDF` / one sky accent
  `#8FBBD9`; Georgia serif everywhere (system font — do **not** add web fonts);
  sentence-case headings; British English; **no em dashes**, no emoji. Tokens
  are inlined at the top of `static/style.css`.
- **Low-bandwidth is a hard requirement.** Cards are server-rendered so the site
  works with JS off; `filter.js` is progressive enhancement only. Keep payloads
  tiny — no frameworks, no images (inline SVG icons only).

## Deploy

`.github/workflows/update.yml` runs weekly (+ manual dispatch): fetch → enrich →
commit new `data/circulars` JSON → deploy `site/` to GitHub Pages. Enable Pages
(Settings → Pages → Source: GitHub Actions) and add the `ANTHROPIC_API_KEY`
secret.
