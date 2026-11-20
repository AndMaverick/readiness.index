"""Responses, exact scoring, levels with a bottleneck rule, coverage, evidence audit and perception gaps.

Scores are computed in rational arithmetic so a result sitting exactly on a level boundary lands on the right side of it."""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from .instrument import Instrument, SpecError, exact

LEVEL_FLOORS: tuple[tuple[int, str], ...] = ((0, "Emerging"), (40, "Developing"), (60, "Scaling"), (80, "Leading"))
LEVEL_NAMES = [n for _, n in LEVEL_FLOORS]


def level_index(score: Fraction | float) -> int:
    idx = 0
    for i, (floor, _) in enumerate(LEVEL_FLOORS):
        if score >= floor:
            idx = i
    return idx


def level_name(score: Fraction | float) -> str:
    return LEVEL_NAMES[level_index(score)]


def level_floor(name: str) -> int:
    for floor, n in LEVEL_FLOORS:
        if n == name:
            return floor
    raise SpecError(f"unknown level {name!r}; use one of {LEVEL_NAMES}")


@dataclass(frozen=True)
class Respondent:
    name: str
    role: str
    weight: Fraction
    ratings: dict[str, int | None]


@dataclass(frozen=True)
class Responses:
    respondents: tuple[Respondent, ...]
    evidence: dict[str, str] = field(default_factory=dict)


def parse_responses(instrument: Instrument, raw: Any, evidence: Any = None) -> Responses:
    if not isinstance(raw, dict) or not raw:
        raise SpecError("respondents: need at least one respondent")
    ids = set(instrument.item_ids)
    lo, hi = instrument.scale
    out = []
    for name, r in sorted(raw.items()):
        where = f"respondents.{name}"
        if not isinstance(r, dict) or set(r) - {"role", "weight", "ratings"}:
            raise SpecError(f"{where}: expected role, ratings and optionally weight")
        role = r.get("role", "unspecified")
        if not isinstance(role, str) or not role:
            raise SpecError(f"{where}.role: must be a non-empty string")
        w = exact(r.get("weight", 1))
        if w <= 0:
            raise SpecError(f"{where}.weight: must be positive")
        ratings_raw = r.get("ratings")
        if not isinstance(ratings_raw, dict):
            raise SpecError(f"{where}.ratings: must map item ids to ratings")
        unknown = sorted(set(ratings_raw) - ids)
        if unknown:
            raise SpecError(f"{where}.ratings: unknown items {unknown}")
        ratings: dict[str, int | None] = {}
        for iid in instrument.item_ids:
            v = ratings_raw.get(iid)
            if v is None:
                ratings[iid] = None
                continue
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                raise SpecError(f"{where}.ratings.{iid}: a whole number from {lo} to {hi}, or null for 'do not know'")
            ratings[iid] = v
        out.append(Respondent(name, role, w, ratings))
    ev: dict[str, str] = {}
    if evidence is not None:
        if not isinstance(evidence, dict):
            raise SpecError("evidence: must map item ids to text")
        for k, v in evidence.items():
            if k not in ids:
                raise SpecError(f"evidence: unknown item {k!r}")
            if not isinstance(v, str) or not v.strip():
                raise SpecError(f"evidence.{k}: must be non-empty text")
            ev[k] = v
    return Responses(tuple(out), ev)


@dataclass(frozen=True)
class Scores:
    items: dict[str, Fraction | None]          # mean rating per item (1 to 5), None if nobody rated it
    dimensions: dict[str, Fraction]            # 0 to 100
    overall: Fraction
    level_by_score: str
    level: str                                 # after the bottleneck rule
    limiting_dimension: str | None             # set when the bottleneck lowered the level


