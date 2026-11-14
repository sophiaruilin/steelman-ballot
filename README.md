# Steelman Ballot

**Get informed: the strongest case for every side.**

Enter any U.S. address and get a plain-language, nonpartisan briefing on everything on your ballot. For each measure: **what would change** (today vs. if it passes), and each side's strongest case **on the merits**, with one headline per side and more reasons a tap away. For each candidate: what they **say**, what they've **done**, and who **funds** them. Every claim links to its source, and the app never tells you how to vote.

> 🚧 **Work in progress.** This is a Yale SOM final project, due 11/23/2026. The data layer is working; the agents and dashboard are being built.

## How it works
A team of AI agents researches each ballot from public sources. One research run per jurisdiction per day is shared by every voter there.

```
Address ─► [Ballot Mapper] ─► races and measures
                 │
       ┌─────────┴──────────┐
       ▼                    ▼
[Measure Analyst]×N   [Candidate Profiler]×N
       └─────────┬──────────┘
                 ▼
     [Fact-Check & Neutrality Critic] ──(fails)──► rewrite
                 ▼ (passes)
         [Dashboard Writer] ─► [Translator] ─► EN · ES · 中文 · VI
```

**Sources:** U.S. Census Geocoder and American Community Survey (ACS) · OpenFEC · Congress.gov · Open States · Vote Smart · Ballotpedia · VOTE411 · official state and county election offices. The official ballot always wins when sources disagree.

## Setup
You need **Python 3.11+**.

```bash
cd steelman-ballot
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env            # macOS/Linux: cp .env.example .env
# then fill in your keys (see comments in .env.example for where to sign up)
```

| Key | Used for | Cost |
|---|---|---|
| `PORTKEY_API_KEY` | AI model (gpt-6-astra) | Class key |
| `DATA_GOV_API_KEY` | OpenFEC + Congress.gov | Free |
| `OPENSTATES_API_KEY` | State legislators and votes | Free |
| `CENSUS_API_KEY` | ACS local demographics | Free |
| `VOTESMART_API_KEY` | Voting records and ratings (optional) | Free on request |

## Run the web app
```bash
python -m uvicorn backend.app:app --port 8020     # then open http://localhost:8020
```
Mobile-first and installable (Add to Home Screen); works inside WhatsApp and WeChat browsers; the last ballot
and opened cards stay readable offline. `SNAPSHOT_ONLY=1` (default) serves only researched cards and never calls a model.

## Deploy (Render, free)
In Render: **New → Blueprint →** pick this repo → **Apply** (uses `render.yaml`). No API keys are needed:
the public site runs in snapshot mode. After the first deploy, set `PUBLIC_BASE_URL` to the site's address so
share links and QR codes point to it.

## Try the agents
```bash
python -m backend.agents.ballot_mapper "1315 10th St, Sacramento, CA 95814"
python -m backend.pipeline CA 3                    # Analyst + Critic -> output/cards/CA-2026-11-03-prop-3.json
python -m backend.agents.candidate_profiler CA lt-governor
```

## Evaluate (California look-back)
```bash
python -m backend.eval.grade                                   # 6-prop sample, gpt-6-astra writer
python -m backend.eval.grade --writer gpt-6-luna --props 1 3 39
python -m backend.eval.summary                                 # -> output/eval/summary.md
```

## Tests
```bash
python -m pytest -q
```
The tests run offline: no network and no model calls.

## Project layout
```
steelman-ballot/
├── backend/
│   ├── config.py          keys, model, cache policy, spending limits
│   ├── cache.py           shared per-jurisdiction cache + refresh rules
│   ├── models.py          card formats (MeasureCard, Steelman, Claim)
│   ├── agents/            ballot_mapper, measure_analyst, candidate_profiler, critic,
│   │                      common (safe fetch tool, citation + quote checks)
│   ├── pipeline.py        Analyst -> Critic -> rewrite loop (max 2); per-contest cache
│   ├── eval/              CA look-back grader + summary (output/eval/summary.md)
│   ├── share.py           WhatsApp / WeChat / share-sheet text (always both sides)
│   ├── sources/           one adapter per data source: geocoder, fec (Funded by),
│   │                      congress + openstates (Did), http (allowlisted client),
│   │                      filters, web (safe page reader), replay (test tapes)
│   └── prompts/           system prompts for each agent
├── backend/app.py         web API: ballot, cards, share text, QR, share pages (Open Graph)
├── frontend/              mobile-first web app (plain HTML/CSS/JS, no CDNs), PWA + offline
├── tests/                 offline tests + saved API responses
├── data/                  demo snapshots (runtime cache is git-ignored)
├── output/                evaluation results, report assets
└── AI_prompts.md          log of the prompts used to build this project
```

## Principles
- **Steelman, never strawman.** Each side is stated so that its own supporters would sign it.
- **On the merits.** Cards argue about what the change would do, never about the other side's motives, funders or party labels.
- **Facts are separate from arguments.** "What the evidence says" is kept apart from the steelmen, so there's no false balance.
- **Official sources win** on voting instructions, dates and ballot contents.
- **No persuasion.** Your priorities change the order of the cards, never their content.
- **Addresses are not stored**, only the district key.

## License
MIT. See [LICENSE](LICENSE).
