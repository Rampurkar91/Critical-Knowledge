# Screenshot capture tool

This small ESM script renders the running KnowledgeBridge React app in real
headless Chromium and writes screenshots into `docs/screenshots/`.

## Usage

From the repository root, start both services:

```bash
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev -- --host 0.0.0.0 --port 5173
```

In another terminal:

```bash
cd tools/browser
npm ci
npm run capture
```

Environment overrides: `KB_UI_BASE`, `KB_API_BASE`, `DEMO_PASSWORD`.
Use `KB_SCREENSHOTS=access.png,audit.png npm run capture` to refresh only named
files. A full run writes `docs/screenshots/capture-manifest.json` with route,
role, title, file size, browser errors and failed API responses. If a capture
was split into batches, regenerate a static file manifest with
`KB_MANIFEST_ONLY=1 npm run capture`.

Run `npm run check:routes` for a faster no-screenshot runtime check of every
documented route. It writes `reports/ui_route_check.json`; the latest result is
17 routes, 0 runtime errors and 0 failed API responses.

These dependencies are documentation tooling only; the application itself does
not require Chromium or Puppeteer at runtime.
