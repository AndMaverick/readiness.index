"""Plain-text and JSON rendering of an analysis."""
from __future__ import annotations

import json
from typing import Any


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def to_text(r: dict[str, Any]) -> str:
    out = [f"{r['name']}   (readiness.index {r['version']}, fingerprint {r['fingerprint'][:16]})", ""]
    lo, hi = r["overall_interval"]
    out.append(f"Overall {r['overall']:.1f} out of 100 (95% interval {lo:.1f} to {hi:.1f}), from {r['respondents']} respondents")
    cap = f", held down from {r['level_by_score']} by {r['limiting_dimension']}" if r["limiting_dimension"] else ""
    out.append(f"Level: {r['level']}{cap}")
    probs = ", ".join(f"{k} {_pct(v)}" for k, v in r["level_probabilities"].items() if v > 0)
    out.append(f"Resampled panels land on: {probs}")
    if r["respondents"] < 3:
        out.append("Note: fewer than three respondents, so the intervals say little.")
    out.append("")
    out.append("Dimensions")
    out.append(f"  {'dimension':<12} {'score':>6}  {'95% interval':<14} {'target':>6} {'weight':>6}")
    for name, d in sorted(r["dimensions"].items(), key=lambda kv: (kv[1]["score"], kv[0])):
        iv = f"{d['interval'][0]:.1f} to {d['interval'][1]:.1f}"
        out.append(f"  {name:<12} {d['score']:>6.1f}  {iv:<14} {d['target']:>6.0f} {100 * d['weight']:>5.0f}%")
    a = r["agreement"]
    out.append("")
    out.append("Do people agree?")
    md = r["mean_disagreement"]
    if md is not None:
        n_c = len(r["contested_items"])
        out.append(f"  raters differ by {md:.2f} rating points on an average item (standard deviation); {n_c} {'item is' if n_c == 1 else 'items are'} contested (3+ points apart)")
    out.append("  Krippendorff alpha, how well raters track differences between items: " + ("undefined" if a["alpha"] is None else f"{a['alpha']:.3f}, {a['label']}"))
    out.append(f"  answers given: {_pct(r['coverage'])}")
    for c in r["contested_items"][:3]:
        out.append(f"  contested: {c['item']} rated from {c['low']} to {c['high']}")
    for g in r["perception_gaps"][:3]:
        out.append(f"  {g['dimension']}: {g['highest_role']} rates it {g['gap']:.1f} points above {g['lowest_role']}")
    if r["unsupported_high"]:
        out.append("")
        out.append(f"Rated 4 or higher with no evidence on file ({len(r['unsupported_high'])}): " + ", ".join(r["unsupported_high"]))
    out.append("")
    out.append("Weakest items")
    for w in r["weakest_items"]:
        out.append(f"  {w['item']:<14} {w['mean_rating']:.2f} out of 5")
    p = r["plan"]
    if p:
        out.append("")
        out.append("Roadmap (exact best order, respecting prerequisites)")
        for i, s in enumerate(p["steps"], start=1):
            out.append(
                f"  {i}. {s['dimension']:<12} +{s['points']:.1f} points, effort {s['start']:.1f} to {s['finish']:.1f}, "
                f"overall {s['overall_after']:.1f}, level {s['level_after']}"
            )
        if p["greedy_order"] != p["order"]:
            out.append(f"  a benefit-per-effort rule would order it {' > '.join(p['greedy_order'])} and cost {p['saving']:.0%} more value-time")
    if r["gates"]:
        out.append("")
        out.append("Gates")
        for g in r["gates"]:
            out.append(f"  {'PASS' if g['passed'] else 'FAIL'}  {g['gate']}: {g['detail']}")
        out.append("")
        out.append("RESULT: " + ("PASS" if r["passed"] else "FAIL"))
    return "\n".join(out) + "\n"


def compare_text(c: dict[str, Any]) -> str:
    out = [f"{c['before']}  ->  {c['after']}", "", f"  {'':<12} {'before':>7} {'after':>7} {'change':>7}  {'95% interval for the change':<28} verdict"]
    for row in c["changes"]:
        verdict = "reliable " + ("gain" if row["delta"] > 0 else "drop") if row["reliable"] else "within noise"
        iv = f"{row['low']:+.1f} to {row['high']:+.1f}"
        out.append(f"  {row['name']:<12} {row['before']:>7.1f} {row['after']:>7.1f} {row['delta']:>+7.1f}  {iv:<28} {verdict}")
    return "\n".join(out) + "\n"
