export type SecurityLink = { kind: 'reset' | 'email'; token: string } | { kind: 'alert' };
export function consumeSecurityFragment(): SecurityLink | null {
  const hash = window.location.hash.slice(1);
  if (hash === 'security-alert') {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    return { kind: 'alert' };
  }
  const values = new URLSearchParams(hash);
  for (const [name, kind] of [['reset-password', 'reset'], ['confirm-email-change', 'email']] as const) {
    const token = values.get(name);
    if (token !== null) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
      return /^[A-Za-z0-9_-]{43}$/.test(token) ? { kind, token } : null;
    }
  }
  return null;
}