def score_responses(instrument: Instrument, respondents: tuple[Respondent, ...]) -> Scores:
    lo, hi = instrument.scale
    items: dict[str, Fraction | None] = {}
    for iid in instrument.item_ids:
        num, den = Fraction(0), Fraction(0)
        for r in respondents:
            v = r.ratings.get(iid)
            if v is not None:
                num += r.weight * v
                den += r.weight
        items[iid] = num / den if den else None
    dims: dict[str, Fraction] = {}
    for d in instrument.dimensions:
        num, den = Fraction(0), Fraction(0)
        for it in d.items:
            m = items[it.id]
            if m is not None:
                num += it.weight * m
                den += it.weight
        if not den:
            raise SpecError(f"nobody rated any item in {d.name!r}; the dimension cannot be scored")
        dims[d.name] = (num / den - lo) / (hi - lo) * 100
    overall = sum((d.weight * dims[d.name] for d in instrument.dimensions), Fraction(0))
    by_score = level_index(overall)
    weakest = min(dims, key=lambda k: (dims[k], k))
    cap = level_index(dims[weakest]) + 1
    final = min(by_score, cap)
    limiting = weakest if final < by_score else None
    return Scores(items, dims, overall, LEVEL_NAMES[by_score], LEVEL_NAMES[final], limiting)


def coverage(instrument: Instrument, respondents: tuple[Respondent, ...]) -> float:
    cells = len(instrument.item_ids) * len(respondents)
    answered = sum(1 for r in respondents for v in r.ratings.values() if v is not None)
    return answered / cells


def unsupported_high(instrument: Instrument, responses: Responses, scores: Scores, threshold: float = 4.0) -> list[str]:
    """Items rated at or above ``threshold`` on average with no evidence on file."""
    return [
        iid for iid in instrument.item_ids
        if (m := scores.items[iid]) is not None and m >= Fraction(repr(threshold)) and iid not in responses.evidence
    ]


def role_means(instrument: Instrument, respondents: tuple[Respondent, ...]) -> dict[str, dict[str, Fraction]]:
    """Dimension scores computed separately for each role. Roles whose people left a dimension entirely unrated are skipped for it."""
    out: dict[str, dict[str, Fraction]] = {}
    for role in sorted({r.role for r in respondents}):
        group = tuple(r for r in respondents if r.role == role)
        try:
            out[role] = score_responses(instrument, group).dimensions
        except SpecError:
            continue
    return out


def perception_gaps(instrument: Instrument, respondents: tuple[Respondent, ...]) -> list[dict[str, Any]]:
    """For each dimension, the spread between the most and least optimistic role, widest first."""
    by_role = role_means(instrument, respondents)
    if len(by_role) < 2:
        return []
    rows = []
    for d in instrument.dimension_names:
        vals = {role: dims[d] for role, dims in by_role.items() if d in dims}
        if len(vals) < 2:
            continue
        hi = max(vals, key=lambda k: (vals[k], k))
        lo = min(vals, key=lambda k: (vals[k], k))
        rows.append({"dimension": d, "gap": float(vals[hi] - vals[lo]), "highest_role": hi, "lowest_role": lo})
    return sorted(rows, key=lambda r: (-r["gap"], r["dimension"]))


def _rated(respondents: tuple[Respondent, ...], item_id: str) -> list[int]:
    return [v for r in respondents if (v := r.ratings.get(item_id)) is not None]


def disagreement(instrument: Instrument, respondents: tuple[Respondent, ...]) -> dict[str, float | None]:
    """Mean standard deviation of the ratings people gave the same item, per dimension, in rating points. None with fewer than two raters."""
    out: dict[str, float | None] = {}
    for d in instrument.dimensions:
        sds = []
        for it in d.items:
            vals = _rated(respondents, it.id)
            if len(vals) >= 2:
                m = sum(vals) / len(vals)
                sds.append((sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5)
        out[d.name] = sum(sds) / len(sds) if sds else None
    return out


def contested_items(instrument: Instrument, respondents: tuple[Respondent, ...], span: int = 3) -> list[dict[str, Any]]:
    """Items where the highest and lowest rating differ by ``span`` points or more, widest first. These are the questions to discuss, because
    a panel average hides that some people see a working practice and others see none."""
    rows = []
    for d in instrument.dimensions:
        for it in d.items:
            vals = _rated(respondents, it.id)
            if len(vals) >= 2 and max(vals) - min(vals) >= span:
                rows.append({"item": it.id, "dimension": d.name, "low": min(vals), "high": max(vals), "range": max(vals) - min(vals)})
    return sorted(rows, key=lambda r: (-r["range"], r["item"]))
