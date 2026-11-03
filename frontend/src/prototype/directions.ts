/** The three UX02 art directions, applied on the same markup through data-direction tokens. */
export const directions = [
  { id: "orbital", label: "A — Console orbitale (recommandée)" },
  { id: "atlas", label: "B — Atlas stellaire" },
  { id: "tactical", label: "C — Pont tactique" },
] as const;
export type Direction = (typeof directions)[number]["id"];
