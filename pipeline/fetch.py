"""Discover and download the latest PSVC circular PDF from dpsa.gov.za.

For a first run (or offline) the pipeline can instead point at a local PDF via
``run.py --pdf``. Circular number, year and issue date are read from the PDF's
own cover text, so metadata never depends on the filename.
"""
from __future__ import annotations

import os
import re
import subprocess
import shutil
from typing import List, Optional, Tuple
from urllib.parse import urljoin

PSVC_INDEX_URL = "https://www.dpsa.gov.za/newsroom/psvc/"
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def circular_meta_from_pdf(pdf_path: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Return (number, year, date_issued_iso) read from the circular cover page."""
    exe = shutil.which("pdftotext")
    if not exe:
        return _meta_from_filename(pdf_path)
    out = subprocess.run(
        [exe, "-f", "1", "-l", "1", pdf_path, "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    number = year = None
    date_iso = None
    m = re.search(r"PUBLICATION\s+NO\s+(\d+)\s+OF\s+(\d{4})", out, re.IGNORECASE)
    if m:
        number, year = int(m.group(1)), int(m.group(2))
    md = re.search(r"DATE\s+ISSUED\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", out, re.IGNORECASE)
    if md:
        mon = _MONTHS.get(md.group(2).lower())
        if mon:
            date_iso = "%04d-%02d-%02d" % (int(md.group(3)), mon, int(md.group(1)))
    if number is None:
        number, year = _meta_from_filename(pdf_path)[:2]
    return number, year, date_iso


def _meta_from_filename(pdf_path: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    name = os.path.basename(pdf_path)
    m = re.search(r"(\d+)\s+of\s+(\d{4})", name, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2)), None
    return None, None, None


def _get_soup(url: str):
    import requests
    from bs4 import BeautifulSoup

    resp = requests.get(url, timeout=30, headers={"User-Agent": "psvc-pipeline/1.0"})
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def discover_circular_pages() -> List[Tuple[int, int, str]]:
    """Return (number, year, page_url) for each circular sub-page on the index.

    The PSVC index links to per-circular pages such as
    ``/newsroom/psvc/circular-23-of-2026/``; the PDF lives on that sub-page.
    """
    soup = _get_soup(PSVC_INDEX_URL)
    pages = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"circular-(\d+)-of-(\d{4})", a["href"], re.IGNORECASE)
        if m:
            num, year = int(m.group(1)), int(m.group(2))
            pages[(num, year)] = urljoin(PSVC_INDEX_URL, a["href"])
    return [(n, y, url) for (n, y), url in pages.items()]


def _is_full_circular_pdf(url: str) -> bool:
    name = os.path.basename(url.split("?")[0]).lower()
    # the combined circular is named like "PSV CIRCULAR 23 of 2026.pdf";
    # per-annexure splits are single letters (a.pdf, b.pdf, …).
    if re.fullmatch(r"[a-z]{1,2}\.pdf", name):
        return False
    return "circular" in name and "of" in name


def circular_pdf_url(page_url: str) -> Optional[str]:
    soup = _get_soup(page_url)
    pdfs = [urljoin(page_url, a["href"]) for a in soup.find_all("a", href=True)
            if a["href"].lower().endswith(".pdf")]
    for url in pdfs:
        if _is_full_circular_pdf(url):
            return url
    # fall back to the first non-annexure PDF, else the first PDF.
    for url in pdfs:
        if not re.fullmatch(r"[a-z]{1,2}\.pdf", os.path.basename(url.split("?")[0]).lower()):
            return url
    return pdfs[0] if pdfs else None


def latest_pdf_link() -> Optional[Tuple[str, Optional[int]]]:
    """Resolve the newest circular to (pdf_url, number)."""
    pages = discover_circular_pages()
    if not pages:
        return None
    num, year, page_url = max(pages, key=lambda p: (p[1], p[0]))
    pdf = circular_pdf_url(page_url)
    return (pdf, num) if pdf else None


def download(url: str, dest_dir: str = "data/raw") -> str:
    import requests

    os.makedirs(dest_dir, exist_ok=True)
    fname = os.path.basename(url.split("?")[0]) or "circular.pdf"
    dest = os.path.join(dest_dir, fname)
    if os.path.exists(dest):
        return dest
    with requests.get(url, stream=True, timeout=120, headers={"User-Agent": "psvc-pipeline/1.0"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=65536):
                fh.write(chunk)
    return dest


def fetch_latest(dest_dir: str = "data/raw") -> Optional[str]:
    """Download the newest circular; return its local path (or None on failure)."""
    link = latest_pdf_link()
    if not link:
        return None
    return download(link[0], dest_dir)
