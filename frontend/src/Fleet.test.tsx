import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { FleetView } from "./components/FleetView";
import { ApiError, previewMission, validFleets } from "./fleet/api";
import { colony, colonizing, done, empire, fleets, freeWorld, garrison, mission, near, order, origin, otherEmpire, otherFleets, secondColony, surveying, universe } from "../tests/fleetFixture";

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
beforeAll(() => {
  // jsdom has no <dialog> modal support.
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.open = true; };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) { this.open = false; };
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

type Call = [string, RequestInit | undefined];
type Reply = ReturnType<typeof json>;
function setup(route: (url: string, init?: RequestInit) => Reply | Promise<Reply>, target?: { empire: string; system: string; planet?: string }) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => route(url, init));
  vi.stubGlobal("fetch", fetcher);
  const lost = vi.fn();
  render(<StrictMode><FleetView universe={universe} enabled csrf={"a".repeat(64)} onSessionLost={lost} target={target} /></StrictMode>);
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

// --- Shortcut toward another Empire than the first readable one -------------------------------

const twoEmpires = (url: string) => {
  if (url.endsWith("/fleets")) return json({ empires: [{ id: empire, name: "Empire A" }, { id: otherEmpire, name: "Empire B" }] });
  return json(url.endsWith(otherEmpire) ? otherFleets() : fleets());
};

test("shortcut to the second Empire reads it and prefills once, never with the first Empire's data", async () => {
  const { calls } = setup(twoEmpires, { empire: otherEmpire, system: near });
  const dialog = await screen.findByRole("dialog", { name: "Envoyer une flotte" });
  expect(within(dialog).getByText(/Garnison Bastion B/)).toBeVisible();
  expect(within(dialog).getByRole("combobox", { name: "Destination" })).toHaveValue(near);
  expect(within(dialog).getByRole("radio", { name: "Cartographie" })).toBeChecked();
  expect(screen.getByRole("combobox", { name: "Empire" })).toHaveValue(otherEmpire);
  const reads = () => calls().filter(([url, init]) => !init?.method && /\/fleets\/[0-9a-f-]{36}$/.test(url)).map(([url]) => url);
  expect(reads().every((url) => url.endsWith(otherEmpire))).toBe(true); // A is never read nor shown
  const settled = calls().length;
  await new Promise((r) => setTimeout(r, 50));
  expect(calls().length).toBe(settled); // no selection loop
  fireEvent.click(within(dialog).getByRole("button", { name: "Fermer" }));
  await waitFor(() => expect(screen.queryByText("Calculer le devis")).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "Actualiser" }));
  await waitFor(() => expect(reads().length).toBeGreaterThan(1));
  await new Promise((r) => setTimeout(r, 20));
  expect(screen.queryByText("Calculer le devis")).not.toBeInTheDocument(); // consumed once only
});

test("shortcut to an inaccessible Empire shows the readable one without any prefilled dialog", async () => {
  setup((url) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire A" }] }) : json(fleets()),
    { empire: otherEmpire, system: near });
  expect(await screen.findByText("Garnison Nouvelle Aube")).toBeVisible();
  expect(screen.queryByText("Calculer le devis")).not.toBeInTheDocument();
});

// --- Superseded mission quotes -----------------------------------------------------------------

const alpha = "bbbbbbbb-0000-4000-8000-000000000001";
const beta = "bbbbbbbb-0000-4000-8000-000000000002";
function deferred() {
  let resolve!: (reply: Reply) => void;
  const promise = new Promise<Reply>((r) => { resolve = r; });
  return { promise, resolve };
}
const quoted = (kind: string, destination: string, hops: number) => json({
  kind, destination_id: destination, hops, cost: { alloys: "0", flux: "4000000", data: kind === "SURVEY" ? "20000000" : "0" },
  travel_us: "600000000", survey_us: kind === "SURVEY" ? "900000000" : "0", travel_arrival_at: "2099-01-01T00:10:00Z",
  due_at: "2099-01-01T00:10:00Z", payer_colony_id: colony, affordable: true,
});
/** Fleet screen whose previews wait until the test answers them, in any order. */
function slowQuotes() {
  const pending: { body: Record<string, unknown>; reply: ReturnType<typeof deferred> }[] = [];
  const world = fleets([]);
  world.systems = [...world.systems!, { id: alpha, state: "MAPPED", name: "Alpha" }, { id: beta, state: "MAPPED", name: "Bêta" }];
  const { calls } = setup((url, init) => {
    if (url.endsWith("/missions/preview")) {
      const reply = deferred();
      pending.push({ body: JSON.parse(String(init!.body)), reply });
      return reply.promise;
    }
    if (init?.method === "POST") return json({ result: { mission_id: mission, fleet_id: garrison }, fleets: world });
    return url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(world);
  });
  return { pending, calls };
}
async function openSend() {
  const card = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Envoyer…" }));
  return screen.getByRole("dialog");
}
const pick = (dialog: HTMLElement, value: string) =>
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Destination" }), { target: { value } });
const probes = (dialog: HTMLElement, n: number) =>
  fireEvent.change(within(dialog).getByRole("spinbutton", { name: /Sonde/ }), { target: { value: String(n) } });
