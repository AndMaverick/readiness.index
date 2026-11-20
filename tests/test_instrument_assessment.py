import copy
import random
import unittest
from fractions import Fraction as F

from readiness_index import DEFAULT_SPEC, DIMENSIONS, SpecError, default_instrument, parse_instrument, score_responses
from readiness_index.assessment import (
    contested_items,
    coverage,
    disagreement,
    level_floor,
    level_name,
    parse_responses,
    perception_gaps,
    unsupported_high,
)
from readiness_index.synthetic import assessment, respondent_ratings
from tests import oracles

INST = default_instrument()


def small_spec():
    return {
        "name": "tiny",
        "dimensions": {
            "a": {"weight": 1, "items": [
                {"id": "a.1", "text": "t", "anchors": {"1": "x", "3": "y", "5": "z"}},
                {"id": "a.2", "text": "t", "anchors": {"1": "x", "3": "y", "5": "z"}},
            ]},
            "b": {"weight": 1, "items": [{"id": "b.1", "text": "t", "anchors": {"1": "x", "3": "y", "5": "z"}}]},
        },
    }


def people(inst, raw):
    return parse_responses(inst, raw).respondents


class TestInstrument(unittest.TestCase):
    def test_default_instrument_shape(self):
        self.assertEqual(len(INST.item_ids), 24)
        self.assertEqual(len(set(INST.item_ids)), 24)
        self.assertEqual(sum(d.weight for d in INST.dimensions), 1)
        self.assertEqual({d.name: float(d.weight) for d in INST.dimensions}, DIMENSIONS)

    def test_every_item_has_anchors_for_1_3_5(self):
        for d in INST.dimensions:
            self.assertEqual(len(d.items), 4)
            for it in d.items:
                self.assertTrue(all(len(a) >= 4 for a in it.anchors), it.id)

    def test_spec_round_trip(self):
        again = parse_instrument(INST.to_spec())
        self.assertEqual(again.to_spec(), INST.to_spec())

    def test_weights_are_normalised(self):
        spec = small_spec()
        spec["dimensions"]["a"]["weight"] = 3
        inst = parse_instrument(spec)
        self.assertEqual({d.name: d.weight for d in inst.dimensions}, {"a": F(3, 4), "b": F(1, 4)})

    def test_strict_validation(self):
        def edit(f):
            s = copy.deepcopy(small_spec())
            f(s)
            return s
        bad = [
            edit(lambda s: s.update(extra=1)),
            edit(lambda s: s["dimensions"]["a"].update(weight=0)),
            edit(lambda s: s["dimensions"]["a"]["items"][0].update(id="b.1")),
            edit(lambda s: s["dimensions"]["a"]["items"][0].update(anchors={"1": "x", "5": "z"})),
            edit(lambda s: s["dimensions"]["a"]["items"][0].update(text="")),
            edit(lambda s: s["dimensions"]["a"]["items"][0].update(weight=-1)),
            edit(lambda s: s["dimensions"]["a"].update(items=[])),
            edit(lambda s: s.update(dimensions={})),
            "nope",
        ]
        for spec in bad:
            with self.subTest(spec=str(spec)[:60]), self.assertRaises(SpecError):
                parse_instrument(spec)


