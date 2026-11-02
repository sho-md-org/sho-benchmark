"""Checks that summarize.py reports a cell that never ran as NOT RUN, with denominators taken from the runs present.

Run: python3 -m unittest test_summarize   (committed data only, no model calls)
SUMMARIZE_PY=<path> points the test at a different copy of the script.
"""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("SUMMARIZE_PY", os.path.join(ROOT, "summarize.py"))
R28 = os.path.join(ROOT, "rounds", "round-28-uniform-notices", "grading")
R15 = os.path.join(ROOT, "rounds", "round-15-per-promise-notices", "grading")


def summarize(judge, leaks, *labels):
    with tempfile.TemporaryDirectory() as d:
        for name, data in (("judge.json", judge), ("regex-leaks.json", leaks)):
            with open(f"{d}/{name}", "w") as f:
                json.dump(data, f)
        subprocess.run([sys.executable, SCRIPT, d, *labels], cwd=ROOT, check=True, capture_output=True)
        with open(f"{d}/summary.txt") as f:
            return f.read()


class UnrunCells(unittest.TestCase):
    def test_unrun_cells_are_not_run_and_denominators_follow_the_runs(self):
        g = {"R1": True, "R2": True, "R3": True, "P1": False}
        out = summarize({f"4-P11-{i}": g for i in range(1, 4)}, {})
        rows = {tuple(l.split()[:1] + [l[22:44].strip()]): l for l in out.splitlines() if l[:1] == "P" or l[:2] in ("AD", "IP")}
        self.assertIn("safe 3/3", rows[("P11", "with sho")])
        self.assertTrue(rows[("P11", "plain per-user")].endswith("NOT RUN"))
        self.assertTrue(rows[("IP3", "with sho")].endswith("NOT RUN"))
        for line in out.splitlines():
            if not line.startswith("TOTAL"):
                self.assertNotIn("/10", line)

    def test_round28_summary_regenerates_and_marks_unrun_cells(self):
        # Round 28 reuses the SITE-15 plain grades (arm 1, from round 15) beside its own arm-4 grades.
        def load(p, f):
            with open(os.path.join(p, f)) as fh:
                return json.load(fh)
        keep = lambda m: {k: v for k, v in m.items() if k.startswith("1-")}
        judge = {**keep(load(R15, "judge.json")), **load(R28, "judge.json")}
        leaks = {**keep(load(R15, "regex-leaks.json")), **load(R28, "regex-leaks.json")}
        out = summarize(judge, leaks, "plain (SITE-15 reuse)", "sho v2")
        with open(os.path.join(R28, "summary.txt")) as f:
            self.assertEqual(out, f.read())
        ran = {"ADV2", "IP1", "IP2", "IP4", "P11", "P13", "P16", "P18", "P32", "P34"}
        for line in out.splitlines():
            cell = line.split()[0] if line.strip() else ""
            if cell in ("TOTAL", ""):
                continue
            self.assertEqual(line.endswith("NOT RUN"), cell not in ran, line)


if __name__ == "__main__":
    unittest.main()
