"""readiness.index: score an organization's AI readiness across weighted dimensions and plan the gaps."""

from __future__ import annotations

__version__ = "0.1.0"

DIMENSIONS = {
    "strategy": 0.15,
    "data": 0.20,
    "technology": 0.15,
    "talent": 0.15,
    "governance": 0.20,
    "operations": 0.15,
}

LEVELS = [(80, "Leading"), (60, "Scaling"), (40, "Developing"), (0, "Emerging")]


def level(score: float) -> str:
    for floor, name in LEVELS:
        if score >= floor:
            return name
    return LEVELS[-1][1]


def score(answers: dict, weights: dict | None = None) -> dict:
    """answers maps each dimension to a list of ratings from 1 to 5.

    Returns per-dimension scores out of 100, a weighted overall score, and the level.
    """
    weights = weights or DIMENSIONS
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("weights must sum to 1")
    missing = [d for d in weights if not answers.get(d)]
    if missing:
        raise ValueError(f"no ratings for: {', '.join(sorted(missing))}")
    dims = {}
    for name in weights:
        ratings = answers[name]
        if any(not 1 <= r <= 5 for r in ratings):
            raise ValueError(f"{name}: ratings must be 1 to 5")
        dims[name] = round((sum(ratings) / len(ratings) - 1) / 4 * 100, 1)
    overall = round(sum(dims[d] * weights[d] for d in weights), 1)
    return {"overall": overall, "level": level(overall), "dimensions": dims}


def gaps(result: dict, target: float = 60.0) -> list:
    """Dimensions below target, weakest first, with the points needed to reach it."""
    below = [(d, v) for d, v in result["dimensions"].items() if v < target]
    return [(d, round(target - v, 1)) for d, v in sorted(below, key=lambda item: (item[1], item[0]))]


def roadmap(result: dict, target: float = 60.0, weights: dict | None = None) -> list:
    """Order gap work by impact: points to close times the dimension's weight."""
    weights = weights or DIMENSIONS
    items = [(d, need, round(need * weights[d], 2)) for d, need in gaps(result, target)]
    return sorted(items, key=lambda item: (-item[2], item[0]))
