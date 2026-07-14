"""Render the static site from one or more Circular records.

The site is rendered once per language into a self-contained tree: English at
the site root, and each other language under ``site/<lang>/`` with its own copy
of ``static/``. Because every tree is self-contained, the ``root`` relative-link
scheme (``""`` / ``"../"`` / ``"../../"``) works unchanged inside each one, and
the only cross-tree links are the language switcher, whose hrefs are computed
per page (see ``_alternates``). No absolute paths, so the site still works under
any base path (e.g. a GitHub Pages project subpath).

Output layout (English tree shown; each of af/zu/xh mirrors it under its code):

    site/
      index.html                 latest circular (search + filter + cards)
      circular/<n>-<year>.html   one listing page per circular
      jobs/<n>-<year>/<slug>.html  one detail page per post
      archive.html  about.html  404.html
      static/style.css  static/filter.js
      af/  zu/  xh/               same tree, translated
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
from typing import Dict, List
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import CATEGORIES, PROVINCES, Circular, Job

_ROOT = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(_ROOT, "templates")
STATIC_DIR = os.path.join(_ROOT, "static")
I18N_DIR = os.path.join(_ROOT, "i18n")

# English at the site root; each other language in its own subtree.
LANGUAGES = ["en", "af", "zu", "xh"]
HTML_LANG = {"en": "en-ZA", "af": "af-ZA", "zu": "zu-ZA", "xh": "xh-ZA"}

# Small inline favicon: green tile + cream briefcase, URL-encoded for a data: URI.
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<rect width="24" height="24" rx="5" fill="%231e3a2b"/>'
    '<g fill="none" stroke="%23f4eedf" stroke-width="1.7" stroke-linecap="round" '
    'stroke-linejoin="round"><rect x="5" y="8.5" width="14" height="10" rx="1.6"/>'
    '<path d="M9 8.5V7.4A1.2 1.2 0 0 1 10.2 6.2h3.6A1.2 1.2 0 0 1 15 7.4V8.5"/>'
    '<path d="M5 12.5h14"/></g></svg>'
)
FAVICON = quote(_FAVICON_SVG, safe="")


def _human_date(iso: str, month_names: List[str]) -> str:
    """'2026-07-03' -> '3 July 2026' (localised months). '' on anything bad."""
    if not iso:
        return ""
    try:
        y, m, d = (int(x) for x in iso.split("-")[:3])
        return "%d %s %d" % (d, month_names[m - 1], y)
    except (ValueError, IndexError):
        return ""


def _sentence_items(text: str, min_words: int = 2) -> List[str]:
    """Split run-on requirement/duty prose into readable bullet items."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z(])", text)
    items: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # merge stubby fragments (e.g. lone acronyms) into the previous item
        if items and len(p.split()) < min_words:
            items[-1] = items[-1].rstrip(". ") + ". " + p
        else:
            items.append(p)
    return items if len(items) > 1 else []


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


# ---------------------------------------------------------------------------
# i18n helpers
# ---------------------------------------------------------------------------
def _read_catalog_file(lang: str) -> dict:
    path = os.path.join(I18N_DIR, "%s.json" % lang)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_catalog(lang: str) -> dict:
    """English catalog overlaid with ``lang`` so any missing key falls back to
    English. Language endonyms (``lang_names``) are always the canonical set."""
    en = _read_catalog_file("en")
    if lang == "en":
        cat = dict(en)
    else:
        cat = dict(en)
        cat.update(_read_catalog_file(lang))
    cat["lang_names"] = en.get("lang_names", {})  # endonyms never translated
    return cat


def _job_view(job: Job, lang: str) -> Dict[str, str]:
    """Resolve the four translatable fields, falling back to English per field."""
    tr = None if lang == "en" else job.translations.get(lang)

    def pick(field: str) -> str:
        val = getattr(tr, field, None) if tr else None
        return val if val else (getattr(job, field) or "")

    return {
        "title": pick("title"),
        "summary": pick("summary"),
        "requirements": pick("requirements"),
        "duties": pick("duties"),
    }


