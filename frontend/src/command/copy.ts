/** Command map wording (player language, no game rule). Server codes reuse the Fleet messages. */
import { message } from "../fleet/messages";
import type { CommandQuote } from "./types";

export type QuoteState =
  | { status: "idle" }
  | { status: "loading"; key: string }
  | { status: "ready"; key: string; quote: CommandQuote }
  | { status: "error"; key: string; code: string };

export const refusal = (code: string) => message(code);

export const risks: Record<string, string> = {
  SURVEY: "La sonde révèle le système à l’arrivée, puis l’analyse dure le temps indiqué. Rappel possible pendant le trajet seulement.",
  DEPLOY: "Aucun remboursement après le départ. Rappel possible pendant le trajet seulement.",
  COLONIZE: "L’occupation du monde n’est vérifiée qu’à l’arrivée ; un monde pris fait échouer la mission sans révéler l’occupant. Le cargo à bord devient le stock initial.",
  ATTACK: "Défense et occupation adverses restent inconnues jusqu’à la bataille. Seules des unités militaires peuvent être perdues ; ni butin ni conquête. Rappel possible jusqu’à la bataille.",
};
