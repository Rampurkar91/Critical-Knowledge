# Optional integration endpoint exercise

**Status:** PASS — all exercised endpoints returned HTTP 2xx and all assertions passed.

**Generated:** 2026-11-09T08:55:27.082657+00:00

This is an implementation smoke test, not a production-integration benchmark.
It used a disposable SQLite database, a **local mock GitHub API** and a **local
OpenAI-compatible LLM adapter** bound to `127.0.0.1`. It made **0 external API
calls** and used dummy local tokens only. No real repository, model endpoint,
API key or customer data was contacted.

| Optional path | Measured result |
| --- | --- |
| `POST /api/projects/{id}/sources/text` | HTTP 201; created `local://optional/text-source` |
| `POST /api/projects/{id}/sources/upload` | HTTP 201; created `local://optional/upload` |
| `POST /api/projects/{id}/sources/github/connect` | HTTP 200; `knowledgebridge/mock-repo` returned 3 sources, created 3 (0 duplicates) |
| `POST /api/projects/{id}/extract` | HTTP 200; reconstruction reran over the expanded source set |
| Authorised source count | 15 sources visible to the manager after ingestion |
| `POST /api/projects/{id}/ask` with LLM configured | HTTP 200; provider `openai-compatible:knowledgebridge-grounded-mock`, 5 authorised citations |
| Mock requests | 3 total; 2 GitHub; 1 LLM; all carried an Authorization header |
| LLM grounding | Mock request contained 5 authorised evidence entries; restricted-canary marker present: `false` |

The deterministic local answer path (`provider=deterministic-local`) is measured
separately in `reports/EVALUATION_REPORT.md`. This exercise verifies the optional
adapter branch and its fallback inputs: `ai_engine/llm.py` receives only evidence
already filtered by `ai_engine/retrieval.py` and `backend/app/services/permissions.py`.

Reproduce with:

```bash
.venv/bin/python reports/exercise_optional_integrations.py
```

Machine-readable results: `reports/optional_integrations.json`.
