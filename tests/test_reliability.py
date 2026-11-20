import random
import unittest

from readiness_index import SpecError, bootstrap, compare, default_instrument, krippendorff_alpha, score_responses
from readiness_index.assessment import parse_responses
from readiness_index.reliability import agreement_label, quantile
from readiness_index.synthetic import assessment
from tests import oracles

INST = default_instrument()
N = None


def panel(profile, n=8, seed=0, **kw):
    return parse_responses(INST, assessment(profile, n=n, seed=seed, **kw)["respondents"]).respondents


FLAT = dict.fromkeys(INST.dimension_names, 3.0)


class TestKrippendorff(unittest.TestCase):
    def test_published_example(self):
        # Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability": 4 coders, 12 units, interval alpha = 0.849
        a = [1, 2, 3, 3, 2, 1, 4, 1, 2, N, N, N]
        b = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, N, 3]
        c = [N, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, N]
        d = [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, N]
        rows = [{f"u{i}": v[i] for i in range(12)} for v in (a, b, c, d)]
        self.assertAlmostEqual(krippendorff_alpha(rows), 0.849, places=3)

    def test_matches_coincidence_matrix_oracle(self):
        for seed in range(80):
            rng = random.Random(seed)
            coders, units = rng.randint(2, 6), rng.randint(2, 15)
            rows = [{f"u{i}": (rng.randint(1, 5) if rng.random() > 0.2 else None) for i in range(units)} for _ in range(coders)]
            items = [f"u{i}" for i in range(units)]
            got, want = krippendorff_alpha(rows, items), oracles.alpha_coincidence(rows, items)
            if want is None:
                self.assertIsNone(got)
            else:
                self.assertAlmostEqual(got, want, places=10, msg=f"seed {seed}")

    def test_perfect_agreement_is_one(self):
        rows = [{"a": 1, "b": 3, "c": 5}, {"a": 1, "b": 3, "c": 5}, {"a": 1, "b": 3, "c": 5}]
        self.assertAlmostEqual(krippendorff_alpha(rows), 1.0)

    def test_undefined_cases(self):
        self.assertIsNone(krippendorff_alpha([{"a": 3, "b": 3}, {"a": 3, "b": 3}]))      # no variation at all
        self.assertIsNone(krippendorff_alpha([{"a": 3, "b": 4}]))                         # nobody to compare with
        self.assertIsNone(krippendorff_alpha([{"a": 3, "b": N}, {"a": N, "b": 4}]))       # no item rated twice

    def test_independent_random_raters_score_near_zero(self):
        vals = []
        for seed in range(60):
            rng = random.Random(seed)
            rows = [{f"u{i}": rng.randint(1, 5) for i in range(30)} for _ in range(5)]
            vals.append(krippendorff_alpha(rows))
        self.assertAlmostEqual(sum(vals) / len(vals), 0.0, delta=0.03)

    def test_invariant_to_coder_order_and_to_a_constant_shift(self):
        rng = random.Random(4)
        rows = [{f"u{i}": rng.randint(1, 4) for i in range(10)} for _ in range(4)]
        a = krippendorff_alpha(rows)
        self.assertAlmostEqual(krippendorff_alpha(list(reversed(rows))), a, places=12)
        self.assertAlmostEqual(krippendorff_alpha([{k: v + 1 for k, v in r.items()} for r in rows]), a, places=12)

    def test_labels(self):
        self.assertEqual([agreement_label(x) for x in (None, 0.9, 0.8, 0.7, 0.5)], ["undefined", "reliable", "reliable", "tentative", "unreliable"])


