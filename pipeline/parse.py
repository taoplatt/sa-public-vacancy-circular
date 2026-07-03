"""Turn segmented post blocks into fully-populated ``Job`` records.

Every field is derived deterministically from the circular text, so the site
is complete without any API call. The optional LLM enrichment step
(``extract.py``) only refines ``category``, ``city``, normalised salary/date and
``summary`` on top of what this module produces.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .schema import Job, slugify

# --- province normalisation -------------------------------------------------
_PROVINCE_MAP = {
    "EASTERN CAPE": "Eastern Cape",
    "FREE STATE": "Free State",
    "GAUTENG": "Gauteng",
    "KWAZULU NATAL": "KwaZulu-Natal",
    "KWAZULU-NATAL": "KwaZulu-Natal",
    "LIMPOPO": "Limpopo",
    "MPUMALANGA": "Mpumalanga",
    "NORTHERN CAPE": "Northern Cape",
    "NORTH WEST": "North West",
    "WESTERN CAPE": "Western Cape",
    "NATIONAL": "National",
}
_CANONICAL_PROVINCES = list(_PROVINCE_MAP.values())

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# --- keyword-based sector classification (LLM refines this later) -----------
_CATEGORY_KEYWORDS = [
    ("Health", ["nurs", "medical", "clinic", "health", "pharmac", "doctor",
                "hospital", "dental", "radiograph", "physio", "patient",
                "professional nurse", "paramedic", "emergency medical"]),
    ("Education", ["teacher", "lecturer", "education", "school", "curriculum",
                   "examination", "training officer", "tvet", "college"]),
    ("Finance", ["financ", "account", "audit", "budget", "payroll", "salary",
                 "revenue", "treasury", "bookkeep", "supply chain", "procure"]),
    ("IT", ["information technology", "ict", " it ", "software", "developer",
            "network", "systems admin", "database", "cyber", "programmer",
            "web ", "gis "]),
    ("Engineering", ["engineer", "technician", "artisan", "electric", "mechanic",
                     "construction", "built environment", "surveyor", "draught",
                     "quantity survey", "civil", "maintenance"]),
    ("Legal", ["legal", "law ", "attorney", "advocate", "magistrate", "court",
               "prosecut", "litigation", "registrar of", "conveyanc"]),
    ("Security", ["police", "saps", "security", "correctional", "warder",
                  "traffic", "peace officer", "investigat", "forensic",
                  "warrant officer", "constable", "defence", "soldier"]),
    ("Social Services", ["social work", "social worker", "community develop",
                         "child care", "probation", "youth", "gender",
                         "victim empowerment", "welfare"]),
    ("Agriculture", ["agricultur", "farm", "veterinary", "animal health",
                     "horticultur", "forestry", "land reform", "rural develop",
                     "environment", "conservation", "water", "sanitation"]),
    ("Administration", ["administrat", "clerk", "secretar", "receptionist",
                        "registry", "human resource", "personnel", "office",
                        "records", "data captur", "management", "director",
                        "coordinator", "officer"]),
]


def normalize_province(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().upper())
    if key in _PROVINCE_MAP:
        return _PROVINCE_MAP[key]
    # tolerate stray words like "PROVINCE"
    for raw, canon in _PROVINCE_MAP.items():
        if raw in key:
            return canon
    return "National"


# Uppercase words that should stay uppercase even though they are longer than the
# generic acronym threshold.
_KEEP_UPPER = {
    "SAPS", "SARS", "SITA", "GIS", "ICT", "EMS", "OHS", "HRM", "HRD", "SCM",
    "GCIS", "NHLS", "DDG", "CFO", "CEO", "COO", "ICU", "HIV", "NGO", "PMDS",
    "OSD", "SMS", "VIP", "GITO", "DPSA", "DALRRD", "NSG", "SAQA", "PFMA",
    "TVET", "ABET", "EPWP", "IEC", "SANDF", "SASSA", "NPA", "CSIR",
}
_SMALL = {"of", "and", "the", "for", "in", "to", "a", "at", "on", "with"}


def smart_titlecase(name: str) -> str:
    """Sentence-case a shouty ALL-CAPS heading, preserving real acronyms."""
    name = re.sub(r"\s+", " ", name.strip())
    if not name:
        return name
    words = name.split(" ")
    out: List[str] = []
    for i, w in enumerate(words):
        core = re.sub(r"[^A-Za-z0-9]", "", w)
        low = w.lower()
        if i != 0 and low in _SMALL:
            out.append(low)
        elif core.upper() in _KEEP_UPPER:
            out.append(w)
        # parenthetical codes: "(DOA)"
        elif w.startswith("(") and w.rstrip(")").lstrip("(").isupper():
            out.append(w)
        # short all-caps codes: IT, HR, SCM
        elif re.fullmatch(r"[A-Z0-9&/]+", core) and len(core) <= 3:
            out.append(w)
        elif w.isupper() or w.islower():
            out.append(w.capitalize())
        else:
            out.append(w)  # already mixed-case; leave as-is
    result = " ".join(out)
    return result[:1].upper() + result[1:] if result else result


def _titlecase_department(name: str) -> str:
    return smart_titlecase(name)


def parse_title(title_line: str) -> Tuple[str, str, int]:
    """Return (clean_title, reference_number, number_of_posts)."""
    line = re.sub(r"\s+", " ", title_line).strip()
    ref = ""
    posts = 1

    m_ref = re.search(r"\bREF\s*NO[:.]?\s*(.+?)(?:\s*\(|$)", line, re.IGNORECASE)
    if m_ref:
        ref = m_ref.group(1).strip().rstrip(".")

    m_posts = re.search(r"\(\s*X?\s*(\d+)\s*POSTS?\)", line, re.IGNORECASE)
    if m_posts:
        posts = int(m_posts.group(1))

    # strip the REF NO ... and any trailing (Xn POSTS)/parentheticals
    title = re.split(r"\bREF\s*NO\b", line, flags=re.IGNORECASE)[0]
    title = re.sub(r"\(\s*X?\s*\d+\s*POSTS?\)", "", title, flags=re.IGNORECASE)
    title = title.strip(" :-").strip()
    # safety net: strip a dangling "REF"/"REF NO" left when it wrapped oddly
    title = re.sub(r"[\s,;:-]+REF(\s+NO)?\.?$", "", title, flags=re.IGNORECASE).strip()
    if not title:
        title = line
    return smart_titlecase(title), ref, posts


def _rand_to_int(s: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def parse_salary(text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Return (level, salary_min, salary_max)."""
    level = None
    m_level = re.search(r"\bLevel\s*(\d{1,2})\b", text, re.IGNORECASE)
    if m_level:
        level = int(m_level.group(1))

    amounts = re.findall(r"R\s?([\d][\d\s]{3,})", text)
    values = [v for v in (_rand_to_int(a) for a in amounts) if v]
    smin = smax = None
    if values:
        smin = min(values)
        smax = max(values) if len(values) > 1 else None
    return level, smin, smax


