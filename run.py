#!/usr/bin/env python3
"""Orchestrate the PSVC pipeline: fetch → segment → parse → (enrich) → build.

Usage
-----
  python run.py --pdf "PSV CIRCULAR 23 of 2026.pdf"   # process a local PDF, build site
  python run.py                                        # fetch newest circular, build site
  python run.py --enrich                               # + LLM enrichment (needs API key)
  python run.py --enrich --sync-limit 5                # enrich 5 jobs synchronously (test)
  python run.py --build-only                           # rebuild site from existing data/

Extracted data is written to data/circulars/circular-<n>-<year>.json (committed,
the archive's source of truth). The site is rendered from every circular found
there, so the browsable archive always reflects the full history.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import os

from pipeline import build, extract, fetch, parse, segment
from pipeline.schema import Circular

DATA_DIR = "data/circulars"


def _load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines from a local .env into the environment (no overwrite).

    Lets you keep ANTHROPIC_API_KEY in a git-ignored .env instead of exporting
    it each shell. Existing environment variables always win.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def process_pdf(pdf_path: str, enrich: bool = False, sync_limit: int = 0) -> Circular:
    number, year, date_iso = fetch.circular_meta_from_pdf(pdf_path)
    print("[run] %s -> circular %s of %s (issued %s)" % (
        os.path.basename(pdf_path), number, year, date_iso or "?"))
    blocks = segment.segment_pdf(pdf_path)
    jobs = parse.parse_all(blocks)
    print("[run] parsed %d jobs" % len(jobs))

    if enrich:
        if sync_limit:
            extract.enrich_sync(jobs, limit=sync_limit)
        else:
            extract.enrich_jobs(jobs)

    circ = Circular(
        number=number or 0,
        year=year or 0,
        date_issued=date_iso,
        source_pdf=os.path.basename(pdf_path),
        generated_at=_now_iso(),
        jobs=jobs,
    )
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "circular-%s.json" % circ.slug)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(circ.model_dump_json(indent=2))
    print("[run] wrote %s" % path)
    return circ


def load_all_circulars() -> list:
    circs = []
    for path in glob.glob(os.path.join(DATA_DIR, "*.json")):
        with open(path, encoding="utf-8") as fh:
            circs.append(Circular.model_validate_json(fh.read()))
    circs.sort(key=lambda c: (c.year, c.number), reverse=True)
    return circs


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the SA public-service vacancy site.")
    ap.add_argument("--pdf", help="Path to a local circular PDF to process.")
    ap.add_argument("--build-only", action="store_true", help="Only rebuild the site.")
    ap.add_argument("--enrich", action="store_true", help="Run LLM enrichment (needs key).")
    ap.add_argument("--sync-limit", type=int, default=0, help="Enrich N jobs synchronously.")
    ap.add_argument("--out", default="site", help="Output directory (default: site).")
    args = ap.parse_args()

    _load_dotenv()  # pick up ANTHROPIC_API_KEY from a local .env if present

    if not args.build_only:
        pdf = args.pdf
        if not pdf:
            pdf = fetch.fetch_latest()
            if not pdf:
                raise SystemExit("Could not fetch a circular. Pass --pdf <path>.")
        process_pdf(pdf, enrich=args.enrich, sync_limit=args.sync_limit)

    circulars = load_all_circulars()
    if not circulars:
        raise SystemExit("No circular data in %s. Run once without --build-only." % DATA_DIR)
    build.build_site(circulars, out_dir=args.out)
    print("[run] built %s from %d circular(s)" % (args.out, len(circulars)))


if __name__ == "__main__":
    main()