def _alternates(lang: str, root: str, base_rel: str):
    """Relative hrefs to the same page in every language.

    English pages sit one directory shallower than af/zu/xh pages, so the walk
    back to the true site root is ``root`` for English and ``root + '../'``
    otherwise. Everything stays relative -> the site remains relocatable.
    """
    back = root if lang == "en" else root + "../"
    return [(code, back + ("" if code == "en" else code + "/") + base_rel)
            for code in LANGUAGES]


# ---------------------------------------------------------------------------
# rendering helpers
# ---------------------------------------------------------------------------
def _sorted_jobs(circ: Circular, today: str) -> List[Job]:
    def key(j: Job):
        closed = 1 if (j.closing_date and j.closing_date < today) else 0
        return (closed, j.closing_date or "9999-99-99", j.post_number)

    return sorted(circ.jobs, key=key)


def _present(values, order):
    seen = set(values)
    return [v for v in order if v in seen]


def _copy_static(out_dir: str) -> None:
    dst = os.path.join(out_dir, "static")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(STATIC_DIR, dst)


def _write_cname(out_dir: str) -> None:
    """Emit a CNAME at the site root when a custom domain is configured.

    GitHub Pages (deployed via Actions) needs a CNAME file in the published
    artifact for a custom domain to stick across deploys. Set ``PSVC_DOMAIN``
    (locally in ``.env``, or as the ``CUSTOM_DOMAIN`` repo variable in CI) to the
    bare host, e.g. ``jobs.example.com``. With no domain set, no file is written
    and the default ``*.github.io`` URL is used.
    """
    domain = (os.environ.get("PSVC_DOMAIN") or "").strip()
    if not domain:
        return
    with open(os.path.join(out_dir, "CNAME"), "w", encoding="utf-8") as fh:
        fh.write(domain + "\n")
    print("[build] wrote CNAME -> %s" % domain)


def _write(out_dir: str, rel_path: str, html: str) -> None:
    path = os.path.join(out_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)


def _detail_disclaimer(t: dict, job: Job, circ: Circular) -> str:
    dd = t["dd_lead"].format(post=job.post_number, label=circ.label)
    dd += " " + t["dd_apply"].format(department=job.department)
    if job.closing_date_text:
        dd += t["dd_by"].format(closing=job.closing_date_text)
    if job.reference_number:
        dd += t["dd_ref"].format(reference=job.reference_number)
    dd += t["dd_tail"]
    return dd


def build_site(circulars: List[Circular], out_dir: str = "site") -> None:
    if not circulars:
        raise ValueError("build_site needs at least one circular")
    env = _env()
    today = datetime.date.today().isoformat()
    soon_cutoff = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
    circulars = sorted(circulars, key=lambda c: (c.year, c.number), reverse=True)
    latest = circulars[0]

    os.makedirs(out_dir, exist_ok=True)
    for lang in LANGUAGES:
        tree_dir = out_dir if lang == "en" else os.path.join(out_dir, lang)
        _build_tree(env, circulars, latest, tree_dir, lang,
                    _load_catalog(lang), today, soon_cutoff)

    _write_cname(out_dir)  # custom domain (PSVC_DOMAIN), site root only

    total_jobs = sum(len(c.jobs) for c in circulars)
    pages_per_lang = 2 + len(circulars) * 2 + total_jobs
    print("[build] %d languages · %d pages · %d circular(s) · %d jobs" % (
        len(LANGUAGES), pages_per_lang * len(LANGUAGES), len(circulars), total_jobs))


