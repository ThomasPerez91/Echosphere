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
const portal = 'https://portal.echosphere.localhost:8443', game = 'https://game.echosphere.localhost:8443';
const env = name => process.env[`COLONIZATION_${name}`];
const [universe, colony, empire, system] = ['UNIVERSE', 'COLONY', 'EMPIRE', 'SYSTEM'].map(env);
if (!universe || !colony || !empire || !system || !env('EDGE_IP')) throw new Error('Dedicated recipe environment required');
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
async function accepted(page) {
  await page.getByText('Ordre accepté par le serveur.').waitFor();
  await page.getByRole('button', { name: 'Masquer' }).click();
}
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${env('EDGE_IP')},MAP game.echosphere.localhost ${env('EDGE_IP')}`, '--no-proxy-server',
] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto(portal);
  await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
  await page.getByLabel('Adresse email', { exact: true }).first().fill('colonization@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
  await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
  await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
  await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();

  // 1. Colonizer ordered through the UI at the current progressive server price.
  await page.goto(`${game}/#universe/${universe}/fleets`);
  await page.getByRole('heading', { name: 'Vos flottes', level: 1 }).waitFor();
  await page.getByRole('combobox', { name: 'Classe' }).selectOption('colonizer');
  await page.getByText(/Prix serveur actuel/).waitFor();
  await page.getByText(/rang 1/).waitFor();
  await page.getByRole('button', { name: 'Commander' }).click();
  await accepted(page);
  await marker('ordered'); await waitMarker('produced');

  // 2. Founding package loaded through the UI into the garrison holding the colonizer.
  await page.reload();
  const garrison = page.locator('.fleet-card').filter({ hasText: 'Garnison' });
  await garrison.getByText('Colonisateur').waitFor();
  await garrison.getByRole('button', { name: 'Charger…' }).click();
  const load = page.getByRole('dialog', { name: 'Charger' });
  for (const [label, value] of [['Alliages', '600'], ['Flux', '300'], ['Données', '100']])
    await load.getByRole('spinbutton', { name: new RegExp(label) }).fill(value);
  await load.getByRole('button', { name: 'Confirmer' }).click();
  await accepted(page);

  // 3. System View → "Coloniser…" on another world of the home system → same Fleet flow.
  await page.goto(`${game}/#universe/${universe}/galaxy/system/${empire}/${system}`);
  const worlds = page.locator('.system-world-list button');
  await worlds.first().waitFor();
  if (await page.getByText(/\bLibre\b/).count()) throw new Error('A world must never be shown as free');
  let offered = false;
  for (const world of await worlds.all()) {
    await world.click();
    if (await page.getByRole('link', { name: 'Coloniser…' }).count()) { offered = true; break; }
  }
  if (!offered) throw new Error('A world without own colony must offer "Coloniser…"');
  await page.getByText(/Occupation actuelle inconnue/).waitFor();
  await page.getByRole('link', { name: 'Coloniser…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Envoyer une flotte' });
  await dialog.getByRole('radio', { name: 'Colonisation' }).waitFor();
  if (!await dialog.getByRole('radio', { name: 'Colonisation' }).isChecked()) throw new Error('COLONIZE must be prefilled');
  for (const [label, value] of [['Alliages', '600'], ['Flux', '300'], ['Données', '100']])
    await dialog.getByRole('spinbutton', { name: new RegExp(label) }).fill(value);
  await dialog.getByRole('button', { name: 'Calculer le devis' }).click();
  await dialog.getByText(/0 saut\(s\)/).waitFor();
  await dialog.getByText(/aucun carburant/).waitFor();
  await dialog.getByRole('button', { name: 'Confirmer' }).click();
  await accepted(page);
  await marker('launched');
  const founded = JSON.parse(await waitMarker('founded'));

  // 4. The founded colony appears in the existing Colony selector with the planet's capacity.
  await page.goto(`${game}/#universe/${universe}/colony`);
  await page.getByRole('button', { name: 'Actualiser la colonie' }).click();  // no page reload
  const selector = page.getByRole('combobox', { name: 'Colonie' });
  await selector.waitFor();
  await selector.selectOption({ label: founded.planet });
  const meter = page.getByRole('meter', { name: 'Secteurs utilisés' });
  await page.getByRole('heading', { name: founded.planet }).first().waitFor();
  if (await meter.getAttribute('aria-valuemax') !== String(founded.sectors) || await meter.getAttribute('aria-valuenow') !== '0')
    throw new Error('The founded colony must use its planet capacity with every sector free');
  await page.screenshot({ path: '/artifacts/colony-founded-390.png', fullPage: true });
  console.log(`Colonization: UI colonizer + package + System View shortcut, worker founded ${founded.planet} (${founded.sectors} sectors, stocks = package, production 0)`);

  // 5. Portal down: two-Empire contest resolved by two workers; reports reveal no Empire.
  const portalRequests = [];
  context.on('request', req => { if (new URL(req.url()).host === new URL(portal).host) portalRequests.push(req.url()); });
  await marker('portal-stop');
  const contest = JSON.parse(await waitMarker('portal-stopped'));
  const projection = (await read(page)).body;
  const mine = projection.missions.find(m => m.id === contest.mine);
  if (!mine?.report) throw new Error('Own contest report expected');
  const expected = contest.winner === empire ? 'founded' : 'failed';
  if (mine.report.result.outcome !== expected) throw new Error(`Unexpected contest outcome: ${JSON.stringify(mine.report)}`);
  if (/Empire rival/.test(JSON.stringify(projection))) throw new Error('The rival Empire must never be revealed');
  await page.goto(`${game}/#universe/${universe}/fleets`);
  await page.getByText(expected === 'founded' ? 'Colonie fondée' : 'Monde indisponible à l’arrivée').first().waitFor();
  if (portalRequests.length) throw new Error('Gameplay must not call Portal');

  // 6. Session expiry: reads and COLONIZE commands refused.
  const csrf = (await read(page, `/api/game/${universe}/session`)).body.csrf_token;
  await marker('expire'); await waitMarker('expired');
  if ((await read(page)).status !== 401) throw new Error('Expired session must refuse reads');
  const refused = await call(page, `${root}/missions`, { idempotency_key: 'expired_colonize_intention', fleet_id: colony, kind: 'COLONIZE', target_planet_id: colony, units: { colonizer: 1 } }, csrf);
  if (refused.status !== 401) throw new Error('Expired session must refuse COLONIZE');
  await context.close();
  console.log('Colonization: contest report without rival identity, zero Portal calls, expiry 401');
} finally { await browser.close(); }
