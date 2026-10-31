import type { SystemDetail } from '../src/galaxy/api';
import { colony, empire, origin, projection, session } from './galaxyFixture';
export { colony, empire, origin, session, universe, otherEmpire, near } from './galaxyFixture';
// Server order is by planet id: the own world is deliberately NOT the first one.
const worlds = [
  { id: '0aaaaaaa-0000-4000-8000-000000000001', name: 'Rocher Pâle', sector_capacity: 6, orbital_capacity: 1 },
  { id: '0aaaaaaa-0000-4000-8000-000000000002', name: 'Géante Brune', sector_capacity: 9, orbital_capacity: 3 },
];
export function detail(state: 'MAPPED' | 'MONITORED' = 'MONITORED'): SystemDetail {
  const base = projection().systems.find(s => s.id === origin)!;
  const own = base.planets![0];
  const link = { colony_id: colony, planet_id: own.id, name: own.name };
  return { ...base, state, planets: [...worlds, own], server_time: session.server_time, empire_id: empire,
    permissions: ['galaxy.read', 'colony.read'],
    routes: [{ id: '44444444-4444-4444-8444-444444444444', neighbor: { id: projection().systems[1].id, state: 'DETECTED' } }],
    presences: state === 'MONITORED' ? [{ kind: 'own_colony', current: true, observed_at: base.last_seen_at!, colony: link }] : [],
    colony_links: state === 'MONITORED' ? [link] : [] };
}
/** What the server sends without colony.read: generic presence, no Colony identifier at all. */
export function withoutColonyRead(): SystemDetail {
  const value = detail();
  return { ...value, observation: null, permissions: ['galaxy.read'], colony_links: [],
    presences: value.presences!.map(p => ({ ...p, colony: null })) };
}
