"""How much to trust the numbers: rater agreement (Krippendorff's alpha), bootstrap intervals, level stability and reliable change."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .assessment import LEVEL_NAMES, Respondent, level_index, score_responses
from .instrument import Instrument, SpecError


def krippendorff_alpha(respondents: tuple[Respondent, ...] | list[dict[str, int | None]], items: list[str] | None = None) -> float | None:
    """Krippendorff's alpha for interval data: 1 means the raters agree perfectly, 0 means they agree no more than chance.

    Units are the items, coders are the respondents, and missing ratings are allowed. Returns None when the ratings do not vary at all
    (alpha is undefined) or when no item was rated by two people. Computed from pairs of ratings within an item and across the pool:
    alpha = 1 - D_o / D_e."""
    rows = [r.ratings if isinstance(r, Respondent) else r for r in respondents]
    ids = items if items is not None else sorted({k for row in rows for k in row})
    units = []
    for iid in ids:
        vals = [row[iid] for row in rows if row.get(iid) is not None]
        if len(vals) >= 2:
            units.append([float(v) for v in vals])  # type: ignore[arg-type]
    if not units:
        return None
    n = sum(len(u) for u in units)
    d_o = 0.0
    for u in units:
        m = len(u)
        s = sum((u[i] - u[j]) ** 2 for i in range(m) for j in range(m) if i != j)
        d_o += s / (m - 1)
    d_o /= n
    pool = [v for u in units for v in u]
    d_e = sum((pool[i] - pool[j]) ** 2 for i in range(n) for j in range(n) if i != j) / (n * (n - 1))
    if d_e == 0:
        return None
    return 1 - d_o / d_e


def agreement_label(alpha: float | None) -> str:
    """Krippendorff's own reading of alpha: 0.80 and up is reliable, 0.667 to 0.80 allows tentative conclusions, below that do not rely on it."""
    if alpha is None:
        return "undefined"
    if alpha >= 0.8:
        return "reliable"
    if alpha >= 0.667:
        return "tentative"
    return "unreliable"


def quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation quantile (the usual 'type 7') of an already sorted list."""
    if not sorted_values:
        raise ValueError("no values")
    if not 0 <= q <= 1:
        raise ValueError("q must be within 0 to 1")
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


@dataclass(frozen=True)
class Bootstrap:
    resamples: int
    seed: int
    overall: list[float]
    dimensions: dict[str, list[float]]
    levels: list[int]

    def interval(self, values: list[float], confidence: float = 0.95) -> tuple[float, float]:
        s = sorted(values)
        tail = (1 - confidence) / 2
        return quantile(s, tail), quantile(s, 1 - tail)

    def overall_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        return self.interval(self.overall, confidence)

    def dimension_interval(self, name: str, confidence: float = 0.95) -> tuple[float, float]:
        return self.interval(self.dimensions[name], confidence)

    def level_probabilities(self) -> dict[str, float]:
        n = len(self.levels)
        return {name: sum(1 for x in self.levels if x == i) / n for i, name in enumerate(LEVEL_NAMES)}

    def p_level_at_least(self, name: str) -> float:
        idx = LEVEL_NAMES.index(name)
        return sum(1 for x in self.levels if x >= idx) / len(self.levels)


def bootstrap(instrument: Instrument, respondents: tuple[Respondent, ...], *, resamples: int = 2000, seed: int = 1) -> Bootstrap:
    """Resample respondents with replacement and rescore. The spread of the rescored results is what a different panel might have said.

    A plain percentile bootstrap is too narrow for small panels because resampling n people from n people understates the variance by a factor
    (n-1)/n. Each rescored value is therefore moved away from the full-panel score by sqrt(n/(n-1)) (the "expanded percentile" correction), and the result is kept within the 0 to 100 scale.
    The level probabilities are tallied from the uncorrected resamples."""
    if resamples < 50:
        raise ValueError("resamples must be at least 50")
    rng = random.Random(seed)
    n = len(respondents)
    overall: list[float] = []
    dims: dict[str, list[float]] = {d: [] for d in instrument.dimension_names}
    levels: list[int] = []
    for _ in range(resamples):
        sample = tuple(respondents[rng.randrange(n)] for _ in range(n))
        try:
            s = score_responses(instrument, sample)
        except SpecError:
            # a resample that happens to contain nobody who rated some dimension: score it from the full panel instead of dropping it
            s = score_responses(instrument, respondents)
        overall.append(float(s.overall))
        for d in dims:
            dims[d].append(float(s.dimensions[d]))
        levels.append(level_index(s.overall))
    point = score_responses(instrument, respondents)
    k = (n / (n - 1)) ** 0.5 if n > 1 else 1.0
    p0 = float(point.overall)
    overall = [min(100.0, max(0.0, p0 + (x - p0) * k)) for x in overall]
    for d in dims:
        c = float(point.dimensions[d])
        dims[d] = [min(100.0, max(0.0, c + (x - c) * k)) for x in dims[d]]
    return Bootstrap(resamples, seed, overall, dims, levels)


@dataclass(frozen=True)
class Change:
    name: str
    before: float
    after: float
    delta: float
    low: float
    high: float

    @property
    def reliable(self) -> bool:
        """The interval for the change excludes zero, so a different panel would very probably also have seen movement in this direction."""
        return self.low > 0 or self.high < 0


def compare(
    instrument: Instrument,
    before: tuple[Respondent, ...],
    after: tuple[Respondent, ...],
    *,
    resamples: int = 2000,
    seed: int = 1,
    confidence: float = 0.95,
) -> list[Change]:
    """Change in the overall score and every dimension between two assessments, each with a bootstrap interval. The two panels are
    resampled independently, because they are different people (or the same people asked again; independent resampling is the more
    cautious choice either way)."""
    b = bootstrap(instrument, before, resamples=resamples, seed=seed)
    a = bootstrap(instrument, after, resamples=resamples, seed=seed + 1)
    s0, s1 = score_responses(instrument, before), score_responses(instrument, after)
    rows = []
    series = [("overall", float(s0.overall), float(s1.overall), b.overall, a.overall)]
    series += [(d, float(s0.dimensions[d]), float(s1.dimensions[d]), b.dimensions[d], a.dimensions[d]) for d in instrument.dimension_names]
    tail = (1 - confidence) / 2
    for name, x0, x1, xs, ys in series:
        diffs = sorted(y - x for x, y in zip(xs, ys, strict=True))
        rows.append(Change(name, x0, x1, x1 - x0, quantile(diffs, tail), quantile(diffs, 1 - tail)))
    return rows
