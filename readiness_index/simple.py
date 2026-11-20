"""The 0.1 interface: score ratings per dimension, find the gaps, order them by weighted impact. Behaviour unchanged."""

from __future__ import annotations

from typing import Any

DIMENSIONS: dict[str, float] = {
    "strategy": 0.15,
    "data": 0.20,
    "technology": 0.15,
    "talent": 0.15,
    "governance": 0.20,
    "operations": 0.15,
}

LEVELS: list[tuple[int, str]] = [(80, "Leading"), (60, "Scaling"), (40, "Developing"), (0, "Emerging")]


def level(score: float) -> str:
    for floor, name in LEVELS:
        if score >= floor:
            return name
    return LEVELS[-1][1]


def score(answers: dict[str, list[float]], weights: dict[str, float] | None = None) -> dict[str, Any]:
    """answers maps each dimension to a list of ratings from 1 to 5.

    Returns per-dimension scores out of 100, a weighted overall score, and the level.
    """
    weights = weights or DIMENSIONS
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("weights must sum to 1")
    missing = [d for d in weights if not answers.get(d)]
    if missing:
        raise ValueError(f"no ratings for: {', '.join(sorted(missing))}")
    dims: dict[str, float] = {}
    for name in weights:
        ratings = answers[name]
        if any(not 1 <= r <= 5 for r in ratings):
            raise ValueError(f"{name}: ratings must be 1 to 5")
        dims[name] = round((sum(ratings) / len(ratings) - 1) / 4 * 100, 1)
    overall = round(sum(dims[d] * weights[d] for d in weights), 1)
    return {"overall": overall, "level": level(overall), "dimensions": dims}


def gaps(result: dict[str, Any], target: float = 60.0) -> list[tuple[str, float]]:
    """Dimensions below target, weakest first, with the points needed to reach it."""
    below = [(d, v) for d, v in result["dimensions"].items() if v < target]
    return [(d, round(target - v, 1)) for d, v in sorted(below, key=lambda item: (item[1], item[0]))]


def roadmap(result: dict[str, Any], target: float = 60.0, weights: dict[str, float] | None = None) -> list[tuple[str, float, float]]:
    """Order gap work by impact: points to close times the dimension's weight."""
    weights = weights or DIMENSIONS
    items = [(d, need, round(need * weights[d], 2)) for d, need in gaps(result, target)]
    return sorted(items, key=lambda item: (-item[2], item[0]))
