import random
import unittest
from fractions import Fraction as F

from readiness_index import SpecError, best_order, greedy_order, make_task, plan_work
from readiness_index.planner import MAX_TASKS, cost_of, is_valid_order
from tests import oracles


def random_instance(seed, n):
    rng = random.Random(seed)
    names = [f"t{i}" for i in range(n)]
    tasks = []
    for i, name in enumerate(names):
        earlier = names[:i]
        needs = {x for x in earlier if rng.random() < 0.3}
        tasks.append((name, rng.choice([0, 0.5, 1, 2, 3.5, 7, 10]), rng.choice([0.5, 1, 2, 3, 5]), needs))
    rng.shuffle(tasks)                                 # the order tasks are listed in must not matter
    return tasks


def build(raw):
    return [make_task(n, b, e, set(needs)) for n, b, e, needs in raw]


class TestPlanner(unittest.TestCase):
    def test_matches_brute_force_over_all_permutations(self):
        for seed in range(150):
            n = random.Random(seed).randint(1, 7)
            raw = random_instance(seed, n)
            tasks = build(raw)
            order = best_order(tasks)
            want, _ = oracles.brute_force_cost([(a, b, c, tuple(d)) for a, b, c, d in raw])
            self.assertTrue(is_valid_order(order, tasks), msg=f"seed {seed}")
            self.assertEqual(cost_of(order, tasks), want, msg=f"seed {seed}")

    def test_never_worse_than_greedy_and_sometimes_better(self):
        better = 0
        for seed in range(300):
            raw = random_instance(1000 + seed, random.Random(seed).randint(3, 8))
            tasks = build(raw)
            best, greedy = cost_of(best_order(tasks), tasks), cost_of(greedy_order(tasks), tasks)
            self.assertLessEqual(best, greedy)
            better += best < greedy
        self.assertGreater(better, 0)

    def test_hand_examples(self):
        # no prerequisites: highest benefit per effort first (Smith's rule): A has ratio 2, B has 1.5
        t = [make_task("A", 6, 3), make_task("B", 3, 2)]
        self.assertEqual(best_order(t), ["A", "B"])
        self.assertEqual(cost_of(["A", "B"], t), 6 * 3 + 3 * 5)
        # a low-value task unlocks a high-value one; the greedy rule starts with the wrong task
        t = [make_task("A", 1, 1), make_task("B", 3, 2), make_task("C", 10, 1, {"A"})]
        self.assertEqual(best_order(t), ["A", "C", "B"])
        self.assertEqual(cost_of(best_order(t), t), 33)
        self.assertEqual(greedy_order(t), ["B", "A", "C"])
        self.assertEqual(cost_of(greedy_order(t), t), 49)

    def test_no_prerequisites_is_smiths_rule(self):
        for seed in range(50):
            rng = random.Random(seed)
            tasks = [make_task(f"t{i}", rng.uniform(0.1, 9), rng.uniform(0.5, 6)) for i in range(7)]
            smith = sorted((t.name for t in tasks), key=lambda n: -next(t for t in tasks if t.name == n).benefit / next(t for t in tasks if t.name == n).effort)
            self.assertEqual(cost_of(best_order(tasks), tasks), cost_of(smith, tasks))

    def test_listing_order_does_not_change_the_answer(self):
        raw = random_instance(9, 7)
        a = best_order(build(raw))
        b = best_order(build(list(reversed(raw))))
        self.assertEqual(a, b)

    def test_ties_resolve_by_name(self):
        t = [make_task("b", 2, 1), make_task("a", 2, 1), make_task("c", 2, 1)]
        self.assertEqual(best_order(t), ["a", "b", "c"])

    def test_plan_schedule_and_saving(self):
        t = [make_task("A", 1, 1), make_task("B", 3, 2), make_task("C", 10, 1, {"A"})]
        p = plan_work(t)
        self.assertEqual(p.order, ("A", "C", "B"))
        self.assertEqual([(s.name, s.start, s.finish) for s in p.steps], [("A", 0, 1), ("C", 1, 2), ("B", 2, 4)])
        self.assertEqual((p.cost, p.greedy_cost, p.total_effort), (33.0, 49.0, 4.0))
        self.assertAlmostEqual(p.saving, 1 - 33 / 49)

    def test_empty_and_single(self):
        self.assertEqual(best_order([]), [])
        self.assertEqual(best_order([make_task("x", 1, 1)]), ["x"])

    def test_errors(self):
        with self.assertRaises(SpecError):
            best_order([make_task("a", 1, 1, {"b"}), make_task("b", 1, 1, {"a"})])
        with self.assertRaises(SpecError):
            best_order([make_task("a", 1, 1, {"zzz"})])
        with self.assertRaises(SpecError):
            best_order([make_task("a", 1, 1, {"a"})])
        with self.assertRaises(SpecError):
            best_order([make_task("a", 1, 1), make_task("a", 2, 2)])
        with self.assertRaises(SpecError):
            make_task("a", -1, 1)
        with self.assertRaises(SpecError):
            make_task("a", 1, 0)
        with self.assertRaises(SpecError):
            best_order([make_task(f"t{i}", 1, 1) for i in range(MAX_TASKS + 1)])

    def test_limit_size_runs_in_reasonable_time(self):
        tasks = [make_task(f"t{i}", 1 + i % 5, 1 + i % 3, {f"t{i - 1}"} if i % 4 == 3 else set()) for i in range(14)]
        order = best_order(tasks)
        self.assertTrue(is_valid_order(order, tasks))

    def test_exact_arithmetic(self):
        t = [make_task("a", 0.1, 0.3), make_task("b", 0.2, 0.6)]
        self.assertEqual(cost_of(["a", "b"], t), F(1, 10) * F(3, 10) + F(2, 10) * F(9, 10))


if __name__ == "__main__":
    unittest.main()
