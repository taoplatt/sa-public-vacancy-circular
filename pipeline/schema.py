"""Data models for the Public Service Vacancy Circular pipeline.

A `Job` is one advertised post. A `Circular` is one weekly publication holding
many jobs. These models are the contract shared by every pipeline stage and by
the site builder, and they define the JSON stored under ``data/circulars/``.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# Sector categories used for filtering. Kept deliberately small and stable so
# the filter UI and the LLM enrichment agree on a fixed vocabulary.
CATEGORIES: List[str] = [
    "Health",
    "Education",
    "Finance",
    "IT",
    "Engineering",
    "Legal",
    "Security",
    "Social Services",
    "Agriculture",
    "Administration",
    "Other",
]

# The nine provinces plus the national bucket. Segmentation assigns one of these
# to every job so the province filter is always populated.
PROVINCES: List[str] = [
    "National",
    "Eastern Cape",
    "Free State",
    "Gauteng",
    "KwaZulu-Natal",
    "Limpopo",
    "Mpumalanga",
    "Northern Cape",
    "North West",
    "Western Cape",
]


class JobTranslation(BaseModel):
    """A machine translation of a job's free-text fields into one language.

    Every field is optional so a partial or failed translation degrades
    gracefully: any field left ``None`` falls back to the English source when
    the site is rendered (see ``build.py``). The verbatim fields (reference,
    salary, dates, addresses, department) are never translated.
    """

    title: Optional[str] = None
    summary: Optional[str] = None
    requirements: Optional[str] = None
    duties: Optional[str] = None


class Job(BaseModel):
    """One advertised post, after deterministic parsing (+ optional LLM enrichment)."""

    # Identity
    post_number: str                      # e.g. "23/01"
    reference_number: str = ""            # e.g. "3/3/1/47/2026"
    slug: str                             # url-safe id for the detail page

    # Headline fields (drive the card + filters)
    title: str
    department: str
    province: str = "National"
    centre: str = ""                      # raw CENTRE value
    city: Optional[str] = None            # best-effort city within the centre
    salary_text: str = ""                 # raw SALARY value
    salary_level: Optional[int] = None    # parsed OSD/SMS level, if present
    salary_min: Optional[int] = None      # parsed rand amount
    salary_max: Optional[int] = None
    number_of_posts: int = 1
    is_readvertisement: bool = False
    closing_date_text: str = ""           # raw closing-date value
    closing_date: Optional[str] = None    # ISO 8601 (YYYY-MM-DD) if parseable
    category: str = "Other"               # one of CATEGORIES
    summary: Optional[str] = None         # short plain-language blurb

    # Long-form detail (rendered on the job page)
    requirements: str = ""
    duties: str = ""
    enquiries: str = ""
    applications: str = ""
    notes: str = ""

    # Machine translations of the free-text fields, keyed by language code
    # ("af", "zu", "xh"). English is the canonical source and is never stored
    # here; a missing language or field falls back to English at render time.
    translations: Dict[str, JobTranslation] = Field(default_factory=dict)

    def is_open(self, today_iso: Optional[str] = None) -> bool:
        """True when the closing date is unknown or not yet passed."""
        if not self.closing_date:
            return True
        if today_iso is None:
            return True
        return self.closing_date >= today_iso


class Circular(BaseModel):
    """One weekly PSVC publication and all the jobs extracted from it."""

    number: int
    year: int
    date_issued: Optional[str] = None     # ISO 8601
    source_url: Optional[str] = None
    source_pdf: Optional[str] = None      # local filename of the archived PDF
    generated_at: Optional[str] = None    # ISO 8601 build timestamp
    jobs: List[Job] = Field(default_factory=list)

    @property
    def slug(self) -> str:
        return f"{self.number}-{self.year}"

    @property
    def label(self) -> str:
        return f"Circular {self.number} of {self.year}"


# ---------------------------------------------------------------------------
# LLM structured-output schema
# ---------------------------------------------------------------------------
# The enrichment call asks Claude to normalise a handful of fields that regex
# handles poorly (sector, city, ISO date, salary band) and to write a one-line
# summary. Only these fields are overwritten on the deterministic Job, so a
# failed or skipped enrichment never loses data.
def enrichment_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "category": {"type": "string", "enum": CATEGORIES},
            "city": {"type": ["string", "null"]},
            "salary_level": {"type": ["integer", "null"]},
            "salary_min": {"type": ["integer", "null"]},
            "salary_max": {"type": ["integer", "null"]},
            "closing_date": {
                "type": ["string", "null"],
                "description": "ISO 8601 date (YYYY-MM-DD) or null",
            },
            "number_of_posts": {"type": "integer"},
            "is_readvertisement": {"type": "boolean"},
            "summary": {
                "type": "string",
                "description": "One sentence, plain English, no more than 30 words.",
            },
        },
        "required": [
            "category",
            "city",
            "salary_level",
            "salary_min",
            "salary_max",
            "closing_date",
            "number_of_posts",
            "is_readvertisement",
            "summary",
        ],
    }


# ---------------------------------------------------------------------------
# Translation structured-output schema
# ---------------------------------------------------------------------------
# The translate stage (pipeline/translate.py) asks Claude to translate a post's
# four free-text fields into one target language. The punctuation note on
# requirements/duties is load-bearing: build.py's ``_sentence_items`` splits
# those fields into bullet points on ``.``/``;`` boundaries, so the translation
# must keep sentence-ending punctuation or the bullets collapse into one block.
def translation_schema() -> dict:
    _bullet = (
        "Keep the same sentence boundaries as the English: end each sentence "
        "with a full stop or semicolon and start each with a capital letter, so "
        "the text can still be split into bullet points."
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "requirements": {"type": "string", "description": _bullet},
            "duties": {"type": "string", "description": _bullet},
        },
        "required": ["title", "summary", "requirements", "duties"],
    }


def slugify(text: str, fallback: str = "post") -> str:
    """URL-safe slug from arbitrary text."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback
