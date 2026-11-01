// Real HTTPS / control plane / handoff for the human of the AI recipe. The page is closed while
// the AI plays; no request interception, no runtime fixture data and no AI view in the UI.
import { chromium } from '@playwright/test';
import { access, readFile, writeFile } from 'node:fs/promises';
const marker = (name, content = 'ready') => writeFile(`/artifacts/${name}`, content);
async function waitMarker(name, timeout = 600000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return (await readFile(`/artifacts/${name}`, 'utf8')).trim(); }
    catch { await new Promise(r => setTimeout(r, 200)); }
  }
  throw new Error(`Marker timeout: ${name}`);
}
const portal = 'https://portal.echosphere.localhost:8443', game = 'https://game.echosphere.localhost:8443';
const env = name => process.env[`AI_${name}`];
const [universe, colony, planet] = ['UNIVERSE', 'COLONY', 'PLANET'].map(env);
if (!universe || !colony || !planet || !env('EDGE_IP')) throw new Error('Dedicated recipe environment required');
const read = page => page.evaluate(async ([u, c]) => {
  const response = await fetch(`/api/game/${u}/colonies/${c}`, { headers: { 'X-Game-Request': 'bootstrap' } });
  return response.status;
}, [universe, colony]);
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${env('EDGE_IP')},MAP game.echosphere.localhost ${env('EDGE_IP')}`, '--no-proxy-server',
] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  let page = await context.newPage();
  await page.goto(portal);
  await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
  await page.getByLabel('Adresse email', { exact: true }).first().fill('ai@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
  await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
  await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
  await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();
  await page.goto(`${game}/#universe/${universe}/colony`);
  await page.getByRole('heading', { name: planet }).first().waitFor();
  // The human leaves: page closed while the AI plays, Portal is then stopped.
  await page.close();
  await marker('entered');

  await waitMarker('reopen');
  page = await context.newPage();
  await page.goto(`${game}/#universe/${universe}/colony`);
  await page.getByRole('heading', { name: planet }).first().waitFor();
  if (await read(page) !== 200) throw new Error('Established Game session must outlive Portal');
  await marker('reopened');

  await waitMarker('expired');
  if (await read(page) !== 401) throw new Error('Expired human session must refuse reads');
  console.log('AI recipe: human page closed during AI play, Portal down, expiry 401');
} finally {
  await browser.close();
}
