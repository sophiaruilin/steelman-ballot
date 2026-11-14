"""Research many contests in one run, in priority order, with a hard token budget.

    python -m backend.batch --plan                    # list what would run, no model calls
    python -m backend.batch --budget 1500000          # run until done or the budget is reached
    python -m backend.batch --only MA NYC             # just these groups

Groups, in order: CA re-runs for 6/6 verified (3, 5, 41) -> MA (9) -> NYC (5) -> rest of CA (8)
-> CA statewide races (6). Cards are saved to output/cards/ as each one finishes, so a run that
stops on budget or an API error keeps everything done so far. Already-verified cards are skipped
unless --force. Progress: output/batch_log.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

from backend import config

ELECTION = "2026-11-03"
LOG = config.ROOT / "output" / "batch_log.jsonl"
CARDS = config.ROOT / "output" / "cards"


def _tokens(usage_by_model: dict) -> int:
    return sum((u.get("input_tokens") or 0) + (u.get("output_tokens") or 0) for u in usage_by_model.values())


def _verified(card_id: str) -> bool:
    p = CARDS / f"{card_id}.json"
    return p.exists() and json.loads(p.read_text(encoding="utf-8")).get("steelman_verified", False)


def build_plan(groups: list[str] | None, force: bool) -> list[dict]:
    from backend.agents.ballot_mapper import ca_measures, ma_measures, nyc_measures
    from backend.sources.web import WebReader

    reader = WebReader()
    ca = {m.slug: m for m in ca_measures(reader, ELECTION)}
    plan = []

    def add(group, state, m, rerun=False):
        cid = f"{state}-{ELECTION}-{m.slug}"
        if groups and group not in groups:
            return
        if not force and not rerun and _verified(cid):
            return
        if rerun and not force and _verified(cid) and json.loads((CARDS / f"{cid}.json").read_text(encoding="utf-8")).get("format") == "v3.1":
            return
        plan.append({"group": group, "kind": "measure", "state": state, "id": cid, "measure": m})

    for n in ("3", "5", "41"):
        add("CA-rerun", "CA", ca[f"prop-{n}"], rerun=True)
    for m in ma_measures(reader, ELECTION):
        add("MA", "MA", m)
    for m in nyc_measures(reader, ELECTION):
        add("NYC", "NY", m)
    for slug, m in ca.items():
        if slug.split("-")[1] not in ("1", "3", "5", "39", "41", "45"):
            add("CA", "CA", m)
    for slug in ("governor", "sos", "controller", "treasurer", "insurance-commissioner", "superintendent"):
        cid = f"CA-{ELECTION}-{slug}"
        if (not groups or "CA-races" in groups) and (force or not (CARDS / f"{cid}.json").exists()):
            plan.append({"group": "CA-races", "kind": "race", "state": "CA", "id": cid, "slug": slug})
    return plan


async def run(plan: list[dict], budget: int) -> None:
    from backend.agents.candidate_profiler import profile_ca_statewide
    from backend.pipeline import research_measure, save

    LOG.parent.mkdir(parents=True, exist_ok=True)
    spent = 0
    for i, job in enumerate(plan, 1):
        if spent >= budget:
            print(f"Budget reached ({spent:,} of {budget:,} tokens). Stopping before {job['id']}.", flush=True)
            break
        t0 = time.time()
        try:
            if job["kind"] == "measure":
                m = job["measure"]
                rec = await research_measure(job["state"], m.number.split()[-1], ELECTION, urls=m.urls,
                                             slug=m.slug, label=m.label, display_number=m.number)
                rec["format"] = "v3.1"
                rec["scope"] = m.scope
                save(rec)
                used = _tokens(rec["meta"]["usage_by_model"])
                result = {"verified": rec["steelman_verified"], "turing": rec["turing"], "rewrites": rec["rewrites"]}
            else:
                rec = await profile_ca_statewide(job["slug"])
                out = CARDS / f"{rec['race_id']}.json"
                out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
                used = _tokens(rec["meta"]["usage_by_model"])
                result = {"candidates": len(rec["card"]["candidates"])}
        except Exception as e:   # keep going; one failed contest shouldn't stop the batch
            msg = str(e)[:300]
            print(f"[{i}/{len(plan)}] {job['id']}: ERROR {msg}", flush=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": job["id"], "error": msg, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
            if "quota" in msg.lower() or "credit" in msg.lower() or "Usage Limit" in msg:
                print("Out of API credit or quota: stopping.", flush=True)
                break
            continue
        spent += used
        line = {"id": job["id"], "group": job["group"], "tokens": used, "spent": spent,
                "seconds": round(time.time() - t0, 1), **result, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
        print(f"[{i}/{len(plan)}] {job['id']}: {result} · {used:,} tokens · total {spent:,}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="show the plan only (no model calls)")
    ap.add_argument("--budget", type=int, default=int(os.getenv("BATCH_TOKEN_BUDGET", "1500000")))
    ap.add_argument("--only", nargs="*", help="groups: CA-rerun MA NYC CA CA-races")
    ap.add_argument("--force", action="store_true", help="redo cards that are already verified")
    a = ap.parse_args()
    plan = build_plan(a.only, a.force)
    est = {"measure": 40_000, "race": 6_000}
    print(f"{len(plan)} contests, estimated ~{sum(est[j['kind']] for j in plan):,} tokens; budget {a.budget:,}")
    for j in plan:
        print(f"  {j['group']:9} {j['id']}")
    if not a.plan:
        asyncio.run(run(plan, a.budget))
