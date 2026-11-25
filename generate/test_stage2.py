import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def load():
    spec = importlib.util.spec_from_file_location('stage2', Path(__file__).with_name('stage2.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage2 = load()
MODEL = {'commitments': [], 'decisions': [], 'dependencies': []}


def response(result='{"links": []}', code=0):
    return subprocess.CompletedProcess([], code, json.dumps({'result': result}), '')


class Stage2Tests(unittest.TestCase):
    def test_import_has_no_io_or_subprocess_effects_and_missing_env(self):
        with patch.dict(os.environ, {}, clear=True), patch('builtins.open', side_effect=AssertionError), patch('subprocess.run', side_effect=AssertionError), patch('os.replace', side_effect=AssertionError):
            module = load()
        self.assertEqual(module.ENV, {'HOME': '', 'PATH': '', 'USER': '', 'LANG': 'en_US.UTF-8'})

    def test_balanced_json(self):
        obj = {'links': [{'text': 'brace } and { with "quotes"', 'nested': {'a': 1}}]}
        for text in [json.dumps(obj), '```json\n' + json.dumps(obj) + '\n```', 'prose ' + json.dumps(obj) + ' {"other": 1}']:
            self.assertEqual(stage2.extract_json_object(text), obj)
        for text in [None, [], 'no json', '{invalid']:
            with self.assertRaises(ValueError):
                stage2.extract_json_object(text)

    def test_success_schema_and_command(self):
        with patch.object(stage2.subprocess, 'run', return_value=response()) as run:
            result = stage2.run_stage2(MODEL)
        self.assertEqual(set(result), {'extractor', 'commitments', 'decisions', 'dependencies', 'links', 'log'})
        self.assertEqual(result['links'], [])
        self.assertEqual(result['log'], [])
        self.assertEqual(result['extractor']['S2'], stage2.S2)
        self.assertIn('COMMITMENTS:\n[]', run.call_args.args[0][2])
        self.assertEqual(run.call_args.kwargs['timeout'], 590)

    def test_retry_and_rejected_responses(self):
        bad = [response(code=1), response('null'), response('{"links": null}'), response('{"links": {}}'), response('{}'), response('{"links": "bad"}'), subprocess.CompletedProcess([], 0, 'invalid', ''), subprocess.TimeoutExpired('mock', 590), OSError('mock')]
        for first in bad:
            with self.subTest(first=first), patch.object(stage2.subprocess, 'run', side_effect=[first, response()]) as run:
                result = stage2.run_stage2(MODEL)
                self.assertEqual(len(result['log']), 1)
                self.assertEqual(run.call_count, 2)

    def test_failure_does_not_write_model(self):
        with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(MODEL))), patch.object(stage2.subprocess, 'run', return_value=response(code=2)) as run, patch.object(stage2, 'write_atomic') as write:
            with self.assertRaises(RuntimeError):
                stage2.main()
            self.assertEqual(run.call_count, 2)
            write.assert_not_called()

    def test_main_success(self):
        with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(MODEL))) as opened, patch.object(stage2.subprocess, 'run', return_value=response()), patch.object(stage2, 'write_atomic') as write, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(stage2.main(), 0)
            opened.assert_called_once_with('data/model-stage1.json', encoding='utf-8')
            self.assertEqual(write.call_args.args[0], 'data/model.json')
            self.assertEqual(write.call_args.args[1]['links'], [])

    def test_atomic_cleanup_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.json'
            path.write_text('original', encoding='utf-8')
            for bad in [float('nan'), float('inf'), object()]:
                with self.assertRaises((ValueError, TypeError)):
                    stage2.write_atomic(path, bad)
                self.assertEqual(path.read_text(), 'original')
                self.assertEqual(list(Path(directory).iterdir()), [path])
            for operation in ['fdopen', 'replace']:
                with patch.object(stage2.os, operation, side_effect=OSError('mock')):
                    with self.assertRaises(OSError):
                        stage2.write_atomic(path, {'links': []})
                self.assertEqual(path.read_text(), 'original')
                self.assertEqual(list(Path(directory).iterdir()), [path])
            stage2.write_atomic(path, {'links': ['é']})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'links': ['é']})


if __name__ == '__main__':
    unittest.main()
