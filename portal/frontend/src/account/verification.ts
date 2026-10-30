export function consumeVerificationFragment(): string | null {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get('verify-email');
  if (token !== null) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
  return token !== null && /^[A-Za-z0-9_-]{43}$/.test(token) ? token : null;
}