class TestQuantile(unittest.TestCase):
    def test_known_values(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(quantile(xs, 0), 1.0)
        self.assertEqual(quantile(xs, 1), 5.0)
        self.assertEqual(quantile(xs, 0.5), 3.0)
        self.assertAlmostEqual(quantile(xs, 0.1), 1.4)
        self.assertEqual(quantile([7.0], 0.3), 7.0)

    def test_errors(self):
        with self.assertRaises(ValueError):
            quantile([], 0.5)
        with self.assertRaises(ValueError):
            quantile([1.0], 1.5)


class TestBootstrap(unittest.TestCase):
    def test_deterministic_and_seed_sensitive(self):
        p = panel(FLAT, seed=1)
        a, b = bootstrap(INST, p, resamples=300, seed=7), bootstrap(INST, p, resamples=300, seed=7)
        c = bootstrap(INST, p, resamples=300, seed=8)
        self.assertEqual(a.overall, b.overall)
        self.assertNotEqual(a.overall, c.overall)

    def test_identical_respondents_give_a_zero_width_interval(self):
        ratings = dict.fromkeys(INST.item_ids, 3)
        p = parse_responses(INST, {f"r{k}": {"ratings": ratings} for k in range(5)}).respondents
        b = bootstrap(INST, p, resamples=100)
        lo, hi = b.overall_interval()
        self.assertEqual((lo, hi), (50.0, 50.0))
        self.assertEqual(b.level_probabilities()["Developing"], 1.0)

    def test_single_respondent_has_no_spread(self):
        p = panel(FLAT, n=1)
        lo, hi = bootstrap(INST, p, resamples=100).overall_interval()
        self.assertEqual(lo, hi)

    def test_interval_brackets_the_point_estimate_and_narrows_with_panel_size(self):
        widths = {}
        for n in (4, 16, 64):
            ws = []
            for seed in range(8):
                p = panel(FLAT, n=n, seed=seed)
                point = float(score_responses(INST, p).overall)
                lo, hi = bootstrap(INST, p, resamples=300, seed=1).overall_interval()
                self.assertLessEqual(lo, point + 1.0)
                self.assertGreaterEqual(hi, point - 1.0)
                ws.append(hi - lo)
            widths[n] = sum(ws) / len(ws)
        self.assertGreater(widths[4], widths[16])
        self.assertGreater(widths[16], widths[64])

    def test_probabilities_sum_to_one_and_levels_are_ordered(self):
        b = bootstrap(INST, panel(FLAT, seed=3), resamples=200)
        self.assertAlmostEqual(sum(b.level_probabilities().values()), 1.0)
        self.assertAlmostEqual(b.p_level_at_least("Emerging"), 1.0)
        self.assertLessEqual(b.p_level_at_least("Leading"), b.p_level_at_least("Scaling"))

    def test_small_panel_correction_widens_the_interval_but_stays_on_the_scale(self):
        low = dict.fromkeys(INST.item_ids, 1)
        high = dict.fromkeys(INST.item_ids, 5)
        p = parse_responses(INST, {"a": {"ratings": low}, "b": {"ratings": high}}).respondents
        b = bootstrap(INST, p, resamples=400, seed=1)
        self.assertEqual(b.overall_interval(), (0.0, 100.0))
        self.assertTrue(all(0.0 <= x <= 100.0 for x in b.overall))

    def test_too_few_resamples(self):
        with self.assertRaises(ValueError):
            bootstrap(INST, panel(FLAT), resamples=10)

    def test_resample_missing_a_whole_dimension_does_not_crash(self):
        # one respondent answers only strategy; resamples that omit them must still score
        full = dict.fromkeys(INST.item_ids, 3)
        part = {i: 3 for i in INST.item_ids if i.startswith("strategy")}
        p = parse_responses(INST, {"a": {"ratings": full}, "b": {"ratings": part}}).respondents
        self.assertEqual(len(bootstrap(INST, p, resamples=100).overall), 100)


class TestCompare(unittest.TestCase):
    def test_detects_a_real_change(self):
        before = panel(dict.fromkeys(INST.dimension_names, 2.5), n=9, seed=1)
        after = panel(dict.fromkeys(INST.dimension_names, 3.5), n=9, seed=2)
        rows = {c.name: c for c in compare(INST, before, after, resamples=500)}
        self.assertTrue(rows["overall"].reliable)
        self.assertAlmostEqual(rows["overall"].delta, 25, delta=8)
        self.assertGreater(rows["overall"].low, 0)

    def test_no_change_is_rarely_flagged(self):
        flagged, runs = 0, 40
        for k in range(runs):
            a = panel(FLAT, n=8, seed=100 + k)
            b = panel(FLAT, n=8, seed=500 + k)
            flagged += compare(INST, a, b, resamples=200, seed=k)[0].reliable
        self.assertLessEqual(flagged / runs, 0.15)

    def test_swapping_the_waves_negates_the_change(self):
        a, b = panel(FLAT, seed=1), panel(dict.fromkeys(INST.dimension_names, 3.6), seed=2)
        fwd, back = compare(INST, a, b, resamples=200)[0], compare(INST, b, a, resamples=200)[0]
        self.assertAlmostEqual(fwd.delta, -back.delta, places=12)

    def test_deltas_match_the_scores(self):
        a, b = panel(FLAT, seed=1), panel(dict.fromkeys(INST.dimension_names, 3.6), seed=2)
        row = compare(INST, a, b, resamples=100)[0]
        self.assertAlmostEqual(row.delta, float(score_responses(INST, b).overall - score_responses(INST, a).overall), places=12)

    def test_spec_error_type_is_exported(self):
        self.assertTrue(issubclass(SpecError, ValueError))


if __name__ == "__main__":
    unittest.main()
