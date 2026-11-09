import { expect, test } from "vitest";
import { validFleets } from "../fleet/api";
import { validProjection } from "../galaxy/api";
import { fleetFixture, galaxyFixture, ids, quoteFixture, SERVER_TIME } from "../prototype/fixtures";
import { defaultUnits, knownHops, eligibleFleets, engageable, fleetLines, missionPosition, missionRoute, missionRouteLabel, offers, point, recallable, serverPath, systemName } from "./model";
import type { World } from "./model";

const world = (): World => ({ fleets: fleetFixture(), galaxy: galaxyFixture() });

test("fixtures pass the production API validators (contract-shaped, no extra field)", () => {
  expect(validFleets(fleetFixture(), fleetFixture().empire.id)).toBe(true);
  expect(validProjection(galaxyFixture(), galaxyFixture().empire.id)).toBe(true);
});

test("Fog of War: a detected signal is never named and only offers a survey", () => {
  const w = world();
  expect(systemName(w, ids.signalA)).toBe("Signal détecté");
  expect(galaxyFixture().systems.find((s) => s.id === ids.signalA)).not.toHaveProperty("name");
  expect(offers(w, ids.signalA).map((o) => o.kind)).toEqual(["SURVEY"]);
  expect(systemName(w, "99999999-0000-4000-8000-000000000000")).toBe("Système hors de vos connaissances");
});

test("a known system offers move, colonize and attack per known free world, never on an own colony", () => {
  const w = world();
  expect(offers(w, ids.lyra).map((o) => o.kind)).toEqual(["DEPLOY", "COLONIZE", "ATTACK"]);
  expect(offers(w, ids.home).map((o) => o.kind)).toEqual(["DEPLOY"]); // Aube Prime is ours
  expect(offers(w, ids.draco).map((o) => o.kind)).toEqual(["DEPLOY"]); // no known planet
});

test("eligible fleets and default units follow the unit families already offered by the Fleet screen", () => {
  const w = world();
  expect(eligibleFleets(w, "SURVEY", ids.signalA).map((f) => f.name)).toEqual(["Garnison Aube Prime", "Sonde Kepler"]);
  const garrison = w.fleets.fleets!.find((f) => f.id === ids.garrison)!;
  expect(engageable(w, garrison, "SURVEY")).toEqual({ probe: 1 });
  expect(engageable(w, garrison, "ATTACK")).toEqual({ interceptor: 3 });
  expect(eligibleFleets(w, "COLONIZE", ids.lyra).map((f) => f.name)).toEqual(["Pionnier"]);
  expect(eligibleFleets(w, "DEPLOY", ids.vesta).map((f) => f.id)).not.toContain(ids.kepler); // already there
});

test("without fleet.command nothing is offered", () => {
  const w = world();
  w.fleets.permissions = w.fleets.permissions.filter((p) => p !== "fleet.command");
  expect(offers(w, ids.lyra)).toEqual([]);
});

test("a reason in plain words replaces an impossible action", () => {
  const w = world();
  w.fleets.fleets = w.fleets.fleets!.filter((f) => !f.stacks.probe);
  expect(offers(w, ids.signalA)[0].reason).toMatch(/Aucune sonde/);
});

test("fleet lines say where each fleet is, what it does and where it goes", () => {
  const lines = fleetLines(world(), Date.parse(SERVER_TIME));
  expect(lines.find((l) => l.id === ids.kepler)).toMatchObject({ where: "Vesta", state: "Stationnée", destination: null });
  expect(lines.find((l) => l.id === ids.garrison)).toMatchObject({ state: "En garnison", garrison: true });
  expect(lines.find((l) => l.id === ids.scout)).toMatchObject({ state: "Cartographie en route", destination: "Signal détecté",
    arrival: "2099-01-01T12:20:00Z" });
  // Past the arrival date the screen never pretends: the server confirms the result.
  expect(fleetLines(world(), Date.parse("2099-01-01T12:30:00Z")).find((l) => l.id === ids.scout)?.state).toBe("Cartographie en cours");
  expect(fleetLines(world(), Date.parse("2099-01-01T12:40:00Z")).find((l) => l.id === ids.scout)?.state)
    .toBe("Cartographie — résultat attendu du serveur");
});

test("a moving fleet is drawn along the server path between its dates (display estimate)", () => {
  const w = world();
  const m = w.fleets.missions![0];
  const start = missionPosition(w, m, Date.parse(m.started_at))!;
  const end = missionPosition(w, m, Date.parse(m.travel_arrival_at) + 1)!;
  expect(start).toEqual({ x: -110, y: 70 });
  expect(end).toEqual({ x: -150, y: -90 });
  const q = quoteFixture(ids.home, "DEPLOY", ids.lyra, { frigate: 2 }, null, SERVER_TIME);
  if ("error" in q) throw new Error(q.error);
  const half = { ...m, origin: { id: ids.home, state: "MONITORED" as const }, destination: { id: ids.lyra, state: "MAPPED" as const },
    started_at: SERVER_TIME, travel_arrival_at: q.travel_arrival_at, path: q.path, hops: q.hops };
  expect(missionPosition(w, half, (Date.parse(SERVER_TIME) + Date.parse(q.travel_arrival_at)) / 2)).toEqual({ x: 120, y: -60 });
  expect(missionRoute(w, half)?.kind).toBe("server");
  expect(missionRouteLabel(half, missionRoute(w, half)!)).toBe("Trajet de la mission");
});

