import { startAuthentication, startRegistration, WebAuthnAbortService } from '@simplewebauthn/browser';
import type { PublicKeyCredentialCreationOptionsJSON, PublicKeyCredentialRequestOptionsJSON } from '@simplewebauthn/browser';

export type FactorChoice = 'none' | 'totp' | 'webauthn';
export async function mfaPost(path: string, body: unknown, csrf: string, signal?: AbortSignal) {
  const response = await fetch('/api/mfa/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(body), signal });
  const result = await response.json();
  if (!response.ok) throw new Error('Preuve MFA refusée ou indisponible. Utilisez un code encore inutilisé ou votre authentificateur enregistré.');
  return result;
}
export async function factorProof(choice: FactorChoice, code: string, action: string, parameters: unknown, password: string, csrf: string, signal?: AbortSignal, email?: string) {
  if (choice === 'none') return undefined;
  if (choice === 'totp') return { totp: code };
  const result = await mfaPost('assertion/options', { current_password: password, action, parameters: parameters ?? null, email: email ?? null }, csrf, signal);
  const cancel = () => WebAuthnAbortService.cancelCeremony();
  signal?.addEventListener('abort', cancel, { once: true });
  try {
    if (signal?.aborted) throw new Error('cancelled');
    const credential = await startAuthentication({ optionsJSON: result.options as PublicKeyCredentialRequestOptionsJSON });
    return { challenge_id: result.challenge_id, credential };
  } finally { signal?.removeEventListener('abort', cancel); }
}
export async function registration(options: unknown, signal?: AbortSignal) {
  const cancel = () => WebAuthnAbortService.cancelCeremony();
  signal?.addEventListener('abort', cancel, { once: true });
  try {
    if (signal?.aborted) throw new Error('cancelled');
    return await startRegistration({ optionsJSON: options as PublicKeyCredentialCreationOptionsJSON });
  } finally { signal?.removeEventListener('abort', cancel); }
}
