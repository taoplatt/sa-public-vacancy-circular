# TODO

Working notes so we can pick up quickly. Newest context at the top.

## Status (2026-07-06): LLM stages moved to OpenRouter + custom-domain wired

**Provider migration (done, in code).** Enrich + translate no longer use the
Anthropic Message Batches API. New `pipeline/llm.py` is a thin OpenRouter client
(OpenAI-compatible `/chat/completions`): structured `chat_json` (via
`response_format: json_schema`, with a graceful fallback + tolerant JSON parse),
plain `chat_text` for the UI catalogs, and a `map_concurrent` thread-pool
fan-out that replaces Batch. `extract.py` / `translate.py` were rewritten on top
of it (gap-fill retry kept); `anthropic` dropped from `requirements.txt`.
- Env key is now `OPENROUTER_API_KEY` (was `ANTHROPIC_API_KEY`); model via
  `PSVC_MODEL` (default `z-ai/glm-5.2`), concurrency via `PSVC_LLM_CONCURRENCY`.
- Deterministic-first invariant preserved: no key -> stages skip, site builds.
  Verified `--build-only` -> 4 langs, 2316 pages, 575 jobs.
- Workflow updated: `secrets.OPENROUTER_API_KEY` + `vars.PSVC_MODEL`.
- **Live smoke test passed** (2026-07-06, GLM 5.2): enrich returns clean JSON;
  af + zu translations both succeed 2/2. IMPORTANT gotcha found + fixed: GLM 5.2
  is a *reasoning* model, and reasoning tokens ate the `max_tokens` budget so the
  JSON came back empty (enrich 0/1, translate 0/2). Fix: `llm.py` now sends
  `reasoning: {enabled: false}` by default (override `PSVC_REASONING_EFFORT`);
  token ceilings nudged up (enrich 800, translate 6000, gap-fill 10000).
- Still heavier/slower per call than Haiku across ~2,300 requests/circular --
  measure cost + timing on the first full run, swap `PSVC_MODEL` if it bites.
  Partially addresses section 1's cheaper-model goal (flexibility done; $ TBD).

**Custom domain (repo side wired; domain not registered yet).** `build.py` now
writes `site/CNAME` from `PSVC_DOMAIN`; workflow passes `vars.CUSTOM_DOMAIN`.
Verified locally (CNAME at root only, not in language subtrees).

**Action items for the user (both changes):**
- [x] Add the `OPENROUTER_API_KEY` **repo secret**. DONE 2026-07-06 (set via
      `gh secret set` from the local `.env`). The full enrich+translate path is
      not yet exercised on CI: the skip guard means a dispatch only processes a
      *new* circular, and 23/2026 is already archived -- so the next new circular
      (or a `--force` run) is the first CI run that spends OpenRouter credit.
      The old `ANTHROPIC_API_KEY` repo secret is now unused and can be deleted.
