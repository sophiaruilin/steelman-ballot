# Steelman Ballot: user testing kit

**Goal:** get real-user evidence for the report (Impact, Safety, Limits) and find the changes that would most improve the app.
**Who:** 5–8 people. Aim for a mix: different political leanings, at least one person who rarely votes on ballot measures,
and if possible one Spanish or Chinese reader. 5 is enough to find most usability problems.
**Time:** about 20 minutes each, in person or on a video call. Ask them to use **their own phone**.
**Live app:** https://steelman-ballot.onrender.com (open it a minute early: the free plan sleeps).

Files here:
- `session_script.md`: what to say and do, step by step
- `questions.md`: every question, ready to paste into a Google Form (or print)
- `results_template.csv`: one row per person; fill it in (or export the Google Form as CSV) and bring it back

When you bring results back, I'll compute the Impact numbers (time saved, comprehension gain, fairness, usability),
pull out the top issues, and turn the clear wins into changes.

## What each part measures (and which report section it feeds)

| Part | Measures | Report section |
|---|---|---|
| A. By hand vs. with the app (timed) | Minutes to feel ready to vote; comprehension score | **Impact** (time saved, better understanding) |
| B. Fairness check | "Would supporters of each side sign this?" 1–5; which way the card leans | **Safety** / neutrality evidence |
| C. Ease of use (UMUX-Lite, 2 items) | Standard usability score, 0–100 | **Impact** / Limits |
| D. Sharing on WhatsApp / WeChat | Did the link open and read well on their phone? | Mobile claims |
| E. Language (optional) | Spanish or Chinese reader: clear and natural? | Language access |
| F. Open questions | Most useful, most confusing, what's missing, would they use it | **Limits + next steps** |

## Design choices that make the numbers credible
- **Within-person comparison, balanced:** each person researches one measure by hand and a *different* measure with
  the app. Half do by-hand first, half do app first, and the two measures swap. That cancels out "the second one is
  always easier" and "one measure is just simpler."
- **Same comprehension questions** for by-hand and app, with answers checked against the official guide.
- **Privacy:** no names in the results (use P1, P2…). Political lean is optional. Don't record addresses.
- **Don't help during the timed parts.** Note where they get stuck instead; that's the most useful data.
