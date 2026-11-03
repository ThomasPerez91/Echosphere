import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { GalaxyScreen } from "./components/GalaxyScreen";
import { LiveCommandMap } from "./command/LiveCommandMap";
import type { FleetProjection } from "./fleet/api";
import type { Projection } from "./galaxy/api";
import { fleetFixture, galaxyFixture, ids, quoteFixture, SERVER_TIME } from "./prototype/fixtures";

// Contract-shaped projections (the prototype fixtures pass the production validators) served
// through a stubbed fetch: the live container is exercised end to end against the API module.
const universe = "90000000-0000-4000-8000-000000000001";
const first = galaxyFixture().empire;
const second = { id: "10000000-0000-4000-8000-000000000002", name: "Ligue de Vesta" };
const csrf = "c".repeat(64);
const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
type Reply = ReturnType<typeof json>;
type Call = [string, RequestInit | undefined];

afterEach(() => { cleanup(); vi.unstubAllGlobals(); try { window.localStorage.clear(); } catch { /* none */ } });

const galaxyOf = (empire = first): Projection => ({ ...galaxyFixture(), empire });
const fleetsOf = (empire = first): FleetProjection => ({ ...fleetFixture(), empire });
const quote = (withPath: boolean) => {
  const q = quoteFixture(ids.home, "DEPLOY", ids.lyra, { frigate: 2, interceptor: 2 }, null, SERVER_TIME);
  if ("error" in q) throw new Error(q.error);
  if (!withPath) delete q.path;
  return q;
};
/** What the server would answer after the launch: the Escadre is moving, with its mission. */
const launched = (): FleetProjection => {
  const p = fleetsOf();
  const q = quote(false);
  const m = { ...p.missions![0], id: "61000000-0000-4000-8000-000000000001", fleet_id: ids.escadre, kind: "DEPLOY" as const,
    origin: p.systems!.find((s) => s.id === ids.home)!, destination: p.systems!.find((s) => s.id === ids.lyra)!, hops: 2,
    stacks: { frigate: 2, interceptor: 2 }, started_at: SERVER_TIME, travel_arrival_at: q.travel_arrival_at, due_at: q.due_at };
  return { ...p, missions: [m, ...p.missions!], fleets: p.fleets!.map((f) => (f.id === ids.escadre
    ? { ...f, status: "MOVING" as const, system: null, mission_id: m.id } : f)) };
};

function serve(route: (url: string, init?: RequestInit) => Reply | undefined, empires = [first]) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const answer = route(url, init);
    if (answer) return answer;
    if (url.endsWith("/galaxy") || url.endsWith("/fleets")) return json({ empires });
    const empire = empires.find((e) => url.endsWith(`/galaxy/${e.id}`) || url.endsWith(`/fleets/${e.id}`));
    if (empire && url.includes("/galaxy/")) return json(galaxyOf(empire));
    if (empire) return json(fleetsOf(empire));
    return json({ error: { code: "unavailable" } }, 503);
  });
  vi.stubGlobal("fetch", fetcher);
  return { calls: () => fetcher.mock.calls as unknown as Call[] };
}
const live = (props: { initialEmpire?: string } = {}) => {
  const lost = vi.fn();
  const economy = vi.fn();
  render(<StrictMode><LiveCommandMap universe={universe} enabled csrf={csrf} onSessionLost={lost} onEconomyChanged={economy} {...props} /></StrictMode>);
  return { lost, economy };
};
const map = async () => within(await screen.findByRole("group", { name: /Carte de commandement/ }));
const posts = (calls: Call[]) => calls.filter(([, init]) => init?.method === "POST");

async function planMoveToLyra() {
  fireEvent.click((await map()).getByRole("button", { name: "Lyra" }));
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  const p = within(screen.getByRole("region", { name: "Déplacer une flotte" }));
  fireEvent.click(p.getByRole("radio", { name: /Escadre Héliade/ }));
  fireEvent.click(p.getByRole("button", { name: "Continuer" }));
  fireEvent.click(p.getByRole("button", { name: "Continuer" }));
  return p;
}