# Words that mean "this is not a town name" when they show up in a centre value.
_NOT_A_CITY = re.compile(
    r"government|department|provincial|national|\boffice\b|directorate|"
    r"various|to be|tbc|nationwide|region|centre$|headquarters",
    re.IGNORECASE,
)


def _clean_city(text: str) -> Optional[str]:
    # drop any parenthetical aside, matched or dangling
    text = re.sub(r"\s*\([^)]*\)?", "", text)
    text = text.strip(" .,;:-()")
    if not text or ":" in text:
        return None
    if _NOT_A_CITY.search(text):
        return None
    # reject province names (a city isn't a province) and multi-province blobs,
    # comparing on letters only so "KwaZulu Natal" == "KwaZulu-Natal"
    low_alnum = re.sub(r"[^a-z]", "", text.lower())
    if any(re.sub(r"[^a-z]", "", p.lower()) in low_alnum for p in _CANONICAL_PROVINCES):
        return None
    return text[:60]


def _looks_like_ref(text: str) -> bool:
    return "/" in text or (bool(re.search(r"\d", text)) and len(text) > 24)


def parse_centre(centre: str, province: str) -> Optional[str]:
    centre = re.sub(r"\s+", " ", centre).strip()
    if not centre:
        return None
    # Multi-post CENTRE blocks pack several "… Ref No: XXX (X1 Post)" entries;
    # keep only the first location, before any ref/post-count marker.
    centre = re.split(r"\bref\s*no\b|\(\s*x?\s*\d+\s*post", centre, maxsplit=1, flags=re.IGNORECASE)[0]
    centre = centre.strip(" :,-")
    if not centre:
        return None
    # common shapes: "Gauteng: Pretoria", "North West, Mafikeng", "Pretoria"
    for sep in (":", ",", "-"):
        if sep in centre:
            city = _clean_city(centre.split(sep)[-1])
            if city and not _looks_like_ref(city):
                return city
            break
    city = _clean_city(centre)
    return city if city and not _looks_like_ref(city) else None


def parse_closing_date(text: str) -> Tuple[str, Optional[str]]:
    raw = re.sub(r"\s+", " ", text).strip()
    if not raw:
        return "", None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        day = int(m.group(1))
        mon = _MONTHS.get(m.group(2).lower())
        year = int(m.group(3))
        if mon:
            return raw, "%04d-%02d-%02d" % (year, mon, day)
    return raw, None


