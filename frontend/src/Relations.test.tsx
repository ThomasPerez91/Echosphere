import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { RelationsView } from "./components/RelationsView";
import { validRelations } from "./relations/api";
import { allied, empire, neutral, partner, received, relations, rival, stranger, universe } from "../tests/relationsFixture";

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

type Call = [string, RequestInit | undefined];
type Reply = ReturnType<typeof json>;
function setup(route: (url: string, init?: RequestInit) => Reply | Promise<Reply>) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => route(url, init));
  vi.stubGlobal("fetch", fetcher);
  const lost = vi.fn();
  render(<StrictMode><RelationsView universe={universe} enabled csrf={"a".repeat(64)} onSessionLost={lost} /></StrictMode>);
  return { fetcher, lost, calls: () => fetcher.mock.calls as unknown as Call[] };
}
const listing = json({ available: true, empires: [{ id: empire, name: "Empire test" }] });
const base = (projection = relations([neutral(), received, allied])) =>
  (url: string) => url.endsWith("/relations") ? listing : json(projection);

test("StrictMode mount reads only; contacts, states, dated facts and alerts from the server", async () => {
  const { calls } = setup(base());
  expect(await screen.findByRole("heading", { name: "Civilisations connues" })).toBeVisible();
  const rivalCard = screen.getByRole("heading", { name: "Hégémonie Rivale" }).closest("li")!;
  expect(within(rivalCard).getByText("Sans accord")).toBeVisible();
  expect(within(rivalCard).getByText(/Kepler b — Kepler/)).toBeVisible();
  const allyCard = screen.getByRole("heading", { name: "Concorde" }).closest("li")!;
  expect(within(allyCard).getByText("Pacte actif")).toBeVisible();
  expect(within(allyCard).getByText("Rencontré au combat", { exact: false })).toBeVisible();
  const partnerCard = screen.getByRole("heading", { name: "Ligue Aurorale" }).closest("li")!;
  expect(within(partnerCard).getByText("Présenté par une proposition de pacte", { exact: false })).toBeVisible();
  expect(within(partnerCard).queryByText("Présence observée")).toBeNull();
  // An incoming proposal is an alert of its own.
  const alerts = screen.getByRole("heading", { name: "Alertes diplomatiques" }).closest("section")!;
  expect(within(alerts).getByText("Ligue Aurorale")).toBeVisible();
  expect(calls().every(([, init]) => !init?.method)).toBe(true);
});

