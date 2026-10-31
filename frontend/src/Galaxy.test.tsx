import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { GalaxyView } from "./components/GalaxyView";
import { validProjection } from "./galaxy/api";
import {
  active,
  colony,
  empire,
  near,
  origin,
  otherEmpire,
  projection,
  universe,
} from "../tests/galaxyFixture";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

type Reply = { ok: boolean; status: number; json: () => Promise<unknown> };
const json = (status: number, body: unknown): Reply => ({ ok: status < 400, status, json: async () => body });

function setup(post?: (call: number) => Reply | Promise<Reply>, lost = vi.fn()) {
  let state = projection();
  let calls = 0;
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      calls += 1;
      const reply = post ? await post(calls) : null;
      if (reply) return reply;
      state = projection([active()]);
      return json(200, { mission_id: active().id, galaxy: state });
    }
    return json(200, url.endsWith("/galaxy") ? { empires: [{ id: empire, name: "Empire test" }] } : state);
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <StrictMode>
      <GalaxyView universe={universe} enabled csrf={"a".repeat(64)} onSessionLost={lost} />
    </StrictMode>,
  );
  return fetcher;
}
const posts = (f: ReturnType<typeof setup>) => f.mock.calls.filter((c) => c[1]?.method === "POST");
const keyOf = (call: unknown[]) => JSON.parse((call[1] as RequestInit).body as string).idempotency_key;

async function prepare() {
  const node = await screen.findByRole("button", { name: "Signal détecté 1, Détecté, position approximative partagée" });
  node.focus();
  fireEvent.keyDown(node, { key: "Enter" });
  fireEvent.click(await screen.findByRole("button", { name: "Préparer l’expédition" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirmer l’expédition" }));
}

test("StrictMode mount sends no command and shows only server knowledge", async () => {
  const f = setup();
  expect(await screen.findByRole("heading", { name: "Système d’origine" })).toBeVisible();
  expect(posts(f)).toHaveLength(0);
  expect(screen.getAllByText("Signal détecté 1").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Signal détecté 2").length).toBeGreaterThan(0);
  expect(screen.getByText("Nouvelle Aube")).toBeVisible();
  // Text list equivalent to the map, operable without pointer.
  const list = screen.getByRole("heading", { name: "Systèmes connus" }).closest("section")!;
  expect(list.querySelectorAll("button")).toHaveLength(3);
  for (const call of f.mock.calls) expect((call[1] as RequestInit).credentials).toBe("same-origin");
});

test("keyboard selection, server quote and one explicit CSRF-protected command", async () => {
  const f = setup();
  await prepare();
  await screen.findByText(/Expédition acceptée par le serveur/);
  expect(posts(f)).toHaveLength(1);
  const [url, init] = posts(f)[0] as [string, RequestInit];
  expect(url).toBe(`/api/game/${universe}/exploration/${empire}/missions`);
  expect(init.headers).toMatchObject({ "X-CSRF-Token": "a".repeat(64) });
  expect(JSON.parse(init.body as string)).toMatchObject({ colony_id: colony, destination_id: near });
  expect(await screen.findByText("Capacité engagée")).toBeVisible();
  expect(screen.getByRole("progressbar", { name: "Avancement estimé de l’expédition" })).toBeVisible();
});

test("unknown outcome reuses the same intention key; a definitive refusal drops it", async () => {
  const f = setup((call) => {
    if (call === 1) throw new TypeError("lost reply");
    if (call === 2) return json(409, { error: { code: "insufficient_resources" } });
    return null as unknown as Reply;
  });
  await prepare();
  await screen.findByText(/Résultat non confirmé/);
  await prepare();
  await screen.findByText("La colonie source ne dispose pas des ressources nécessaires.");
  await prepare();
  await screen.findByText(/Expédition acceptée par le serveur/);
  const keys = posts(f).map(keyOf);
  expect(keys).toHaveLength(3);
  expect(keys[0]).toBe(keys[1]);
  expect(keys[2]).not.toBe(keys[1]);
});

test("expired session on command notifies the shell", async () => {
  const lost = vi.fn();
  setup(() => json(401, { error: { code: "authentication_required" } }), lost);
  await prepare();
  await waitFor(() => expect(lost).toHaveBeenCalled());
});

test("a late response for a previous Empire never replaces the selected one", async () => {
  let release: (value: Reply) => void = () => {};
  const second = projection([], otherEmpire);
  second.systems[0].name = "Origine B";
  const fetcher = vi.fn(async (url: string) => {
    if (url.endsWith("/galaxy"))
      return json(200, { empires: [{ id: empire, name: "Empire test" }, { id: otherEmpire, name: "Second Empire" }] });
    if (url.endsWith(otherEmpire)) return json(200, second);
    // The first read answers; the refresh for the first Empire stays in flight.
    if (fetcher.mock.calls.length >= 3) return new Promise<Reply>((resolve) => (release = resolve));
    return json(200, projection());
  });
  vi.stubGlobal("fetch", fetcher);
  render(<GalaxyView universe={universe} enabled csrf={"a".repeat(64)} onSessionLost={() => {}} />);
  expect(await screen.findByRole("heading", { name: "Système d’origine" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Actualiser" }));
  fireEvent.change(screen.getByLabelText("Empire"), { target: { value: otherEmpire } });
  expect(await screen.findByRole("heading", { name: "Origine B" })).toBeVisible();
  release(json(200, projection()));
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(screen.getByRole("heading", { name: "Origine B" })).toBeVisible();
  expect(screen.queryByText("Système d’origine")).toBeNull();
});

test("fog leaks and dangling references are refused before render", () => {
  const leak = projection();
  (leak.systems[1] as Record<string, unknown>).name = "Hidden";
  expect(validProjection(leak, empire)).toBe(false);
  const planets = projection();
  (planets.systems[2] as Record<string, unknown>).planets = [];
  expect(validProjection(planets, empire)).toBe(false);
  const dangling = projection();
  dangling.routes.push({ id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", a_id: origin, b_id: "99999999-9999-4999-8999-999999999999" });
  expect(validProjection(dangling, empire)).toBe(false);
  expect(validProjection(projection(), otherEmpire)).toBe(false);
  expect(validProjection(projection(), empire)).toBe(true);
});
