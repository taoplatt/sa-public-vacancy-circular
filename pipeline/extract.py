"""Optional LLM enrichment of parsed jobs, via the Claude Message Batches API.

The deterministic parser already fills every field. This step asks Claude
(Haiku 4.5) to refine the handful of fields that regex handles poorly:
sector ``category``, a clean ``city``, normalised salary band / level, an ISO
``closing_date``, and a one-line plain-language ``summary``.

Design notes
------------
* Uses the **Batch API** (50% cost, async) — a natural fit for a weekly run.
* A large, stable system prompt (schema + rules) is **prompt-cached**; the only
  per-request variation is the compact job payload, keeping input cost low.
* Enrichment is best-effort: any job whose result is missing or invalid keeps
  its deterministic values, so the site is never degraded by this step.
* If ``ANTHROPIC_API_KEY`` / an ``ant`` profile is not available, the whole
  step is skipped and the deterministic jobs are returned unchanged.
"""
from __future__ import annotations

import json
import os
import time
from typing import List, Optional

from .schema import CATEGORIES, Job, enrichment_schema

MODEL = "claude-haiku-4-5"

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


def _has_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # An `ant auth login` profile also works with a zero-arg client.
    import shutil

    return shutil.which("ant") is not None


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


def _request_params(job: Job) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 400,
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": _job_payload(job)}],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": enrichment_schema(),
            }
        },
    }


def enrich_jobs(
    jobs: List[Job],
    *,
    limit: Optional[int] = None,
    poll_seconds: int = 30,
    verbose: bool = True,
) -> List[Job]:
    """Enrich jobs in place via the Batch API. Returns the same list."""
    if not _has_credentials():
        if verbose:
            print(
                "[extract] No ANTHROPIC_API_KEY / ant profile found; "
                "keeping deterministic values (site is still complete)."
            )
        return jobs

    try:
        import anthropic
    except ImportError:
        if verbose:
            print("[extract] anthropic SDK not installed; skipping enrichment.")
        return jobs

    targets = jobs[:limit] if limit else jobs
    client = anthropic.Anthropic()

    # Key by list index, not post_number: a circular can repeat a post number
    # across annexures, and Batch custom_ids must be unique within a batch.
    requests = [
        {"custom_id": str(i), "params": _request_params(job)}
        for i, job in enumerate(targets)
    ]
    if verbose:
        print("[extract] submitting batch of %d jobs (model=%s)…" % (len(requests), MODEL))
    batch = client.messages.batches.create(requests=requests)

    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        if verbose:
            print("[extract] batch %s: %s" % (batch.id, b.processing_status))
        time.sleep(poll_seconds)

    ok = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            continue
        try:
            idx = int(result.custom_id)
        except ValueError:
            continue
        if not 0 <= idx < len(targets):
            continue
        job = targets[idx]
        msg = result.result.message
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        _apply(job, data)
        ok += 1
    if verbose:
        print("[extract] enriched %d/%d jobs." % (ok, len(targets)))
    return jobs


def enrich_sync(jobs: List[Job], *, limit: int = 5, verbose: bool = True) -> List[Job]:
    """Synchronous enrichment of a few jobs, for local testing without batching."""
    if not _has_credentials():
        if verbose:
            print("[extract] No credentials; skipping sync enrichment.")
        return jobs
    import anthropic

    client = anthropic.Anthropic()
    for job in jobs[:limit]:
        params = _request_params(job)
        msg = client.messages.create(**params)
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        try:
            _apply(job, json.loads(text))
        except json.JSONDecodeError:
            pass
    return jobs
