import { expect, test } from '@playwright/test';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/lobby/memberships', route => route.fulfill({ json: { memberships: [], revocations: [] } }));
  await page.route('**/api/mfa/status', route => route.fulfill({ json: { enabled: false, totp: false, credentials: [] } }));
  await page.route('**/api/auth/sessions', route => route.fulfill({ status: 401, json: { error: { code: 'authentication_required' } } }));
});

for (const width of [320, 390, 768, 1440]) {
  test(`Portal keyboard and retry at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    let recovered = false;
    await page.route('**/api/ready', route => route.fulfill(recovered
      ? { json: { status: 'ready', service: 'portal' } }
      : { status: 503, json: { detail: 'Database unavailable' } }));
    await page.goto('/');
    await expect(page.getByRole('status')).toHaveText('Portal indisponible');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Aller au contenu' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('main')).toBeFocused();
    const retry = page.getByRole('button', { name: 'Vérifier à nouveau' });
    await retry.focus();
    const box = await retry.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    recovered = true;
    await page.keyboard.press('Enter');
    await expect(page.getByRole('status')).toHaveText('Portal disponible');
    await page.screenshot({ path: testInfo.outputPath('portal.png'), fullPage: true });
  });
}

// Observe native fetch metadata on a real local server; interception omits these headers.
// TLS itself is verified independently against the development CA by the Compose smoke.
test('Portal and Game development hosts are same-site in Chromium', async ({ page }) => {
  let relation: string | string[] | undefined;
  let port = 0;
  const server = createServer((request, response) => {
    if (request.url === '/api/health') {
      relation = request.headers['sec-fetch-site'];
      response.writeHead(200, { 'Content-Type': 'application/json' });
      response.end('{"status":"ok"}');
    } else {
      response.writeHead(200, { 'Content-Type': 'text/html' });
      response.end(`<a href="http://game.echosphere.localhost:${port}/api/health">Entrer</a>`);
    }
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  port = (server.address() as AddressInfo).port;
  try {
    await page.goto(`http://portal.echosphere.localhost:${port}/`);
    await page.getByRole('link', { name: 'Entrer' }).click();
    await expect(page).toHaveURL(`http://game.echosphere.localhost:${port}/api/health`);
    expect(relation).toBe('same-site');
  } finally {
    server.closeAllConnections();
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});

for (const width of [320, 1440]) {
  test(`Registration and verification at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route('**/api/ready', route => route.fulfill({ json: { status: 'ready', service: 'portal' } }));
    const requests: string[] = [];
    await page.route('**/api/accounts/**', async route => {
      requests.push(route.request().postData() ?? '');
      await route.fulfill({ status: route.request().url().endsWith('/verify') ? 200 : 202,
        json: { status: route.request().url().endsWith('/verify') ? 'verified' : 'request_received' } });
    });
    await page.goto('/');
    await page.getByLabel('Adresse email').fill('player@example.org');
    await page.getByLabel('Mot de passe', { exact: true }).fill('Browser test phrase 2026 !');
    await page.getByRole('button', { name: 'Créer le compte', exact: true }).click();
    await expect(page.getByText('Demande reçue.', { exact: false })).toBeVisible();
    await expect(page.getByLabel('Mot de passe', { exact: true })).toHaveValue('');
    expect(JSON.parse(requests[0]).email).toBe('player@example.org');
    await page.getByRole('button', { name: 'Déjà inscrit sans lien valide ?' }).click();
    await page.getByLabel('Mot de passe', { exact: true }).fill('Browser test phrase 2026 !');
    await page.getByRole('button', { name: 'Renvoyer le lien', exact: true }).click();
    await expect(page.getByText('Demande reçue.', { exact: false })).toBeVisible();
    const token = 'a'.repeat(43);
    await page.goto(`/#verify-email=${token}`);
    await expect(page.getByRole('heading', { name: 'Confirmer votre adresse', exact: true })).toBeVisible();
    expect(new URL(page.url()).hash).toBe('');
    await page.getByLabel('Mot de passe', { exact: true }).fill('Browser test phrase 2026 !');
    await page.getByRole('button', { name: 'Confirmer mon adresse' }).click();
    await expect(page.getByText('Votre adresse est confirmée.', { exact: false })).toBeVisible();
    expect(JSON.parse(requests[2]).token).toBe(token);
    expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('verification.png'), fullPage: true });
  });
}


