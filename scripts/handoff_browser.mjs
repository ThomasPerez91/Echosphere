// Real HTTPS/API navigation against an isolated Compose project; no request interception.
import { chromium } from '@playwright/test';
import { access, writeFile } from 'node:fs/promises';
const marker = async (name) => writeFile(`/artifacts/${name}`, 'ready');
async function waitMarker(name) {
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    try { await access(`/artifacts/${name}`); return; } catch { await new Promise(resolve => setTimeout(resolve, 200)); }
  }
  throw new Error(`Timeout waiting for ${name}`);
}

const portal = 'https://portal.echosphere.localhost:8443';
const game = 'https://game.echosphere.localhost:8443';
const universe = process.env.HANDOFF_UNIVERSE;
if (!universe || !process.env.HANDOFF_EDGE_IP) throw new Error('Dedicated test environment required');
const browser = await chromium.launch({ args: [
  `--host-resolver-rules=MAP portal.echosphere.localhost ${process.env.HANDOFF_EDGE_IP},MAP game.echosphere.localhost ${process.env.HANDOFF_EDGE_IP}`,
  '--no-proxy-server',
] });
try {
  for (const width of [320, 1440]) {
    const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 900 } });
    const page = await context.newPage();
    const urls = [];
    page.on('response', response => {
      if (response.status() >= 400) console.log('HTTP refusal', response.status(), new URL(response.url()).pathname,
        'origin:', response.request().headers().origin ?? 'absent');
    });
    page.on('request', request => urls.push(request.url()));
    await page.goto(portal);
    await page.getByRole('button', { name: 'Se connecter à mon compte', exact: true }).click();
    await page.getByLabel('Adresse email', { exact: true }).first().fill('handoff@example.org');
    await page.getByLabel('Mot de passe', { exact: true }).first().fill('A long test passphrase 2026 !');
    await page.getByRole('button', { name: 'Ouvrir ma session', exact: true }).click();
    await page.getByRole('link', { name: 'Entrer dans cet univers' }).waitFor();
    await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
    await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Déconnecter cette partie' }).waitFor();
    if (!page.url().startsWith(`${game}/#universe/${universe}/empire`)) throw new Error('Clean Game URL expected');
    if (urls.some(value => value.includes('ticket=') || value.includes('eyJ'))) throw new Error('Ticket leaked in URL');
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Horizontal overflow');
    const cookies = await context.cookies(game);
    const session = cookies.find(cookie => cookie.name.startsWith('__Host-game-session-'));
    if (!session?.secure || !session.httpOnly || session.domain !== 'game.echosphere.localhost') throw new Error('Game cookie isolation');
    const read = async () => page.evaluate(async () => {
      const response = await fetch(`/api/game/${document.location.hash.split('/')[1]}/session`, { headers: { 'X-Game-Request': 'bootstrap' } });
      return { status: response.status, body: await response.json() };
    });
    const before = await read();
    await page.getByRole('link', { name: 'Retour au lobby' }).click();
    await page.getByRole('heading', { name: 'Mes parties' }).waitFor();
    await page.goto(`${game}/#universe/${universe}/empire`);
    await page.getByRole('button', { name: 'Actualiser mon accès' }).waitFor();
    const after = await read();
    if (before.body.idle_expires_at !== after.body.idle_expires_at) throw new Error('Read or return refreshed activity');
    await page.getByRole('button', { name: 'Actualiser mon accès' }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('heading', { name: 'Accès à la partie', exact: true }).waitFor();
    const explicit = await read();
    if (!(explicit.body.idle_expires_at > before.body.idle_expires_at)) throw new Error('Explicit action did not refresh idle');
    if (explicit.body.expires_at !== before.body.expires_at) throw new Error('Absolute deadline moved');
    await page.screenshot({ path: `/artifacts/game-context-${width}.png`, fullPage: true });
    await page.getByRole('button', { name: 'Déconnecter cette partie' }).focus();
    await page.keyboard.press('Enter');
    await page.getByText('Partie déconnectée.', { exact: false }).waitFor();
    await page.getByRole('link', { name: 'Retour au lobby' }).click();
    await page.getByRole('heading', { name: 'Mes parties' }).waitFor();
    // Portal remained authenticated. A fresh browser ceremony after logout can succeed.
    await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
    await page.getByRole('button', { name: 'Déconnecter cette partie' }).waitFor();
    if (width === 1440 && process.env.C09_OUTAGE === '1') {
      await marker('outage-ready'); await waitMarker('outage-stopped');
      const during = await read();
      if (during.status !== 200 || during.body.expires_at !== before.body.expires_at) throw new Error('Game autonomy/deadline during Portal outage');
      await page.getByRole('button', { name: 'Actualiser mon accès' }).click();
      const probe = await context.newPage();
      const portalFailure = await probe.goto(`${portal}/api/ready`);
      if (!portalFailure || portalFailure.status() < 500) throw new Error('Portal was not actually stopped');
      await probe.close();
      await marker('outage-checked'); await waitMarker('outage-resumed');
      await page.goto(portal);
      await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click();
      await page.getByText('Déconnexion encore en attente sur certains services Game.', { exact: true }).waitFor();
      await marker('revocation-ready'); await waitMarker('revocation-acked');
      await page.getByRole('button', { name: 'Vérifier la déconnexion des parties' }).click();
      await page.getByText('Déconnexion terminée : tous les services Game concernés ont confirmé.', { exact: true }).waitFor();
      const revokedPage = await context.newPage();
      await revokedPage.goto(`${game}/#universe/${universe}/empire`);
      await revokedPage.getByRole('alert').filter({ hasText: 'a expiré' }).waitFor();
      const revoked = await revokedPage.evaluate(async id => (await fetch(`/api/game/${id}/session`, {
        headers: { 'X-Game-Request': 'bootstrap' } })).status, universe);
      if (revoked !== 401) throw new Error('Acknowledged device logout must invalidate Game');
      await revokedPage.close();
      console.log('C09 Portal outage, worker continuation, durable delayed revocation and receipt acknowledgement passed');
    }
    await context.close();
    console.log(`Handoff Chromium ${width}px: real HTTPS, POST, host-only cookies, explicit idle, targeted logout passed`);
  }
} finally { await browser.close(); }
