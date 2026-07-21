# Meta ads plan, probe 1 (£100)

This is the complete plan for spending £100 on Meta to test whether the Maison
Method message converts cold traffic. It is written so that someone who has
never opened Ads Manager can execute it. It is a probe, not a launch: organic
TikTok is the primary channel, and the hooks that win there are the hooks we
pay to amplify here.

**The funnel being tested:**
Meta ad → landing page → waitlist email signup (the `Lead` pixel event fires
on `/thanks.html`) → £12 First Client Kit offer on the thank-you page (the
`Purchase` pixel event fires on completed checkout).

Decision rules live in `ads/thresholds.md`. This file covers structure, setup
and spend.

---

## 1. Campaign structure

One campaign. Two ad sets. That is all £100 supports.

```
Campaign: MM-Probe1-Leads        (objective: Leads, budget at ad set level)
├── Ad set: side-hustlers        £3.50/day
│     ├── Ads from copy/side-hustlers.md          (2 video, 1 static)
│     └── Ads from copy/stay-at-home-parents.md   (creative variant, see below)
└── Ad set: career-switchers     £3.50/day
      └── Ads from copy/career-switchers.md       (2 video, 1 static)
```

- **Objective:** Leads. Conversion location: **Website** (not Instant Forms;
  we want people on our page, on our list, seeing the £12 offer).
- **Performance goal:** Maximise number of conversions.
- **Conversion event:** `Lead` (fires on `/thanks.html`).

**Why stay-at-home parents are a creative variant, not a third ad set.**
Three ad sets at £100 means about £33 each, which is not enough for even one
ad set to produce a readable signal (see section 8). The stay-at-home-parent
audience also overlaps heavily with the broad side-hustler audience Meta will
build, so we do not need a separate targeting bucket to reach them. We let
the school-hours creative run inside the side-hustlers ad set and read its
per-ad results. If it clearly outperforms, it earns its own ad set in probe 2.

## 2. CBO vs ABO: use ABO

Set the budget at the **ad set level** (ABO), fixed **£3.50/day per ad set**.
Do not use Advantage campaign budget (CBO). At £7/day total, CBO will starve
one ad set within days based on early noise, and we are buying information
about two messages, not delivery efficiency. ABO guarantees each message gets
its full £49 over 14 days unless we deliberately kill it.

## 3. Budget and schedule

- **£3.50/day × 2 ad sets × 14 days = £98.** The remaining £2 is buffer for
  Meta's daily-budget overshoot (it can spend up to 25% over on a given day,
  balancing across the week).
- Run continuously, no dayparting. At this budget, restricting hours only
  slows learning.
- Both ad sets will likely sit in the learning phase for the whole probe
  (learning needs ~50 conversions per ad set per week, which £24.50/week will
  not buy). That is fine and expected. Ignore the "Learning limited" warning;
  it does not invalidate the data, it just means CPLs will be noisier.

## 4. Targeting: UK only

Location: United Kingdom. Age 24 to 54. All genders. English (UK) only.

**Why not Europe at £100:**

1. **Language.** The landing page, the kit and the ads are in British
   English. Paying to send Dutch or German scrollers to an English page adds
   a translation variable we cannot read at this scale.
2. **CPM stability.** One country means one auction. Mixing UK and EU
   markets, where CPMs differ by 2 to 3 times, lets Meta chase the cheapest
   impressions (often the least relevant) and makes the CPL uninterpretable.
3. **One variable at a time.** This probe tests the message. Geography is a
   separate test for a later probe, if the message works.

## 5. Advantage+ audience vs manual, and interests to seed

Use **Advantage+ audience** with interest **suggestions** seeded (Meta treats
your interests as a starting signal and expands from there). At £100 either
approach works, but the pixel is brand new with zero history, so the seeds
matter more than usual. Do not tick "Advantage detailed targeting" off, and do
not layer exclusions; keep it broad and let the `Lead` event do the narrowing.