test("UX-API-01: a path system missing from the map falls back to the estimated departure–destination segment", () => {
  const w = world();
  const m = { ...w.fleets.missions![0], origin: { id: ids.home, state: "MONITORED" as const },
    destination: { id: ids.lyra, state: "MAPPED" as const }, hops: 2,
    path: [ids.home, "00000000-0000-4000-8000-0000000000ff", ids.lyra] };
  const route = missionRoute(w, m)!;
  expect(route.kind).toBe("estimated");
  expect(route.points).toEqual([point(w, ids.home), point(w, ids.lyra)]);
  expect(missionRouteLabel(m, route)).toMatch(/estimé/);
  expect(missionPosition(w, m, Date.parse(m.started_at))).toEqual(point(w, ids.home));
});

test("UX-API-01: a 0-hop mission stays on its system, without a line", () => {
  const w = world();
  const m = { ...w.fleets.missions![0], origin: { id: ids.home, state: "MONITORED" as const },
    destination: { id: ids.home, state: "MONITORED" as const }, hops: 0, path: [ids.home] };
  expect(missionRoute(w, m)).toEqual({ kind: "server", points: [point(w, ids.home)] });
  expect(missionPosition(w, m, Date.parse(m.started_at) + 1000)).toEqual(point(w, ids.home));
});

test("UX-API-01: a return mirrors the outbound path and says so", () => {
  const w = world();
  const q = quoteFixture(ids.home, "DEPLOY", ids.lyra, { frigate: 2 }, null, SERVER_TIME);
  if ("error" in q) throw new Error(q.error);
  const m = { ...w.fleets.missions![0], status: "returning" as const, origin: { id: ids.home, state: "MONITORED" as const },
    destination: { id: ids.lyra, state: "MAPPED" as const }, path: q.path, hops: q.hops, started_at: SERVER_TIME,
    travel_arrival_at: q.travel_arrival_at, due_at: q.travel_arrival_at, recalled_at: null,
    return_at: new Date(2 * Date.parse(q.travel_arrival_at) - Date.parse(SERVER_TIME)).toISOString() };
  const route = missionRoute(w, m)!;
  expect(missionRouteLabel(m, route)).toBe("Retour estimé en miroir de l’aller");
  // Leaving the destination at due_at, home at return_at.
  expect(missionPosition(w, m, Date.parse(m.due_at))).toEqual(point(w, ids.lyra));
  expect(missionPosition(w, m, Date.parse(m.return_at!) + 1)).toEqual(point(w, ids.home));
});

test("D-UX-4/5 defaults: one probe, exactly one colonizer, the task fleet for a move, nothing for an attack or from a garrison", () => {
  const w = world();
  const f = (id: string) => w.fleets.fleets!.find((x) => x.id === id)!;
  expect(defaultUnits(w, f(ids.kepler), "SURVEY")).toEqual({ probe: 1 });
  expect(defaultUnits(w, f(ids.pionnier), "COLONIZE")).toEqual({ colonizer: 1 });
  expect(defaultUnits(w, f(ids.escadre), "DEPLOY")).toEqual({ frigate: 2, interceptor: 2 });
  expect(defaultUnits(w, f(ids.escadre), "ATTACK")).toEqual({});
  for (const kind of ["SURVEY", "DEPLOY", "ATTACK"] as const) expect(defaultUnits(w, f(ids.garrison), kind)).toEqual({});
});

test("a server path is used only when coherent; otherwise nothing is drawn as the real route", () => {
  const w = world();
  const q = quoteFixture(ids.home, "DEPLOY", ids.lyra, { frigate: 2 }, null, SERVER_TIME);
  if ("error" in q) throw new Error(q.error);
  expect(serverPath(w, q, ids.home)).toEqual([ids.home, ids.vesta, ids.lyra]);
  expect(serverPath(w, { ...q, path: undefined }, ids.home)).toBeUndefined(); // current contract
  expect(serverPath(w, { ...q, path: [ids.home, ids.lyra] }, ids.home)).toBeUndefined(); // hops + 1 entries
  expect(serverPath(w, q, ids.vesta)).toBeUndefined(); // must start at the fleet's system
  expect(serverPath(w, { ...q, path: [ids.home, "99999999-0000-4000-8000-000000000000", ids.lyra] }, ids.home)).toBeUndefined();
});

test("recall follows the Fleet screen rule: while travelling, or until the battle for an attack", () => {
  const m = world().fleets.missions![0];
  expect(recallable(m, Date.parse("2099-01-01T12:10:00Z"))).toBe(true);
  expect(recallable(m, Date.parse("2099-01-01T12:25:00Z"))).toBe(false);
  expect(recallable({ ...m, status: "returning" }, Date.parse("2099-01-01T12:10:00Z"))).toBe(false);
  const attack = { ...m, kind: "ATTACK" as const, due_at: "2099-01-02T11:40:00Z",
    attack: { engagement_id: m.id, battle_at: "2099-01-02T11:40:00Z", state: "pending" as const } };
  expect(recallable(attack, Date.parse("2099-01-01T18:00:00Z"))).toBe(true);
  expect(recallable({ ...attack, attack: { ...attack.attack, state: "resolved" as const } }, Date.parse("2099-01-01T18:00:00Z"))).toBe(false);
});

test("distance = fewest jumps from the nearest own colony over the known routes, unknown without a route", () => {
  const w = world();
  expect(knownHops(w, ids.home)).toEqual({ hops: 0, from: ids.home });
  expect(knownHops(w, ids.vesta)).toEqual({ hops: 1, from: ids.home });
  expect(knownHops(w, ids.lyra)).toEqual({ hops: 2, from: ids.home });
  expect(knownHops(w, ids.signalC)).toEqual({ hops: 3, from: ids.home });
  const cut = { ...w, galaxy: { ...w.galaxy, routes: w.galaxy.routes.filter((r) => r.b_id !== ids.signalB) } };
  expect(knownHops(cut, ids.signalB)).toBeNull();
});
