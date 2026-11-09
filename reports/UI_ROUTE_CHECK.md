# UI route runtime check

**Status:** PASS — 17 routes checked, 0 failures.

**Checked:** 2026-11-09T08:54:44.372Z

This is a runtime smoke check of the running React app in headless Chromium,
not a visual-regression test or an accuracy benchmark. It verifies that each
route renders substantive content and records browser runtime errors and
failed API responses.

| Role | Route | Text length | Browser errors | Failed API responses |
| --- | --- | ---: | ---: | ---: |
| `public` | `/` | 2722 | 0 | 0 |
| `public` | `/login` | 929 | 0 | 0 |
| `manager` | `/dashboard` | 3790 | 0 | 0 |
| `manager` | `/workspace` | 1842 | 0 | 0 |
| `manager` | `/sources` | 3353 | 0 | 0 |
| `manager` | `/graph` | 4429 | 0 | 0 |
| `manager` | `/decisions` | 3683 | 0 | 0 |
| `manager` | `/verification` | 17872 | 0 | 0 |
| `manager` | `/conflicts` | 3507 | 0 | 0 |
| `manager` | `/risks` | 7874 | 0 | 0 |
| `manager` | `/review` | 5145 | 0 | 0 |
| `manager` | `/handover` | 23199 | 0 | 0 |
| `manager` | `/continuity` | 1785 | 0 | 0 |
| `manager` | `/access` | 3046 | 0 | 0 |
| `manager` | `/audit` | 7981 | 0 | 0 |
| `engineer` | `/incoming` | 24875 | 0 | 0 |
| `analyst` | `/graph` | 1957 | 0 | 0 |

Screenshots and the capture manifest are in `docs/screenshots/`. Machine-readable
results are in `reports/ui_route_check.json`.

Reproduce with:

```bash
cd tools/browser
npm ci
npm run check:routes
```
