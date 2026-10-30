// 5D real loop over HTTPS in an isolated Compose project; no request interception.
import { chromium } from '@playwright/test';
import { access, writeFile } from 'node:fs/promises';

const marker = name => writeFile(`/artifacts/${name}`, 'ready');
async function waitMarker(name, timeout = 120000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return; } catch { await new Promise(resolve => setTimeout(resolve, 200)); }
  }
  throw new Error(`Timeout waiting for ${name}`);
}
const portal = 'https://portal.echosphere.localhost:8443';
const game = 'https://game.echosphere.localhost:8443';
const universe = process.env.COLONY_UNIVERSE, colony = process.env.COLONY_ID;
if (!universe || !colony || !process.env.COLONY_EDGE_IP) throw new Error('Dedicated test environment required');
const M = 1_000_000n;

async function projection(page) {
  return page.evaluate(async ([u, c]) => {
    const response = await fetch(`/api/game/${u}/colonies/${c}`, { headers: { 'X-Game-Request': 'bootstrap' } });
    return { status: response.status, body: await response.json() };
  }, [universe, colony]);
}
const stock = (body, resource) => BigInt(body.resources.find(r => r.resource === resource).stock);
const level = (body, sector) => body.infrastructures.find(i => i.sector_index === sector)?.level ?? 0;
async function until(page, predicate, label, timeout = 90000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const read = await projection(page);
    if (read.status === 200 && predicate(read.body)) return read.body;
    await page.waitForTimeout(1000);
  }
  throw new Error(`Server state not reached: ${label}`);
}
async function openColony(page) {
  await page.goto(`${game}/#universe/${universe}/colony/infrastructure`);
  await page.getByRole('heading', { name: 'Nouvelle Aube' }).waitFor();
}

const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${process.env.COLONY_EDGE_IP},MAP game.echosphere.localhost ${process.env.COLONY_EDGE_IP}`,
  '--no-proxy-server',
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
  console.log('5D: Portal login, lobby and signed handoff reached the Game shell');

  await openColony(page);
  const initial = (await projection(page)).body;
  if (initial.infrastructures.length !== 4 || level(initial, 5) !== 0) throw new Error('Reference colony expected');
  await page.getByRole('button', { name: 'Construire Nœud de données' }).click();
  await page.getByText('Ordre de construction accepté par le serveur.').waitFor();
  const reserved = (await projection(page)).body;
  const order = reserved.queue[0];
  if (order?.infrastructure_type !== 'data_node' || order.sector_index !== 5) throw new Error('Real queued order expected');
  if (stock(initial, 'alloys') - stock(reserved, 'alloys') < 249n * M) throw new Error('Alloys must be reserved immediately');
  await page.getByRole('progressbar').first().waitFor();
  await page.screenshot({ path: '/artifacts/colony-queue-390.png' });
  await page.close(); // No browser page depends on the construction any more.
  await marker('built'); await waitMarker('completed');

  page = await context.newPage();
  await openColony(page);
  const completed = (await projection(page)).body;
  if (level(completed, 5) !== 1 || completed.queue.length) throw new Error('Worker completion must be visible');
  const dataRate = BigInt(completed.resources.find(r => r.resource === 'data').rate_per_hour);
  if (dataRate !== 120n * M) throw new Error('Production must include the new Data Node');
  await page.getByText('Secteur 5 · niveau 1').waitFor();
  console.log('5D: construction reserved, completed by the worker without a page, production updated');

  await page.getByRole('button', { name: 'Améliorer Complexe d’extraction niveau 2' }).click();
  await page.getByText('Ordre de construction accepté par le serveur.').waitFor();
  console.log('5D: next action accepted after completion');

  await marker('portal-stop'); await waitMarker('portal-stopped');
  const probe = await context.newPage();
  const down = await probe.goto(`${portal}/api/ready`);
  if (!down || down.status() < 500) throw new Error('Portal must actually be unavailable');
  await probe.close();
  const portalRequests = [];
  page.on('request', request => { if (new URL(request.url()).host === new URL(portal).host) portalRequests.push(request.url()); });
  await page.reload();
  await page.getByRole('heading', { name: 'Nouvelle Aube' }).waitFor();
  await page.getByRole('button', { name: 'Construire Réacteur de Flux' }).click();
  await page.getByText('Ordre de construction accepté par le serveur.').waitFor();
  const finished = await until(page, body => level(body, 1) === 2 && level(body, 6) === 1 && !body.queue.length,
    'upgrade and new reactor completed during Portal outage');
  if (BigInt(finished.resources.find(r => r.resource === 'alloys').rate_per_hour) !== 210n * M) throw new Error('Upgrade production expected');
  await page.getByRole('button', { name: 'Actualiser la colonie' }).click();
  await page.getByText('Secteur 6 · niveau 1').waitFor();
  if (portalRequests.length) throw new Error('Gameplay must not call Portal during the outage');
  await page.screenshot({ path: '/artifacts/colony-portal-down-390.png' });
  console.log('5D: Portal down — colony readable, construction accepted, worker progressed, no Portal request');

  await marker('expire'); await waitMarker('expired');
  await page.getByRole('button', { name: 'Construire Nœud de données' }).click();
  await page.getByRole('alert').filter({ hasText: 'a expiré' }).first().waitFor();
  if ((await projection(page)).status !== 401) throw new Error('Expired session must refuse reads and commands');
  console.log('5D: at the session deadline new commands are refused (401) without Portal');
  await context.close();
} finally { await browser.close(); }
