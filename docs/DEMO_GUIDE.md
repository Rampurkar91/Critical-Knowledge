# KnowledgeBridge hackathon demo guide

This guide demonstrates the 11 required steps with the synthetic Atlas Migration
dataset. Every record is **demonstration data**; no real credentials, customer
records or private documents are included.

## Before you start

```bash
cp .env.example .env
# optional: edit DEMO_PASSWORD / JWT_SECRET for your local demo
.venv/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# in another terminal
cd frontend && npm run dev -- --host 0.0.0.0 --port 5173
```

Open `http://localhost:5173`. If the SQLite demo DB already exists and you want
a clean run, stop the API, delete `database/knowledgebridge.db`, and restart with
`SEED_DEMO_DATA=true`.

Demo accounts (default password `DemoPass!2026`):

| Role | Email | Clearance |
| --- | --- | ---: |
| Manager | `manager@knowledgebridge.demo` | 3 |
| Technical lead | `lead@knowledgebridge.demo` | 2 |
| Incoming engineer | `engineer@knowledgebridge.demo` | 1 |
| Incoming analyst | `analyst@knowledgebridge.demo` | 0 |
| Auditor | `auditor@knowledgebridge.demo` | 2 |

## 11-step walkthrough

1. **Upload / inspect docs.** Log in as manager. Open **Source Integration**. The 10 seeded synthetic sources are already present; use **Add text source** or **Upload** to add a labelled Markdown/text document. Click a source to see its classification, SHA-256 and evidence metadata.
2. **Extract knowledge.** Open **Project Workspace** → **Run extraction**, or `POST /api/projects/{project_id}/extract`. The deterministic extractor creates exact-offset evidence spans, claims, tasks, risks and dependency claims. No LLM key is required.
3. **Reconstruct graph.** Open **Graph Explorer**. Use the as-of timeline to move from July to November 2026; filter by node type; pan/zoom; click a decision node to open its original evidence quote and permitted edges.
4. **Explore decisions.** Open **Decision History**. Show `DEC-001` → `DEC-006` supersession, decision reasons (`why`), owners, dependencies and `valid_to` state changes.
5. **Identify conflicts and outdated information.** Open **Conflict Dashboard** and **Verification Dashboard**. The two deliberate conflicts are `task.KB-104.owner` and `api.rate_limit`; outdated records are `DEC-001` and `RISK-002`; the unsupported claim is `F-301`.
6. **Inspect evidence.** In **Verification Dashboard**, open a claim. Each statement links to its source ref, exact quote and character offsets. Explain the heuristic score note: it is not a calibrated probability.
7. **Review / correct / approve.** Open **Review Centre**. Use bulk **Approve eligible**, then resolve each open conflict by selecting the newer primary-source claim. Use **Correct** on a claim to create a versioned replacement with copied evidence; show the review history.
8. **Generate actionable handover.** Open **Handover Report**. Generate for `engineer@knowledgebridge.demo`. Confirm the eight sections, exactly five priority next actions, checklist, evidence register and uncertainty fields. Edit the draft as manager, then **Approve** and **Share**. Export Markdown and show each statement's citation.
9. **Switch to incoming-member account.** Log out, log in as `engineer@knowledgebridge.demo`. Open **Incoming Dashboard** and **Handover Report**. Confirm only the recipient's shared handover is visible and the clearance is `internal`.
10. **Verify restricted information is inaccessible.** As engineer, open **Graph Explorer**, search for `RESTRICTED-CANARY-9F3A`, and ask the AI panel about the restricted production key path. The restricted source `SRC-009`, decision `DEC-900`, fact `F-900`, task `KB-900`, risk `RISK-900` and canary must not appear in graph nodes/edges, search results, AI citations, claims, tasks, handover or export. The UI shows hidden-by-policy counters instead of hidden content. Log in as analyst to show even stricter public-clearance filtering.
11. **Display personalised next actions and continue.** On the incoming dashboard, show `NA-001`, `NA-002`, `NA-003`, `NA-006`, `NA-005`, acknowledge an item, start it, complete it, then open **Continuity Dashboard** to show measured acknowledgement/completion rates, overdue items, open questions and the audit trail.

Optional final checks:

- Log in as `auditor@knowledgebridge.demo` and open **Audit History** to show the hash-chain continuity indicator and ingestion/review/share/export events.
- Log in as manager and open **Access Management** to change a member's clearance, claim types or tags; repeat step 10 to show the new policy taking effect.
- Open `/docs` for the interactive OpenAPI reference.
- Run `.venv/bin/python reports/exercise_optional_integrations.py` to exercise optional upload, GitHub and OpenAI-compatible LLM paths against local mocks (no external API calls); see `reports/OPTIONAL_INTEGRATIONS.md`.
- Run `cd tools/browser && npm run check:routes` to validate all 17 UI routes; see `reports/ui_route_check.json`.

## API-only demonstration

```bash
# Login
curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"manager@knowledgebridge.demo","password":"DemoPass!2026"}'

# Then use the returned bearer token; see docs/API.md for endpoints.
```

## Reset and troubleshooting

- **Reset demo:** stop API, `rm -f database/knowledgebridge.db`, restart with `SEED_DEMO_DATA=true`.
- **Frontend cannot reach API:** ensure backend is on port 8000; Vite proxies `/api`, `/docs`, `/openapi.json` to `127.0.0.1:8000`.
- **No LLM configured:** expected. The app uses deterministic extraction and extractive answers; set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` only if you want the optional grounded adapter.
- **No GitHub token:** expected. Seeded synthetic GitHub activity is available; the optional live adapter is read-only.
- **Do not commit `.env`:** it is gitignored; `.env.example` is the safe template.

## Screenshot checklist

Capture real UI screenshots into `docs/screenshots/`:

1. `landing.png`
2. `dashboard.png`
3. `graph.png`
4. `verification.png`
5. `handover.png`
6. `incoming.png`