const ask = (dialog: HTMLElement) => fireEvent.click(within(dialog).getByRole("button", { name: "Calculer le devis" }));
const answer = async (entry: { reply: ReturnType<typeof deferred> }, reply: Reply) => {
  entry.reply.resolve(reply);
  await new Promise((r) => setTimeout(r, 0));
};

test("A — a late quote for a previous destination is ignored; Confirm sends the latest one", async () => {
  const { pending, calls } = slowQuotes();
  const dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1); ask(dialog);
  pick(dialog, beta); ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(2));
  expect(pending.map((q) => q.body.destination_id)).toEqual([alpha, beta]);
  await answer(pending[1], quoted("DEPLOY", beta, 2));
  expect(await within(dialog).findByText(/2 saut\(s\)/)).toBeVisible();
  await answer(pending[0], quoted("DEPLOY", alpha, 1));
  expect(within(dialog).getByRole("combobox", { name: "Destination" })).toHaveValue(beta);
  expect(within(dialog).queryByText(/1 saut\(s\)/)).not.toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirmer" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const launch = calls().find(([url, init]) => url.endsWith("/missions") && init?.method === "POST")!;
  expect(JSON.parse(String(launch[1]!.body))).toMatchObject({ kind: "DEPLOY", destination_id: beta, units: { probe: 1 } });
});

test("B — a late DEPLOY quote never overwrites a SURVEY chosen meanwhile", async () => {
  const { pending } = slowQuotes();
  const dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1); ask(dialog);
  fireEvent.click(within(dialog).getByRole("radio", { name: "Cartographie" }));
  pick(dialog, near); ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(2));
  await answer(pending[1], quoted("SURVEY", near, 3));
  await answer(pending[0], quoted("DEPLOY", alpha, 1));
  expect(within(dialog).getByRole("radio", { name: "Cartographie" })).toBeChecked();
  expect(within(dialog).getByRole("combobox", { name: "Destination" })).toHaveValue(near);
  expect(within(dialog).getByText(/3 saut\(s\)/)).toBeVisible();
  expect(within(dialog).getByText(/analyse 15 min/)).toBeVisible();
});

test("C — composition edits invalidate the quote; a late one for the old composition is ignored", async () => {
  const { pending, calls } = slowQuotes();
  const dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1); ask(dialog);
  probes(dialog, 2); ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(2));
  expect(pending.map((q) => q.body.units)).toEqual([{ probe: 1 }, { probe: 2 }]);
  await answer(pending[1], quoted("DEPLOY", alpha, 2));
  await answer(pending[0], quoted("DEPLOY", alpha, 1));
  expect(within(dialog).getByRole("spinbutton", { name: /Sonde/ })).toHaveValue(2);
  expect(within(dialog).getByText(/2 saut\(s\)/)).toBeVisible();
  // Any further edit hides the quote: Confirm is gone until the server quotes again.
  probes(dialog, 1);
  expect(within(dialog).queryByText(/saut\(s\)/)).not.toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: "Confirmer" })).not.toBeInTheDocument();
  ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(3));
  expect(calls().some(([url, init]) => url.endsWith("/missions") && init?.method === "POST")).toBe(false);
});

test("D — a quote answered after closing never reopens the dialog", async () => {
  const { pending } = slowQuotes();
  const dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1); ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(1));
  fireEvent.click(within(dialog).getByRole("button", { name: "Fermer" }));
  await answer(pending[0], quoted("DEPLOY", alpha, 1));
  expect(screen.queryByText("Calculer le devis")).not.toBeInTheDocument();
  expect(screen.queryByText(/saut\(s\)/)).not.toBeInTheDocument();
});

