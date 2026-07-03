"""Render the static site from one or more Circular records.

Output layout (relative links throughout, so it works at any base path,
including a GitHub Pages project subpath):

    site/
      index.html                 latest circular (search + filter + cards)
      circular/<n>-<year>.html   one listing page per circular
      jobs/<n>-<year>/<slug>.html  one detail page per post
      archive.html  about.html  404.html
      static/style.css  static/filter.js
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
from typing import List
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import CATEGORIES, PROVINCES, Circular, Job

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

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


_MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


def _human_date(iso: str) -> str:
    """'2026-07-03' -> '3 July 2026'. Returns '' on anything unparseable."""
    if not iso:
        return ""
    try:
        y, m, d = (int(x) for x in iso.split("-")[:3])
        return "%d %s %d" % (d, _MONTH_NAMES[m], y)
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


def _write(out_dir: str, rel_path: str, html: str) -> None:
    path = os.path.join(out_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)


def build_site(circulars: List[Circular], out_dir: str = "site") -> None:
    if not circulars:
        raise ValueError("build_site needs at least one circular")
    env = _env()
    today = datetime.date.today().isoformat()
    soon_cutoff = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
    circulars = sorted(circulars, key=lambda c: (c.year, c.number), reverse=True)
    latest = circulars[0]

    os.makedirs(out_dir, exist_ok=True)
    _copy_static(out_dir)

    listing_tpl = env.get_template("listing.html")
    job_tpl = env.get_template("job.html")

    def render_listing(circ: Circular, *, root: str, job_prefix: str) -> str:
        jobs = _sorted_jobs(circ, today)
        provinces = _present((j.province for j in jobs), PROVINCES)
        categories = _present((j.category for j in jobs), CATEGORIES)
        departments = sorted({j.department for j in jobs if j.department})
        is_latest = circ.slug == latest.slug
        return listing_tpl.render(
            root=root,
            nav="latest" if is_latest else "archive",
            favicon=FAVICON,
            circular=circ,
            jobs=jobs,
            job_prefix=job_prefix,
            departments=departments,
            provinces=provinces,
            categories=categories,
            total=len(jobs),
            dept_count=len(departments),
            prov_count=len(provinces),
            today=today,
            soon_cutoff=soon_cutoff,
            issued_human=_human_date(circ.date_issued or ""),
            page_title=("Public Service Vacancies" if is_latest
                        else "%s · Public Service Vacancies" % circ.label),
            heading="Public service vacancies" if is_latest else circ.label,
        )

    def render_job(circ: Circular, job: Job, *, back_url: str, back_label: str) -> str:
        return job_tpl.render(
            root="../../",
            nav="latest" if circ.slug == latest.slug else "archive",
            favicon=FAVICON,
            circular=circ,
            job=job,
            req_items=_sentence_items(job.requirements),
            duty_items=_sentence_items(job.duties),
            back_url=back_url,
            back_label=back_label,
            today=today,
            soon_cutoff=soon_cutoff,
        )

    # Landing page = latest circular listing.
    _write(out_dir, "index.html",
           render_listing(latest, root="", job_prefix="jobs/%s/" % latest.slug))

    # Per-circular listing pages + per-job detail pages.
    for circ in circulars:
        _write(out_dir, "circular/%s.html" % circ.slug,
               render_listing(circ, root="../", job_prefix="../jobs/%s/" % circ.slug))
        back_url = "../../circular/%s.html" % circ.slug
        back_label = "Back to %s" % circ.label
        for job in circ.jobs:
            _write(out_dir, "jobs/%s/%s.html" % (circ.slug, job.slug),
                   render_job(circ, job, back_url=back_url, back_label=back_label))

    # Archive, about, 404.
    _write(out_dir, "archive.html", env.get_template("archive.html").render(
        root="", nav="archive", favicon=FAVICON, circulars=circulars))
    _write(out_dir, "about.html", env.get_template("about.html").render(
        root="", nav="about", favicon=FAVICON, generated_at=latest.generated_at))
    _write(out_dir, "404.html", env.get_template("404.html").render(
        root="", nav="", favicon=FAVICON))

    # A .nojekyll so GitHub Pages serves the folders as-is.
    _write(out_dir, ".nojekyll", "")

    total_jobs = sum(len(c.jobs) for c in circulars)
    print("[build] %d pages · %d circular(s) · %d jobs" % (
        2 + len(circulars) * 2 + total_jobs, len(circulars), total_jobs))
