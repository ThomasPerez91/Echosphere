import { expect, test } from '@playwright/test';

test('WebAuthn registration and login use a real Chromium authenticator at mobile width', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 320, height: 900 });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  await cdp.send('WebAuthn.addVirtualAuthenticator', { options: {
    protocol: 'ctap2', transport: 'internal', hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true,
  } });
  const challenge = Buffer.alloc(32, 7).toString('base64url');
  let credentialId = '';
  let authentication: Record<string, unknown> | undefined;
  let authenticated = true;
  const snapshot = { status: 'authenticated', user: { email: 'player@example.org', email_verified: true },
    csrf_token: 'test-session-proof', session_id: 'current', sessions: [{ id: 'current', current: true }] };
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/ready') return route.fulfill({ json: { status: 'ready', service: 'portal' } });
    if (path === '/api/auth/sessions') return route.fulfill({ json: snapshot });
    if (path === '/api/mfa/status') return route.fulfill({ json: { enabled: !!credentialId, totp: false,
      credentials: credentialId ? [{ id: 'stored', name: 'Ma passkey' }] : [] } });
    if (path === '/api/security/step-up') return route.fulfill({ json: { proof: 'action-proof' } });
    if (path === '/api/mfa/enroll/begin') return route.fulfill({ json: { challenge_id: 'registration', options: {
      challenge, rp: { id: 'localhost', name: 'Echosphere' },
      user: { id: Buffer.alloc(16, 1).toString('base64url'), name: 'player@example.org', displayName: 'Echosphere' },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }], timeout: 10000,
      attestation: 'none', authenticatorSelection: { userVerification: 'required' },
    } } });
    if (path === '/api/mfa/enroll/finish') {
      const data = route.request().postDataJSON();
      expect(data.credential.response.attestationObject).toBeTruthy();
      credentialId = data.credential.id;
      authenticated = false;
      return route.fulfill({ json: { global_logout: true, backup_codes: ['GENERATED-ONCE-TEST-CODE'] } });
    }
    if (path === '/api/auth/challenge') return route.fulfill({ json: { csrf_token: 'preauth-proof' } });
    if (path === '/api/mfa/assertion/options') return route.fulfill({ json: { challenge_id: 'login', options: {
      challenge, rpId: 'localhost', allowCredentials: [{ id: credentialId, type: 'public-key' }],
      userVerification: 'required', timeout: 10000,
    } } });
    if (path === '/api/auth/login') {
      authentication = route.request().postDataJSON().factor;
      authenticated = true;
      return route.fulfill({ json: snapshot });
    }
    return route.fulfill({ status: 404, json: { error: { code: 'unexpected_test_route' } } });
  });
  await page.goto('http://localhost:5174/');
  await page.getByLabel('Opération MFA').selectOption('webauthn');
  await page.getByLabel('Nom de l’authentificateur').fill('Ma passkey');
  await page.getByLabel('Mot de passe pour la MFA').fill('Browser authentication password !');
  await page.getByRole('button', { name: 'Valider cette opération MFA' }).click();
  await expect(page.getByRole('heading', { name: 'Vos dix codes de secours' })).toBeVisible();
  expect(authenticated).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('mfa-mobile.png'), fullPage: true });
  await page.getByRole('button', { name: 'Masquer les codes' }).click();
  await page.getByLabel('Adresse email', { exact: true }).fill('player@example.org');
  await page.getByLabel('Mot de passe', { exact: true }).fill('Browser authentication password !');
  await page.getByLabel('Preuve MFA').selectOption('webauthn');
  await page.getByRole('button', { name: 'Ouvrir ma session' }).click();
  await expect(page.getByRole('heading', { name: 'Vos connexions' })).toBeVisible();
  expect(authenticated).toBe(true);
  expect(authentication).toMatchObject({ challenge_id: 'login', credential: { id: credentialId, type: 'public-key' } });
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
});