**Interest seeds (both ad sets):**

- Interior design
- Home décor / DIY (Do it yourself)
- Mrs Hinch (and similar UK home-content interests Meta suggests, e.g.
  Stacey Solomon, cleaning and home organisation pages)
- IKEA, Dunelm, Farrow & Ball (home retail signals)
- Pinterest

**Add to side-hustlers only:** Side hustle / Second job / Extra income.
**Add to career-switchers only:** Career change / Career development /
Professional development.

## 6. Placements

**Advantage+ placements** (automatic). Do not hand-pick. Expect Reels and
Stories to take most of the delivery, because our creative is 9:16 video that
looks native there and those placements are cheapest. That is the point: the
ads are rebuilt from organic TikTok hooks and belong in vertical video. The
one static image per ad set covers Feed without fighting the algorithm.

## 7. When to kill vs when to let learn

- **Days 1 to 3: touch nothing.** No budget changes, no pausing, no new ads.
  Every edit resets delivery and burns money re-learning.
- **From day 4:** check daily, but act only on the rules below.
- **Kill an ad set** if its CPL is over **£4 after £25 spend** in that ad
  set. Reallocate its £3.50/day to the surviving ad set (accept the small
  learning reset; at this scale learning never completes anyway).
- **Within an ad set:** if one ad has spent £15 with zero leads while a
  sibling ad has leads, pause the zero. Otherwise leave the ads alone and let
  Meta distribute.
- **Do not add new creative mid-flight** unless an entire ad set has died.
  New ads reset the auction story and we lose the clean 14-day read.

Full decision thresholds (page conversion, tripwire, 4-week gates) are in
`ads/thresholds.md`.

## 8. UTM conventions

Every ad's website URL carries UTMs so GoatCounter and MailerLite can tell us
which ad produced which signup, independently of Meta's own reporting.

```
utm_source=meta&utm_medium=paid&utm_campaign=probe1&utm_content=<adset>-<creative>
```

Ad set slugs: `side-hustlers`, `career-switchers`.
Creative slugs are defined in each copy file. Examples:

```
?utm_source=meta&utm_medium=paid&utm_campaign=probe1&utm_content=side-hustlers-v1-evenings
?utm_source=meta&utm_medium=paid&utm_campaign=probe1&utm_content=side-hustlers-sahp-v1-schoolrun
?utm_source=meta&utm_medium=paid&utm_campaign=probe1&utm_content=career-switchers-v2-proof
```

Note the stay-at-home-parent creatives carry the `side-hustlers-sahp-` prefix
because they run inside the side-hustlers ad set.

## 9. Setup checklist (Ads Manager, step by step)

Do these in order. Steps 1 to 6 are plumbing; do not spend a penny until
step 6 passes.

1. **Business assets.** Create (or confirm) a Meta Business Portfolio at
   business.facebook.com, add the Maison Method Facebook Page and Instagram
   account, and create an ad account set to GBP, UK time zone.
2. **Create the pixel (dataset).** Events Manager → Connect data →
   Web → name it `Maison Method`. Copy the pixel ID into
   `brand/brand.json` (`analytics.meta_pixel_id`, currently a TODO) and
   confirm the site templates render the base pixel code on every page.
3. **Wire the Lead event.** On `/thanks.html` only, fire
   `fbq('track', 'Lead');` after the base pixel loads. The event must not
   fire on the landing page itself.
4. **Wire the Purchase event.** In Payhip, add the same pixel ID
   (Payhip fires `Purchase` with value on completed checkout). If Payhip is
   not connected yet, note it: leads still count, but tripwire reads will be
   manual (Payhip sales report) until it is.
5. **Check the form is real.** `brand/brand.json` shows the MailerLite form
   action is still a TODO, with a `mailto:` fallback. **Do not launch on the
   fallback**: a `mailto:` never reaches `/thanks.html`, so the Lead event
   never fires and Meta optimises on nothing. Finish ops/setup.md step 2
   first.