class TestScoring(unittest.TestCase):
    def test_matches_hand_computation_on_random_panels_with_gaps(self):
        for seed in range(40):
            rng = random.Random(seed)
            profile = {d: rng.uniform(1.5, 4.5) for d in INST.dimension_names}
            a = assessment(profile, n=rng.randint(1, 9), seed=seed, blank=0.3)
            for r in a["respondents"].values():
                if rng.random() < 0.3:
                    r["weight"] = rng.choice([0.5, 2, 3])
            try:
                got = score_responses(INST, people(INST, a["respondents"]))
            except SpecError:
                continue                                  # a whole dimension unrated; covered separately
            dims, overall = oracles.score_by_hand(DEFAULT_SPEC, list(a["respondents"].values()))
            self.assertEqual(got.overall, overall, msg=f"seed {seed}")
            self.assertEqual(got.dimensions, dims, msg=f"seed {seed}")

    def test_level_boundaries_are_exact(self):
        # ratings 3,3,3,4,4 average 3.4, which is exactly 60 on the 0 to 100 scale
        spec = {"dimensions": {"a": {"weight": 1, "items": [
            {"id": f"a.{i}", "text": "t", "anchors": {"1": "x", "3": "y", "5": "z"}} for i in range(5)]}}}
        inst = parse_instrument(spec)
        r = {"x": {"ratings": {"a.0": 3, "a.1": 3, "a.2": 3, "a.3": 4, "a.4": 4}}}
        s = score_responses(inst, people(inst, r))
        self.assertEqual(s.overall, 60)
        self.assertEqual(s.level, "Scaling")
        self.assertEqual(level_name(F(5999999, 100000)), "Developing")
        self.assertEqual([level_name(x) for x in (0, 39, 40, 59, 60, 79, 80, 100)],
                         ["Emerging", "Emerging", "Developing", "Developing", "Scaling", "Scaling", "Leading", "Leading"])

    def test_bottleneck_caps_the_level(self):
        inst = parse_instrument(small_spec())
        r = {"x": {"ratings": {"a.1": 5, "a.2": 5, "b.1": 2}}}      # a = 100, b = 25, overall 62.5
        s = score_responses(inst, people(inst, r))
        self.assertEqual(s.level_by_score, "Scaling")
        self.assertEqual(s.level, "Developing")
        self.assertEqual(s.limiting_dimension, "b")
        r2 = {"x": {"ratings": {"a.1": 5, "a.2": 5, "b.1": 4}}}     # b = 75, overall 87.5, cap = Leading
        s2 = score_responses(inst, people(inst, r2))
        self.assertEqual((s2.level, s2.limiting_dimension), ("Leading", None))

    def test_unrated_dimension_is_an_error_and_unrated_item_is_skipped(self):
        inst = parse_instrument(small_spec())
        with self.assertRaises(SpecError):
            score_responses(inst, people(inst, {"x": {"ratings": {"a.1": 3, "a.2": 3}}}))
        s = score_responses(inst, people(inst, {"x": {"ratings": {"a.1": 5, "b.1": 1}}}))
        self.assertEqual(s.dimensions["a"], 100)
        self.assertIsNone(s.items["a.2"])

    def test_invariances(self):
        a = assessment(dict.fromkeys(INST.dimension_names, 3.2), n=6, seed=3)
        base = score_responses(INST, people(INST, a["respondents"]))
        rev = dict(reversed(list(a["respondents"].items())))
        self.assertEqual(score_responses(INST, people(INST, rev)).overall, base.overall)
        doubled = {**a["respondents"], **{k + "_copy": v for k, v in a["respondents"].items()}}
        self.assertEqual(score_responses(INST, people(INST, doubled)).dimensions, base.dimensions)
        weighted = copy.deepcopy(a["respondents"])
        weighted["r01"]["weight"] = 2
        dup = copy.deepcopy(a["respondents"])
        dup["r01_copy"] = copy.deepcopy(dup["r01"])
        self.assertEqual(score_responses(INST, people(INST, weighted)).overall, score_responses(INST, people(INST, dup)).overall)

    def test_raising_every_rating_by_one_adds_25_points(self):
        r = {"x": {"ratings": dict.fromkeys(INST.item_ids, 2)}}
        r2 = {"x": {"ratings": dict.fromkeys(INST.item_ids, 3)}}
        a, b = score_responses(INST, people(INST, r)), score_responses(INST, people(INST, r2))
        self.assertEqual(b.overall - a.overall, 25)

    def test_monotone_in_every_rating(self):
        rng = random.Random(1)
        base = {i: rng.randint(1, 4) for i in INST.item_ids}
        s0 = score_responses(INST, people(INST, {"x": {"ratings": base}}))
        for iid in INST.item_ids:
            up = dict(base)
            up[iid] += 1
            s1 = score_responses(INST, people(INST, {"x": {"ratings": up}}))
            self.assertGreater(s1.overall, s0.overall)

    def test_input_validation(self):
        ok = dict.fromkeys(INST.item_ids, 3)
        bad = [
            {},
            {"x": {"ratings": {**ok, "strategy.1": 6}}},
            {"x": {"ratings": {**ok, "strategy.1": 0}}},
            {"x": {"ratings": {**ok, "strategy.1": 3.5}}},
            {"x": {"ratings": {**ok, "strategy.1": True}}},
            {"x": {"ratings": {**ok, "nope.1": 3}}},
            {"x": {"ratings": ok, "weight": 0}},
            {"x": {"ratings": ok, "colour": 1}},
            {"x": {"role": "", "ratings": ok}},
            {"x": ok},
        ]
        for raw in bad:
            with self.subTest(raw=str(raw)[:50]), self.assertRaises(SpecError):
                parse_responses(INST, raw)

    def test_coverage(self):
        raw = {"x": {"ratings": dict.fromkeys(INST.item_ids, 3)}, "y": {"ratings": dict.fromkeys(INST.item_ids[:12], 3)}}
        self.assertEqual(coverage(INST, people(INST, raw)), 36 / 48)


