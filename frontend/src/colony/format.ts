// Presentation only: labels and exact formatting of server values. No game rule lives here.
import type { Amounts } from './api';

const MICRO = 1_000_000n;
const number = new Intl.NumberFormat('fr-FR');

export const resourceLabels: Record<keyof Amounts, string> = { alloys: 'Alliages', flux: 'Flux', data: 'Données' };
export const resourceSymbols: Record<keyof Amounts, string> = { alloys: '⬡', flux: 'ϟ', data: '▤' };
export const resourceKeys = ['alloys', 'flux', 'data'] as const;

const infrastructureLabels: Record<string, string> = {
  extraction_complex: 'Complexe d’extraction',
  flux_reactor: 'Réacteur de Flux',
  data_node: 'Nœud de données',
  industrial_complex: 'Complexe industriel',
  logistics_center: 'Centre logistique',
};
export const infrastructureLabel = (kind: string) => infrastructureLabels[kind] ?? kind;

/** Whole units, rounded down, from an exact micro-unit decimal string. */
export function units(value: string) {
  return number.format(BigInt(value) / MICRO);
}

/** Hourly rate with at most one decimal, rounded down. */
export function rate(value: string) {
  const tenths = BigInt(value) * 10n / MICRO;
  const whole = tenths / 10n, fraction = tenths % 10n;
  return fraction ? `${number.format(whole)},${fraction}` : number.format(whole);
}

export function ratio(stock: string, capacity: string | null) {
  if (!capacity || BigInt(capacity) === 0n) return 0;
  return Number(BigInt(stock) * 1000n / BigInt(capacity)) / 10;
}

export function duration(microseconds: string) {
  let seconds = Number(BigInt(microseconds) / 1_000_000n);
  if (BigInt(microseconds) % 1_000_000n) seconds += 1;
  const days = Math.floor(seconds / 86400), hours = Math.floor(seconds % 86400 / 3600);
  const minutes = Math.floor(seconds % 3600 / 60), rest = seconds % 60;
  if (days) return `${days} j${hours ? ` ${hours} h` : ''}`;
  if (hours) return `${hours} h${minutes ? ` ${String(minutes).padStart(2, '0')}` : ''}`;
  if (minutes) return `${minutes} min${rest ? ` ${String(rest).padStart(2, '0')} s` : ''}`;
  return `${rest} s`;
}

export const time = (value: string) => new Date(value).toLocaleString('fr-FR', {
  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });

export function costParts(cost: Amounts) {
  return resourceKeys.filter(key => BigInt(cost[key]) > 0n).map(key => ({ key, label: resourceLabels[key], value: units(cost[key]) }));
}

const messages: Record<string, string> = {
  insufficient_resources: 'Ressources insuffisantes pour cette construction.',
  queue_full: 'La file de construction est pleine.',
  sector_unavailable: 'Aucun secteur disponible pour cette action, ou le niveau demandé ne suit pas le niveau prévu.',
  unique_limit: 'Cette infrastructure est limitée à un exemplaire par colonie.',
  prerequisites_unmet: 'Une infrastructure prérequise doit d’abord être achevée.',
  refund_exceeds_capacity: 'Annulation impossible : le remboursement dépasserait la capacité de stockage. Dépensez des ressources puis réessayez.',
  order_completed: 'Cette construction est déjà terminée.',
  order_not_found: 'Cet ordre n’existe plus. La colonie a été actualisée.',
  permission_denied: 'Votre accès à cet Empire ne permet pas cette action.',
  idempotency_conflict: 'Cette action a déjà été envoyée avec un autre contenu. Actualisez la colonie.',
  authentication_required: 'Votre session a expiré ou a été déconnectée. Retournez au lobby pour entrer à nouveau.',
  csrf_denied: 'Requête refusée. Vérifiez votre accès puis réessayez.',
  origin_denied: 'Requête refusée. Vérifiez votre accès puis réessayez.',
  colony_not_found: 'Colonie indisponible pour votre accès.',
  colony_busy: 'La colonie rattrape des événements en attente. Réessayez dans un instant.',
  invalid_request: 'Action invalide. Actualisez la colonie.',
};
export function errorMessage(code: string) {
  return messages[code] ?? 'Service Game indisponible. Si vous réessayez, la même action ne sera pas dupliquée.';
}

export const reasonLabel = (reason: string | null) => reason ? errorMessage(reason) : '';