- [ ] Register a domain, set `CUSTOM_DOMAIN` repo var + the same domain in
      Settings -> Pages (for HTTPS), and add DNS (subdomain -> CNAME to
      `taoplatt.github.io`; apex -> GitHub's four A records 185.199.108-111.153).

---

## Status (as of 2026-07-04)

Multilingual support shipped to `main` (commit `9241983`): the site builds in
English (canonical) + Afrikaans/isiZulu/isiXhosa. Chrome is translated from
committed `i18n/*.json` catalogs; job content is translated by Claude Haiku 4.5
via the Batch API into `Job.translations` (`pipeline/translate.py`). Filtering,
the language switcher, `hreflang`, and the machine-translation notice are all
verified locally.

**Done (2026-07-04): circular 23 of 2026 is fully enriched AND translated.**
All 575 posts enriched (category/city/salary/summary) and all **1725/1725**
translation units (575 posts x af/zu/xh) populated inline under
`Job.translations`. Two commits: `b9ae844` (bug fix, below) and `0207b62`
(the populated JSON). Site rebuilds clean (4 languages, 2316 pages).

Ran with: `python run.py --pdf "PSV CIRCULAR 23 of 2026.pdf" --enrich --translate`.

Bug found + fixed along the way: a circular can **reuse a post number across
annexures** (23/287 appears twice in this one), which crashed the Batch API
(duplicate `custom_id`) and would have silently collapsed the duplicate when
mapping results back. `extract.py` and `translate.py` now key Batch requests by
**list index**, not post_number (commit `b9ae844`).

Two operational notes from the first real run:
- Batches lose ~1-2% of requests to transient failures (we saw 25/1725); they
  fall back to English gracefully. A one-off synchronous gap-fill (higher
  `max_tokens` for long posts) filled the rest. See the "self-healing" item below.
- The Anthropic **API credit balance gates every run** (enrich + translate) --
  keep it funded for the weekly CI job.

**Next: deployment (section 2).**

---

## Tomorrow

### 1. Optimise the full translation pipeline
- [~] **Move off Claude Haiku to a much cheaper / open-source model (COST PRIORITY).**
      Provider is now OpenRouter (model = `PSVC_MODEL`, default GLM 5.2); see the
      2026-07-06 status. Remaining: measure real $/circular and settle on the
      cheapest model that keeps isiZulu/isiXhosa quality. The constraints below
      still apply to whatever model is chosen.
      Full enrich+translate was ~$8/circular on Haiku Batch. Goal: cut this hard,
      ideally to ~free / self-hosted. Constraints from the earlier free-MT
      discussion:
      - The African languages gate the choice: isiZulu/isiXhosa rule out
        LibreTranslate/Argos (no zu/xh models). Real options: self-hosted **Meta
        NLLB** (open, strong zu/xh, compute-only), the Google web endpoint (flaky
        at volume, ToS-grey), or a small open LLM (Qwen/Llama) for enrich + NLLB
        for translate.
      - A raw MT model will NOT preserve what the Haiku prompt currently guards:
        verbatim reference numbers / dates / department + place names, and
        sentence boundaries (the `.`/`;` bullet split in `build.py`). Plan for
        entity-masking pre/post-processing, not a straight swap.
      - Enrichment (category/city/salary/summary) can likely move to a cheap
        local model, or tighten the deterministic parse so it needs less LLM.
      - Keep the deterministic-first invariant: the site must still build with no
        model at all.
- [x] **Self-healing gap-fill (batch retries).** DONE (commit `312b63f`).
      `translate_jobs` now retries the missing (post, language) pairs
      synchronously after the batch (larger `max_tokens` for long posts), so
      weekly runs reach ~100% unattended. No-op when the batch already covered
      everything; best-effort on failure.
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
**LIVE (2026-07-04): https://taoplatt.github.io/sa-public-vacancy-circular/**
Deployed the verified 100% build via a `build_only` workflow_dispatch (no API
spend). All four language trees serve HTTP 200; translations, `hreflang` and the
MT notice verified on the live site.
- [x] Enable GitHub Pages (Source: GitHub Actions) -- done via API (`build_type=workflow`).
- [x] **Add the `OPENROUTER_API_KEY` repository secret.** DONE 2026-07-06 (set
      via `gh secret set` from the local `.env`); the weekly scheduled run can now
      enrich/translate a new circular. The old `ANTHROPIC_API_KEY` secret is set
      but now unused (pipeline moved to OpenRouter 2026-07-06) and can be deleted.
      Historical note: before the secret was set,
      a scheduled run builds any new circular English-only; existing committed
      translations still serve, so nothing breaks. NOTE: the skip guard (commit
      `6750924`) now makes the weekly cron a cheap no-op until a genuinely new
      circular is published, so setting the secret no longer risks ~$8/week of
      churn -- it only spends when there is new work.
- [~] Trigger a manual run end-to-end: `build_only` deploy done + live. The FULL
      enrich+translate+commit+deploy path is not exercised yet -- it runs on the
      weekly cron (or a normal dispatch) once the secret is set.
- [x] Verify the live site: four language trees, `hreflang` alternates
      (en/af/xh/zu/x-default), MT notice on non-English only, job pages load,
      JS-off works (cards are server-rendered).
- [~] **Custom domain** (nicer for sharing) + HTTPS. Repo side wired 2026-07-06:
      `build.py` emits `site/CNAME` from `PSVC_DOMAIN`; workflow passes
      `vars.CUSTOM_DOMAIN`. Remaining: register the domain, set `CUSTOM_DOMAIN` +
      the domain in Settings -> Pages + DNS records. (Pages already enforces
      HTTPS on the github.io URL.)
- [x] Payload sanity (low-bandwidth): index ~36-47KB gzipped, job pages ~5.5KB,
      css 4KB + js 2.2KB. Index raw ~480KB but served gzipped and renders all 575
      cards for JS-off -- revisit with pagination only if it grows.

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
