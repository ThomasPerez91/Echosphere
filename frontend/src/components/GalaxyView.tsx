import { useCallback, useEffect, useRef, useState } from 'react';
import { duration, exactUnits, resourceKeys, resourceLabels, time } from '../colony/format';
import { empires, GalaxyError, projection, request } from '../galaxy/api';
import type { Projection } from '../galaxy/api';

const stateLabels = { DETECTED: 'Détecté', MAPPED: 'Cartographié', MONITORED: 'Surveillé' };
const messages: Record<string, string> = {
  galaxy_unavailable: 'La galaxie n’est pas initialisée pour cet Empire.',
  exploration_active: 'Une expédition est déjà engagée.',
  insufficient_resources: 'La colonie ne dispose pas des ressources nécessaires.',
  permission_denied: 'Vous ne disposez pas des permissions nécessaires.',
  destination_mapped: 'Ce système est déjà cartographié.',
  destination_unreachable: 'Aucun chemin connu ne permet cette expédition.',
  system_not_found: 'Ce système n’est pas accessible.',
  authentication_required: 'La session a expiré. Retournez au lobby.',
};
type ViewBox = { x: number; y: number; width: number; height: number };
function bounds(data: Projection): ViewBox {
  const xs = data.systems.map(s => s.x), ys = data.systems.map(s => s.y);
  const x = Math.min(...xs) - 100, y = Math.min(...ys) - 100;
  return { x, y, width: Math.max(300, Math.max(...xs) - x + 100),
    height: Math.max(300, Math.max(...ys) - y + 100) };
}
export function GalaxyView({ universe, csrf, onSessionLost, onEconomyChanged }: {
  universe: string; csrf?: string; onSessionLost: () => void; onEconomyChanged: () => void;
}) {
  const [data, setData] = useState<Projection | null>(null);
  const [choices, setChoices] = useState<{id: string; name: string}[]>([]);
  const [empire, setEmpire] = useState('');
  const [selected, setSelected] = useState('');
  const [source, setSource] = useState('');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [pending, setPending] = useState(false);
  const [view, setView] = useState<ViewBox | null>(null);
  const [tick, setTick] = useState(Date.now());
  const dialog = useRef<HTMLDialogElement>(null);
  const launchButton = useRef<HTMLButtonElement>(null);
  const drag = useRef<{ x: number; y: number; box: ViewBox } | null>(null);
  const current = useRef({ universe, empire, csrf, onSessionLost, onEconomyChanged });
  current.current = { universe, empire, csrf, onSessionLost, onEconomyChanged };
  const generation = useRef(0);
  const loading = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const intent = useRef<{ signature: string; key: string } | null>(null);
  const lastServer = useRef('');
  const load = useCallback(async (target?: string) => {
    loading.current?.abort();
    const controller = new AbortController(); loading.current = controller;
    const observed = generation.current;
    const scope = current.current;
    const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      let id = target ?? scope.empire;
      if (!id) {
        const list = empires(await request(`/api/game/${scope.universe}/galaxy`, controller.signal));
        if (observed !== generation.current || controller.signal.aborted) return;
        setChoices(list);
        if (!list.length) { setError('Aucun Empire accessible pour la Galaxie.'); return; }
        id = list[0].id; setEmpire(id);
      }
      const result = projection(await request(`/api/game/${scope.universe}/galaxy/${id}`, controller.signal));
      if (observed !== generation.current || controller.signal.aborted || result.server_time < lastServer.current) return;
      lastServer.current = result.server_time; setData(result); setError('');
      setView(old => old ?? bounds(result));
    } catch (caught) {
      if (observed !== generation.current || controller.signal.aborted) return;
      if (caught instanceof GalaxyError && caught.status === 401) current.current.onSessionLost();
      setError(caught instanceof GalaxyError ? messages[caught.code] ?? 'La galaxie est momentanément indisponible.' : 'La connexion a été interrompue.');
    } finally { window.clearTimeout(timer); }
  }, []);
  useEffect(() => {
    generation.current += 1; lastServer.current = ''; intent.current = null;
    setData(null); setChoices([]); setEmpire(''); setSelected(''); setSource(''); setView(null); setFeedback('');
    current.current.empire = '';
    void load();
    return () => { generation.current += 1; loading.current?.abort(); };
  }, [universe, load]);
  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const active = data?.missions.find(m => m.status === 'active');
  useEffect(() => {
    if (!active || !data) return;
    // Passive, bounded rereads never count as activity. The server alone confirms completion.
    const remaining = Math.max(0, Date.parse(active.due_at) - Date.parse(data.server_time));
    const timers = [0, 3000, 10000, 30000].map(delay => window.setTimeout(() => void load(), remaining + delay));
    return () => timers.forEach(window.clearTimeout);
  }, [active, data, load]);
  const system = data?.systems.find(s => s.id === selected);
  const funding = source || data?.sources[0]?.id || '';
  const option = data?.options.find(o => o.destination_id === selected && o.colony_id === funding);
  const confirm = async () => {
    if (!option || busy.current || !data) return;
    busy.current = true; setPending(true); dialog.current?.close();
    const observed = generation.current;
    const scope = current.current;
    const signature = `${scope.universe}/${scope.empire}/${funding}/${selected}`;
    if (intent.current?.signature !== signature) intent.current = { signature, key: crypto.randomUUID() };
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      const value = await request(`/api/game/${scope.universe}/exploration/${scope.empire}/missions`, controller.signal,
        { colony_id: funding, destination_id: selected, idempotency_key: intent.current.key }, scope.csrf);
      if (observed !== generation.current) return;
      if (!value || typeof value !== 'object' || !('galaxy' in value)) throw new GalaxyError('invalid_response', 0);
      const result = projection(value.galaxy);
      lastServer.current = result.server_time; setData(result); intent.current = null;
      setFeedback('Expédition acceptée. Elle progressera même après fermeture du navigateur.');
      current.current.onEconomyChanged();
    } catch (caught) {
      if (observed !== generation.current) return;
      if (caught instanceof GalaxyError && caught.status > 0 && caught.status < 500) {
        intent.current = null;
        setFeedback(messages[caught.code] ?? 'La commande a été refusée. Actualisez les informations.');
        if (caught.status === 401) current.current.onSessionLost(); else void load();
      } else setFeedback('Résultat non confirmé. Réessayez la même expédition pour retrouver son résultat sans double paiement.');
    } finally {
      window.clearTimeout(timer); busy.current = false;
      if (observed === generation.current) { setPending(false); launchButton.current?.focus(); }
    }
  };
  const changeEmpire = (id: string) => {
    generation.current += 1; lastServer.current = ''; current.current.empire = id;
    intent.current = null; setEmpire(id); setData(null); setSelected(''); setSource(''); setView(null); void load(id);
  };
  const zoom = (factor: number) => setView(old => old ? { x: old.x + old.width * (1 - factor) / 2,
    y: old.y + old.height * (1 - factor) / 2, width: Math.min(4000, Math.max(100, old.width * factor)),
    height: Math.min(4000, Math.max(100, old.height * factor)) } : old);
  return <section className="galaxy-screen" aria-label="Carte galactique">
    <div className="galaxy-toolbar">
      {choices.length > 0 && <label>Empire <select value={empire} disabled={pending}
        onChange={e => changeEmpire(e.target.value)}>{choices.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label>}
      <button type="button" onClick={() => void load()}>Actualiser la galaxie</button>
    </div>
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p role="status">Chargement des connaissances…</p>}
    {data && view && <>
      <p className="galaxy-legend">◌ Détecté · ◉ Cartographié · ◈ Surveillé. Seules vos connaissances sont affichées.</p>
      <div className="galaxy-layout"><div className="panel galaxy-map-panel">
        <div className="galaxy-toolbar" aria-label="Commandes de la carte">
          <button type="button" onClick={() => zoom(0.8)} aria-label="Zoom avant">+</button>
          <button type="button" onClick={() => zoom(1.25)} aria-label="Zoom arrière">−</button>
          <button type="button" onClick={() => setView(bounds(data))}>Recentrer</button>
        </div>
        <svg className="galaxy-map" aria-label="Systèmes et routes connus" role="group"
          viewBox={`${view.x} ${view.y} ${view.width} ${view.height}`}
          onPointerDown={e => { if (e.target === e.currentTarget) {
            drag.current = { x: e.clientX, y: e.clientY, box: view }; e.currentTarget.setPointerCapture(e.pointerId);
          } }} onPointerMove={e => { if (drag.current) {
            const rect = e.currentTarget.getBoundingClientRect(); const initial = drag.current;
            setView({ ...initial.box, x: initial.box.x - (e.clientX - initial.x) * initial.box.width / rect.width,
              y: initial.box.y - (e.clientY - initial.y) * initial.box.height / rect.height });
          } }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
          {data.routes.map(r => { const a = data.systems.find(s => s.id === r.a_id)!, b = data.systems.find(s => s.id === r.b_id)!;
            return <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} vectorEffect="non-scaling-stroke" />; })}
          {data.systems.map((s, i) => <g key={s.id} tabIndex={0} role="button" aria-pressed={selected === s.id}
            aria-label={`${s.name ?? `Système détecté ${i + 1}`} — ${stateLabels[s.state]}`}
            className={`galaxy-node galaxy-node--${s.state.toLowerCase()}`} onClick={() => setSelected(s.id)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(s.id); } }}>
            <circle cx={s.x} cy={s.y} r={10} className="galaxy-hit" vectorEffect="non-scaling-stroke" />
            <circle cx={s.x} cy={s.y} r={8} className="galaxy-star" vectorEffect="non-scaling-stroke" />
            <text x={s.x + 18} y={s.y + 4}>{s.name ?? `Détection ${i + 1}`}</text>
          </g>)}
        </svg>
        <label className="galaxy-list-label">Systèmes connus — sélection accessible
          <select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Choisir un système</option>
            {data.systems.map((s, i) => <option key={s.id} value={s.id}>{s.name ?? `Système détecté ${i + 1}`} — {stateLabels[s.state]}</option>)}
          </select>
        </label>
      </div><aside className="panel galaxy-detail" aria-label="Connaissance du système">
        {system ? <><h2>{system.name ?? 'Système détecté'}</h2><p>{stateLabels[system.state]}</p>
          {system.state === 'DETECTED' ? <p>Position approximative. Structure encore inconnue.</p>
            : <><p>{system.last_seen_at ? `${system.state === 'MONITORED' ? 'Observation locale' : 'Dernière observation'} : ${time(system.last_seen_at)}` : 'Structure connue durablement ; aucune surveillance distante.'}</p>
              <ul>{system.planets?.map(p => <li key={p.id}><strong>{p.name}</strong> · {p.sector_capacity} secteurs · {p.orbital_capacity} orbitaux</li>)}</ul></>}
          {system.state === 'DETECTED' && <>
            {data.sources.length > 0 && <label>Colonie source <select value={funding} disabled={pending}
              onChange={e => setSource(e.target.value)}>{data.sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
            {option ? <><p>{option.hops} saut(s) aller · {duration(option.duration_us)}</p>
              <ul>{resourceKeys.map(r => <li key={r}>{exactUnits(option.cost[r])} {resourceLabels[r]}</li>)}</ul>
              <button ref={launchButton} type="button" disabled={pending || !!option.reason}
                onClick={() => dialog.current?.showModal()}>Préparer l’expédition</button>
              {option.reason && <p>{messages[option.reason] ?? 'Expédition indisponible.'}</p>}</>
              : <p>Aucune expédition accessible depuis vos colonies autorisées.</p>}
          </>}
        </> : <p>Sélectionnez un système sur la carte ou dans la liste.</p>}
      </aside></div>
      <section className="panel" aria-label="Expéditions"><h2>Expéditions</h2>
        {!data.missions.length && <p>Aucune expédition connue.</p>}
        {data.missions.map(m => <article key={m.id}><h3>{m.status === 'active' ? 'Expédition en cours' : 'Expédition terminée'}</h3>
          <p>Échéance : {time(m.due_at)}</p>
          {m.status === 'active' && <><progress max={100} value={Math.max(0, Math.min(100,
            (tick - Date.parse(m.started_at)) * 100 / (Date.parse(m.due_at) - Date.parse(m.started_at))))} aria-label="Avancement estimé de l’expédition" />
            <p>Seul le serveur confirme l’achèvement. Vous pouvez fermer cette page.</p></>}
          {m.report && <details><summary>Rapport d’exploration</summary><p>{m.report.discoveries.system.name} — structure cartographiée.</p>
            <p>Observation : {time(m.report.observed_at)} · traitement : {time(m.report.processed_at)}</p></details>}
        </article>)}
      </section>
      <dialog ref={dialog} onClose={() => launchButton.current?.focus()} aria-labelledby="expedition-title">
        <h2 id="expedition-title">Engager cette expédition ?</h2>
        <p>Le coût sera débité immédiatement depuis la colonie source. Aucun rappel, annulation ou remboursement.</p>
        {option && <><p>Durée : {duration(option.duration_us)}</p><ul>{resourceKeys.map(r => <li key={r}>{exactUnits(option.cost[r])} {resourceLabels[r]}</li>)}</ul></>}
        <button type="button" onClick={() => dialog.current?.close()}>Retour</button>
        <button type="button" disabled={pending} onClick={() => void confirm()}>Confirmer l’expédition</button>
      </dialog>
    </>}
    {feedback && <p role="status">{feedback}</p>}
  </section>;
}
