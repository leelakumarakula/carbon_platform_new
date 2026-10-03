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
const phase6 = { engagement: '', scope: '', sample: '', tests: 0, shipment: '', unitPrefilled: '', qaFails: -1, approved: '', lineage: false,
  analysisStatus: '', labRestricted: false, buyerFarmerBlocked: false, sod: '', retest: '', windDown: {}, audit: [] };
const phase7 = { readinessBlocker: false, labels: false, runBlocked: false, runLabel: false, runCode: '', runStatus: '', netResult: 'x',
  modules: -1, projectStatus: '', qaCanRead: false, valueRefused: false, outsidersBlocked: false, audit: [] };
const phase8a = { noReportForBlocked: false, finding: '', category: '', findingStatus: '', reportRefused: '', readinessLabel: false,
  readinessBlocked: false, createRefused: '', niphad: '', outsidersBlocked: false, projectStatus: '', audit: [] };
const phase8b = { labels: false, assignment: '', proposed: '', accepted: '', submitRefused: '', noDecision: false, projectStatus: '', niphad: '',
  vvbIsolated: false, nonVvbBlocked: false, unknownSubmission: 0, vvbNav: false, audit: [] };
const phase9a = { demoNote: false, cards: false, blocker: false, createRefused: '', niphadRefused: '', registryNav: false, registryPage: false,
  creditsEmpty: false, noDemoCredits: false, demoRegistry: '', outsidersBlocked: false, vvbNoRegistry: false, projectStatus: '' };
const phase9b = { ledgerNav: false, demoNote: false, columns: false, ledgerEmpty: false, inventoryEmpty: false, openRefused: '', reserveRefused: '',
  transferRefused: '', retireRefused: '', balanceRejected: '', holderNav: false, holderDemoNote: false, holderEmpty: false, holderNoLedger: false,
  outsidersBlocked: false, nonHoldersBlocked: false };
const phase10 = { buyerNav: false, demoNote: false, noListings: false, kyc: '', kycUi: false, orderRefused: '', balanceRejected: '',
  noOrders: false, financeNav: false, noPayments: false, listingRefused: '', sellerEmpty: false, complianceNav: false, outsidersBlocked: false,
  noFakeData: false };
const phase11 = { financeNav: false, demoNote: false, revenueEmpty: false, configRequired: false, payoutsEmpty: false, sharingRefused: '',
  costRefused: '', settlementRefused: '', amountRejected: '', farmerNav: false, farmerEmpty: false, outsidersBlocked: false, farmerBlocked: false,
  noFakeData: false };
const phase12 = { jobsNav: false, statusPanel: false, demoNote: false, brokerHonest: false, registry: 0, triggered: '', replay: false,
  cancelledUi: false, arbitraryRefused: '', retryRefused: '', outsidersBlocked: false, noFinanceTasks: false, audit: [] };
const phase12b = { scanState: '', eicarRefused: '', quarantined: '', quarantineNav: false, quarantinePage: false, historyUi: false,
  releaseRefused: '', stillQuarantined: false, downloadBlocked: '', outsidersBlocked: false, adminNoManage: '', audit: [] };
