# KnowledgeBridge synthetic demonstration dataset

**All records in this folder are synthetic demonstration data.** Names, repositories,
vendors, credentials and URLs are invented for the hackathon walkthrough. No real
customer documents, API keys, passwords or confidential material are included.

The structured `@record` lines are intentionally explicit: they make the extraction,
citation offsets, conflict detection and evaluation reproducible without requiring
an external LLM or API key. Each source file has front matter with its own
classification level. The backend reads `manifest.json` to seed the sources and
`gold_labels.json` provides expected annotations for the measured evaluation.

Measured inventory from `gold_labels.json` and the seeded database:

| Condition | Records |
| --- | --- |
| 15 tasks | `KB-101` … `KB-114`, `KB-900` |
| 9 historical decisions | `DEC-001` … `DEC-008`, `DEC-900` |
| 7 risks / 2 blockers | `RISK-001` … `RISK-006`, `RISK-900`, `BLK-001`, `BLK-002` |
| 24 explicit dependency pairs | recorded `depends_on` fields |
| 2 conflicting pairs | `task.KB-104.owner`, `api.rate_limit` |
| 2 outdated records | `DEC-001` superseded by `DEC-006`; `RISK-002` superseded by `RISK-005` |
| 1 unsupported claim | `F-301` (`unsupported=true`) |
| 5 unfinished-work records | `UF-001` … `UF-005` |
| 7 unresolved questions | `Q-001` … `Q-005`, `GH-201`, `GH-202` |
| 6 next actions | `NA-001` … `NA-006` |
| 4 contacts | `C-001` … `C-004` |
| Restricted canary | `RESTRICTED-CANARY-9F3A` in `09-restricted-security-review.md` |
| Different roles / clearances | manager 3, technical lead 2, engineer 1, analyst 0, auditor 2 |

`gold_labels.json` contains **expected labels, not measured outcomes**. Actual test
and evaluation results are written to `reports/EVALUATION_REPORT.md` and
`reports/evaluation.json` by `reports/generate_evaluation.py`.