test("mount reads both projections of the same Empire only; selecting a system sends nothing", async () => {
  const { calls } = serve(() => undefined);
  live();
  fireEvent.click((await map()).getByRole("button", { name: "Lyra" }));
  expect(screen.getByRole("heading", { name: "Lyra", level: 2 })).toBeVisible();
  expect(posts(calls())).toEqual([]);
  const urls = calls().map(([u]) => u);
  expect(urls).toContain(`/api/game/${universe}/galaxy/${first.id}`);
  expect(urls).toContain(`/api/game/${universe}/fleets/${first.id}`);
  expect(screen.getByText(`Empire : ${first.name}`)).toBeVisible();
});

test("the Fleet projection follows the map's Empire; switching Empire re-reads both, never mixes them", async () => {
  // The Fleet list puts the second Empire first: the container must still align on the map's Empire.
  const { calls } = serve((url) => (url.endsWith("/fleets") ? json({ empires: [second, first] }) : undefined), [first, second]);
  live({ initialEmpire: first.id });
  await map();
  expect(screen.getByRole("combobox", { name: "Empire" })).toHaveValue(first.id);
  expect(calls().map(([u]) => u)).toContain(`/api/game/${universe}/fleets/${first.id}`);
  fireEvent.change(screen.getByRole("combobox", { name: "Empire" }), { target: { value: second.id } });
  await waitFor(() => expect(calls().map(([u]) => u)).toContain(`/api/game/${universe}/galaxy/${second.id}`));
  await waitFor(() => expect(calls().map(([u]) => u).filter((u) => u.endsWith(`/fleets/${second.id}`)).length).toBeGreaterThan(0));
  expect(await screen.findByRole("group", { name: /Carte de commandement/ })).toBeVisible();
});

