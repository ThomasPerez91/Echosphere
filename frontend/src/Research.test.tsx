import { StrictMode } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { ResearchView } from "./components/ResearchView";
import {
  colony,
  empire,
  order,
  projection,
  universe,
} from "../tests/researchFixture";
import { validProjection } from "./research/api";

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
function setup(queued = false, unknownFirst = false) {
  let state = projection(queued ? [order()] : []);
  let tries = 0;
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      tries += 1;
      if (unknownFirst && tries === 1) throw new TypeError("lost reply");
      state = projection(init.body === "{}" ? [] : [order()]);
      return { ok: true, status: 200, json: async () => ({ research: state }) };
    }
    return {
      ok: true,
      status: 200,
      json: async () =>
        url.endsWith("/research")
          ? { empires: [{ id: empire, name: "Empire test" }] }
          : state,
    };
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <StrictMode>
      <ResearchView
        universe={universe}
        enabled
        csrf={"a".repeat(64)}
        onSessionLost={() => {}}
      />
    </StrictMode>,
  );
  return fetcher;
}
const posts = (f: ReturnType<typeof setup>) =>
  f.mock.calls.filter((c) => c[1]?.method === "POST");
async function choose() {
  fireEvent.change(await screen.findByLabelText("Colonie payeuse"), {
    target: { value: colony },
  });
}
async function start() {
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Rechercher Fabrication modulaire I",
    }),
  );
  // Role queries over the full catalogue are slow on CI runners: wait longer, same assertion.
  fireEvent.click(await screen.findByRole("button", { name: "Confirmer" }, { timeout: 5000 }));
}

test("no runtime mutation on StrictMode mount, explicit source and prerequisites", async () => {
  const f = setup();
  const start = await screen.findByRole("button", {
    name: "Rechercher Fabrication modulaire I",
  });
  expect(start).toBeDisabled();
  expect(posts(f)).toHaveLength(0);
  await choose();
  expect(start).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Rechercher Fabrication modulaire II" }),
  ).toBeDisabled();
  expect(screen.getByText("Prérequis non acquis")).toBeVisible();
});
test("confirmation sends a single explicit, CSRF protected financing command", async () => {
  const f = setup();
  await choose();
  await start();
  await screen.findByText("Recherche acceptée par le serveur.");
  expect(posts(f)).toHaveLength(1);
  expect(JSON.parse(posts(f)[0][1]!.body as string)).toMatchObject({
    technology_id: "engineering_1",
    colony_id: colony,
  });
  expect(posts(f)[0][1]!.headers).toMatchObject({
    "X-CSRF-Token": "a".repeat(64),
  });
});
test("unknown response retries exact same intent key", async () => {
  const f = setup(false, true);
  await choose();
  await start();
  await screen.findByText(/Réponse incertaine/);
  await start();
  await screen.findByText("Recherche acceptée par le serveur.");
  const keys = posts(f).map(
    (c) => JSON.parse(c[1]!.body as string).idempotency_key,
  );
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});
test("refund confirmation exposes destination, theory, recoverable, lost and cascade", async () => {
  const f = setup(true);
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Annuler Fabrication modulaire I",
    }),
  );
  expect(
    screen.getByText("Colonie destinataire : Nouvelle Aube"),
  ).toBeVisible();
  expect(screen.getByText(/Remboursement théorique/)).toHaveTextContent(
    "80 Alliages",
  );
  expect(screen.getByText(/Montant récupérable/)).toHaveTextContent(
    "3 Alliages",
  );
  expect(screen.getByText(/Perte définitive/)).toHaveTextContent("77 Alliages");
  expect(screen.getByText(/Cascade : aucune/)).toBeVisible();
  expect(posts(f)).toHaveLength(0);
  // Role queries over the full catalogue are slow on CI runners: wait longer, same assertion.
  fireEvent.click(await screen.findByRole("button", { name: "Confirmer" }, { timeout: 5000 }));
  await waitFor(() => expect(posts(f)).toHaveLength(1));
});
test("malformed monetary projections refused before render", () => {
  const p = projection();
  p.sources[0].stocks.data = "1.2";
  expect(validProjection(p, empire)).toBe(false);
  expect(validProjection(projection(), "another-empire")).toBe(false);
});
