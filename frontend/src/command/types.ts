import type { MissionView, Plan, Protocol, Quote } from "../fleet/api";

/** Server quote; `path` exists only once UX-API-01 ships (optional, validated twice before use). */
export type CommandQuote = Quote; // `path` is optional on Quote until UX-API-01 ships
export type LaunchResult = { missionId: string | null };
export type CommandFeedback = { tone: "success" | "error" | "unknown"; code: string } | null;

/**
 * The only seam between the command map and data. Production implements it with the Game API
 * (`useFleets().run`, `previewMission`); the UX03 prototype with fixtures. Errors thrown by
 * `preview` carry a server `code`; `launch`/`recall` resolve null when refused or unknown (the
 * container exposes the reason through `CommandFeedback`).
 */
export type MissionApi = {
  preview(plan: Plan, signal: AbortSignal): Promise<CommandQuote>;
  launch(plan: Plan, quote: CommandQuote): Promise<LaunchResult | null>;
  recall(mission: MissionView): Promise<boolean>;
  /** 13B: change the first-contact protocol of a stationed task fleet (absent where unsupported). */
  protocol?(fleetId: string, protocol: Protocol | null): Promise<boolean>;
};
