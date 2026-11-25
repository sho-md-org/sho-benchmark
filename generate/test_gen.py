import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gen.py")
spec = importlib.util.spec_from_file_location("corpus_generator", SOURCE)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
BASELINE = ("bf74f7ca54f4a98e4bf252fe4c8a2038622d4e25b2c237b640d787f98cdc29f4",
            "20a66f5fedb407e6cdd4293301dd2e3eda5501fb77d2c0748565aea3f32cb0cb")


class GeneratorTests(unittest.TestCase):
    def test_import_does_not_generate_write_or_seed(self):
        source = SOURCE.read_text(encoding="utf-8")
        state = random.getstate()
        with patch("builtins.open", side_effect=AssertionError("file access")), patch.object(Path, "mkdir", side_effect=AssertionError("mkdir")), patch.object(random, "seed", side_effect=AssertionError("seed")), contextlib.redirect_stdout(io.StringIO()) as output:
            exec(compile(source, str(SOURCE), "exec"), {"__name__": "imported_generator"})
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(random.getstate(), state)

    def test_default_bytes_match_pre_refactor_baseline(self):
        records, truth = gen.generate_corpus()
        for value, indent, digest in zip((records, truth), (None, 1), BASELINE):
            self.assertEqual(hashlib.sha256(json.dumps(value, indent=indent).encode("utf-8")).hexdigest(), digest)
        self.assertEqual(len(records), 3000)
        ids = {r["id"] for r in records}
        self.assertEqual(len(ids), 3000)
        self.assertTrue(all(p["record"] in ids for p in truth["promises"]))
        self.assertTrue(set(truth["canaries"]).issubset(ids))

    def test_repeatability_independence_and_global_random_state(self):
        state = random.getstate()
        first = gen.generate_corpus()
        self.assertEqual(first, gen.generate_corpus())
        self.assertNotEqual(first, gen.generate_corpus(seed=2))
        self.assertNotEqual(first, gen.generate_corpus(id_seed=2))
        self.assertEqual(gen.generate_corpus(2, 3), gen.generate_corpus(2, 3))
        first[0][0]["body"] = "mutated"
        self.assertNotEqual(first, gen.generate_corpus())
        self.assertEqual(random.getstate(), state)

    def test_main_creates_nested_directory_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "nested/data"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gen.main(out), 0)
                self.assertEqual(gen.main(out), 0)
            for name, digest in zip(("corpus.json", "truth.json"), BASELINE):
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["corpus.json", "truth.json"])

    def test_atomic_failure_cleanup_and_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.json"
            path.write_text("old", encoding="utf-8")
            for bad in (float("nan"), float("inf"), float("-inf")):
                with self.assertRaises(ValueError):
                    gen.write_atomic(path, {"bad": bad})
            with patch.object(gen.os, "replace", side_effect=OSError("rename failed")):
                with self.assertRaises(OSError):
                    gen.write_atomic(path, {"new": 1})
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(directory).iterdir()), [path])
            gen.write_atomic(path, {"text": "é"}, indent=1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"text": "é"})

    def test_temp_write_failure_closes_and_removes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.json"
            real_factory = gen.tempfile.NamedTemporaryFile
            handles = []
            def failing_file(*args, **kwargs):
                handle = real_factory(*args, **kwargs)
                handles.append(handle)
                handle.write = lambda body: (_ for _ in ()).throw(OSError("write failed"))
                return handle
            with patch.object(gen.tempfile, "NamedTemporaryFile", failing_file):
                with self.assertRaises(OSError):
                    gen.write_atomic(path, {})
            self.assertTrue(all(handle.closed for handle in handles))
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
