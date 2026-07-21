# Setup guide

Everything the repo cannot do for you: account creation and pasting five
values into `brand/brand.json`. Each step is 5-15 minutes. Do them in order;
the site works (in demo mode) from step 1, and each step upgrades it.

After ANY edit to `brand/brand.json`, rebuild and push:

```bash
python build.py     # check the warnings shrink each time
git add -A && git commit -m "Configure <thing>" && git push
```

## 1. GitHub Pages (site goes live)

1. Repo Settings -> Pages -> Source: **GitHub Actions**.
2. Push to `main`. The `deploy.yml` workflow builds and deploys automatically.
3. Site appears at `https://taoplatt.github.io/maison-method/`.

**Custom domain (recommended before running ads, ~£10/yr):** buy
`maisonmethod.com` or `.co.uk` (Cloudflare Registrar or Porkbun are cheapest).
Then: Settings -> Secrets and variables -> Actions -> Variables -> new
variable `CUSTOM_DOMAIN` = `maisonmethod.com`. Add the same domain in
Settings -> Pages (provisions HTTPS). At your registrar add a `CNAME` record
pointing the domain (or `www`) to `taoplatt.github.io`; for an apex domain add
GitHub's four A records (185.199.108.153 to 185.199.111.153). Update
`site_url` and `domain` in `brand/brand.json`.

## 2. MailerLite (the waitlist starts storing emails)

1. Create a free account at mailerlite.com (free to 1,000 subscribers,
   EU-based, GDPR-native).
2. Subscribers -> Groups -> create group `waitlist`.
3. Forms -> Embedded forms -> create -> pick any layout (we only need the
   endpoint, not their styling) -> assign to group `waitlist`.
4. In the form's **HTML code** (not JavaScript) embed option, find the
   `<form action="...">` URL. Copy it into `brand/brand.json` ->
   `waitlist.form_action`. Check the email input's `name` attribute in the
   same snippet; if it is not `fields[email]`, set `waitlist.email_field`
   to match. If the snippet has extra hidden inputs, copy them verbatim into
   `waitlist.hidden_html` as one string.
5. In the form settings, set **success behaviour** to redirect to
   `https://<your-site>/thanks.html`.
6. Turn on **double opt-in** (Forms settings). Required posture for UK/EU.
7. Create a welcome automation (Automations -> when subscriber joins group
   `waitlist`): one email, sent immediately. Draft:

   > Subject: You're in
   >
   > You are on the Maison Method waitlist. Two things worth knowing:
   > we launch to this list first, at a founding price that will not be
   > repeated, and until then we will only email you when there is
   > something genuinely useful to say.
   >
   > If you want a head start today, The First Client Kit is £12 and
   > contains the 30-day roadmap, the pricing guide and every client
   > template you need for a first brief: [Payhip link]
   >
   > Talk soon,
   > Maison Method

8. Rebuild + push. The build warning about the form disappears.

## 3. Payhip (the £12 kit goes on sale)

1. Build the product PDF: `python product/build_pdf.py` (output lands in
   `product/dist/`).
2. Create a free account at payhip.com. Payhip is UK-based and acts as
   **merchant of record**, so UK/EU VAT on digital products is their
   problem, not yours. Fee on the free plan: 5% per sale.
3. Add product -> Digital product -> upload the PDF + the
   `pricing-calculator.csv` -> price **£12**.
4. Copy the product URL into `brand/brand.json` -> `product.checkout_url`.
5. Rebuild + push. The thank-you page switches from "available this week"
   to a live buy button.

## 4. GoatCounter (traffic numbers, no cookies)

1. Create a free account at goatcounter.com, pick a code, e.g.
   `maisonmethod` -> your dashboard is `maisonmethod.goatcounter.com`.
2. Put the code in `brand/brand.json` -> `analytics.goatcounter_code`.
3. Rebuild + push. Pageviews appear within a minute of the next visit.

## 5. Meta pixel (only before ads; skip until then)

1. business.facebook.com -> create a Business portfolio -> Events Manager ->
   Connect data -> Web -> create pixel.
2. Copy the pixel ID (a long number) into `brand/brand.json` ->
   `analytics.meta_pixel_id`. Rebuild + push. The consent banner now
   appears for new visitors; the pixel loads only after "That's fine".
3. Verify: Events Manager -> Test events -> open your site, accept the
   banner, land on `/thanks.html` -> you should see `PageView` then `Lead`.
4. Now follow `ads/meta-plan.md`.

## 6. Social accounts

1. TikTok: register the handle in `brand/brand.json` -> `social.tiktok`
   (fallbacks listed in `brand/social/bios.md`). Avatar: export
   `brand/social/avatar.svg` to 400x400 PNG. Bio text is in `bios.md`.
   Put the site URL in the link field.
2. Instagram: same assets, bio in `bios.md`. Cross-post the TikToks as
   Reels (remove the TikTok watermark; export from CapCut directly).
3. Start posting per `content/calendar.md`.

## Launch order (the whole test, end to end)

1. Steps 1-2 above (site live + waitlist storing emails). ~30 min.
2. Step 6: social accounts live, first 3 videos posted. Day 1.
3. Step 3: kit on sale, thank-you page upgraded. Week 1.
4. Post daily per `content/calendar.md`, log in `content/hooks-tracker.md`. Weeks 1-4.
5. Step 5 + `ads/meta-plan.md`: £100 probe using the top 3 organic hooks. Weeks 2-4.
6. Every Sunday: fill in `ops/scorecard.md`. At week 4, apply the decision
   gates in `ads/thresholds.md`.
