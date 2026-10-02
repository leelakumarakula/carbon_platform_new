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
    ['/admin/audit', 'DEMO_DATA_SEEDED', '06-audit'],
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

  // ---- farmer: least privilege
  const f = await session('farmer@demo.carbon.example');
  await f.page.getByRole('button', { name: 'Sign in' }).click();
  await f.page.getByText('Welcome,').waitFor();
  navItems = await f.page.locator('nav a').allInnerTexts();
  console.log('farmer nav:', navItems.map((s) => s.replace(/\s+/g, ' ').trim()));
  await f.page.goto(`${BASE}/admin/users`);
  await f.page.getByText("You don't have access to this page").waitFor();
  await shot(f.page, '09-farmer-forbidden');
  await f.ctx.close();

  await browser.close();
  // One 401 per session is expected: the silent session-restore attempt before sign-in.
  const real = problems.filter((p) => !p.includes('status of 401'));
  console.log(real.length ? 'PROBLEMS:\n' + real.join('\n') : 'OK: no unexpected console errors or 5xx responses');
  if (!stillIn || real.length || navItems.length !== 1) process.exitCode = 1;
})().catch((e) => {
  console.error('DRIVER FAILED:', e.message);
  process.exit(1);
});
