import type { Resource } from '../colony/api';

/** Self-hosted assets of the Echosphere visual pack (frontend/public/assets). */
export const asset = (path: string) => `/assets/${path}`;

export const resourceIcon = { alloys: 'icons/ressources/ressource-alliages.svg', flux: 'icons/ressources/ressource-flux.svg',
  data: 'icons/ressources/ressource-donnees.svg' } as const;

const planets = ['kareth', 'elyndra', 'thalos', 'ishara', 'veyl'] as const;
/** Cosmetic illustration chosen from an id (no game meaning): same picture for the same world. */
export function planetImage(id: string) {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return asset(`img/planets/${planets[h % planets.length]}.webp`);
}

const whole = new Intl.NumberFormat('fr-FR');
const tenth = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
/** Mockup style: 184,2 K above 100 000, whole units below. */
export const compact = (units: number) => units >= 100_000 ? `${tenth.format(Math.floor(units / 100) / 10)} K` : whole.format(Math.floor(units));
export const integer = (units: number) => whole.format(Math.floor(units));

/**
 * Stock estimated between two server readings: settled stock + hourly rate × elapsed time, capped
 * by the capacity. Display only; the server stays authoritative and every read replaces it.
 */
export function estimate(resource: Resource, elapsedMs: number) {
  const stock = Number(resource.stock) / 1e6, rate = Number(resource.rate_per_hour) / 1e6;
  const capacity = resource.capacity === null ? Infinity : Number(resource.capacity) / 1e6;
  if (stock >= capacity) return stock;
  return Math.min(stock + Math.max(0, rate) * Math.max(0, elapsedMs) / 3.6e6, capacity);
}

const relative = new Intl.RelativeTimeFormat('fr-FR', { numeric: 'auto' });
/** « Il y a 3 h » from a server date and the server clock. */
export function ago(date: string, now: number) {
  const seconds = Math.round((Date.parse(date) - now) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return relative.format(seconds, 'second');
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute');
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), 'hour');
  return relative.format(Math.round(seconds / 86400), 'day');
}

export const infrastructureImage: Record<string, string> = {
  extraction_complex: 'complexe-extraction', flux_reactor: 'reacteur-flux', data_node: 'noeud-donnees',
  industrial_complex: 'complexe-industriel', logistics_center: 'centre-logistique',
  // COL-11: existing illustrations (docking ring with ships, surface laboratory domes).
  orbital_shipyard: 'anneau-amarrage', research_center: 'laboratoire-avance',
};
export const buildingImage = (kind: string) => asset(`img/batiments/${infrastructureImage[kind] ?? 'centre-de-commandement'}.webp`);
