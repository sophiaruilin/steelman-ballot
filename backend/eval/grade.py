"""Accuracy evaluation for the California look-back (Nov 3, 2026).

    python -m backend.eval.grade                      # 6-prop sample, gpt-6-astra writer
    python -m backend.eval.grade --writer gpt-6-luna --props 1 3 39

For each prop: run the full pipeline (Analyst -> Critic -> rewrites), then a separate Grader scores the
final card against the official guide: claim fidelity, yes/no/fiscal correctness, and coverage of the
official arguments' key points. Results: output/eval/<writer>.json and output/eval/summary.md.

The look-back is "frozen in time" by construction: the official guide pages were published before the
election and contain no results, and the agents may only read allowlisted official pages.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from backend import config
from backend.agents.common import usage_dict
from backend.pipeline import research_measure
from backend.sources.web import fence

SAMPLE = ["1", "3", "5", "39", "41", "45"]   # bond, tax, recall rules, voter ID, tax limits, environmental review
EVAL_DIR = config.ROOT / "output" / "eval"


class ClaimGrade(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    note: str = ""


class Point(BaseModel):
    point: str
    rank: int = 0          # 1 = the side's most emphasized point
    covered: bool


class Grade(BaseModel):
    claims: list[ClaimGrade]
    yes_correct: bool
    no_correct: bool
    fiscal_correct: bool
    effect_notes: list[str] = []
    points_for: list[Point]
    points_against: list[Point]
    neutrality_issues: list[str] = []


@lru_cache(maxsize=1)
def grader() -> Agent[None, Grade]:
    model, settings = config.build_model(config.MODEL_NAME)
    return Agent(model, name="grader", output_type=Grade, model_settings=settings, retries=2,
                 instructions=(config.PROMPTS_DIR / "grader.md").read_text(encoding="utf-8"))


def official_pages(record: dict) -> dict[str, str]:
    from backend.sources.web import WebReader
    r = WebReader()
    return {u: r.fetch(u).data["text"] for u in record["sources"] if "voterguide.sos.ca.gov" in u}


async def grade_card(record: dict, pages: dict[str, str]) -> tuple[Grade, dict]:
    prompt = ("CARD (JSON):\n" + json.dumps(record["card"], ensure_ascii=False, indent=1)
              + "\n\nOFFICIAL PAGES:\n" + "\n\n".join(fence(u, t) for u, t in pages.items()))
    res = await grader().run(prompt, usage_limits=UsageLimits(request_limit=3, total_tokens_limit=60_000))
    return res.output, usage_dict(res.usage)


def _top3(g: Grade) -> float | None:
    """Share of each side's 3 highest-ranked official points that the card covers."""
    top = []
    for pts in (g.points_for, g.points_against):
        top += sorted(pts, key=lambda p: p.rank or 99)[:3]
    return round(sum(p.covered for p in top) / len(top), 3) if top else None


def score(g: Grade) -> dict:
    n = len(g.claims)
    sup = sum(c.verdict == "supported" for c in g.claims)
    con = sum(c.verdict == "contradicted" for c in g.claims)
    pts = g.points_for + g.points_against
    return {
        "claims": n, "supported": sup, "unsupported": n - sup - con, "contradicted": con,
        "fidelity": round(sup / n, 3) if n else None,
        "effects_correct": sum([g.yes_correct, g.no_correct, g.fiscal_correct]),
        "coverage_for": round(sum(p.covered for p in g.points_for) / len(g.points_for), 3) if g.points_for else None,
        "coverage_against": round(sum(p.covered for p in g.points_against) / len(g.points_against), 3) if g.points_against else None,
        "coverage": round(sum(p.covered for p in pts) / len(pts), 3) if pts else None,
        "coverage_top3": _top3(g),
        "neutrality_issues": len(g.neutrality_issues),
    }


async def run(props: list[str], writer: str) -> dict:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in props:
        rec = await research_measure("CA", n, writer_model=writer)
        rec.pop("_source_text", None)
        pages = official_pages(rec)
        g, gu = await grade_card(rec, pages)
        s = score(g)
        rows.append({"prop": n, "verified": rec["steelman_verified"], "turing": rec["turing"],
                     "rewrites": rec["rewrites"], "score": s, "grade": g.model_dump(),
                     "usage": rec["meta"]["usage_by_model"], "grader_usage": gu,
                     "seconds": rec["meta"]["seconds"], "card": rec["card"]})
        print(f"Prop {n}: verified={rec['steelman_verified']} turing={rec['turing']} rewrites={rec['rewrites']} "
              f"fidelity={s['fidelity']} contradicted={s['contradicted']} effects={s['effects_correct']}/3 "
              f"coverage={s['coverage']}", flush=True)
    out = {"writer": writer, "critic": config.CRITIC_MODEL, "props": props, "rows": rows}
    (EVAL_DIR / f"{writer}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


async def regrade(src: str = "gpt-6-astra.json") -> dict:
    """Grade the cards already in an eval file again (no new cards written) and update the scores."""
    path = EVAL_DIR / src
    run = json.loads(path.read_text(encoding="utf-8"))
    for row in run["rows"]:
        rec = {"card": row["card"], "sources": [u for u in row.get("sources", [])] or
               [f"https://voterguide.sos.ca.gov/propositions/{row['prop']}/{p}"
                for p in ("title-summary.htm", "analysis.htm", "arguments-rebuttals.htm")]}
        g, gu = await grade_card(rec, official_pages(rec))
        row["grade"], row["score"], row["grader_usage"] = g.model_dump(), score(g), gu
        s = row["score"]
        print(f"Prop {row['prop']}: fidelity={s['fidelity']} contradicted={s['contradicted']} "
              f"coverage={s['coverage']} top3={s['coverage_top3']}", flush=True)
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    return run


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--writer", default=config.MODEL_NAME)
    ap.add_argument("--props", nargs="*", default=SAMPLE)
    ap.add_argument("--regrade", metavar="EVAL_FILE", help="re-grade cards in output/eval/EVAL_FILE")
    a = ap.parse_args()
    asyncio.run(regrade(a.regrade) if a.regrade else run(a.props, a.writer))
