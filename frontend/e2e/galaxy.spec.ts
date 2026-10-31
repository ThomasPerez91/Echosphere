import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { active, empire, projection, session, universe } from "../tests/galaxyFixture";
// Intercepted UI only; smoke_galaxy_compose exercises real HTTPS/services/worker separately.

async function routes(page: Page) {
  let state = projection();
  const counter = { posts: 0 };
  await page.route("**/api/ready", (r) => r.fulfill({ json: { status: "ready" } }));
  await page.route(`**/api/game/${universe}/session`, (r) => r.fulfill({ json: session }));
  await page.route(`**/api/game/${universe}/colonies`, (r) => r.fulfill({ json: { colonies: [] } }));
  await page.route(`**/api/game/${universe}/galaxy`, (r) =>
    r.fulfill({ json: { empires: [{ id: empire, name: "Empire test" }] } }),
  );
  await page.route(`**/api/game/${universe}/galaxy/${empire}`, (r) => r.fulfill({ json: state }));
  await page.route(`**/api/game/${universe}/exploration/${empire}/missions`, (r) => {
    counter.posts++;
    state = projection([active()]);
    return r.fulfill({ json: { mission_id: active().id, galaxy: state } });
  });
  return counter;
}
const viewBox = (page: Page) =>
  page.locator("svg.galaxy-map").evaluate((e) => e.getAttribute("viewBox")!.split(" ").map(Number));

for (const width of [320, 390, 768, 1440]) {
  test(`galaxy ${width}px: pan, zoom, keyboard, list, touch and confirmed expedition`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({ viewport: { width, height: 800 }, hasTouch: true });
    const page = await context.newPage();
    const counter = await routes(page);
    await page.goto(`/#universe/${universe}/galaxy`);
    const map = page.locator("svg.galaxy-map");
    await expect(map).toBeVisible();
    await expect(page.getByRole("heading", { name: "Système d’origine" })).toBeVisible();
    expect(counter.posts).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    // Keyboard on the map: arrows pan, +/- zoom, 0 recentres.
    const initial = await viewBox(page);
    await map.focus();
    await page.keyboard.press("ArrowRight");
    expect((await viewBox(page))[0]).toBeGreaterThan(initial[0]);
    await page.keyboard.press("+");
    expect((await viewBox(page))[2]).toBeLessThan(initial[2]);
    await page.keyboard.press("0");
    expect(await viewBox(page)).toEqual(initial);

    // Mouse drag pans inside the map without scrolling the page.
    await map.scrollIntoViewIfNeeded();
    const scroll = await page.evaluate(() => scrollY);
    let box = (await map.boundingBox())!;
    await page.mouse.move(box.x + 12, box.y + box.height - 12);
    await page.mouse.down();
    await page.mouse.move(box.x + 60, box.y + box.height - 40, { steps: 4 });
    await page.mouse.up();
    expect((await viewBox(page))[0]).toBeLessThan(initial[0]);
    expect(await page.evaluate(() => scrollY)).toBe(scroll);

    // Wheel over the map zooms and never scrolls the page.
    await page.getByRole("button", { name: "Recentrer" }).click();
    box = (await map.boundingBox())!;
    const beforeWheel = await page.evaluate(() => scrollY);
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -200);
    await expect.poll(async () => (await viewBox(page))[2]).toBeLessThan(initial[2]);
    expect(await page.evaluate(() => scrollY)).toBe(beforeWheel);

    // Touch drag pans the map (pointerType touch) and keeps the page still.
    await page.getByRole("button", { name: "Recentrer" }).click();
    box = (await map.boundingBox())!;
    const beforeTouch = await page.evaluate(() => scrollY);
    const cdp = await context.newCDPSession(page);
    const at = (dx: number) => [{ x: box.x + 15 + dx, y: box.y + box.height - 15 }];
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(0) });
    for (const dx of [10, 25, 40]) await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at(dx) });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    expect((await viewBox(page))[0]).toBeLessThan(initial[0]);
    expect(await page.evaluate(() => scrollY)).toBe(beforeTouch);

    // Zoom controls are real buttons with touch-sized targets.
    for (const name of ["Zoom avant", "Zoom arrière", "Recentrer"]) {
      const control = (await page.getByRole("button", { name }).boundingBox())!;
      expect(control.height).toBeGreaterThanOrEqual(44);
      expect(control.width).toBeGreaterThanOrEqual(44);
    }

    // Textual list is an equivalent selection path.
    await page.locator(".galaxy-list").getByRole("button", { name: /Signal détecté 2/ }).click();
    await expect(page.getByRole("heading", { name: "Signal détecté 2", level: 2 })).toBeVisible();

    // Keyboard selection on a map node, then explicit confirmation.
    const node = page.getByRole("button", { name: "Signal détecté 1, Détecté, position approximative partagée" });
    await node.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Signal détecté 1", level: 2 })).toBeVisible();
    const prepare = page.getByRole("button", { name: "Préparer l’expédition" });
    await prepare.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Aucune annulation, aucun rappel, aucun remboursement");
    await page.keyboard.press("Escape");
    await expect(prepare).toBeFocused();
    expect(counter.posts).toBe(0);
    await prepare.click();
    const confirm = dialog.getByRole("button", { name: "Confirmer l’expédition" });
    const target = (await confirm.boundingBox())!;
    expect(target.y + target.height).toBeLessThanOrEqual(800);
    expect(target.height).toBeGreaterThanOrEqual(44);
    await confirm.click();
    await expect(page.getByText(/Expédition acceptée par le serveur/)).toBeVisible();
    await expect(page.getByText("Capacité engagée")).toBeVisible();
    await expect(page.getByRole("progressbar", { name: "Avancement estimé de l’expédition" })).toBeVisible();
    expect(counter.posts).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`galaxy-${width}.png`), fullPage: true });
    await context.close();
  });
}