test("server summary, confirmation with CSRF and idempotency key, then both projections are re-read", async () => {
  let galaxyReads = 0;
  const { calls } = serve((url, init) => {
    if (url.endsWith(`/galaxy/${first.id}`)) { galaxyReads += 1; return json(galaxyOf()); }
    if (url.endsWith("/missions/preview")) return json(quote(true));
    if (url.endsWith("/missions") && init?.method === "POST")
      return json({ result: { mission_id: "61000000-0000-4000-8000-000000000001", fleet_id: ids.escadre }, fleets: launched() });
    return undefined;
  });
  const { economy } = live();
  const p = await planMoveToLyra();
  expect(await p.findByRole("list", { name: "Étapes du trajet" })).toHaveTextContent("Vesta");
  const preview = calls().find(([u]) => u.endsWith("/missions/preview"))!;
  expect(JSON.parse(String(preview[1]!.body))).toMatchObject({ fleet_id: ids.escadre, kind: "DEPLOY", destination_id: ids.lyra,
    units: { frigate: 2, interceptor: 2 } });
  const before = galaxyReads;
  fireEvent.click(p.getByRole("button", { name: /Confirmer : déplacer une flotte/ }));
  expect(await screen.findByText(/Escadre Héliade part vers Lyra \(2 sauts\)/)).toBeVisible();
  const launch = posts(calls()).find(([u]) => u.endsWith("/missions"))!;
  const body = JSON.parse(String(launch[1]!.body));
  expect(body).toMatchObject({ fleet_id: ids.escadre, kind: "DEPLOY", destination_id: ids.lyra, units: { frigate: 2, interceptor: 2 } });
  expect(body.idempotency_key).toMatch(/^[a-f0-9]{32}$/);
  expect((launch[1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBe(csrf);
  await waitFor(() => expect(galaxyReads).toBeGreaterThan(before));
  expect(economy).toHaveBeenCalled();
  // The mission shown comes from the server's projection, findable in "Vos flottes".
  expect(within(screen.getByRole("region", { name: "Vos flottes" })).getByText("Déplacement en route")).toBeVisible();
});

test("an unknown outcome is said plainly and the retry reuses the same idempotency key", async () => {
  let attempt = 0;
  const { calls } = serve((url, init) => {
    if (url.endsWith("/missions/preview")) return json(quote(false));
    if (url.endsWith("/missions") && init?.method === "POST") return ++attempt === 1 ? json({ error: { code: "unavailable" } }, 503)
      : json({ result: { mission_id: "61000000-0000-4000-8000-000000000001", fleet_id: ids.escadre }, fleets: launched() });
    return undefined;
  });
  live();
  const p = await planMoveToLyra();
  // Current contract: no path, the hop count only and an explicitly indicative line.
  expect(await p.findByText(/Trajet de 2 sauts calculé par le serveur/)).toBeVisible();
  const confirm = () => p.getByRole("button", { name: /Confirmer : déplacer une flotte/ });
  await waitFor(() => expect(confirm()).toBeEnabled());
  fireEvent.click(confirm());
  expect(await screen.findByText(/Résultat non confirmé/)).toBeVisible();
  await waitFor(() => expect(confirm()).toBeEnabled());
  fireEvent.click(confirm());
  expect(await screen.findByText(/Escadre Héliade part vers Lyra/)).toBeVisible();
  const keys = posts(calls()).filter(([u]) => u.endsWith("/missions")).map(([, init]) => JSON.parse(String(init!.body)).idempotency_key);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test("a definitive refusal is explained, keeps the plan and re-reads the fleets", async () => {
  let fleetReads = 0;
  serve((url, init) => {
    if (url.endsWith(`/fleets/${first.id}`)) { fleetReads += 1; return json(fleetsOf()); }
    if (url.endsWith("/missions/preview")) return json(quote(false));
    if (url.endsWith("/missions") && init?.method === "POST") return json({ error: { code: "fleet_busy" } }, 409);
    return undefined;
  });
  live();
  const p = await planMoveToLyra();
  const confirm = () => p.getByRole("button", { name: /Confirmer : déplacer une flotte/ });
  await waitFor(() => expect(confirm()).toBeEnabled());
  const before = fleetReads;
  fireEvent.click(confirm());
  expect(await screen.findByRole("alert")).toBeVisible();
  await waitFor(() => expect(fleetReads).toBeGreaterThan(before));
  expect(screen.getByRole("region", { name: "Déplacer une flotte" })).toBeVisible();
});

test("a malformed server path is dropped: nothing is drawn as the real route", async () => {
  serve((url) => (url.endsWith("/missions/preview") ? json({ ...quote(true), path: [ids.home, ids.lyra] }) : undefined));
  live();
  const p = await planMoveToLyra();
  expect(await p.findByText(/Trajet de 2 sauts calculé par le serveur/)).toBeVisible();
  expect(p.queryByRole("list", { name: "Étapes du trajet" })).toBeNull();
});

test("fleets unavailable for the Empire: explained, with the classic map still one click away", async () => {
  serve((url) => (url.endsWith(`/fleets/${first.id}`) ? json({ error: { code: "permission_denied" } }, 403) : undefined));
  render(<GalaxyScreen universe={universe} enabled csrf={csrf} onSessionLost={() => undefined} onContextChange={() => undefined} />);
  const command = screen.getByRole("button", { name: "Nouvelle carte de commandement" });
  expect(screen.getByRole("button", { name: "Carte classique" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(command);
  expect(command).toHaveAttribute("aria-pressed", "true");
  expect(await screen.findByRole("heading", { name: "Flottes indisponibles" })).toBeVisible();
  expect(window.localStorage.getItem("echosphere.galaxy.mode")).toBe("command");
  fireEvent.click(screen.getByRole("button", { name: "Carte classique" }));
  await waitFor(() => expect(screen.queryByRole("heading", { name: "Flottes indisponibles" })).toBeNull());
  expect(window.localStorage.getItem("echosphere.galaxy.mode")).toBe("classic");
});

test("an expired session during the server summary hands back to the session flow", async () => {
  serve((url) => (url.endsWith("/missions/preview") ? json({ error: { code: "authentication_required" } }, 401) : undefined));
  const { lost } = live();
  await planMoveToLyra();
  expect(await screen.findByRole("alert")).toHaveTextContent(/session a expiré/);
  expect(lost).toHaveBeenCalled();
});
