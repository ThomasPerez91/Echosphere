import { expect, test } from '@playwright/test';
import { empire, fleets, garrison, near, session, universe } from '../tests/fleetFixture';
import { projection } from '../tests/galaxyFixture';

for (const width of [320, 390, 768, 1440]) {
  test(`fleets ${width}px: shortcut, keyboard/touch dialogs, targets and no overflow`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 850 }, hasTouch: true });
    const page = await context.newPage();
    const writes: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/game/') && r.method() !== 'GET') writes.push(r.url()); });
    await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
    await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
    await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
    await page.route(`**/api/game/${universe}/galaxy`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
    const map = projection();
    map.permissions = [...map.permissions, 'fleet.command'];
    await page.route(`**/api/game/${universe}/galaxy/${empire}`, r => r.fulfill({ json: map }));
    await page.route(`**/api/game/${universe}/fleets`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
    await page.route(`**/api/game/${universe}/fleets/${empire}`, r => r.fulfill({ json: fleets() }));

    // Shortcut from Galaxy: same Fleet flow, destination prefilled, nothing sent.
    await page.goto(`/#universe/${universe}/galaxy`);
    await page.locator('.galaxy-list').getByRole('button', { name: /Signal détecté 1/ }).click();
    await page.getByRole('link', { name: 'Envoyer une flotte ici' }).click();
    await expect(page).toHaveURL(new RegExp(`fleets/send/${empire}/${near}$`));
    const dialog = page.getByRole('dialog', { name: 'Envoyer une flotte' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('radio', { name: 'Cartographie' })).toBeChecked();
    await expect(dialog.getByRole('combobox', { name: 'Destination' })).toHaveValue(near);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();

    await page.goto(`/#universe/${universe}/fleets`);
    await expect(page.getByRole('heading', { name: 'Vos flottes', level: 1 })).toBeVisible();
    const card = page.locator('.fleet-card').filter({ hasText: 'Garnison Nouvelle Aube' });
    const send = card.getByRole('button', { name: 'Envoyer…' });
    await send.focus();
    await page.keyboard.press('Enter');
    await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(send).toBeFocused();
    const unload = card.getByRole('button', { name: 'Décharger…' });
    await unload.tap();
    await expect(page.getByRole('dialog', { name: 'Décharger' }).getByText(/conservés à bord/)).toBeVisible();
    await page.getByRole('dialog', { name: 'Décharger' }).getByRole('button', { name: 'Fermer' }).click();
    await expect(unload).toBeFocused();

    for (const button of await page.locator('.fleet-screen button, .fleet-screen select, .fleet-screen input').all()) {
      const box = await button.boundingBox();
      if (box) expect(box.height, await button.innerText().catch(() => '')).toBeGreaterThanOrEqual(44);
    }
    const overflow = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1)
        .map(e => `${e.tagName}.${e.getAttribute('class')}:${(e.textContent ?? '').slice(0, 40)}`).slice(0, 6) }));
    expect(overflow.scrollWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width);
    await page.screenshot({ path: testInfo.outputPath(`fleets-${width}.png`), fullPage: true });
    expect(writes).toEqual([]);
    expect(garrison).toBeTruthy();
    await context.close();
  });
}
