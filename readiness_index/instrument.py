"""The assessment instrument: dimensions, the questions inside each, and what a 1, a 3 and a 5 look like.

A rating is only as good as the shared meaning of the scale, so every question carries behavioural anchors. A respondent who rates a 5 is
saying a specific thing happens, and a reviewer can ask for the evidence."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any


class SpecError(ValueError):
    """The input contains something the model cannot use."""


def exact(x: float | Fraction) -> Fraction:
    """A number as an exact fraction; floats go through their shortest decimal form, so 0.15 is exactly fifteen hundredths."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise SpecError(f"expected a number, got {x!r}")
    if x != x or x in (float("inf"), float("-inf")):
        raise SpecError("numbers must be finite")
    return Fraction(repr(x)) if isinstance(x, float) else Fraction(x)


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    anchors: tuple[str, str, str]            # what a 1, a 3 and a 5 look like
    weight: Fraction = Fraction(1)


@dataclass(frozen=True)
class Dimension:
    name: str
    weight: Fraction
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Instrument:
    name: str
    dimensions: tuple[Dimension, ...]
    scale: tuple[int, int] = (1, 5)

    @property
    def dimension_names(self) -> list[str]:
        return [d.name for d in self.dimensions]

    @property
    def item_ids(self) -> list[str]:
        return [i.id for d in self.dimensions for i in d.items]

    def dimension_of(self, item_id: str) -> str:
        for d in self.dimensions:
            if any(i.id == item_id for i in d.items):
                return d.name
        raise KeyError(item_id)

    def to_spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dimensions": {
                d.name: {
                    "weight": float(d.weight),
                    "items": [
                        {"id": i.id, "text": i.text, "anchors": {"1": i.anchors[0], "3": i.anchors[1], "5": i.anchors[2]}, "weight": float(i.weight)}
                        for i in d.items
                    ],
                }
                for d in self.dimensions
            },
        }


def parse_instrument(spec: Any) -> Instrument:
    if not isinstance(spec, dict):
        raise SpecError("instrument: must be an object")
    extra = sorted(set(spec) - {"name", "dimensions"})
    if extra:
        raise SpecError(f"instrument: unknown keys {extra}")
    dims_raw = spec.get("dimensions")
    if not isinstance(dims_raw, dict) or not dims_raw:
        raise SpecError("instrument.dimensions: need at least one dimension")
    dims, seen = [], set()
    for dname, d in sorted(dims_raw.items()):
        if not isinstance(d, dict) or set(d) - {"weight", "items"}:
            raise SpecError(f"instrument.dimensions.{dname}: expected 'weight' and 'items'")
        w = exact(d.get("weight"))  # type: ignore[arg-type]
        if w <= 0:
            raise SpecError(f"instrument.dimensions.{dname}.weight: must be positive")
        items_raw = d.get("items")
        if not isinstance(items_raw, list) or not items_raw:
            raise SpecError(f"instrument.dimensions.{dname}.items: need at least one item")
        items = []
        for k, it in enumerate(items_raw):
            where = f"instrument.dimensions.{dname}.items[{k}]"
            if not isinstance(it, dict) or set(it) - {"id", "text", "anchors", "weight"}:
                raise SpecError(f"{where}: expected id, text, anchors and optionally weight")
            iid, text, anchors = it.get("id"), it.get("text"), it.get("anchors")
            if not isinstance(iid, str) or not iid or iid in seen:
                raise SpecError(f"{where}.id: must be a unique non-empty string")
            if not isinstance(text, str) or not text:
                raise SpecError(f"{where}.text: must be a non-empty string")
            if not isinstance(anchors, dict) or set(anchors) != {"1", "3", "5"} or not all(isinstance(v, str) and v for v in anchors.values()):
                raise SpecError(f"{where}.anchors: give text for exactly '1', '3' and '5'")
            iw = exact(it.get("weight", 1))
            if iw <= 0:
                raise SpecError(f"{where}.weight: must be positive")
            seen.add(iid)
            items.append(Item(iid, text, (anchors["1"], anchors["3"], anchors["5"]), iw))
        dims.append(Dimension(dname, w, tuple(items)))
    name = spec.get("name", "custom")
    if not isinstance(name, str) or not name:
        raise SpecError("instrument.name: must be a non-empty string")
    total = sum((d.weight for d in dims), Fraction(0))
    dims = [Dimension(d.name, d.weight / total, d.items) for d in dims]
    return Instrument(name, tuple(dims))


