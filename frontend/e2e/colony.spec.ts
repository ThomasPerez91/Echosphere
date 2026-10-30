import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

// Intercepted API: layout, keyboard and viewport checks. The real HTTPS recipe covers the server.
const universe = '052d4535-79c7-413b-ace3-47c732561fbd';
const colony = '7d1c56a0-3c52-4e8e-9d6b-2b1f4b0f8a11';
const M = (value: number) => String(value * 1_000_000);
const amounts = (a: number, f: number, d: number) => ({ alloys: M(a), flux: M(f), data: M(d) });
const now = new Date();
const session = { universe_id: universe, universe_name: 'Univers de recette', csrf_token: 'a'.repeat(64),
  expires_at: new Date(+now + 8 * 3600e3).toISOString(), idle_expires_at: new Date(+now + 2 * 3600e3).toISOString(),
  access_valid_until: new Date(+now + 8 * 3600e3).toISOString(), server_time: now.toISOString(), portal_url: 'https://portal.example.org' };
const kinds = ['extraction_complex', 'flux_reactor', 'data_node', 'industrial_complex', 'logistics_center'];

function projection(queue: unknown[] = []) {
  return {
    server_time: new Date().toISOString(), settled_at: new Date().toISOString(), ruleset_version: 'v0.1',
    permissions: ['colony.cancel', 'colony.construct', 'colony.read'],
    colony: { id: colony, name: 'Nouvelle Aube', planet: { name: 'Nouvelle Aube', sector_capacity: 12, orbital_capacity: 2 },
      system: { name: 'Système Recette' }, empire: { id: 'e', name: 'Empire de recette avec un nom particulièrement long' },
      universe: { id: universe, name: 'Univers de recette' } },
    sectors: { capacity: 12, built: 4, reserved: queue.length, free: 8 - queue.length, free_indices: [5, 6, 7, 8, 9, 10, 11, 12].slice(queue.length) },
    resources: [
      { resource: 'alloys', stock: M(9400), capacity: M(10000), rate_per_hour: M(120) },
      { resource: 'flux', stock: M(1500), capacity: M(10000), rate_per_hour: M(100) },
      { resource: 'data', stock: M(750), capacity: M(10000), rate_per_hour: M(60) },
    ],
    infrastructures: kinds.slice(0, 4).map((kind, index) => ({ sector_index: index + 1, infrastructure_type: kind, level: 1,
      cost: amounts(250, 120, 0), base_duration_us: String(120e6), production_per_hour: amounts(index === 0 ? 120 : 0, index === 1 ? 100 : 0, index === 2 ? 60 : 0),
      construction_bonus_bps: index === 3 ? 1000 : 0, capacity: null })),
    queue, queue_limit: 3,
    options: [
      ...kinds.map(kind => ({ action: 'build', infrastructure_type: kind, sector_index: 5, target_level: 1, cost: amounts(250, 120, 0),
        base_duration_us: String(120e6), estimated_duration_us: String(109090910), production_per_hour: amounts(120, 0, 0),
        construction_bonus_bps: 0, capacity: null, available: kind !== 'industrial_complex', reason: kind === 'industrial_complex' ? 'unique_limit' : null })),
      ...kinds.slice(0, 4).map((kind, index) => ({ action: 'upgrade', infrastructure_type: kind, sector_index: index + 1, target_level: 2,
        cost: amounts(800, 350, 50), base_duration_us: String(900e6), estimated_duration_us: String(818181819), production_per_hour: amounts(210, 0, 0),
        construction_bonus_bps: 0, capacity: null, available: true, reason: null })),
    ],
  };
}

async function routes(page: Page) {
  let queue: unknown[] = [];
  const posts: string[] = [];
  await page.route('**/api/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route(`**/api/game/${universe}/session`, route => route.fulfill({ json: session }));
  // Explicit navigation is C08 activity on the session endpoint, never a Colony command.
  await page.route(`**/api/game/${universe}/navigation`, route => route.fulfill({ json: session }));
  await page.route(`**/api/game/${universe}/colonies`, route => route.fulfill({ json: { server_time: session.server_time,
    colonies: [{ id: colony, name: 'Nouvelle Aube', empire: { id: 'e', name: 'Empire' } }] } }));
  await page.route(`**/api/game/${universe}/colonies/${colony}**`, route => {
    const request = route.request();
    if (request.method() === 'POST') {
      posts.push(request.url());
      const started = new Date();
      queue = [{ id: 'order-1', sequence: 1, status: 'active', infrastructure_type: 'data_node', sector_index: 5, target_level: 1,
        cost: amounts(250, 120, 0), base_duration_us: String(120e6), applied_bonus_bps: 1000, started_at: started.toISOString(),
        due_at: new Date(+started + 600e3).toISOString(), cancel: { available: true, reason: null, refund: amounts(200, 96, 0), also_cancels: [] } }];
      return route.fulfill({ json: { order: { id: 'order-1', status: 'active' }, colony: projection(queue) } });
    }
    return route.fulfill({ json: projection(queue) });
  });
  return posts;
}

async function reachable(page: Page, locator: Locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeGreaterThanOrEqual(44);
  // The real interactive viewport: the element itself is hit at its centre, not a fixed bar above it.
  const hit = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.closest('button, a, select')?.textContent ?? null,
    { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 });
  expect(hit).toBe(await locator.textContent());
}

for (const width of [320, 390, 768, 1440]) {
  test(`connected colony at ${width}px: build, queue, keyboard and viewport`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 800 });
    const posts = await routes(page);
    await page.goto(`/#universe/${universe}/colony/infrastructure`);
    await expect(page.getByRole('heading', { name: 'Nouvelle Aube' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const build = page.getByRole('button', { name: 'Construire Nœud de données' });
    await reachable(page, build);
    await reachable(page, page.getByRole('button', { name: 'Améliorer Complexe d’extraction niveau 2' }));
    await build.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByText('Ordre de construction accepté par le serveur.')).toBeVisible();
    expect(posts).toHaveLength(1);
    await expect(page.getByRole('progressbar', { name: /Avancement estimé de Nœud de données/ })).toBeVisible();
    const cancel = page.getByRole('button', { name: 'Annuler Nœud de données' });
    await reachable(page, cancel);
    await cancel.click();
    await expect(page.getByRole('button', { name: 'Confirmer l’annulation' })).toBeVisible();
    await page.getByRole('button', { name: 'Garder' }).click();
    expect(posts).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`colony-infrastructure-${width}.png`) });
    const sections = page.getByRole('navigation', { name: 'Sections de la colonie' });
    await sections.getByRole('link', { name: 'Vue d’ensemble' }).click();
    await expect(page.getByRole('table', { name: 'Résumé des infrastructures' })).toBeVisible();
    await expect(page.getByText('Alliages : stock proche de la capacité', { exact: false })).toBeVisible();
    await sections.getByRole('link', { name: 'Défense' }).click();
    await expect(page.getByText('Défense — système futur')).toBeVisible();
    await expect(page.getByRole('button', { name: /construire|attaquer|réparer/i })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
