/** UX03 prototype wording shared by components (player language, no game rule). */
import type { FixtureQuote } from "./fixtures";

export type QuoteState =
  | { status: "idle" } | { status: "loading" } | { status: "ready"; quote: FixtureQuote } | { status: "error"; code: string };

const refusals: Record<string, string> = {
  destination_unreachable: "Aucun trajet connu ne mène à ce système depuis cette flotte.",
  destination_unmapped: "Destination non cartographiée : envoyez d’abord une sonde.",
  insufficient_resources: "Ressources insuffisantes dans la colonie d’attache.",
  invalid_request: "Cette combinaison n’est pas valide. Changez de flotte ou d’unités.",
};
export const refusal = (code: string) => refusals[code] ?? "Le serveur n’a pas pu calculer cette mission. Réessayez.";
