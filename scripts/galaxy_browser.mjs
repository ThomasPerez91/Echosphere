// Real HTTPS / control plane / worker. No request interception or runtime fixture data in UI.
import { chromium } from '@playwright/test';
import { access, writeFile } from 'node:fs/promises';
const marker = name => writeFile(`/artifacts/${name}`, 'ready');
async function waitMarker(name) {
  const deadline = Date.now() + 150000;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return; } catch { await new Promise(r => setTimeout(r, 200)); }
  }
  throw new Error(`Marker timeout: ${name}`);
}
const portal = 'https://portal.echosphere.localhost:8443', game = 'https://game.echosphere.localhost:8443';
const universe = process.env.GALAXY_UNIVERSE, colony = process.env.GALAXY_COLONY, empire = process.env.GALAXY_EMPIRE;
if (!universe || !colony || !empire || !process.env.GALAXY_EDGE_IP) throw new Error('Dedicated recipe environment required');
const root = `/api/game/${universe}/galaxy/${empire}`;
async function call(page, path, body, csrf) {
  return page.evaluate(async ([path, body, csrf]) => {
    const response = await fetch(path, body === null
      ? { headers: { 'X-Game-Request': 'bootstrap' } }
      : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  }, [path, body, csrf]);
}
const read = (page, path = root) => call(page, path, null, '');
async function open(page) {
  await page.goto(`${game}/#universe/${universe}/galaxy`);
  await page.getByRole('heading', { name: 'Carte des connaissances' }).waitFor();
}
async function openSystem(page, snapshot, { own = false } = {}) {
  // Enter through the real Galaxy action, then verify the dedicated projection against Knowledge.
  const select = page.locator('.galaxy-list').getByRole('button', { name: new RegExp(`^${snapshot.name} `) });
  await select.click();
  await page.getByRole('link', { name: 'Voir le système', exact: true }).click();
  // The Galaxy detail panel shows the same name: wait for the System View header itself.
  const title = page.locator('.system-heading').getByRole('heading', { name: snapshot.name, exact: true });
  await page.waitForURL(new RegExp(`/galaxy/system/${empire}/${snapshot.id}$`));
  await title.waitFor().catch(async error => {
    await page.screenshot({ path: '/artifacts/system-failure.png', fullPage: true });
    console.error(await page.locator('main').innerText());
    throw error;
  });
  const detail = await read(page, `${root}/systems/${snapshot.id}`);
  if (detail.status !== 200 || JSON.stringify(detail.body.planets) !== JSON.stringify(snapshot.planets)) throw new Error('System View must match stored PlanetKnowledge');
  if (detail.body.state === 'DETECTED') throw new Error('Detailed System View must require mapped structure');
  if (own && (!detail.body.colony_links.some(c => c.colony_id === colony) || !detail.body.presences.some(p => p.current && p.colony?.colony_id === colony))) throw new Error('Own Colony link and dated presence expected');
  for (const planet of detail.body.planets) {
    if (!await page.locator('.system-world-list').getByRole('button', { name: new RegExp(planet.name) }).count()) throw new Error('Known planet missing from text list');
  }
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('System View horizontal overflow');
  await page.screenshot({ path: `/artifacts/system-${own ? 'own' : 'mapped'}-${page.viewportSize().width}.png`, fullPage: true });
  const colonyLink = page.getByRole('link', { name: 'Voir ma colonie', exact: true });
  if (own) {
    // The own world opens preselected; its link leads to the real Colony screen of that colony.
    await colonyLink.click();
    await page.waitForURL(new RegExp(`/colony/overview/${colony}$`));
    await page.getByRole('heading', { name: 'Constructions en cours' }).waitFor();
    await page.goBack();
    await title.waitFor();
  } else if (await colonyLink.count()) throw new Error('No Colony action on a system without own presence');
  await page.getByRole('link', { name: '← Retour à la Galaxie', exact: true }).click();
  await page.getByRole('heading', { name: 'Carte des connaissances' }).waitFor();
}
function audit(p) {
  // Only legitimate knowledge: never the 40-system world, never structure for DETECTED.
  const ids = new Set(p.systems.map(s => s.id));
  if (p.systems.length >= 40) throw new Error('Projection must not contain the whole galaxy');
  for (const s of p.systems) if (s.state === 'DETECTED' && ('name' in s || 'planets' in s)) throw new Error('DETECTED leak');
  for (const r of p.routes) if (!ids.has(r.a_id) || !ids.has(r.b_id)) throw new Error('Route to unknown system');
  for (const key of ['seed', 'inputs', 'starting_sites', 'system_count']) if (key in p) throw new Error(`Leaked ${key}`);
}
async function launch(page, p) {
  const option = p.options.find(o => o.reason === null);
  if (!option) throw new Error('A reachable DETECTED destination is expected');
  const labels = new Map(); let n = 0;
  for (const s of p.systems) labels.set(s.id, s.name ?? `Signal détecté ${++n}`);
  await page.locator('.galaxy-list').getByRole('button', { name: new RegExp(`^${labels.get(option.destination_id)} `) }).click();
  await page.getByRole('button', { name: 'Préparer l’expédition' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Confirmer l’expédition' }).click();
  await page.getByText(/Expédition acceptée par le serveur/).waitFor();
  return option;
}
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${process.env.GALAXY_EDGE_IP},MAP game.echosphere.localhost ${process.env.GALAXY_EDGE_IP}`, '--no-proxy-server',
] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  let page = await context.newPage();
  await page.goto(portal);
  await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
  await page.getByLabel('Adresse email', { exact: true }).first().fill('galaxy@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
  await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
  await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
  await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();
  await open(page);
  const initial = (await read(page)).body;
  audit(initial);
  const detected = initial.systems.filter(s => s.state === 'DETECTED');
  if (initial.systems.filter(s => s.state === 'MONITORED').length !== 1 || !detected.length) throw new Error('One monitored origin and its detected neighbours expected');
  const ownSystem = initial.systems.find(s => s.state === 'MONITORED');
  await openSystem(page, ownSystem, { own: true });
  const first = await launch(page, initial);
  const engaged = (await read(page)).body;
  const mission = engaged.missions.find(m => m.status === 'active');
  if (!mission || mission.cost.alloys !== '50000000' || mission.cost.data !== '25000000' || BigInt(mission.cost.flux) !== 50000000n + 10000000n * BigInt(first.hops)) throw new Error('Exact v0.3 cost snapshot expected');
  for (const r of ['alloys', 'flux', 'data']) {
    const spent = BigInt(initial.sources[0].stocks[r]) - BigInt(engaged.sources[0].stocks[r]);
    if (spent < BigInt(mission.cost[r]) - 1000000n) throw new Error(`Source must be debited once (${r})`);
  }
  await page.screenshot({ path: '/artifacts/galaxy-launched-390.png', fullPage: true });
  await page.close(); await marker('launched'); await waitMarker('completed');

  page = await context.newPage(); await open(page);
  const mapped = (await read(page)).body;
  audit(mapped);
  const destination = mapped.systems.find(s => s.id === first.destination_id);
  if (destination?.state !== 'MAPPED' || !destination.name || !destination.planets.length) throw new Error('Destination must be MAPPED with structure');
  const done = mapped.missions.find(m => m.destination_id === first.destination_id);
  if (done.status !== 'completed' || done.report.observed_at !== done.due_at) throw new Error('Immutable report observed at due_at expected');
  if (mapped.systems.length < initial.systems.length) throw new Error('Knowledge must be monotonic');
  await page.getByText('Terminée').first().waitFor();
  await openSystem(page, destination);
  console.log(`Galaxy/System View: own presence/link, detailed Knowledge, limited map (${initial.systems.length} known), exact debit, page closed, worker restart, MAPPED + report then reopened`);

  await marker('portal-stop'); await waitMarker('portal-stopped');
  const probe = await context.newPage(); const down = await probe.goto(`${portal}/api/ready`);
  if (!down || down.status() < 500) throw new Error('Portal must really be down'); await probe.close();
  const portalRequests = [];
  context.on('request', req => { if (new URL(req.url()).host === new URL(portal).host) portalRequests.push(req.url()); });
  await page.reload(); await page.getByRole('heading', { name: 'Carte des connaissances' }).waitFor();
  const second = await launch(page, (await read(page)).body);
  await page.close(); await marker('outage-launched'); await waitMarker('outage-completed');

  page = await context.newPage(); await open(page);
  const outage = (await read(page)).body;
  audit(outage);
  if (outage.systems.find(s => s.id === second.destination_id)?.state !== 'MAPPED') throw new Error('Knowledge must progress with Portal down');
  await openSystem(page, outage.systems.find(s => s.id === second.destination_id));
  const third = await launch(page, outage);
  const csrf = (await read(page, `/api/game/${universe}/session`)).body.csrf_token;
  await marker('expire'); await waitMarker('expired');
  if ((await read(page)).status !== 401) throw new Error('Expired session must refuse reads');
  const expiredSystem = await read(page, `${root}/systems/${ownSystem.id}`);
  if (expiredSystem.status !== 401 || 'planets' in expiredSystem.body) throw new Error('Expired System deep-link must not leak structure');
  const refused = await call(page, `/api/game/${universe}/exploration/${empire}/missions`,
    { idempotency_key: 'expired_recipe_intention', colony_id: colony, destination_id: third.destination_id }, csrf);
  if (refused.status !== 401) throw new Error('Expired session must refuse new commands');
  if (portalRequests.length) throw new Error('Gameplay must not call Portal');
  await marker('expiry-checked'); await waitMarker('expiry-completed');
  await context.close();
  console.log('Galaxy: Portal-down expedition/offline worker/progress, zero Portal calls, expiry 401 while accepted mission completes');
} finally { await browser.close(); }
