import { expect, test } from '@playwright/test';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';

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
