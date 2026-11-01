import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { FleetView } from "./components/FleetView";
import { ApiError, previewMission, validFleets } from "./fleet/api";
import { colony, done, empire, fleets, garrison, mission, near, order, surveying, universe } from "../tests/fleetFixture";

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
beforeAll(() => {
  // jsdom has no <dialog> modal support.
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.open = true; };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) { this.open = false; };
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

type Call = [string, RequestInit | undefined];
function setup(route: (url: string, init?: RequestInit) => ReturnType<typeof json>) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => route(url, init));
  vi.stubGlobal("fetch", fetcher);
  const lost = vi.fn();
  render(<StrictMode><FleetView universe={universe} enabled csrf={"a".repeat(64)} onSessionLost={lost} /></StrictMode>);
  return { fetcher, lost, calls: () => fetcher.mock.calls as unknown as Call[] };
}
const base = (url: string) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(fleets());

test("StrictMode mount reads only; server state for production, garrison, missions and reports", async () => {
  const { calls } = setup(base);
  expect(await screen.findByRole("heading", { name: "Production — Nouvelle Aube" })).toBeVisible();
  expect(screen.getByText("Garnison Nouvelle Aube")).toBeVisible();
  expect(screen.getByText(/Signal détecté — structure inconnue/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Rapports récents" })).toBeVisible();
  expect(screen.getByText("En fabrication")).toBeVisible();
  expect(calls().every(([, init]) => !init?.method)).toBe(true);
});

test("production order is one CSRF intention; an unknown outcome retries with the same key", async () => {
  let attempt = 0;
  const { calls } = setup((url, init) => {
    if (init?.method === "POST") return ++attempt === 1 ? json({ error: { code: "unavailable" } }, 503)
      : json({ result: { order_id: order, status: "queued" }, fleets: fleets() });
    return base(url);
  });
  const button = await screen.findByRole("button", { name: "Commander" });
  fireEvent.click(button);
  await screen.findByText(/Réessayer n’enverra pas l’action deux fois/);
  fireEvent.click(screen.getByRole("button", { name: "Commander" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const posts = calls().filter(([, init]) => init?.method === "POST");
  const keys = posts.map(([, init]) => JSON.parse(String(init!.body)).idempotency_key);
  expect(posts).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect((posts[0][1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBe("a".repeat(64));
  expect(JSON.parse(String(posts[0][1]!.body))).toMatchObject({ colony_id: colony, ship_class: "probe", quantity: 1 });
});

test("SURVEY is quoted by the server before confirmation and sends the chosen units only", async () => {
  const { calls } = setup((url, init) => {
    if (url.endsWith("/missions/preview")) return json({
      kind: "SURVEY", destination_id: near, hops: 1, cost: { alloys: "0", flux: "4000000", data: "20000000" },
      travel_us: "600000000", survey_us: "900000000", travel_arrival_at: "2099-01-01T00:10:00Z",
      due_at: "2099-01-01T00:25:00Z", payer_colony_id: colony, affordable: true,
    });
    if (init?.method === "POST") return json({ result: { mission_id: mission, fleet_id: garrison }, fleets: fleets() });
    return base(url);
  });
  const garrisonCard = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(garrisonCard).getByRole("button", { name: "Envoyer…" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.click(within(dialog).getByRole("radio", { name: "Cartographie" }));
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Destination" }), { target: { value: near } });
  fireEvent.change(within(dialog).getByRole("spinbutton", { name: /Sonde/ }), { target: { value: "1" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Calculer le devis" }));
  expect(await within(dialog).findByText(/1 saut\(s\)/)).toBeVisible();
  expect(within(dialog).getByText(/analyse 15 min/)).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirmer" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const launch = calls().find(([url, init]) => url.endsWith("/missions") && init?.method === "POST")!;
  expect(JSON.parse(String(launch[1]!.body))).toMatchObject({ fleet_id: garrison, kind: "SURVEY", destination_id: near, units: { probe: 1 } });
});

test("recall is offered only while travelling; an analysis under way has no recall", async () => {
  setup(base);
  const card = (await screen.findByText("Flotte 2", { selector: "h3" })).closest("li")!;
  expect(within(card).getByRole("button", { name: "Rappeler…" })).toBeVisible();
  cleanup();
  const analysing = surveying("2098-12-31T23:55:00Z");
  analysing.travel_arrival_at = "2098-12-31T23:59:00Z";
  setup((url) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(fleets([analysing])));
  const later = (await screen.findByText("Flotte 2", { selector: "h3" })).closest("li")!;
  expect(within(later).getByText("Analyse en cours")).toBeVisible();
  expect(within(later).queryByRole("button", { name: "Rappeler…" })).not.toBeInTheDocument();
});

test("unload preview shows credited and kept-aboard amounts before confirmation", async () => {
  setup(base);
  const card = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Décharger…" }));
  expect(within(screen.getByRole("dialog")).getByText(/100 crédités, 200 conservés à bord/)).toBeVisible();
});

test("a ruleset without Fleets is explained, never filled with fake ships", async () => {
  setup((url) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] })
    : json({ server_time: "2099-01-01T00:00:00Z", empire: { id: empire, name: "Empire test" }, permissions: ["fleet.read"], available: false }));
  expect(await screen.findByRole("heading", { name: "Flottes indisponibles dans cette partie" })).toBeVisible();
  expect(screen.queryByText(/Garnison/)).not.toBeInTheDocument();
});

test("validator refuses Colony data without colony.read and named DETECTED signals", async () => {
  expect(validFleets(fleets(), empire)).toBe(true);
  expect(validFleets(fleets(undefined, ["fleet.read"]), empire)).toBe(false);
  const leak = fleets();
  (leak.systems![1] as Record<string, unknown>).name = "Hidden";
  expect(validFleets(leak, empire)).toBe(false);
  expect(validFleets(fleets(), "1b0f8f8e-6a3c-4f7e-9d1a-0c5e2f6a7b80")).toBe(false);
  setup((url) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(leak));
  await waitFor(() => expect(screen.getByRole("alert")).toBeVisible());
  expect(screen.queryByText("Hidden")).not.toBeInTheDocument();
});

test("cancelling production sends the backend intention contract and is confirmed by the server", async () => {
  const { calls } = setup((url, init) => {
    if (init?.method === "POST") return json({ result: { order_id: order, refunded: { alloys: "100000000", flux: "64000000", data: "64000000" } },
      fleets: { ...fleets(), colonies: [{ ...fleets().colonies![0], orders: [] }] } });
    return base(url);
  });
  fireEvent.click(await screen.findByRole("button", { name: "Annuler…" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText(/28 perdus définitivement/)).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirmer" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const [url, init] = calls().find(([, i]) => i?.method === "POST")!;
  expect(url).toMatch(new RegExp(`/fleets/${empire}/orders/${order}/cancel$`));
  // Exactly the Keyed body the Game API accepts (extra fields are refused there).
  const body = JSON.parse(String(init!.body));
  expect(Object.keys(body)).toEqual(["idempotency_key"]);
  expect(body.idempotency_key).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
  expect(screen.queryByRole("button", { name: "Annuler…" })).not.toBeInTheDocument();
});

test("mission quote refuses a paying colony without colony.read", async () => {
  const quote = (payer: string | null) => ({
    kind: "DEPLOY", destination_id: near, hops: 1, cost: { alloys: "0", flux: "4000000", data: "0" },
    travel_us: "600000000", survey_us: "0", travel_arrival_at: "2099-01-01T00:10:00Z",
    due_at: "2099-01-01T00:10:00Z", payer_colony_id: payer, affordable: true,
  });
  const ask = (payer: string | null, colonyRead: boolean) => {
    vi.stubGlobal("fetch", vi.fn(async () => json(quote(payer))));
    return previewMission(universe, empire, "a".repeat(64), { fleet_id: garrison, kind: "DEPLOY", destination_id: near, units: { probe: 1 } },
      colonyRead, new AbortController().signal);
  };
  expect((await ask(colony, true)).payer_colony_id).toBe(colony);
  expect((await ask(null, false)).payer_colony_id).toBeNull();
  await expect(ask(colony, false)).rejects.toBeInstanceOf(ApiError);
});

test("an old open mission listed after 30 completed ones stays in flight with its recall", async () => {
  const history = Array.from({ length: 30 }, (_, i) => ({
    ...fleets().missions!.find((m) => m.id === done)!, id: `aaaaaaaa-0000-4000-8000-${String(100 + i).padStart(12, "0")}`,
  }));
  const old = surveying("2098-12-01T00:00:00Z");
  setup((url) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(fleets([...history, old])));
  const moving = (await screen.findByRole("heading", { name: "Flottes en mission" })).closest("section")!;
  const card = within(moving).getByText("Flotte 2", { selector: "h3" }).closest("li")!;
  expect(within(card).getByRole("button", { name: "Rappeler…" })).toBeVisible();
  expect(mission).toBe(old.id);
});
