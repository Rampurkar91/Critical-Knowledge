# Real UI screenshots

These are real screenshots of the running KnowledgeBridge React app, rendered in
headless Chromium and saved as PNG files. They are not generated mockups. The
hero illustration in `frontend/public/hero-network.png` is separate AI artwork
used on the landing page.

Capture tool: `tools/browser/capture_screenshots.mjs`. It logs in through the
real API, stores the JWT in browser `localStorage`, loads each route and takes a
screenshot. `capture-manifest.json` lists routes, roles, file sizes and
timestamps. A separate `npm run check:routes` tool visited all 17 routes and
recorded **0 runtime errors and 0 failed API responses** in
`reports/UI_ROUTE_CHECK.md` and `reports/ui_route_check.json`.

## Key screenshots

| Page | File | Role |
| --- | --- | --- |
| Landing | `landing.png` | public |
| Sign in / demo accounts | `login.png` | public |
| Main dashboard | `dashboard.png` | project manager |
| Project workspace | `workspace.png` | project manager |
| Source integration | `sources.png` | project manager |
| Temporal knowledge graph | `graph.png` | project manager |
| Decision history | `decisions.png` | project manager |
| Evidence verification | `verification.png` | project manager |
| Conflict detection | `conflicts.png` | project manager |
| Risks & dependencies | `risks.png` | project manager |
| Review & approval | `review.png` | project manager |
| Role-specific handover | `handover.png` | project manager |
| Incoming-member dashboard | `incoming.png` | incoming engineer |
| Project continuity | `continuity.png` | project manager |
| Access & permissions | `access.png` | project manager |
| Audit history | `audit.png` | project manager |
| Low-clearance graph | `analyst-graph.png` | incoming analyst |

The analyst graph screenshot shows the hidden-by-policy counters that appear
when restricted nodes and edges are filtered before serialisation.
