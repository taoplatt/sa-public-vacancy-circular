"""Optional machine translation of parsed jobs into South Africa's languages.

The deterministic parse (and optional enrichment) produce complete English
records. This step asks Claude (Haiku 4.5) to translate the four free-text
fields of each post -- ``title``, ``summary``, ``requirements`` and ``duties`` --
into Afrikaans, isiZulu and isiXhosa. English stays the canonical source; the
translations are merged onto each ``Job`` under ``job.translations[lang]``.

Design notes (mirrors ``pipeline/extract.py``)
---------------------------------------------
* Uses the **Batch API** (50% cost, async) -- a natural fit for the weekly run.
  One request per (job, language): bounded output, per-language cached prompt,
  and a failure in one language never costs the others.
* A large, stable system prompt (glossary + rules) is **prompt-cached** per
  language; only the compact job payload varies per request.
* Best-effort: any post whose result is missing or invalid keeps English (the
  render falls back field-by-field), so the site is never degraded by this step.
* If ``ANTHROPIC_API_KEY`` / an ``ant`` profile is not available, the whole step
  is skipped and the jobs are returned unchanged.

Verbatim policy: reference/post numbers, salaries, dates, addresses
(enquiries/applications/notes) and department names are **not** translated --
they never enter the payload -- so they always read in the official English.
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from .schema import Job, JobTranslation, translation_schema

MODEL = "claude-haiku-4-5"

# English is the canonical source and is never translated.
TARGET_LANGUAGES = ["af", "zu", "xh"]

LANGUAGE_NAMES = {"af": "Afrikaans", "zu": "isiZulu", "xh": "isiXhosa"}

# Recurring public-service terms pinned per language so every post uses the same
# word. Guidance for the model, not a hard rule -- it may deviate where context
# clearly demands it.
GLOSSARY: Dict[str, Dict[str, str]] = {
    "af": {
        "department": "departement",
        "requirements": "vereistes",
        "duties": "pligte",
        "closing date": "sluitingsdatum",
        "salary": "salaris",
        "level": "vlak",
        "reference": "verwysing",
        "centre": "sentrum",
        "post": "pos",
        "enquiries": "navrae",
    },
    "zu": {
        "department": "umnyango",
        "requirements": "izidingo",
        "duties": "imisebenzi",
        "closing date": "usuku lokuvala",
        "salary": "iholo",
        "level": "izinga",
        "reference": "inkomba",
        "centre": "isikhungo",
        "post": "isikhundla",
        "enquiries": "imibuzo",
    },
    "xh": {
        "department": "isebe",
        "requirements": "iimfuno",
        "duties": "imisebenzi",
        "closing date": "umhla wokuvala",
        "salary": "umvuzo",
        "level": "inqanaba",
        "reference": "isalathiso",
        "centre": "iziko",
        "post": "isithuba",
        "enquiries": "imibuzo",
    },
}


def _glossary_block(lang: str) -> str:
    pairs = GLOSSARY.get(lang, {})
    if not pairs:
        return ""
    lines = "\n".join("- %s -> %s" % (en, tr) for en, tr in pairs.items())
    return (
        "Use these translations for recurring terms, unless context clearly "
        "requires otherwise:\n" + lines + "\n\n"
    )


def _system_prompt(lang: str) -> str:
    name = LANGUAGE_NAMES.get(lang, lang)
    return (
        "You translate South African public-service job adverts from English "
        "into %s. You are given the free-text fields of one advertised post. "
        "Return only the requested JSON.\n\n" % name
        + _glossary_block(lang)
        + "Rules:\n"
        "- Translate the meaning naturally and in a plain, formal register; do "
        "not translate word-for-word.\n"
        "- Keep the following EXACTLY as in the English source, untranslated and "
        "un-transliterated: numbers, rand amounts, dates, closing dates, "
        "reference numbers, post numbers, salary levels, email addresses, URLs, "
        "phone numbers, department names, and place/town/city names.\n"
        "- In requirements and duties, keep the same sentence boundaries as the "
        "English: end each sentence with a full stop or semicolon and start each "
        "with a capital letter. Do not merge sentences or drop the punctuation "
        "between them.\n"
        "- No preamble, no notes, no emoji. Return the translation only."
    )


def _job_payload(job: Job) -> str:
    """The four translatable fields, in full (no truncation)."""
    return json.dumps(
        {
            "title": job.title,
            "summary": job.summary or "",
            "requirements": job.requirements,
            "duties": job.duties,
        },
        ensure_ascii=False,
    )


def _has_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # An `ant auth login` profile also works with a zero-arg client.
    import shutil

    return shutil.which("ant") is not None


def _apply(job: Job, lang: str, data: dict) -> None:
    """Merge one language's validated translation onto a job (best-effort)."""
    tr = job.translations.get(lang) or JobTranslation()
    for attr in ("title", "summary", "requirements", "duties"):
        val = data.get(attr)
        if isinstance(val, str) and val.strip():
            setattr(tr, attr, val.strip())
    job.translations[lang] = tr


def _request_params(job: Job, lang: str) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 4000,
        "system": [
            {
                "type": "text",
                "text": _system_prompt(lang),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": _job_payload(job)}],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": translation_schema(),
            }
        },
    }


