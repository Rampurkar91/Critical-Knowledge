# Testing and measured evaluation

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm ci && npm run build
```

## Unit and integration tests

```bash
.venv/bin/python -m pytest -q
```

Current measured result: **11 passed, 0 failed** (`reports/pytest-output.txt`).
Tests are split into:

- `tests/unit/test_extractor.py` — exact evidence offsets, gold extraction labels, unsupported marker, restricted source/canary, supersession and conflict keys.
- `tests/unit/test_verification.py` — outdated/unsupported/conflict detection, restricted graph classification, ABAC query filtering and restricted-phrase guard.
- `tests/integration/test_api_workflow.py` — complete 10-stage API workflow, role switching, no-leak assertions across graph/search/ask/claims/tasks/handover/export, acknowledgement/completion, audit chain, member management and external-user denial.

The integration test uses a disposable SQLite database and `fastapi.testclient`.
No live LLM, GitHub or PostgreSQL service is required.

## Measured evaluation

```bash
.venv/bin/python reports/generate_evaluation.py
```

This writes:

- `reports/EVALUATION_REPORT.md` — human-readable measured report.
- `reports/evaluation.json` — machine-readable metrics.

It creates a fresh database, seeds the labelled synthetic dataset, exercises the
API, runs the test suite, and computes precision/recall/F1 against
`sample_data/gold_labels.json`. It reports what is **not** measured rather than
inventing human-study outcomes.

Headline measured values from the latest run:

| Metric | Result |
| --- | ---: |
| Test suite | 11 passed / 0 failed |
| Extraction label precision / recall / F1 | 1.0 / 1.0 / 1.0 |
| Exact evidence-offset accuracy | 1.0 (93/93 spans) |
| Retrieval mean precision@5 / recall@5 | 0.44 / 1.0 |
| Conflict / outdated / unsupported F1 | 1.0 / 1.0 / 1.0 |
| Dependency-pair F1 | 1.0 (24/24) |
| Representative gold-edge recall | 1.0 (12/12) |
| Restricted marker leaks across 9 low-clearance channels | 0 |
| Audit hash-chain continuity | valid |

Reliability/retrieval scores are explainable heuristics, not statistically
calibrated probabilities. Human correction rate and handover preparation time are
workflow telemetry, not human-factors results. Incoming-member task understanding
is explicitly **not measured**.

## Optional integration smoke test

```bash
.venv/bin/python reports/exercise_optional_integrations.py
```

This writes `reports/OPTIONAL_INTEGRATIONS.md` and
`reports/optional_integrations.json`. It uses a disposable SQLite database and a
local `127.0.0.1` mock server for both GitHub and an OpenAI-compatible LLM. It
exercises text-source creation, file upload, GitHub connect, re-extraction and a
grounded `ask` call. Measured result: 3 mock GitHub sources created, 15
authorised sources after ingestion, 5 authorised LLM citations, 0 external API
calls. No real token, repository or model endpoint is contacted.

## Frontend and browser checks

```bash
cd frontend
npm ci
npm run build

cd ../tools/browser
npm ci
npm run check:routes
npm run capture             # regenerates real UI screenshots
```

The production build completed successfully with a >500 kB chunk warning. The
browser route check visits all 17 documented routes with public, manager,
incoming-engineer and incoming-analyst sessions. Latest measured result:
**17 routes, 0 runtime errors, 0 failed API responses** (`reports/UI_ROUTE_CHECK.md` and `reports/ui_route_check.json`).

`npm run capture` writes real PNG screenshots and `capture-manifest.json` into
`docs/screenshots/`. These are rendered from the running app in headless
Chromium, not generated mockups. `KB_SCREENSHOTS=... npm run capture` refreshes
selected files; `KB_MANIFEST_ONLY=1 npm run capture` regenerates the static
manifest after a split capture.

GitHub Actions runs unit/integration tests, the measured evaluation, the
optional local-mock integration exercise and the frontend production build on
each push/PR. Browser screenshot capture is a local documentation step, not a
CI gate.