def classify_category(title: str, department: str) -> str:
    hay = (" " + title + " " + department + " ").lower()
    for cat, keys in _CATEGORY_KEYWORDS:
        for k in keys:
            if k in hay:
                return cat
    return "Other"


def _first_sentence(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    m = re.search(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return (s[:limit] + "…") if len(s) > limit else s


def build_summary(job: Job) -> str:
    where = job.city or job.province
    lead = job.title
    if job.number_of_posts > 1:
        lead = "%s (%d posts)" % (lead, job.number_of_posts)
    tail = " at %s" % job.department if job.department else ""
    place = " in %s" % where if where and where != "National" else ""
    return ("%s%s%s." % (lead, tail, place)).strip()


def parse_post(block: dict) -> Job:
    fields = block.get("fields", {})
    province = normalize_province(block.get("province", "National"))
    department = _titlecase_department(block.get("department", "") or "")

    title_line = block.get("title_line", "")
    metas = list(block.get("meta_lines", []))
    # "REF NO:" often wraps: the POST line ends with "…REF" or "…REF NO:" and the
    # reference number itself lands on the next line (e.g. "DBE/51/2026"). Detect
    # that, strip the dangling label from the title, and take the ref from meta.
    ref_from_meta = None
    posts_from_meta = None
    if metas and re.search(r"\bREF(\s+NO)?[:.]?\s*$", title_line, re.IGNORECASE):
        tail = metas.pop(0)
        mp = re.search(r"\(\s*X?\s*(\d+)\s*POSTS?\)", tail, re.IGNORECASE)
        if mp:
            posts_from_meta = int(mp.group(1))
        ref_from_meta = re.sub(r"\(\s*X?\s*\d+\s*POSTS?\)", "", tail, flags=re.IGNORECASE).strip().rstrip(".")
        title_line = re.sub(r"[\s,;:-]+REF(\s+NO)?[:.]?\s*$", "", title_line, flags=re.IGNORECASE).strip()

    title, ref, posts = parse_title(title_line)
    if not ref and ref_from_meta:
        ref = ref_from_meta
    if posts_from_meta:
        posts = posts_from_meta
    meta = " ".join(metas)
    if not ref:
        m = re.search(r"\bREF\s*NO[:.]?\s*(.+?)(?:\s*\(|$)", meta, re.IGNORECASE)
        if m:
            ref = m.group(1).strip().rstrip(".")
    salary_text = (fields.get("SALARY") or fields.get("STIPEND") or "").strip()
    level, smin, smax = parse_salary(salary_text)
    centre = fields.get("CENTRE", "").strip()
    city = parse_centre(centre, province)

    closing_raw = fields.get("CLOSING DATE") or block.get("dept_defaults", {}).get("CLOSING DATE", "")
    closing_text, closing_iso = parse_closing_date(closing_raw or "")

    applications = fields.get("APPLICATIONS") or block.get("dept_defaults", {}).get("APPLICATIONS", "")
    note = fields.get("NOTE") or ""
    dept_note = block.get("dept_defaults", {}).get("NOTE", "")
    notes = " ".join(x for x in (note, dept_note) if x).strip()

    is_readvert = bool(
        re.search(r"re-?advert", meta + " " + notes + " " + title, re.IGNORECASE)
    )

    slug = "%s-%s" % (block["post_number"].replace("/", "-"), slugify(title)[:48])

    job = Job(
        post_number=block["post_number"],
        reference_number=ref,
        slug=slug,
        title=title,
        department=department,
        province=province,
        centre=centre,
        city=city,
        salary_text=salary_text,
        salary_level=level,
        salary_min=smin,
        salary_max=smax,
        number_of_posts=posts,
        is_readvertisement=is_readvert,
        closing_date_text=closing_text,
        closing_date=closing_iso,
        category=classify_category(title, department),
        requirements=re.sub(r"\s+", " ", fields.get("REQUIREMENTS", "")).strip(),
        duties=re.sub(r"\s+", " ", fields.get("DUTIES", "")).strip(),
        enquiries=re.sub(r"\s+", " ", fields.get("ENQUIRIES", "")).strip(),
        applications=re.sub(r"\s+", " ", applications).strip(),
        notes=notes,
    )
    job.summary = build_summary(job)
    return job


def parse_all(blocks: List[dict]) -> List[Job]:
    jobs: List[Job] = []
    seen = set()
    for b in blocks:
        job = parse_post(b)
        key = (job.post_number, job.reference_number)
        if key in seen:
            continue
        seen.add(key)
        jobs.append(job)
    return jobs
