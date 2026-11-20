import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from readiness_index import SpecError, analyze, cli, compare_assessments, fingerprint, loads
from readiness_index.report import compare_text, to_text

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def load(name):
    return loads((EX / name).read_text(encoding="utf-8"))


class TestLoading(unittest.TestCase):
    def test_duplicate_keys_and_bad_json_are_refused(self):
        for text in ('{"a": 1, "a": 2}', "[1]", "nope", '{"a": NaN}', '{"a": Infinity}'):
            with self.subTest(text=text), self.assertRaises(SpecError):
                loads(text)


class TestFingerprint(unittest.TestCase):
    def test_stable_across_key_order_and_changes_with_content(self):
        a = load("acme_assessment.json")
        reordered = json.loads(json.dumps(dict(reversed(list(a.items())))))
        self.assertEqual(fingerprint(a), fingerprint(reordered))
        base = fingerprint(a)
        for edit in (
            lambda d: d["respondents"]["r01"]["ratings"].update({"data.1": 1}),
            lambda d: d["gates"].update(min_dimension=51),
            lambda d: d["simulation"].update(seed=6),
            lambda d: d.update(name="other"),
            lambda d: d["evidence"].pop(next(iter(d["evidence"]))),
        ):
            b = copy.deepcopy(a)
            edit(b)
            self.assertNotEqual(fingerprint(b), base)


class TestAnalysis(unittest.TestCase):
    def test_acme_passes_and_northgate_fails_on_the_right_gates(self):
        acme = analyze(load("acme_assessment.json"))
        self.assertTrue(acme["passed"])
        self.assertEqual(acme["level"], "Scaling")
        north = analyze(load("northgate_assessment.json"))
        failed = {g["gate"] for g in north["gates"] if not g["passed"]}
        self.assertEqual(failed, {"min_dimension", "max_contested_items", "max_perception_gap", "min_coverage", "max_unsupported_high", "min_prob_level"})
        self.assertEqual(north["plan"]["order"][0], "governance")

    def test_reproducible(self):
        a, b = analyze(load("northgate_assessment.json")), analyze(load("northgate_assessment.json"))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_plan_respects_prerequisites_and_ends_at_target(self):
        r = analyze(load("northgate_assessment.json"))
        order = r["plan"]["order"]
        self.assertLess(order.index("data"), order.index("operations"))
        self.assertLess(order.index("governance"), order.index("operations"))
        finish = r["plan"]["steps"][-1]
        self.assertAlmostEqual(finish["finish"], r["plan"]["total_effort"])
        self.assertLessEqual(r["plan"]["cost"], r["plan"]["greedy_cost"])
        gains = sum(s["overall_gain"] for s in r["plan"]["steps"])
        self.assertAlmostEqual(r["plan"]["steps"][-1]["overall_after"] - r["overall"], gains, places=9)

    def test_no_plan_when_every_dimension_meets_its_target(self):
        a = load("acme_assessment.json")
        a["targets"] = {"default": 10}
        self.assertIsNone(analyze(a)["plan"])

    def test_targets_accept_level_names(self):
        a = load("acme_assessment.json")
        a["targets"] = {"default": "Leading", "data": 50}
        r = analyze(a)
        self.assertEqual(r["dimensions"]["strategy"]["target"], 80)
        self.assertEqual(r["dimensions"]["data"]["target"], 50)

    def test_custom_instrument(self):
        spec = {"name": "mini", "dimensions": {"x": {"weight": 1, "items": [{"id": "x.1", "text": "t", "anchors": {"1": "a", "3": "b", "5": "c"}}]}}}
        r = analyze({"instrument": spec, "respondents": {"p": {"ratings": {"x.1": 5}}, "q": {"ratings": {"x.1": 3}}}})
        self.assertEqual(r["overall"], 75.0)
        self.assertEqual(r["instrument"], "mini")

    def test_cycle_and_bad_references_are_input_errors(self):
        a = load("acme_assessment.json")
        a["targets"] = {"default": 99}
        a["prerequisites"] = {"data": ["governance"], "governance": ["data"]}
        with self.assertRaises(SpecError):
            analyze(a)
        for bad in ({"nope": ["data"]}, {"data": ["nope"]}, {"data": "governance"}, []):
            b = load("acme_assessment.json")
            b["prerequisites"] = bad
            with self.subTest(bad=bad), self.assertRaises(SpecError):
                analyze(b)

    def test_bad_inputs(self):
        base = load("acme_assessment.json")
        edits = {
            "unknown key": lambda d: d.update(extra=1),
            "unknown target dimension": lambda d: d.update(targets={"nope": 50}),
            "target out of range": lambda d: d.update(targets={"default": 120}),
            "bad effort": lambda d: d.update(effort_per_point={"data": 0}),
            "bad resamples": lambda d: d.update(simulation={"resamples": 3}),
            "bad seed": lambda d: d.update(simulation={"seed": "x"}),
            "unknown gate": lambda d: d["gates"].update(nope=1),
            "bad level gate": lambda d: d["gates"].update(min_level="Mythical"),
            "gate range": lambda d: d["gates"].update(min_coverage=2),
            "unpaired gate": lambda d: d["gates"].pop("target_level"),
            "no respondents": lambda d: d.update(respondents={}),
        }
        for label, edit in edits.items():
            d = copy.deepcopy(base)
            edit(d)
            with self.subTest(label), self.assertRaises(SpecError):
                analyze(d)

    def test_text_report_content_and_no_em_dash(self):
        text = to_text(analyze(load("northgate_assessment.json")))
        for needle in ("RESULT: FAIL", "Roadmap", "governance", "contested", "no evidence on file", "FAIL  min_dimension"):
            self.assertIn(needle, text)
        self.assertNotIn(chr(0x2014), text)