def _items(prefix: str, rows: list[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    return [
        {"id": f"{prefix}.{n}", "text": text, "anchors": {"1": low, "3": mid, "5": high}}
        for n, (text, low, mid, high) in enumerate(rows, start=1)
    ]


DEFAULT_SPEC: dict[str, Any] = {
    "name": "AI readiness, six dimensions",
    "dimensions": {
        "strategy": {"weight": 0.15, "items": _items("strategy", [
            ("Priorities. How clearly has the organization decided where AI should and should not be used?",
             "No stated position; AI appears only in individual initiatives.",
             "A list of candidate use cases exists but is not tied to targets or budget.",
             "A funded portfolio tied to named business outcomes, reviewed by executives at least quarterly."),
            ("Ownership. Who is accountable for AI results at executive level?",
             "Nobody; it sits wherever someone volunteered.",
             "An executive sponsor exists but without authority over budget or priorities.",
             "A named executive owns outcomes, budget and trade-offs, and reports them to the board or equivalent."),
            ("Value tracking. How does the organization know whether AI work paid off?",
             "No tracking; value is asserted.",
             "Benefits are estimated at approval and rarely revisited.",
             "Realized value is measured against the approved case and drives the next funding decision."),
            ("Build, buy or partner. How are sourcing decisions made?",
             "Whoever asks first decides; no comparison is made.",
             "Options are compared informally, usually on price.",
             "A standing method compares options on cost, risk, exit terms and capability, and decisions are recorded."),
        ])},
        "data": {"weight": 0.20, "items": _items("data", [
            ("Access. Can teams get the data an AI use case needs?",
             "Data is locked in systems and requests take months.",
             "Access is possible through projects, with manual extraction.",
             "Governed self-service access, with turnaround measured in days."),
            ("Quality. Is data quality measured and managed?",
             "Quality is unknown until a project fails on it.",
             "Quality is checked per project and fixed by hand.",
             "Quality is measured continuously with owners, thresholds and automated alerts."),
            ("Lineage and ownership. Does each important dataset have an owner and a known origin?",
             "Owners and origins are mostly unknown.",
             "Owners exist for core datasets; lineage is partial.",
             "Every critical dataset has a named owner, documented lineage and a change process."),
            ("Rights and privacy. Is the legal basis for using data in AI established?",
             "Not examined before use.",
             "Reviewed case by case, with inconsistent outcomes.",
             "Permitted uses are recorded per dataset and enforced in tooling; exceptions are reviewed."),
        ])},
        "technology": {"weight": 0.15, "items": _items("technology", [
            ("Model and compute access. Can teams reach the models and compute they need?",
             "No sanctioned access; teams use personal accounts.",
             "Approved access for a few teams; procurement is slow.",
             "Sanctioned access for all approved use cases, with usage and cost visible per team."),
            ("Release path. How does an AI feature reach production?",
             "By hand, from a laptop.",
             "A repeatable process exists but depends on specific people.",
             "Automated build, test and deploy with rollback, the same as other critical software."),
            ("Integration. How well do AI components connect to systems of record?",
             "Copy and paste between tools.",
             "Point integrations built per project.",
             "Standard interfaces and shared services; new use cases reuse them."),
            ("Security. Are AI-specific risks covered in the security architecture?",
             "Not considered.",
             "Covered by general controls; AI-specific threats are known but not tested.",
             "AI threats (prompt injection, data leakage, supply chain) are modelled, tested and monitored."),
        ])},
        "talent": {"weight": 0.15, "items": _items("talent", [
            ("Leadership literacy. Do leaders understand what AI can and cannot do?",
             "Understanding comes from marketing material.",
             "Some leaders have been briefed or trained.",
             "Leaders can challenge a proposal on evidence, cost and failure modes."),
            ("Specialist capacity. Is there enough skilled capacity to deliver?",
             "None, or a single person.",
             "A small team that is fully booked.",
             "Capacity planned against the portfolio, with named backups for critical roles."),
            ("Hiring and retention. Can the organization attract and keep the skills it needs?",
             "Open roles stay open; key people leave.",
             "Hiring works for some roles; retention is a concern.",
             "A defined career path, competitive terms and a record of keeping key people."),
            ("Adoption. Are the people who use AI supported to change how they work?",
             "Tools are released with no support.",
             "Training is offered at launch.",
             "Role-specific training, feedback loops and adoption measured after launch."),
        ])},
        "governance": {"weight": 0.20, "items": _items("governance", [
            ("Policy. Is there a clear, current policy on acceptable AI use?",
             "None.",
             "A policy exists but is old or not widely known.",
             "A current policy, known by staff, with a defined exceptions process."),
            ("Risk review. Are use cases classified by risk and reviewed accordingly?",
             "No review.",
             "High-profile use cases are reviewed when someone remembers.",
             "Every use case is risk-classified; review depth follows the class; decisions are recorded."),
            ("Accountability. Who answers when an AI system causes harm, and is there an incident process?",
             "Nobody is clearly responsible.",
             "Responsibility is assigned informally.",
             "Named owners, a tested incident process, and post-incident reviews that change practice."),
            ("Vendor and model oversight. Are third-party models and vendors assessed and monitored?",
             "Vendors are used as they come.",
             "A questionnaire at purchase, rarely revisited.",
             "Assessment at purchase and on change, with contractual rights to audit, notice and exit."),
        ])},
        "operations": {"weight": 0.15, "items": _items("operations", [
            ("Monitoring. Are AI systems watched in production?",
             "No monitoring; problems are reported by users.",
             "Basic uptime and error monitoring.",
             "Quality, drift, cost and safety are monitored with alerts and owners."),
            ("Evaluation. Are systems tested against agreed criteria before release?",
             "Demonstrations only.",
             "Ad hoc test sets built per project.",
             "Maintained evaluation suites gate every release and are rerun on change."),
            ("Cost control. Is AI spend visible and managed?",
             "Unknown until the invoice.",
             "Total spend is known; attribution to use cases is rough.",
             "Cost per use case and per outcome is tracked, with budgets and alerts."),
            ("Retirement and repair. What happens to systems that stop working well?",
             "They run until someone complains.",
             "Fixed when noticed.",
             "Defined thresholds trigger repair or retirement, and the decision is recorded."),
        ])},
    },
}


def default_instrument() -> Instrument:
    return parse_instrument(DEFAULT_SPEC)
