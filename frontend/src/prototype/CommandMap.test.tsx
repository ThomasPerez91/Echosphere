import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { MissionApi } from "./api";
import { fixtureApi, MissionRefused } from "./api";
import { CommandMap } from "./CommandMap";
import { fleetFixture, galaxyFixture, SERVER_TIME } from "./fixtures";
import type { World } from "./model";

afterEach(cleanup);

const now = Date.parse(SERVER_TIME);
function mount(routeMode: "contract" | "extension" = "extension", api?: MissionApi) {
  const world: World = { fleets: fleetFixture(), galaxy: galaxyFixture() };
  render(<CommandMap initial={world} api={api ?? fixtureApi(() => world, () => now, 0)} now={now} routeMode={routeMode} />);
}
const map = () => within(screen.getByRole("group", { name: /Carte de commandement/ }));

test("a new player sends a fleet from the map: system → action → fleet → server summary → confirm → tracking", async () => {
  mount();
  expect(screen.getByRole("heading", { name: "Que voulez-vous faire ?" })).toBeVisible();
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  expect(screen.getByRole("heading", { name: "Lyra", level: 2 })).toBeVisible();
  expect(screen.getByRole("button", { name: "Coloniser Lyra Bastion" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  const planner = screen.getByRole("region", { name: "Déplacer une flotte" });
  expect(within(planner).getAllByRole("radio")).toHaveLength(4);
  fireEvent.click(within(planner).getByRole("radio", { name: /Escadre Héliade/ }));
  // All suitable units leave by default; the summary comes from the server answer.
  expect(within(planner).getByRole("group", { name: "Frégate" })).toHaveTextContent("2 / 2");
  expect(await within(planner).findByText("2 sauts")).toBeVisible();
  expect(within(planner).getByRole("list", { name: "Étapes du trajet" })).toHaveTextContent("Vesta");
  expect(within(planner).getByText(/Aucun remboursement après le départ/)).toBeVisible();
  fireEvent.click(within(planner).getByRole("button", { name: /Confirmer : déplacer une flotte/ }));
  expect(await screen.findByRole("status")).toHaveTextContent("Escadre Héliade arrive à Lyra");
  const dock = screen.getByRole("region", { name: "Vos flottes" });
  expect(within(dock).getByText("En déplacement")).toBeVisible();
  expect(within(dock).getByText(/Entre Aube et Lyra/)).toBeVisible();
});

test("Fog of War: a detected signal shows no name nor structure and only offers a survey", () => {
  mount();
  fireEvent.click(map().getAllByRole("button", { name: /Signal détecté/ })[0]);
  expect(screen.getByRole("heading", { name: "Signal détecté", level: 2 })).toBeVisible();
  expect(screen.getByText(/Existence et position approximative seulement/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Cartographier" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: /Déplacer|Coloniser|Attaquer/ })).toBeNull();
});

test("current contract: without the proposed path field, only the hop count and an indicative line", async () => {
  mount("contract");
  fireEvent.click(map().getByRole("button", { name: "Cygne" }));
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  fireEvent.click(screen.getByRole("radio", { name: /Escadre Héliade/ }));
  expect(await screen.findByText("2 sauts")).toBeVisible();
  expect(screen.queryByRole("list", { name: "Étapes du trajet" })).toBeNull();
  expect(screen.getByText(/Itinéraire exact calculé par le serveur/)).toBeVisible();
});

test("adjusting units asks the server again; a refusal is explained, never guessed", async () => {
  let calls = 0;
  const world: World = { fleets: fleetFixture(), galaxy: galaxyFixture() };
  const base = fixtureApi(() => world, () => now, 0);
  const api: MissionApi = {
    preview: async (plan, signal) => {
      calls += 1;
      if (plan.units.frigate === 1) throw new MissionRefused("destination_unreachable");
      return base.preview(plan, signal);
    },
    launch: base.launch,
  };
  render(<CommandMap initial={world} api={api} now={now} routeMode="extension" />);
  fireEvent.click(map().getByRole("button", { name: "Orion" }));
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  fireEvent.click(screen.getByRole("radio", { name: /Escadre Héliade/ }));
  await screen.findByText("1 saut");
  fireEvent.click(screen.getByRole("button", { name: "Une Frégate de moins" }));
  expect(screen.getByRole("group", { name: "Frégate" })).toHaveTextContent("1 / 2");
  expect(await screen.findByRole("alert")).toHaveTextContent("Aucun trajet connu");
  expect(calls).toBe(2);
  expect(screen.queryByRole("button", { name: /Confirmer/ })).toBeNull();
});

test("a single eligible fleet is preselected; Escape cancels the plan and returns to the actions", async () => {
  mount();
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  fireEvent.click(screen.getByRole("button", { name: "Coloniser Lyra Bastion" }));
  expect(screen.getByRole("radio", { name: /Pionnier/ })).toBeChecked();
  expect(screen.getByText(/1 Colonisateur, consommé à la fondation/)).toBeVisible();
  await screen.findByText("2 sauts");
  fireEvent.keyDown(screen.getByRole("region", { name: "Coloniser Lyra Bastion" }), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("region", { name: "Coloniser Lyra Bastion" })).toBeNull());
  expect(screen.getByRole("heading", { name: "Actions possibles" })).toBeVisible();
});

test("every system is a keyboard button and the fleet list locates a fleet on the map", () => {
  mount();
  const vesta = map().getByRole("button", { name: /^Vesta/ });
  expect(vesta).toHaveAttribute("tabindex", "0");
  fireEvent.keyDown(vesta, { key: "Enter" });
  expect(vesta).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(within(screen.getByRole("region", { name: "Vos flottes" })).getByRole("button", { name: "Localiser Pionnier" }));
  expect(screen.getByRole("heading", { name: "Aube", level: 2 })).toBeVisible();
});

test("search finds a named known system, tabs show planets and known routes, filters only dim", () => {
  mount();
  fireEvent.change(screen.getByRole("searchbox", { name: "Rechercher un système connu" }), { target: { value: "lyr" } });
  fireEvent.submit(screen.getByRole("search"));
  expect(screen.getByRole("heading", { name: "Lyra", level: 2 })).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: /Planètes/ }));
  expect(screen.getByRole("list", { name: "Planètes connues" })).toHaveTextContent("Occupation inconnue");
  fireEvent.click(screen.getByRole("tab", { name: /Routes/ }));
  expect(screen.getByRole("list", { name: "Routes connues" })).toHaveTextContent("Lyra ↔ Vesta");
  // A signal has no name: searching for it finds nothing (Fog of War).
  fireEvent.change(screen.getByRole("searchbox", { name: "Rechercher un système connu" }), { target: { value: "signal" } });
  fireEvent.submit(screen.getByRole("search"));
  expect(screen.getByText("Aucun système connu de ce nom.")).toBeVisible();
  const signals = screen.getByRole("button", { name: "Signaux" });
  fireEvent.click(signals);
  expect(signals).toHaveAttribute("aria-pressed", "true");
  expect(map().getAllByRole("button")).toHaveLength(9); // dimmed, never removed
  fireEvent.click(screen.getByRole("switch", { name: "Noms" }));
  expect(screen.getByRole("switch", { name: "Noms" })).toHaveAttribute("aria-checked", "false");
});
