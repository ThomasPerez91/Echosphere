import { expect, test } from '@playwright/test';
import { empire, frontierFleets, sentinel, session, universe } from '../tests/fleetFixture';

// 13B (v0.9) Fleets UI in a real Chromium: protocol selector by keyboard and touch, Frontier
// panel, targets and overflow. Intercepted Game API only; written in the cloud session, to run
// locally (`npm run test:e2e`), not yet executed.
for (const width of [320, 390, 768, 1440]) {
  test(`frontier ${width}px: protocol by keyboard/touch, Frontier panel, targets, no overflow`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 850 }, hasTouch: true });
    const page = await context.newPage();
    const bodies: unknown[] = [];
    await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
    await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
    await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
    await page.route(`**/api/game/${universe}/fleets`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
    await page.route(`**/api/game/${universe}/fleets/${empire}`, r => r.fulfill({ json: frontierFleets() }));
    await page.route(`**/api/game/${universe}/fleets/${empire}/${sentinel}/protocol`, r => {
      const body = r.request().postDataJSON();
      bodies.push(body);
      // Mirrors the backend ProtocolChoice model (extra="forbid"): anything else is the real 422.
      const keys = Object.keys(body).sort().join();
      const valid = keys === 'idempotency_key,protocol' && /^[A-Za-z0-9_-]{16,64}$/.test(body.idempotency_key);
      return valid
        ? r.fulfill({ json: { result: { fleet_id: sentinel, protocol: body.protocol }, fleets: frontierFleets() } })
        : r.fulfill({ status: 422, json: { error: { code: 'invalid_request' } } });
    });

    await page.goto(`/#universe/${universe}/fleets`);
    const card = page.locator('.fleet-card').filter({ hasText: 'Sentinelle' });
    await expect(card.getByText('Surveillance').first()).toBeVisible();
    const select = card.getByRole('combobox', { name: 'Protocole de premier contact' });
    await select.focus();
    await select.selectOption('FRIENDLY_CONTACT');
    await expect(card.getByText(/se présente/i)).toBeVisible();
    const apply = card.getByRole('button', { name: 'Appliquer' });
    await apply.tap();
    await expect(page.getByText('Ordre accepté par le serveur.')).toBeVisible();
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ protocol: 'FRIENDLY_CONTACT' });

    const panel = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Frontière' }) });
    await expect(panel.getByText('Signature étrangère détectée')).toBeVisible();
    await expect(panel.getByText('Repli effectué')).toBeVisible();

    for (const control of await page.locator('.fleet-screen button, .fleet-screen select').all()) {
      const box = await control.boundingBox();
      if (box) expect(box.height, await control.innerText().catch(() => '')).toBeGreaterThanOrEqual(44);
    }
    const overflow = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    expect(overflow.scrollWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width);
    await page.screenshot({ path: testInfo.outputPath(`frontier-${width}.png`), fullPage: true });
    await context.close();
  });
}
