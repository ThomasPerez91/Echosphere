import { expect, test } from '@playwright/test';
import { detail, empire, origin, near, session, universe } from '../tests/systemFixture';
import { projection } from '../tests/galaxyFixture';

for (const width of [320, 390, 768, 1440]) {
  test(`system ${width}px: knowledge, keyboard/touch, deep-link and history`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 850 }, hasTouch: true });
    const page = await context.newPage();
    const requests: string[] = [];
    page.on('request', r => { if (r.url().includes('/api/game/')) requests.push(`${r.method()} ${r.url()}`); });
    await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
    await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
    await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
    await page.route(`**/api/game/${universe}/galaxy`, r => r.fulfill({ json: { empires: [{ id: empire, name: 'Empire test' }] } }));
    await page.route(`**/api/game/${universe}/galaxy/${empire}`, r => r.fulfill({ json: projection() }));
    await page.route(`**/api/game/${universe}/galaxy/${empire}/systems/${origin}`, r => r.fulfill({ json: detail() }));
    await page.route(`**/api/game/${universe}/galaxy/${empire}/systems/${near}`, r => r.fulfill({ json: projection().systems[1] }));
    await page.goto(`/#universe/${universe}/galaxy`);
    await expect(page.getByRole('link', { name: 'Voir le système' })).toBeVisible();
    // Preserve the existing map framing while opening/returning from a subroute.
    await page.getByRole('button', { name: 'Zoom avant', exact: true }).click();
    const box = await page.locator('.galaxy-map').getAttribute('viewBox');
    const open = page.getByRole('link', { name: 'Voir le système', exact: true });
    await open.focus(); await page.keyboard.press('Enter');
    await expect(page).toHaveURL(new RegExp(`galaxy/system/${empire}/${origin}$`));
    // Scoped: the Galaxy detail panel carries the same system name.
    const heading = page.locator('.system-heading').getByRole('heading', { name: 'Système d’origine', exact: true });
    await expect(heading).toBeFocused();
    await expect(page.getByText('Présence propre observée : Nouvelle Aube')).toBeVisible();
    const overflow = await page.evaluate(() => ({
      width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')].filter(element =>
        element.getBoundingClientRect().right > innerWidth + 1).map(element => ({
        tag: element.tagName, class: element.getAttribute('class'),
        text: element.textContent?.slice(0, 80), right: element.getBoundingClientRect().right,
      })),
    }));
    expect(overflow.scrollWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width);
    // Own world is preselected even though it is not first in server order.
    await expect(page.getByRole('link', { name: 'Voir ma colonie', exact: true })).toBeVisible();
    const other = page.getByRole('button', { name: 'Sélectionner Rocher Pâle' });
    await other.tap();
    await expect(page.getByRole('link', { name: 'Voir ma colonie', exact: true })).toHaveCount(0);
    const planet = page.getByRole('button', { name: 'Sélectionner Nouvelle Aube' });
    await planet.scrollIntoViewIfNeeded();
    const rect = (await planet.boundingBox())!;
    expect(rect.height).toBeGreaterThanOrEqual(44);
    await planet.tap();
    await expect(page.getByRole('link', { name: 'Voir ma colonie', exact: true })).toHaveAttribute('href',
      `#universe/${universe}/colony/overview/${detail().colony_links![0].colony_id}`);
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`system-${width}.png`), fullPage: true });
    await page.goBack();
    await expect(page.locator('.galaxy-map')).toHaveAttribute('viewBox', box!);
    await page.goForward(); await expect(heading).toBeVisible();
    await page.reload(); await expect(heading).toBeVisible();
    // System route has no Galaxy GET/polling of its own and no gameplay mutation.
    const before = requests.length;
    await page.getByRole('button', { name: 'Actualiser les connaissances' }).click();
    await expect.poll(() => requests.length).toBeGreaterThan(before);
    expect(requests.slice(before).every(r => r.startsWith('GET ') && r.includes('/systems/'))).toBe(true);
    await page.getByRole('link', { name: '← Retour à la Galaxie', exact: true }).click();
    await page.locator('.galaxy-list').getByRole('button', { name: /Signal détecté 1/ }).click();
    await expect(page.getByRole('link', { name: 'Voir le système' })).toHaveCount(0);
    await page.goto(`/#universe/${universe}/galaxy/system/${empire}/${near}`);
    await expect(page.getByRole('heading', { name: 'Structure encore inconnue' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Mondes connus' })).toHaveCount(0);
    await context.close();
  });
}