def _custom_id(job: Job, lang: str) -> str:
    # post_number is unique per circular; "__<lang>" disambiguates the language.
    return "%s__%s" % (job.post_number.replace("/", "_"), lang)


def translate_jobs(
    jobs: List[Job],
    *,
    languages: Optional[List[str]] = None,
    limit: Optional[int] = None,
    poll_seconds: int = 30,
    verbose: bool = True,
) -> List[Job]:
    """Translate jobs in place via the Batch API. Returns the same list."""
    languages = languages or TARGET_LANGUAGES
    if not _has_credentials():
        if verbose:
            print(
                "[translate] No ANTHROPIC_API_KEY / ant profile found; "
                "keeping English only (site still builds, falls back to English)."
            )
        return jobs

    try:
        import anthropic
    except ImportError:
        if verbose:
            print("[translate] anthropic SDK not installed; skipping translation.")
        return jobs

    targets = jobs[:limit] if limit else jobs
    client = anthropic.Anthropic()

    requests = [
        {"custom_id": _custom_id(job, lang), "params": _request_params(job, lang)}
        for job in targets
        for lang in languages
    ]
    if verbose:
        print(
            "[translate] submitting batch of %d requests (%d jobs x %d languages, "
            "model=%s)..." % (len(requests), len(targets), len(languages), MODEL)
        )
    batch = client.messages.batches.create(requests=requests)

    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        if verbose:
            print("[translate] batch %s: %s" % (batch.id, b.processing_status))
        time.sleep(poll_seconds)

    by_id: Dict[str, Job] = {job.post_number.replace("/", "_"): job for job in targets}
    ok = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            continue
        try:
            key, lang = result.custom_id.rsplit("__", 1)
        except ValueError:
            continue
        job = by_id.get(key)
        if not job:
            continue
        msg = result.result.message
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        _apply(job, lang, data)
        ok += 1
    if verbose:
        print("[translate] translated %d/%d requests." % (ok, len(requests)))
    return jobs


def translate_sync(
    jobs: List[Job],
    *,
    languages: Optional[List[str]] = None,
    limit: int = 5,
    verbose: bool = True,
) -> List[Job]:
    """Synchronous translation of a few jobs, for local testing without batching."""
    languages = languages or TARGET_LANGUAGES
    if not _has_credentials():
        if verbose:
            print("[translate] No credentials; skipping sync translation.")
        return jobs
    import anthropic

    client = anthropic.Anthropic()
    for job in jobs[:limit]:
        for lang in languages:
            params = _request_params(job, lang)
            msg = client.messages.create(**params)
            text = next((blk.text for blk in msg.content if blk.type == "text"), "")
            try:
                _apply(job, lang, json.loads(text))
            except json.JSONDecodeError:
                pass
    return jobs


# ---------------------------------------------------------------------------
# UI (chrome) catalog translation
# ---------------------------------------------------------------------------
# One small synchronous call per language translates the whole English chrome
# catalog (i18n/en.json). Run only when the English strings change; the output
# is committed and hand-editable.
_UI_SYSTEM = (
    "You translate the user-interface text of a South African public-service "
    "job website from English into %s. You are given a JSON object of English "
    "strings. Return a JSON object with EXACTLY the same keys and nesting, "
    "translating only the string values.\n\n"
    "Rules:\n"
    "- Do not add, remove, rename or reorder keys.\n"
    "- Keep any text inside curly braces such as {label} or {date} exactly as "
    "given -- these are placeholders.\n"
    "- Keep arrays (for example the list of month names) as arrays in the same "
    "order and length.\n"
    "- In the 'category' and 'province' maps, keep the KEYS in English and "
    "translate only their VALUES.\n"
    "- Use plain, formal wording. No emoji. Return only the JSON object."
)


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        # strip a ```json ... ``` fence if the model added one
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -3]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def translate_ui(src_catalog: dict, lang: str, *, verbose: bool = True) -> Optional[dict]:
    """Translate one English chrome catalog into ``lang``. Returns None on failure."""
    if not _has_credentials():
        if verbose:
            print("[translate] No credentials; cannot build UI catalog for %s." % lang)
        return None
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=_UI_SYSTEM % LANGUAGE_NAMES.get(lang, lang),
        messages=[{"role": "user", "content": json.dumps(src_catalog, ensure_ascii=False)}],
    )
    text = next((blk.text for blk in msg.content if blk.type == "text"), "")
    return _extract_json(text)


def translate_ui_catalogs(
    i18n_dir: str = "i18n",
    *,
    languages: Optional[List[str]] = None,
    verbose: bool = True,
) -> None:
    """Regenerate i18n/<lang>.json from i18n/en.json for each target language."""
    languages = languages or TARGET_LANGUAGES
    src_path = os.path.join(i18n_dir, "en.json")
    with open(src_path, encoding="utf-8") as fh:
        src = json.load(fh)
    for lang in languages:
        catalog = translate_ui(src, lang, verbose=verbose)
        if not catalog:
            if verbose:
                print("[translate] UI catalog for %s failed; leaving file as-is." % lang)
            continue
        out_path = os.path.join(i18n_dir, "%s.json" % lang)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(catalog, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        if verbose:
            print("[translate] wrote %s" % out_path)
