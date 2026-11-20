"""Regenerate the three example assessments. The respondents are synthetic: ratings drawn around a stated profile with a fixed seed, so the
files are reproducible and no real organization is described.

Run from the repository root:  python examples/generate_examples.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from readiness_index import analyze  # noqa: E402
from readiness_index.synthetic import assessment  # noqa: E402

PREREQS = {"operations": ["data", "governance"], "technology": ["data"], "strategy": [], "talent": ["strategy"]}
EFFORT = {"default": 1.0, "data": 1.6, "governance": 0.9, "technology": 1.3, "talent": 1.1, "strategy": 0.7, "operations": 1.2}


def with_evidence(a: dict, only_high: bool = True, skip: set[str] = frozenset()) -> dict:
    """Attach an evidence note to every item the panel rated 4 or higher on average, except those in ``skip``."""
    res = analyze({**a, "evidence": {}})  # scores only; gates absent
    del res
    from readiness_index import default_instrument, score_responses
    from readiness_index.assessment import parse_responses
    inst = default_instrument()
    resp = parse_responses(inst, a["respondents"])
    sc = score_responses(inst, resp.respondents)
    ev = {iid: f"Artifact reviewed by the assessor: {iid}" for iid, m in sc.items.items() if m is not None and m >= 4 and iid not in skip}
    return {**a, "evidence": ev}


def main() -> None:
    out = ROOT / "examples"
    acme_profile = {"strategy": 4.2, "data": 3.8, "technology": 4.0, "talent": 3.6, "governance": 3.9, "operations": 3.7}
    after = assessment(acme_profile, n=9, seed=21, noise=0.55)
    after["name"] = "Acme Logistics, Q4 2026 (synthetic example)"
    after.update(
        targets={"default": 60, "governance": 70},
        effort_per_point=EFFORT,
        prerequisites=PREREQS,
        simulation={"resamples": 2000, "seed": 5},
        gates={"min_level": "Scaling", "min_dimension": 50, "max_contested_items": 2, "max_perception_gap": 20, "max_unsupported_high": 0,
               "min_respondents": 6, "target_level": "Scaling", "min_prob_level": 0.9, "min_coverage": 0.95},
    )
    after = with_evidence(after)
    before_profile = {"strategy": 3.5, "data": 2.7, "technology": 3.2, "talent": 3.0, "governance": 2.4, "operations": 2.8}
    before = assessment(before_profile, n=8, seed=22, noise=0.55)
    before["name"] = "Acme Logistics, Q1 2026 (synthetic example)"
    before["simulation"] = {"resamples": 2000, "seed": 5}
    north_profile = {"strategy": 3.6, "data": 2.6, "technology": 3.3, "talent": 2.9, "governance": 1.9, "operations": 2.4}
    north = assessment(north_profile, n=9, seed=23, noise=0.7, role_bias={"executive": 1.3, "practitioner": -0.5, "risk": -0.3}, blank=0.08)
    north["name"] = "Northgate Retail, Q4 2026 (synthetic example)"
    north.update(
        targets={"default": 60},
        effort_per_point=EFFORT,
        prerequisites=PREREQS,
        simulation={"resamples": 2000, "seed": 5},
        gates={"min_level": "Developing", "min_dimension": 40, "max_contested_items": 2, "max_perception_gap": 20, "max_unsupported_high": 0,
               "min_respondents": 6, "target_level": "Developing", "min_prob_level": 0.9, "min_coverage": 0.95},
    )
    north = with_evidence(north, skip={"strategy.1", "strategy.2", "technology.1"})
    for name, data in (("acme_assessment", after), ("acme_before", before), ("northgate_assessment", north)):
        (out / f"{name}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
