# Public Service Vacancies (South Africa)

A pipeline and static website that turns the weekly **DPSA Public Service
Vacancy Circular** (a 300+ page PDF published at
[dpsa.gov.za/newsroom/psvc](https://www.dpsa.gov.za/newsroom/psvc/)) into a
fast, mobile-first, low-bandwidth job-search site with a browsable archive.

Each circular contains ~500 advertised government posts. The raw PDF is hard to
search and heavy to open on a phone; this project republishes the same
vacancies as light, static, searchable pages.

## How it works

```
fetch → segment → parse → (enrich) → build → deploy
```

1. **fetch** (`pipeline/fetch.py`) — finds the newest circular on the DPSA site
   (it follows the per-circular sub-page to the combined PDF) and downloads it.
2. **segment** (`pipeline/segment.py`) — runs `pdftotext -layout` and a state
   machine that splits the PDF into one text block per post, tracking
   department/province and inheriting department-level closing date /
   applications / notes. Field labels sit at column 0, so boundaries are exact.
3. **parse** (`pipeline/parse.py`) — turns each block into a complete `Job`
   record: title, reference, salary + level + band, location, closing date
   (ISO), sector, requirements, duties, how to apply. Fully deterministic, so
   the site is complete with no API call.
4. **enrich** (`pipeline/extract.py`, optional) — Claude **Haiku 4.5** via the
   **Message Batches API** refines the fields regex handles poorly (sector,
   city, salary band, ISO date) and writes a one-line summary. Best-effort: any
   job it can't improve keeps its deterministic values. Skipped automatically
   when no API key is present.
5. **build** (`pipeline/build.py`) — Jinja2 renders a static site: a landing
   page for the latest circular (search + filters + cards), a detail page per
   post, and a browsable archive of every circular processed.

The visual language is the **Hillian design system** — a green/cream palette
with one sky accent, Georgia serif throughout (a system font, so **no web fonts
are downloaded**), hairline rules and generous whitespace.

## Low-bandwidth by design

- The whole ~500-job landing page is **~35 KB gzipped**; CSS ~2.7 KB, JS ~1.4 KB.
- Every card is **server-rendered**, so the site works with **JavaScript off**
  (all jobs visible, browser find works). Filtering/sorting is a ~4 KB
  progressive enhancement.
- No web fonts, no images (inline SVG icons only), no frameworks.

## Running it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # needs poppler's pdftotext on PATH

python run.py --pdf "PSV CIRCULAR 23 of 2026.pdf"   # process a local PDF
python run.py                                        # fetch the newest circular
python run.py --enrich                               # + LLM enrichment (needs ANTHROPIC_API_KEY)
python run.py --enrich --sync-limit 5                # enrich 5 jobs synchronously (quick test)
python run.py --build-only                           # rebuild the site from data/

python -m http.server -d site                        # preview at http://localhost:8000
```

- Extracted data is written to `data/circulars/circular-<n>-<year>.json`
  (committed; the archive's source of truth).
- The site is rendered to `site/` (git-ignored; built + deployed by CI).

## Deployment

`.github/workflows/update.yml` runs weekly (and on demand): it fetches the
newest circular, enriches with Claude (using the `ANTHROPIC_API_KEY` repo
secret), commits the new JSON to the archive, and deploys `site/` to GitHub
Pages. Enable Pages (Settings → Pages → Source: GitHub Actions) and add the
secret to activate enrichment; without it the site still builds from the
deterministic parse.

## Layout

```
pipeline/   fetch, segment, parse, extract, build, schema
templates/  Jinja2: base, listing, job, archive, about, 404, _macros
static/     style.css (Hillian tokens inlined), filter.js
data/       raw/ (PDFs, ignored) · circulars/ (extracted JSON, committed)
run.py      orchestrator
```

## Disclaimer

This is an independent, unofficial index. Always apply to the department named
in each advert, by its stated closing date, quoting its reference number. Where
anything here differs from the official circular, the circular is authoritative.
