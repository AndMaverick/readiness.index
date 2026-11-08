import unittest

from readiness_index import DIMENSIONS, gaps, level, roadmap, score


def uniform(rating):
    return {d: [rating, rating] for d in DIMENSIONS}


class ReadinessTests(unittest.TestCase):
    def test_extremes(self):
        self.assertEqual(score(uniform(1))["overall"], 0.0)
        self.assertEqual(score(uniform(5))["overall"], 100.0)
        self.assertEqual(score(uniform(5))["level"], "Leading")

    def test_midpoint(self):
        result = score(uniform(3))
        self.assertEqual(result["overall"], 50.0)
        self.assertEqual(result["level"], "Developing")

    def test_weighting_matters(self):
        answers = uniform(5)
        answers["data"] = [1]
        low_data = score(answers)["overall"]
        answers = uniform(5)
        answers["strategy"] = [1]
        low_strategy = score(answers)["overall"]
        self.assertLess(low_data, low_strategy)

    def test_level_bands(self):
        self.assertEqual([level(x) for x in (10, 45, 65, 90)], ["Emerging", "Developing", "Scaling", "Leading"])

    def test_gaps_weakest_first(self):
        answers = uniform(4)
        answers["governance"] = [1, 2]
        answers["talent"] = [2, 3]
        found = gaps(score(answers))
        self.assertEqual([d for d, _ in found], ["governance", "talent"])

    def test_roadmap_orders_by_weighted_impact(self):
        answers = uniform(5)
        answers["strategy"] = [2]
        answers["governance"] = [1]
        order = [d for d, _, _ in roadmap(score(answers))]
        self.assertEqual(order[0], "governance")

    def test_validation(self):
        with self.assertRaises(ValueError):
            score({"strategy": [3]})
        bad = uniform(3)
        bad["data"] = [6]
        with self.assertRaises(ValueError):
            score(bad)
        with self.assertRaises(ValueError):
            score(uniform(3), weights={"strategy": 0.5})


if __name__ == "__main__":
    unittest.main()
