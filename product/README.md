# The First Client Kit (product source)

This folder contains the full content of The First Client Kit, the £12 Maison Method starter product: everything an aspiring interior designer in the UK or Europe needs to land a first paying client (a £200 to £500 room refresh or e-design brief) in about 30 days.

## Files, in reading order

| File | What it is |
|---|---|
| `01-start-here.md` | Orientation, the permission facts (no licence or degree needed for residential design work in the UK and most of Europe), and what the kit will not do |
| `02-first-client-roadmap.md` | The core asset: the 30-day week-by-week roadmap, with all outreach scripts word for word |
| `03-pricing-guide.md` | Fixed-fee pricing for beginners, typical UK ranges, the "that's expensive" script, when to raise |
| `04-client-templates.md` | Six copy-paste client documents: enquiry reply, questionnaire, proposal, letter of agreement, invoice, testimonial request |
| `05-tool-stack.md` | The free/cheap tool stack (£0 a month to start) mapped to the roadmap |
| `06-launch-checklist.md` | The whole 30 days as one printable tick-box page |
| `pricing-calculator.csv` | Companion spreadsheet for `03`; opens in Excel or Google Sheets with working formulas |

## Building the sellable PDF

`build_pdf.py` (written separately, lives alongside this folder's tooling) assembles chapters `01` to `06`, in filename order, into the single PDF that buyers download. `pricing-calculator.csv` ships as a separate file in the buyer's download alongside the PDF, and this README is internal only and is not included in the product.

House style for edits: British English, sentence case headings, no em dashes, no emoji, no invented testimonials or numbers presented as real. See `brand/voice.md` before changing any copy.
