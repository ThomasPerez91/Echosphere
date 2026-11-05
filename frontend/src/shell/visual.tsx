import type { CSSProperties, ReactNode } from 'react';
import { asset } from './assets';

/** Mono mask icon (currentColor): nav, tabs and actions of the pack. */
export function Ico({ name, className = '' }: { name: string; className?: string }) {
  return <i aria-hidden="true" className={`d-ico d-i-${name} ${className}`.trim()} />;
}

/** Coloured SVG icon of the pack, purely decorative. */
export function Pic({ src, size = 28, className }: { src: string; size?: number; className?: string }) {
  return <img src={asset(src)} alt="" width={size} height={size} className={className} />;
}

export function Bar({ value, tone, label }: { value: number; tone?: 'amber'; label?: string }) {
  const p = Math.max(0, Math.min(100, value));
  return <span className={`d-bar${tone ? ` d-${tone}` : ''}`} role={label ? 'progressbar' : undefined} aria-label={label}
    aria-valuemin={label ? 0 : undefined} aria-valuemax={label ? 100 : undefined} aria-valuenow={label ? Math.round(p) : undefined}>
    <i style={{ '--d-p': `${p}%` } as CSSProperties} /></span>;
}

/** Panel header of the mockup: icon, title, optional link on the right. */
export function PanelHead({ icon, title, id, more, children }: { icon: string; title: string; id?: string; more?: { href: string; label: string } | null; children?: ReactNode }) {
  return <header className="d-panel-head">
    <h2 id={id}><Pic src={icon} />{title}</h2>
    {more && <a href={more.href} className="d-more">{more.label} <span aria-hidden="true">→</span></a>}
    {children}
  </header>;
}

/**
 * Honest placeholder for a mockup feature the Game backend does not provide yet: the layout stays,
 * no invented number is shown.
 */
export function Pending({ what, compact: small = false }: { what: string; compact?: boolean }) {
  return <div className={`d-pending${small ? ' d-pending--small' : ''}`}>
    <strong>Implémentation backend nécessaire</strong>
    <span>{what}</span>
  </div>;
}
