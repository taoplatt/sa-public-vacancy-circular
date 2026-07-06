# CLAUDE.md

Guidance for working in this repository.

## What this is

A pipeline + static site that turns the weekly **DPSA Public Service Vacancy
Circular** (a 300+ page PDF, ~575 posts) into a fast, mobile-first,
low-bandwidth job-search site with a browsable archive. See `README.md` for the
user-facing overview.

Data flow: `fetch → segment → parse → (enrich) → (translate) → build → deploy`.

The site is multilingual: English is canonical, and it is also rendered into
Afrikaans (`af`), isiZulu (`zu`) and isiXhosa (`xh`) at build time.

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
python run.py --enrich --translate                   # + translate job content to af/zu/xh (Batch)
python run.py --translate --translate-limit 3        # translate 3 jobs synchronously (quick check)
python run.py --translate-ui                          # regenerate i18n/<lang>.json chrome catalogs
python run.py --build-only                           # re-render site/ (all languages) from existing data/

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

Enrichment and translation call **OpenRouter** (an OpenAI-compatible gateway in
front of many models), which reads `OPENROUTER_API_KEY` from the environment.
The model is chosen with `PSVC_MODEL` (any OpenRouter slug; default
`z-ai/glm-5.2`). Two places:

- **Local:** copy `.env.example` to `.env` and paste the key. `run.py` auto-loads
  `.env` (git-ignored). Or `export OPENROUTER_API_KEY=sk-or-...` in your shell.
- **CI:** repo **Settings → Secrets and variables → Actions → New repository
  secret**, named `OPENROUTER_API_KEY`. Optionally set `PSVC_MODEL` as a
  repository **variable** to pin a model. The workflow already references both.

Without a key, `pipeline/extract.py` and `pipeline/translate.py` skip their work
and the site still builds fully from the deterministic parse (in English; the
other-language trees fall back to English content).

OpenRouter has **no batch endpoint**, so both stages issue ordinary synchronous
requests fanned out over a small thread pool (`pipeline/llm.py`, tune with
`PSVC_LLM_CONCURRENCY`). Structured output uses `response_format: json_schema`,
falling back to tolerant JSON parsing for models that don't support it. Note the
default `z-ai/glm-5.2` is a *reasoning* model (heavier per call than a small
translation model); swap `PSVC_MODEL` for something cheaper if cost/latency bites.

**Reasoning is disabled by default** (`llm.py:_reasoning_config`). On a reasoning
model the chain-of-thought consumes the `max_tokens` budget and the JSON answer
truncates to empty -- so these mechanical extract/translate calls send
`reasoning: {enabled: false}`. Re-enable per-deployment with
`PSVC_REASONING_EFFORT=low|medium|high` if a future model needs it.

## Architecture

| File | Role |
|---|---|
| `pipeline/schema.py` | `Job` / `Circular` Pydantic models, category & province vocab, LLM output schema |
| `pipeline/fetch.py` | Discover + download the newest circular PDF from DPSA |
| `pipeline/segment.py` | `pdftotext -layout` → one raw text block per post (+ inherited dept context) |
| `pipeline/parse.py` | Raw block → complete `Job` (deterministic; no API call) |
| `pipeline/llm.py` | OpenRouter client: structured `chat_json`, plain `chat_text`, and a `map_concurrent` fan-out; reads `OPENROUTER_API_KEY` / `PSVC_MODEL` |
| `pipeline/extract.py` | Optional LLM enrichment (via `llm.py`), merged onto parsed jobs |
| `pipeline/translate.py` | Optional LLM translation (af/zu/xh) into `Job.translations`; also `--translate-ui` for the chrome catalogs |
| `pipeline/build.py` | Jinja2 → static `site/`, once per language (en at root, `af`/`zu`/`xh` subtrees) |
| `run.py` | Orchestrator + `.env` loader |
| `templates/`, `static/` | Jinja2 templates; `style.css` + `filter.js` |
| `i18n/` | Chrome message catalogs: `en.json` (hand-authored source) + `af`/`zu`/`xh` (generated, editable) |

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
  archive). `site/` and `data/raw/` are git-ignored and regenerated. Job
  translations live **inline** in those JSON files (under `Job.translations`).
- **Multilingual gotchas:**
  - **Filter machinery stays English on every language tree.** In
    `templates/_macros.html`, all `data-*` attributes, `data-search`, and
    `<option value>`s use the canonical English category/province/department
    values, because `filter.js` does exact-string equality. Only the *display*
    text is localised (via the `category`/`province` maps in the catalog). Never
    translate a filter value or a `data-*` attribute.
  - **Catalog fallback:** `build.py:_load_catalog` overlays `i18n/<lang>.json`
    on `i18n/en.json`, so a missing key falls back to English — never a
    `KeyError`. `en.json` is the source of truth; regenerate the others with
    `--translate-ui` when you change it.
  - **Bullet-punctuation coupling:** `build.py:_sentence_items` splits
    `requirements`/`duties` into bullets on `.`/`;` boundaries. The translation
    prompt (and the `translation_schema` field descriptions) instruct the model
    to preserve sentence-ending punctuation; if a translation drops it, the
    field degrades to a single paragraph (graceful, never an error).
  - Each language is a **self-contained tree** with its own `static/` copy;
    cross-tree links are only the language switcher, whose relative hrefs
    `build.py:_alternates` computes per page (English sits one level shallower
    than `af`/`zu`/`xh`). No absolute paths — the site stays relocatable.
- **Design = Hillian system.** Green `#1E3A2B` / cream `#F4EEDF` / one sky accent
  `#8FBBD9`; Georgia serif everywhere (system font — do **not** add web fonts);
  sentence-case headings; British English; **no em dashes**, no emoji. Tokens
  are inlined at the top of `static/style.css`.
- **Low-bandwidth is a hard requirement.** Cards are server-rendered so the site
  works with JS off; `filter.js` is progressive enhancement only. Keep payloads
  tiny — no frameworks, no images (inline SVG icons only).

## Deploy

`.github/workflows/update.yml` runs weekly (+ manual dispatch): fetch → enrich →
translate → commit new `data/circulars` JSON (translations included inline) →
deploy `site/` to GitHub Pages. Enable Pages (Settings → Pages → Source: GitHub
Actions) and add the `OPENROUTER_API_KEY` secret. The `i18n/` chrome catalogs are
committed and regenerated manually with `--translate-ui`, not on every run.

**Custom domain.** Set the `CUSTOM_DOMAIN` repo **variable** (Settings → Secrets
and variables → Actions → Variables) to the bare host, e.g. `jobs.example.com`.
The workflow passes it as `PSVC_DOMAIN`, and `build.py` writes `site/CNAME` so
the domain survives every deploy. Also set the same domain in Settings → Pages
(so GitHub provisions the TLS cert and enforces HTTPS) and add the DNS records at
your registrar: a **subdomain** → one `CNAME` to `taoplatt.github.io`; an
**apex** → GitHub's four `A` records (185.199.108–111.153) plus a `www` CNAME.
