"""Measure readiness.index against independent implementations and against simulated truth, and print the counts quoted in the README.

Run from the repository root:  python examples/evaluate.py
Every number is computed here from fixed seeds, so the output is the same on every machine."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from readiness_index import (  # noqa: E402
    DEFAULT_SPEC,
    SpecError,
    best_order,
    bootstrap,
    compare,
    default_instrument,
    greedy_order,
    krippendorff_alpha,
    make_task,
    score_responses,
)
from readiness_index.assessment import parse_responses  # noqa: E402
from readiness_index.planner import cost_of  # noqa: E402
from readiness_index.synthetic import assessment  # noqa: E402
from tests import oracles  # noqa: E402  (independent reference implementations)

INST = default_instrument()
FLAT = dict.fromkeys(INST.dimension_names, 3.0)


def panel(profile, n, seed, **kw):
    return parse_responses(INST, assessment(profile, n=n, seed=seed, **kw)["respondents"]).respondents


def agreement() -> None:
    worst, designs = 0.0, 0
    for seed in range(300):
        rng = random.Random(seed)
        coders, units = rng.randint(2, 7), rng.randint(2, 20)
        rows = [{f"u{i}": (rng.randint(1, 5) if rng.random() > 0.25 else None) for i in range(units)} for _ in range(coders)]
        items = [f"u{i}" for i in range(units)]
        got, want = krippendorff_alpha(rows, items), oracles.alpha_coincidence(rows, items)
        if want is None:
            assert got is None
            continue
        designs += 1
        worst = max(worst, abs(got - want))
    print(f"Krippendorff alpha vs the coincidence-matrix method: {designs} random rater designs, largest gap {worst:.1e}")


def scoring() -> None:
    bad, n = 0, 0
    for seed in range(250):
        rng = random.Random(seed)
        profile = {d: rng.uniform(1.5, 4.5) for d in INST.dimension_names}
        a = assessment(profile, n=rng.randint(1, 9), seed=seed, blank=0.3)
        for r in a["respondents"].values():
            if rng.random() < 0.3:
                r["weight"] = rng.choice([0.5, 2, 3])
        try:
            got = score_responses(INST, parse_responses(INST, a["respondents"]).respondents)
        except SpecError:
            continue
        dims, overall = oracles.score_by_hand(DEFAULT_SPEC, list(a["respondents"].values()))
        n += 1
        bad += not (got.overall == overall and got.dimensions == dims)
    print(f"exact scores vs a from-the-definition recomputation (rational arithmetic): {n} panels with gaps and weights, differences {bad}")


def sequencing() -> None:
    bad, suboptimal, savings, n = 0, 0, [], 0
    for seed in range(400):
        rng = random.Random(seed)
        k = rng.randint(2, 7)
        names = [f"t{i}" for i in range(k)]
        raw = [(nm, rng.choice([0.5, 1, 2, 3.5, 7, 10]), rng.choice([0.5, 1, 2, 3, 5]), {x for x in names[:i] if rng.random() < 0.35}) for i, nm in enumerate(names)]
        tasks = [make_task(a, b, c, d) for a, b, c, d in raw]
        want, _ = oracles.brute_force_cost([(a, b, c, tuple(d)) for a, b, c, d in raw])
        best, greedy = cost_of(best_order(tasks), tasks), cost_of(greedy_order(tasks), tasks)
        n += 1
        bad += best != want
        if greedy > best:
            suboptimal += 1
            savings.append(float(1 - best / greedy))
    mean = sum(savings) / len(savings) if savings else 0.0
    print(f"roadmap order vs brute force over every permutation: {n} random plans, differences {bad}; "
          f"the benefit-per-effort rule was beaten in {suboptimal}, by {mean:.1%} of its cost on average")


def interval_coverage() -> None:
    truth_panel = panel({"strategy": 3.4, "data": 2.6, "technology": 3.1, "talent": 3.0, "governance": 2.2, "operations": 2.8}, 3000, 99)
    truth = float(score_responses(INST, truth_panel).overall)
    profile = {"strategy": 3.4, "data": 2.6, "technology": 3.1, "talent": 3.0, "governance": 2.2, "operations": 2.8}
    out = {}
    for n in (8, 24):
        hits, runs = 0, 120
        for k in range(runs):
            lo, hi = bootstrap(INST, panel(profile, n, 1000 + k), resamples=200, seed=k).overall_interval()
            hits += lo <= truth <= hi
        out[n] = hits / runs
    print(f"95% bootstrap interval, coverage of the true score over 120 simulated panels: {out[8]:.0%} with 8 respondents, {out[24]:.0%} with 24")


def change_detection() -> None:
    runs = 100
    false_alarm = power = 0
    for k in range(runs):
        a, b = panel(FLAT, 9, 2000 + k), panel(FLAT, 9, 4000 + k)
        false_alarm += compare(INST, a, b, resamples=200, seed=k)[0].reliable
        up = panel(dict.fromkeys(INST.dimension_names, 3.4), 9, 6000 + k)      # a true gain of 10 points
        power += compare(INST, a, up, resamples=200, seed=k)[0].reliable
    print(f"reliable-change flag over {runs} simulated before/after pairs of 9 respondents: "
          f"{false_alarm / runs:.0%} flagged when nothing changed, {power / runs:.0%} flagged for a true 10-point gain")


def speed() -> None:
    p = panel(FLAT, 12, 1)
    start = time.perf_counter()
    bootstrap(INST, p, resamples=2000, seed=1)
    print(f"2000 bootstrap resamples of a 12-respondent, 24-item assessment: {time.perf_counter() - start:.1f} s")


if __name__ == "__main__":
    agreement()
    scoring()
    sequencing()
    interval_coverage()
    change_detection()
    speed()
