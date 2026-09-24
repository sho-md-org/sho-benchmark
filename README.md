# sho benchmark

This is the test behind the numbers on [sho.md](https://sho.md/method). It asks one question: when a company changes a promise in a place some people can't see, does an AI agent keep repeating the old promise? And does sho stop it without leaking what changed?

Everything here runs on **Brightline**, a fictional B2B software company. Every person, customer and record in it is made up.

## What's inside

| Path | What it is |
|---|---|
| `data/corpus.json` | About 3,000 records across Notion, Slack, Linear, a CRM and meeting notes, each tagged with who can see it |
| `data/truth.json` | The hidden ground truth: the promises, the decisions that changed them, and canary words |
| `data/cells.json` | The test questions (cells): renewal briefs, sales replies, probes and adversarial asks |
| `data/model.json` | sho's promise model, extracted once from the raw records and then frozen |
| `generate/` | The scripts that generated the company and extracted the model |
| `server/mcp.mjs` | The test server. Arm 1 is an ordinary agent that searches tools with the person's own access. Arm 4 is an agent that also asks sho |
| `run.sh` | Runs one agent run. `SCOPE=feature` gives round 13, `SCOPE=promise` gives round 15 |
| `grade.py`, `summarize.py` | Blind AI grading against written criteria, and the summary table |
| `rounds/` | Two recorded rounds: the pre-registration and its hash, results, leak review, judge outputs and every agent answer |

## How a round works

1. Write down the pass bars and hash them **before** any run (`PREREGISTRATION.md`, `PREREG.sha256`).
2. Ask each question 10 times to an ordinary agent (arm 1) and to an agent with sho (arm 4). Opus runs the agents.
3. Have a blind AI judge (Opus) grade every answer against the rubric in `grade.py`.
4. Have a second model (Sonnet) re-grade every flagged answer plus a random 20% sample.
5. Have a person review every possible leak.
6. Report each bar as pass or fail. Bars are never moved afterwards.

## Results, including what failed

| Round | Design | False alarms (bar: at most 4 of 40) | Changed promises handled safely | Leaks beyond an ordinary agent |
|---|---|---|---|---|
| 13 | Notice on every promise on an affected feature | 6 of 40, **fail** | 20 of 20, pass | none, pass |
| 15 | Notice only on the promise that changed | 1 of 40, pass | 20 of 20, pass | comparison probe 10 of 10 vs 6 of 10, **fail**, not shipped |

Earlier rounds (10 and 11) produced the scale figures quoted on sho.md: 40 promises in 3,000 records, and 56 of 60 safe with sho vs 3 of 60 without. Round numbers are our internal names for each run of the benchmark. They appear inside the pre-registrations, which are published byte-identical so their hashes still verify.

## Rerun it

```bash
npm install                                        # @modelcontextprotocol/sdk and zod
SCOPE=promise ./run.sh 4 P13 1                     # one run: arm 4, cell P13, run 1
python3 grade.py opus grading-local                # grade everything in runs/
python3 summarize.py grading-local
```

You need the `claude` CLI, signed in. Runs cost model usage. Expect small run-to-run differences.

## What this doesn't show

- The company and its data are fictional. Real records are messier.
- The 40 scale-test promises were written from templates, so they're easier to find than real ones.
- AI models graded the answers, not people. A second model and a human leak review check them.
- It is not a customer result.
