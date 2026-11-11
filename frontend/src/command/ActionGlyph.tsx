import type { MissionKind } from "../fleet/api";

/** Decorative pictogram of a map action (context menu of the reference carte-galaxie.html). */
const PATHS: Record<MissionKind, string> = {
  SURVEY: "M12 3a9 9 0 1 0 9 9h-2a7 7 0 1 1-7-7V3Zm0 4a5 5 0 1 0 5 5h-2a3 3 0 1 1-3-3V7Zm0 4 7-7 1.4 1.4-7 7L12 11Z",
  PROSPECT: "M11 3a8 8 0 1 0 4.9 14.3l4.4 4.4 1.4-1.4-4.4-4.4A8 8 0 0 0 11 3Zm0 2a6 6 0 1 1 0 12 6 6 0 0 1 0-12Zm-1 2v3H7v2h3v3h2v-3h3v-2h-3V7h-2Z",
  STUDY: "M11 3a8 8 0 1 0 4.9 14.3l4.4 4.4 1.4-1.4-4.4-4.4A8 8 0 0 0 11 3Zm0 2a6 6 0 1 1 0 12 6 6 0 0 1 0-12Z",
  DEPLOY: "M4 11h11.2l-4.6-4.6L12 5l7 7-7 7-1.4-1.4 4.6-4.6H4v-2Z",
  RETURN: "M20 11H8.8l4.6-4.6L12 5l-7 7 7 7 1.4-1.4L8.8 13H20v-2Z",
  COLONIZE: "M6 3h2v1h10l-2 4 2 4H8v9H6V3Zm2 3v4h6.8l-1-2 1-2H8Z",
  ATTACK: "M11 2h2v3.1A7 7 0 0 1 18.9 11H22v2h-3.1A7 7 0 0 1 13 18.9V22h-2v-3.1A7 7 0 0 1 5.1 13H2v-2h3.1A7 7 0 0 1 11 5.1V2Zm1 5a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4Z",
  EXTRACT: "M14 2l8 8-2.8 2.8-1.6-1.6L9 19.8 4.2 15l8.6-8.6-1.6-1.6L14 2Zm-6 15.6 1 1L18.4 9l-1-1L8 17.6ZM3 20l1.6-1.6 1 1L4 21l-1-1Z",
};

export function ActionGlyph({ kind }: { kind: MissionKind }) {
  return <span className={`cmd-glyph cmd-glyph--${kind.toLowerCase()}`} aria-hidden="true">
    <svg viewBox="0 0 24 24" width="16" height="16"><path d={PATHS[kind]} fill="currentColor" /></svg></span>;
}
