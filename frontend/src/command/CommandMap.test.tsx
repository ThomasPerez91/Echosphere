import { useMemo, useRef, useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { fixtureApi, MissionRefused } from "../prototype/api";
import { fleetFixture, galaxyFixture, SERVER_TIME } from "../prototype/fixtures";
import { CommandMap } from "./CommandMap";
import type { World } from "./model";
import type { MissionApi } from "./types";

afterEach(cleanup);

const now = Date.parse(SERVER_TIME);

/** The component is controlled: this harness plays the container (fixture world + re-read echo). */
function Harness({ withPath = true, wrap, at = now }: { withPath?: boolean; wrap?: (api: MissionApi) => MissionApi; at?: number }) {
  const [world, setWorld] = useState<World>(() => ({ fleets: fleetFixture(), galaxy: galaxyFixture() }));
  const current = useRef(world);
  current.current = world;
  const api = useMemo(() => {
    const base = fixtureApi(() => current.current, (w) => { current.current = w; setWorld(w); }, () => at, { latencyMs: 0, withPath: () => withPath });
    return wrap ? wrap(base) : base;
  }, [withPath, wrap, at]);
  return <div className="cmd-root"><CommandMap world={world} api={api} now={at} /></div>;
}
const map = () => within(screen.getByRole("group", { name: /Carte de commandement/ }));
const planner = (name: string | RegExp) => within(screen.getByRole("region", { name }));
const next = (name: string | RegExp) => fireEvent.click(planner(name).getByRole("button", { name: "Continuer" }));

test("system → known info → action → explicit fleet → units → server summary → confirm → back to the map with the fleet tracked", async () => {
  render(<Harness />);
  expect(screen.getByRole("heading", { name: "Que voulez-vous faire ?" })).toBeVisible();
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  expect(screen.getByRole("heading", { name: "Lyra", level: 2 })).toBeVisible();
  expect(screen.getByRole("button", { name: "Coloniser Lyra Bastion" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  const p = planner("Déplacer une flotte");
  // Several fleets: nothing is chosen for the player, Continue waits for a choice.
  expect(p.getAllByRole("radio")).toHaveLength(4);
  expect(p.getByRole("button", { name: "Continuer" })).toBeDisabled();
  expect(p.getByText("Garnison — détachement")).toBeVisible();
  fireEvent.click(p.getByRole("radio", { name: /Escadre Héliade/ }));
  next("Déplacer une flotte");
  // A task fleet moves as it is by default, shown and editable.
  expect(p.getByRole("group", { name: "Frégate" })).toHaveTextContent("2 / 2");
  expect(p.getByText("4 unité(s) engagée(s) sur 4.")).toBeVisible();
  next("Déplacer une flotte");
  await waitFor(() => expect(p.getByRole("button", { name: /Confirmer : déplacer une flotte/ })).toBeEnabled());
  expect(p.getByText("Sauts").nextElementSibling).toHaveTextContent("2");
  expect(p.getByRole("list", { name: "Étapes du trajet" })).toHaveTextContent("Vesta");
  expect(p.getByText(/Aucun remboursement après le départ/)).toBeVisible();
  fireEvent.click(p.getByRole("button", { name: /Confirmer : déplacer une flotte/ }));
  expect(await screen.findByRole("status")).toHaveTextContent("Escadre Héliade part vers Lyra (2 sauts)");
  // Back to the map; the fleet comes from the re-read projection, findable in "Vos flottes".
  expect(screen.queryByRole("region", { name: "Déplacer une flotte" })).toBeNull();
  const dock = within(screen.getByRole("region", { name: "Vos flottes" }));
  expect(dock.getByText("Déplacement en route")).toBeVisible();
  expect(dock.getByText(/Entre Aube et Lyra/)).toBeVisible();
  expect(dock.getByRole("progressbar", { name: "Avancement estimé de Escadre Héliade" })).toBeVisible();
});

test("Fog of War: a detected signal shows no name nor structure and only offers a survey with one probe", async () => {
  render(<Harness />);
  fireEvent.click(map().getAllByRole("button", { name: /Signal détecté/ })[0]);
  expect(screen.getByRole("heading", { name: "Signal détecté", level: 2 })).toBeVisible();
  expect(screen.getByText(/Existence et position approximative seulement/)).toBeVisible();
  expect(screen.queryByRole("button", { name: /Déplacer|Coloniser|Attaquer/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Cartographier" }));
  const p = planner("Cartographier");
  fireEvent.click(p.getByRole("radio", { name: /Sonde Kepler/ }));
  next("Cartographier");
  expect(p.getByRole("group", { name: "Sonde" })).toHaveTextContent("1 / 1");
});

test("a garrison never gives units by default: the player picks the detached units explicitly", () => {
  render(<Harness />);
  fireEvent.click(map().getAllByRole("button", { name: /Signal détecté/ })[0]);
  fireEvent.click(screen.getByRole("button", { name: "Cartographier" }));
  const p = planner("Cartographier");
  fireEvent.click(p.getByRole("radio", { name: /Garnison Aube Prime/ }));
  expect(p.getByText(/Une garnison défend sa colonie/)).toBeVisible();
  next("Cartographier");
  expect(p.getByRole("group", { name: "Sonde" })).toHaveTextContent("0 / 1");
  expect(p.getByRole("button", { name: "Continuer" })).toBeDisabled();
  fireEvent.click(p.getByRole("button", { name: "Une Sonde de plus" }));
  expect(p.getByRole("button", { name: "Continuer" })).toBeEnabled();
});

test("an attack starts with no unit engaged and only offers military classes", () => {
  render(<Harness />);
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  fireEvent.click(screen.getByRole("button", { name: "Attaquer Lyra Bastion" }));
  const p = planner("Attaquer Lyra Bastion");
  fireEvent.click(p.getByRole("radio", { name: /Escadre Héliade/ }));
  next("Attaquer Lyra Bastion");
  expect(p.getByRole("group", { name: "Frégate" })).toHaveTextContent("0 / 2");
  expect(p.queryByRole("group", { name: "Sonde" })).toBeNull();
  expect(p.getByRole("button", { name: "Continuer" })).toBeDisabled();
});

test("current contract: without `path`, only the server hop count and an explicitly indicative line", async () => {
  render(<Harness withPath={false} />);
  fireEvent.click(map().getByRole("button", { name: "Cygne" }));
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  fireEvent.click(screen.getByRole("radio", { name: /Escadre Héliade/ }));
  next("Déplacer une flotte");
  next("Déplacer une flotte");
  expect(await screen.findByText(/Trajet de 2 sauts calculé par le serveur/)).toBeVisible();
  expect(screen.queryByRole("list", { name: "Étapes du trajet" })).toBeNull();
  expect(screen.getByText(/à titre indicatif/)).toBeVisible();
});

test("changing units after the quote asks the server again; a refusal is explained and blocks the confirmation", async () => {
  let calls = 0;
  const wrap = (base: MissionApi): MissionApi => ({ ...base,
    preview: async (plan, signal) => {
      calls += 1;
      if (plan.units.frigate === 1) throw new MissionRefused("destination_unreachable");
      return base.preview(plan, signal);
    } });
  render(<Harness wrap={wrap} />);
  fireEvent.click(map().getByRole("button", { name: "Orion" }));
  fireEvent.click(screen.getByRole("button", { name: "Déplacer une flotte" }));
  fireEvent.click(screen.getByRole("radio", { name: /Escadre Héliade/ }));
  next("Déplacer une flotte");
  next("Déplacer une flotte");
  await screen.findByRole("heading", { name: "Vérifier et confirmer" });
  await waitFor(() => expect(screen.getByRole("button", { name: /Confirmer : déplacer/ })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Retour" }));
  fireEvent.click(screen.getByRole("button", { name: "Une Frégate de moins" }));
  next("Déplacer une flotte");
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(calls).toBe(2);
  expect(screen.getByRole("button", { name: /Confirmer : déplacer/ })).toBeDisabled();
});

test("a server refusal at launch keeps the plan and never shows a mission", async () => {
  const wrap = (base: MissionApi): MissionApi => ({ ...base, launch: async () => null });
  render(<Harness wrap={wrap} />);
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  fireEvent.click(screen.getByRole("button", { name: "Coloniser Lyra Bastion" }));
  const p = planner("Coloniser Lyra Bastion");
  // A single task fleet is preselected and the planner opens on its units.
  expect(p.getByText(/1 Colonisateur, consommé à la fondation/)).toBeVisible();
  next("Coloniser Lyra Bastion");
  await waitFor(() => expect(p.getByRole("button", { name: /Confirmer : coloniser/ })).toBeEnabled());
  fireEvent.click(p.getByRole("button", { name: /Confirmer : coloniser/ }));
  await waitFor(() => expect(p.getByRole("button", { name: /Confirmer : coloniser/ })).toBeEnabled());
  expect(screen.getByRole("region", { name: "Coloniser Lyra Bastion" })).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Vos flottes" })).queryByText(/Colonisation en route/)).toBeNull();
});

test("Escape cancels the plan and returns to the actions", async () => {
  render(<Harness />);
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  fireEvent.click(screen.getByRole("button", { name: "Coloniser Lyra Bastion" }));
  fireEvent.keyDown(screen.getByRole("region", { name: "Coloniser Lyra Bastion" }), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("region", { name: "Coloniser Lyra Bastion" })).toBeNull());
  expect(screen.getByRole("heading", { name: "Actions possibles" })).toBeVisible();
});

test("keyboard systems; Localiser selects a stationed fleet's system and centres a moving one on its estimate", () => {
  render(<Harness />);
  const vesta = map().getByRole("button", { name: /^Vesta/ });
  expect(vesta).toHaveAttribute("tabindex", "0");
  fireEvent.keyDown(vesta, { key: "Enter" });
  expect(vesta).toHaveAttribute("aria-pressed", "true");
  const dock = within(screen.getByRole("region", { name: "Vos flottes" }));
  fireEvent.click(dock.getByRole("button", { name: "Localiser Pionnier" }));
  expect(screen.getByRole("heading", { name: "Aube", level: 2 })).toBeVisible();
  fireEvent.click(dock.getByRole("button", { name: "Localiser Éclaireur Draco" }));
  expect(screen.getByRole("status")).toHaveTextContent(/position estimée de Éclaireur Draco/);
});

test("recall asks for confirmation, then the fleet turns back", async () => {
  render(<Harness at={Date.parse("2099-01-01T12:10:00Z")} />);
  const dock = within(screen.getByRole("region", { name: "Vos flottes" }));
  fireEvent.click(dock.getByRole("button", { name: "Rappeler… Éclaireur Draco" }));
  expect(dock.getByText(/aucun remboursement du carburant/)).toBeVisible();
  fireEvent.click(dock.getByRole("button", { name: "Confirmer le rappel" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Rappel confirmé : Éclaireur Draco fait demi-tour.");
  expect(dock.getByText("Retour après rappel")).toBeVisible();
});

test("search finds a named known system, tabs show planets and routes, filters only dim", () => {
  render(<Harness />);
  fireEvent.change(screen.getByRole("searchbox", { name: "Rechercher un système connu" }), { target: { value: "lyr" } });
  fireEvent.submit(screen.getByRole("search"));
  expect(screen.getByRole("heading", { name: "Lyra", level: 2 })).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: /Planètes/ }));
  expect(screen.getByRole("list", { name: "Planètes connues" })).toHaveTextContent("Occupation inconnue");
  fireEvent.click(screen.getByRole("tab", { name: /Routes/ }));
  expect(screen.getByRole("list", { name: "Routes connues" })).toHaveTextContent("Lyra ↔ Vesta");
  fireEvent.change(screen.getByRole("searchbox", { name: "Rechercher un système connu" }), { target: { value: "signal" } });
  fireEvent.submit(screen.getByRole("search"));
  expect(screen.getByText("Aucun système connu de ce nom.")).toBeVisible();
  const signals = screen.getByRole("button", { name: "Signaux" });
  fireEvent.click(signals);
  expect(signals).toHaveAttribute("aria-pressed", "true");
  expect(map().getAllByRole("button")).toHaveLength(9);
});

test("09/11: the fleet symbol above a system opens its fleets; Déplacer picks a destination on the map, Escape restores the window", async () => {
  render(<Harness />);
  fireEvent.click(map().getByRole("button", { name: /^Flottes à Aube : 3$/ }));
  const win = () => within(screen.getByRole("dialog", { name: "Flottes à Aube" }));
  expect(win().getByText(/2 Frégate, 2 Intercepteur/)).toBeVisible();
  expect(win().getByText(/défense de la colonie/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Que voulez-vous faire ?" })).toBeVisible(); // the system is not selected
  fireEvent.click(win().getByRole("button", { name: "Déplacer… Escadre Héliade" }));
  expect(screen.getByText("Choisissez une destination sur la carte")).toBeVisible();
  expect(screen.queryByRole("dialog", { name: "Flottes à Aube" })).toBeNull();
  // Escape cancels the picking and puts the window back.
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.getByRole("dialog", { name: "Flottes à Aube" })).toBeVisible();
  expect(screen.queryByText("Choisissez une destination sur la carte")).toBeNull();
  // A right click on the map cancels as well.
  fireEvent.click(win().getByRole("button", { name: "Déplacer… Escadre Héliade" }));
  fireEvent.contextMenu(screen.getByRole("group", { name: /Carte de commandement/ }));
  expect(screen.getByRole("dialog", { name: "Flottes à Aube" })).toBeVisible();
  // Picking the fleet's own system keeps the picking; another known system opens the server summary.
  fireEvent.click(win().getByRole("button", { name: "Déplacer… Escadre Héliade" }));
  fireEvent.click(map().getByRole("button", { name: /^Aube/ }));
  expect(screen.getByText(/Escadre Héliade est déjà à Aube/)).toBeVisible();
  fireEvent.click(map().getByRole("button", { name: "Lyra" }));
  const p = planner("Déplacer une flotte");
  expect(p.getAllByText("Escadre Héliade")[0]).toBeVisible();
  await waitFor(() => expect(p.getByRole("button", { name: /Confirmer : déplacer une flotte/ })).toBeEnabled());
  expect(screen.queryByText("Choisissez une destination sur la carte")).toBeNull();
});

test("09/11: a stationed task fleet changes its first-contact mission from the fleet window", async () => {
  const calls: [string, string | null][] = [];
  function Frontier() {
    const [world] = useState<World>(() => ({ fleets: { ...fleetFixture(), frontier: { protocols: ["SURVEILLANCE", "AMBUSH"], detections: [], encounters: [] } }, galaxy: galaxyFixture() }));
    const api = useMemo(() => ({ ...fixtureApi(() => world, () => undefined, () => now, { latencyMs: 0 }),
      protocol: async (id: string, value: string | null) => { calls.push([id, value]); return true; } }), [world]);
    return <div className="cmd-root"><CommandMap world={world} api={api as MissionApi} now={now} /></div>;
  }
  render(<Frontier />);
  fireEvent.click(map().getByRole("button", { name: /^Flottes à Aube/ }));
  const win = within(screen.getByRole("dialog", { name: "Flottes à Aube" }));
  // Garrisons have no protocol; the two task fleets do.
  expect(win.getAllByRole("combobox", { name: "Changer de mission" })).toHaveLength(2);
  fireEvent.change(win.getAllByRole("combobox", { name: "Changer de mission" })[0], { target: { value: "AMBUSH" } });
  fireEvent.click(win.getAllByRole("button", { name: "Appliquer" })[0]);
  expect(await win.findByText("Mission changée.")).toBeVisible();
  expect(calls).toHaveLength(1);
  expect(calls[0][1]).toBe("AMBUSH");
});
