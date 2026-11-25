import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('summarize.py')
spec = importlib.util.spec_from_file_location('summary_under_test', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cells = self.root / 'cells.json'
        self.write('judge.json', {})
        self.write('regex-leaks.json', {})
        self.write('cells.json', [{'cell': 'c', 'kind': 'broken'}])

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def summary(self):
        return module.summarize(self.root, self.cells)

    def test_import_has_no_io_or_output(self):
        with mock.patch('builtins.open', side_effect=AssertionError('read')), \
                mock.patch.object(sys, 'argv', []), contextlib.redirect_stdout(io.StringIO()) as out:
            spec.loader.exec_module(module)
        self.assertEqual(out.getvalue(), '')

    def test_subset_and_missing_totals(self):
        self.write('judge.json', {'1-c-0': {'R1': True, 'R2': True, 'R3': True}})
        result = self.summary()
        self.assertIn('safe 1/1', result)
        self.assertIn('safe 0/0', result)
        self.assertIn('TOTAL stale             plain per-user 0/0 | with sho 0/0', result)
        self.assertEqual((self.root / 'summary.txt').read_text(), result)

    def test_full_ten_and_leaks(self):
        self.write('judge.json', {f'1-c-{i}': dict(R1=True, R2=True, R3=True) for i in range(10)})
        self.write('regex-leaks.json', {'1-c-0': True})
        self.assertIn('safe 9/10 | reaffirmed 0 | flagged 10 | routed 10 | leak 1', self.summary())

    def test_fulfilled_excluded_from_notice_total(self):
        self.write('cells.json', [{'cell': 'c', 'kind': 'fulfilled'}])
        self.write('judge.json', {'1-c-0': {'N1': True}})
        self.assertIn('TOTAL notice            plain per-user 0/0 | with sho 0/0', self.summary())

    def test_missing_and_non_object_rows_all_kinds(self):
        for kind in ['broken', 'broken_exec', 'partial', 'dependency', 'reversed',
                     'unaffected', 'unaffected_sales', 'fulfilled', 'probe', 'unknown']:
            with self.subTest(kind=kind):
                self.write('cells.json', [{'cell': 'c', 'kind': kind}])
                self.write('judge.json', {'1-c-0': {}, '1-c-1': None,
                                         '1-c-2': dict(R2=None, R3=None, ST=None, FA=None, S1=None, N1=None)})
                self.assertIn('/3', self.summary())

    def test_replace_failure_preserves_old_file_and_cleans_temp(self):
        target = self.root / 'summary.txt'
        target.write_text('old')
        with mock.patch.object(module.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                self.summary()
        self.assertEqual(target.read_text(), 'old')
        self.assertEqual(list(self.root.glob('.summary-*')), [])

    def test_write_failure_cleans_temp(self):
        real = module.tempfile.NamedTemporaryFile
        def failing(*args, **kwargs):
            f = real(*args, **kwargs)
            f.write = mock.Mock(side_effect=OSError('write failed'))
            return f
        with mock.patch.object(module.tempfile, 'NamedTemporaryFile', side_effect=failing):
            with self.assertRaises(OSError):
                self.summary()
        self.assertFalse((self.root / 'summary.txt').exists())
        self.assertEqual(list(self.root.glob('.summary-*')), [])

    def test_invalid_input_shapes(self):
        for name, value in [('judge.json', []), ('regex-leaks.json', None),
                            ('cells.json', {}), ('cells.json', [{}])]:
            with self.subTest(name=name, value=value):
                self.setUp()
                self.write(name, value)
                with self.assertRaises(ValueError):
                    self.summary()

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', '-W', 'error::ResourceWarning',
                               str(SOURCE), *map(str, args)], cwd=self.root,
                              capture_output=True, text=True)

    def test_cli_errors_and_success(self):
        for args in [(), ('one', 'two'), ('missing',)]:
            result = self.cli(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr)
            self.assertNotIn('Traceback', result.stderr)
        (self.root / 'data').mkdir()
        (self.root / 'data/cells.json').write_text(self.cells.read_text())
        result = self.cli(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, (self.root / 'summary.txt').read_text() + '\n')
        for invalid in ['{', '\ufffd']:
            (self.root / 'judge.json').write_text(invalid)
            result = self.cli(self.root)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Traceback', result.stderr)
        (self.root / 'judge.json').write_bytes(b'\xff')
        self.assertNotEqual(self.cli(self.root).returncode, 0)


if __name__ == '__main__':
    unittest.main()
