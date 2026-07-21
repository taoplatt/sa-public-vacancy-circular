#!/usr/bin/env python3
"""Assemble the First Client Kit chapters into one styled, printable HTML
file and (if Chromium is available) a PDF.

    python product/build_pdf.py

Outputs product/dist/first-client-kit.html and, when possible,
product/dist/first-client-kit.pdf. If no Chromium is found, open the HTML
in any browser and print to PDF (A4) - the print CSS does the rest.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

HERE = Path(__file__).parent
ROOT = HERE.parent
DIST = HERE / "dist"

CHROMIUM_CANDIDATES = [
    "chromium",
    "chromium-browser",
    "google-chrome",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
]

PAGE_CSS = """
@page { size: A4; margin: 22mm 18mm; }
body { font-family: Georgia, 'Times New Roman', serif; color: %(ink)s;
       line-height: 1.55; font-size: 11.5pt; max-width: 46em; margin: 0 auto; padding: 2em 1em; }
h1 { font-size: 26pt; line-height: 1.1; color: %(ink)s; margin: 1.6em 0 .4em; page-break-before: always; }
h1:first-of-type { page-break-before: avoid; }
h2 { font-size: 15pt; color: %(terracotta)s; margin: 1.4em 0 .4em; }
h3 { font-size: 12pt; margin: 1.2em 0 .3em; }
blockquote { border-left: 3px solid %(sage)s; margin: 1em 0; padding: .2em 1em; color: #453f33; }
code, pre { font-family: 'Courier New', monospace; font-size: 10pt; background: %(plaster)s; }
pre { padding: .8em; white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%%; font-size: 10.5pt; }
th, td { border: 1px solid %(line)s; padding: .45em .6em; text-align: left; }
th { background: %(plaster)s; }
.cover { text-align: center; padding-top: 30vh; page-break-after: always; }
.cover .kicker { text-transform: uppercase; letter-spacing: .15em; font-size: 10pt; color: %(terracotta)s; }
.cover h1 { page-break-before: avoid; font-size: 34pt; margin: .3em 0; }
.cover p { color: #55503f; }
"""


def main() -> int:
    brand = json.loads((ROOT / "brand" / "brand.json").read_text(encoding="utf-8"))
    chapters = sorted(HERE.glob("0*.md"))
    if not chapters:
        print("No chapter files (product/0*.md) found. Write the chapters first.")
        return 1

    md = markdown.Markdown(extensions=["tables", "sane_lists", "smarty"])
    body_parts = [
        '<div class="cover">'
        f'<p class="kicker">{brand["name"]}</p>'
        f'<h1>{brand["product"]["name"]}</h1>'
        "<p>The 30-day path to your first paying interior design client.</p>"
        "</div>"
    ]
    for ch in chapters:
        body_parts.append(md.reset().convert(ch.read_text(encoding="utf-8")))

    css = PAGE_CSS % {
        "ink": brand["colors"]["ink"],
        "terracotta": brand["colors"]["terracotta"],
        "sage": brand["colors"]["sage"],
        "plaster": brand["colors"]["plaster"],
        "line": brand["colors"]["line"],
    }
    html = (
        "<!doctype html><html lang='en-GB'><head><meta charset='utf-8'>"
        f"<title>{brand['product']['name']}</title><style>{css}</style></head>"
        f"<body>{''.join(body_parts)}</body></html>"
    )

    DIST.mkdir(exist_ok=True)
    out_html = DIST / "first-client-kit.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"wrote {out_html} ({len(chapters)} chapters)")

    chromium = next((c for c in CHROMIUM_CANDIDATES if shutil.which(c) or Path(c).exists()), None)
    if not chromium:
        print("No Chromium found: open the HTML in a browser and print to PDF (A4).")
        return 0
    out_pdf = DIST / "first-client-kit.pdf"
    result = subprocess.run(
        [chromium, "--headless", "--disable-gpu", "--no-sandbox",
         f"--print-to-pdf={out_pdf}", "--no-pdf-header-footer", out_html.as_uri()],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and out_pdf.exists():
        print(f"wrote {out_pdf} ({out_pdf.stat().st_size // 1024} KB)")
    else:
        print("Chromium PDF export failed; open the HTML and print to PDF instead.")
        print(result.stderr[-400:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
