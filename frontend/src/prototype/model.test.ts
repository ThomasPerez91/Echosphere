import { expect, test } from "vitest";
import { validFleets } from "../fleet/api";
import { validProjection } from "../galaxy/api";
import { fleetFixture, galaxyFixture, ids, quoteFixture, SERVER_TIME } from "./fixtures";
import { eligibleFleets, engageable, fleetLines, missionPosition, offers, systemName } from "./model";
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
  expect(lines.find((l) => l.id === ids.scout)).toMatchObject({ state: "Cartographie — en route", destination: "Signal détecté" });
  // Past the arrival date the screen never pretends: the server confirms the arrival.
  const later = fleetLines(world(), Date.parse("2099-01-01T12:40:00Z"));
  expect(later.find((l) => l.id === ids.scout)?.state).toBe("Cartographie en cours");
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
    started_at: SERVER_TIME, travel_arrival_at: q.travel_arrival_at };
  expect(missionPosition(w, half, (Date.parse(SERVER_TIME) + Date.parse(q.travel_arrival_at)) / 2, q.path)).toEqual({ x: 120, y: -60 });
});