def _build_tree(env, circulars, latest, out_dir, lang, t, today, soon_cutoff):
    os.makedirs(out_dir, exist_ok=True)
    _copy_static(out_dir)
    html_lang = HTML_LANG.get(lang, "en-ZA")
    month_names = t["month_names"]

    listing_tpl = env.get_template("listing.html")
    job_tpl = env.get_template("job.html")

    def base_ctx(root, base_rel, nav):
        alternates = _alternates(lang, root, base_rel)
        en_href = next(href for code, href in alternates if code == "en")
        # Canonical path for analytics (matches the browser path the JS beacon
        # records: homepage is "/" or "/<lang>/", not "/index.html").
        prefix = "" if lang == "en" else lang + "/"
        page_path = "/" + prefix + base_rel
        if page_path.endswith("/index.html"):
            page_path = page_path[: -len("index.html")]
        return dict(root=root, nav=nav, favicon=FAVICON, t=t, lang=lang,
                    html_lang=html_lang, alternates=alternates, en_href=en_href,
                    page_path=page_path)

    def render_listing(circ, *, root, job_prefix, base_rel):
        jobs = _sorted_jobs(circ, today)
        job_views = [_job_view(j, lang) for j in jobs]
        provinces = _present((j.province for j in jobs), PROVINCES)
        categories = _present((j.category for j in jobs), CATEGORIES)
        departments = sorted({j.department for j in jobs if j.department})
        is_latest = circ.slug == latest.slug
        page_title = (t["page_title_latest"] if is_latest
                      else t["page_title_other"].format(label=circ.label))
        heading = t["hero_heading"] if is_latest else circ.label
        return listing_tpl.render(
            circular=circ,
            jobs=jobs,
            job_views=job_views,
            job_prefix=job_prefix,
            departments=departments,
            provinces=provinces,
            categories=categories,
            total=len(jobs),
            today=today,
            soon_cutoff=soon_cutoff,
            issued_human=_human_date(circ.date_issued or "", month_names),
            page_title=page_title,
            heading=heading,
            listing_description=t["listing_description"].format(
                total=len(jobs), label=circ.label),
            **base_ctx(root, base_rel, "latest" if is_latest else "archive"),
        )

    def render_job(circ, job, *, back_url, base_rel):
        view = _job_view(job, lang)
        nav = "latest" if circ.slug == latest.slug else "archive"
        return job_tpl.render(
            circular=circ,
            job=job,
            view=view,
            req_items=_sentence_items(view["requirements"]),
            duty_items=_sentence_items(view["duties"]),
            back_url=back_url,
            back_label=t["back_to"].format(label=circ.label),
            disclaimer=_detail_disclaimer(t, job, circ),
            today=today,
            soon_cutoff=soon_cutoff,
            **base_ctx("../../", base_rel, nav),
        )

    # Landing page = latest circular listing.
    _write(out_dir, "index.html", render_listing(
        latest, root="", job_prefix="jobs/%s/" % latest.slug, base_rel="index.html"))

    # Per-circular listing pages + per-job detail pages.
    for circ in circulars:
        _write(out_dir, "circular/%s.html" % circ.slug, render_listing(
            circ, root="../", job_prefix="../jobs/%s/" % circ.slug,
            base_rel="circular/%s.html" % circ.slug))
        back_url = "../../circular/%s.html" % circ.slug
        for job in circ.jobs:
            _write(out_dir, "jobs/%s/%s.html" % (circ.slug, job.slug),
                   render_job(circ, job, back_url=back_url,
                              base_rel="jobs/%s/%s.html" % (circ.slug, job.slug)))

    # Archive, about, 404.
    _write(out_dir, "archive.html", env.get_template("archive.html").render(
        circulars=circulars, **base_ctx("", "archive.html", "archive")))
    _write(out_dir, "about.html", env.get_template("about.html").render(
        generated_at=latest.generated_at, **base_ctx("", "about.html", "about")))
    _write(out_dir, "404.html", env.get_template("404.html").render(
        **base_ctx("", "404.html", "")))

    # A .nojekyll at the site root so GitHub Pages serves the folders as-is.
    if lang == "en":
        _write(out_dir, ".nojekyll", "")
