# API documentation

Interactive OpenAPI documentation is served at `/docs` and `/openapi.json`.
All project endpoints require `Authorization: Bearer <JWT>` and active project
membership. Responses are permission-filtered before serialisation.

## Auth and metadata

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create user/organisation or add to an existing organisation. |
| `POST` | `/api/auth/login` | Issue JWT. |
| `GET` | `/api/auth/me` | Current user and project memberships. |
| `GET` | `/api/meta` | Role policies, status categories, sensitivity labels. |
| `GET/POST` | `/api/organizations` | List / create organisations. |
| `GET` | `/api/health`, `/api` | Health and API root. |

## Projects, members and dashboard

| Method | Path | Purpose |
| --- | --- | --- |
| `GET/POST` | `/api/projects` | List authorised projects / create project. |
| `GET/PATCH` | `/api/projects/{project_id}` | Project detail / update. |
| `GET` | `/api/projects/{project_id}/dashboard` | Dashboard workspace payload and statistics. |
| `GET/POST` | `/api/projects/{project_id}/members` | List / add project members. |
| `PATCH` | `/api/members/{member_id}` | Update role, clearance, allowlists. |

## Sources and extraction

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/projects/{project_id}/sources` | Authorised source list. |
| `GET` | `/api/sources/{source_id}/content` | Authorised source content. |
| `POST` | `/api/projects/{project_id}/sources/text` | Ingest structured text. |
| `POST` | `/api/projects/{project_id}/sources/upload` | Ingest UTF-8 text/PDF. |
| `POST` | `/api/projects/{project_id}/sources/github/connect` | Optional read-only GitHub activity ingestion. |
| `POST` | `/api/projects/{project_id}/extract` | Run extraction → graph → verification pipeline. |

## Knowledge, graph, search and AI

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/projects/{project_id}/claims` | Permission-filtered claims. |
| `GET` | `/api/claims/{claim_id}/evidence` | Claim detail with exact-offset evidence citations. |
| `GET` | `/api/evidence/{evidence_id}` | Single authorised evidence span and source excerpt. |
| `GET` | `/api/projects/{project_id}/graph` | Temporal graph with as-of date, hidden-policy counters. |
| `GET` | `/api/projects/{project_id}/graph/nodes/{node_id}` | Node evidence and permitted edges. |
| `GET` | `/api/projects/{project_id}/decisions`, `/timeline` | Decision history and state changes. |
| `GET` | `/api/projects/{project_id}/risks`, `/tasks` | Risks, blockers, dependencies, tasks. |
| `GET` | `/api/projects/{project_id}/search` | Permission-aware lexical search. |
| `POST` | `/api/projects/{project_id}/ask` | Grounded extractive answer or optional LLM answer with authorised citations. |

## Verification and governance

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/projects/{project_id}/verification/summary` | Status counts, score disclaimer, issues. |
| `POST` | `/api/projects/{project_id}/verification/run` | Re-run verification and graph rebuild. |
| `GET` | `/api/projects/{project_id}/conflicts`, `/outdated`, `/unsupported` | Conflict/outdated/unsupported queues. |
| `POST` | `/api/conflicts/{conflict_id}/resolve` | Manager conflict resolution. |
| `GET` | `/api/projects/{project_id}/review/pending`, `/reviews` | Review queue and history. |
| `POST` | `/api/projects/{project_id}/review/approve-eligible`, `/api/claims/{claim_id}/review` | Bulk approval / approve, reject, correct. |
| `GET` | `/api/projects/{project_id}/audit`, `/continuity` | Hash-chained audit history and continuity telemetry. |

## Handovers and continuation

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/projects/{project_id}/handovers/generate` | Generate role-specific draft. |
| `GET` | `/api/projects/{project_id}/handovers`, `/api/handovers/mine` | Manager list / recipient list. |
| `GET/PATCH` | `/api/handovers/{handover_id}` | View / edit and version. |
| `POST` | `/api/handovers/{handover_id}/approve`, `/share` | Human approval and controlled sharing. |
| `GET` | `/api/handovers/{handover_id}/export`, `/items` | Markdown export / checklist items. |
| `POST` | `/api/handover-items/{item_id}/action` | Acknowledge, start, complete. |

Exact request bodies are validated by `backend/app/schemas.py`; the OpenAPI schema
is authoritative for current field names.
