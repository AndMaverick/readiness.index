"""readiness.index: measure AI readiness the way an auditor would.

The 0.1 functions (``score``, ``gaps``, ``roadmap``, ``level``, ``DIMENSIONS``) are unchanged. The 0.2 additions score real respondent data
against a documented instrument, say how far to trust the result (rater agreement, bootstrap intervals, level probabilities), find where roles
disagree, flag high ratings with no evidence, order the work exactly under prerequisites, and gate the result for a review or a pipeline."""
from ._version import __version__
from .assessment import level_name, score_responses
from .instrument import (
    DEFAULT_SPEC,
    Instrument,
    SpecError,
    default_instrument,
    parse_instrument,
)
from .planner import Plan, Task, best_order, greedy_order, make_task
from .planner import plan as plan_work
from .reliability import bootstrap, compare, krippendorff_alpha
from .scenario import analyze, fingerprint, loads
from .scenario import compare as compare_assessments
from .simple import DIMENSIONS, LEVELS, gaps, level, roadmap, score

__all__ = [
    "DEFAULT_SPEC", "DIMENSIONS", "LEVELS", "Instrument", "Plan", "SpecError", "Task", "__version__", "analyze", "best_order", "bootstrap",
    "compare", "compare_assessments", "default_instrument", "fingerprint", "gaps", "greedy_order", "krippendorff_alpha", "level",
    "level_name", "loads", "make_task", "parse_instrument", "plan_work", "roadmap", "score", "score_responses",
]
