"""Sequencing the work: the exact best order for closing gaps when some gaps must be closed before others can start.

One team works through the gaps one after another. Closing gap j takes ``effort`` units and adds ``benefit`` points to the overall score once
it is done. Finishing valuable work early is worth more than finishing it late, so the best order minimizes the sum of benefit times
completion time, which is the same as maximizing the score-weeks accumulated along the way. Without prerequisites the best order is Smith's
rule (highest benefit per unit of effort first). With prerequisites that rule can be wrong, and the problem is hard in general, but a plan
has a handful of gaps, so the exact optimum is found by dynamic programming over subsets."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .instrument import SpecError, exact

MAX_TASKS = 16


@dataclass(frozen=True)
class Task:
    name: str
    benefit: Fraction                  # overall-score points gained when the gap is closed
    effort: Fraction                   # effort units to close it
    needs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Step:
    name: str
    start: float
    finish: float
    benefit: float


@dataclass(frozen=True)
class Plan:
    order: tuple[str, ...]
    steps: tuple[Step, ...]
    cost: float                        # sum of benefit x finish time for the best order (lower is better)
    greedy_order: tuple[str, ...]
    greedy_cost: float                 # the same for "best benefit per effort among what is available"
    total_effort: float

    @property
    def saving(self) -> float:
        """Share of the greedy plan's cost that the exact plan avoids."""
        return 0.0 if self.greedy_cost == 0 else 1 - self.cost / self.greedy_cost


def make_task(name: str, benefit: float | Fraction, effort: float | Fraction, needs: set[str] | frozenset[str] = frozenset()) -> Task:
    b, e = exact(benefit), exact(effort)
    if b < 0 or e <= 0:
        raise SpecError(f"{name}: benefit must not be negative and effort must be positive")
    return Task(name, b, e, frozenset(needs))


def _validate(tasks: list[Task]) -> dict[str, Task]:
    by = {t.name: t for t in tasks}
    if len(by) != len(tasks):
        raise SpecError("duplicate task names")
    if len(tasks) > MAX_TASKS:
        raise SpecError(f"too many gaps to sequence exactly ({len(tasks)}, limit {MAX_TASKS})")
    for t in tasks:
        missing = sorted(t.needs - set(by))
        if missing:
            raise SpecError(f"{t.name} needs unknown tasks {missing}")
        if t.name in t.needs:
            raise SpecError(f"{t.name} needs itself")
    # cycle check by repeated removal of tasks whose needs are met
    done: set[str] = set()
    while len(done) < len(by):
        ready = [n for n, t in by.items() if n not in done and t.needs <= done]
        if not ready:
            raise SpecError("prerequisites form a cycle among: " + ", ".join(sorted(set(by) - done)))
        done.update(ready)
    return by


def cost_of(order: list[str], tasks: list[Task]) -> Fraction:
    by = {t.name: t for t in tasks}
    clock, total = Fraction(0), Fraction(0)
    for n in order:
        clock += by[n].effort
        total += by[n].benefit * clock
    return total


def is_valid_order(order: list[str], tasks: list[Task]) -> bool:
    by = {t.name: t for t in tasks}
    if sorted(order) != sorted(by):
        return False
    seen: set[str] = set()
    for n in order:
        if not by[n].needs <= seen:
            return False
        seen.add(n)
    return True


def greedy_order(tasks: list[Task]) -> list[str]:
    """Among the tasks whose prerequisites are done, always take the one with the most benefit per unit of effort."""
    by = _validate(tasks)
    done: set[str] = set()
    out: list[str] = []
    while len(out) < len(by):
        ready = [t for n, t in by.items() if n not in done and t.needs <= done]
        pick = min(ready, key=lambda t: (-(t.benefit / t.effort), t.name))
        out.append(pick.name)
        done.add(pick.name)
    return out


def best_order(tasks: list[Task]) -> list[str]:
    """The order that minimizes the sum of benefit x completion time, subject to prerequisites. Exact; ties go to the earliest names."""
    by = _validate(tasks)
    names = sorted(by)
    n = len(names)
    if n == 0:
        return []
    bit = {name: 1 << i for i, name in enumerate(names)}
    needs = [sum((bit[x] for x in by[name].needs), 0) for name in names]
    effort = [by[name].effort for name in names]
    benefit = [by[name].benefit for name in names]
    full = (1 << n) - 1
    elapsed = [Fraction(0)] * (1 << n)
    for mask in range(1, 1 << n):
        low = (mask & -mask).bit_length() - 1
        elapsed[mask] = elapsed[mask & (mask - 1)] + effort[low]
    # togo[mask] = least cost of finishing the remaining tasks once the tasks in mask are done (None if mask is not a reachable state)
    togo: list[Fraction | None] = [None] * (1 << n)
    togo[full] = Fraction(0)
    for mask in range(full - 1, -1, -1):
        best: Fraction | None = None
        for j in range(n):
            if mask & (1 << j) or needs[j] & ~mask:
                continue
            rest = togo[mask | (1 << j)]
            if rest is None:
                continue
            c = benefit[j] * (elapsed[mask] + effort[j]) + rest
            if best is None or c < best:
                best = c
        togo[mask] = best
    # walk forward, always taking the alphabetically first task that keeps the plan optimal, so the answer is canonical
    order: list[str] = []
    mask = 0
    while mask != full:
        target = togo[mask]
        for j in range(n):
            if mask & (1 << j) or needs[j] & ~mask:
                continue
            rest = togo[mask | (1 << j)]
            if rest is not None and benefit[j] * (elapsed[mask] + effort[j]) + rest == target:
                order.append(names[j])
                mask |= 1 << j
                break
        else:  # pragma: no cover
            raise AssertionError("no optimal continuation")
    return order


def plan(tasks: list[Task]) -> Plan:
    """The exact best order, the greedy comparison and the schedule."""
    best = best_order(tasks)
    greedy = greedy_order(tasks)
    by = {t.name: t for t in tasks}
    clock = Fraction(0)
    steps = []
    for n in best:
        start = clock
        clock += by[n].effort
        steps.append(Step(n, float(start), float(clock), float(by[n].benefit)))
    return Plan(tuple(best), tuple(steps), float(cost_of(best, tasks)), tuple(greedy), float(cost_of(greedy, tasks)), float(clock))
