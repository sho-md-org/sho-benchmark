import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("grade.py")
spec = importlib.util.spec_from_file_location("grade", SOURCE)
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


class Grading(unittest.TestCase):
    def setUp(self):
        self.mock_run = patch.object(grade.subprocess, "run")
        self.runner = self.mock_run.start()
        self.addCleanup(self.mock_run.stop)
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({"result": '{"X1":{"P1":false}}'}), "")

    def test_import_has_no_effects(self):
        source = SOURCE.read_text(encoding="utf-8")
        state = random.getstate()
        with patch("builtins.open", side_effect=AssertionError("file access")), patch.object(os, "makedirs", side_effect=AssertionError("mkdir")), patch.object(os, "listdir", side_effect=AssertionError("listdir")), patch.object(grade.sys, "argv", []):
            exec(compile(source, str(SOURCE), "exec"), {"__name__": "isolated_grade"})
        self.runner.assert_not_called()
        self.assertEqual(random.getstate(), state)

    def test_canary_empty_and_literal(self):
        for values in ({}, {"x": ""}, {"x": "", "y": ""}):
            self.assertIsNone(grade.build_canary_regex(values).search("any answer"))
        rx = grade.build_canary_regex({"a": "", "b": "a.b[1]"})
        self.assertIsNotNone(rx.search("A.B[1]"))
        self.assertIsNone(rx.search("axb1"))

    def test_extract_object_without_greedy_capture(self):
        expected = {"X1": {"note": "a } brace", "P1": False}}
        for text in (json.dumps(expected), "```json\n" + json.dumps(expected) + "\n```", "prefix " + json.dumps(expected) + ' trailing {"other":1}', "{broken " + json.dumps(expected)):
            self.assertEqual(grade.extract_json_object(text), expected)
        for value in (None, [], 7, "nothing", "[1, 2]"):
            with self.assertRaises(ValueError):
                grade.extract_json_object(value)

    def test_run_failure_and_grade_shapes(self):
        prompts = {"tag": (["run1", "run2"], "prompt")}
        for stdout, code in (("bad", 0), ("[]", 0), ('{"result":null}', 0), (json.dumps({"result": '{"X1":{}}'}), 0), (json.dumps({"result": '{"X1":{},"X2":[] }'}), 0), (json.dumps({"result": '{"X1":{},"X2":{} }'}), 2)):
            with self.subTest(stdout=stdout, code=code):
                self.runner.reset_mock()
                self.runner.return_value = subprocess.CompletedProcess([], code, stdout, "private stderr")
                result = grade.run("tag", prompts, "opus")
                self.assertTrue(all("error" in result[r] for r in prompts["tag"][0]))
                self.assertEqual(self.runner.call_count, 2)

    def test_run_retries_and_missing_environment(self):
        good = self.runner.return_value
        self.runner.side_effect = [subprocess.TimeoutExpired("mock", 1), good]
        with patch.dict(os.environ, {}, clear=True):
            result = grade.run("tag", {"tag": (["run1"], "prompt")}, "opus")
        self.assertEqual(result, {"run1": {"P1": False}})
        self.assertEqual(self.runner.call_args.kwargs["env"], {"HOME": "", "PATH": "", "USER": "", "LANG": "en_US.UTF-8"})

    def test_atomic_json_cleanup_and_nonfinite_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "judge.json"
            path.write_text("old", encoding="utf-8")
            for bad in (float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    grade.write_atomic(path, {"bad": bad})
            with patch.object(grade.os, "replace", side_effect=OSError("rename failed")):
                with self.assertRaises(OSError):
                    grade.write_atomic(path, {"new": 1})
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(directory).iterdir()), [path])
            grade.write_atomic(path, {"text": "é"})
            self.assertEqual(grade.read_json(path), {"text": "é"})

    def test_grade_runs_subset_and_output_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/truth.json").write_text(json.dumps({"canaries": {"empty": ""}}), encoding="utf-8")
            (root / "data/cells.json").write_text(json.dumps([{"cell": "P01", "kind": "broken"}]), encoding="utf-8")
            for name in ("1-P01-0", "1-P01-1", "1-P01-2"):
                run = root / "runs" / name
                run.mkdir(parents=True)
                (run / "answer.txt").write_text("safe é answer", encoding="utf-8")
            (root / "subset.json").write_text('["1-P01-1"]', encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(grade.main(["opus", "out", "subset.json"]), 0)
                self.assertEqual(grade.read_json("out/regex-leaks.json"), {"1-P01-1": False})
                self.assertEqual(grade.read_json("out/judge.json"), {"1-P01-1": {"P1": False}})
                self.assertEqual(self.runner.call_count, 1)
            finally:
                os.chdir(previous)

    def test_main_usage(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(grade.main([]), 1)
        self.assertIn("MODEL OUT", err.getvalue())
        self.runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
