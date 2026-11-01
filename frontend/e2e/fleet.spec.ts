import { expect, test } from '@playwright/test';
import { colonizing, empire, fleets, freeWorld, garrison, near, order, origin, otherEmpire, otherFleets, session, universe } from '../tests/fleetFixture';
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

test('cancel production from the UI: Keyed body as validated by the Game API, then server state', async ({ page }) => {
  await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
  await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
  await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
  await page.route(`**/api/game/${universe}/fleets`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
  await page.route(`**/api/game/${universe}/fleets/${empire}`, r => r.fulfill({ json: fleets() }));
  const bodies: unknown[] = [];
  await page.route(`**/api/game/${universe}/fleets/${empire}/orders/${order}/cancel`, r => {
    const body = r.request().postDataJSON();
    bodies.push(body);
    // Mirrors the backend Keyed model (extra="forbid"): anything else is the real 422.
    const keyed = Object.keys(body).join() === 'idempotency_key' && /^[A-Za-z0-9_-]{16,64}$/.test(body.idempotency_key);
    const after = fleets();
    after.colonies![0].orders = [];
    return keyed
      ? r.fulfill({ json: { result: { order_id: order, refunded: { alloys: '100000000', flux: '64000000', data: '64000000' } }, fleets: after } })
      : r.fulfill({ status: 422, json: { error: { code: 'invalid_request' } } });
  });
  await page.goto(`/#universe/${universe}/fleets`);
  await page.getByRole('button', { name: 'Annuler…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Annuler la production' });
  await dialog.getByRole('button', { name: 'Confirmer' }).click();
  await expect(page.getByText('Ordre accepté par le serveur.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Annuler…' })).toHaveCount(0);
  expect(bodies).toHaveLength(1);
});

test('shortcut from Galaxy on the second Empire opens that Empire prefilled, never the first one', async ({ page }) => {
  const both = { empires: [{ id: empire, name: 'Empire A' }, { id: otherEmpire, name: 'Empire B' }] };
  const firstReads: string[] = [];
  await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
  await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
  await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
  await page.route(`**/api/game/${universe}/galaxy`, r => r.fulfill({ json: both }));
  for (const id of [empire, otherEmpire]) {
    const map = projection([], id);
    map.permissions = [...map.permissions, 'fleet.command'];
    await page.route(`**/api/game/${universe}/galaxy/${id}`, r => r.fulfill({ json: map }));
  }
  await page.route(`**/api/game/${universe}/fleets`, r => r.fulfill({ json: both }));
  await page.route(`**/api/game/${universe}/fleets/${empire}`, r => { firstReads.push(r.request().url()); return r.fulfill({ json: fleets() }); });
  await page.route(`**/api/game/${universe}/fleets/${otherEmpire}`, r => r.fulfill({ json: otherFleets() }));

  await page.goto(`/#universe/${universe}/galaxy`);
  await page.getByRole('combobox', { name: 'Empire' }).selectOption(otherEmpire);
  await page.locator('.galaxy-list').getByRole('button', { name: /Signal détecté 1/ }).click();
  await page.getByRole('link', { name: 'Envoyer une flotte ici' }).click();
  await expect(page).toHaveURL(new RegExp(`fleets/send/${otherEmpire}/${near}$`));
  const dialog = page.getByRole('dialog', { name: 'Envoyer une flotte' });
  await expect(dialog.getByText(/Garnison Bastion B/)).toBeVisible();
  await expect(dialog.getByRole('combobox', { name: 'Destination' })).toHaveValue(near);
  await expect(page.getByRole('combobox', { name: 'Empire' })).toHaveValue(otherEmpire);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await page.getByRole('button', { name: 'Actualiser' }).click();
  await expect(dialog).toBeHidden(); // prefill consumed once
  expect(firstReads).toEqual([]);
});

for (const width of [320, 390, 768, 1440]) {
  test(`colonize ${width}px: System View shortcut, COLONIZE dialog, targets and no overflow`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 850 }, hasTouch: true });
    const page = await context.newPage();
    const writes: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/game/') && r.method() !== 'GET') writes.push(r.url()); });
    await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
    await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
    await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
    await page.route(`**/api/game/${universe}/fleets`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
    await page.route(`**/api/game/${universe}/fleets/${empire}`, r => r.fulfill({ json: colonizing() }));
    await page.goto(`/#universe/${universe}/fleets/colonize/${empire}/${origin}/${freeWorld}`);
    const dialog = page.getByRole('dialog', { name: 'Envoyer une flotte' });
    await expect(dialog.getByRole('radio', { name: 'Colonisation' })).toBeChecked();
    await expect(dialog.getByRole('combobox', { name: 'Monde visé' })).toHaveValue(freeWorld);
    await expect(dialog.getByText(/Occupation actuelle inconnue/)).toBeVisible();
    await expect(page.getByText(/\bLibre\b/)).toHaveCount(0);
    // A radio's touch target is its whole label (.fleet-choice), as everywhere in Fleets.
    for (const control of await dialog.locator('button, select, input:not([type=radio]), label.fleet-choice').all()) {
      const box = await control.boundingBox();
      if (box) expect(box.height, await control.getAttribute('name') ?? '').toBeGreaterThanOrEqual(44);
    }
    const overflow = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.width);
    // A modal dialog does not widen the document: check that nothing inside it leaks out.
    const leaks = await dialog.evaluate((box) => {
      const edge = box.getBoundingClientRect().right;
      return [...box.querySelectorAll('*')].filter((e) => e.getBoundingClientRect().right > edge + 1).map((e) => e.tagName);
    });
    expect(leaks).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`colonize-${width}.png`), fullPage: true });
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    expect(writes).toEqual([]);
    await context.close();
  });
}
