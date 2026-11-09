/**
 * Capture real KnowledgeBridge UI screenshots from a running Vite dev server.
 *
 * Prerequisites (from this directory):
 *   npm ci
 *   # backend running on :8000 and frontend running on :5173
 *   npm run capture
 *
 * The script logs in through the API, stores the resulting JWT in the browser's
 * localStorage, then renders each route in a real headless Chromium instance.
 * No mockups or AI-generated imagery are used.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import chromium, { inflate, setupLambdaEnvironment } from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';

const UI_BASE = process.env.KB_UI_BASE || 'http://127.0.0.1:5173';
const API_BASE = process.env.KB_API_BASE || 'http://127.0.0.1:8000';
const DEMO_PASSWORD = process.env.DEMO_PASSWORD || 'DemoPass!2026';
const OUTPUT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs/screenshots');

const ALL_ROUTES = [
  { file: 'landing.png', route: '/', role: 'public', fullPage: true, label: 'Landing page' },
  { file: 'login.png', route: '/login', role: 'public', fullPage: true, label: 'Sign in and demo accounts' },
  { file: 'dashboard.png', route: '/dashboard', role: 'manager', fullPage: false, label: 'Manager dashboard' },
  { file: 'workspace.png', route: '/workspace', role: 'manager', fullPage: false, label: 'Project workspace' },
  { file: 'sources.png', route: '/sources', role: 'manager', fullPage: false, label: 'Source integration' },
  { file: 'graph.png', route: '/graph', role: 'manager', fullPage: false, label: 'Temporal knowledge graph' },
  { file: 'decisions.png', route: '/decisions', role: 'manager', fullPage: false, label: 'Decision history' },
  { file: 'verification.png', route: '/verification', role: 'manager', fullPage: false, label: 'Evidence verification' },
  { file: 'conflicts.png', route: '/conflicts', role: 'manager', fullPage: false, label: 'Conflict detection' },
  { file: 'risks.png', route: '/risks', role: 'manager', fullPage: false, label: 'Risks and dependencies' },
  { file: 'review.png', route: '/review', role: 'manager', fullPage: false, label: 'Review and approval centre' },
  { file: 'handover.png', route: '/handover', role: 'manager', fullPage: false, label: 'Role-specific handover report' },
  { file: 'incoming.png', route: '/incoming', role: 'engineer', fullPage: false, label: 'Incoming-member dashboard' },
  { file: 'continuity.png', route: '/continuity', role: 'manager', fullPage: false, label: 'Project continuity dashboard' },
  { file: 'access.png', route: '/access', role: 'manager', fullPage: false, label: 'Access and permissions' },
  { file: 'audit.png', route: '/audit', role: 'manager', fullPage: false, label: 'Audit history' },
  { file: 'analyst-graph.png', route: '/graph', role: 'analyst', fullPage: false, label: 'Low-clearance graph with hidden-by-policy counters' },
];

const ONLY = (process.env.KB_SCREENSHOTS || '').split(',').map((value) => value.trim()).filter(Boolean);
const ROUTES = ONLY.length ? ALL_ROUTES.filter((spec) => ONLY.includes(spec.file)) : ALL_ROUTES;

async function apiJson(pathname, options = {}) {
  const response = await fetch(`${API_BASE}${pathname}`, options);
  if (!response.ok) {
    throw new Error(`${pathname} returned ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function login(email) {
  return apiJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: DEMO_PASSWORD }),
  });
}

async function preparePage(browser, token, projectId, clearAuth = false) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  const errors = [];
  const failedResponses = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto(`${UI_BASE}/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.evaluate(({ token, projectId, clearAuth }) => {
    if (clearAuth) {
      localStorage.clear();
    } else {
      localStorage.setItem('knowledgebridge_token', token);
      localStorage.setItem('knowledgebridge_project', projectId);
    }
  }, { token, projectId, clearAuth });
  return { page, errors, failedResponses };
}

async function capture(browser, spec, tokens, projectId) {
  const token = spec.role === 'public' ? '' : tokens[spec.role];
  const { page, errors, failedResponses } = await preparePage(
    browser,
    token,
    projectId,
    spec.role === 'public',
  );
  try {
    await page.goto(`${UI_BASE}${spec.route}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForFunction(() => {
      const text = document.body ? document.body.innerText.trim() : '';
      return text.length > 200 && document.querySelectorAll('.animate-spin').length === 0;
    }, { timeout: 30000 });
    await page.evaluate(async () => {
      if (document.fonts) await document.fonts.ready;
    });
    await new Promise((resolve) => setTimeout(resolve, 450));
    const info = await page.evaluate(() => ({
      title: document.title,
      heading: document.querySelector('h1, h2')?.textContent?.trim() || '',
      textLength: document.body.innerText.trim().length,
      hasErrorPanel: document.body.innerText.includes('Something went wrong') || document.body.innerText.includes('Request failed'),
      hasNoProject: document.body.innerText.includes('No project selected'),
    }));
    const outputPath = path.join(OUTPUT_DIR, spec.file);
    await page.screenshot({ path: outputPath, fullPage: spec.fullPage, type: 'png' });
    const stat = await fs.stat(outputPath);
    return {
      file: `docs/screenshots/${spec.file}`,
      label: spec.label,
      route: spec.route,
      role: spec.role,
      fullPage: spec.fullPage,
      bytes: stat.size,
      ...info,
      browserErrors: errors,
      failedApiResponses: failedResponses,
    };
  } finally {
    await page.close();
  }
}

async function writeStaticManifest() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const screenshots = [];
  for (const spec of ALL_ROUTES) {
    const outputPath = path.join(OUTPUT_DIR, spec.file);
    const stat = await fs.stat(outputPath);
    screenshots.push({
      file: `docs/screenshots/${spec.file}`,
      label: spec.label,
      route: spec.route,
      role: spec.role,
      fullPage: spec.fullPage,
      bytes: stat.size,
      captured_at: stat.mtime.toISOString(),
      validation: 'Rendered from the running app in headless Chromium; browser diagnostics are emitted by a full npm run capture.',
    });
  }
  const manifest = {
    generated_at: new Date().toISOString(),
    mode: 'static manifest from captured PNG files',
    browser: 'headless Chromium via @sparticuz/chromium + puppeteer-core',
    ui_base: UI_BASE,
    api_base: API_BASE,
    screenshot_count: screenshots.length,
    screenshots,
  };
  await fs.writeFile(path.join(OUTPUT_DIR, 'capture-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  console.log(`wrote manifest for ${screenshots.length} existing screenshots`);
}

async function main() {
  if (process.env.KB_MANIFEST_ONLY === '1') {
    await writeStaticManifest();
    return;
  }
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const manager = await login('manager@knowledgebridge.demo');
  const engineer = await login('engineer@knowledgebridge.demo');
  const analyst = await login('analyst@knowledgebridge.demo');
  const tokens = {
    manager: manager.access_token,
    engineer: engineer.access_token,
    analyst: analyst.access_token,
  };
  const projects = await apiJson('/api/projects', {
    headers: { Authorization: `Bearer ${tokens.manager}` },
  });
  const projectId = Array.isArray(projects) ? projects[0].id : projects.items[0].id;

  const libArchive = fileURLToPath(new URL('./node_modules/@sparticuz/chromium/bin/al2023.tar.br', import.meta.url));
  const libRoot = await inflate(libArchive);
  setupLambdaEnvironment(path.join(libRoot, 'lib'));
  const executablePath = await chromium.executablePath();
  const browser = await puppeteer.launch({
    executablePath,
    args: [...chromium.args, '--no-sandbox', '--disable-setuid-sandbox'],
    headless: true,
  });

  const results = [];
  try {
    for (const spec of ROUTES) {
      const result = await capture(browser, spec, tokens, projectId);
      results.push(result);
      console.log(`captured ${result.file}: ${result.heading || result.title} (${result.bytes} bytes)`);
    }
  } finally {
    await browser.close();
  }

  const manifest = {
    captured_at: new Date().toISOString(),
    browser: 'headless Chromium via @sparticuz/chromium + puppeteer-core',
    ui_base: UI_BASE,
    api_base: API_BASE,
    project_id: projectId,
    screenshot_count: results.length,
    screenshots: results,
  };
  await fs.writeFile(path.join(OUTPUT_DIR, 'capture-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

  const failures = results.filter((r) => r.hasErrorPanel || r.hasNoProject || r.browserErrors.length || r.failedApiResponses.length);
  if (failures.length) {
    console.error('Screenshots captured, but UI issues were detected:', JSON.stringify(failures, null, 2));
    process.exitCode = 1;
  } else {
    console.log(`all ${results.length} screenshots captured with no runtime errors or failed API responses`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
