// Real HTTPS / control plane / worker. No request interception or runtime fixture data in UI.
import { chromium } from '@playwright/test';
import { access, writeFile } from 'node:fs/promises';
const marker = name => writeFile(`/artifacts/${name}`, 'ready');
async function waitMarker(name) {
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return; } catch { await new Promise(r => setTimeout(r, 200)); }
  }
  throw new Error(`Marker timeout: ${name}`);
}
const portal = 'https://portal.echosphere.localhost:8443', game = 'https://game.echosphere.localhost:8443';
const universe = process.env.COLONY_UNIVERSE, colony = process.env.COLONY_ID, empire = process.env.RESEARCH_EMPIRE;
if (!universe || !colony || !empire || !process.env.COLONY_EDGE_IP) throw new Error('Dedicated recipe environment required');
const root = `/api/game/${universe}/research/${empire}`;
async function read(page, path = root) {
  return page.evaluate(async path => {
    const response = await fetch(path, { headers: { 'X-Game-Request': 'bootstrap' } });
    return { status: response.status, body: await response.json() };
  }, path);
}
async function open(page) {
  await page.goto(`${game}/#universe/${universe}/research`);
  await page.getByLabel('Colonie payeuse').selectOption(colony);
  await page.getByRole('button', { name: 'Actualiser la recherche' }).waitFor();
}
async function launch(page, label, programmed = false) {
  await page.getByRole('button', { name: `${programmed ? 'Programmer' : 'Rechercher'} ${label}`, exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('Colonie payeuse : Nouvelle Aube').waitFor();
  await dialog.getByRole('button', { name: 'Confirmer', exact: true }).click();
  await page.getByText('Recherche acceptée par le serveur.').waitFor();
}
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${process.env.COLONY_EDGE_IP},MAP game.echosphere.localhost ${process.env.COLONY_EDGE_IP}`, '--no-proxy-server',
] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  let page = await context.newPage();
  await page.goto(portal);
  await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
  await page.getByLabel('Adresse email', { exact: true }).first().fill('colony@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
  await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
  await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
  await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();
  await page.getByText('Nouvelle Aube').first().waitFor();
  await open(page);
  const initial = (await read(page)).body;
  if (initial.ruleset_version !== 'v0.2' || initial.technologies.length !== 8 || initial.acquired.length) throw new Error('Empty pinned v0.2 Research expected');
  await launch(page, 'Calcul scientifique I');
  await launch(page, 'Fabrication modulaire I', true);
  const reserved = (await read(page)).body;
  if (reserved.queue.length !== 2 || reserved.queue[1].duration_us !== '12000000') throw new Error('Queued duration must be frozen before Calcul acquisition');
  if (BigInt(initial.sources[0].stocks.data) - BigInt(reserved.sources[0].stocks.data) < 399000000n) throw new Error('Both full costs must be reserved');
  await page.screenshot({ path: '/artifacts/research-queue-390.png' });
  await page.close(); await marker('built'); await waitMarker('completed');
  page = await context.newPage(); await open(page);
  const completed = (await read(page)).body;
  if (completed.queue.length || completed.acquired.length !== 2 || completed.bonuses.colony_alloys !== 500 || completed.bonuses.research_duration !== 500) throw new Error('Worker acquisitions/effects expected');
  const colonyView = (await read(page, `/api/game/${universe}/colonies/${colony}`)).body;
  const build = colonyView.options.find(o => o.action === 'build' && o.infrastructure_type === 'data_node');
  if (build.cost.alloys !== '237500000') throw new Error('Engineering must reduce actual Colony quote');
  console.log('Research: both reservations, offline worker, frozen following duration, acquired effects and real Colony quote verified');
  await marker('portal-stop'); await waitMarker('portal-stopped');
  const probe = await context.newPage(); const down = await probe.goto(`${portal}/api/ready`);
  if (!down || down.status() < 500) throw new Error('Portal must really be down'); await probe.close();
  const portalRequests = [];
  context.on('request', req => { if (new URL(req.url()).host === new URL(portal).host) portalRequests.push(req.url()); });
  await page.reload(); await page.getByLabel('Colonie payeuse').selectOption(colony);
  await launch(page, 'Gestion énergétique I');
  let active = (await read(page)).body;
  if (active.queue[0]?.duration_us !== '11400000') throw new Error('New orders must receive Calcul I');
  await page.close(); // Again only the worker is able to finish, with Portal stopped.
  await marker('outage-built'); await waitMarker('outage-completed');
  page = await context.newPage(); await open(page);
  const finished = (await read(page)).body;
  if (finished.acquired.length !== 3 || finished.queue.length) throw new Error('Research must complete with Portal down');
  const discounted = (await read(page, `/api/game/${universe}/colonies/${colony}`)).body;
  const nextBuild = discounted.options.find(o => o.action === 'build' && o.infrastructure_type === 'data_node');
  if (nextBuild.cost.flux !== '114000000') throw new Error('Energy must reduce real Colony Flux quote');
  if (portalRequests.length) throw new Error('Gameplay must not call Portal');
  await marker('expire'); await waitMarker('expired');
  if ((await read(page)).status !== 401) throw new Error('Expired session must be refused');
  await page.getByRole('button', { name: 'Actualiser la recherche' }).click();
  await page.getByText(/session a expiré|session.*expirée/i).first().waitFor();
  await context.close();
  console.log('Research: Portal-down read/start/offline worker/effects, zero Portal calls and expiry refusal verified');
} finally { await browser.close(); }
