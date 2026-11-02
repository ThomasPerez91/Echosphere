// Real HTTPS / control plane / handoff for the human of the Combat recipe. The page is closed
// while time passes; no request interception and no runtime fixture data in the UI.
import { chromium } from '@playwright/test';
import { access, readFile, writeFile } from 'node:fs/promises';
const marker = (name, content = 'ready') => writeFile(`/artifacts/${name}`, content);
async function waitMarker(name, timeout = 900000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return (await readFile(`/artifacts/${name}`, 'utf8')).trim(); }
    catch { await new Promise(r => setTimeout(r, 200)); }
  }
  throw new Error(`Marker timeout: ${name}`);
}
const portal = 'https://portal.echosphere.localhost:8443', game = 'https://game.echosphere.localhost:8443';
const env = name => process.env[`COMBAT_${name}`];
const [universe, empire] = ['UNIVERSE', 'EMPIRE'].map(env);
if (!universe || !empire || !env('EDGE_IP')) throw new Error('Dedicated recipe environment required');
const read = page => page.evaluate(async ([u, e]) => {
  const response = await fetch(`/api/game/${u}/fleets/${e}`, { headers: { 'X-Game-Request': 'bootstrap' } });
  return response.status;
}, [universe, empire]);
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${env('EDGE_IP')},MAP game.echosphere.localhost ${env('EDGE_IP')}`, '--no-proxy-server',
] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  let page = await context.newPage();
  await page.goto(portal);
  await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
  await page.getByLabel('Adresse email', { exact: true }).first().fill('combat@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
  await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
  await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
  await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();
  await page.goto(`${game}/#universe/${universe}/fleets`);
  await page.getByRole('heading', { name: 'Vos flottes', level: 1 }).waitFor();
  // v0.7 military production is offered by the real projection.
  await page.getByRole('combobox', { name: 'Classe' }).first().selectOption('frigate');
  await page.getByText(/· militaire/).first().waitFor();
  await page.close();
  await marker('entered');

  await waitMarker('reopen');
  page = await context.newPage();
  await page.goto(`${game}/#universe/${universe}/fleets`);
  await page.getByRole('heading', { name: 'Rapports de combat' }).waitFor();
  const reports = page.locator('.combat-report');
  if (await reports.count() !== 2) throw new Error('Two dated combat reports expected for the attacker');
  if (await page.getByText(/Alliages|Flux|Données/).locator('xpath=ancestor::li[contains(@class,"combat-report")]').count())
    throw new Error('A combat report must never show resources');
  if (await read(page) !== 200) throw new Error('Established Game session must outlive Portal');
  await page.screenshot({ path: '/artifacts/combat-reports.png', fullPage: true });
  await marker('reopened');

  await waitMarker('expired');
  if (await read(page) !== 401) throw new Error('Expired human session must refuse reads');
  console.log('Combat recipe: human UI shows military production and two dated reports, Portal down, expiry 401');
} finally {
  await browser.close();
}
