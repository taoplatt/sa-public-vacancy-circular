# Maison Method

**Turn your eye for interiors into income.** A demand test for a
business-in-a-box that takes aspiring interior designers (UK/Europe:
side-hustlers, career switchers, stay-at-home parents) from zero to their
first paying client. No degree required, because none is needed.

This repo is the entire test: brand, landing site + waitlist, a £12 tripwire
product, a faceless TikTok content engine, a £100 Meta ads probe, and the
scorecard that decides whether the full product gets built.

## The funnel

```
faceless TikToks + £100 Meta probe
        -> landing page (waitlist email)
        -> thank-you page (£12 First Client Kit on Payhip)
        -> scorecard -> BUILD / ITERATE / KILL at week 4
```

## Quickstart

```bash
pip install -r requirements.txt
python build.py                      # renders site/ from templates/ + brand/brand.json
python -m http.server -d site 8099   # preview at http://localhost:8099
python product/build_pdf.py          # assembles the sellable kit PDF into product/dist/
```

Pushing to `main` builds and deploys to GitHub Pages automatically
(`.github/workflows/deploy.yml`). Launch sequence: **`ops/setup.md`**, top to
bottom.

## Repo map

| Path | What it is |
|---|---|
| `brand/` | `brand.json` (single source of truth: name, colours, URLs, TODOs), voice guide, logo/favicon/social SVGs |
| `templates/` + `static/` + `build.py` | The static site: landing, thank-you/tripwire, privacy, consent-gated Meta pixel |
| `product/` | The First Client Kit (£12): chapter markdown, pricing calculator, PDF builder |
| `content/` | 30 faceless TikTok scripts in 5 formats, 30-day calendar, production workflow, hooks tracker |
| `ads/` | £100 Meta media plan, ad copy per persona, kill/scale thresholds |
| `ops/` | Setup guide (all external accounts) and the weekly scorecard |

## Design decisions worth knowing

- **Config-driven brand.** Rebranding (name, colours, tagline, URLs) is an
  edit to `brand/brand.json` + rebuild. Templates and CSS contain nothing
  brand-specific.
- **Graceful TODOs.** With unset config the site still builds and demos: the
  form falls through to the thank-you page, the buy button becomes
  "available this week", no pixel means no consent banner. `build.py` prints
  a warning per unfinished step.
- **Tiny and dependency-free.** ~20 KB per page, system serif, no JS
  frameworks; the site works fully with JavaScript disabled. Pixel is
  consent-gated (UK/EU); GoatCounter is cookieless.
- **Payhip on purpose.** Merchant of record, so UK/EU VAT on the digital
  product is handled at checkout.
- **No invented social proof.** Testimonials, member counts and milestones
  enter the copy only when they are real (see `brand/voice.md`).

## The decision gates (summary; full rules in `ads/thresholds.md`)

- Landing conversion: >=8% from cold ads is healthy; <5% means fix the page,
  not the budget.
- Meta CPL <=£2.50 continue, >£4 after £25 spend kill the ad set.
- Kit take-rate >=3% of signups is a strong real-money signal.
- Week 4: >=300 waitlist or >=10 sales -> **build**; 100-300 -> **iterate**;
  <100 -> **kill or pivot**.