6. **Verify with Test Events.** Events Manager → your dataset → Test events
   tab. Open the landing page in the test browser, submit the form with a
   real test email, land on `/thanks.html`, and confirm you see `PageView`
   then `Lead` appear in the stream. Click through to the kit checkout and
   complete a test purchase if possible; confirm `Purchase`. Remove your
   test email from MailerLite afterwards.
7. **Create the campaign.** Ads Manager → Create → objective **Leads** →
   name `MM-Probe1-Leads`. Decline Advantage+ setup prompts that hide the
   manual options; choose manual campaign setup. Leave campaign budget
   (CBO) **off**.
8. **Ad set 1: `side-hustlers`.** Conversion location Website, pixel
   `Maison Method`, event `Lead`. Performance goal: maximise conversions.
   Budget £3.50/day. Location UK, age 24 to 54, Advantage+ audience with the
   side-hustler seeds from section 5. Placements: Advantage+.
9. **Ad set 2: `career-switchers`.** Duplicate ad set 1, rename, swap the
   persona-specific interest seeds. Everything else identical.
10. **Build the ads.** For each ad set, create the ads specified in the
    matching `ads/copy/*.md` file (2 faceless videos and 1 static each, plus
    the 3 stay-at-home-parent creatives inside side-hustlers). Primary text,
    headline and description come straight from those files. Website URL is
    the landing page **with the full UTM string** from section 8. CTA
    button: **Sign up**.
11. **Turn off per-ad enhancements you did not choose.** Under Advantage+
    creative, switch off automatic text rewrites and music additions; leave
    aspect-ratio adaptation on. The copy passed voice and policy review as
    written; Meta must not rewrite it.
12. **Publish, then check Meta's ad review status** (usually under an hour,
    sometimes 24). If an ad is rejected, do not argue in edits; check it
    against the policy notes in the copy file, adjust, resubmit.
13. **Day 1 sanity check.** After the first few hundred impressions, click
    your own ad preview link and confirm the UTMs survive to the landing
    page URL bar and that GoatCounter shows the visit.
14. **Log daily from day 4.** One row per ad set per day: spend, impressions,
    CPM, link clicks, landing page views, Leads, CPL. Five minutes; do not
    change anything unless a section 7 rule fires.
15. **Day 14: stop, read, decide** using `ads/thresholds.md`.

## 10. What the £100 buys, and what it cannot tell you

**Expected outcome:** roughly **25 to 60 leads** at a **£1.70 to £4.00 CPL**
(UK lead-gen CPMs for this kind of audience typically land £8 to £15; the
spread depends mostly on landing page conversion).

**Decisions this data CAN support:**

- **Kill or continue on the message.** If cold strangers will not give an
  email for "first paying design client in 30 days, no degree required" at
  under £4 a lead, the message (or the page) needs work before any more
  spend. That is the single question this probe answers.
- **Landing page sanity.** Ad clicks × page conversion rate is readable at
  a few hundred clicks (thresholds in `thresholds.md`).
- **Directional creative read.** Which hooks earn cheap clicks feeds back
  into organic TikTok, even at small n.
- **Plumbing proof.** Pixel, events, UTMs and the tripwire flow verified
  end to end before any bigger spend.

**Decisions this data CANNOT support:**

- **Declaring a persona winner.** 12 to 30 leads per ad set is nowhere near
  statistical separation; at ~£3 CPL you need roughly 50+ leads per ad set
  before a gap between them means anything. Treat persona results as a hint
  for probe 2's design, not a verdict.
- **Forecasting CPL at scale.** Learning-limited ad sets at £3.50/day do not
  predict costs at £35/day.
- **Tripwire conversion rate.** With 25 to 60 leads, take-rate maths is
  unstable; any sale at all is the signal (see `thresholds.md`).
- **Anything about Europe.** We did not test it.
