// UI smoke test against a running stack seeded with DEMO data.
//   BASE_URL=http://localhost:4200 CHROME_PATH=... SHOTS_DIR=... npm run e2e:smoke
// The run signs in ~15 times within a minute; start the API under test with LOGIN_RATE_LIMIT_PER_MINUTE=100
// (the production default of 10/min per IP would correctly block it).
// Uses an installed Chrome/Edge (no browser download). DEMO password is read from backend/.env.
const fs = require('fs');
const path = require('path');
const { chromium, request } = require('playwright-core');

const BASE = process.env.BASE_URL || 'http://localhost:4200';
const OUT = process.env.SHOTS_DIR || path.join(__dirname, 'screenshots');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const env = fs.readFileSync(path.join(__dirname, '..', '..', 'backend', '.env'), 'utf8');
const DEMO_PW = (process.env.DEMO_USER_PASSWORD || /^DEMO_USER_PASSWORD=(.*)$/m.exec(env)[1]).trim();
fs.mkdirSync(OUT, { recursive: true });

let stillIn = false;
let lastPage = null; // for a failure screenshot
let navItems = [];
const phase2 = { pmPolygon: 0, overlapFlag: false, drawnArea: '', farmerFarms: 0 };
const phase3 = { demoProjects: 0, created: '', areaText: '', boundaryShapes: 0, status: '', historyOk: false, audit: [], farmerProjects: 0,
  buyerBlocked: false, tiles: false };
const phase5 = { dashboard: false, planApproved: false, periodOpen: false, points: 0, assigned: false, collected: '', accepted: 0, qaFails: -1,
  datasetApproved: false, periodStatus: '', projectStatus: '', audit: [], buyerBlocked: false, farmerBlocked: false };
const REQUIRED_AUDIT_P5 = ['MRV_PLAN_CREATED', 'MRV_PLAN_APPROVED', 'MONITORING_PERIOD_CREATED', 'STRATUM_CREATED', 'SAMPLING_DESIGN_CREATED',
  'SAMPLING_POINT_CREATED', 'SAMPLING_POINT_ASSIGNED', 'FIELD_COLLECTION_SUBMITTED', 'FIELD_COLLECTION_ACCEPTED', 'MRV_EVIDENCE_ADDED',
  'MRV_DATASET_SUBMITTED', 'MRV_QA_COMPLETED', 'MRV_DATASET_APPROVED'];
const PNG = Buffer.from('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
  + '1f15c4890000000d49444154789c6360f8cf00000301010018dd8db40000000049454e44ae426082', 'hex');
const phase4 = { catalog: false, approvedReadOnly: false, demoLock: '', candidates: 0, recommended: false, locked: '', audit: [] };
const REQUIRED_AUDIT_P4 = ['PROJECT_METHODOLOGY_CANDIDATES_EVALUATED', 'PROJECT_METHODOLOGY_REVIEWED', 'PROJECT_METHODOLOGY_CONFIRMED'];
const REQUIRED_AUDIT = ['PROJECT_CREATED', 'PROJECT_STATUS_CHANGED', 'PROJECT_FARM_ADDED', 'PROJECT_CARBON_RIGHT_CREATED',
  'PROJECT_PARTICIPANT_ADDED', 'PROJECT_STANDARD_SELECTED', 'PROJECT_ACTIVITY_SELECTED', 'PROJECT_CREDITING_PERIOD_CREATED',
  'PROJECT_BASELINE_UPDATED', 'PROJECT_SUBMITTED'];