class TestAudits(unittest.TestCase):
    def test_unsupported_high_ratings(self):
        raw = {"x": {"ratings": {i: (5 if i.startswith("data") else 2) for i in INST.item_ids}}}
        resp = parse_responses(INST, raw, {"data.1": "Access policy v3, approved 2026-03"})
        sc = score_responses(INST, resp.respondents)
        self.assertEqual(unsupported_high(INST, resp, sc), ["data.2", "data.3", "data.4"])
        with self.assertRaises(SpecError):
            parse_responses(INST, raw, {"data.1": "  "})
        with self.assertRaises(SpecError):
            parse_responses(INST, raw, {"made.up": "x"})

    def test_roles_and_perception_gaps(self):
        base = dict.fromkeys(INST.item_ids, 3)
        high = {i: (5 if i.startswith("data") else 3) for i in INST.item_ids}
        raw = {"e1": {"role": "executive", "ratings": high}, "p1": {"role": "practitioner", "ratings": base}, "p2": {"role": "practitioner", "ratings": base}}
        gaps = perception_gaps(INST, people(INST, raw))
        self.assertEqual(gaps[0]["dimension"], "data")
        self.assertEqual((gaps[0]["highest_role"], gaps[0]["lowest_role"]), ("executive", "practitioner"))
        self.assertAlmostEqual(gaps[0]["gap"], 50.0)
        self.assertEqual([g["gap"] for g in gaps[1:]], [0.0] * 5)
        self.assertEqual(perception_gaps(INST, people(INST, {"p1": {"role": "p", "ratings": base}})), [])

    def test_disagreement_and_contested(self):
        spec = parse_instrument(small_spec())
        raw = {"x": {"ratings": {"a.1": 1, "a.2": 3, "b.1": 5}}, "y": {"ratings": {"a.1": 5, "a.2": 3, "b.1": 5}}}
        p = people(spec, raw)
        d = disagreement(spec, p)
        self.assertAlmostEqual(d["a"], (((1 - 3) ** 2 + (5 - 3) ** 2) ** 0.5 + 0) / 2)       # sample sd of (1,5) is 2.828; of (3,3) is 0
        self.assertEqual(d["b"], 0.0)
        c = contested_items(spec, p)
        self.assertEqual([x["item"] for x in c], ["a.1"])
        self.assertEqual((c[0]["low"], c[0]["high"], c[0]["range"]), (1, 5, 4))
        self.assertIsNone(disagreement(spec, people(spec, {"x": {"ratings": {"a.1": 1, "a.2": 3, "b.1": 5}}}))["a"])

    def test_level_names(self):
        self.assertEqual(level_floor("Scaling"), 60)
        with self.assertRaises(SpecError):
            level_floor("Mythical")

    def test_synthetic_ratings_are_reproducible_and_in_range(self):
        a = respondent_ratings(random.Random(1), dict.fromkeys(INST.dimension_names, 3.0))
        b = respondent_ratings(random.Random(1), dict.fromkeys(INST.dimension_names, 3.0))
        self.assertEqual(a, b)
        self.assertTrue(all(1 <= v <= 5 for v in a.values()))


if __name__ == "__main__":
    unittest.main()
