import { useEffect, useState } from "react";
import type { Plan } from "../fleet/api";
import type { QuoteState } from "./copy";
import { EXTRACT_HOURS } from "./MissionPlanner";
import type { PlannerStep } from "./MissionPlanner";
import { actionLabels, defaultUnits, eligibleFleets, isGarrison, serverPath, stationed, systemName } from "./model";
import type { ActionOffer, World } from "./model";
import type { MissionApi } from "./types";

export type Intent = { offer: ActionOffer; fleet: string | null; units: Record<string, number>; hours?: number; comeBack?: boolean };

/**
 * One mission intention towards `target`, shared by the command map and the System View (the same
 * planner, the same server summary and the same confirmation). The server summary is asked only
 * on the summary step and follows the exact intention: any change makes the shown quote obsolete
 * and cancels the request in flight. Nothing is sent before `confirm`.
 */
export function useMissionFlow(world: World, api: MissionApi, target: string | null, pending: boolean) {
  const [intent, setIntent] = useState<Intent | null>(null);
  const [step, setStep] = useState<PlannerStep>("fleet");
  const [quote, setQuote] = useState<QuoteState>({ status: "idle" });
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false); // local guard until the container reports `pending`

  const candidates = intent && target ? eligibleFleets(world, intent.offer.kind, target) : [];
  const fleet = intent?.fleet ? stationed(world).find((f) => f.id === intent.fleet) ?? null : null;
  const engaged = intent ? Object.fromEntries(Object.entries(intent.units).filter(([, n]) => n > 0)) : {};
  const plan: Plan | null = intent && fleet && target && Object.keys(engaged).length ? {
    fleet_id: fleet.id, kind: intent.offer.kind, units: engaged,
    ...(intent.offer.planet ? { target_planet_id: intent.offer.planet }
      : intent.offer.opportunity ? { target_opportunity_id: intent.offer.opportunity } : { destination_id: target }),
    ...(intent.offer.kind === "EXTRACT" ? { duration_hours: intent.hours ?? EXTRACT_HOURS.initial, ...(intent.comeBack ? { after: "RETURN" as const } : {}) } : {}),
  } : null;
  const planKey = plan ? JSON.stringify(plan) : null;
  const ready = quote.status === "ready" && quote.key === planKey ? quote.quote : null;
  const path = serverPath(world, ready, fleet?.system?.id);

  useEffect(() => {
    if (step !== "summary" || !plan || !planKey) return;
    const controller = new AbortController();
    setQuote({ status: "loading", key: planKey });
    api.preview(plan, controller.signal)
      .then((q) => setQuote({ status: "ready", key: planKey, quote: q }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        const code = typeof e === "object" && e && "code" in e && typeof e.code === "string" ? e.code : "unavailable";
        setQuote({ status: "error", key: planKey, code });
      });
    return () => controller.abort();
    // planKey captures every field of `plan`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, planKey, api]);

  /** Opens the planner on an explicit intention (e.g. a fleet moved from the map). */
  const begin = (next: Intent, at: PlannerStep) => { setIntent(next); setStep(at); setQuote({ status: "idle" }); setFailed(false); };
  /** Starts an offered action: a single task fleet is preselected; several fleets or a garrison need an explicit choice. */
  const start = (offer: ActionOffer, system = target) => {
    if (!system) return;
    const choices = eligibleFleets(world, offer.kind, system);
    const only = choices.length === 1 && !isGarrison(choices[0]) ? choices[0] : null;
    begin({ offer, fleet: only?.id ?? null, units: only ? defaultUnits(world, only, offer.kind) : {} }, only ? "units" : "fleet");
  };
  const chooseFleet = (id: string) => {
    const f = stationed(world).find((x) => x.id === id)!;
    setIntent((p) => p && { ...p, fleet: id, units: defaultUnits(world, f, p.offer.kind) });
  };
  const update = (change: Partial<Intent>) => setIntent((p) => p && { ...p, ...change });
  const stop = () => setIntent(null);

  /** Sends the confirmed intention; the notice to show when the server accepted it, else null. */
  async function confirm(): Promise<string | null> {
    if (!plan || !ready || !fleet || !target || pending || busy) return null;
    setBusy(true);
    const result = await api.launch(plan, ready).finally(() => setBusy(false));
    if (!result) { setFailed(true); return null; }
    setIntent(null);
    return `${actionLabels[plan.kind]} confirmé : ${fleet.name} part vers ${systemName(world, ready.destination_id)} (${ready.hops} saut${ready.hops > 1 ? "s" : ""}).`;
  }

  return { intent, step, setStep, quote, failed, setFailed, busy, setBusy, candidates, fleet, plan, planKey, ready, path,
    begin, start, chooseFleet, update, stop, confirm };
}
