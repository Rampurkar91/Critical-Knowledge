# KnowledgeBridge — measured evaluation report

Generated: 2026-11-09T08:55:24Z

## Scope and honesty statement

This report contains **actual measurements** from a fresh disposable SQLite database seeded with the labelled synthetic Atlas Migration demonstration dataset. It is not a claim of production accuracy or worldwide novelty. The official attached PDF was not present in the workspace, so no PDF-specific findings were invented. No live LLM, GitHub, PostgreSQL, FAISS/ChromaDB or human-subject evaluation was performed.

Reliability and retrieval values are explainable heuristics, **not statistically calibrated probabilities**. Gold labels are hand-authored expected annotations for the synthetic dataset, not measured outcomes.

## Test suite

- Command: `.venv/bin/python -m pytest -q`
- Result: **11 passed, 0 failed**, exit code 0.
- Output tail: `...........                                                              [100%]
11 passed in 9.71s`

## Extraction and evidence

| Metric | Measured value |
| --- | ---: |
| Expected non-dependency labels | 70 |
| Actual non-dependency claims | 70 |
| Derived dependency claims | 24 |
| Extraction label precision | 1.0000 |
| Extraction label recall | 1.0000 |
| Extraction label F1 | 1.0000 |
| Evidence spans | 93 |
| Exact character-offset matches | 93 |
| Exact evidence-offset accuracy | 1.0000 |
| Active claims | 94 |
| Claims with evidence links | 93 |

Extraction precision uses active non-dependency claims because dependency claims are deterministically derived from `depends_on` fields and are evaluated separately below.

Restricted-query note: A lexical match on the generic word 'restricted' may return an authorised internal document; the exact canary and hidden identifiers must not appear in its payload. Returned source refs: `[]`.

## Retrieval, verification and graph

| Metric | Measured value |
| --- | ---: |
| Retrieval queries | 5 |
| Mean precision@5 | 0.4400 |
| Mean recall@5 | 1.0000 |
| Restricted-query authorised documents returned to engineer | 0 (marker hits: 0) |
| Conflict precision / recall / F1 | 1.0000 / 1.0000 / 1.0000 |
| Outdated precision / recall / F1 | 1.0000 / 1.0000 / 1.0000 |
| Unsupported precision / recall / F1 | 1.0000 / 1.0000 / 1.0000 |
| Unsupported claim rate | 0.0106 |
| Dependency-pair F1 | 1.0000 |
| Graph nodes / edges | 120 / 210 |
| `depends_on` edges | 24 |
| Representative gold-edge recall | 1.0000 |
| Restricted nodes / edges in graph | 9 / 23 |
| Score disclaimer on every claim | True |

Verification status counts: `{"Conflicting": 4, "Needs Review": 87, "Outdated": 2, "Unsupported": 1}`.

Graph relationship counts: `{"assigned_to": 15, "blocks": 2, "decided_by": 9, "depends_on": 24, "owned_by": 51, "supersedes": 2, "supported_by": 93, "supported_by_reason": 9, "tracks": 5}`.

The representative gold edge set is a 12-edge subset used as a regression check; `all_edge_exact_match_rate` is reported in JSON but is **not** a precision estimate because the gold set is not exhaustive.

## Handover quality and continuation

| Metric | Measured value |
| --- | ---: |
| Required sections present | 8/8 (1.0000) |
| Statement items with evidence | 35/35 (1.0000) |
| Evidence register entries | 57 |
| Next actions / checklist items | 5 / 14 |
| Recommendation precision / recall / F1 | 1.0000 / 1.0000 / 1.0000 |
| Exact priority-order match | True |
| Acknowledgement rate after workflow | 0.0714 |
| Completion rate after workflow | 0.0714 |
| Handover preparation time (average / maximum) | 3.0s / 3s |
| Human correction rate | 0.0000 (0/89 automated review events) |
| Incoming-member task understanding | **Not measured** — Requires a human-in-the-loop study with incoming members; no value is invented. |

Handover preparation time is elapsed wall-clock seconds from the first source ingestion timestamp to generation in this automated run. It is **not** a measured reduction in human preparation time. Human correction rate is computed from recorded review events and is not a human-factors study.

## Permission enforcement

| Check | Measured value |
| --- | ---: |
| Low-clearance channels tested | 9 |
| Restricted marker leaks | 0 |
| Engineer hidden nodes / edges | 31 / 87 |
| Analyst hidden nodes / edges | 113 / 202 |
| Manager can see restricted graph | True |
| Search query guard applied | True |
| Ask question guard applied | False |
| Permission-guard audit events | 4 |
| Denied audit events | 1 |
| Engineer approve attempt status | 403 |
| External project access status | 404 |
| Audit hash-chain continuity valid | True |

Per-channel restricted-marker hits: `{"analyst_graph": [], "engineer_ask": [], "engineer_claims": [], "engineer_export": [], "engineer_graph": [], "engineer_handover": [], "engineer_search": [], "engineer_tasks": [], "manager_export": []}`.

## What is not measured

- Incoming-member task understanding: requires a human-subject study.
- Real reduction in handover preparation time: requires comparison against a manual baseline.
- Neural/LLM extraction accuracy: no live LLM was configured; deterministic extraction was measured.
- PostgreSQL, FAISS/ChromaDB, live GitHub and cloud deployment behaviour: not exercised in this evaluation.
- Production security/penetration testing: automated policy checks only.
- PDF analysis: the official attached PDF was not present in the workspace.

Separate runtime smoke checks are documented in `reports/OPTIONAL_INTEGRATIONS.md`
(local mock GitHub/LLM adapters, 0 external API calls) and
`reports/UI_ROUTE_CHECK.md` / `reports/ui_route_check.json` (17 UI routes,
0 runtime errors/failed API responses). They are implementation checks and
do not change the measured metrics above; no live external service was evaluated.

## Reproduce

```bash
.venv/bin/python -m pytest -q
.venv/bin/python reports/generate_evaluation.py
```

Machine-readable results: `reports/evaluation.json`.
