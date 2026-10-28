import { expect, test } from '@playwright/test';

for (const width of [320, 390, 768, 1440]) {
  test(`navigation and layout at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route('**/api/ready', route => route.fulfill({ json: { status: 'ready' } }));
    await page.goto('/');
    await expect(page.getByRole('status')).toHaveText('Services disponibles');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Votre horizon commence ici.');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    // The first keyboard stop must provide a direct route into the content.
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Aller au contenu' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('main')).toBeFocused();
    const colony = page.getByRole('link', { name: 'Colonie', exact: true });
    const box = await colony.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    expect(box?.width).toBeGreaterThanOrEqual(44);
    await colony.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    await expect(colony).toHaveAttribute('aria-current', 'page');
    if (width <= 800) {
      const more = page.getByRole('button', { name: 'Plus' });
      await more.click();
      await expect(more).toHaveAttribute('aria-expanded', 'true');
      await page.keyboard.press('Escape');
      await expect(more).toBeFocused();
      await expect(more).toHaveAttribute('aria-expanded', 'false');
      await more.click();
    }
    await page.getByRole('link', { name: 'Rapports', exact: true }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('La mémoire de votre empire.');
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.goBack();
    await expect(colony).toHaveAttribute('aria-current', 'page');
    await page.reload();
    await expect(colony).toHaveAttribute('aria-current', 'page');
    await expect(page.getByText('Aucun univers / aucune colonie active')).toBeVisible();
    const defense = page.getByRole('link', { name: 'Défense', exact: true });
    await defense.focus();
    await page.keyboard.press('Enter');
    await expect(defense).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    await expect(page.getByText('Défense — système futur')).toBeVisible();
    await expect(page.getByRole('button', { name: /construire|attaquer|réparer/i })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('colony.png'), fullPage: true });
    await page.getByRole('link', { name: 'Empire', exact: true }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Votre horizon commence ici.');
    await page.screenshot({ path: testInfo.outputPath('empire.png'), fullPage: true });
  });
}

test('failed readiness, retry and navigation with keyboard', async ({ page }) => {
  let recovered = false;
  let attempts = 0;
  await page.route('**/api/ready', route => {
    attempts += 1;
    return route.fulfill(!recovered ? { status: 503, json: { detail: 'Database unavailable' } } : { json: { status: 'ready' } });
  });
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Connexion indisponible');
  const beforeRetry = attempts;
  recovered = true;
  await page.getByRole('button', { name: 'Vérifier la connexion' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toHaveText('Services disponibles');
  expect(attempts).toBe(beforeRetry + 1);
});
