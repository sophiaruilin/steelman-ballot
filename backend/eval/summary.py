"""Summarize evaluation runs into output/eval/summary.md (accuracy + tokens, astra vs luna writer).

    python -m backend.eval.summary
"""

from __future__ import annotations

import json
from statistics import mean

from backend.eval.grade import EVAL_DIR


def _tokens(row: dict) -> dict:
    t = {"input": 0, "cached": 0, "output": 0}
    for u in row["usage"].values():          # app cost only (writer + critic), grader excluded
        t["input"] += u["input_tokens"]
        t["cached"] += u["cache_read_tokens"]
        t["output"] += u["output_tokens"]
    return t


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(mean(xs), 3) if xs else None


def table(run: dict) -> tuple[str, dict]:
    lines = ["| Prop | Verified | Turing (Yes/No) | Rewrites | Claims | Supported | Unsupported | Contradicted | "
             "Yes/No/Fiscal correct | Argument coverage | Top-3 coverage | Input tok | Cached | Output tok |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in run["rows"]:
        s, t = r["score"], _tokens(r)
        lines.append(f"| {r['prop']} | {'yes' if r['verified'] else 'no'} | {r['turing']['yes']}/{r['turing']['no']} | "
                     f"{r['rewrites']} | {s['claims']} | {s['supported']} | {s['unsupported']} | {s['contradicted']} | "
                     f"{s['effects_correct']}/3 | {s['coverage']} | {s.get('coverage_top3', '-')} | {t['input']:,} | {t['cached']:,} | {t['output']:,} |")
    rows = run["rows"]
    agg = {
        "props": len(rows),
        "verified": sum(r["verified"] for r in rows),
        "fidelity": _avg([r["score"]["fidelity"] for r in rows]),
        "contradicted": sum(r["score"]["contradicted"] for r in rows),
        "effects_correct": f"{sum(r['score']['effects_correct'] for r in rows)}/{3 * len(rows)}",
        "coverage": _avg([r["score"]["coverage"] for r in rows]),
        "coverage_top3": _avg([r["score"].get("coverage_top3") for r in rows]),
        "rewrites": _avg([r["rewrites"] for r in rows]),
        "turing_min_avg": _avg([min(r["turing"].values()) for r in rows]),
        "input_per_prop": round(mean(_tokens(r)["input"] for r in rows)),
        "cached_per_prop": round(mean(_tokens(r)["cached"] for r in rows)),
        "output_per_prop": round(mean(_tokens(r)["output"] for r in rows)),
        "seconds_per_prop": round(mean(r["seconds"] for r in rows), 1),
    }
    return "\n".join(lines), agg


def main():
    runs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(EVAL_DIR.glob("gpt-*.json"))}
    out = ["# California look-back: accuracy and cost (Nov 3, 2026 propositions)", "",
           "Each card: Analyst writes -> Critic (gpt-6-luna) reviews -> up to 2 rewrites. A separate Grader then "
           "scores the final card against the official voter guide (Legislative Analyst = answer key).", ""]
    aggs = {}
    for name, run in runs.items():
        t, agg = table(run)
        aggs[name] = agg
        out += [f"## Writer: {name}", "", t, "", "**Averages:** " + json.dumps(agg), ""]
    if len(aggs) > 1:
        out += ["## Writer comparison (same props only)", ""]
        common = set.intersection(*(set(r["prop"] for r in runs[n]["rows"]) for n in runs))
        out += ["| Writer | Props | Fidelity | Contradicted | Effects correct | Coverage | Rewrites | Min Turing | "
                "Input/prop | Cached/prop | Output/prop |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, run in runs.items():
            sub = {**run, "rows": [r for r in run["rows"] if r["prop"] in common]}
            _, a = table(sub)
            out.append(f"| {name} | {sorted(common, key=int)} | {a['fidelity']} | {a['contradicted']} | {a['effects_correct']} | "
                       f"{a['coverage']} | {a['rewrites']} | {a['turing_min_avg']} | {a['input_per_prop']:,} | "
                       f"{a['cached_per_prop']:,} | {a['output_per_prop']:,} |")
    base = EVAL_DIR / "baseline_gpt-6-astra.json"
    if base.exists() and "gpt-6-astra" in runs:
        _, b = table(json.loads(base.read_text(encoding="utf-8")))
        _, a = table(runs["gpt-6-astra"])
        out += ["", "## Prompt change: each side's top 3 official points (same 6 props, same models)", "",
                "| Metric | Before | After |", "|---|---|---|"]
        for k, label in [("verified", "Steelmen verified (of 6)"), ("fidelity", "Claims supported"),
                         ("contradicted", "Claims contradicted"), ("effects_correct", "Yes/No/cost correct"),
                         ("coverage", "Official argument points covered"),
                         ("coverage_top3", "Each side's top-3 points covered"), ("rewrites", "Rewrites per prop"),
                         ("turing_min_avg", "Lowest Turing score (avg)"), ("input_per_prop", "Input tokens / prop"),
                         ("cached_per_prop", "Cached tokens / prop"), ("output_per_prop", "Output tokens / prop")]:
            out.append(f"| {label} | {b[k]} | {a[k]} |")
    if "gpt-6-astra" in runs:
        _, a = table(runs["gpt-6-astra"])
        rows = runs["gpt-6-astra"]["rows"]
        out += ["", "## Targets", "", "| Metric | Target | Current |", "|---|---|---|",
                f"| Claims supported by sources | >= 99%, 0 contradicted | {a['fidelity']:.1%}, {a['contradicted']} contradicted |",
                f"| Yes / No / cost correct | 100% | {a['effects_correct']} |",
                f"| Each side's top-3 official points covered | >= 95% | {a['coverage_top3']:.1%} |",
                f"| All official points covered | 85-90% | {a['coverage']:.1%} |",
                f"| Steelmen verified by the Critic | >= 85-90% | {a['verified']}/{len(rows)} |"]
    (EVAL_DIR / "summary.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
