# TODO

Working notes so we can pick up quickly. Newest context at the top.

## Status (as of 2026-07-03)

Multilingual support shipped to `main` (commit `9241983`): the site builds in
English (canonical) + Afrikaans/isiZulu/isiXhosa. Chrome is translated from
committed `i18n/*.json` catalogs; job content is translated by Claude Haiku 4.5
via the Batch API into `Job.translations` (`pipeline/translate.py`). Filtering,
the language switcher, `hreflang`, and the machine-translation notice are all
verified locally.

**Not yet done:** the committed circular JSON has **no job-content translations
yet** (chrome is translated; per-post titles/requirements/duties fall back to
English). Populating them + deploying is tomorrow's job.

Immediate command to populate the current circular locally (Batch, ~$4-8, async):
```bash
python run.py --pdf "PSV CIRCULAR 23 of 2026.pdf" --enrich --translate
```

---

## Tomorrow

### 1. Optimise the full translation pipeline
- [ ] **Don't re-translate unchanged posts.** Right now `--translate` re-does all
      575 posts × 3 languages every run. Add incremental translation: skip a
      (post, language) whose source text already has a translation (or key by a
      content hash of title+summary+requirements+duties) so weekly runs only
      translate new/changed posts. Biggest cost + latency win.
- [ ] **Confirm prompt-cache hits.** Verify the per-language cached system prompt
      is actually being read (Batch `usage.cache_read_input_tokens`); tune so the
      glossary/rules block stays a stable prefix.
- [ ] **Revisit request granularity** — currently one request per (job, language)
      = 1,725/circular. Measure vs one-request-per-job-all-languages (fewer
      requests, shared context) on cost + quality before changing.
- [ ] **Nguni quality pass.** Expand/curate `GLOSSARY` in `pipeline/translate.py`
      for isiZulu/isiXhosa with a fluent reviewer; spot-check ~10 translated
      adverts. Note: Afrikaans bullet count came out lower than EN in testing
      (16 vs 22) — sentences merged; acceptable but worth watching.
- [ ] **Cost + timing.** Two sequential Batches per run (enrich then translate);
      confirm the CI `timeout-minutes: 120` is enough at full volume, and log the
      actual $ per circular once we have a real run.
- [ ] **Archive size.** Inline translations grow each circular JSON ~70%
      (~3.7MB -> ~6.3MB). Fine for now; revisit if the committed archive gets
      heavy over many weeks (sidecar files or git-lfs are fallbacks).

### 2. Actual deployment
- [ ] Enable GitHub Pages: repo **Settings -> Pages -> Source: GitHub Actions**.
- [ ] Add the **`ANTHROPIC_API_KEY`** repository secret (Settings -> Secrets and
      variables -> Actions).
- [ ] Trigger a manual run: **Actions -> Update vacancies -> Run workflow**
      (`workflow_dispatch`) to enrich + translate + commit + deploy end-to-end.
- [ ] Verify the **live** site: all four language trees, switcher links resolve
      at the real base URL, `hreflang` alternates are absolute-correct under the
      Pages path, MT notice on non-English only, JS-off still works.
- [ ] Decide on a **custom domain** (nicer for sharing) + HTTPS.
- [ ] Sanity-check the deployed payload size per language page (low-bandwidth is
      a hard requirement) and that `static/` isn't bloated by the per-tree copies.

### 3. LinkedIn post / dissemination plan
- [ ] Draft a **LinkedIn post**: what it is (free, fast, low-bandwidth, now in 4
      languages), why (the DPSA circular is a 300-page PDF), and a link + a couple
      of screenshots (English + isiZulu views are a strong before/after).
- [ ] Prepare **demo assets**: screenshots of the switcher, a filtered view, a
      job page; maybe a short screen recording.
- [ ] **Audiences + channels:** public-service job seekers, university/TVET career
      offices, community/NGO networks, civic-tech SA, WhatsApp/Telegram job
      groups, relevant subreddits/Facebook groups.
- [ ] **Framing + disclaimers:** lead with usefulness; be explicit it's an
      independent, unofficial index and English is authoritative (mirror the
      site's own notice). Avoid implying DPSA endorsement.
- [ ] Consider a short **README/landing blurb** aimed at first-time visitors and
      an "about the languages" note (machine-translated, English canonical).

---

## Backlog / smaller
- [ ] Pre-existing latent issues left untouched during the i18n work (fix
      separately to keep diffs clean): `soon` var never passed into `job_row`
      (inert "Closes soon" tag), and the missing `#result-count` element (vacancy
      count never renders). See CLAUDE.md gotchas.
- [ ] CLAUDE.md's design note still says "Georgia serif / cream / sky accent" but
      the live design is green + SA-gold, white ground, system sans-serif
      (redesign commit `32725f8`). Update the design section to match reality.
- [ ] Optionally localise the "Circular N of YYYY" label (kept English as a
      publication name for now).
