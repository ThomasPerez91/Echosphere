import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { session, universe } from '../tests/galaxyFixture';
import { fleetFixture, galaxyFixture, ids, quoteFixture, SERVER_TIME } from '../src/prototype/fixtures';

// UX04 live command map inside the real App shell (Galaxy screen, switch → new map), against an
// intercepted Game API: contract-shaped projections, the real preview/launch endpoints, CSRF and
// idempotency checked on the wire. Not a real-universe validation (see ux04-live-command-map.md).
const empire = galaxyFixture().empire;

async function serve(page: Page, posts: { url: string; body: Record<string, unknown>; csrf?: string }[]) {
  let launched = false;
  await page.route('**/api/ready', r => r.fulfill({ json: { status: 'ready' } }));
  await page.route(`**/api/game/${universe}/session`, r => r.fulfill({ json: session }));
  await page.route(`**/api/game/${universe}/colonies`, r => r.fulfill({ json: { colonies: [] } }));
  await page.route(`**/api/game/${universe}/galaxy`, r => r.fulfill({ json: { empires: [empire] } }));
  await page.route(`**/api/game/${universe}/fleets`, r => r.fulfill({ json: { empires: [empire] } }));
  await page.route(`**/api/game/${universe}/galaxy/${empire.id}`, r => r.fulfill({ json: galaxyFixture() }));
  await page.route(`**/api/game/${universe}/fleets/${empire.id}`, r => r.fulfill({ json: launched ? moved() : fleetFixture() }));
  await page.route(`**/api/game/${universe}/fleets/${empire.id}/missions/preview`, r => {
    posts.push({ url: r.request().url(), body: r.request().postDataJSON(), csrf: r.request().headers()['x-csrf-token'] });
    const q = quoteFixture(ids.home, 'DEPLOY', ids.lyra, { frigate: 2, interceptor: 2 }, null, SERVER_TIME);
    if ('error' in q) return r.fulfill({ status: 409, json: { error: { code: q.error } } });
    delete q.path; // current contract: no UX-API-01 path yet
    return r.fulfill({ json: q });
  });
  await page.route(`**/api/game/${universe}/fleets/${empire.id}/missions`, r => {
    const body = r.request().postDataJSON();
    posts.push({ url: r.request().url(), body, csrf: r.request().headers()['x-csrf-token'] });
    launched = true;
    return r.fulfill({ json: { result: { mission_id: '61000000-0000-4000-8000-000000000001', fleet_id: ids.escadre }, fleets: moved() } });
  });
}
function moved() {
  const p = fleetFixture();
  const q = quoteFixture(ids.home, 'DEPLOY', ids.lyra, { frigate: 2, interceptor: 2 }, null, SERVER_TIME);
  if ('error' in q) throw new Error(q.error);
  const m = { ...p.missions![0], id: '61000000-0000-4000-8000-000000000001', fleet_id: ids.escadre, kind: 'DEPLOY' as const,
    origin: p.systems!.find(s => s.id === ids.home)!, destination: p.systems!.find(s => s.id === ids.lyra)!, hops: 2,
    stacks: { frigate: 2, interceptor: 2 }, started_at: SERVER_TIME, travel_arrival_at: q.travel_arrival_at, due_at: q.due_at };
  return { ...p, missions: [m, ...p.missions!], fleets: p.fleets!.map(f => (f.id === ids.escadre
    ? { ...f, status: 'MOVING' as const, system: null, mission_id: m.id } : f)) };
}

for (const width of [390, 768, 1440]) {
  test(`live command map ${width}px: switch, plan, server summary, confirm, tracking, no overflow`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
    const page = await context.newPage();
    const posts: { url: string; body: Record<string, unknown>; csrf?: string }[] = [];
    await serve(page, posts);
    await page.goto(`/#universe/${universe}/galaxy`);
    // UX05: the command map is the default view; the classic map stays one click away.
    await expect(page.getByRole('button', { name: 'Nouvelle carte de commandement' })).toHaveAttribute('aria-pressed', 'true');
    const map = page.getByRole('group', { name: /Carte de commandement/ });
    await map.getByRole('button', { name: 'Lyra', exact: true }).tap();
    expect(posts).toEqual([]); // selecting a destination sends nothing
    await page.getByRole('button', { name: 'Déplacer une flotte' }).tap();
    const planner = page.getByRole('region', { name: 'Déplacer une flotte' });
    await planner.getByRole('radio', { name: /Escadre Héliade/ }).check();
    await planner.getByRole('button', { name: 'Continuer' }).tap();
    await planner.getByRole('button', { name: 'Continuer' }).tap();
    await expect(planner.getByText(/Trajet de 2 sauts calculé par le serveur/)).toBeVisible();
    for (const control of await page.locator('.cmd-root button:visible, .galaxy-mode button').all()) {
      const box = await control.boundingBox();
      if (box) expect(box.height, await control.innerText().catch(() => '')).toBeGreaterThanOrEqual(44);
    }
    await planner.getByRole('button', { name: /Confirmer : déplacer une flotte/ }).tap();
    await expect(page.getByRole('status').filter({ hasText: 'part vers Lyra' })).toBeVisible();
    const launch = posts.find(p => p.url.endsWith('/missions'))!;
    expect(launch.body).toMatchObject({ fleet_id: ids.escadre, kind: 'DEPLOY', destination_id: ids.lyra, units: { frigate: 2, interceptor: 2 } });
    expect(String(launch.body.idempotency_key)).toMatch(/^[a-f0-9]{32}$/);
    expect(launch.csrf).toBe(session.csrf_token);
    await expect(page.getByRole('region', { name: 'Vos flottes' }).getByText('Déplacement en route')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.screenshot({ path: testInfo.outputPath(`live-command-${width}.png`), fullPage: true });
    await context.close();
  });
}