test("E — an old quote never fills a dialog reopened afterwards, even with the same choices", async () => {
  const { pending } = slowQuotes();
  let dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1); ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(1));
  fireEvent.click(within(dialog).getByRole("button", { name: "Fermer" }));
  dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1);
  await answer(pending[0], quoted("DEPLOY", alpha, 1));
  expect(within(dialog).queryByText(/saut\(s\)/)).not.toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Calculer le devis" })).toBeVisible();
});

test("F — a superseded quote failing late shows no error and keeps the current quote", async () => {
  const { pending } = slowQuotes();
  const dialog = await openSend();
  pick(dialog, alpha); probes(dialog, 1); ask(dialog);
  pick(dialog, beta); ask(dialog);
  await waitFor(() => expect(pending).toHaveLength(2));
  await answer(pending[1], quoted("DEPLOY", beta, 2));
  await answer(pending[0], json({ error: { code: "destination_unreachable" } }, 409));
  expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
  expect(within(dialog).getByText(/2 saut\(s\)/)).toBeVisible();
});

test("travel arrival switches a SURVEY to analysis and removes recall without a server read", async () => {
  const arriving = surveying("2098-12-31T23:59:00Z");
  arriving.travel_arrival_at = "2099-01-01T00:00:00.400Z"; // 400 ms after the server time
  const { calls } = setup((url) => url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(fleets([arriving])));
  const card = (await screen.findByText("Flotte 2", { selector: "h3" })).closest("li")!;
  expect(within(card).getByRole("button", { name: "Rappeler…" })).toBeVisible();
  const reads = calls().length;
  expect(await within(card).findByText("Analyse en cours", {}, { timeout: 2000 })).toBeVisible();
  expect(within(card).queryByRole("button", { name: "Rappeler…" })).not.toBeInTheDocument();
  expect(calls().length).toBe(reads); // local deadline only: no polling
});

// --- Colonization (v0.5) ------------------------------------------------------------------------

const colonizeRoute = (permissions?: string[]) => (url: string, init?: RequestInit) => {
  if (url.endsWith("/missions/preview")) return json({
    kind: "COLONIZE", destination_id: origin, hops: 0, cost: { alloys: "0", flux: "0", data: "0" }, travel_us: "0", survey_us: "0",
    travel_arrival_at: "2099-01-01T00:00:00Z", due_at: "2099-01-01T00:00:00Z", payer_colony_id: colony, affordable: true,
    target_planet_id: freeWorld, package_minimum: { alloys: "500000000", flux: "250000000", data: "50000000" },
  });
  if (init?.method === "POST") return json({ result: { mission_id: mission, fleet_id: garrison }, fleets: colonizing(permissions) });
  return url.endsWith("/fleets") ? json({ empires: [{ id: empire, name: "Empire test" }] }) : json(colonizing(permissions));
};

