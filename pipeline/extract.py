"""Optional LLM enrichment of parsed jobs, via OpenRouter.

The deterministic parser already fills every field. This step asks the
configured model (``PSVC_MODEL``, default GLM 5.2) to refine the handful of
fields that regex handles poorly: sector ``category``, a clean ``city``,
normalised salary band / level, an ISO ``closing_date``, and a one-line
plain-language ``summary``.

Design notes
------------
* OpenRouter has no batch endpoint, so requests are issued synchronously and
  fanned out over a small thread pool (see ``pipeline/llm.py``).
* Structured output is requested via ``response_format: json_schema``; the
  large, stable system prompt (schema + rules) is identical across requests, so
  only the compact job payload varies.
* Enrichment is best-effort: any job whose result is missing or invalid keeps
  its deterministic values, so the site is never degraded by this step.
* If ``OPENROUTER_API_KEY`` is not available, the whole step is skipped and the
  deterministic jobs are returned unchanged.
"""
from __future__ import annotations

import json
from typing import List, Optional

from . import llm
from .schema import CATEGORIES, Job, enrichment_schema

SYSTEM_PROMPT = (
    "You normalise South African public-service job adverts into structured "
    "data. You are given the raw fields of one advertised post. Return only the "
    "requested JSON.\n\n"
    "Rules:\n"
    "- category: choose the single best sector from this fixed list: "
    + ", ".join(CATEGORIES)
    + ".\n"
    "- city: the specific town/city of the post (e.g. 'Pretoria', 'Mthatha'); "
    "null if the centre names only a province or an office.\n"
    "- salary_level: the numeric OSD/SMS level if stated, else null.\n"
    "- salary_min / salary_max: annual rand amounts as integers (no spaces), "
    "else null. If a single amount, set salary_min and leave salary_max null.\n"
    "- closing_date: ISO 8601 (YYYY-MM-DD) if a date is present, else null.\n"
    "- number_of_posts: integer number of posts advertised (default 1).\n"
    "- is_readvertisement: true only if the advert says it is a re-advertisement.\n"
    "- summary: one plain-English sentence (max 30 words) a job-seeker can scan; "
    "no preamble.\n"
    "Use British English. No emoji."
)


def _job_payload(job: Job) -> str:
    return json.dumps(
        {
            "title": job.title,
            "department": job.department,
            "province": job.province,
            "centre": job.centre,
            "salary_text": job.salary_text[:200],
            "closing_date_text": job.closing_date_text,
            "requirements_excerpt": job.requirements[:400],
            "duties_excerpt": job.duties[:300],
        },
        ensure_ascii=False,
    )


def _apply(job: Job, data: dict) -> None:
    """Merge a validated enrichment result onto a job (deterministic fallback kept)."""
    cat = data.get("category")
    if cat in CATEGORIES:
        job.category = cat
    if data.get("city"):
        job.city = str(data["city"])[:60]
    for attr in ("salary_level", "salary_min", "salary_max", "number_of_posts"):
        val = data.get(attr)
        if isinstance(val, int):
            setattr(job, attr, val)
    if data.get("closing_date"):
        job.closing_date = str(data["closing_date"])
    if isinstance(data.get("is_readvertisement"), bool):
        job.is_readvertisement = data["is_readvertisement"]
    if data.get("summary"):
        job.summary = str(data["summary"]).strip()


def enrich_jobs(
    jobs: List[Job],
    *,
    limit: Optional[int] = None,
    verbose: bool = True,
) -> List[Job]:
    """Enrich jobs in place via concurrent OpenRouter calls. Returns the same list."""
    if not llm.have_credentials():
        if verbose:
            print(
                "[extract] No OPENROUTER_API_KEY found; keeping deterministic "
                "values (site is still complete)."
            )
        return jobs

    targets = jobs[:limit] if limit else jobs
    if verbose:
        print("[extract] enriching %d jobs (model=%s)…" % (len(targets), llm.model_name()))

    def worker(_idx: int, job: Job) -> Optional[dict]:
        return llm.chat_json(
            SYSTEM_PROMPT,
            _job_payload(job),
            enrichment_schema(),
            max_tokens=800,
            schema_name="enrichment",
        )

    results = llm.map_concurrent(worker, targets)
    ok = 0
    for job, data in zip(targets, results):
        if isinstance(data, dict):
            _apply(job, data)
            ok += 1
    if verbose:
        print("[extract] enriched %d/%d jobs." % (ok, len(targets)))
    return jobs


def enrich_sync(jobs: List[Job], *, limit: int = 5, verbose: bool = True) -> List[Job]:
    """Enrich only the first ``limit`` jobs -- a quick local check."""
    return enrich_jobs(jobs, limit=limit, verbose=verbose)
