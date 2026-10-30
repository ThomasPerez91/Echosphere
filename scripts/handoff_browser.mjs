// Real HTTPS/API navigation against an isolated Compose project; no request interception.
import { chromium } from '@playwright/test';

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
    await page.getByRole('button', { name: 'Confirmer avec mon compte Portal' }).click();
    await page.getByRole('heading', { name: 'Confirmer l’entrée dans l’univers' }).waitFor();
    await page.getByRole('button', { name: 'Continuer' }).click();
    await page.getByRole('heading', { name: 'Entrer dans l’univers' }).waitFor();
    await page.getByRole('button', { name: 'Continuer' }).click();
    await page.getByRole('heading', { name: 'Contexte Game', exact: true }).waitFor();
    if (!page.url().startsWith(`${game}/api/game/${universe}/view`)) throw new Error('Clean Game URL expected');
    if (urls.some(value => value.includes('ticket=') || value.includes('eyJ'))) throw new Error('Ticket leaked in URL');
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Horizontal overflow');
    const cookies = await context.cookies(game);
    const session = cookies.find(cookie => cookie.name.startsWith('__Host-game-session-'));
    if (!session?.secure || !session.httpOnly || session.domain !== 'game.echosphere.localhost') throw new Error('Game cookie isolation');
    const read = async () => page.evaluate(async () => {
      const response = await fetch(location.pathname.replace('/view', '/session'), { headers: { 'X-Game-Request': 'bootstrap' } });
      return { status: response.status, body: await response.json() };
    });
    const before = await read();
    await page.getByRole('link', { name: 'Retour au lobby' }).click();
    await page.getByRole('heading', { name: 'Mes parties' }).waitFor();
    await page.goto(`${game}/api/game/${universe}/view`);
    const after = await read();
    if (before.body.idle_expires_at !== after.body.idle_expires_at) throw new Error('Read or return refreshed activity');
    await page.getByRole('button', { name: 'Actualiser explicitement le contexte' }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('heading', { name: 'Contexte Game', exact: true }).waitFor();
    const explicit = await read();
    if (!(explicit.body.idle_expires_at > before.body.idle_expires_at)) throw new Error('Explicit action did not refresh idle');
    if (explicit.body.expires_at !== before.body.expires_at) throw new Error('Absolute deadline moved');
    await page.screenshot({ path: `/artifacts/game-context-${width}.png`, fullPage: true });
    await page.getByRole('button', { name: 'Déconnecter cette partie' }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('heading', { name: 'Partie déconnectée', exact: true }).waitFor();
    await page.getByRole('link', { name: 'Retour au lobby' }).click();
    await page.getByRole('heading', { name: 'Mes parties' }).waitFor();
    // Portal remained authenticated. A fresh browser ceremony after logout can succeed.
    await page.getByRole('link', { name: 'Entrer dans cet univers' }).click();
    await page.getByRole('button', { name: 'Confirmer avec mon compte Portal' }).click();
    await page.getByRole('button', { name: 'Continuer' }).click();
    await page.getByRole('button', { name: 'Continuer' }).click();
    await page.getByRole('heading', { name: 'Contexte Game', exact: true }).waitFor();
    await context.close();
    console.log(`Handoff Chromium ${width}px: real HTTPS, POST, host-only cookies, explicit idle, targeted logout passed`);
  }
} finally { await browser.close(); }
