// UI smoke test against a running stack seeded with DEMO data.
//   BASE_URL=http://localhost:4200 CHROME_PATH=... SHOTS_DIR=... npm run e2e:smoke
// Uses an installed Chrome/Edge (no browser download). DEMO password is read from backend/.env.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const BASE = process.env.BASE_URL || 'http://localhost:4200';
const OUT = process.env.SHOTS_DIR || path.join(__dirname, 'screenshots');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const env = fs.readFileSync(path.join(__dirname, '..', '..', 'backend', '.env'), 'utf8');
const DEMO_PW = (process.env.DEMO_USER_PASSWORD || /^DEMO_USER_PASSWORD=(.*)$/m.exec(env)[1]).trim();
fs.mkdirSync(OUT, { recursive: true });

let stillIn = false;
let navItems = [];
const phase2 = { pmPolygon: 0, overlapFlag: false, drawnArea: '', farmerFarms: 0 };
(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const problems = [];
  async function session(email) {
    const ctx = await browser.newContext({ viewport: { width: 1360, height: 860 } });
    const page = await ctx.newPage();
    page.on('console', (m) => m.type() === 'error' && problems.push(`[${email}] console: ${m.text()}`));
    page.on('pageerror', (e) => problems.push(`[${email}] pageerror: ${e.message}`));
    page.on('response', (r) => r.url().includes('/api/') && r.status() >= 500 && problems.push(`[${email}] ${r.status()} ${r.url()}`));
    await page.goto(`${BASE}/login`);
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(DEMO_PW);
    return { ctx, page };
  }
  const shot = async (page, name) => page.screenshot({ path: path.join(OUT, `${name}.jpg`), type: 'jpeg', quality: 70 });

  // ---- admin
  const { ctx, page } = await session('admin@demo.carbon.example');
  await page.waitForTimeout(600);
  await shot(page, '01-login');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByText('Welcome,').waitFor();
  await page.waitForTimeout(800);
  await shot(page, '02-dashboard');
  for (const [route, text, name] of [
    ['/admin/users', 'demo.carbon.example', '03-users'],
    ['/admin/organizations', 'DEMO-DEV-A', '04-organizations'],
    ['/admin/roles', 'Platform Admin', '05-roles'],
    ['/admin/audit', 'Entries can never be edited or deleted', '06-audit'],
    ['/admin/security', 'Security events', '07-security'],
  ]) {
    await page.goto(BASE + route);
    await page.getByText(text).first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(500);
    await shot(page, name);
  }
  // user detail: open the demo farmer
  await page.goto(`${BASE}/admin/users`);
  await page.getByText('farmer@demo.carbon.example').click();
  await page.getByText('Role grants').waitFor();
  await page.waitForTimeout(400);
  await shot(page, '08-user-detail');
  // reload keeps the session (silent refresh via httpOnly cookie)
  await page.reload();
  await page.getByText('Role grants').waitFor();
  stillIn = await page.getByText('Demo Platform Admin').first().isVisible();
  console.log('session survives reload:', stillIn);
  await ctx.close();

  // ---- Phase 2: project manager — farmers, KYC, farms, map
  const pm = await session('pm@demo.carbon.example');
  await pm.page.getByRole('button', { name: 'Sign in' }).click();
  await pm.page.getByText('Welcome,').waitFor();
  await pm.page.goto(`${BASE}/farmers`);
  await pm.page.getByText('Asha Patil (DEMO)').first().waitFor();
  await shot(pm.page, '10-farmers');
  await pm.page.getByText('Asha Patil (DEMO)').first().click();
  await pm.page.getByRole('tab', { name: 'KYC' }).click();
  await pm.page.getByText('••••').first().waitFor();
  await shot(pm.page, '11-farmer-kyc');
  await pm.page.goto(`${BASE}/farms`);
  await pm.page.getByText('Pimpalgaon plot 1 (DEMO)').first().waitFor();
  await shot(pm.page, '12-farms');
  await pm.page.getByText('Pimpalgaon plot 1 (DEMO)').first().click();
  await pm.page.getByText('Measured area').waitFor();
  await pm.page.locator('.leaflet-interactive').first().waitFor();
  await pm.page.waitForTimeout(1500);
  await shot(pm.page, '13-farm-overview');
  phase2.pmPolygon = await pm.page.locator('path.leaflet-interactive').count();
  await pm.ctx.close();

  // ---- Phase 2: GIS reviewer — overlap flag on the farm in review
  const gis = await session('gis@demo.carbon.example');
  await gis.page.getByRole('button', { name: 'Sign in' }).click();
  await gis.page.getByText('Welcome,').waitFor();
  await gis.page.goto(`${BASE}/farms`);
  await gis.page.getByText('GIS_REVIEW').first().waitFor();
  await gis.page.getByText('GIS_REVIEW').first().click();
  await gis.page.getByRole('tab', { name: /Overlaps/ }).click();
  await gis.page.getByText('Clear', { exact: true }).waitFor();
  await shot(gis.page, '14-overlaps');
  phase2.overlapFlag = true;
  await gis.ctx.close();

  // ---- Phase 2: field collector — draw a boundary on the map and let SQL Server check it (not saved)
  const col = await session('collector@demo.carbon.example');
  await col.page.getByRole('button', { name: 'Sign in' }).click();
  await col.page.getByText('Welcome,').waitFor();
  await col.page.goto(`${BASE}/farms`);
  await col.page.getByText('Sinnar plot 2 (DEMO)').first().waitFor();
  await col.page.getByText('Sinnar plot 2 (DEMO)').first().click();
  await col.page.getByRole('tab', { name: 'Boundary' }).click();
  const map = col.page.locator('.map').first();
  await map.waitFor();
  await col.page.waitForTimeout(1200);
  const box = await map.boundingBox();
  for (const [dx, dy] of [[0.35, 0.35], [0.65, 0.35], [0.65, 0.65], [0.35, 0.65]]) {
    await col.page.mouse.click(box.x + box.width * dx, box.y + box.height * dy);
    await col.page.waitForTimeout(150);
  }
  await col.page.getByRole('button', { name: 'Check boundary' }).click();
  await col.page.getByText('Measured by SQL Server').waitFor();
  phase2.drawnArea = await col.page.getByText('Measured by SQL Server').innerText();
  await shot(col.page, '15-boundary-check');
  await col.ctx.close();

  // ---- farmer: least privilege + self-service
  const f = await session('farmer@demo.carbon.example');
  await f.page.getByRole('button', { name: 'Sign in' }).click();
  await f.page.getByText('Welcome,').waitFor();
  navItems = await f.page.locator('nav a').allInnerTexts();
  console.log('farmer nav:', navItems.map((s) => s.replace(/\s+/g, ' ').trim()));
  await f.page.goto(`${BASE}/admin/users`);
  await f.page.getByText("You don't have access to this page").waitFor();
  await shot(f.page, '09-farmer-forbidden');
  await f.page.goto(`${BASE}/me/farmer`);
  await f.page.getByText('Asha Patil (DEMO)').first().waitFor();
  await f.page.goto(`${BASE}/farms`);
  await f.page.getByText('Pimpalgaon plot 1 (DEMO)').first().waitFor();
  phase2.farmerFarms = await f.page.getByText(/Pimpalgaon plot \d \(DEMO\)/).count();
  await shot(f.page, '16-farmer-my-farms');
  await f.ctx.close();
  console.log('phase 2:', JSON.stringify(phase2));

  await browser.close();
  // One 401 per session is expected: the silent session-restore attempt before sign-in.
  const real = problems.filter((p) => !p.includes('status of 401'));
  console.log(real.length ? 'PROBLEMS:\n' + real.join('\n') : 'OK: no unexpected console errors or 5xx responses');
  const p2ok = phase2.pmPolygon > 0 && phase2.overlapFlag && /ha/.test(phase2.drawnArea) && phase2.farmerFarms >= 2;
  if (!stillIn || real.length || navItems.length !== 3 || !p2ok) process.exitCode = 1;
})().catch((e) => {
  console.error('DRIVER FAILED:', e.message);
  process.exit(1);
});
