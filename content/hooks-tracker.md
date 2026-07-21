# Hooks tracker

Log every post here. This table is the account's only judge (see the "post,
do not agonise" rule in `workflow.md`) and the source for Meta ad creatives.

## How to fill it in

- Log the row the day you post (date, script id, hook text). Fill metrics at
  24h and 72h from TikTok Studio > Analytics > the post's detail view.
- Watch-through % = "watched full video" if shown, otherwise average watch
  time divided by video length.
- Profile visits and link clicks come from the post's analytics; signups
  attributed = MailerLite signups in the 24h after posting minus the daily
  baseline (imperfect, fine at this scale; note big overlaps in Notes).
- Hook version matters: `PM-01-h1` and `PM-01-h2` (a re-hook of the same
  video) get separate rows. That is the whole experiment.

## Verdict rules (apply at 72h, during the Sunday review)

- kill: views below your account's median AND watch-through under 20%.
  Do not re-hook it; the body did not hold anyone.
- iterate: watch-through 35%+ but views below median. The video works, the
  hook did not. Write 2 new hooks; it goes in a re-hook slot (`calendar.md`).
- scale: views at 2x your median or better. Re-hook it again anyway (winners
  usually have a second, bigger hook in them) and flag it as an ad candidate.

Recompute your median over the trailing 14 posts; it will move fast in month
one.

## The ads handoff

Every second Sunday (calendar days 14 and 28): rank all rows by 72h views.
The top 3 hooks become the Meta ad creatives. For each: note the script id,
the exact hook text, and the watch-through %, then take them to the `ads/`
folder work as the opening text/first frame of the ad variants. Organic TikTok
is the cheap testing ground; Meta spend only ever goes behind hooks this table
has already proven.

## The log

| Date | Script id | Hook text | Views 24h | Views 72h | Watch-through % | Profile visits | Link clicks | Signups attr. | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | PM-01-h1 | You do not need a design degree | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |
| YYYY-MM-DD | | | | | | | | | | |

Add rows as needed; keep the newest at the bottom so the trailing-14 median
is always the last 14 rows.

## Fortnightly ad candidates

| Review date | Rank | Script id | Hook text | 72h views | Watch-through % | Sent to ads/ ? |
|---|---|---|---|---|---|---|
| | 1 | | | | | |
| | 2 | | | | | |
| | 3 | | | | | |