test("accepting is one CSRF intention; an unknown outcome retries with the same key", async () => {
  let attempt = 0;
  const after = relations([neutral(), { ...received, state: "PACT", proposal: null, pact: { accepted_at: "2099-01-01T00:00:00Z", notice: null }, actions: ["terminate"] }, allied]);
  const { calls } = setup((url, init) => {
    if (init?.method === "POST") return ++attempt === 1 ? json({ error: { code: "unavailable" } }, 503)
      : json({ result: { event_id: rival, kind: "accepted" }, relations: after });
    return base()(url);
  });
  const card = (await screen.findByRole("heading", { name: "Ligue Aurorale" })).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Accepter le pacte" }));
  await screen.findByText(/Réessayer n’enverra pas l’action deux fois/);
  fireEvent.click(within(screen.getByRole("heading", { name: "Ligue Aurorale" }).closest("li")!).getByRole("button", { name: "Accepter le pacte" }));
  await screen.findByText("Pacte de non-agression conclu.");
  const posts = calls().filter(([, init]) => init?.method === "POST");
  expect(posts).toHaveLength(2);
  expect(posts[0][0]).toBe(`/api/game/${universe}/relations/${empire}/${partner}/accept`);
  const keys = posts.map(([, init]) => JSON.parse(String(init!.body)).idempotency_key);
  expect(keys[0]).toBe(keys[1]);
  expect((posts[0][1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBe("a".repeat(64));
});

test("breaking a pact needs an explicit confirmation and can be cancelled", async () => {
  const { calls } = setup(base());
  const card = (await screen.findByRole("heading", { name: "Concorde" })).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Rompre le pacte…" }));
  fireEvent.click(within(card).getByRole("button", { name: "Annuler" }));
  expect(calls().some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.click(within(card).getByRole("button", { name: "Rompre le pacte…" }));
  expect(within(card).getByRole("button", { name: "Confirmer la rupture" })).toBeVisible();
});

test("a definitive refusal shows its reason and starts a new intention next time", async () => {
  const { calls } = setup((url, init) => init?.method === "POST"
    ? json({ error: { code: "proposal_cooldown" } }, 409) : base()(url));
  const card = (await screen.findByRole("heading", { name: "Hégémonie Rivale" })).closest("li")!;
  fireEvent.click(within(card).getByRole("button", { name: "Proposer un pacte" }));
  await screen.findByText(/refusée récemment/);
  fireEvent.click(within(screen.getByRole("heading", { name: "Hégémonie Rivale" }).closest("li")!).getByRole("button", { name: "Proposer un pacte" }));
  await screen.findAllByText(/refusée récemment/);
  const keys = calls().filter(([, init]) => init?.method === "POST").map(([, init]) => JSON.parse(String(init!.body)).idempotency_key);
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
});

test("a universe without relations says so instead of an error", async () => {
  setup((url) => url.endsWith("/relations") ? json({ available: false, empires: [] }) : json({}, 500));
  expect(await screen.findByRole("heading", { name: "Relations indisponibles dans cette partie" })).toBeVisible();
});

test("without the negotiate right no action is offered", async () => {
  setup(base(relations([neutral(), allied], false)));
  await screen.findByRole("heading", { name: "Civilisations connues" });
  expect(screen.queryByRole("button", { name: "Proposer un pacte" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Rompre le pacte…" })).toBeNull();
});

test("the client refuses projections that would leak beyond a dated presence", () => {
  expect(validRelations(relations())).toBe(true);
  const leaky = relations([neutral({ contact: { ...neutral().contact!, presence: { ...neutral().contact!.presence!, stocks: "1" } as never } })]);
  expect(validRelations(leaky)).toBe(false);
  // Actions offered without the negotiate right are a server contract violation.
  expect(validRelations({ ...relations(), can_negotiate: false })).toBe(false);
  // A pact state without its pact (or the reverse) is incoherent.
  expect(validRelations(relations([neutral({ state: "PACT" })]))).toBe(false);
  expect(validRelations(relations([{ ...allied, empire: { id: stranger, name: "Concorde" } }]))).toBe(true);
});

test("v0.12: relation score and observed forces come from the server, never computed here", async () => {
  const scored = { ...allied, standing: { score: 56, label: "allied" as const, factors: [{ kind: "pact", points: 40 }, { kind: "pact_age", points: 16 }] },
    assessment: { observed_at: "2099-01-01T00:00:00Z", ships: 3, attack: 360, hull: 900 } };
  const unseen = { ...neutral(), standing: { score: -50, label: "hostile" as const, factors: [{ kind: "hostile_received", points: -50 }] }, assessment: null };
  setup(base(relations([unseen, scored])));
  const card = (await screen.findByRole("heading", { name: "Concorde" })).closest("li")!;
  expect(within(card).getByLabelText("Relation Allié, 56 sur 100")).toBeVisible();
  const profile = screen.getByRole("heading", { name: "Profil et évaluation" }).closest("section")!;
  expect(within(profile).getByText("Pacte +40 · Ancienneté du pacte +16")).toBeVisible();
  expect(within(profile).getByText(/3 vaisseaux militaires, puissance 360, coque 900/)).toBeVisible();
  expect(within(profile).getByText("Forces inconnues : aucun combat observé.")).toBeVisible();
  expect(within(profile).getByText("Hostile")).toBeVisible();
});
