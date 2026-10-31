import { expect, test } from '@playwright/test';
import { colony, empire, order, projection, session, universe } from '../tests/researchFixture';
// Intercepted UI only; smoke_research_compose exercises real HTTPS/services/worker separately.
for (const width of [320, 390, 768, 1440]) {
  test(`research ${width}px: explicit source, keyboard, confirmation and bounded refunds`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 800 });
    let state = projection(); let posts = 0;
    await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
    await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
    await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
    await page.route(`**/api/game/${universe}/research`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
    await page.route(`**/api/game/${universe}/research/${empire}**`, r => {
      if (r.request().method() === 'POST') { posts++; state = projection(r.request().url().endsWith('/cancel') ? [] : [order()]); return r.fulfill({ json: { research: state } }); }
      return r.fulfill({ json: state });
    });
    await page.goto(`/#universe/${universe}/research`);
    const start = page.getByRole('button', { name: 'Rechercher Fabrication modulaire I', exact: true });
    await expect(start).toBeDisabled(); expect(posts).toBe(0);
    await page.getByLabel('Colonie payeuse').selectOption(colony);
    await start.focus(); await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible(); await expect(dialog.getByText(/Colonie payeuse : Nouvelle Aube/)).toBeVisible();
    await page.keyboard.press('Escape'); await expect(start).toBeFocused();
    await start.click(); await dialog.getByRole('button', { name: 'Confirmer', exact: true }).click();
    await expect(page.getByText('Recherche acceptée par le serveur.')).toBeVisible(); expect(posts).toBe(1);
    await page.getByRole('button', { name: 'Annuler Fabrication modulaire I' }).click();
    await expect(dialog.getByText(/Perte définitive/)).toContainText('77 Alliages');
    const confirm = dialog.getByRole('button', { name: 'Confirmer', exact: true });
    await confirm.scrollIntoViewIfNeeded();
    const box = await confirm.boundingBox(); expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThanOrEqual(800); expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`research-${width}.png`), fullPage: true });
    await confirm.click(); expect(posts).toBe(2);
  });
}
