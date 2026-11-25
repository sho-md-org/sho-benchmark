import concurrent.futures as cf
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

S1 = """You extract company state from records. For EACH record below, identify:
- commitments: a promise actually made to a customer, partner or another team about a feature, date or scope. Include informal and second-hand promises. EXCLUDE non-promises ("exploring", "on the roadmap, no commitment", "we'll consider", a competitor's promise). Fields: promiser, recipient, what, scope_details (specific capabilities promised, e.g. 'IdP-initiated login', 'SIEM/Splunk streaming', 'CSV export'), by_when (as written).
- decisions: a decision that sets, changes, cuts, rescopes, reverses or confirms the delivery date or scope of a product feature, or announces it shipped. Fields: date, decided_by, subject, aliases (codenames and plain names you can infer), what, effect (set|delay|cut|rescope|reverse|confirm|shipped), new_date, scope_removed.
- dependencies: a statement that feature X depends on / is built on / ships after feature Y. Fields: feature, depends_on.
Use the record id exactly. Return ONLY JSON: {"commitments":[{"record":..,...}],"decisions":[{"record":..,...}],"dependencies":[{"record":..,"feature":..,"depends_on":..}]}"""
S2 = """Below are commitments, product decisions and feature dependencies extracted from a company's records. Features may be named by codename or plain name; match them.
For EACH commitment decide its CURRENT state using the decisions about its feature, and decisions about any feature it depends on (a delay or cut of a dependency delays the dependent feature). Order decisions by date; a later 'reverse' restores the earlier plan. A 'rescope' that removes a capability affects only commitments whose scope_details include that capability; other commitments on the same feature are unaffected.
States: as_promised | changed (delayed or cut past the promised time) | partially_changed (a promised capability was removed) | fulfilled (shipped) .
Return ONLY JSON: {"links":[{"commitment_record":..,"affecting_decisions":[{"record":..,"date":..,"effect":..,"via_dependency":true|false}],"latest_decision_record":..|null,"current_state":..,"owner":"<person who owns the latest decision, or null>"}]} with one entry per commitment."""

def extract_json_object(text):
    if not isinstance(text, str):
        raise ValueError('model result must be text')
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            value, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError('model result contains no JSON object')


def call_model(prompt, model):
    env = {k: os.environ[k] for k in ('HOME', 'PATH', 'USER') if k in os.environ}
    env['LANG'] = 'en_US.UTF-8'
    out = subprocess.run(['claude', '-p', prompt, '--model', model,
                          '--output-format', 'json', '--tools', '', '--strict-mcp-config',
                          '--setting-sources', '', '--no-session-persistence'],
                         capture_output=True, text=True, env=env, timeout=590)
    if out.returncode != 0:
        raise ValueError(f'model subprocess exited with status {out.returncode}')
    envelope = json.loads(out.stdout)
    if not isinstance(envelope, dict):
        raise ValueError('model envelope must be an object')
    return extract_json_object(envelope.get('result'))


def validate(value, fields):
    if not isinstance(value, dict) or any(not isinstance(value.get(k), list) for k in fields):
        raise ValueError('model response requires lists: ' + ', '.join(fields))
    return value


def write_atomic(path, value):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.extract-', delete=False) as f:
            temporary = f.name
            json.dump(value, f, indent=1, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def run_extract(corpus_path='data/corpus.json', output_path='data/model-stage1.json'):
    with open(corpus_path, encoding='utf-8') as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise ValueError('corpus must be a list')
    fields = ('commitments', 'decisions', 'dependencies')

    def stage1(batch):
        retry_log = []
        body = "\n\n".join(f"[{r['id']}] {r['title']} ({r['tool']}, {r['date']})\n{r['body']}" for r in batch)
        for _ in (1, 2):
            try:
                return validate(call_model(S1 + "\n\nRECORDS:\n" + body, 'sonnet'), fields), retry_log
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                retry_log.append(f'stage1 retry: {error}')
        return dict(commitments=[], decisions=[], dependencies=[], error=True), retry_log

    batches = [records[i:i+50] for i in range(0, len(records), 50)]
    with cf.ThreadPoolExecutor(12) as ex:
        results = list(ex.map(stage1, batches))
    parts = [part for part, _ in results]
    log = [entry for _, entries in results for entry in entries]
    C, D, P = ([entry for part in parts for entry in part[key]] for key in fields)
    links = {'links': []}
    for _ in (1, 2):
        try:
            links = validate(call_model(S2 + "\n\nCOMMITMENTS:\n" + json.dumps(C)
                             + "\n\nDECISIONS:\n" + json.dumps(D)
                             + "\n\nDEPENDENCIES:\n" + json.dumps(P), 'opus'), ('links',))
            break
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            log.append(f'stage2 retry: {error}')
    result = {'extractor': {'stage1_model': 'sonnet', 'stage2_model': 'opus',
                           'S1': S1, 'S2': S2, 'batch': 50},
              'commitments': C, 'decisions': D, 'dependencies': P,
              'links': links['links'], 'errors': sum(1 for p in parts if p.get('error')), 'log': log}
    write_atomic(output_path, result)
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args:
        print('usage: extract.py', file=sys.stderr)
        return 2
    try:
        result = run_extract()
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f'extract: {error}', file=sys.stderr)
        return 1
    print('commitments', len(result['commitments']), 'decisions', len(result['decisions']),
          'dependencies', len(result['dependencies']), 'links', len(result['links']),
          'stage1 errors', result['errors'], 'log', result['log'][:3])
    return 0


if __name__ == '__main__':
    sys.exit(main())