for (const width of [320, 1440]) {
  test(`Login, explicit refresh and logout at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route('**/api/ready', route => route.fulfill({ json: { status: 'ready', service: 'portal' } }));
    let loggedIn = false;
    let navigation = 0;
    const snapshot = { status: 'authenticated', user: { email: 'player@example.org', email_verified: true },
      session_id: 'one', csrf_token: 'session-proof', sessions: [{ id: 'one', current: true }] };
    await page.route('**/api/auth/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/sessions')) return route.fulfill(loggedIn ? { json: snapshot } : { status: 401, json: {} });
      if (path.endsWith('/challenge')) return route.fulfill({ json: { csrf_token: 'login-proof' } });
      if (path.endsWith('/login')) {
        expect(route.request().headers()['x-csrf-token']).toBe('login-proof');
        loggedIn = true;
        return route.fulfill({ json: snapshot });
      }
      expect(route.request().headers()['x-csrf-token']).toBe('session-proof');
      if (path.endsWith('/navigation')) { navigation++; return route.fulfill({ json: snapshot }); }
      loggedIn = false;
      return route.fulfill({ json: { current_session_closed: true, game_revocation: 'pending' } });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Se connecter à mon compte' }).click();
    await page.getByLabel('Adresse email').fill('player@example.org');
    await page.getByLabel('Mot de passe', { exact: true }).fill('Browser C03 password !');
    await page.getByRole('button', { name: 'Ouvrir ma session' }).press('Enter');
    await expect(page.getByRole('heading', { name: 'Vos connexions' })).toBeVisible();
    expect(navigation).toBe(0);
    await page.getByRole('button', { name: 'Actualiser mes connexions' }).click();
    await expect.poll(() => navigation).toBe(1);
    await expect(page.getByRole('button', { name: 'Se déconnecter', exact: true })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
    await page.screenshot({ path: testInfo.outputPath('sessions.png'), fullPage: true });
    await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Déconnexion des parties en attente');
  });
}


for (const width of [320, 1440]) {
  test(`Password recovery and email confirmation at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route('**/api/ready', route => route.fulfill({ json: { status: 'ready', service: 'portal' } }));
    let recoveries = 0;
    await page.route('**/api/security/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/request')) return route.fulfill({ status: 202, json: { status: 'request_received' } });
      if (path.includes('/password/')) { recoveries++; return route.fulfill({ json: { status: 'password_reset', game_revocation: 'pending' } }); }
      return route.fulfill({ json: { status: 'additional_confirmation_required' } });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Se connecter à mon compte' }).click();
    await page.getByRole('button', { name: 'Mot de passe oublié ?' }).click();
    await page.getByLabel('Adresse email').fill('player@example.org');
    await page.getByRole('button', { name: 'Demander un lien de récupération' }).click();
    await expect(page.getByText('Demande reçue.', { exact: false })).toBeVisible();
    await page.goto('/#reset-password=' + 'a'.repeat(43));
    await expect(page.getByRole('heading', { name: 'Choisir un nouveau mot de passe' })).toBeVisible();
    expect(new URL(page.url()).hash).toBe('');
    await page.getByLabel('Nouveau mot de passe', { exact: true }).fill('Browser replacement password !');
    await page.getByLabel('Confirmer le nouveau mot de passe', { exact: true }).fill('Browser replacement password !');
    await page.getByRole('button', { name: 'Réinitialiser mon mot de passe' }).press('Enter');
    await expect(page.getByText('Modification réussie.', { exact: false })).toBeVisible();
    expect(recoveries).toBe(1);
    await page.goto('/#confirm-email-change=' + 'b'.repeat(43));
    await page.getByRole('button', { name: 'Confirmer cette adresse' }).click();
    await expect(page.getByText('Cette adresse est confirmée.', { exact: false })).toBeVisible();
    expect(new URL(page.url()).hash).toBe('');
    expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('security-confirmation.png'), fullPage: true });
  });
}
