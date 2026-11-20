"""Independent implementations used to check the library: they share no code with it."""
from __future__ import annotations

import itertools
from collections import Counter
from fractions import Fraction


def alpha_coincidence(rows, items):
    """Krippendorff's alpha (interval) by the coincidence-matrix route, the way the original paper lays it out.

    ``rows`` is a list of {item: rating or None} dicts, one per coder. Differs from the library's pair-sum computation."""
    coincidence = Counter()
    for iid in items:
        vals = [r[iid] for r in rows if r.get(iid) is not None]
        m = len(vals)
        if m < 2:
            continue
        for i, a in enumerate(vals):
            for j, b in enumerate(vals):
                if i != j:
                    coincidence[(a, b)] += 1 / (m - 1)
    n_c = Counter()
    for (a, _), w in coincidence.items():
        n_c[a] += w
    n = sum(n_c.values())
    if n <= 1:
        return None
    observed = sum(w * (a - b) ** 2 for (a, b), w in coincidence.items())
    expected = sum(n_c[a] * n_c[b] * (a - b) ** 2 for a in n_c for b in n_c)
    if expected == 0:
        return None
    return 1 - (n - 1) * observed / expected


def score_by_hand(instrument_spec, respondents):
    """Dimension and overall scores straight from the definition, using Fractions and plain loops."""
    dims = {}
    total_w = sum(Fraction(repr(d["weight"])) for d in instrument_spec["dimensions"].values())
    overall = Fraction(0)
    for dname, d in instrument_spec["dimensions"].items():
        num = den = Fraction(0)
        for it in d["items"]:
            iw = Fraction(repr(it.get("weight", 1)))
            a = b = Fraction(0)
            for r in respondents:
                v = r["ratings"].get(it["id"])
                if v is not None:
                    rw = Fraction(repr(r.get("weight", 1)))
                    a += rw * v
                    b += rw
            if b:
                num += iw * a / b
                den += iw
        dims[dname] = (num / den - 1) / 4 * 100
        overall += Fraction(repr(d["weight"])) / total_w * dims[dname]
    return dims, overall


def brute_force_cost(tasks):
    """Cheapest valid order of (name, benefit, effort, needs) by trying every permutation. Returns (cost, order)."""
    best = None
    names = [t[0] for t in tasks]
    info = {t[0]: t for t in tasks}
    for perm in itertools.permutations(names):
        seen, ok, clock, cost = set(), True, Fraction(0), Fraction(0)
        for n in perm:
            _, benefit, effort, needs = info[n]
            if not set(needs) <= seen:
                ok = False
                break
            seen.add(n)
            clock += Fraction(repr(effort))
            cost += Fraction(repr(benefit)) * clock
        if ok and (best is None or cost < best[0]):
            best = (cost, perm)
    return best