test("COLONIZE targets a known world with exactly one colonizer and the package, never a destination", async () => {
  const { calls } = setup(colonizeRoute());
  const card = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Envoyer…" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.click(within(dialog).getByRole("radio", { name: "Colonisation" }));
  const worlds = within(dialog).getByRole("combobox", { name: "Monde visé" });
  // An own colony named under colony.read is not offered; nothing is ever called "Libre".
  expect(within(worlds).queryByText(/Nouvelle Aube/)).not.toBeInTheDocument();
  expect(within(dialog).getByText(/Occupation actuelle inconnue/)).toBeVisible();
  expect(screen.queryByText(/\bLibre\b/)).not.toBeInTheDocument();
  fireEvent.change(worlds, { target: { value: freeWorld } });
  for (const [label, value] of [["Alliages", "600"], ["Flux", "300"], ["Données", "100"]])
    fireEvent.change(within(dialog).getByRole("spinbutton", { name: new RegExp(label) }), { target: { value } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Calculer le devis" }));
  expect(await within(dialog).findByText(/0 saut\(s\)/)).toBeVisible();
  expect(within(dialog).getByText(/aucun carburant/)).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirmer" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const preview = JSON.parse(String(calls().find(([url]) => url.endsWith("/missions/preview"))![1]!.body));
  expect(preview).toEqual({ fleet_id: garrison, kind: "COLONIZE", units: { colonizer: 1 }, target_planet_id: freeWorld });
  const launch = JSON.parse(String(calls().find(([url, init]) => url.endsWith("/missions") && init?.method === "POST")![1]!.body));
  expect(launch).toMatchObject({ kind: "COLONIZE", target_planet_id: freeWorld, units: { colonizer: 1 }, cargo: { alloys: 600, flux: 300, data: 100 } });
  expect(launch).not.toHaveProperty("destination_id");
});

test("COLONIZE is not offered without colony.expand; a short package is flagged before the server refuses", async () => {
  setup(colonizeRoute(["colony.read", "galaxy.read", "fleet.read", "fleet.build", "fleet.command"]));
  const card = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Envoyer…" }));
  expect(within(screen.getByRole("dialog")).queryByRole("radio", { name: "Colonisation" })).not.toBeInTheDocument();
  cleanup();
  setup(colonizeRoute());
  const again = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(again).getByRole("button", { name: "Envoyer…" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("radio", { name: "Colonisation" }));
  expect(within(screen.getByRole("dialog")).getByText(/insuffisant, chargez d’abord le colonisateur/)).toBeVisible();
});

test("a colonizer order shows the current progressive server price and always holds one unit", async () => {
  const { calls } = setup(colonizeRoute());
  fireEvent.change(await screen.findByRole("combobox", { name: "Classe" }), { target: { value: "colonizer" } });
  expect(screen.getByText(/Prix serveur actuel : 2\s?400 Alliages · 1\s?200 Flux · 600 Données/)).toBeVisible();
  expect(screen.getByText(/rang 3.*×2/)).toBeVisible();
  fireEvent.change(screen.getByRole("spinbutton", { name: /Quantité/ }), { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Commander" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const body = JSON.parse(String(calls().find(([url, init]) => url.endsWith("/orders") && init?.method === "POST")![1]!.body));
  expect(body).toMatchObject({ ship_class: "colonizer", quantity: 1 });
});

test("with two own colonies in the system, load and unload require an explicit colony", async () => {
  const { calls } = setup(colonizeRoute());
  const card = (await screen.findByText("Garnison Nouvelle Aube")).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Décharger…" }));
  const dialog = screen.getByRole("dialog");
  const choice = within(dialog).getByRole("combobox", { name: "Colonie" });
  expect(choice).toHaveValue("");
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirmer" }));
  expect(calls().some(([url]) => url.endsWith("/unload"))).toBe(false); // nothing silently chosen
  fireEvent.change(choice, { target: { value: secondColony } });
  expect(within(dialog).getByText(/500 crédités, 100 conservés à bord/)).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirmer" }));
  await screen.findByText("Ordre accepté par le serveur.");
  const unload = calls().find(([url]) => url.endsWith("/unload"))!;
  expect(JSON.parse(String(unload[1]!.body))).toMatchObject({ colony_id: secondColony });
});

test("the System View shortcut opens the COLONIZE dialog on the chosen world", async () => {
  setup(colonizeRoute(), { empire, system: origin, planet: freeWorld });
  const dialog = await screen.findByRole("dialog", { name: "Envoyer une flotte" });
  expect(within(dialog).getByRole("radio", { name: "Colonisation" })).toBeChecked();
  expect(within(dialog).getByRole("combobox", { name: "Monde visé" })).toHaveValue(freeWorld);
});

test("validator refuses world structure on DETECTED signals and colony names without colony.read", () => {
  expect(validFleets(colonizing(), empire)).toBe(true);
  const restricted = colonizing(["galaxy.read", "fleet.read", "fleet.command", "colony.expand"]);
  expect(validFleets(restricted, empire)).toBe(true);
  const named = colonizing(["galaxy.read", "fleet.read", "fleet.command", "colony.expand"]);
  named.systems![0].planets![0].colony_id = colony;
  expect(validFleets(named, empire)).toBe(false);
  const leaked = colonizing();
  (leaked.systems![1] as Record<string, unknown>).planets = [];
  expect(validFleets(leaked, empire)).toBe(false);
  const report = colonizing(["galaxy.read", "fleet.read"]);
  report.missions = [{ ...surveying(), kind: "COLONIZE", status: "completed", completed_at: "2099-01-01T00:00:00Z", payer_colony_id: null,
    target_planet: { id: freeWorld, name: "Monde" }, report: { observed_at: "2099-01-01T00:00:00Z", processed_at: "2099-01-01T00:00:01Z",
      result: { kind: "COLONIZE", outcome: "founded", colony_id: secondColony } } }];
  expect(validFleets(report, empire)).toBe(false);
});
