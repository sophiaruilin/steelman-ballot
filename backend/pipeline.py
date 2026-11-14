"""Research pipeline for one measure: Analyst writes -> Critic reviews -> rewrite (at most twice).

    python -m backend.pipeline CA 3

The rewrite continues the Analyst's own conversation (message history), so the source pages are
already in context and aren't fetched or re-sent from scratch. If the card still fails after
config.MAX_CRITIC_ROUNDS rewrites, it's published with steelman_verified = False, which the
dashboard shows as a "steelman unverified" badge.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from backend import config
from backend.agents import critic, measure_analyst
from backend.agents.common import ResearchDeps, log_run, usage_dict
from backend.sources.web import WebReader


def _add(total: dict, u: dict, model: str) -> None:
    t = total.setdefault(model, {k: 0 for k in u})
    for k, v in u.items():
        t[k] = t.get(k, 0) + (v or 0)


async def research_measure(state: str, number: str, election: str = "2026-11-03",
                           urls: list[str] | None = None, reader: WebReader | None = None) -> dict:
    urls = urls or measure_analyst.start_urls(state, number)
    deps = ResearchDeps(reader=reader or WebReader())
    measure_id = f"{state.upper()}-{election}-prop-{number}"
    prompt = (f"Measure: {state.upper()} Proposition {number}, election {election}. measure_id = '{measure_id}'.\n"
              "Start by fetching these official pages:\n" + "\n".join(f"- {u}" for u in urls))
    analyst = measure_analyst.get_agent()
    usage: dict = {}
    rounds = []
    t0 = time.time()

    result = await analyst.run(prompt, deps=deps, usage_limits=measure_analyst.PER_MEASURE_LIMITS)
    _add(usage, usage_dict(result.usage), config.MODEL_NAME)

    for rnd in range(config.MAX_CRITIC_ROUNDS + 1):
        card = result.output
        verdict, checks, cu = await critic.review(card, deps.fetched)
        _add(usage, usage_dict(cu), config.CRITIC_MODEL)
        rounds.append({"round": rnd, "verdict": verdict.model_dump(), "checks": checks})
        if verdict.verdict == "pass" or rnd == config.MAX_CRITIC_ROUNDS:
            break
        feedback = ("The neutrality critic asked for revisions. Make these edits using only the pages you "
                    "already read, then return the full corrected card.\n" + verdict.instructions)
        result = await analyst.run(feedback, deps=deps, message_history=result.all_messages(),
                                   usage_limits=measure_analyst.PER_MEASURE_LIMITS)
        _add(usage, usage_dict(result.usage), config.MODEL_NAME)

    final = rounds[-1]["verdict"]
    record = {
        "measure_id": measure_id,
        "card": result.output.model_dump(),
        "steelman_verified": final["verdict"] == "pass",
        "turing": {"yes": final["turing_yes"]["score"], "no": final["turing_no"]["score"]},
        "rewrites": len(rounds) - 1,
        "review_rounds": rounds,
        "sources": list(deps.fetched),
        "meta": {"seconds": round(time.time() - t0, 1), "usage_by_model": usage,
                 "blocked": deps.blocked, "injection_flags": deps.injection_flags},
    }
    log_run({"agent": "pipeline.measure", "measure_id": measure_id, "verified": record["steelman_verified"],
             "rewrites": record["rewrites"], "turing": record["turing"], **record["meta"]})
    return record


def save(record: dict) -> str:
    out = config.ROOT / "output" / "cards" / f"{record['measure_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    state, number = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("CA", "3")
    rec = asyncio.run(research_measure(state, number))
    path = save(rec)
    for r in rec["review_rounds"]:
        v = r["verdict"]
        print(f"round {r['round']}: {v['verdict']}  turing yes={v['turing_yes']['score']} no={v['turing_no']['score']}  "
              f"swap={'ok' if v['swap_test_pass'] else 'FAIL'}  words={r['checks']['words']}")
        for k in ("fidelity_problems", "label_problems", "loaded_or_overconfident", "never_list", "false_balance", "swap_notes"):
            for x in v[k][:3]:
                print(f"   {k}: {x}")
    print("verified:", rec["steelman_verified"], "| usage:", json.dumps(rec["meta"]["usage_by_model"]))
    print("saved", path)
