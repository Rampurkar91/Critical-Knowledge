/**
 * Fast runtime smoke check for every documented UI route.
 *
 * Unlike capture_screenshots.mjs, this does not write images; it reuses one
 * browser page per role and records runtime errors, failed API responses and
 * visible error/empty-project states. Run with `npm run check:routes`.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import chromium, { inflate, setupLambdaEnvironment } from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';

const UI_BASE = process.env.KB_UI_BASE || 'http://127.0.0.1:5173';
const API_BASE = process.env.KB_API_BASE || 'http://127.0.0.1:8000';
const DEMO_PASSWORD = process.env.DEMO_PASSWORD || 'DemoPass!2026';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const MANIFEST = path.resolve(HERE, '../../docs/screenshots/capture-manifest.json');
const OUTPUT = path.resolve(HERE, '../../reports/ui_route_check.json');

async function apiJson(pathname, options = {}) {
  const response = await fetch(`${API_BASE}${pathname}`, options);
  if (!response.ok) throw new Error(`${pathname} returned ${response.status}`);
  return response.json();
}

async function login(email) {
  return apiJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: DEMO_PASSWORD }),
  });
}

async function main() {
  const manifest = JSON.parse(await fs.readFile(MANIFEST, 'utf8'));
  const specs = manifest.screenshots.map(({ file, label, route, role }) => ({ file, label, route, role }));
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
  const browser = await puppeteer.launch({
    executablePath: await chromium.executablePath(),
    args: [...chromium.args, '--no-sandbox', '--disable-setuid-sandbox'],
    headless: true,
  });

  const results = [];
  try {
    for (const role of ['public', 'manager', 'engineer', 'analyst']) {
      const page = await browser.newPage();
      await page.setViewport({ width: 1440, height: 1000 });
      let errors = [];
      let failedResponses = [];
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
      await page.evaluate(({ token, projectId, role }) => {
        if (role === 'public') {
          localStorage.clear();
        } else {
          localStorage.setItem('knowledgebridge_token', token);
          localStorage.setItem('knowledgebridge_project', projectId);
        }
      }, { token: tokens[role] || '', projectId, role });

      for (const spec of specs.filter((item) => item.role === role)) {
        errors = [];
        failedResponses = [];
        let waitTimedOut = false;
        await page.goto(`${UI_BASE}${spec.route}`, { waitUntil: 'networkidle2', timeout: 60000 });
        try {
          await page.waitForFunction(() => {
            const text = document.body ? document.body.innerText.trim() : '';
            return text.length > 400 && document.querySelectorAll('.animate-spin').length === 0;
          }, { timeout: 20000 });
        } catch {
          waitTimedOut = true;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
        const info = await page.evaluate(() => ({
          title: document.title,
          heading: document.querySelector('h1, h2')?.textContent?.trim() || '',
          textLength: document.body.innerText.trim().length,
          hasErrorPanel: document.body.innerText.includes('Something went wrong') || document.body.innerText.includes('Request failed'),
          hasNoProject: document.body.innerText.includes('No project selected'),
        }));
        results.push({
          ...spec,
          ...info,
          waitTimedOut,
          browserErrors: [...errors],
          failedApiResponses: [...failedResponses],
        });
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }

  const failures = results.filter((r) => r.waitTimedOut || r.hasErrorPanel || r.hasNoProject || r.browserErrors.length || r.failedApiResponses.length);
  const report = {
    checked_at: new Date().toISOString(),
    browser: 'headless Chromium via @sparticuz/chromium + puppeteer-core',
    ui_base: UI_BASE,
    api_base: API_BASE,
    project_id: projectId,
    route_count: results.length,
    failure_count: failures.length,
    status: failures.length ? 'FAIL' : 'PASS',
    results,
  };
  await fs.mkdir(path.dirname(OUTPUT), { recursive: true });
  await fs.writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  console.log(`${report.status}: ${results.length} routes checked; ${failures.length} failures`);
  if (failures.length) {
    console.error(JSON.stringify(failures, null, 2));
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
