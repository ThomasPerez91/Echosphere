// Real HTTPS / control plane / worker. No request interception or runtime fixture data in UI.
import { chromium } from '@playwright/test';
import { access, readFile, writeFile } from 'node:fs/promises';
const marker = (name, content = 'ready') => writeFile(`/artifacts/${name}`, content);
async function waitMarker(name) {
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return (await readFile(`/artifacts/${name}`, 'utf8')).trim(); }
    catch { await new Promise(r => setTimeout(r, 200)); }
  }
  throw new Error(`Marker timeout: ${name}`);
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const portal = 'https://portal.echosphere.localhost:8443', game = 'https://game.echosphere.localhost:8443';
const universe = process.env.FLEET_UNIVERSE, colony = process.env.FLEET_COLONY, empire = process.env.FLEET_EMPIRE;
if (!universe || !colony || !empire || !process.env.FLEET_EDGE_IP) throw new Error('Dedicated recipe environment required');
const root = `/api/game/${universe}/fleets/${empire}`;
async function call(page, path, body, csrf) {
  return page.evaluate(async ([path, body, csrf]) => {
    const response = await fetch(path, body === null
      ? { headers: { 'X-Game-Request': 'bootstrap' } }
      : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  }, [path, body, csrf]);
}
const read = (page, path = root) => call(page, path, null, '');
let serial = 0;
async function command(page, path, body, key = `recipe_intention_${++serial}_${Date.now()}`) {
  const csrf = (await read(page, `/api/game/${universe}/session`)).body.csrf_token;
  return call(page, root + path, { idempotency_key: key, ...body }, csrf);
}
async function until(page, check, label, timeout = 120000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const projection = (await read(page)).body;
    if (projection.fleets && check(projection)) return projection;
    await sleep(1000);
  }
  throw new Error(`Timeout waiting for ${label}`);
}
async function open(page) {
  await page.goto(`${game}/#universe/${universe}/fleets`);
  await page.getByRole('heading', { name: 'Vos flottes', level: 1 }).waitFor();
}
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${process.env.FLEET_EDGE_IP},MAP game.echosphere.localhost ${process.env.FLEET_EDGE_IP}`, '--no-proxy-server',
] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  let page = await context.newPage();
  await page.goto(portal);
  await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
  await page.getByLabel('Adresse email', { exact: true }).first().fill('fleet@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
  await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
  await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
  await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();

  // 1. Production through the real UI, then page closed: only the worker builds the batch.
  await open(page);
  for (const ship of ['probe', 'freighter']) {
    await page.getByRole('combobox', { name: 'Classe' }).selectOption(ship);
    await page.getByRole('button', { name: 'Commander' }).click();
    await page.getByText('Ordre accepté par le serveur.').waitFor();
    await page.getByRole('button', { name: 'Masquer' }).click();
  }
  await page.close();
  await marker('ordered'); await waitMarker('produced');
  page = await context.newPage();
  await open(page);
  const garrisonCard = page.locator('.fleet-card').filter({ hasText: 'Garnison' });
  await garrisonCard.getByText('Sonde').waitFor();
  await page.screenshot({ path: '/artifacts/fleets-produced-390.png', fullPage: true });
  let p = (await read(page)).body;
  const garrison = p.fleets.find(f => f.kind === 'GARRISON');
  const origin = garrison.system.id;
  if (JSON.stringify(garrison.stacks) !== JSON.stringify({ freighter: 1, probe: 1 }) && JSON.stringify(garrison.stacks) !== JSON.stringify({ probe: 1, freighter: 1 }))
    throw new Error(`Garrison expected one probe and one freighter: ${JSON.stringify(garrison.stacks)}`);
  if (p.systems.some(s => s.state === 'DETECTED' && 'name' in s)) throw new Error('DETECTED leak');

  // 2. SURVEY launched through the UI while the worker is stopped: GETs past due change nothing.
  await marker('stop-worker'); await waitMarker('worker-stopped');
  // Production cancelled through the real UI (no interception): queued then active order.
  const production = page.locator('ol.fleet-list > li');
  for (const quantity of ['10', '1']) {
    await page.getByRole('combobox', { name: 'Classe' }).selectOption('probe');
    await page.getByRole('spinbutton', { name: 'Quantité' }).fill(quantity);
    await page.getByRole('button', { name: 'Commander' }).click();
    await page.getByText('Ordre accepté par le serveur.').waitFor();
    await page.getByRole('button', { name: 'Masquer' }).click();
  }
  p = (await read(page)).body;
  const orders = Object.fromEntries(p.colonies[0].orders.map(o => [o.status, o]));
  if (!orders.active || !orders.queued) throw new Error(`Active and queued orders expected: ${JSON.stringify(p.colonies[0].orders)}`);
  for (const o of [orders.queued, orders.active]) {
    await production.filter({ has: page.getByText(`${o.quantity} × Sonde`, { exact: true }) })
      .getByRole('button', { name: 'Annuler…' }).click();
    await page.getByRole('dialog', { name: 'Annuler la production' }).getByRole('button', { name: 'Confirmer' }).click();
    await page.getByText('Ordre accepté par le serveur.').waitFor();
    await page.getByRole('button', { name: 'Masquer' }).click();
  }
  await page.getByText('Aucune production en cours.').waitFor();
  const dataStock = async () => BigInt((await read(page, `/api/game/${universe}/colonies/${colony}`)).body.resources.find(r => r.resource === 'data').stock);
  const before = await dataStock();
  const cancelReplay = await command(page, `/orders/${orders.queued.id}/cancel`, {});
  const refunded = cancelReplay.body.result?.refunded ?? {};
  if (cancelReplay.status !== 200 || refunded.alloys !== '80000000' || refunded.flux !== '40000000' || refunded.data !== '40000000')
    throw new Error(`Cancel replay must return the single 100 % refund: ${JSON.stringify(cancelReplay.body)}`);
  if (await dataStock() - before >= 1000000n) throw new Error('A cancel replay must never refund twice');
  await marker('orders-cancelled', JSON.stringify({ queued: orders.queued.id, active: orders.active.id }));
  await waitMarker('orders-checked');
  console.log('Fleet: queued and active production cancelled through the UI, replay refunds nothing more');
  await garrisonCard.getByRole('button', { name: 'Envoyer…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Envoyer une flotte' });
  await dialog.getByRole('radio', { name: 'Cartographie' }).check();
  const destination = dialog.getByRole('combobox', { name: 'Destination' });
  const target = await destination.locator('option').nth(1).getAttribute('value');
  await destination.selectOption(target);
  await dialog.getByRole('spinbutton', { name: /Sonde/ }).fill('1');
  await dialog.getByRole('button', { name: 'Calculer le devis' }).click();
  await dialog.getByText(/saut\(s\)/).waitFor();
  await dialog.getByRole('button', { name: 'Confirmer' }).click();
  await page.getByText('Ordre accepté par le serveur.').waitFor();
  p = (await read(page)).body;
  const survey = p.missions.find(m => m.kind === 'SURVEY' && m.status === 'active');
  await sleep(Date.parse(survey.due_at) - Date.parse(p.server_time) + 3000);
  p = (await read(page)).body;
  const galaxyMap = (await read(page, `/api/game/${universe}/galaxy/${empire}`)).body;
  const detail = (await read(page, `/api/game/${universe}/galaxy/${empire}/systems/${target}`)).body;
  if (p.missions.find(m => m.id === survey.id).status !== 'active' || detail.state !== 'DETECTED' ||
    galaxyMap.systems.find(s => s.id === target).state !== 'DETECTED')
    throw new Error('A GET must never complete a Fleet mission');
  await page.close();
  await marker('gets-checked', survey.id); await waitMarker('surveyed');
  page = await context.newPage();
  await open(page);
  p = (await read(page)).body;
  const probe = p.fleets.find(f => f.id === survey.fleet_id);
  if (probe.status !== 'STATIONED' || probe.system.id !== target || probe.system.state === 'DETECTED') throw new Error('Probe must stand at the mapped target');
  await marker('second-colony', target);
  const second = await waitMarker('colony-ready');
  console.log('Fleet: UI production offline, UI SURVEY, GETs past due non-mutating, worker mapping proven in DB first');

  // 3. DEPLOY then recall while travelling: time-symmetric, idempotent, one return.
  const deploy = await command(page, '/missions', { fleet_id: probe.id, kind: 'DEPLOY', destination_id: origin, units: { probe: 1 } });
  if (deploy.status !== 200) throw new Error(`DEPLOY refused: ${JSON.stringify(deploy.body)}`);
  const recallKey = `recipe_recall_${Date.now()}`;
  const recalled = await command(page, `/missions/${deploy.body.result.mission_id}/recall`, {}, recallKey);
  const replay = await command(page, `/missions/${deploy.body.result.mission_id}/recall`, {}, recallKey);
  if (recalled.status !== 200 || JSON.stringify(replay.body.result) !== JSON.stringify(recalled.body.result)) throw new Error('Recall must be idempotent');
  await until(page, x => x.fleets.find(f => f.id === probe.id)?.status === 'STATIONED', 'recall return');
  console.log('Fleet: DEPLOY recalled, symmetric return processed by the worker');

  // 4. SURVEY from the stationed probe: recall refused once the analysis started.
  p = (await read(page)).body;
  const csrf = (await read(page, `/api/game/${universe}/session`)).body.csrf_token;
  let next = null;
  for (const s of p.systems.filter(s => s.state === 'DETECTED')) {
    const q = await call(page, `${root}/missions/preview`, { fleet_id: probe.id, kind: 'SURVEY', destination_id: s.id, units: { probe: 1 } }, csrf);
    if (q.status === 200) { next = s.id; break; }
  }
  if (!next) throw new Error('A DETECTED neighbour of the mapped target is expected');
  const second_survey = await command(page, '/missions', { fleet_id: probe.id, kind: 'SURVEY', destination_id: next, units: { probe: 1 } });
  p = (await read(page)).body;
  const analysing = p.missions.find(m => m.id === second_survey.body.result.mission_id);
  await sleep(Date.parse(analysing.travel_arrival_at) - Date.parse(p.server_time) + 2000);
  const late = await command(page, `/missions/${analysing.id}/recall`, {});
  if (late.status !== 409 || late.body.error.code !== 'recall_too_late') throw new Error('Recall during analysis must be refused');
  await until(page, x => x.missions.find(m => m.id === analysing.id)?.status === 'completed', 'analysis end');
  console.log('Fleet: recall refused during analysis, survey completed normally');

  // 5. Cargo: LOAD A → DEPLOY → UNLOAD B with partial storage, surplus kept aboard.
  const loaded = await command(page, `/${garrison.id}/load`, { colony_id: colony, cargo: { alloys: 300 } });
  if (loaded.status !== 200) throw new Error(`LOAD refused: ${JSON.stringify(loaded.body)}`);
  const convoy = await command(page, '/missions', { fleet_id: garrison.id, kind: 'DEPLOY', destination_id: target, units: { freighter: 1 }, cargo: { alloys: 300 } });
  const freighter = convoy.body.result.fleet_id;
  p = await until(page, x => x.fleets.find(f => f.id === freighter)?.status === 'STATIONED', 'convoy arrival');
  const preview = p.fleets.find(f => f.id === freighter).unload;
  if (preview.credited.alloys !== String(100e6) || preview.kept.alloys !== String(200e6)) throw new Error(`Unload preview: ${JSON.stringify(preview)}`);
  const unloaded = await command(page, `/${freighter}/unload`, { colony_id: second });
  if (unloaded.body.result.credited.alloys !== String(100e6) || unloaded.body.result.kept.alloys !== String(200e6)) throw new Error('Partial unload expected');
  console.log('Fleet: LOAD → DEPLOY → UNLOAD, 100 credited to the full test colony, 200 kept aboard');

  // 6. Portal down: new mission accepted and completed with zero Portal calls.
  const portalRequests = [];
  context.on('request', req => { if (new URL(req.url()).host === new URL(portal).host) portalRequests.push(req.url()); });
  await marker('portal-stop'); await waitMarker('portal-stopped');
  const probeDown = await context.newPage(); const down = await probeDown.goto(`${portal}/api/ready`).catch(() => null);
  if (down && down.ok()) throw new Error('Portal must be unavailable'); await probeDown.close(); portalRequests.length = 0;
  const home = await command(page, '/missions', { fleet_id: freighter, kind: 'RETURN', units: { freighter: 1 } });
  if (home.status !== 200) throw new Error(`RETURN refused: ${JSON.stringify(home.body)}`);
  await until(page, x => x.fleets.find(f => f.id === freighter)?.system?.id === origin, 'return home with Portal down');

  // 7. Session expiry: commands and reads refused; the accepted mission still completes.
  const lastTrip = await command(page, '/missions', { fleet_id: probe.id, kind: 'RETURN', units: { probe: 1 } });
  if (lastTrip.status !== 200) throw new Error(`Final RETURN refused: ${JSON.stringify(lastTrip.body)}`);
  await marker('expire'); await waitMarker('expired');
  if ((await read(page)).status !== 401) throw new Error('Expired session must refuse reads');
  if ((await read(page, `/api/game/${universe}/galaxy/${empire}/systems/${target}`)).status !== 401) throw new Error('Expired System deep-link must refuse');
  const refused = await call(page, `${root}/orders`, { idempotency_key: 'expired_fleet_intention', colony_id: colony, ship_class: 'probe', quantity: 1 }, csrf);
  if (refused.status !== 401) throw new Error('Expired session must refuse new commands');
  if (portalRequests.length) throw new Error('Gameplay must not call Portal');
  await marker('summary', JSON.stringify({ recall: deploy.body.result.mission_id, second, freighter, last: lastTrip.body.result.mission_id }));
  await marker('expiry-checked'); await waitMarker('expiry-completed');
  await context.close();
  console.log('Fleet: Portal-down RETURN, zero Portal calls, expiry 401 while the accepted RETURN completes');
} finally { await browser.close(); }