const REQUIRED_AUDIT_P6 = ['LAB_ENGAGEMENT_PROPOSED', 'LAB_ENGAGEMENT_ACCEPTED', 'LAB_ENGAGEMENT_ENDED', 'LAB_SAMPLE_REGISTERED', 'LAB_CUSTODY_SEALED',
  'LAB_TEST_CREATED', 'LAB_SHIPMENT_CREATED', 'LAB_SHIPMENT_DISPATCHED', 'LAB_SHIPMENT_RECEIPT_RECORDED', 'LAB_TEST_STARTED', 'LAB_RESULT_CREATED',
  'LAB_REPORT_ATTACHED', 'LAB_RESULT_SUBMITTED', 'LAB_QA_STARTED', 'LAB_RESULT_APPROVED', 'LAB_RETEST_REQUESTED', 'LAB_RESULT_SUPERSEDED'];
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
    page.on('console', (m) => m.type() === 'error' && problems.push(`[${email}] console: ${m.text()} @ ${m.location()?.url ?? ''}`));
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
  await P.getByLabel('Search code, name, region').fill('(DEMO)');   // each E2E run adds a project; the seeded ones may be past page 1
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
  await pm2.page.getByLabel('Search code, name, region').fill('Niphad');
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
  await M.getByText('Points generated (SQL Server validated).').waitFor();
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
  for (const k of ['location_confirmed', 'depth_measured', 'sample_labelled_with_sample_code']) await C.locator(`[data-check="${k}"] input`).check();
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
    checklist: Object.fromEntries(fc2.required_checklist.map((k) => [k, true])) } }));
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
  // ---- Phase 6: engagement → sample (auto tests) → seal → shipment → receipt → analysis → laboratory QA → lineage; SoD, retest, wind-down
  const LAB = `${BASE}/api/v1/lab`;
  const LABV = `${BASE}/api/v1/laboratory`;
  const p6Start = new Date(Date.now() - 2000).toISOString();
  const PDF = Buffer.from('%PDF-1.4\n% E2E laboratory report (test document, not a real analysis)\n%%EOF\n');
  const errCode = async (r) => `${r.status()} ${(await r.json().catch(() => ({}))).error_code ?? ''}`.trim();
  // Material select identified by its data-testid (labels can overlap, e.g. "Laboratory" / "LABORATORY rules in scope")
  async function pick(page, testid, option, multiple = false) {
    const target = page.locator('mat-option:not(.mat-mdc-option-disabled)').filter(option ? { hasText: option } : {}).first();
    for (let i = 0; i < 20; i++) {
      await page.getByTestId(testid).click({ force: true });
      if (await target.waitFor({ timeout: 1000 }).then(() => true, () => false)) break;
      await page.keyboard.press('Escape');
    }
    await target.click();
    if (multiple) await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
  }
  const supH = await as('supervisor');
  const techH = await as('labtech');
  const lmH = await as('labmanager');
  const lqaH = await as('labqa');
  const labOrg = (await json(await api.get(`${LAB}/projects/${projectId}/laboratories`, { headers: mrvH }))).find((o) => o.code === 'DEMO-LAB-B');
  // engagement: MRV manager proposes (UI), the laboratory manager accepts (UI)
  await M.goto(`${BASE}/mrv/projects/${projectId}?tab=samples`);
  lastPage = M;
  await pick(M, 'engage-lab', labOrg.name);
  await pick(M, 'engage-rules', null, true);
  await M.getByTestId('propose-engagement').click();
  await M.getByText('Proposed', { exact: true }).first().waitFor();
  const lm = await signIn('labmanager');
  lastPage = lm.page;
  await lm.page.goto(`${BASE}/laboratory`);
  const projCode = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).project_code;
  await lm.page.locator('.line', { hasText: projCode }).getByTestId('accept-engagement').click();
  await lm.page.locator('.line', { hasText: projCode }).getByText('Active', { exact: true }).waitFor();
  const eng = (await json(await api.get(`${LAB}/engagements?project_id=${projectId}`, { headers: mrvH }))).find((e) => e.status === 'ACTIVE');
  phase6.engagement = eng.status;
  phase6.scope = eng.rules.map((r) => `${r.rule_code} (${r.unit})`).join(', ');
  await shot(lm.page, '60-lab-engagement-accepted');
  // 1–2. field agent registers & seals a sample from their own accepted record (phone UI); tests are created automatically
  const fcs = await json(await api.get(`${MRV}/field-collections?monitoring_period_id=${period.id}`, { headers: mrvH }));
  const fc1 = fcs.find((x) => x.sampling_point_id === pts[0].id && x.status === 'ACCEPTED');
  const fcB = fcs.find((x) => x.sampling_point_id === pts[1].id && x.status === 'ACCEPTED');
  lastPage = C;
  await C.goto(`${BASE}/field/collections/${fc1.id}`);
  await C.getByTestId('register-sample').click();
  await C.getByTestId('seal-sample').waitFor();
  const smp = (await json(await api.get(`${LAB}/samples?field_collection_id=${fc1.id}`, { headers: colH })))[0];
  phase6.sample = smp.sample_code;
  phase6.tests = smp.test_count;
  await C.getByTestId(`seal-${smp.sample_code}`).fill('E2E-SEAL-0001');
  await C.getByTestId('seal-sample').click();
  await C.getByText('Sealed', { exact: true }).first().waitFor();
  await shot(C, '61-field-register-seal-mobile');
  // 3–4. supervisor creates the shipment, adds the sealed sample and dispatches it (UI)
  lastPage = sup.page;
  await sup.page.goto(`${BASE}/mrv/projects/${projectId}?tab=samples`);
  await pick(sup.page, 'ship-lab', labOrg.name);
  await sup.page.getByTestId('create-shipment').click();
  await sup.page.getByText(/SHP-\d{4}-\d{6}/).first().waitFor();
  const ship = (await json(await api.get(`${LAB}/shipments?project_id=${projectId}`, { headers: supH })))[0];
  await pick(sup.page, `add-samples-${ship.shipment_code}`, smp.sample_code, true);
  await sup.page.getByRole('button', { name: 'Add', exact: true }).click();
  await sup.page.getByText(`${smp.sample_code} · In shipment`).waitFor();
  await sup.page.getByTestId('dispatch').click();
  await sup.page.getByText('Dispatched', { exact: true }).first().waitFor();
  phase6.shipment = ship.shipment_code;
  await shot(sup.page, '62-mrv-samples-shipment');
  // 5. laboratory receives (item level) and registers the sample (UI)
  const lt = await signIn('labtech');
  const T = lt.page;
  lastPage = T;
  await T.goto(`${BASE}/laboratory`);
  await T.getByRole('tab', { name: 'Incoming' }).click();
  await T.getByTestId('receive').click();
  await T.getByText('Receipt recorded.').waitFor();
  await T.getByRole('tab', { name: 'Samples' }).click();
  await T.getByTestId(`accession-${smp.sample_code}`).fill(`ACC-${smp.sample_code}`);
  await T.locator('tr', { hasText: smp.sample_code }).getByRole('button', { name: 'Register', exact: true }).click();  // other runs' samples may wait too
  await T.getByText(`ACC-${smp.sample_code}`).waitFor();
  await shot(T, '63-lab-samples');
  // 6–7. technician analyses, enters the result with the rule's exact unit, attaches the PDF report and submits (UI)
  await T.getByRole('tab', { name: 'Worklist' }).click();
  const test1 = (await json(await api.get(`${LABV}/tests`, { headers: techH }))).find((t) => t.sample_code === smp.sample_code);
  await T.getByRole('link', { name: test1.test_code }).click();
  await T.getByTestId('start-test').click();
  await T.getByTestId('result-value').fill('1.23');
  phase6.unitPrefilled = await T.getByTestId('result-unit').inputValue();
  await T.getByTestId('save-result').click();
  await T.getByTestId('report-1').setInputFiles({ name: 'e2e-report.pdf', mimeType: 'application/pdf', buffer: PDF });
  await T.getByText('Report: e2e-report.pdf').waitFor();
  await T.getByTestId('submit-result').click();
  await T.getByText('Submitted', { exact: true }).first().waitFor();
  await shot(T, '64-lab-test-result');
  const r1 = (await json(await api.get(`${LABV}/tests/${test1.id}`, { headers: techH }))).results[0];
  // 8–9. a different laboratory manager performs QA and approves (UI)
  const lq = await signIn('labqa');
  lastPage = lq.page;
  await lq.page.goto(`${BASE}/laboratory`);
  await lq.page.getByRole('tab', { name: 'QA' }).click();
  await lq.page.locator(`a[href="/laboratory/qa/${r1.id}"]`).click();
  await lq.page.getByTestId('start-lab-qa').click();
  await lq.page.getByTestId('lab-qa-notes').waitFor();
  phase6.qaFails = await lq.page.locator('.check', { hasText: 'FAIL' }).count();
  await shot(lq.page, '65-lab-qa-checks');
  await lq.page.getByTestId('lab-qa-notes').fill('E2E: all laboratory QA checks pass');
  await lq.page.getByTestId('lab-qa-submit').click();
  await lq.page.getByText('Approved', { exact: true }).first().waitFor();
  phase6.approved = (await json(await api.get(`${LABV}/qa/${r1.id}`, { headers: lqaH }))).result.status;
  // 10. project user sees the approved result and its full lineage (UI)
  lastPage = M;
  await M.goto(`${BASE}/mrv/projects/${projectId}?tab=samples`);
  await M.getByTestId('lineage-link').first().click();
  await M.getByTestId('lineage').waitFor();
  const lineageText = await M.getByTestId('lineage').innerText();
  phase6.lineage = [smp.sample_code, fc1.collection_code, pts[0].point_code, 'Farm', 'Methodology', 'Plan measurement'].every((s) => lineageText.includes(s));
  phase6.analysisStatus = (await json(await api.get(`${MRV}/field-collections/${fc1.id}`, { headers: mrvH }))).analysis_status;
  await shot(M, '66-lab-result-lineage');
  // 11. laboratory users see allow-listed data only: no farmer / farm / GPS / MRV data
  const labJson = JSON.stringify([await json(await api.get(`${LABV}/samples/${smp.id}`, { headers: techH })),
    await json(await api.get(`${LABV}/shipments/${ship.id}`, { headers: techH })), await json(await api.get(`${LABV}/tests/${test1.id}`, { headers: techH }))]);
  const leaks = ['farmer', 'farm_', 'latitude', 'longitude', 'gps', 'field_collection', 'sampling_point', 'stratum'].filter((k) => labJson.includes(k));
  const labDenied = [];
  for (const u of [`${BASE}/api/v1/farmers`, `${BASE}/api/v1/farms`, `${MRV}/projects`, `${LAB}/samples/${smp.id}`, `${LAB}/results/${r1.id}/lineage`,
    `${MRV}/field-collections/${fc1.id}`]) {
    const r = await api.get(u, { headers: techH });
    if ([403, 404].includes(r.status())) labDenied.push(u);
  }
  await T.goto(`${BASE}/mrv`);
  await T.getByText("You don't have access to this page").waitFor();
  phase6.labRestricted = !leaks.length && labDenied.length === 6;
  if (leaks.length) console.log('laboratory view leaks:', leaks);
  // 12. buyer / farmer remain outside Phase 6
  let outside = 0;
  for (const who of ['buyer', 'farmer']) {
    const h = await as(who);
    for (const u of [`${LABV}/dashboard`, `${LAB}/results?project_id=${projectId}`, `${LAB}/samples?project_id=${projectId}`]) {
      if ([403, 404].includes((await api.get(u, { headers: h })).status())) outside++;
    }
  }
  phase6.buyerFarmerBlocked = outside === 6;
  // 14 + 13. retest: labmanager requests it; technician re-analyses; the requester's approval is refused (SEPARATION_OF_DUTIES); labqa approves
  const t2 = await json(await api.post(`${LABV}/results/${r1.id}/retest`, { headers: lmH, data: { reason: 'E2E: duplicate check requested' } }));
  await json(await api.post(`${LABV}/tests/${t2.id}/start`, { headers: techH, data: {} }));
  const r2 = await json(await api.post(`${LABV}/tests/${t2.id}/results`, { headers: techH, data: { result_type: 'NUMERIC', value_number: 1.25,
    unit: t2.required_unit, analysed_at: new Date().toISOString() } }));
  await json(await api.post(`${LABV}/results/${r2.id}/report`, { headers: techH, multipart: { file: { name: 'e2e-retest.pdf', mimeType: 'application/pdf', buffer: PDF } } }));
  await json(await api.post(`${LABV}/results/${r2.id}/submit`, { headers: techH }));
  const lmStart = await api.post(`${LABV}/qa/${r2.id}/start`, { headers: lmH });
  const sod = lmStart.ok() ? await api.post(`${LABV}/qa/${r2.id}/decision`, { headers: lmH, data: { decision: 'APPROVED', notes: 'E2E: requester tries',
    acknowledge_configuration: false } }) : lmStart;
  phase6.sod = await errCode(sod);
  if (!lmStart.ok() || (await json(await api.get(`${LABV}/qa/${r2.id}`, { headers: lqaH }))).can_start) {
    await json(await api.post(`${LABV}/qa/${r2.id}/start`, { headers: lqaH }));
  }
  await json(await api.post(`${LABV}/qa/${r2.id}/decision`, { headers: lqaH, data: { decision: 'APPROVED', notes: 'E2E: retest result approved',
    acknowledge_configuration: false } }));
  const all = await json(await api.get(`${LAB}/results?project_id=${projectId}&status=ALL`, { headers: mrvH }));
  phase6.retest = `${all.find((x) => x.id === r1.id)?.status}/${all.find((x) => x.id === r2.id)?.status}`;
  // 15. wind-down: a second sample is already in transit when the project ends the engagement
  const s2 = await json(await api.post(`${LAB}/samples`, { headers: colH, data: { field_collection_id: fcB.id, description: 'E2E second core' } }));
  await json(await api.post(`${LAB}/samples/${s2.id}/seal`, { headers: colH, data: { seal_number: 'E2E-SEAL-0002' } }));
  const ship2 = await json(await api.post(`${LAB}/shipments`, { headers: supH, data: { project_id: projectId, laboratory_org_id: labOrg.id } }));
  await json(await api.post(`${LAB}/shipments/${ship2.id}/items`, { headers: supH, data: { sample_ids: [s2.id] } }));
  await json(await api.post(`${LAB}/shipments/${ship2.id}/dispatch`, { headers: supH, data: {} }));
  await json(await api.post(`${LAB}/engagements/${eng.id}/end`, { headers: mrvH, data: { reason: 'E2E: laboratory contract finished' } }));
  const wind = {
    receiptAllowed: (await api.post(`${LABV}/shipments/${ship2.id}/receive`, { headers: techH, data: { items: [{ sample_id: s2.id, accepted: true,
      condition: 'intact', seal_number_observed: 'E2E-SEAL-0002' }] } })).ok(),
    newShipment: await errCode(await api.post(`${LAB}/shipments`, { headers: supH, data: { project_id: projectId, laboratory_org_id: labOrg.id } })),
    retest: await errCode(await api.post(`${LABV}/results/${r2.id}/retest`, { headers: lmH, data: { reason: 'E2E: after the end' } })),
    endAgain: await errCode(await api.post(`${LABV}/engagements/${eng.id}/end`, { headers: lmH, data: { reason: 'E2E: again' } })),
    approvedStillVisible: (await json(await api.get(`${LAB}/results?project_id=${projectId}`, { headers: mrvH }))).some((x) => x.id === r2.id),
  };
  const pending = (await json(await api.get(`${LABV}/tests`, { headers: techH }))).find((t) => t.sample_code === s2.sample_code);
  wind.newTestStart = pending ? await errCode(await api.post(`${LABV}/tests/${pending.id}/start`, { headers: techH, data: {} })) : 'no test';
  phase6.windDown = wind;
  // audit (platform admin)
  const actions = new Set();
  for (const et of ['lab_engagement', 'lab_sample', 'lab_shipment', 'lab_test', 'lab_result']) {
    const pg = await json(await api.get(`${BASE}/api/v1/admin/audit-logs?entity_type=${et}&from=${encodeURIComponent(p6Start)}&page_size=100`,
      { headers: await as('admin') }));
    pg.items.forEach((x) => actions.add(x.action));
  }
  phase6.audit = [...actions].sort();
  for (const x of [lm, lt, lq]) await x.ctx.close();

  // ---- Phase 7: calculation — the E2E project's locked DEMO methodology has no registered calculation module, so the analyst sees
  // the real blocker (CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE), the run becomes BLOCKED and the project stays MONITORING.
  const CALCV = `${BASE}/api/v1/calculations`;
  const p7Start = new Date(Date.now() - 2000).toISOString();
  const an = await signIn('analyst');
  const A = an.page;
  lastPage = A;
  await A.goto(`${BASE}/calculations?project=${projectId}`);   // needs only calculation.read (the analyst has no projects.read)
  await A.getByTestId('calc-blockers').waitFor();
  phase7.readinessBlocker = (await A.getByTestId('calc-blockers').innerText()).includes('CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE');
  phase7.labels = (await A.getByText('Calculated tCO2e — not verified, not issued').count()) > 0
    && (await A.getByTestId('demo-label').innerText()).includes('DEMO — not carbon accounting');
  await shot(A, '70-calc-readiness');
  await A.getByTestId('create-run').click();
  await A.locator('[data-run^="CALC-"]').first().waitFor();
  await A.locator('[data-run^="CALC-"]').first().click();
  await A.getByTestId('freeze').click();
  await A.getByTestId('run-blockers').waitFor();
  phase7.runBlocked = (await A.getByTestId('run-status').innerText()).trim() === 'Blocked'
    && (await A.getByTestId('run-blockers').innerText()).includes('NO_CALCULATION_MODULE');
  phase7.runLabel = (await A.getByTestId('calc-label').innerText()).includes('not verified, not issued');
  await shot(A, '71-calc-run-blocked');
  const anH = await as('analyst');
  const calcRuns = await json(await api.get(`${CALCV}/runs?project_id=${projectId}`, { headers: anH }));
  phase7.runCode = calcRuns[0].run_code;
  phase7.runStatus = calcRuns[0].status;
  phase7.netResult = calcRuns[0].net_result;
  phase7.modules = (await json(await api.get(`${CALCV}/modules`, { headers: anH }))).length;
  phase7.projectStatus = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).status;
  phase7.qaCanRead = (await api.get(`${CALCV}/runs/${calcRuns[0].id}`, { headers: qaH })).ok();
  phase7.valueRefused = (await api.post(`${CALCV}/runs`, { headers: anH, data: { project_id: projectId, monitoring_period_id: period.id,
    net_result: '999' } })).status() === 422;
  let outside7 = 0;
  for (const who of ['buyer', 'farmer', 'labtech']) {
    if ([403, 404].includes((await api.get(`${CALCV}/runs?project_id=${projectId}`, { headers: await as(who) })).status())) outside7++;
  }
  phase7.outsidersBlocked = outside7 === 3;
  const calcAudit = new Set();
  const pg7 = await json(await api.get(`${BASE}/api/v1/admin/audit-logs?entity_type=calculation_run&from=${encodeURIComponent(p7Start)}&page_size=100`,
    { headers: await as('admin') }));
  pg7.items.forEach((x) => calcAudit.add(x.action));
  phase7.audit = [...calcAudit].sort();
  await an.ctx.close();

  // ---- Phase 8A: internal pre-verification on the honest (blocked) path — a finding on the BLOCKED run (QA raises in the UI,
  // the analyst responds, QA resolves), no report for a non-APPROVED run, readiness blocked (no approved calculation), Niphad blocked.
  const p8Start = new Date(Date.now() - 2000).toISOString();
  const qs = await signIn('qa');
  const Q = qs.page;
  lastPage = Q;
  await Q.goto(`${BASE}/calculations/runs/${calcRuns[0].id}`);
  await Q.getByTestId('report-not-available').waitFor();
  phase8a.noReportForBlocked = true;
  await Q.getByRole('tab', { name: 'Findings' }).click();
  await pick(Q, 'finding-category', 'Methodology Issue');
  await Q.getByTestId('finding-title').fill('No calculation module registered');
  await Q.getByTestId('finding-description').fill('E2E: the locked DEMO methodology has no registered calculation module.');
  await Q.getByTestId('raise-finding').click();
  await Q.locator('[data-finding^="CFND-"]').first().waitFor();
  await shot(Q, '80-calc-finding');
  const fnd = (await json(await api.get(`${CALCV}/findings?project_id=${projectId}`, { headers: qaH })))[0];
  phase8a.finding = fnd.finding_code;
  phase8a.category = fnd.category_label;
  await json(await api.post(`${CALCV}/findings/${fnd.id}/respond`, { headers: anH, data: { response: 'E2E: a module needs an approved methodology.' } }));
  phase8a.findingStatus = (await json(await api.post(`${CALCV}/findings/${fnd.id}/resolve`, { headers: qaH,
    data: { note: 'E2E: acknowledged; stays blocked until a module exists' } }))).status;
  phase8a.reportRefused = await errCode(await api.post(`${CALCV}/runs/${calcRuns[0].id}/reports`, { headers: anH }));
  await Q.goto(`${BASE}/calculations?project=${projectId}`);
  await Q.getByTestId('readiness-blockers').waitFor();
  phase8a.readinessLabel = (await Q.getByTestId('readiness-label').innerText()).includes('Internal readiness — not verification');
  phase8a.readinessBlocked = (await Q.getByTestId('readiness-blockers').innerText()).includes('NO_APPROVED_CALCULATION');
  await shot(Q, '81-calc-readiness');
  phase8a.createRefused = await errCode(await api.post(`${CALCV}/projects/${projectId}/verification-readiness`, { headers: anH,
    data: { monitoring_period_id: period.id } }));
  const calcProjects = await json(await api.get(`${CALCV}/projects`, { headers: anH }));
  const niphad = calcProjects.find((x) => x.name.startsWith('Niphad'));
  const nv = await json(await api.get(`${CALCV}/projects/${niphad.id}/verification-readiness?monitoring_period_id=${niphad.periods[0].id}`,
    { headers: anH }));
  phase8a.niphad = `${nv.blockers.map((b) => b.code).join(',')} | ${nv.calculation_blockers[0].code} ${nv.calculation_blockers[0].reason}`;
  let outside8 = 0;
  for (const who of ['vvb', 'buyer', 'farmer', 'labtech']) {
    if ([403, 404].includes((await api.get(`${CALCV}/findings?project_id=${projectId}`, { headers: await as(who) })).status())) outside8++;
  }
  phase8a.outsidersBlocked = outside8 === 4;
  phase8a.projectStatus = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).status;
  const a8 = new Set();
  const pg8 = await json(await api.get(`${BASE}/api/v1/admin/audit-logs?entity_type=calculation_finding&from=${encodeURIComponent(p8Start)}&page_size=100`,
    { headers: await as('admin') }));
  pg8.items.forEach((x) => a8.add(x.action));
  phase8a.audit = [...a8].sort();
  await qs.ctx.close();

  // ---- Phase 8B: VVB / ACVA — assignment-only DEMO flow. No READY package exists (no calculation module), so nothing is submitted and
  // no decision, report or verified quantity is recorded (nothing is faked). The PM proposes DEMO-VVB-C for the E2E period (UI), the VVB
  // accepts with a COI declaration in its own workspace (UI), submission is refused; Niphad likewise; the VVB API is isolated.
  const VER = `${BASE}/api/v1/verification`;
  const VVBA = `${BASE}/api/v1/vvb`;
  const COI = 'E2E: no conflict of interest with the project, its developer or its farmers.';
  const p8bStart = new Date(Date.now() - 2000).toISOString();
  const pmS = await signIn('pm');
  const PM = pmS.page;
  lastPage = PM;
  await PM.goto(`${BASE}/mrv/projects/${projectId}?tab=verification`);
  await PM.getByTestId('calculated-label').waitFor();
  phase8b.labels = (await PM.getByTestId('calculated-label').innerText()).includes('Calculated tCO2e — not verified, not issued');
  await pick(PM, 'vvb-org', 'Verification Body C (DEMO)');
  await PM.getByTestId('propose-assignment').click();
  await PM.locator('[data-assignment^="VAS-"]').first().waitFor();
  await shot(PM, '90-verification-proposed');
  const asg = (await json(await api.get(`${VER}/projects/${projectId}/assignments?period_id=${period.id}`, { headers: pmH })))[0];
  phase8b.assignment = asg.assignment_code;
  phase8b.proposed = asg.status;
  const vvbS = await signIn('vvb');
  const VV = vvbS.page;
  lastPage = VV;
  await VV.goto(`${BASE}/vvb`);
  await VV.locator(`[data-assignment="${asg.assignment_code}"] a`).click();
  await VV.getByTestId('coi-input').fill(COI);
  await VV.getByTestId('accept-assignment').click();
  await VV.getByTestId('coi').waitFor();
  await VV.getByTestId('no-package').waitFor();
  await shot(VV, '91-vvb-assignment-accepted');
  const vvbH = await as('vvb');
  const acc = await json(await api.get(`${VVBA}/assignments/${asg.id}`, { headers: vvbH }));
  phase8b.accepted = `${acc.status} ${acc.coi_declaration === COI ? 'COI' : 'no COI'}`;
  phase8b.submitRefused = await errCode(await api.post(`${VER}/assignments/${asg.id}/submit`, { headers: pmH }));
  const pv = await json(await api.get(`${VER}/projects/${projectId}/periods/${period.id}`, { headers: pmH }));
  phase8b.noDecision = pv.current_decision === null && pv.assignments.every((x) => !x.decisions.length && !x.submissions.length);
  phase8b.projectStatus = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).status;
  // Niphad (DEMO): assignment and COI allowed; submission blocked because its package is not READY (idempotent across runs)
  const nPeriod = niphad.periods[0].id;
  let nAsg = (await json(await api.get(`${VER}/projects/${niphad.id}/assignments?period_id=${nPeriod}`, { headers: pmH })))
    .find((x) => ['PROPOSED', 'ACCEPTED'].includes(x.status));
  if (!nAsg) {
    const vorg = (await json(await api.get(`${VER}/projects/${niphad.id}/vvb-organizations`, { headers: pmH }))).find((o) => o.code === 'DEMO-VVB-C');
    nAsg = await json(await api.post(`${VER}/projects/${niphad.id}/assignments`, { headers: pmH,
      data: { monitoring_period_id: nPeriod, vvb_organization_id: vorg.id } }));
  }
  if (nAsg.status === 'PROPOSED') nAsg = await json(await api.post(`${VVBA}/assignments/${nAsg.id}/accept`, { headers: vvbH, data: { coi_declaration: COI } }));
  phase8b.niphad = `${nAsg.status} | ${await errCode(await api.post(`${VER}/assignments/${nAsg.id}/submit`, { headers: pmH }))}`;
  // isolation: the VVB user gets no generic project / calculation / project-side verification / farmer / audit access
  let iso = 0;
  for (const url of [`${BASE}/api/v1/projects/${projectId}`, `${CALCV}/runs?project_id=${projectId}`, `${VER}/projects/${projectId}/assignments`,
    `${BASE}/api/v1/farmers`, `${BASE}/api/v1/admin/audit-logs`]) {
    if ([403, 404].includes((await api.get(url, { headers: vvbH })).status())) iso++;
  }
  phase8b.vvbIsolated = iso === 5;
  let notVvb = 0;
  for (const who of ['pm', 'analyst', 'buyer', 'farmer', 'labtech']) {
    if ((await api.get(`${VVBA}/assignments`, { headers: await as(who) })).status() === 403) notVvb++;
  }
  phase8b.nonVvbBlocked = notVvb === 5;
  phase8b.unknownSubmission = (await api.get(`${VVBA}/submissions/${require('crypto').randomUUID()}/package`, { headers: vvbH })).status();
  await VV.goto(`${BASE}/projects`);
  await VV.getByText("You don't have access to this page").waitFor();
  phase8b.vvbNav = (await VV.locator('nav a', { hasText: 'VVB workspace' }).count()) > 0 && !(await VV.locator('nav a', { hasText: 'Projects' }).count());
  const a8b = new Set();
  const pg8b = await json(await api.get(`${BASE}/api/v1/admin/audit-logs?entity_type=verification_assignment&from=${encodeURIComponent(p8bStart)}&page_size=100`,
    { headers: await as('admin') }));
  pg8b.items.forEach((x) => a8b.add(x.action));
  phase8b.audit = [...a8b].sort();
  for (const x of [pmS, vvbS]) await x.ctx.close();

  // ---- Phase 9A: registry & issuance — honest DEMO path only. No period is VERIFIED (no calculation module), so nothing can be submitted
  // to a registry and no credit exists; nothing is fabricated (no account, registration, submission, issuance or serial number is created).
  const REG = `${BASE}/api/v1/registry`;
  const CRED = `${BASE}/api/v1/credits`;
  const pm9 = await signIn('pm');
  const P9 = pm9.page;
  lastPage = P9;
  await P9.goto(`${BASE}/mrv/projects/${projectId}?tab=registry`);
  await P9.getByTestId('demo-registry').waitFor();
  phase9a.demoNote = (await P9.getByTestId('demo-registry').innerText()).includes('DEMO — no registry issuance');
  phase9a.cards = (await P9.getByTestId('qty-calculated').innerText()).includes('Calculated tCO2e — not verified, not issued')
    && (await P9.getByTestId('qty-verified').innerText()).includes('VVB-stated verified quantity')
    && (await P9.getByTestId('qty-issued').innerText()).includes('Registry-issued credits');
  phase9a.blocker = (await P9.getByTestId('registry-blockers').first().innerText()).includes('NO_VERIFIED_DECISION');
  await shot(P9, '95-registry-demo-blocked');
  phase9a.createRefused = await errCode(await api.post(`${REG}/projects/${projectId}/submissions`, { headers: pmH,
    data: { monitoring_period_id: period.id, registry_account_id: require('crypto').randomUUID() } }));
  phase9a.niphadRefused = await errCode(await api.post(`${REG}/projects/${niphad.id}/submissions`, { headers: pmH,
    data: { monitoring_period_id: niphad.periods[0].id, registry_account_id: require('crypto').randomUUID() } }));
  phase9a.demoRegistry = (await json(await api.get(`${REG}/organizations?environment=DEMO`, { headers: pmH }))).map((o) => o.name).join(',');
  phase9a.projectStatus = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).status;
  await pm9.ctx.close();
  const rg = await signIn('registry');
  const RG = rg.page;
  lastPage = RG;
  phase9a.registryNav = (await RG.locator('nav a', { hasText: 'Registry' }).count()) > 0 && (await RG.locator('nav a', { hasText: 'Issued credits' }).count()) > 0;
  await RG.goto(`${BASE}/registry`);
  await RG.getByTestId('registry-project').waitFor();
  phase9a.registryPage = true;
  await RG.goto(`${BASE}/credits`);
  await RG.getByTestId('no-credits').waitFor();
  phase9a.creditsEmpty = true;
  await shot(RG, '96-credits-none');
  await rg.ctx.close();
  phase9a.noDemoCredits = (await json(await api.get(`${CRED}/batches`, { headers: await as('credits') }))).length === 0;
  let out9 = 0;
  for (const who of ['vvb', 'buyer', 'farmer', 'labtech']) {
    const h = await as(who);
    if ((await api.get(`${REG}/accounts`, { headers: h })).status() === 403 && (await api.get(`${CRED}/batches`, { headers: h })).status() === 403) out9++;
  }
  phase9a.outsidersBlocked = out9 === 4;
  phase9a.vvbNoRegistry = (await api.get(`${REG}/projects/${projectId}/periods/${period.id}`, { headers: await as('vvb') })).status() === 403;

  // ---- Phase 9B: credit ledger — honest DEMO path. DEMO has no registry-issued batch, so nothing is opened, reserved, transferred or
  // retired; the ledger and holder views state "DEMO — no registry-issued credits" and every movement on a non-existent batch is refused.
  const LEDGER_DEMO = 'DEMO — no registry-issued credits';
  const cm = await signIn('credits');
  const CM = cm.page;
  lastPage = CM;
  phase9b.ledgerNav = (await CM.locator('nav a', { hasText: 'Credit ledger' }).count()) > 0;
  await CM.goto(`${BASE}/ledger`);
  await CM.getByTestId('ledger-demo-note').waitFor();
  phase9b.demoNote = (await CM.getByTestId('ledger-demo-note').innerText()).includes(LEDGER_DEMO);
  const head9 = await CM.getByTestId('ledger-inventory').locator('thead').innerText();
  phase9b.columns = ['Issued (registry)', 'Available', 'Reserved', 'Pending transfer', 'Pending retirement', 'Transferred out', 'Retired']
    .every((h) => head9.includes(h));
  phase9b.ledgerEmpty = (await CM.getByTestId('no-ledger-batches').count()) === 1;
  await shot(CM, '97-ledger-demo');
  await cm.ctx.close();
  const cmH = await as('credits');
  const inv9 = await json(await api.get(`${CRED}/inventory`, { headers: cmH }));
  phase9b.inventoryEmpty = inv9.batches.length === 0 && inv9.demo_note === LEDGER_DEMO;
  const ghost = require('crypto').randomUUID();
  const until = new Date(Date.now() + 86400000).toISOString();
  phase9b.openRefused = await errCode(await api.post(`${CRED}/batches/${ghost}/open`, { headers: { ...cmH, 'Idempotency-Key': `e2e-${ghost}` } }));
  phase9b.reserveRefused = await errCode(await api.post(`${CRED}/reservations`, { headers: cmH,
    data: { batch_id: ghost, owner_organization_id: ghost, quantity: 1, purpose: 'E2E reservation', expires_at: until } }));
  phase9b.transferRefused = await errCode(await api.post(`${CRED}/transfers`, { headers: cmH,
    data: { kind: 'INTERNAL', batch_id: ghost, sender_organization_id: ghost, recipient_organization_id: require('crypto').randomUUID(), quantity: 1 } }));
  phase9b.retireRefused = await errCode(await api.post(`${CRED}/retirements`, { headers: cmH,
    data: { batch_id: ghost, owner_organization_id: ghost, quantity: 1, beneficiary: 'E2E', reason: 'E2E retirement' } }));
  phase9b.balanceRejected = await errCode(await api.post(`${CRED}/reservations`, { headers: cmH,
    data: { batch_id: ghost, owner_organization_id: ghost, quantity: 1, purpose: 'E2E reservation', expires_at: until, available: 1000 } }));
  const by = await signIn('buyer');
  const BY = by.page;
  lastPage = BY;
  phase9b.holderNav = (await BY.locator('nav a', { hasText: 'My credits' }).count()) > 0
    && (await BY.locator('nav a', { hasText: 'Credit ledger' }).count()) === 0;
  await BY.goto(`${BASE}/holdings`);
  await BY.getByTestId('holdings-demo-note').waitFor();
  phase9b.holderDemoNote = (await BY.getByTestId('holdings-demo-note').innerText()).includes(LEDGER_DEMO);
  phase9b.holderEmpty = (await BY.getByTestId('no-holdings').count()) === 1;
  await shot(BY, '98-holdings-demo');
  await BY.goto(`${BASE}/ledger`);
  await BY.getByText("You don't have access to this page").waitFor();
  phase9b.holderNoLedger = (await api.get(`${CRED}/inventory`, { headers: await as('buyer') })).status() === 403;
  await by.ctx.close();
  let out9b = 0;
  for (const who of ['vvb', 'farmer', 'labtech', 'buyer']) {
    if ((await api.get(`${CRED}/inventory`, { headers: await as(who) })).status() === 403) out9b++;
  }
  phase9b.outsidersBlocked = out9b === 4;
  let nh9b = 0;
  for (const who of ['vvb', 'farmer', 'labtech', 'credits']) {
    if ((await api.get(`${CRED}/holdings`, { headers: await as(who) })).status() === 403) nh9b++;
  }
  phase9b.nonHoldersBlocked = nh9b === 4;

  // ---- Phase 10: marketplace — honest DEMO path. DEMO has no registry-issued credits, so nothing is listed, ordered or paid (no fake
  // listing, order, payment or purchase success). The buyer KYC workflow — which claims no external confirmation — is demonstrated on
  // DEMO-BUYER-D (the profile persists in the development database, so later runs find it already verified).
  const MKT = `${BASE}/api/v1/marketplace`;
  const MKT_DEMO = 'DEMO — no registry-issued credits; nothing is listed';
  const KYC_PDF = Buffer.from('%PDF-1.4\n%E2E DEMO buyer KYC document\n%%EOF\n');
  const bu = await signIn('buyer');
  const BU = bu.page;
  lastPage = BU;
  const buyerNav = (await BU.locator('nav a').allInnerTexts()).map((x) => x.replace(/\s+/g, ' ').trim());
  phase10.buyerNav = ['Marketplace', 'Orders', 'Buyer profile', 'My credits'].every((n) => buyerNav.some((x) => x.endsWith(n)))
    && !buyerNav.some((x) => x.endsWith('Payments') || x.endsWith('Listings') || x.endsWith('KYC review'));
  await BU.goto(`${BASE}/marketplace`);
  await BU.getByTestId('market-demo-note').waitFor();
  phase10.demoNote = (await BU.getByTestId('market-demo-note').innerText()).includes(MKT_DEMO);
  phase10.noListings = (await BU.getByTestId('no-listings').count()) === 1;
  await shot(BU, '99-marketplace-demo');
  const buyerH = await as('buyer');
  let prof = await json(await api.get(`${MKT}/buyer-profile`, { headers: buyerH }));
  if (!prof.profile || ['DRAFT', 'KYC_RETURNED'].includes(prof.profile.status)) {
    await BU.goto(`${BASE}/marketplace/profile`);
    await BU.getByTestId('buyer-profile-form').waitFor();
    await BU.getByLabel('Legal name').fill('Buyer D (DEMO)');
    await BU.getByTestId('save-profile').click();
    await BU.getByTestId('kyc-file').waitFor();
    await BU.getByTestId('kyc-file').setInputFiles({ name: 'kyc.pdf', mimeType: 'application/pdf', buffer: KYC_PDF });
    await BU.getByRole('button', { name: 'Upload', exact: true }).click();
    await BU.getByText('Buyer KYC document').first().waitFor();
    await BU.getByTestId('submit-kyc').click();
    await BU.getByTestId('kyc-status').getByText('KYC submitted').waitFor();
    await shot(BU, '99a-buyer-kyc-submitted');
    prof = await json(await api.get(`${MKT}/buyer-profile`, { headers: buyerH }));
  }
  await bu.ctx.close();
  const cp = await signIn('compliance');
  const CP = cp.page;
  lastPage = CP;
  phase10.complianceNav = (await CP.locator('nav a', { hasText: 'KYC review' }).count()) > 0;
  await CP.goto(`${BASE}/marketplace/kyc-review`);
  await CP.getByTestId('kyc-queue').waitFor();
  if (prof.profile.status === 'KYC_SUBMITTED') {
    await CP.locator('[data-org="DEMO-BUYER-D"]').getByRole('button', { name: 'Verify' }).click();
    await confirmReason(CP, 'Verify', 'E2E: DEMO buyer documents checked');
    phase10.kycUi = true;
  } else {
    phase10.kycUi = prof.profile.status === 'KYC_VERIFIED';
  }
  await CP.locator('[data-org="DEMO-BUYER-D"]').getByText('KYC verified').waitFor();
  await shot(CP, '99b-kyc-review');
  await cp.ctx.close();
  prof = await json(await api.get(`${MKT}/buyer-profile`, { headers: buyerH }));
  phase10.kyc = prof.profile.status;
  // a verified DEMO buyer still cannot buy anything: there is no listing; a request carrying a total / balance is rejected
  phase10.orderRefused = await errCode(await api.post(`${BASE}/api/v1/orders`, { headers: buyerH,
    data: { buyer_organization_id: prof.organization_id, items: [{ listing_id: require('crypto').randomUUID(), quantity: 1 }] } }));
  phase10.balanceRejected = await errCode(await api.post(`${BASE}/api/v1/orders`, { headers: buyerH,
    data: { buyer_organization_id: prof.organization_id, items: [{ listing_id: require('crypto').randomUUID(), quantity: 1 }], total: '1.00' } }));
  const bo = await json(await api.get(`${BASE}/api/v1/orders`, { headers: buyerH }));
  phase10.noOrders = bo.orders.length === 0 && bo.demo_note === MKT_DEMO;
  const fi = await signIn('finance');
  const FI = fi.page;
  lastPage = FI;
  phase10.financeNav = (await FI.locator('nav a', { hasText: 'Payments' }).count()) > 0 && (await FI.locator('nav a', { hasText: 'Listings' }).count()) > 0;
  await FI.goto(`${BASE}/payments`);
  await FI.getByTestId('no-payments').waitFor();
  phase10.noPayments = (await json(await api.get(`${BASE}/api/v1/payments`, { headers: await as('finance') }))).length === 0;
  await shot(FI, '99c-payments-none');
  await fi.ctx.close();
  const cm10H = await as('credits');
  const devOrg = (await json(await api.get(`${BASE}/api/v1/projects/${projectId}`, { headers: pmH }))).organization_id;
  phase10.listingRefused = await errCode(await api.post(`${MKT}/listings`, { headers: cm10H, data: { seller_organization_id: devOrg,
    batch_id: require('crypto').randomUUID(), title: 'E2E', listed_quantity: 1, unit_price: '1.00', currency: 'INR', payment_window_hours: 1 } }));
  const mine = await json(await api.get(`${MKT}/listings?mine=true`, { headers: cm10H }));
  phase10.sellerEmpty = mine.listings.length === 0 && mine.demo_note === MKT_DEMO;
  let out10 = 0;
  for (const who of ['vvb', 'farmer', 'labtech']) {
    const h = await as(who);
    const codes = [];
    for (const url of [`${MKT}/listings`, `${BASE}/api/v1/orders`, `${BASE}/api/v1/payments`, `${MKT}/buyer-profiles`]) {
      codes.push((await api.get(url, { headers: h })).status());
    }
    if (codes.every((c) => c === 403)) out10++;
  }
  phase10.outsidersBlocked = out10 === 3;
  phase10.noFakeData = phase10.noOrders && phase10.noPayments && phase10.sellerEmpty && phase10.noListings;

  // ---- Phase 11: revenue, settlements, payouts — honest DEMO path. DEMO has no registry-issued credits, so no revenue is recognized and no
  // cost, sharing configuration, settlement, entitlement or payout is created (every DEMO write is refused); pages show the DEMO note and
  // configuration-required / empty states. No request may carry a revenue or payout amount.
  const FIN = `${BASE}/api/v1`;
  const FIN_DEMO = 'DEMO — no registry-issued credits; no revenue, cost, entitlement or payout exists in DEMO';
  const uuid = () => require('crypto').randomUUID();
  const fn = await signIn('finance');
  const FN = fn.page;
  lastPage = FN;
  phase11.financeNav = (await FN.locator('nav a', { hasText: 'Revenue & costs' }).count()) > 0
    && (await FN.locator('nav a', { hasText: 'Settlements' }).count()) > 0 && (await FN.locator('nav a', { hasText: 'Payouts' }).count()) > 0;
  await FN.goto(`${BASE}/finance/revenue`);
  await FN.getByTestId('fin-demo-note').waitFor();
  phase11.demoNote = (await FN.getByTestId('fin-demo-note').innerText()).includes(FIN_DEMO);
  await FN.locator('[data-testid="fin-no-revenue"], [data-testid="fin-no-project"]').first().waitFor();
  await shot(FN, '9a-finance-revenue-demo');
  await FN.goto(`${BASE}/finance/settlements`);
  await FN.locator('[data-testid="no-runs"]').waitFor();
  await FN.locator('[data-testid="config-required"], [data-testid="fin-no-project"]').first().waitFor();
  phase11.configRequired = (await FN.getByTestId('config-required').count()) === 1 || (await FN.getByTestId('fin-no-project').count()) === 1;
  await shot(FN, '9b-finance-settlements-config-required');
  await FN.goto(`${BASE}/finance/payouts`);
  await FN.getByTestId('no-payouts').waitFor();
  await shot(FN, '9c-finance-payouts-demo');
  await fn.ctx.close();
  const finH = await as('finance');
  const sum = await json(await api.get(`${FIN}/revenue/summary`, { headers: finH }));
  const rev = await json(await api.get(`${FIN}/revenue?project_id=${projectId}`, { headers: pmH }));
  phase11.revenueEmpty = sum.revenue.length === 0 && sum.demo_note === FIN_DEMO && Array.isArray(rev) && rev.length === 0;
  const runs = await json(await api.get(`${FIN}/settlements`, { headers: finH }));
  const pays = await json(await api.get(`${FIN}/payouts`, { headers: finH }));
  const cases = await json(await api.get(`${FIN}/payouts/adjustments`, { headers: finH }));
  phase11.payoutsEmpty = runs.length === 0 && pays.length === 0 && cases.length === 0;
  phase11.sharingRefused = await errCode(await api.post(`${FIN}/revenue-share`, { headers: pmH, data: { project_id: projectId,
    farmer_share_pct: '40', deduct_approved_costs: false, rounding_mode: 'DOWN', effective_from: '2026-01-01', source_reference: 'E2E DEMO' } }));
  phase11.costRefused = await errCode(await api.post(`${FIN}/costs`, { headers: pmH, data: { project_id: projectId, category: 'E2E',
    description: 'E2E DEMO cost', amount: '1.00', currency: 'INR', incurred_on: '2026-09-01' } }));
  const period11 = (await json(await api.get(`${FIN}/revenue/projects`, { headers: pmH }))).find((x) => x.id === projectId)?.periods?.[0]?.id ?? uuid();
  phase11.settlementRefused = await errCode(await api.post(`${FIN}/settlements`, { headers: finH, data: { project_id: projectId,
    monitoring_period_id: period11, currency: 'INR', revenue_share_version_id: uuid(), allocation_version_id: uuid() } }));
  phase11.amountRejected = await errCode(await api.post(`${FIN}/revenue/recognize`, { headers: finH,
    data: { order_item_id: uuid(), amount: '1000.00' } }));
  const fa = await signIn('farmer');
  const FA = fa.page;
  lastPage = FA;
  phase11.farmerNav = (await FA.locator('nav a', { hasText: 'My payouts' }).count()) > 0
    && (await FA.locator('nav a', { hasText: 'Settlements' }).count()) === 0;
  await FA.goto(`${BASE}/me/payouts`);
  await FA.getByTestId('no-my-payouts').waitFor();
  const mp = await json(await api.get(`${FIN}/payouts/me`, { headers: await as('farmer') }));
  phase11.farmerEmpty = mp.payouts.length === 0;
  await shot(FA, '9d-farmer-my-payouts');
  await FA.goto(`${BASE}/finance/payouts`);
  await FA.getByText("You don't have access to this page").waitFor();
  await fa.ctx.close();
  let out11 = 0;
  for (const who of ['vvb', 'labtech', 'buyer']) {
    const h = await as(who);
    const codes = [];
    for (const url of [`${FIN}/revenue/summary`, `${FIN}/settlements`, `${FIN}/payouts`, `${FIN}/payouts/adjustments`]) {
      codes.push((await api.get(url, { headers: h })).status());
    }
    if (codes.every((c) => c === 403)) out11++;
  }
  phase11.outsidersBlocked = out11 === 3;
  phase11.farmerBlocked = (await api.get(`${FIN}/payouts`, { headers: await as('farmer') })).status() === 403;
  phase11.noFakeData = phase11.revenueEmpty && phase11.payoutsEmpty && phase11.farmerEmpty;

  // ---- Phase 12A: background jobs — operations view for the Platform Administrator. SQL Server is the record; without Redis / a worker
  // (this development machine) a triggered job stays QUEUED with its publication error and lazy expiry keeps every workflow correct.
  // Only allow-listed maintenance tasks exist; nothing financial is ever a job; DEMO jobs act only on DEMO records.
  const JOBS = `${BASE}/api/v1/jobs`;
  const ad = await signIn('admin');
  const AD = ad.page;
  lastPage = AD;
  phase12.jobsNav = (await AD.locator('nav a', { hasText: 'Background jobs' }).count()) > 0;
  await AD.goto(`${BASE}/admin/jobs`);
  await AD.getByTestId('jobs-status').waitFor();
  phase12.statusPanel = true;
  phase12.demoNote = (await AD.getByTestId('jobs-demo-note').innerText()).startsWith('DEMO');
  const adH = await as('admin');
  const st12 = await json(await api.get(`${JOBS}/status`, { headers: adH }));
  phase12.brokerHonest = ['NOT_CONFIGURED', 'UNREACHABLE', 'REACHABLE'].includes(st12.broker)
    && (await AD.getByTestId('jobs-worker').innerText()).includes(st12.worker_alive ? 'Heartbeat' : 'No heartbeat');
  const reg = await json(await api.get(`${JOBS}/registry`, { headers: adH }));
  phase12.registry = reg.length;
  phase12.noFinanceTasks = reg.every((t) => !/revenue|settle|payout|payment|refund|approve|reconcil|issu|retire|transfer/i.test(`${t.job_type} ${t.task_name}`));
  const key12 = `e2e-${require('crypto').randomUUID()}`;
  const trig = await api.post(`${JOBS}/trigger`, { headers: { ...adH, 'Idempotency-Key': key12 }, data: { job_type: 'EXPIRY_MARKETPLACE_OBJECTS' } });
  const job12 = await json(trig);
  phase12.triggered = `${trig.status()} ${job12.environment} ${job12.status}`;
  phase12.replay = (await json(await api.post(`${JOBS}/trigger`, { headers: { ...adH, 'Idempotency-Key': key12 },
    data: { job_type: 'EXPIRY_MARKETPLACE_OBJECTS' } }))).id === job12.id;
  await AD.goto(`${BASE}/admin/jobs`);
  const row12 = AD.locator(`[data-job="${job12.job_code}"]`);
  await row12.waitFor();
  await shot(AD, '9e-admin-background-jobs');
  if ((await json(await api.get(`${JOBS}/${job12.id}`, { headers: adH }))).status === 'QUEUED') {
    await row12.getByRole('button', { name: 'Cancel' }).click();
    await confirmReason(AD, 'Cancel job', 'E2E: demonstration job not needed');
    await row12.getByText('Cancelled').waitFor();
  }
  const after12 = await json(await api.get(`${JOBS}/${job12.id}`, { headers: adH }));
  phase12.cancelledUi = ['CANCELLED', 'SUCCEEDED'].includes(after12.status);
  await AD.locator('[data-testid="jobs"] a', { hasText: job12.job_code }).click();
  await AD.getByTestId('job-detail').waitFor();
  await shot(AD, '9f-admin-background-job-detail');
  await ad.ctx.close();
  phase12.arbitraryRefused = await errCode(await api.post(`${JOBS}/trigger`, { headers: adH, data: { job_type: 'os.system' } }));
  phase12.retryRefused = await errCode(await api.post(`${JOBS}/${job12.id}/retry`, { headers: adH, data: { reason: 'E2E: not failed' } }));
  let out12 = 0;
  for (const who of ['pm', 'finance', 'farmer', 'buyer', 'vvb']) {
    const h = await as(who);
    const codes = [];
    for (const url of [JOBS, `${JOBS}/status`, `${JOBS}/registry`, `${JOBS}/${job12.id}`]) codes.push((await api.get(url, { headers: h })).status());
    codes.push((await api.post(`${JOBS}/trigger`, { headers: h, data: { job_type: 'RETENTION_PURGE' } })).status());
    if (codes.every((c) => c === 403)) out12++;
  }
  phase12.outsidersBlocked = out12 === 5;
  const aud12 = await json(await api.get(`${BASE}/api/v1/admin/audit-logs?entity_type=background_job&entity_id=${job12.id}`, { headers: adH }));
  phase12.audit = [...new Set(aud12.items.map((a) => a.action))].sort();

  // ---- Phase 12B-I: document safety. This development machine has no antivirus engine: the signature scanner blocks EICAR and records
  // everything else NOT_SCANNED (never "clean"). A security administrator quarantines a DEMO document; release is refused because the
  // release rescan is not CLEAN (a test-signature result never is). Every step is audited; nothing is faked.
  const DOCS = `${BASE}/api/v1/evidence/documents`;
  const pmH12 = await as('pm');
  const farmers12 = await json(await api.get(`${BASE}/api/v1/farmers`, { headers: pmH12 }));
  const farmer12 = (farmers12.items ?? farmers12)[0];
  const up12 = await json(await api.post(`${BASE}/api/v1/farmers/${farmer12.id}/documents`, { headers: pmH12,
    multipart: { category: 'OTHER', title: 'E2E 12B safety check', file: { name: 'e2e-12b.pdf', mimeType: 'application/pdf', buffer: PDF } } }));
  phase12b.scanState = (await json(await api.get(`${DOCS}/${up12.id}`, { headers: pmH12 }))).scan_state;
  const EICAR = 'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*';
  phase12b.eicarRefused = await errCode(await api.post(`${BASE}/api/v1/farmers/${farmer12.id}/documents`, { headers: pmH12,
    multipart: { category: 'OTHER', title: 'EICAR', file: { name: 'eicar.pdf', mimeType: 'application/pdf', buffer: Buffer.from(`%PDF-1.4
${EICAR}`) } } }));
  const secH = await as('security');
  const q12 = await api.post(`${DOCS}/${up12.id}/quarantine`, { headers: secH, data: { reason: 'E2E: security hold for review' } });
  phase12b.quarantined = `${q12.status()} ${(await q12.json()).status}`;
  phase12b.downloadBlocked = await errCode(await api.get(`${DOCS}/${up12.id}/download`, { headers: pmH12 }));
  const se = await signIn('security');
  const SE = se.page;
  lastPage = SE;
  phase12b.quarantineNav = (await SE.locator('nav a', { hasText: 'Document quarantine' }).count()) > 0;
  await SE.goto(`${BASE}/admin/quarantine`);
  const qRow = SE.locator(`[data-doc="${up12.id}"]`);
  await qRow.waitFor();
  phase12b.quarantinePage = (await qRow.getByRole('button', { name: 'Release' }).count()) === 1;
  await qRow.locator('a').click();
  await SE.getByTestId('scan-history').getByText('NOT_SCANNED').first().waitFor();
  phase12b.historyUi = true;
  await shot(SE, '9g-security-document-quarantine');
  await se.ctx.close();
  phase12b.releaseRefused = await errCode(await api.post(`${DOCS}/${up12.id}/release`, { headers: secH, data: { reason: 'E2E: attempt release' } }));
  phase12b.stillQuarantined = (await json(await api.get(`${DOCS}/${up12.id}/scans`, { headers: secH }))).map((x) => x.result).join(',') === 'NOT_SCANNED,NOT_SCANNED'
    && (await json(await api.get(`${DOCS}/quarantined`, { headers: secH }))).some((d) => d.id === up12.id);
  let out12b = 0;
  for (const who of ['pm', 'finance', 'farmer', 'buyer', 'vvb']) {
    const h = await as(who);
    const codes = [(await api.get(`${DOCS}/quarantined`, { headers: h })).status(), (await api.get(`${DOCS}/${up12.id}/scans`, { headers: h })).status(),
      (await api.post(`${DOCS}/${up12.id}/release`, { headers: h, data: { reason: 'E2E: not allowed' } })).status()];
    if (codes.every((c) => c === 403)) out12b++;
  }
  phase12b.outsidersBlocked = out12b === 5;
  phase12b.adminNoManage = `${(await api.get(`${DOCS}/quarantined`, { headers: adH })).status()} ${(await api.post(`${DOCS}/${up12.id}/rescan`, { headers: adH })).status()}`;
  const aud12b = await json(await api.get(`${BASE}/api/v1/admin/audit-logs?entity_id=${farmer12.id}`, { headers: adH }));
  phase12b.audit = [...new Set(aud12b.items.map((a) => a.action))].filter((a) => a.startsWith('DOCUMENT_')).sort();
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
  await b.page.goto(`${BASE}/laboratory`);
  await b.page.getByText("You don't have access to this page").waitFor();
  phase6.buyerUiBlocked = !(await b.page.locator('nav a', { hasText: 'Laboratory' }).count());
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
  await f.page.goto(`${BASE}/laboratory`);
  await f.page.getByText("You don't have access to this page").waitFor();
  phase6.farmerUiBlocked = true;
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
  console.log('phase 6:', JSON.stringify(phase6));
  console.log('phase 7:', JSON.stringify(phase7));
  console.log('phase 8A:', JSON.stringify(phase8a));
  console.log('phase 8B:', JSON.stringify(phase8b));
  console.log('phase 9A:', JSON.stringify(phase9a));
  console.log('phase 9B:', JSON.stringify(phase9b));
  console.log('phase 10:', JSON.stringify(phase10));
  console.log('phase 11:', JSON.stringify(phase11));
  console.log('phase 12A:', JSON.stringify(phase12));
  console.log('phase 12B-I:', JSON.stringify(phase12b));

  await browser.close();
  // One 401 per session is expected: the silent session-restore attempt before sign-in.
  // Expected: one 401 per session (silent session restore), and the 409 of the deliberately blocked Phase 7 freeze.
  const real = problems.filter((p) => !p.includes('status of 401') && !(p.includes('status of 409') && p.includes('/freeze')));
  console.log(real.length ? 'PROBLEMS:\n' + real.join('\n') : 'OK: no unexpected console errors or 5xx responses');
  const p2ok = phase2.pmPolygon > 0 && phase2.overlapFlag && /ha/.test(phase2.drawnArea) && phase2.farmerFarms >= 2;
  const missingAudit = REQUIRED_AUDIT.filter((a) => !phase3.audit.includes(a));
  if (missingAudit.length) console.log('missing audit events:', missingAudit);
  const p3ok = phase3.demoProjects >= 2 && /ha/.test(phase3.areaText) && phase3.boundaryShapes >= 2 && phase3.status === 'ELIGIBILITY_REVIEW'
    && phase3.historyOk && !missingAudit.length && phase3.farmerProjects >= 1 && phase3.buyerBlocked && phase3.tiles;
  // farmer nav: Dashboard, My farmer profile, My farms, My projects, My payouts (Phase 11)
  const missingP4 = REQUIRED_AUDIT_P4.filter((a) => !phase4.audit.includes(a));
  if (missingP4.length) console.log('missing phase 4 audit events:', missingP4);
  const p4ok = phase4.catalog && phase4.approvedReadOnly && phase4.candidates >= 2 && phase4.recommended && /version/.test(phase4.locked)
    && /DEMO-CCTS-SOIL/.test(phase4.demoLock) && !missingP4.length;
  const missingP5 = REQUIRED_AUDIT_P5.filter((a) => !phase5.audit.includes(a));
  if (missingP5.length) console.log('missing phase 5 audit events:', missingP5);
  const p5ok = phase5.dashboard && phase5.planApproved && phase5.periodOpen && phase5.points === 2 && phase5.assigned
    && /^FIELD-\d{4}-\d{6}$/.test(phase5.collected) && phase5.accepted === 2 && phase5.qaFails === 0 && phase5.datasetApproved
    && phase5.periodStatus === 'APPROVED' && phase5.projectStatus === 'MONITORING' && phase5.buyerBlocked && phase5.farmerBlocked && !missingP5.length;
  const missingP6 = REQUIRED_AUDIT_P6.filter((a) => !phase6.audit.includes(a));
  if (missingP6.length) console.log('missing phase 6 audit events:', missingP6);
  const w = phase6.windDown;
  const p6ok = phase6.engagement === 'ACTIVE' && /^SMP-\d{4}-\d{6}$/.test(phase6.sample) && phase6.tests >= 1 && /^SHP-\d{4}-\d{6}$/.test(phase6.shipment)
    && phase6.unitPrefilled !== '' && phase6.qaFails === 0 && phase6.approved === 'APPROVED' && phase6.lineage && phase6.analysisStatus === 'ANALYSED'
    && phase6.labRestricted && phase6.buyerFarmerBlocked && phase6.buyerUiBlocked && phase6.farmerUiBlocked
    && phase6.sod === '403 SEPARATION_OF_DUTIES' && phase6.retest === 'SUPERSEDED/APPROVED'
    && w.receiptAllowed && w.newShipment === '409 ENGAGEMENT_NOT_ACTIVE' && w.retest === '409 ENGAGEMENT_NOT_ACTIVE'
    && w.newTestStart === '409 ENGAGEMENT_NOT_ACTIVE' && w.endAgain === '409 ENGAGEMENT_ENDED' && w.approvedStillVisible && !missingP6.length;
  const p7ok = phase7.readinessBlocker && phase7.labels && phase7.runBlocked && phase7.runLabel && /^CALC-\d{4}-\d{6}$/.test(phase7.runCode)
    && phase7.runStatus === 'BLOCKED' && phase7.netResult === null && phase7.modules === 0 && phase7.projectStatus === 'MONITORING'
    && phase7.qaCanRead && phase7.valueRefused && phase7.outsidersBlocked
    && ['CALCULATION_RUN_CREATED', 'CALCULATION_BLOCKED'].every((a) => phase7.audit.includes(a));
  const p8ok = phase8a.noReportForBlocked && /^CFND-\d{4}-\d{6}$/.test(phase8a.finding) && phase8a.category === 'Methodology Issue'
    && phase8a.findingStatus === 'RESOLVED' && phase8a.reportRefused === '409 RUN_NOT_APPROVED' && phase8a.readinessLabel && phase8a.readinessBlocked
    && phase8a.createRefused === '409 NO_APPROVED_CALCULATION'
    && phase8a.niphad === 'NO_APPROVED_CALCULATION | CONFIGURATION_REQUIRED NO_CALCULATION_MODULE'
    && phase8a.outsidersBlocked && phase8a.projectStatus === 'MONITORING'
    && ['CALCULATION_FINDING_RAISED', 'CALCULATION_FINDING_RESPONDED', 'CALCULATION_FINDING_RESOLVED'].every((a) => phase8a.audit.includes(a));
  const p8bok = phase8b.labels && /^VAS-\d{4}-\d{6}$/.test(phase8b.assignment) && phase8b.proposed === 'PROPOSED' && phase8b.accepted === 'ACCEPTED COI'
    && phase8b.submitRefused === '409 NO_READY_PACKAGE' && phase8b.noDecision && phase8b.projectStatus === 'MONITORING'
    && phase8b.niphad === 'ACCEPTED | 409 NO_READY_PACKAGE' && phase8b.vvbIsolated && phase8b.nonVvbBlocked && phase8b.unknownSubmission === 404
    && phase8b.vvbNav
    && ['VERIFICATION_ASSIGNMENT_PROPOSED', 'VERIFICATION_ASSIGNMENT_ACCEPTED', 'VERIFICATION_COI_DECLARED'].every((a) => phase8b.audit.includes(a));
  const p9ok = phase9a.demoNote && phase9a.cards && phase9a.blocker && phase9a.createRefused === '409 NO_VERIFIED_DECISION'
    && phase9a.niphadRefused === '409 NO_VERIFIED_DECISION' && phase9a.registryNav && phase9a.registryPage && phase9a.creditsEmpty
    && phase9a.noDemoCredits && phase9a.demoRegistry === 'Carbon Registry R (DEMO)' && phase9a.outsidersBlocked && phase9a.vvbNoRegistry
    && phase9a.projectStatus === 'MONITORING';
  const p9bok = phase9b.ledgerNav && phase9b.demoNote && phase9b.columns && phase9b.ledgerEmpty && phase9b.inventoryEmpty
    && phase9b.openRefused.startsWith('404') && phase9b.reserveRefused.startsWith('404') && phase9b.transferRefused.startsWith('404')
    && phase9b.retireRefused.startsWith('404') && phase9b.balanceRejected.startsWith('422') && phase9b.holderNav && phase9b.holderDemoNote
    && phase9b.holderEmpty && phase9b.holderNoLedger && phase9b.outsidersBlocked && phase9b.nonHoldersBlocked;
  const p10ok = phase10.buyerNav && phase10.demoNote && phase10.noListings && phase10.kyc === 'KYC_VERIFIED' && phase10.kycUi
    && phase10.orderRefused === '404 LISTING_NOT_FOUND' && phase10.balanceRejected.startsWith('422') && phase10.noOrders && phase10.financeNav
    && phase10.noPayments && phase10.listingRefused === '404 CREDIT_BATCH_NOT_FOUND' && phase10.sellerEmpty && phase10.complianceNav && phase10.outsidersBlocked
    && phase10.noFakeData;
  const p11ok = phase11.financeNav && phase11.demoNote && phase11.revenueEmpty && phase11.configRequired && phase11.payoutsEmpty
    && phase11.sharingRefused === '409 DEMO_FINANCE_NOT_ALLOWED' && phase11.costRefused === '409 DEMO_FINANCE_NOT_ALLOWED'
    && phase11.settlementRefused === '409 DEMO_FINANCE_NOT_ALLOWED' && phase11.amountRejected.startsWith('422') && phase11.farmerNav
    && phase11.farmerEmpty && phase11.outsidersBlocked && phase11.farmerBlocked && phase11.noFakeData;
  const p12ok = phase12.jobsNav && phase12.statusPanel && phase12.demoNote && phase12.brokerHonest && phase12.registry === 5
    && /^201 DEMO (QUEUED|CLAIMED|RUNNING|SUCCEEDED)$/.test(phase12.triggered) && phase12.replay && phase12.cancelledUi
    && phase12.arbitraryRefused === '422 TASK_NOT_TRIGGERABLE' && phase12.retryRefused === '409 JOB_NOT_RETRYABLE' && phase12.outsidersBlocked
    && phase12.noFinanceTasks && phase12.audit.includes('JOB_CREATED')
    && (after12.status === 'CANCELLED' ? phase12.audit.includes('JOB_CANCELLED') : phase12.audit.includes('JOB_SUCCEEDED'));
  const p12bok = phase12b.scanState === 'NOT_SCANNED' && phase12b.eicarRefused === '422 MALWARE_DETECTED' && phase12b.quarantined === '200 QUARANTINED'
    && phase12b.downloadBlocked === '409 DOCUMENT_QUARANTINED' && phase12b.quarantineNav && phase12b.quarantinePage && phase12b.historyUi
    && phase12b.releaseRefused === '409 DOCUMENT_RELEASE_REFUSED' && phase12b.stillQuarantined && phase12b.outsidersBlocked
    && phase12b.adminNoManage === '200 403'
    && ['DOCUMENT_QUARANTINED', 'DOCUMENT_RELEASE_REFUSED', 'DOCUMENT_RESCANNED', 'DOCUMENT_UPLOADED'].every((a) => phase12b.audit.includes(a));
  if (!stillIn || real.length || navItems.length !== 5 || !p2ok || !p3ok || !p4ok || !p5ok || !p6ok || !p7ok || !p8ok || !p8bok || !p9ok
    || !p9bok || !p10ok || !p11ok || !p12ok || !p12bok) process.exitCode = 1;
})().catch(async (e) => {
  console.error('DRIVER FAILED:', e.message);
  if (lastPage) {
    await lastPage.screenshot({ path: path.join(OUT, 'zz-failure.jpg'), type: 'jpeg', quality: 70 }).catch(() => undefined);
    console.error('page text:', (await lastPage.locator('body').innerText().catch(() => '')).slice(0, 1500));
  }
  process.exit(1);
});
