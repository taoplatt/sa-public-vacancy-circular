#!/usr/bin/env python3
"""Render the Maison Method site from templates/ + brand/brand.json into site/.

Usage:
    python build.py                # build to site/
    MM_DOMAIN=maisonmethod.com python build.py   # also write site/CNAME

Rebranding: edit brand/brand.json (name, colours, copy anchors) and rebuild.
Nothing brand-specific lives in the templates or CSS.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).parent
SITE = ROOT / "site"
PAGES = ["index.html", "thanks.html", "privacy.html"]


def is_todo(value: str) -> bool:
    return not value or value.strip().upper().startswith("TODO")


def main() -> int:
    brand = json.loads((ROOT / "brand" / "brand.json").read_text(encoding="utf-8"))
    warnings = []

    # Waitlist form: fall back to a same-site GET to thanks.html until the
    # real MailerLite action URL is configured, so the funnel is always
    # demo-able end to end and never dead-ends.
    wl = brand["waitlist"]
    if is_todo(wl.get("form_action", "")):
        form_action = "thanks.html"
        form_method = "get"
        form_email_field = "email"
        form_hidden = Markup("")
        warnings.append(
            "waitlist.form_action is TODO: the form redirects to thanks.html "
            "but stores nothing. Complete ops/setup.md step 2 before launch."
        )
    else:
        form_action = wl["form_action"]
        form_method = "post"
        form_email_field = wl.get("email_field", "fields[email]")
        form_hidden = Markup(wl.get("hidden_html", '<input type="hidden" name="ml-submit" value="1">'))

    pixel_id = "" if is_todo(brand["analytics"].get("meta_pixel_id", "")) else brand["analytics"]["meta_pixel_id"]
    if not pixel_id:
        warnings.append("analytics.meta_pixel_id is TODO: no consent banner, no pixel (fine until ads run).")

    goatcounter = None if is_todo(brand["analytics"].get("goatcounter_code", "")) else brand["analytics"]["goatcounter_code"]
    if not goatcounter:
        warnings.append("analytics.goatcounter_code is TODO: no traffic analytics.")

    checkout_live = not is_todo(brand["product"].get("checkout_url", ""))
    if not checkout_live:
        warnings.append("product.checkout_url is TODO: thanks.html shows the 'available this week' fallback instead of a buy button.")

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    ctx = {
        "brand": brand,
        "year": date.today().year,
        "form_action": form_action,
        "form_method": form_method,
        "form_email_field": form_email_field,
        "form_hidden": form_hidden,
        "pixel_id": pixel_id,
        "goatcounter": goatcounter,
        "checkout_live": checkout_live,
    }

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "static").mkdir(parents=True)

    for page in PAGES:
        html = env.get_template(page).render(**ctx)
        (SITE / page).write_text(html, encoding="utf-8")

    for f in (ROOT / "static").iterdir():
        shutil.copy(f, SITE / "static" / f.name)
    shutil.copy(ROOT / "brand" / "logo.svg", SITE / "static" / "logo.svg")
    shutil.copy(ROOT / "brand" / "favicon.svg", SITE / "static" / "favicon.svg")

    # GitHub Pages: no Jekyll processing; optional custom domain.
    (SITE / ".nojekyll").write_text("")
    domain = os.environ.get("MM_DOMAIN", "")
    if domain:
        (SITE / "CNAME").write_text(domain + "\n")

    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"built {len(PAGES)} pages -> site/ ({total / 1024:.0f} KB total)")
    for w in warnings:
        print(f"  WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