class TestCompare(unittest.TestCase):
    def test_example_change(self):
        c = compare_assessments(load("acme_before.json"), load("acme_assessment.json"))
        rows = {r["name"]: r for r in c["changes"]}
        self.assertTrue(rows["overall"]["reliable"])
        self.assertTrue(rows["governance"]["reliable"])
        self.assertAlmostEqual(rows["overall"]["delta"], rows["overall"]["after"] - rows["overall"]["before"])
        self.assertIn("reliable gain", compare_text(c))

    def test_different_instruments_are_refused(self):
        a = load("acme_assessment.json")
        b = copy.deepcopy(a)
        spec = {"dimensions": {"x": {"weight": 1, "items": [{"id": "x.1", "text": "t", "anchors": {"1": "a", "3": "b", "5": "c"}}]}}}
        b["instrument"] = spec
        b["respondents"] = {"p": {"ratings": {"x.1": 4}}}
        with self.assertRaises(SpecError):
            compare_assessments(a, b)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_exit_codes(self):
        self.assertEqual(self.run_cli("assess", str(EX / "acme_assessment.json"))[0], 0)
        self.assertEqual(self.run_cli("assess", str(EX / "northgate_assessment.json"))[0], 1)
        code, _, err = self.run_cli("assess", str(EX / "missing.json"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_bad_file_is_exit_2(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write('{"respondents": {}}')
        try:
            code, _, err = self.run_cli("assess", fh.name)
        finally:
            os.unlink(fh.name)
        self.assertEqual(code, 2)
        self.assertIn("respondent", err)

    def test_json_and_overrides(self):
        code, out, _ = self.run_cli("assess", str(EX / "acme_assessment.json"), "--json", "--resamples", "100", "--seed", "9")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["version"], "0.2.0")

    def test_compare_instrument_and_fingerprint_commands(self):
        code, out, _ = self.run_cli("compare", str(EX / "acme_before.json"), str(EX / "acme_assessment.json"))
        self.assertEqual(code, 0)
        self.assertIn("overall", out)
        code, out, _ = self.run_cli("instrument")
        self.assertEqual(len(json.loads(out)["dimensions"]), 6)
        code, out, _ = self.run_cli("fingerprint", str(EX / "acme_assessment.json"))
        self.assertEqual(out.strip(), fingerprint(load("acme_assessment.json")))

    def test_module_entry_point_and_hash_seed_independence(self):
        outs = []
        for hash_seed in ("0", "1", "4242"):
            env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(ROOT)}
            p = subprocess.run(
                [sys.executable, "-m", "readiness_index", "assess", str(EX / "northgate_assessment.json"), "--json"],
                capture_output=True, text=True, env=env, cwd=ROOT, check=False,
            )
            self.assertEqual(p.returncode, 1, p.stderr)
            outs.append(p.stdout)
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[0], outs[2])


if __name__ == "__main__":
    unittest.main()
