"""Tokenomics from real runs: every published card stores the tokens its agents used (meta.usage_by_model).

    python -m backend.eval.tokenomics            -> prints totals and writes output/eval/tokenomics.json

Prices are USD per 1M tokens (input, cached input, output), as published for the OpenAI API in Nov 2026
by price trackers (gpt-6-astra $10 / $1 / $50; gpt-6-luna $0.10 / $0.50, no separate cached rate, so cached
luna input is charged at the full input rate here). Confirm against your own OpenAI billing.
"""
from __future__ import annotations

import collections
import json
import statistics as st
from pathlib import Path

from backend import config

PRICES = {"gpt-6-astra": (10.0, 1.0, 50.0), "gpt-6-luna": (0.10, 0.10, 0.50)}
CARDS = config.ROOT / "output" / "cards"
FIELDS = ("requests", "input_tokens", "cache_read_tokens", "output_tokens")


def price_for(role_model: str) -> tuple[float, float, float]:
    return next((p for m, p in PRICES.items() if m in role_model), PRICES["gpt-6-astra"])


def cost(role_model: str, u: dict) -> float:
    pi, pc, po = price_for(role_model)
    inp, cached, out = u.get("input_tokens", 0), u.get("cache_read_tokens", 0), u.get("output_tokens", 0)
    return ((inp - cached) * pi + cached * pc + out * po) / 1e6


def card_rows() -> list[dict]:
    rows = []
    for f in sorted(CARDS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        meta = d.get("meta", {})
        usage = meta.get("usage_by_model", {})
        tot = collections.Counter()
        for v in usage.values():
            tot.update({k: v.get(k, 0) for k in FIELDS})
        rows.append({"id": f.stem, "kind": "measure" if "steelman_yes" in d["card"] else "race",
                     "tokens": dict(tot), "cost": sum(cost(k, v) for k, v in usage.items()),
                     "seconds": meta.get("seconds"), "verified": d.get("steelman_verified"),
                     "blocked": len(meta.get("blocked") or []),
                     "injection_flags": sum(len(v) if isinstance(v, list) else int(v or 0)
                                            for v in (meta.get("injection_flags") or {}).values()),
                     "by_model": usage})
    return rows


def summarize() -> dict:
    rows = card_rows()
    out = {"prices_usd_per_1M": PRICES, "kinds": {}}
    for kind in ("measure", "race"):
        R = [r for r in rows if r["kind"] == kind]
        agg = collections.Counter()
        for r in R:
            agg.update(r["tokens"])
        costs = [r["cost"] for r in R]
        n = len(R)
        out["kinds"][kind] = {
            "cards": n, "total": dict(agg),
            "per_card": {k: round(agg[k] / n) for k in FIELDS},
            "cost_total": round(sum(costs), 2), "cost_mean": round(st.mean(costs), 4),
            "cost_median": round(st.median(costs), 4), "cost_max": round(max(costs), 4),
            "seconds_median": st.median([r["seconds"] for r in R if r["seconds"]]),
        }
    by_model = collections.defaultdict(collections.Counter)
    for r in rows:
        for k, v in r["by_model"].items():
            by_model[k].update({x: v.get(x, 0) for x in FIELDS})
    out["by_model"] = {k: {**dict(v), "cost": round(cost(k, v), 2)} for k, v in by_model.items()}
    out["injection_flags"] = [(r["id"], r["blocked"], r["injection_flags"]) for r in rows if r["blocked"] or r["injection_flags"]]
    return out


if __name__ == "__main__":
    s = summarize()
    (config.ROOT / "output" / "eval" / "tokenomics.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k != "prices_usd_per_1M"}, indent=1))
