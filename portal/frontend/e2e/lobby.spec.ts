import { expect, test } from '@playwright/test';

for (const width of [320, 1440]) {
  test(`owned lobby confirmation at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    let confirmed = false;
    const calls: string[] = [];
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      calls.push(route.request().method() + ' ' + path);
      if (path === '/api/ready') return route.fulfill({ json: { status: 'ready', service: 'portal' } });
      if (path === '/api/auth/sessions') return route.fulfill({ json: { status: 'authenticated', user: { email: 'player@example.org', email_verified: true },
        csrf_token: 'session-proof', session_id: 'current', sessions: [{ id: 'current', current: true }] } });
      if (path === '/api/mfa/status') return route.fulfill({ json: { enabled: false, totp: false, credentials: [] } });
      if (path === '/api/auth/navigation') { confirmed = true; return route.fulfill({ json: {} }); }
      if (path === '/api/lobby/memberships') return route.fulfill({ json: {
        memberships: [{ membership_id: 'one', universe_id: 'universe', name: 'UNIVERS'.repeat(17), desired_status: 'active',
          applied_status: confirmed ? 'active' : null, delivery_state: confirmed ? 'applied' : 'pending', expired: false,
          valid_until: '2026-10-30T20:00:00Z', last_checked_at: confirmed ? '2026-10-30T12:00:00Z' : null, entry_available: false }],
        revocations: [{ scope: 'device', state: confirmed ? 'acknowledged' : 'pending', created_at: '2026-10-30T12:00:00Z' }],
      } });
      return route.fulfill({ status: 404 });
    });
    await page.goto('/');
    await expect(page.getByText('Confirmation de Game en attente')).toBeVisible();
    expect(calls.filter(item => item.startsWith('POST'))).toEqual([]);
    await page.getByRole('button', { name: 'Actualiser mes parties' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByText('Participation confirmée par Game')).toBeVisible();
    await expect(page.getByText(/révocation confirmée par les services Game/)).toBeVisible();
    expect(calls.filter(item => item.startsWith('POST'))).toEqual(['POST /api/auth/navigation']);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('lobby.png'), fullPage: true });
  });
}
