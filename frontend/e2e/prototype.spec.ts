import { expect, test } from '@playwright/test';

// UX03 prototype (frontend/prototype/index.html, fixtures only, no Game API call). Prepared for
// `npx playwright test e2e/prototype.spec.ts`; Full CI runs e2e only on master.
for (const width of [390, 768, 1440]) {
  test(`prototype ${width}px: map-driven mission, 44 px targets, no overflow, no network command`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
    const page = await context.newPage();
    const api: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/')) api.push(r.url()); });
    await page.goto('/prototype/');
    const map = page.getByRole('group', { name: /Carte de commandement/ });
    await map.getByRole('button', { name: 'Cygne', exact: true }).tap();
    await page.getByRole('button', { name: 'Déplacer une flotte' }).tap();
    await page.getByRole('radio', { name: /Escadre Héliade/ }).check();
    await expect(page.getByText('2 sauts')).toBeVisible();
    await expect(page.getByRole('list', { name: 'Étapes du trajet' })).toContainText('Orion');
    for (const control of await page.locator('.proto-root button, .proto-root select').all()) {
      const box = await control.boundingBox();
      if (box) expect(box.height, await control.innerText().catch(() => '')).toBeGreaterThanOrEqual(44);
    }
    await page.getByRole('button', { name: /Confirmer/ }).tap();
    await expect(page.getByRole('status')).toContainText('Escadre Héliade arrive à Cygne');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    expect(api).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`prototype-${width}.png`), fullPage: true });
    await context.close();
  });
}

test('prototype keyboard: Tab to a system, Enter, actions reachable, Escape cancels', async ({ page }) => {
  await page.goto('/prototype/');
  const lyra = page.getByRole('group', { name: /Carte de commandement/ }).getByRole('button', { name: 'Lyra', exact: true });
  await lyra.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Lyra', level: 2 })).toBeVisible();
  await page.getByRole('button', { name: 'Déplacer une flotte' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Déplacer une flotte', level: 2 })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Actions possibles' })).toBeVisible();
});
