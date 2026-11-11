import type { Protocol } from "./api";

/** 13B first-contact protocols of a stationed task Fleet: shared labels and player help. */
export const protocols: Record<Protocol, { label: string; help: string; tone: "neutral" | "accent" | "warning" | "danger" }> = {
  SURVEILLANCE: { label: "Surveillance", tone: "accent",
    help: "Détecte les flottes étrangères qui entrent dans le système et vous alerte. N’attaque jamais ; se défend si elle est attaquée." },
  AMBUSH: { label: "Embuscade", tone: "warning",
    help: "Détecte, puis attaque seulement un Empire connu qui a commis un acte hostile contre vous depuis moins de 72 h. Jamais un inconnu, jamais sous pacte." },
  INTERCEPTION: { label: "Interception", tone: "danger",
    help: "Attaque toute flotte étrangère militaire détectée à son entrée, même inconnue ou plus forte. Posture très agressive ; un pacte actif l’empêche." },
  FRIENDLY_CONTACT: { label: "Contact amical", tone: "neutral",
    help: "Se présente volontairement aux flottes détectées (identité, système, date). N’attaque jamais ; se replie si une force hostile entre dans le système." },
};
