"""Optional machine translation of parsed jobs into South Africa's languages.

The deterministic parse (and optional enrichment) produce complete English
records. This step asks the configured model (``PSVC_MODEL``, default GLM 5.2)
via OpenRouter to translate the four free-text fields of each post -- ``title``,
``summary``, ``requirements`` and ``duties`` -- into Afrikaans, isiZulu and
isiXhosa. English stays the canonical source; the translations are merged onto
each ``Job`` under ``job.translations[lang]``.

Design notes (mirrors ``pipeline/extract.py``)
---------------------------------------------
* OpenRouter has no batch endpoint, so requests are issued synchronously and
  fanned out over a small thread pool (see ``pipeline/llm.py``). One request per
  (job, language): bounded output, and a failure in one language never costs the
  others.
* A gap-fill pass retries any (post, language) the first pass missed, with a
  larger ``max_tokens`` for very long posts, so weekly runs reach ~100%.
* Best-effort: any post whose result is missing or invalid keeps English (the
  render falls back field-by-field), so the site is never degraded by this step.
* If ``OPENROUTER_API_KEY`` is not available, the whole step is skipped and the
  jobs are returned unchanged.

Verbatim policy: reference/post numbers, salaries, dates, addresses
(enquiries/applications/notes) and department names are **not** translated --
they never enter the payload -- so they always read in the official English.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from . import llm
from .schema import Job, JobTranslation, translation_schema

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


def _apply(job: Job, lang: str, data: dict) -> None:
    """Merge one language's validated translation onto a job (best-effort)."""
    tr = job.translations.get(lang) or JobTranslation()
    for attr in ("title", "summary", "requirements", "duties"):
        val = data.get(attr)
        if isinstance(val, str) and val.strip():
            setattr(tr, attr, val.strip())
    job.translations[lang] = tr


def _translated(job: Job, lang: str) -> bool:
    """True if this post already has a usable translation for ``lang``."""
    tr = job.translations.get(lang)
    return bool(tr and (tr.title or "").strip())


def _translate_one(job: Job, lang: str, *, max_tokens: int = 6000) -> Optional[dict]:
    return llm.chat_json(
        _system_prompt(lang),
        _job_payload(job),
        translation_schema(),
        max_tokens=max_tokens,
        schema_name="translation",
    )


def _fill_gaps_sync(
    targets: List[Job],
    languages: List[str],
    *,
    max_tokens: int = 10000,
    verbose: bool = True,
) -> int:
    """Retry any (post, language) the first pass left untranslated.

    A small fraction of requests fail transiently, and very long posts can
    truncate at the default ``max_tokens``; those fields silently fall back to
    English. This pass retries just the gaps with a larger ``max_tokens`` so
    weekly runs reach ~100% unattended. Best-effort: a failure here (e.g. no API
    credit) simply keeps the English fallback.
    """
    pending = [
        (job, lang)
        for job in targets
        for lang in languages
        if not _translated(job, lang)
    ]
    if not pending:
        return 0
    if verbose:
        print("[translate] gap-fill: retrying %d missing (post, language) pair(s)…" % len(pending))
    filled = 0
    for job, lang in pending:
        data = _translate_one(job, lang, max_tokens=max_tokens)
        if isinstance(data, dict):
            _apply(job, lang, data)
            if _translated(job, lang):
                filled += 1
    if verbose:
        print("[translate] gap-fill: filled %d/%d." % (filled, len(pending)))
    return filled


def translate_jobs(
    jobs: List[Job],
    *,
    languages: Optional[List[str]] = None,
    limit: Optional[int] = None,
    verbose: bool = True,
) -> List[Job]:
    """Translate jobs in place via concurrent OpenRouter calls. Returns the same list."""
    languages = languages or TARGET_LANGUAGES
    if not llm.have_credentials():
        if verbose:
            print(
                "[translate] No OPENROUTER_API_KEY found; keeping English only "
                "(site still builds, falls back to English)."
            )
        return jobs

    targets = jobs[:limit] if limit else jobs
    pairs = [(i, lang) for i in range(len(targets)) for lang in languages]
    if verbose:
        print(
            "[translate] translating %d requests (%d jobs x %d languages, "
            "model=%s)…" % (len(pairs), len(targets), len(languages), llm.model_name())
        )

    def worker(_k: int, pair) -> Optional[dict]:
        i, lang = pair
        return _translate_one(targets[i], lang)

    results = llm.map_concurrent(worker, pairs)
    ok = 0
    for (i, lang), data in zip(pairs, results):
        if isinstance(data, dict):
            _apply(targets[i], lang, data)
            ok += 1
    if verbose:
        print("[translate] translated %d/%d requests." % (ok, len(pairs)))

    # Self-heal: retry any (post, language) the first pass missed, so a weekly
    # run reaches ~100% without a manual follow-up.
    _fill_gaps_sync(targets, languages, verbose=verbose)
    return jobs


def translate_sync(
    jobs: List[Job],
    *,
    languages: Optional[List[str]] = None,
    limit: int = 5,
    verbose: bool = True,
) -> List[Job]:
    """Translate only the first ``limit`` jobs -- a quick local check."""
    return translate_jobs(jobs, languages=languages, limit=limit, verbose=verbose)


# ---------------------------------------------------------------------------
# UI (chrome) catalog translation
# ---------------------------------------------------------------------------
# One small call per language translates the whole English chrome catalog
# (i18n/en.json). Run only when the English strings change; the output is
# committed and hand-editable.
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
    if not llm.have_credentials():
        if verbose:
            print("[translate] No OPENROUTER_API_KEY; cannot build UI catalog for %s." % lang)
        return None
    text = llm.chat_text(
        _UI_SYSTEM % LANGUAGE_NAMES.get(lang, lang),
        json.dumps(src_catalog, ensure_ascii=False),
        max_tokens=8000,
    )
    if not text:
        return None
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
