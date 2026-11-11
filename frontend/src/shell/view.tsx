import { useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { asset } from './assets';
import { Bar, Pic } from './visual';

/**
 * Header of a redrawn view (DA of 10/11/2026): breadcrumb, title and text on the dark left part,
 * the view banner on the right. A banner not produced yet falls back to the shared horizon picture.
 */
export function ViewHero({ crumb, title, text, banner, children }: {
  crumb: string; title: string; text: string; banner: string; children?: ReactNode;
}) {
  return <section className="d-vhero d-scope" style={{ '--d-banner': `url(${asset(`img/vues/${banner}.webp`)})` } as CSSProperties}>
    <div className="d-vhero-text">
      <nav className="d-crumbs" aria-label="Fil d’Ariane"><span>Empire</span><span aria-hidden="true">›</span><span aria-current="page">{crumb}</span></nav>
      <h1 tabIndex={-1}>{title}</h1>
      <p>{text}</p>
    </div>
    {children && <div className="d-vhero-act">{children}</div>}
  </section>;
}

export type Kpi = { icon: string; value: ReactNode; label: string; bar?: number; note?: string };

/** Row of figure cards under the hero; every value comes from a server projection. */
export function Kpis({ items, label }: { items: Kpi[]; label: string }) {
  return <ul className="d-kpis d-scope" aria-label={label}>
    {items.map(item => <li key={item.label} className="d-card d-kpi">
      <span className="d-kpi-ico"><Pic src={item.icon} size={34} /></span>
      <span className="d-kpi-body"><strong>{item.value}</strong><span>{item.label}</span>
        {item.bar !== undefined && <Bar value={item.bar} />}
        {item.note && <small>{item.note}</small>}</span>
    </li>)}
  </ul>;
}

/**
 * Illustration of an item (ship, technology, report category…). Until its picture is produced
 * (see docs/visual-reference/assets-a-produire.md), a framed placeholder with the item's icon.
 */
export function Thumb({ src, icon, className = '' }: { src: string | null; icon: string; className?: string }) {
  const [missing, setMissing] = useState(false);
  return <span className={`d-thumb ${className}`.trim()} aria-hidden="true">
    {src && !missing ? <img src={asset(src)} alt="" loading="lazy" onError={() => setMissing(true)} />
      : <span className="d-thumb-ph"><Pic src={icon} size={30} /></span>}
  </span>;
}

/** Planned pictures (placeholders until the user provides them). */
export const shipImage = (kind: string) => `img/vaisseaux/${({
  probe: 'sonde', freighter: 'cargo-leger', extractor: 'extracteur', colonizer: 'colonisateur',
  interceptor: 'intercepteur', frigate: 'fregate', cruiser: 'croiseur',
} as Record<string, string>)[kind] ?? kind}.webp`;
const techFiles: Record<string, string> = {
  engineering: 'fabrication-modulaire', energy: 'gestion-energetique', computation: 'calcul-scientifique', xenoscience: 'protocoles-analyse',
};
export const technologyImage = (id: string) => {
  const [domain, tier] = id.split('_');
  return `img/technologies/${techFiles[domain] ?? domain}-${tier ?? '1'}.webp`;
};
export const reportImage = (category: string) => `img/rapports/${category}.webp`;
export const domainImage = (domain: string) => `img/domaines/${domain}.webp`;