(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const problems = [];
  async function session(email, viewport = { width: 1360, height: 860 }) {
    const ctx = await browser.newContext({ viewport });
    const page = await ctx.newPage();
    lastPage = page;
    page.on('console', (m) => m.type() === 'error' && problems.push(`[${email}] console: ${m.text()}`));
    page.on('pageerror', (e) => problems.push(`[${email}] pageerror: ${e.message}`));
    page.on('response', (r) => r.url().includes('/api/') && r.status() >= 500 && problems.push(`[${email}] ${r.status()} ${r.url()}`));
    await page.goto(`${BASE}/login`);
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(DEMO_PW);
    return { ctx, page };
  }
  const shot = async (page, name) => page.screenshot({ path: path.join(OUT, `${name}.jpg`), type: 'jpeg', quality: 70 });
  // Material select: open by its label, pick the first matching enabled option.
  async function choose(page, labelText, option) {
    // A Material select does not open until its options have loaded, so retry the click briefly.
    const opts = page.locator('mat-option:not(.mat-mdc-option-disabled)');
    const target = (option ? opts.filter({ hasText: option }) : opts).first();
    for (let i = 0; i < 20; i++) {
      await page.getByRole('combobox', { name: labelText }).click({ force: true }); // long floating labels can overlap the trigger
      if (await target.waitFor({ timeout: 1000 }).then(() => true, () => false)) break;
      await page.keyboard.press('Escape');
    }
    await target.click();
    await page.waitForTimeout(200);
  }
  async function confirmReason(page, button, reason) {
    const dlg = page.locator('mat-dialog-container');
    await dlg.getByLabel('Reason (recorded in the audit log)').fill(reason);
    await dlg.getByRole('button', { name: button }).click();
    await dlg.waitFor({ state: 'detached' });
  }

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

  // ---- Phase 3: project manager creates a project end to end (UI), then submits it for eligibility review
  const pp = await session('pm@demo.carbon.example');
  const P = pp.page;
  P.on('request', (r) => { if (r.url().includes('/api/v1/config/client')) phase3.tiles = true; });
  await P.getByRole('button', { name: 'Sign in' }).click();
  await P.getByText('Welcome,').waitFor();
  await P.goto(`${BASE}/projects`);
  await P.getByText('Nashik soil health pilot (DEMO)').first().waitFor();
  phase3.demoProjects = await P.getByText(/\(DEMO\)$/).count();
  await shot(P, '20-projects');
  await P.getByRole('link', { name: 'New project' }).click();
  const projectName = `E2E pilot ${Date.now()}`;
  await P.getByLabel('Project name').fill(projectName);
  await P.getByRole('button', { name: 'Create project' }).click();
  await P.getByRole('button', { name: 'Start data collection' }).waitFor();
  phase3.created = await P.locator('h1').first().innerText();
  const projectId = P.url().split('/projects/')[1].split('?')[0];
  await P.getByRole('button', { name: 'Start data collection' }).click();
  await confirmReason(P, 'Start data collection', 'E2E: collecting project data');
  await P.getByText('Data collection', { exact: true }).first().waitFor();
  // farms: pick a verified farm; it is already in a DEMO project, so the conflict must be acknowledged (not rejected)
  await P.getByRole('tab', { name: /^Farms/ }).click();
  await choose(P, 'Farm');
  await P.getByLabel('Agreement / evidence reference').fill('E2E carbon-rights clause, participation agreement');
  await P.getByText('Conflicts to acknowledge').waitFor();
  await P.getByText('I acknowledge these conflicts').click();
  await P.getByLabel('Why the farm can still join').fill('E2E: overlap with DEMO project to be assessed in eligibility review');
  await P.getByRole('button', { name: 'Add farm' }).click();
  await P.locator('.chip', { hasText: 'Rights:' }).first().waitFor();
  await shot(P, '21-project-farms');
  // boundary computed by SQL Server from the farm polygons
  await P.getByRole('tab', { name: 'Boundary' }).click();
  await P.getByText('Project area').waitFor();
  await P.locator('path.leaflet-interactive').first().waitFor();
  await P.waitForTimeout(1200);
  phase3.areaText = await P.locator('dt:has-text("Project area") + dd').innerText();
  phase3.boundaryShapes = await P.locator('path.leaflet-interactive').count();
  await shot(P, '22-project-boundary');
  // team
  await P.getByRole('tab', { name: /^Team/ }).click();
  await choose(P, 'Person', 'Demo QA Officer');
  await P.getByRole('button', { name: 'Add to team' }).click();
  await P.locator('.line').filter({ hasText: 'Demo QA Officer' }).first().waitFor();
  // standard + activity references (no methodology selection)
  await P.getByRole('tab', { name: 'Standard & activity' }).click();
  await choose(P, 'Standard / route', 'Verified Carbon Standard');
  await P.getByRole('button', { name: 'Select', exact: true }).first().click();
  await P.getByText('Official source').waitFor();
  await choose(P, 'Activity offered under the standard', 'reduced tillage');
  await P.getByRole('button', { name: 'Select', exact: true }).nth(1).click();
  await P.getByText('(current)').nth(1).waitFor();
  await shot(P, '23-project-standard');
  // crediting period + baseline metadata
  await P.getByRole('tab', { name: 'Crediting & baseline' }).click();
  await P.getByLabel('Start', { exact: true }).fill('2026-06-01');
  await P.getByLabel('End', { exact: true }).fill('2036-05-31');
  await P.getByRole('button', { name: 'Record period' }).click();
  await P.getByText('2026-06-01 → 2036-05-31').first().waitFor();
  await P.getByLabel('From', { exact: true }).fill('2021-06-01');
  await P.getByLabel('To', { exact: true }).fill('2026-05-31');
  await P.getByLabel('Baseline practices (description)').fill('Conventional tillage, residue burning');
  await P.getByRole('button', { name: 'Record baseline' }).click();
  await P.getByText('v1 ·').waitFor();
  // carbon rights recorded with the farm
  await P.getByRole('tab', { name: /^Carbon rights/ }).click();
  await P.getByText('Unverified').first().waitFor();
  // submit → ELIGIBILITY_REVIEW
  await P.getByRole('button', { name: 'Submit for eligibility review' }).click();
  await confirmReason(P, 'Submit for eligibility review', 'E2E: all project data recorded');
  await P.getByText('Eligibility review', { exact: true }).first().waitFor();
  phase3.status = 'ELIGIBILITY_REVIEW';
  await P.getByRole('tab', { name: 'Status history' }).click();
  await P.getByText('Submitted for eligibility review').waitFor();
  phase3.historyOk = await P.getByText('E2E: all project data recorded').isVisible();
  await shot(P, '24-project-history');
  // audit events (read through the API as the platform admin)
  const api = await request.newContext(); // independent of any browser context
  const tokens = {};
  const tokenFor = async (who) => (tokens[who] ??= (await (await api.post(`${BASE}/api/v1/auth/login`,
    { data: { email: `${who}@demo.carbon.example`, password: DEMO_PW } })).json()).access_token);
  const as = async (who) => ({ Authorization: `Bearer ${await tokenFor(who)}` });
  const auditActions = async () => [...new Set((await (await api.get(
    `${BASE}/api/v1/admin/audit-logs?entity_type=project&entity_id=${projectId}&page_size=100`, { headers: await as('admin') })).json())
    .items.map((r) => r.action))].sort();
  phase3.audit = await auditActions();

  // ---- Phase 4: take the E2E project through eligibility (GIS + QA via API), then methodology selection in the UI
  const gisH = await as('gis');
  const qaH = await as('qa');
  const pmH = await as('pm');
  await api.post(`${BASE}/api/v1/projects/${projectId}/boundary/review`, { headers: gisH, data: { decision: 'ACCEPTED', notes: 'E2E boundary ok' } });
  for (const cr of await (await api.get(`${BASE}/api/v1/projects/${projectId}/carbon-rights`, { headers: qaH })).json()) {
    await api.post(`${BASE}/api/v1/projects/${projectId}/carbon-rights/${cr.id}/review`, { headers: qaH, data: { status: 'VERIFIED', notes: 'E2E seen' } });
  }
  const appr = await api.post(`${BASE}/api/v1/projects/${projectId}/approve-eligibility`, { headers: qaH, data: { reason: 'E2E eligible' } });
  const conf = await api.post(`${BASE}/api/v1/projects/${projectId}/confirm-activity`, { headers: pmH, data: { reason: 'E2E activity' } });
  if (!appr.ok() || !conf.ok()) throw new Error(`eligibility setup failed: ${appr.status()} ${conf.status()}`);
  await P.goto(`${BASE}/projects/${projectId}?tab=methodology`);
  await P.getByText('Declared facts').waitFor();
  await P.getByLabel('Fact key').fill('additionality_assessment');
  await P.getByLabel('Value', { exact: true }).fill('COMPLETED');
  await P.getByRole('button', { name: 'Add fact' }).click();
  await P.getByRole('button', { name: 'Evaluate candidates' }).click();
  await P.locator('mat-expansion-panel').first().waitFor();
  phase4.candidates = await P.locator('mat-expansion-panel').count();
  await P.locator('mat-expansion-panel-header').first().click();
  await P.getByText('Evidence required:').first().waitFor();
  await shot(P, '30-methodology-candidates');
  await pp.ctx.close();
  // methodology specialist recommends the first candidate (the engine never decides)
  const ms = await session('methodology@demo.carbon.example');
  await ms.page.getByRole('button', { name: 'Sign in' }).click();
  await ms.page.getByText('Welcome,').waitFor();
  await ms.page.goto(`${BASE}/methodologies`);
  await ms.page.getByText('DEMO-ALM-SOC').first().waitFor();
  phase4.catalog = true;
  await shot(ms.page, '31-methodologies');
  await ms.page.locator('tr', { hasText: 'Approved' }).first().getByRole('link', { name: 'Open' }).click();
  await ms.page.getByText('Rule revisions').waitFor();
  phase4.approvedReadOnly = await ms.page.getByText('cannot be edited').isVisible();
  await shot(ms.page, '32-methodology-version');
  await ms.page.goto(`${BASE}/projects/${projectId}?tab=methodology`);
  await ms.page.locator('mat-expansion-panel-header').first().click();
  await ms.page.getByRole('button', { name: 'Recommend', exact: true }).first().click();
  await confirmReason(ms.page, 'Recommend', 'E2E: candidate fits the project data; additionality document requested');
  await ms.page.getByText(/Recommended by/).first().waitFor();
  phase4.recommended = true;
  await ms.ctx.close();
  // project manager confirms → methodology + version locked
  const pm2 = await session('pm@demo.carbon.example');
  await pm2.page.getByRole('button', { name: 'Sign in' }).click();
  await pm2.page.getByText('Welcome,').waitFor();
  await pm2.page.goto(`${BASE}/projects/${projectId}?tab=methodology`);
  await pm2.page.locator('mat-expansion-panel-header').first().click();
  await pm2.page.getByRole('button', { name: /Confirm & lock/ }).first().click();
  await confirmReason(pm2.page, 'Confirm & lock', 'E2E: confirmed with the methodology specialist');
  await pm2.page.locator('.locked').waitFor();
  phase4.locked = (await pm2.page.locator('.locked strong').innerText()).trim();
  await shot(pm2.page, '33-methodology-locked');
  // the seeded DEMO project B is locked too
  await pm2.page.goto(`${BASE}/projects`);
  await pm2.page.getByText('Niphad residue retention programme (DEMO)').first().click();
  await pm2.page.getByRole('tab', { name: 'Methodology' }).click();
  await pm2.page.locator('.locked').waitFor();
  phase4.demoLock = (await pm2.page.locator('.locked strong').innerText()).trim();
  phase4.audit = await auditActions();
  await pm2.ctx.close();

  // ---- Phase 5: MRV plan → period → strata → sampling design → points → field collection → dataset → QA → APPROVED
  const MRV = `${BASE}/api/v1/mrv`;
  const json = async (r) => { if (!r.ok()) throw new Error(`${r.url()} → ${r.status()} ${await r.text()}`); return r.json(); };
  const signIn = async (who, viewport) => {
    const s = await session(`${who}@demo.carbon.example`, viewport);
    await s.page.getByRole('button', { name: 'Sign in' }).click();
    await s.page.getByText('Welcome,').waitFor();
    return s;
  };
  const mrv = await signIn('mrv');
  const M = mrv.page;
  await M.goto(`${BASE}/mrv`);
  await M.getByText(projectName).first().waitFor();
  phase5.dashboard = true;
  await shot(M, '40-mrv-dashboard');
  await M.getByText(projectName).first().click();
  await M.getByText('CONFIGURATION_REQUIRED.').waitFor(); // the DEMO methodology configures no sampling rules
  await M.getByRole('link', { name: 'Create MRV plan' }).click();
  await M.getByLabel('Monitoring start').fill('2026-06-01');
  await M.getByLabel('Monitoring end').fill('2036-05-31');
  await M.getByRole('button', { name: 'Add measurement' }).click();
  await M.getByLabel('Code').fill('TILL');
  await M.getByLabel('Name', { exact: true }).fill('Tillage practice');
  await M.getByLabel('Allowed values (comma separated)').fill('CONVENTIONAL, REDUCED, NO_TILL');
  await shot(M, '41-mrv-plan-create');
  await M.getByTestId('create-plan').click();
  await M.getByTestId('submit-plan').click();
  await confirmReason(M, 'Submit', 'E2E: plan ready for approval');
  await M.getByText('Submitted', { exact: true }).first().waitFor();
  const planUrl = M.url();
  const qa = await signIn('qa');
  await qa.page.goto(planUrl);
  await qa.page.getByTestId('approve-plan').click();
  await confirmReason(qa.page, 'Approve', 'E2E: plan approved; CONFIGURATION_REQUIRED gaps acknowledged');
  await qa.page.getByText('Approved', { exact: true }).first().waitFor();
  phase5.planApproved = true;
  await shot(qa.page, '42-mrv-plan-approved');
  // monitoring period in the UI
  await M.goto(`${BASE}/mrv/projects/${projectId}?tab=periods`);
  await M.getByLabel('Name', { exact: true }).fill('E2E monitoring 1');
  await M.getByLabel('Start', { exact: true }).fill('2026-06-01');
  await M.getByLabel('End', { exact: true }).fill('2027-05-31');
  await M.getByRole('button', { name: 'Create period' }).click();
  for (const step of ['Mark planned', 'Start period', 'Open data collection']) {
    await M.getByRole('button', { name: step }).first().click();
    await confirmReason(M, step, `E2E: ${step.toLowerCase()}`);
  }
  await M.getByText('Data collection', { exact: true }).first().waitFor();
  phase5.periodOpen = true;
  await shot(M, '43-mrv-periods');
  // strata (API: MRV manager creates, GIS approves), sampling design in the UI
  const mrvH = await as('mrv');
  const colH = await as('collector');
  const farmIds = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}/farms`, { headers: pmH }))).map((f) => f.farm_id);
  const st = await json(await api.post(`${MRV}/projects/${projectId}/strata`, { headers: mrvH,
    data: { code: 'E2E1', name: 'E2E stratum', farm_ids: farmIds, characteristics: [{ characteristic: 'SOIL_TYPE', value: 'Vertisol' }] } }));
  await json(await api.post(`${MRV}/strata/${st.id}/approve`, { headers: gisH, data: { reason: 'E2E stratum geometry ok' } }));
  await M.goto(`${BASE}/mrv/projects/${projectId}?tab=design`);
  await M.getByTestId('count-E2E1').fill('2');
  await M.getByRole('button', { name: /Create design/ }).click();
  await M.getByText('SOIL-1').first().waitFor();
  const period = (await json(await api.get(`${MRV}/monitoring-periods?project_id=${projectId}`, { headers: mrvH })))[0];
  const design = (await json(await api.get(`${MRV}/sampling-designs?project_id=${projectId}`, { headers: mrvH })))[0];
  await json(await api.post(`${MRV}/sampling-designs/${design.id}/versions/${design.current.id}/approve`, { headers: gisH, data: { reason: 'E2E design ok' } }));
  await M.reload();
  await M.getByTestId('generate-points').click();
  await M.getByText('Points generated').waitFor();
  await shot(M, '44-mrv-design');
  // supervisor assigns the points to the collector (UI)
  const sup = await signIn('supervisor');
  await sup.page.goto(`${BASE}/mrv/projects/${projectId}?tab=points`);
  await sup.page.getByRole('button', { name: 'Select unassigned' }).click();
  await choose(sup.page, 'Field collector', 'collector@');
  await sup.page.getByTestId('assign').click();
  await sup.page.getByText('Assigned', { exact: true }).first().waitFor();
  const pts = await json(await api.get(`${MRV}/sampling-points?monitoring_period_id=${period.id}`, { headers: mrvH }));
  phase5.points = pts.length;
  phase5.assigned = pts.every((x) => x.status === 'ASSIGNED');
  await shot(sup.page, '45-mrv-points-map');
  // field collector on a phone: first point through the UI, the second through the API
  const fieldS = await signIn('collector', { width: 390, height: 844 });
  const C = fieldS.page;
  await C.goto(`${BASE}/field`);
  await C.locator(`[data-point="${pts[0].point_code}"]`).getByTestId('start-collection').click();
  await C.getByText('Field checklist').waitFor();
  await C.getByLabel('Latitude').fill(String(pts[0].latitude));
  await C.getByLabel('Longitude').fill(String(pts[0].longitude));
  for (const k of ['location_confirmed', 'depth_measured', 'sample_labelled']) await C.locator(`[data-check="${k}"] input`).check();
  await C.getByTestId('photo').setInputFiles({ name: 'sample.png', mimeType: 'image/png', buffer: PNG });
  await C.getByText('Photos (1)').waitFor();
  await shot(C, '46-field-collection-mobile');
  await C.getByTestId('submit-collection').click();
  await C.getByText('Submitted', { exact: true }).first().waitFor();
  phase5.collected = (await C.locator('app-page-header h1').innerText().catch(() => '')).trim();
  await C.goto(`${BASE}/field`);
  await C.getByText('Collected', { exact: true }).first().waitFor();
  await shot(C, '47-field-dashboard-mobile');
  const fc2 = await json(await api.post(`${MRV}/field-collections`, { headers: colH, data: { sampling_point_id: pts[1].id } }));
  await json(await api.patch(`${MRV}/field-collections/${fc2.id}`, { headers: colH, data: { collected_at: new Date().toISOString(),
    gps_latitude: Number(pts[1].latitude), gps_longitude: Number(pts[1].longitude), actual_depth_top_cm: 0, actual_depth_bottom_cm: 30,
    checklist: { location_confirmed: true, depth_measured: true, sample_labelled: true, photo_taken: true } } }));
  await json(await api.post(`${MRV}/evidence`, { headers: colH, multipart: { project_id: projectId, entity_type: 'FIELD_COLLECTION', entity_id: fc2.id,
    evidence_type: 'FIELD_PHOTO', file: { name: 'sample.png', mimeType: 'image/png', buffer: PNG } } }));
  await json(await api.post(`${MRV}/field-collections/${fc2.id}/submit`, { headers: colH }));
  // supervisor accepts both records (UI)
  await sup.page.reload();
  lastPage = sup.page;
  await sup.page.getByTestId('accept').nth(1).waitFor();
  for (let left = 2; left > 0; left--) {
    await sup.page.getByTestId('accept').first().click();
    await confirmReason(sup.page, 'Accepted', 'E2E: sample and photo checked');
    for (let t = 0; t < 50 && (await sup.page.getByTestId('accept').count()) >= left; t++) await sup.page.waitForTimeout(200);
  }
  phase5.accepted = (await json(await api.get(`${MRV}/field-collections?monitoring_period_id=${period.id}`, { headers: mrvH })))
    .filter((x) => x.status === 'ACCEPTED').length;
  // activity data per farm (API), dataset created (API), submitted (UI)
  const plan = (await json(await api.get(`${MRV}/plans?project_id=${projectId}`, { headers: mrvH }))).find((x) => x.status === 'APPROVED');
  const till = plan.measurements.find((m) => m.code === 'TILL');
  for (const fid of farmIds) {
    await json(await api.post(`${MRV}/monitoring-records`, { headers: colH, data: { monitoring_period_id: period.id, measurement_id: till.id,
      farm_id: fid, value: 'REDUCED', observed_on: new Date().toISOString().slice(0, 10), measurement_phase: 'PROJECT' } }));
  }
  const ds = await json(await api.post(`${MRV}/datasets`, { headers: mrvH, data: { monitoring_period_id: period.id } }));
  await M.goto(`${BASE}/mrv/datasets/${ds.id}`);
  await M.getByTestId('submit-dataset').click();
  await confirmReason(M, 'Submit', 'E2E: collection complete');
  await M.getByText('Submitted', { exact: true }).first().waitFor();
  // QA officer: deterministic checks, PASS, approve (UI)
  lastPage = qa.page;
  await qa.page.goto(`${BASE}/mrv/datasets/${ds.id}`);
  await qa.page.getByTestId('start-qa').click();
  await qa.page.getByTestId('complete-qa').waitFor();
  phase5.qaFails = await qa.page.locator('.check', { hasText: 'FAIL' }).count();
  await shot(qa.page, '48-mrv-qa-review');
  await qa.page.getByTestId('complete-qa').click();
  await confirmReason(qa.page, 'Record', 'E2E: all checks pass');
  await qa.page.getByTestId('approve-dataset').click();
  await confirmReason(qa.page, 'Approve', 'E2E: dataset approved');
  await qa.page.getByText('Approved', { exact: true }).first().waitFor();
  phase5.datasetApproved = true;
  await shot(qa.page, '49-mrv-dataset-approved');
  phase5.periodStatus = (await json(await api.get(`${MRV}/monitoring-periods/${period.id}`, { headers: mrvH }))).status;
  phase5.projectStatus = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).status;
  phase5.audit = [...new Set((await json(await api.get(`${MRV}/projects/${projectId}/history`, { headers: mrvH }))).map((h) => h.action))].sort();
  await M.goto(`${BASE}/mrv/projects/${projectId}?tab=history`);
  await M.getByText('Mrv dataset approved').first().waitFor();
  await shot(M, '50-mrv-history');
  for (const x of [mrv, qa, sup, fieldS]) await x.ctx.close();
  await api.dispose();

  // ---- Phase 3: buyer has no project access
  const b = await session('buyer@demo.carbon.example');
  await b.page.getByRole('button', { name: 'Sign in' }).click();
  await b.page.getByText('Welcome,').waitFor();
  await b.page.goto(`${BASE}/projects`);
  await b.page.getByText("You don't have access to this page").waitFor();
  phase3.buyerBlocked = !(await b.page.locator('nav a', { hasText: 'Projects' }).count());
  await b.page.goto(`${BASE}/mrv`);
  await b.page.getByText("You don't have access to this page").waitFor();
  await b.page.goto(`${BASE}/field`);
  await b.page.getByText("You don't have access to this page").waitFor();
  phase5.buyerBlocked = !(await b.page.locator('nav a', { hasText: 'MRV' }).count());
  await b.ctx.close();

  // ---- farmer: least privilege + self-service
  const f = await session('farmer@demo.carbon.example');
  await f.page.getByRole('button', { name: 'Sign in' }).click();
  await f.page.getByText('Welcome,').waitFor();
  navItems = await f.page.locator('nav a').allInnerTexts();
  console.log('farmer nav:', navItems.map((s) => s.replace(/\s+/g, ' ').trim()));
  await f.page.goto(`${BASE}/mrv`);
  await f.page.getByText("You don't have access to this page").waitFor();
  phase5.farmerBlocked = true;
  await f.page.goto(`${BASE}/admin/users`);
  await f.page.getByText("You don't have access to this page").waitFor();
  await shot(f.page, '09-farmer-forbidden');
  await f.page.goto(`${BASE}/me/farmer`);
  await f.page.getByText('Asha Patil (DEMO)').first().waitFor();
  await f.page.goto(`${BASE}/farms`);
  await f.page.getByText('Pimpalgaon plot 1 (DEMO)').first().waitFor();
  phase2.farmerFarms = await f.page.getByText(/Pimpalgaon plot \d \(DEMO\)/).count();
  await shot(f.page, '16-farmer-my-farms');
  await f.page.goto(`${BASE}/me/projects`);
  await f.page.getByText('Nashik soil health pilot (DEMO)').first().waitFor();
  phase3.farmerProjects = await f.page.locator('mat-card').count();
  await shot(f.page, '25-farmer-my-projects');
  await f.ctx.close();
  console.log('phase 2:', JSON.stringify(phase2));
  console.log('phase 3:', JSON.stringify(phase3));
  console.log('phase 4:', JSON.stringify(phase4));
  console.log('phase 5:', JSON.stringify(phase5));

  await browser.close();
  // One 401 per session is expected: the silent session-restore attempt before sign-in.
  const real = problems.filter((p) => !p.includes('status of 401'));
  console.log(real.length ? 'PROBLEMS:\n' + real.join('\n') : 'OK: no unexpected console errors or 5xx responses');
  const p2ok = phase2.pmPolygon > 0 && phase2.overlapFlag && /ha/.test(phase2.drawnArea) && phase2.farmerFarms >= 2;
  const missingAudit = REQUIRED_AUDIT.filter((a) => !phase3.audit.includes(a));
  if (missingAudit.length) console.log('missing audit events:', missingAudit);
  const p3ok = phase3.demoProjects >= 2 && /ha/.test(phase3.areaText) && phase3.boundaryShapes >= 2 && phase3.status === 'ELIGIBILITY_REVIEW'
    && phase3.historyOk && !missingAudit.length && phase3.farmerProjects >= 1 && phase3.buyerBlocked && phase3.tiles;
  // farmer nav: Dashboard, My farmer profile, My farms, My projects
  const missingP4 = REQUIRED_AUDIT_P4.filter((a) => !phase4.audit.includes(a));
  if (missingP4.length) console.log('missing phase 4 audit events:', missingP4);
  const p4ok = phase4.catalog && phase4.approvedReadOnly && phase4.candidates >= 2 && phase4.recommended && /version/.test(phase4.locked)
    && /DEMO-CCTS-SOIL/.test(phase4.demoLock) && !missingP4.length;
  const missingP5 = REQUIRED_AUDIT_P5.filter((a) => !phase5.audit.includes(a));
  if (missingP5.length) console.log('missing phase 5 audit events:', missingP5);
  const p5ok = phase5.dashboard && phase5.planApproved && phase5.periodOpen && phase5.points === 2 && phase5.assigned
    && /^FIELD-\d{4}-\d{6}$/.test(phase5.collected) && phase5.accepted === 2 && phase5.qaFails === 0 && phase5.datasetApproved
    && phase5.periodStatus === 'APPROVED' && phase5.projectStatus === 'MONITORING' && phase5.buyerBlocked && phase5.farmerBlocked && !missingP5.length;
  if (!stillIn || real.length || navItems.length !== 4 || !p2ok || !p3ok || !p4ok || !p5ok) process.exitCode = 1;
})().catch(async (e) => {
  console.error('DRIVER FAILED:', e.message);
  if (lastPage) {
    await lastPage.screenshot({ path: path.join(OUT, 'zz-failure.jpg'), type: 'jpeg', quality: 70 }).catch(() => undefined);
    console.error('page text:', (await lastPage.locator('body').innerText().catch(() => '')).slice(0, 1500));
  }
  process.exit(1);
});
