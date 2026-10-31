import type { SystemDetail } from '../src/galaxy/api';
import { colony, empire, origin, projection, session } from './galaxyFixture';
export { colony, empire, origin, session, universe, otherEmpire, near } from './galaxyFixture';
export function detail(state: 'MAPPED' | 'MONITORED' = 'MONITORED'): SystemDetail {
  const base = projection().systems.find(s => s.id === origin)!;
  const link = { colony_id: colony, planet_id: base.planets![0].id, name: base.planets![0].name };
  return { ...base, state, server_time: session.server_time, empire_id: empire,
    permissions: ['galaxy.read', 'colony.read'],
    routes: [{ id: '44444444-4444-4444-8444-444444444444', neighbor: { id: projection().systems[1].id, state: 'DETECTED' } }],
    presences: state === 'MONITORED' ? [{ kind: 'own_colony', current: true, observed_at: base.last_seen_at!, colony: link }] : [],
    colony_links: state === 'MONITORED' ? [link] : [] };
}
