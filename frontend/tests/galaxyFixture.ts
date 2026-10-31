import type { Mission, Projection } from "../src/galaxy/api";
// Intercepted UI data only: shapes follow the Game API; values are test placeholders, not rules.
export const universe = "052d4535-79c7-413b-ace3-47c732561fbd";
export const empire = "8c315025-a146-4510-9347-475838286851";
export const otherEmpire = "1b0f8f8e-6a3c-4f7e-9d1a-0c5e2f6a7b80";
export const colony = "7d1c56a0-3c52-4e8e-9d6b-2b1f4b0f8a11";
export const origin = "11111111-1111-4111-8111-111111111111";
export const near = "22222222-2222-4222-8222-222222222222";
export const twin = "33333333-3333-4333-8333-333333333333";
export const mission = "44444444-4444-4444-8444-444444444444";
const route = (n: number, a: string, b: string) => ({
  id: `aaaaaaa${n}-aaaa-4aaa-8aaa-aaaaaaaaaaaa`,
  a_id: a,
  b_id: b,
});
export const amounts = (a: number, f: number, d: number) => ({
  alloys: String(a * 1e6),
  flux: String(f * 1e6),
  data: String(d * 1e6),
});
export const session = {
  universe_id: universe,
  universe_name: "Galaxy test",
  csrf_token: "a".repeat(64),
  expires_at: "2099-01-01T08:00:00Z",
  idle_expires_at: "2099-01-01T02:00:00Z",
  access_valid_until: "2099-01-01T08:00:00Z",
  server_time: "2099-01-01T00:00:00Z",
  portal_url: "https://portal.example.org",
};
export function active(): Mission {
  return {
    id: mission,
    destination_id: near,
    colony_id: colony,
    status: "active",
    started_at: session.server_time,
    due_at: "2099-01-01T00:45:00Z",
    cost: amounts(50, 60, 25),
    report: null,
  };
}
export function projection(missions: Mission[] = [], id = empire): Projection {
  const engaged = missions.some((m) => m.status === "active");
  return {
    server_time: session.server_time,
    empire: { id, name: id === empire ? "Empire test" : "Second Empire" },
    permissions: ["colony.read", "galaxy.read", "exploration.read", "exploration.start"],
    systems: [
      {
        id: origin,
        state: "MONITORED",
        x: 480,
        y: 520,
        discovered_at: session.server_time,
        name: "Système d’origine",
        mapped_at: session.server_time,
        last_seen_at: session.server_time,
        observation: { own_colony_ids: [colony] },
        planets: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            name: "Nouvelle Aube",
            sector_capacity: 12,
            orbital_capacity: 2,
          },
        ],
      },
      { id: near, state: "DETECTED", x: 650, y: 450, discovered_at: session.server_time },
      { id: twin, state: "DETECTED", x: 650, y: 450, discovered_at: session.server_time },
    ],
    routes: [route(1, origin, near), route(2, origin, twin)],
    sources: [{ id: colony, name: "Nouvelle Aube", stocks: amounts(500, 500, 500) }],
    options: [near, twin].map((destination) => ({
      colony_id: colony,
      destination_id: destination,
      hops: 1,
      cost: amounts(50, 60, 25),
      duration_us: String(45 * 60 * 1e6),
      reason: engaged ? "exploration_active" : null,
    })),
    missions,
  };
}
