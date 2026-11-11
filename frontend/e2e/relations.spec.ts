import { expect, test } from '@playwright/test';
import { allied, empire, neutral, received, relations, universe } from '../tests/relationsFixture';
import { session } from '../tests/galaxyFixture';

for (const width of [320, 390, 768, 1440]) {
  test(`relations ${width}px: states, alerts, keyboard rupture confirmation, targets and no overflow`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 850 }, hasTouch: true });
    const page = await context.newPage();
    const writes: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/game/') && r.method() !== 'GET') writes.push(r.url()); });
    await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
    await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
    await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
    await page.route(`**/api/game/${universe}/relations`, r => r.fulfill({ json: { available: true, empires: [{ id: empire, name: 'Empire test' }] } }));
    await page.route(`**/api/game/${universe}/relations/${empire}`, r => r.fulfill({ json: relations([neutral(), received, allied]) }));

    await page.goto(`/#universe/${universe}/relations`);
    await expect(page.getByRole('heading', { name: 'Civilisations connues' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Alertes diplomatiques' })).toBeVisible();
    const ally = page.locator('.fleet-card').filter({ hasText: 'Concorde' });
    await expect(ally.getByText('Pacte actif')).toBeVisible();
    const partner = page.locator('.fleet-card').filter({ hasText: 'Ligue Aurorale' });
    await expect(partner.getByText(/Présenté par une proposition de pacte/)).toBeVisible();
    await expect(partner.getByRole('button', { name: 'Accepter le pacte' })).toBeVisible();

    // Breaking a pact is never one keystroke: an explicit confirmation, cancellable by keyboard.
    const rupture = ally.getByRole('button', { name: 'Rompre le pacte…' });
    await rupture.focus();
    await page.keyboard.press('Enter');
    const cancel = ally.getByRole('button', { name: 'Annuler' });
    await expect(ally.getByRole('button', { name: 'Confirmer la rupture' })).toBeVisible();
    await cancel.focus();
    await page.keyboard.press('Enter');
    await expect(ally.getByRole('button', { name: 'Rompre le pacte…' })).toBeVisible();

    for (const control of await page.locator('.relations-screen button, .relations-screen select').all()) {
      const box = await control.boundingBox();
      if (box) expect(box.height, await control.innerText().catch(() => '')).toBeGreaterThanOrEqual(44);
    }
    const overflow = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1)
        .map(e => `${e.tagName}.${e.getAttribute('class')}:${(e.textContent ?? '').slice(0, 40)}`).slice(0, 6) }));
    expect(overflow.scrollWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width);
    await page.screenshot({ path: testInfo.outputPath(`relations-${width}.png`), fullPage: true });
    expect(writes).toEqual([]);
    await context.close();
  });
}
