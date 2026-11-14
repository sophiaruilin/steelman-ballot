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
from datetime import date

from backend import cache, config
from backend.agents import critic, measure_analyst
from backend.agents.common import ResearchDeps, log_run, usage_dict
from backend.sources.web import WebReader


def _add(total: dict, u: dict, model: str) -> None:
    t = total.setdefault(model, {k: 0 for k in u})
    for k, v in u.items():
        t[k] = t.get(k, 0) + (v or 0)


async def research_measure(state: str, number: str, election: str = "2026-11-03",
                           urls: list[str] | None = None, reader: WebReader | None = None,
                           writer_model: str | None = None) -> dict:
    urls = urls or measure_analyst.start_urls(state, number)
    deps = ResearchDeps(reader=reader or WebReader())
    measure_id = f"{state.upper()}-{election}-prop-{number}"
    prompt = (f"Measure: {state.upper()} Proposition {number}, election {election}. measure_id = '{measure_id}'.\n"
              "Start by fetching these official pages:\n" + "\n".join(f"- {u}" for u in urls))
    writer = writer_model or config.MODEL_NAME
    analyst = measure_analyst.get_agent(writer)
    usage: dict = {}
    rounds = []
    t0 = time.time()

    result = await analyst.run(prompt, deps=deps, usage_limits=measure_analyst.PER_MEASURE_LIMITS)
    _add(usage, usage_dict(result.usage), "writer:" + writer)

    for rnd in range(config.MAX_CRITIC_ROUNDS + 1):
        card = result.output
        verdict, checks, cu = await critic.review(card, deps.fetched)
        _add(usage, usage_dict(cu), "critic:" + config.CRITIC_MODEL)
        rounds.append({"round": rnd, "verdict": verdict.model_dump(), "checks": checks})
        if verdict.verdict == "pass" or rnd == config.MAX_CRITIC_ROUNDS:
            break
        feedback = ("The neutrality critic asked for revisions. Make these edits using only the pages you "
                    "already read, then return the full corrected card.\n" + verdict.instructions)
        result = await analyst.run(feedback, deps=deps, message_history=result.all_messages(),
                                   usage_limits=measure_analyst.PER_MEASURE_LIMITS)
        _add(usage, usage_dict(result.usage), "writer:" + writer)

    final = rounds[-1]["verdict"]
    record = {
        "measure_id": measure_id,
        "card": result.output.model_dump(),
        "steelman_verified": final["verdict"] == "pass",
        "turing": {"yes": final["turing_yes"]["score"], "no": final["turing_no"]["score"]},
        "rewrites": len(rounds) - 1,
        "review_rounds": rounds,
        "sources": list(deps.fetched),
        "meta": {"seconds": round(time.time() - t0, 1), "writer_model": writer, "usage_by_model": usage,
                 "blocked": deps.blocked, "injection_flags": deps.injection_flags},
    }
    record["_source_text"] = dict(deps.fetched)   # for cache fingerprints; removed before saving
    log_run({"agent": "pipeline.measure", "measure_id": measure_id, "verified": record["steelman_verified"],
             "rewrites": record["rewrites"], "turing": record["turing"], **record["meta"]})
    return record


async def get_measure(state: str, number: str, election: str = "2026-11-03", *, now=None,
                      reader: WebReader | None = None) -> tuple[dict, str]:
    """Serve a measure card from the contest cache, or research it. Returns (record, action).

    One research run per statewide measure per refresh window, shared by every voter in the state.
    """
    key = cache.contest_key(state, "statewide", f"prop-{number}")
    entry = cache.load(key, election)
    now = now or cache.utcnow()
    action = cache.decide(entry, now=now, election_day=date.fromisoformat(election))
    if action == "serve":
        return entry.payload, action
    if action == "check" and entry is not None:
        reader = reader or WebReader()
        fresh = {}
        for url in entry.payload.get("sources", []):
            try:
                fresh[url] = cache.fingerprint_text(reader.fetch(url).data["text"])
            except Exception:
                fresh[url] = entry.fingerprints.get(url, "")   # unreachable: keep the old card
        if not cache.changed_sources(entry.fingerprints, fresh):
            entry.checked_at = now
            cache.save(entry)
            return entry.payload, "checked_unchanged"
    record = await research_measure(state, number, election, reader=reader)
    fps = {u: cache.fingerprint_text(t) for u, t in record.pop("_source_text", {}).items()}
    cache.save(cache.CacheEntry(key, election, built_at=now, checked_at=now, fingerprints=fps, payload=record))
    return record, "researched"


def save(record: dict) -> str:
    record = {k: v for k, v in record.items() if not k.startswith("_")}
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
