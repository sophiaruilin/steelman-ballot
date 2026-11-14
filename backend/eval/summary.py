"""Summarize evaluation runs into output/eval/summary.md (accuracy, cost, card versions, targets).

    python -m backend.eval.summary
"""

from __future__ import annotations

import json
from statistics import mean

from backend.eval.grade import EVAL_DIR

VERSIONS = [  # (file, label) in the order the card design evolved
    ("baseline_gpt-6-astra.json", "v1: pros/cons steelmen"),
    ("v2_top3_gpt-6-astra.json", "v2: + each side's top 3 official points"),
    ("gpt-6-astra.json", "v3: What changes + one headline per side, on the merits only"),
]


def _tokens(row: dict) -> dict:
    t = {"input": 0, "cached": 0, "output": 0}
    for u in row["usage"].values():          # app cost only (writer + critic), grader excluded
        t["input"] += u["input_tokens"]
        t["cached"] += u["cache_read_tokens"]
        t["output"] += u["output_tokens"]
    return t


def _avg(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(mean(xs), 3) if xs else None


def _pct(x):
    return "-" if x is None else f"{x:.0%}"


def aggregate(run: dict) -> dict:
    rows = run["rows"]
    sc = [r["score"] for r in rows]
    return {
        "props": len(rows),
        "verified": sum(r["verified"] for r in rows),
        "fidelity": _avg([s["fidelity"] for s in sc]),
        "contradicted": round(sum(s["contradicted"] or 0 for s in sc), 1),
        "effects_correct": f"{round(sum(s['effects_correct'] or 0 for s in sc), 1):g}/{3 * len(rows)}",
        "top1_in_headline": _avg([s.get("top1_in_headline") for s in sc]),
        "coverage_top3": _avg([s.get("coverage_top3") for s in sc]),
        "coverage": _avg([s["coverage"] for s in sc]),
        "rewrites": _avg([r["rewrites"] for r in rows]),
        "turing_min_avg": _avg([min(r["turing"].values()) for r in rows]),
        "reading_grade": _avg([(r.get("checks") or {}).get("reading_grade") for r in rows]),
        "input_per_prop": round(mean(_tokens(r)["input"] for r in rows)),
        "cached_per_prop": round(mean(_tokens(r)["cached"] for r in rows)),
        "output_per_prop": round(mean(_tokens(r)["output"] for r in rows)),
        "seconds_per_prop": round(mean(r["seconds"] for r in rows), 1),
    }


def per_prop_table(run: dict) -> str:
    lines = ["| Prop | Verified | Turing (Yes/No) | Rewrites | Claims supported | Contradicted | Yes/No/cost correct | "
             "#1 point = headline | Top-3 covered | All covered | Reading grade | Input tok | Cached | Output tok |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in run["rows"]:
        s, t = r["score"], _tokens(r)
        lines.append(
            f"| {r['prop']} | {'yes' if r['verified'] else 'no'} | {r['turing']['yes']}/{r['turing']['no']} | "
            f"{r['rewrites']} | {_pct(s['fidelity'])} | {s['contradicted']} | {s['effects_correct']}/3 | "
            f"{_pct(s.get('top1_in_headline'))} | {_pct(s.get('coverage_top3'))} | {_pct(s['coverage'])} | "
            f"{(r.get('checks') or {}).get('reading_grade', '-')} | {t['input']:,} | {t['cached']:,} | {t['output']:,} |")
    return "\n".join(lines)


def main():
    out = ["# California look-back: accuracy and cost (Nov 3, 2026 propositions)", "",
           "Each card: Analyst (gpt-6-astra) writes -> Critic (gpt-6-luna) reviews -> up to 2 rewrites. A separate "
           "Grader (gpt-6-astra) scores the final card against the official voter guide, with the Legislative "
           "Analyst as the answer key. Current cards are graded twice and averaged to smooth grader noise.", ""]
    current = EVAL_DIR / "gpt-6-astra.json"
    if current.exists():
        run = json.loads(current.read_text(encoding="utf-8"))
        a = aggregate(run)
        out += ["## Current cards (v3)", "", per_prop_table(run), "",
                "## Targets", "", "| Metric | Target | Current |", "|---|---|---|",
                f"| Claims supported by sources | >= 99%, 0 contradicted | {_pct(a['fidelity'])}, {a['contradicted']} contradicted |",
                f"| Yes / No / cost correct | 100% | {a['effects_correct']} |",
                f"| Each side's #1 point is its headline | 100% | {_pct(a['top1_in_headline'])} |",
                f"| Each side's top-3 points covered (on the merits) | >= 95% | {_pct(a['coverage_top3'])} |",
                f"| All points on the merits covered | 85-90% | {_pct(a['coverage'])} |",
                f"| Steelmen verified by the Critic | >= 85-90% | {a['verified']}/{a['props']} |",
                f"| Reading level of what voters see first | about grade 8-9 | {a['reading_grade']} |", ""]
    versions = [(label, json.loads((EVAL_DIR / f).read_text(encoding="utf-8")))
                for f, label in VERSIONS if (EVAL_DIR / f).exists()]
    if len(versions) > 1:
        aggs = [(label, aggregate(run)) for label, run in versions]
        out += ["## How the card design evolved (same 6 props, same models)", "",
                "| Metric | " + " | ".join(l for l, _ in aggs) + " |", "|---|" + "---|" * len(aggs)]
        for k, name in [("verified", "Steelmen verified (of 6)"), ("fidelity", "Claims supported"),
                        ("contradicted", "Claims contradicted"), ("effects_correct", "Yes/No/cost correct"),
                        ("top1_in_headline", "#1 point is the headline"), ("coverage_top3", "Top-3 points covered"),
                        ("coverage", "All points covered"), ("rewrites", "Rewrites per prop"),
                        ("turing_min_avg", "Lowest Turing score (avg)"), ("reading_grade", "Reading grade"),
                        ("input_per_prop", "Input tokens / prop"), ("cached_per_prop", "Cached tokens / prop"),
                        ("output_per_prop", "Output tokens / prop"), ("seconds_per_prop", "Seconds / prop")]:
            out.append(f"| {name} | " + " | ".join(str(a[k]) if a[k] is not None else "-" for _, a in aggs) + " |")
        out += ["", "Note: v1 and v2 counted all official points; v3 counts only points about the change, "
                "setting aside arguments about motives or funders by design."]
    luna = EVAL_DIR / "gpt-6-luna.json"
    base_file = EVAL_DIR / "baseline_gpt-6-astra.json"
    if luna.exists() and base_file.exists():
        lrun = json.loads(luna.read_text(encoding="utf-8"))
        props = [r["prop"] for r in lrun["rows"]]
        base = json.loads(base_file.read_text(encoding="utf-8"))
        bsub = {**base, "rows": [r for r in base["rows"] if r["prop"] in props]}
        la, ba = aggregate(lrun), aggregate(bsub)
        out += ["", f"## Writer model comparison (v1 cards, props {', '.join(props)})", "",
                "| Writer | Verified | Claims supported | Rewrites | Input/prop | Output/prop |", "|---|---|---|---|---|---|",
                f"| gpt-6-astra | {ba['verified']}/{ba['props']} | {_pct(ba['fidelity'])} | {ba['rewrites']} | "
                f"{ba['input_per_prop']:,} | {ba['output_per_prop']:,} |",
                f"| gpt-6-luna | {la['verified']}/{la['props']} | {_pct(la['fidelity'])} | {la['rewrites']} | "
                f"{la['input_per_prop']:,} | {la['output_per_prop']:,} |"]
    (EVAL_DIR / "summary.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
