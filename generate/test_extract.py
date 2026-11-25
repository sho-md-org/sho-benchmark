import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('extract.py')
spec = importlib.util.spec_from_file_location('extract_under_test', SOURCE)
module = importlib.util.module_from_spec(spec)
with mock.patch('subprocess.run', side_effect=AssertionError('live subprocess forbidden')):
    spec.loader.exec_module(module)


class ExtractTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(module.subprocess, 'run', side_effect=AssertionError('unmocked model call'))
        self.run = patcher.start()
        self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root / 'corpus.json'
        self.output = self.root / 'model-stage1.json'
        self.corpus.write_text(json.dumps([dict(id='r', title='Title', tool='mail', date='today', body='Hello')]))

    def response(self, value):
        return subprocess.CompletedProcess([], 0, json.dumps({'result': json.dumps(value)}), '')

    def extract(self):
        return module.run_extract(self.corpus, self.output)

    def test_import_safe(self):
        with mock.patch('builtins.open', side_effect=AssertionError('read')), \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            spec.loader.exec_module(module)
        self.run.assert_not_called()
        self.assertEqual(stdout.getvalue(), '')

    def test_balanced_json(self):
        value = {'a': {'b': '} escaped " {'}, 'array': [1, 2]}
        self.assertEqual(module.extract_json_object('```json\n' + json.dumps(value) + '\n``` {"second":1}'), value)
        self.assertEqual(module.extract_json_object('noise {bad} {"valid":true}'), {'valid': True})
        for value in [None, '', 'not json', '[]']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.extract_json_object(value)

    def test_call_environment_and_exit(self):
        self.run.side_effect = None
        self.run.return_value = self.response({'links': []})
        with mock.patch.dict(module.os.environ, {}, clear=True):
            self.assertEqual(module.call_model('prompt', 'opus'), {'links': []})
        self.assertEqual(self.run.call_args.kwargs['env'], {'LANG': 'en_US.UTF-8'})
        self.assertEqual(self.run.call_args.kwargs['timeout'], 590)
        self.run.return_value = subprocess.CompletedProcess([], 1, 'not json', 'private stderr')
        with self.assertRaisesRegex(ValueError, 'status 1'):
            module.call_model('prompt', 'sonnet')

    def test_invalid_envelopes(self):
        self.run.side_effect = None
        for raw in ['bad', '[]', '{}', '{"result":null}']:
            self.run.return_value = subprocess.CompletedProcess([], 0, raw, '')
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                module.call_model('prompt', 'sonnet')

    def test_success_schema_and_prompt(self):
        stage1 = dict(commitments=[{'record': 'r'}], decisions=[], dependencies=[])
        self.run.side_effect = [self.response(stage1), self.response({'links': [{'commitment_record': 'r'}]})]
        result = self.extract()
        self.assertEqual(result['commitments'], stage1['commitments'])
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['log'], [])
        self.assertEqual(json.loads(self.output.read_text()), result)
        self.assertEqual(set(result), {'extractor', 'commitments', 'decisions', 'dependencies', 'links', 'errors', 'log'})
        self.assertIn(module.S1 + '\n\nRECORDS:\n[r] Title (mail, today)\nHello', self.run.call_args_list[0].args[0])

    def test_stage_validation_and_retry(self):
        self.run.side_effect = [self.response({'commitments': None}),
                               self.response(dict(commitments=[], decisions=[], dependencies=[])),
                               self.response({'links': {}}), self.response({'links': []})]
        result = self.extract()
        self.assertEqual(result['errors'], 0)
        self.assertEqual(len(result['log']), 2)
        for field in ['commitments', 'decisions', 'dependencies']:
            value = dict(commitments=[], decisions=[], dependencies=[])
            value[field] = {}
            with self.assertRaises(ValueError):
                module.validate(value, ('commitments', 'decisions', 'dependencies'))

    def test_subprocess_failures_exhaust_retries(self):
        self.run.side_effect = [OSError('missing'), subprocess.TimeoutExpired('mock', 590),
                               self.response({'links': None}), self.response({})]
        result = self.extract()
        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['links'], [])
        self.assertEqual(len(result['log']), 4)

    def test_parallel_logs_are_complete_and_ordered(self):
        rows = [dict(id=str(i), title='T', tool='mail', date='D', body='B') for i in range(650)]
        self.corpus.write_text(json.dumps(rows))
        def failure(args, **kwargs):
            raise OSError(args[2].split('RECORDS:\n')[-1].split('\n')[0])
        self.run.side_effect = failure
        result = self.extract()
        self.assertEqual(result['errors'], 13)
        self.assertEqual(len(result['log']), 28)
        for i in range(13):
            self.assertIn(f'[{i * 50}]', result['log'][i * 2])

    def test_atomic_failures(self):
        self.output.write_text('old')
        for value in [{'number': float('nan')}, {'number': float('inf')}]:
            with self.assertRaises(ValueError):
                module.write_atomic(self.output, value)
            self.assertEqual(self.output.read_text(), 'old')
            self.assertEqual(list(self.root.glob('.extract-*')), [])
        with mock.patch.object(module.os, 'replace', side_effect=OSError('rename')):
            with self.assertRaises(OSError):
                module.write_atomic(self.output, {})
        self.assertEqual(self.output.read_text(), 'old')
        self.assertEqual(list(self.root.glob('.extract-*')), [])

    def test_main_errors_and_output(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(module.main(['extra']), 2)
            with mock.patch.object(module, 'run_extract', side_effect=ValueError('bad JSON')):
                self.assertEqual(module.main([]), 1)
        self.assertIn('bad JSON', stderr.getvalue())
        with mock.patch.object(module, 'run_extract', return_value=dict(commitments=[], decisions=[], dependencies=[], links=[], errors=0, log=[])), contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(module.main([]), 0)
        self.assertEqual(stdout.getvalue(), 'commitments 0 decisions 0 dependencies 0 links 0 stage1 errors 0 log []\n')
        self.run.assert_not_called()

    def test_write_failure_cleanup(self):
        real = module.tempfile.NamedTemporaryFile
        def failing(*args, **kwargs):
            f = real(*args, **kwargs)
            f.write = mock.Mock(side_effect=OSError('disk full'))
            return f
        with mock.patch.object(module.tempfile, 'NamedTemporaryFile', side_effect=failing):
            with self.assertRaises(OSError):
                module.write_atomic(self.output, {'ok': True})
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.extract-*')), [])

    def test_invalid_corpus_never_calls_model(self):
        for raw in ['{', '{}']:
            self.corpus.write_text(raw)
            with self.assertRaises(ValueError):
                self.extract()
        self.corpus.write_bytes(b'\xff')
        with self.assertRaises(UnicodeDecodeError):
            self.extract()
        with self.assertRaises(OSError):
            module.run_extract(self.root / 'missing', self.output)
        self.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
