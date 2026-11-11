import type { Relation, RelationsProjection } from "../src/relations/api";
import { empire, session, universe } from "./galaxyFixture";
export { empire, universe };
// Intercepted UI data only: shapes follow the Game API; values are test placeholders, not rules.
export const rival = "bbbbbbbb-0000-4000-8000-000000000001";
export const partner = "bbbbbbbb-0000-4000-8000-000000000002";
export const stranger = "bbbbbbbb-0000-4000-8000-000000000003";
export const planet = "bbbbbbbb-0000-4000-8000-000000000004";
export const system = "bbbbbbbb-0000-4000-8000-000000000005";
export const event = "bbbbbbbb-0000-4000-8000-000000000006";

export function neutral(overrides: Partial<Relation> = {}): Relation {
  return {
    empire: { id: rival, name: "Hégémonie Rivale" },
    contact: {
      first_source: "presence", first_seen_at: "2099-01-01T00:00:00Z", last_seen_at: "2099-01-01T00:00:00Z",
      presence: { planet_id: planet, planet_name: "Kepler b", system_id: system, system_name: "Kepler", observed_at: "2099-01-01T00:00:00Z" },
    },
    state: "NO_AGREEMENT", pact: null, proposal: null, cooldown_until: null,
    hostility: { by_self_at: null, by_counterpart_at: null },
    actions: ["propose"],
    ...overrides,
  };
}

export function relations(list: Relation[] = [neutral()], canNegotiate = true): RelationsProjection {
  return {
    at: session.server_time,
    terms: { proposal_ttl_seconds: 259200, refusal_cooldown_seconds: 86400, notice_seconds: 86400 },
    relations: canNegotiate ? list : list.map((r) => ({ ...r, actions: [] })),
    history: [],
    can_negotiate: canNegotiate,
  };
}

export const received = neutral({
  empire: { id: partner, name: "Ligue Aurorale" },
  // Introduced by its own proposal: identity and date only, never a place.
  contact: { first_source: "diplomacy", first_seen_at: "2099-01-01T00:00:00Z", last_seen_at: "2099-01-01T00:00:00Z", presence: null },
  proposal: { direction: "received", proposed_at: "2099-01-01T00:00:00Z", expires_at: "2099-01-04T00:00:00Z" },
  actions: ["accept", "refuse"],
});

export const allied = neutral({
  empire: { id: stranger, name: "Concorde" },
  contact: { first_source: "combat", first_seen_at: "2098-12-01T00:00:00Z", last_seen_at: "2098-12-01T00:00:00Z", presence: null },
  state: "PACT",
  pact: { accepted_at: "2098-12-20T00:00:00Z", notice: null },
  hostility: { by_self_at: null, by_counterpart_at: "2098-12-01T00:00:00Z" },
  actions: ["terminate"],
});
