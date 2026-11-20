"""Assessment files: strict loading, a fingerprint that pins the result, the full analysis, plan and gates."""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any

from ._version import __version__
from .assessment import (
    LEVEL_NAMES,
    contested_items,
    coverage,
    disagreement,
    level_floor,
    level_index,
    parse_responses,
    perception_gaps,
    score_responses,
    unsupported_high,
)
from .instrument import DEFAULT_SPEC, Instrument, SpecError, exact, parse_instrument
from .planner import make_task
from .planner import plan as make_plan
from .reliability import agreement_label, bootstrap, krippendorff_alpha
from .reliability import compare as compare_waves

METHOD = "exact-scoring+bootstrap-1"
TOP_KEYS = {"name", "instrument", "respondents", "evidence", "targets", "effort_per_point", "prerequisites", "simulation", "gates"}
GATE_KEYS = {
    "min_overall", "min_level", "min_dimension", "min_agreement", "max_perception_gap", "min_coverage", "max_unsupported_high",
    "min_respondents", "target_level", "min_prob_level", "max_contested_items",
}


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise SpecError(f"duplicate key {k!r} in the file")
        out[k] = v
    return out


def _reject_constant(name: str) -> Any:
    raise SpecError(f"{name} is not allowed")


def loads(text: str) -> dict[str, Any]:
    """Parse JSON strictly. A repeated key is an error, because the second silently overriding the first is how a number goes wrong."""
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise SpecError(f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError("the file must be a JSON object")
    return data


def fingerprint(data: dict[str, Any]) -> str:
    """SHA-256 over the canonical form of the input plus the library version and method."""
    canon = json.dumps({"input": data, "version": __version__, "method": METHOD}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canon.encode("ascii")).hexdigest()


def _instrument(data: dict[str, Any]) -> Instrument:
    spec = data.get("instrument", "default")
    if spec == "default":
        return parse_instrument(DEFAULT_SPEC)
    return parse_instrument(spec)


def _targets(instrument: Instrument, raw: Any) -> dict[str, Fraction]:
    raw = {"default": 60} if raw is None else raw
    if not isinstance(raw, dict):
        raise SpecError("targets: must be an object")
    unknown = sorted(set(raw) - set(instrument.dimension_names) - {"default"})
    if unknown:
        raise SpecError(f"targets: unknown dimensions {unknown}")

    def one(v: Any, where: str) -> Fraction:
        if isinstance(v, str):
            return Fraction(level_floor(v))
        t = exact(v)
        if not 0 <= t <= 100:
            raise SpecError(f"{where}: a score from 0 to 100 or a level name")
        return t

    default = one(raw.get("default", 60), "targets.default")
    return {d: one(raw[d], f"targets.{d}") if d in raw else default for d in instrument.dimension_names}


def _per_dimension(instrument: Instrument, raw: Any, name: str, default: Fraction) -> dict[str, Fraction]:
    if raw is None:
        return dict.fromkeys(instrument.dimension_names, default)
    if not isinstance(raw, dict):
        raise SpecError(f"{name}: must be an object")
    unknown = sorted(set(raw) - set(instrument.dimension_names) - {"default"})
    if unknown:
        raise SpecError(f"{name}: unknown dimensions {unknown}")
    base = exact(raw.get("default", default))
    out = {}
    for d in instrument.dimension_names:
        v = exact(raw[d]) if d in raw else base
        if v <= 0:
            raise SpecError(f"{name}.{d}: must be positive")
        out[d] = v
    return out


def _prereqs(instrument: Instrument, raw: Any) -> dict[str, set[str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("prerequisites: must be an object")
    names = set(instrument.dimension_names)
    out: dict[str, set[str]] = {}
    for d, needs in raw.items():
        if d not in names:
            raise SpecError(f"prerequisites: unknown dimension {d!r}")
        if not isinstance(needs, list) or not all(isinstance(x, str) for x in needs):
            raise SpecError(f"prerequisites.{d}: a list of dimension names")
        bad = sorted(set(needs) - names)
        if bad:
            raise SpecError(f"prerequisites.{d}: unknown dimensions {bad}")
        out[d] = set(needs)
    return out


def _settings(raw: Any) -> tuple[int, int]:
    if raw is None:
        return 2000, 1
    if not isinstance(raw, dict) or set(raw) - {"resamples", "seed"}:
        raise SpecError("simulation: an object with 'resamples' and 'seed'")
    n, seed = raw.get("resamples", 2000), raw.get("seed", 1)
    if isinstance(n, bool) or not isinstance(n, int) or not 50 <= n <= 200_000:
        raise SpecError("simulation.resamples: an integer from 50 to 200000")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SpecError("simulation.seed: must be an integer")
    return n, seed


def _gates(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("gates: must be an object")
    extra = sorted(set(raw) - GATE_KEYS)
    if extra:
        raise SpecError(f"gates: unknown keys {extra}")
    out: dict[str, Any] = {}
    for k in ("min_overall", "min_dimension", "max_perception_gap"):
        if k in raw:
            out[k] = float(exact(raw[k]))
            if not 0 <= out[k] <= 100:
                raise SpecError(f"gates.{k}: from 0 to 100")
    for k in ("min_coverage", "min_prob_level"):
        if k in raw:
            out[k] = float(exact(raw[k]))
            if not 0 <= out[k] <= 1:
                raise SpecError(f"gates.{k}: from 0 to 1")
    if "min_agreement" in raw:
        out["min_agreement"] = float(exact(raw["min_agreement"]))
    for k in ("min_level", "target_level"):
        if k in raw:
            if raw[k] not in LEVEL_NAMES:
                raise SpecError(f"gates.{k}: one of {LEVEL_NAMES}")
            out[k] = raw[k]
    for k in ("max_unsupported_high", "min_respondents", "max_contested_items"):
        if k in raw:
            if isinstance(raw[k], bool) or not isinstance(raw[k], int) or raw[k] < 0:
                raise SpecError(f"gates.{k}: a non-negative whole number")
            out[k] = raw[k]
    if ("min_prob_level" in out) != ("target_level" in out):
        raise SpecError("gates: min_prob_level and target_level go together")
    return out


def _check_keys(data: dict[str, Any]) -> None:
    extra = sorted(set(data) - TOP_KEYS)
    if extra:
        raise SpecError(f"unknown keys {extra}")


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    """Run the full analysis on an assessment dict and return a JSON-ready result with the gate verdicts."""
    _check_keys(data)
    instrument = _instrument(data)
    responses = parse_responses(instrument, data.get("respondents"), data.get("evidence"))
    targets = _targets(instrument, data.get("targets"))
    effort = _per_dimension(instrument, data.get("effort_per_point"), "effort_per_point", Fraction(1))
    prereq = _prereqs(instrument, data.get("prerequisites"))
    resamples, seed = _settings(data.get("simulation"))
    gates = _gates(data.get("gates"))

    people = responses.respondents
    scores = score_responses(instrument, people)
    boot = bootstrap(instrument, people, resamples=resamples, seed=seed)
    alpha = krippendorff_alpha(people, instrument.item_ids)
    unsupported = unsupported_high(instrument, responses, scores)
    gaps_by_role = perception_gaps(instrument, people)
    spread = disagreement(instrument, people)
    result: dict[str, Any] = {
        "name": data.get("name", "assessment"),
        "version": __version__,
        "method": METHOD,
        "fingerprint": fingerprint(data),
        "instrument": instrument.name,
        "respondents": len(people),
        "roles": sorted({r.role for r in people}),
        "overall": float(scores.overall),
        "overall_interval": list(boot.overall_interval()),
        "level_by_score": scores.level_by_score,
        "level": scores.level,
        "limiting_dimension": scores.limiting_dimension,
        "level_probabilities": boot.level_probabilities(),
        "coverage": coverage(instrument, people),
        "agreement": {"alpha": alpha, "label": agreement_label(alpha)},
        "dimensions": {},
        "perception_gaps": gaps_by_role,
        "contested_items": contested_items(instrument, people),
        "mean_disagreement": _mean([v for v in spread.values() if v is not None]),
        "unsupported_high": unsupported,
        "weakest_items": _weakest(instrument, scores),
        "plan": None,
    }
    for d in instrument.dimensions:
        lo, hi = boot.dimension_interval(d.name)
        result["dimensions"][d.name] = {
            "score": float(scores.dimensions[d.name]),
            "weight": float(d.weight),
            "interval": [lo, hi],
            "target": float(targets[d.name]),
            "disagreement": spread[d.name],
        }
    result["plan"] = _plan(instrument, scores.dimensions, targets, effort, prereq)
    result["gates"] = _evaluate_gates(gates, result, boot, instrument, scores.dimensions)
    result["passed"] = all(g["passed"] for g in result["gates"])
    return result


def _items(n: int) -> str:
    return "item" if n == 1 else "items"


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _weakest(instrument: Instrument, scores: Any, n: int = 5) -> list[dict[str, Any]]:
    rows = [(iid, m) for iid, m in scores.items.items() if m is not None]
    rows.sort(key=lambda x: (x[1], x[0]))
    return [{"item": iid, "dimension": instrument.dimension_of(iid), "mean_rating": float(m)} for iid, m in rows[:n]]


def _plan(instrument: Instrument, dims: dict[str, Fraction], targets: dict[str, Fraction], effort: dict[str, Fraction], prereq: dict[str, set[str]]) -> dict[str, Any] | None:
    gap = {d: targets[d] - dims[d] for d in instrument.dimension_names if dims[d] < targets[d]}
    if not gap:
        return None
    weight = {d.name: d.weight for d in instrument.dimensions}
    tasks = [make_task(d, weight[d] * g, g * effort[d], {p for p in prereq.get(d, set()) if p in gap}) for d, g in sorted(gap.items())]
    p = make_plan(tasks)
    now = dict(dims)
    steps = []
    for step in p.steps:
        now[step.name] = targets[step.name]
        overall = sum((weight[d] * now[d] for d in now), Fraction(0))
        weakest = min(now.values())
        steps.append({
            "dimension": step.name,
            "points": float(gap[step.name]),
            "start": step.start,
            "finish": step.finish,
            "overall_gain": step.benefit,
            "overall_after": float(overall),
            "level_after": LEVEL_NAMES[min(level_index(overall), level_index(weakest) + 1)],
        })
    return {
        "steps": steps,
        "order": list(p.order),
        "cost": p.cost,
        "greedy_order": list(p.greedy_order),
        "greedy_cost": p.greedy_cost,
        "saving": p.saving,
        "total_effort": p.total_effort,
    }


def _evaluate_gates(gates: dict[str, Any], r: dict[str, Any], boot: Any, instrument: Instrument, dims: dict[str, Fraction]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        out.append({"gate": name, "passed": passed, "detail": detail})

    if "min_overall" in gates:
        add("min_overall", r["overall"] >= gates["min_overall"], f"overall {r['overall']:.1f}, required {gates['min_overall']:g}")
    if "min_level" in gates:
        ok = LEVEL_NAMES.index(r["level"]) >= LEVEL_NAMES.index(gates["min_level"])
        why = f", held down by {r['limiting_dimension']}" if r["limiting_dimension"] else ""
        add("min_level", ok, f"level {r['level']}{why}, required {gates['min_level']}")
    if "min_dimension" in gates:
        low = min(dims, key=lambda k: (dims[k], k))
        add("min_dimension", float(dims[low]) >= gates["min_dimension"], f"weakest dimension {low} at {float(dims[low]):.1f}, required {gates['min_dimension']:g}")
    if "min_agreement" in gates:
        a = r["agreement"]["alpha"]
        add("min_agreement", a is not None and a >= gates["min_agreement"], "agreement undefined" if a is None else f"alpha {a:.3f} ({r['agreement']['label']}), required {gates['min_agreement']:g}")
    if "max_contested_items" in gates:
        n = len(r["contested_items"])
        add("max_contested_items", n <= gates["max_contested_items"], f"{n} {_items(n)} where raters are 3 or more points apart, allowed {gates['max_contested_items']}")
    if "max_perception_gap" in gates:
        worst = r["perception_gaps"][0] if r["perception_gaps"] else None
        if worst is None:
            add("max_perception_gap", True, "fewer than two roles answered")
        else:
            add("max_perception_gap", worst["gap"] <= gates["max_perception_gap"],
                f"widest gap {worst['gap']:.1f} points on {worst['dimension']} ({worst['highest_role']} vs {worst['lowest_role']}), allowed {gates['max_perception_gap']:g}")
    if "min_coverage" in gates:
        add("min_coverage", r["coverage"] >= gates["min_coverage"], f"{r['coverage']:.1%} of answers given, required {gates['min_coverage']:.1%}")
    if "max_unsupported_high" in gates:
        n = len(r["unsupported_high"])
        add("max_unsupported_high", n <= gates["max_unsupported_high"], f"{n} {_items(n)} rated 4 or higher with no evidence on file, allowed {gates['max_unsupported_high']}")
    if "min_respondents" in gates:
        add("min_respondents", r["respondents"] >= gates["min_respondents"], f"{r['respondents']} respondents, required {gates['min_respondents']}")
    if "target_level" in gates:
        p = boot.p_level_at_least(gates["target_level"])
        add("min_prob_level", p >= gates["min_prob_level"], f"{p:.1%} of resampled panels reach {gates['target_level']}, required {gates['min_prob_level']:.1%}")
    return out


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Change between two assessments of the same instrument, with bootstrap intervals and a verdict on each dimension."""
    for d in (before, after):
        _check_keys(d)
    ib, ia = _instrument(before), _instrument(after)
    if ib.to_spec() != ia.to_spec():
        raise SpecError("the two assessments use different instruments")
    rb = parse_responses(ib, before.get("respondents"), before.get("evidence"))
    ra = parse_responses(ia, after.get("respondents"), after.get("evidence"))
    n, seed = _settings(after.get("simulation"))
    rows = compare_waves(ib, rb.respondents, ra.respondents, resamples=n, seed=seed)
    return {
        "version": __version__,
        "before": before.get("name", "before"),
        "after": after.get("name", "after"),
        "fingerprints": [fingerprint(before), fingerprint(after)],
        "changes": [
            {"name": c.name, "before": c.before, "after": c.after, "delta": c.delta, "low": c.low, "high": c.high, "reliable": c.reliable}
            for c in rows
        ],
    }
