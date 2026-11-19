# Steelman Ballot

**Get informed: the strongest case for every side.**

**Live app:** https://steelman-ballot.onrender.com (free hosting: the first visit after a quiet spell can take ~30-60 seconds to wake up)

Enter an address or ZIP code and get a plain-language, nonpartisan briefing on what's on your ballot. For each measure: each side's **steelman** (its strongest case, **on the merits**, side by side), where they really disagree, what the evidence says, **what would change** (today vs. if it passes), and how voting on it works. For California's statewide races: what each office does, each candidate's official statement, and links to official campaign-finance records. Every claim links to its source, and the app never tells you how to vote. In English, Spanish and Chinese.

**Coverage (Nov 3, 2026 look-back demo):** California (14 statewide propositions + 8 statewide offices), Massachusetts (9 statewide ballot questions), New York (New York City's 5 charter proposals; no statewide proposals in 2026). Any other U.S. street address shows its districts and races.

*Think more deeply. Vote more thoughtfully.* The strongest argument isn't always your own.

## How it works
A team of AI agents researches each ballot from official sources. Each card is researched once and shared by every voter it applies to (cached per contest, refreshed as an election nears).

```
Address or ZIP ─► [Ballot Mapper] ─► districts, races and measures (official voter guides)
                        │
          ┌─────────────┴───────────────┐
          ▼                             ▼
 [Measure Analyst] (AI writer)   [Candidate Profiler] (CA statewide races)
          │  draft card
          ▼
 [Critic] (AI challenger, a different model): "Would this side sign it?" 1-5,
          swap test, source check ──(fails)──► specific fixes ─► rewrite (up to 3)
          │ (passes: "steelman verified")
          ▼
 [Translator] ─► EN · Español · 中文 (numbers checked unchanged)
```

**Sources:** official voter guides (California Secretary of State and Legislative Analyst; Massachusetts *Information for Voters*, read from the official PDF; NYC Votes) · U.S. Census Geocoder and ACS · OpenFEC · Congress.gov · Open States. The official ballot always wins when sources disagree.

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
| `OPENAI_API_KEY` | AI models (gpt-6-astra writer, gpt-6-luna challenger and translator); used first if set | Pay as you go |
| `PORTKEY_API_KEY` | Same models through the class gateway (used if no OpenAI key) | Class key |
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

## User testing
A 20-minute session script, questions and results template for testing with real voters:
[docs/user_testing](docs/user_testing/README.md) (by hand vs. with the app, fairness, ease of use, sharing).

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
│   ├── pipeline.py        Analyst -> Critic -> rewrite loop (max 3); per-contest cache
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
- **No persuasion.** No vote recommendations, no polls, no predictions.
- **Addresses are not stored**, only the district key.

## License
MIT. See [LICENSE](LICENSE).
