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
