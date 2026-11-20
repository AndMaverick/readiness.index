"""Reproducible synthetic assessments, for tests, benchmarks and the examples."""
from __future__ import annotations

import random
from typing import Any

from .instrument import DEFAULT_SPEC, parse_instrument

ROLES = ("executive", "practitioner", "risk")


def respondent_ratings(rng: random.Random, profile: dict[str, float], *, noise: float = 0.7, bias: float = 0.0, blank: float = 0.0) -> dict[str, int | None]:
    """Ratings for every item of the default instrument. ``profile`` maps a dimension to its true level on the 1 to 5 scale."""
    instrument = parse_instrument(DEFAULT_SPEC)
    out: dict[str, int | None] = {}
    for d in instrument.dimensions:
        for it in d.items:
            if blank and rng.random() < blank:
                out[it.id] = None
                continue
            x = profile[d.name] + bias + rng.gauss(0, noise)
            out[it.id] = min(5, max(1, round(x)))
    return out


def assessment(profile: dict[str, float], n: int = 8, seed: int = 0, *, noise: float = 0.7, role_bias: dict[str, float] | None = None, blank: float = 0.0) -> dict[str, Any]:
    """An assessment dict with ``n`` respondents rotating through the roles."""
    rng = random.Random(seed)
    bias = role_bias or {}
    respondents = {}
    for i in range(n):
        role = ROLES[i % len(ROLES)]
        respondents[f"r{i + 1:02d}"] = {"role": role, "ratings": respondent_ratings(rng, profile, noise=noise, bias=bias.get(role, 0.0), blank=blank)}
    return {"name": f"synthetic-{seed}", "respondents": respondents, "simulation": {"resamples": 500, "seed": seed}}
