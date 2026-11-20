"""Command line: ``python -m readiness_index assess assessment.json``.

Exit codes: 0 gates pass (or none set), 1 a gate fails, 2 the input is unusable."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from . import report, scenario
from ._version import __version__
from .instrument import DEFAULT_SPEC, SpecError


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            return scenario.loads(fh.read())
    except OSError as exc:
        raise SpecError(f"cannot read {path}: {exc.strerror}") from exc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="readiness-index", description="Score AI readiness from respondent ratings, with intervals, agreement, a roadmap and gates.")
    p.add_argument("--version", action="version", version=f"readiness.index {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("assess", help="full assessment with gates")
    a.add_argument("assessment")
    a.add_argument("--json", action="store_true", help="print the result as JSON")
    a.add_argument("--resamples", type=int, help="override simulation.resamples")
    a.add_argument("--seed", type=int, help="override simulation.seed")
    c = sub.add_parser("compare", help="change between two assessments, with intervals")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--json", action="store_true")
    f = sub.add_parser("fingerprint", help="print the SHA-256 fingerprint of an assessment file")
    f.add_argument("assessment")
    sub.add_parser("instrument", help="print the default instrument as JSON (questions and anchors)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "instrument":
            print(json.dumps(DEFAULT_SPEC, indent=2))
            return 0
        if args.command == "compare":
            result = scenario.compare(_load(args.before), _load(args.after))
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else report.compare_text(result), end="")
            return 0
        data = _load(args.assessment)
        if args.command == "fingerprint":
            scenario.analyze(data)
            print(scenario.fingerprint(data))
            return 0
        if args.resamples is not None or args.seed is not None:
            sim = dict(data.get("simulation") or {})
            if args.resamples is not None:
                sim["resamples"] = args.resamples
            if args.seed is not None:
                sim["seed"] = args.seed
            data = {**data, "simulation": sim}
        result = scenario.analyze(data)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(report.to_json(result) if args.json else report.to_text(result), end="\n" if args.json else "")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
