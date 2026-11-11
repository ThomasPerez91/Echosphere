import { createElement, useSyncExternalStore } from 'react';
import type { AnchorHTMLAttributes, MouseEvent } from 'react';

/** Portal pages. Paths are real URLs (the dev server and the local edge fall back to index.html). */
export const paths = {
  home: '/', login: '/connexion', register: '/inscription', games: '/parties', newGame: '/parties/nouvelle', account: '/compte', join: '/rejoindre',
} as const;
export type Page = keyof typeof paths | 'missing';

export function pageOf(pathname: string): Page {
  const clean = pathname.replace(/\/+$/, '') || '/';
  const found = (Object.entries(paths) as [keyof typeof paths, string][]).find(([, path]) => path === clean);
  return found ? found[0] : 'missing';
}

const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => {
  listeners.add(listener); window.addEventListener('popstate', listener);
  return () => { listeners.delete(listener); window.removeEventListener('popstate', listener); };
};

export function usePath() {
  return useSyncExternalStore(subscribe, () => window.location.pathname, () => '/');
}

/** Client-side navigation; keeps the query, never a fragment (fragments carry one-time tokens). */
export function navigate(path: string, { replace = false } = {}) {
  if (window.location.pathname === path) return;
  window.history[replace ? 'replaceState' : 'pushState'](null, '', path);
  listeners.forEach(listener => listener());
  if (!/jsdom/i.test(navigator.userAgent)) window.scrollTo({ top: 0 });
}

/** Real link (works with a new tab, copy, keyboard) that navigates without reloading. */
export function Link({ to, onClick, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const follow = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); navigate(to);
  };
  return createElement('a', { ...rest, href: to, onClick: follow });
}
