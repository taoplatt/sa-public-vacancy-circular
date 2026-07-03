"""Segment a PSVC circular PDF into one raw text block per advertised post.

Strategy: run ``pdftotext -layout`` (poppler) to get column-preserving text,
then walk it with a small state machine. The circular's structure makes this
reliable:

* Field labels (POST, SALARY, CENTRE, REQUIREMENTS, DUTIES, ENQUIRIES,
  APPLICATIONS, NOTE, CLOSING DATE) always start at **column 0**.
* Continuation lines and centred headings are always **indented**.
* Departments are announced by a centred ALL-CAPS heading; provinces by a
  ``PROVINCIAL ADMINISTRATION: X`` line; sections by ``ANNEXURE X``.
* CLOSING DATE / APPLICATIONS / NOTE often appear once at department level
  before any POST and are inherited by every post under that department.

The output is a list of dicts (see ``segment_pdf``) that ``parse.py`` turns
into ``Job`` records.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Dict, List, Optional

# Field labels that begin a value block, matched only at column 0.
FIELD_LABELS = [
    "SALARY",
    "STIPEND",
    "CENTRE",
    "REQUIREMENTS",
    "DUTIES",
    "ENQUIRIES",
    "APPLICATIONS",
    "NOTE",
    "CLOSING DATE",
]
_FIELD_RE = re.compile(r"^(" + "|".join(FIELD_LABELS) + r")\s*:\s?(.*)$")
_POST_RE = re.compile(r"^POST\s+(\d+/\d+[A-Za-z]?)\s*:\s*(.*)$")
_ANNEXURE_RE = re.compile(r"^ANNEXURE\s+[A-Z]{1,2}$")
_PROVINCE_RE = re.compile(r"^PROVINCIAL ADMINISTRATION:\s*(.+)$", re.IGNORECASE)
_PAGE_NUM_RE = re.compile(r"^\s*\d{1,4}\s*$")
# Fields that inherit down to every post in a department when set before the
# first POST of that department.
INHERITED_FIELDS = {"CLOSING DATE", "APPLICATIONS", "NOTE"}

# Centred ALL-CAPS lines that are structural, not department names.
_SECTION_HEADERS = {
    "MANAGEMENT ECHELON",
    "OTHER POST",
    "OTHER POSTS",
    "SENIOR MANAGEMENT SERVICE",
    "SMS PRE-ENTRY CERTIFICATE",
    "INDEX",
    "NATIONAL DEPARTMENTS",
    "PROVINCIAL ADMINISTRATIONS",
    "ERRATUM",
    "AMENDMENT",
}
# A department heading is centred, ALL-CAPS, with no lowercase letters.
_HEADING_RE = re.compile(r"^[A-Z0-9 &()/.,'\-]{6,}$")


def _run_pdftotext(pdf_path: str) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError(
            "pdftotext not found. Install poppler (brew install poppler / "
            "apt-get install poppler-utils)."
        )
    out = subprocess.run(
        [exe, "-layout", pdf_path, "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


def _leading_spaces(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _looks_like_heading(stripped: str) -> bool:
    """True if the line is a centred department heading (not a section header)."""
    if stripped in _SECTION_HEADERS:
        return False
    for h in _SECTION_HEADERS:
        if stripped.startswith(h):
            return False
    if not _HEADING_RE.match(stripped):
        return False
    # Must contain real words, not just a code / number.
    letters = sum(c.isalpha() for c in stripped)
    words = [w for w in re.split(r"\s+", stripped) if any(c.isalpha() for c in w)]
    return letters >= 6 and len(words) >= 2


class _PostBuilder:
    def __init__(self, post_number: str, first_value: str, ctx: "_Context") -> None:
        self.post_number = post_number
        self.title_line = first_value
        self.meta_lines: List[str] = []
        self.fields: Dict[str, List[str]] = {}
        self.department = ctx.department or ""
        self.province = ctx.province
        self.dept_defaults = dict(ctx.dept_defaults)
        self._current: Optional[str] = "TITLE"

    def start_field(self, label: str, value: str) -> None:
        self._current = label
        self.fields.setdefault(label, [])
        if value:
            self.fields[label].append(value)

    def add_continuation(self, text: str) -> None:
        if self._current == "TITLE":
            self.meta_lines.append(text)
        elif self._current:
            self.fields[self._current].append(text)

    def to_dict(self) -> dict:
        return {
            "post_number": self.post_number,
            "department": self.department,
            "province": self.province,
            "title_line": self.title_line,
            "meta_lines": self.meta_lines,
            "fields": {k: " ".join(v).strip() for k, v in self.fields.items()},
            "dept_defaults": self.dept_defaults,
        }


class _Context:
    def __init__(self) -> None:
        self.province = "National"
        self.department: Optional[str] = None
        self.dept_defaults: Dict[str, str] = {}
        self._current_default: Optional[str] = None

    def new_department(self, name: Optional[str]) -> None:
        self.department = name
        self.dept_defaults = {}
        self._current_default = None

    def new_province(self, name: str) -> None:
        self.province = name
        self.new_department(None)

    def set_default(self, label: str, value: str) -> None:
        self._current_default = label
        if label in INHERITED_FIELDS:
            self.dept_defaults[label] = value

    def add_default_continuation(self, text: str) -> None:
        if self._current_default and self._current_default in self.dept_defaults:
            self.dept_defaults[self._current_default] = (
                self.dept_defaults[self._current_default] + " " + text
            ).strip()


def segment_pdf(pdf_path: str) -> List[dict]:
    text = _run_pdftotext(pdf_path)
    return segment_text(text)


def segment_text(text: str) -> List[dict]:
    ctx = _Context()
    posts: List[dict] = []
    current: Optional[_PostBuilder] = None
    seen_first_annexure = False
    prev_blank = True

    def flush() -> None:
        nonlocal current
        if current is not None:
            posts.append(current.to_dict())
            current = None

    for raw in text.split("\n"):
        line = raw.replace("\x0c", "").rstrip()
        if line == "":
            prev_blank = True
            continue
        stripped = line.strip()
        indent = _leading_spaces(line)

        # Skip page numbers.
        if _PAGE_NUM_RE.match(line):
            prev_blank = True
            continue

        # Section boundary: ANNEXURE X.
        if _ANNEXURE_RE.match(stripped):
            seen_first_annexure = True
            flush()
            ctx.new_department(None)
            prev_blank = True
            continue

        # Ignore everything before the first department section (intro + index).
        if not seen_first_annexure:
            prev_blank = False
            continue

        # Province header.
        mprov = _PROVINCE_RE.match(stripped)
        if mprov:
            flush()
            ctx.new_province(mprov.group(1).strip())
            prev_blank = True
            continue

        # Column-0 field labels.
        if indent == 0:
            mpost = _POST_RE.match(line)
            if mpost:
                flush()
                current = _PostBuilder(mpost.group(1), mpost.group(2).strip(), ctx)
                prev_blank = False
                continue
            mfield = _FIELD_RE.match(line)
            if mfield:
                label, value = mfield.group(1), mfield.group(2).strip()
                if current is not None:
                    current.start_field(label, value)
                else:
                    ctx.set_default(label, value)
                prev_blank = False
                continue

        # Centred department heading (set off by a blank line, or between posts).
        if _looks_like_heading(stripped) and (prev_blank or current is None):
            flush()
            ctx.new_department(stripped)
            prev_blank = False
            continue

        # Otherwise: a continuation line for the active field / default.
        if current is not None:
            current.add_continuation(stripped)
        else:
            ctx.add_default_continuation(stripped)
        prev_blank = False

    flush()
    return posts
