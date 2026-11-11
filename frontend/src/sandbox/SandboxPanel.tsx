import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError } from '../colony/api';
import { readSandbox, sandboxChanged, sandboxCommand } from './api';
import type { Finished, SandboxCommand, SandboxStatus } from './api';

const SHIPS: Record<string, string> = {
  probe: 'Sonde', freighter: 'Cargo léger', extractor: 'Extracteur', colonizer: 'Colonisateur',
  interceptor: 'Intercepteur', frigate: 'Frégate', cruiser: 'Croiseur',
};
const RESOURCES = [['alloys', 'Alliages'], ['flux', 'Flux'], ['data', 'Données']] as const;
type Resource = typeof RESOURCES[number][0];
const MESSAGES: Record<string, string> = {
  permission_denied: 'Cette session n’a pas le droit de construire.',
  combat_pending: 'Un combat doit d’abord être résolu.',
  invalid_request: 'Valeurs refusées par le serveur.',
};

const plural = (n: number, one: string, many: string) => `${n} ${n > 1 ? many : one}`;
function summary(done: Finished) {
  const parts = [
    done.constructions && plural(done.constructions, 'construction', 'constructions'),
    done.research && plural(done.research, 'recherche', 'recherches'),
    done.ships && plural(done.ships, 'commande de vaisseaux', 'commandes de vaisseaux'),
  ].filter(Boolean);
  return parts.length ? `Terminé maintenant : ${parts.join(', ')}.` : 'Rien en cours : aucune file à terminer.';
}

/**
 * Test game tools (sandbox): set the stocks of a colony, add ships, complete every queue now.
 * Shown only when Game says this universe is a test game; every view rereads after an action.
 */
export function SandboxPanel({ universe, empire, csrf, open, onToggle }: {
  universe: string; empire: string; csrf: string | undefined; open: boolean; onToggle: (open: boolean) => void;
}) {
  const [status, setStatus] = useState<SandboxStatus | null>(null);
  const [colonyId, setColonyId] = useState('');
  const [amounts, setAmounts] = useState<Record<Resource, string>>({ alloys: '', flux: '', data: '' });
  const [ship, setShip] = useState('probe');
  const [count, setCount] = useState('10');
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    readSandbox(universe, empire, abort.signal).then(setStatus).catch(() => setStatus(null));
    return () => abort.abort();
  }, [universe, empire]);
  useEffect(() => () => controller.current?.abort(), []);
  const colony = status?.colonies.find(c => c.id === colonyId) ?? status?.colonies[0];

  const run = useCallback(async (command: SandboxCommand, done: (result: unknown) => string) => {
    if (!csrf || pending) return;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    setPending(true); setFeedback(null);
    try {
      const body = await sandboxCommand(universe, empire, csrf, command, abort.signal);
      setStatus(body);
      setFeedback({ tone: 'ok', text: done(body.result) });
      sandboxChanged();
    } catch (error) {
      if (abort.signal.aborted) return;
      const code = error instanceof ApiError ? error.code : 'unavailable';
      setFeedback({ tone: 'error', text: MESSAGES[code] ?? 'Action non confirmée par le serveur. Réessayez.' });
    } finally { if (controller.current === abort) setPending(false); }
  }, [csrf, pending, universe, empire]);

  if (!status || !colony) return null;
  const grant = (values: Partial<Record<Resource, number>>) => run(
    { kind: 'resources', colony_id: colony.id, ...values }, () => `Stocks de ${colony.name} mis à jour (plafond de stockage ${Number(colony.capacity).toLocaleString('fr-FR')}).`);
  const submitResources = (event: FormEvent) => {
    event.preventDefault();
    const values = Object.fromEntries(RESOURCES.flatMap(([key]) => {
      const n = Number(amounts[key]);
      return amounts[key].trim() !== '' && Number.isInteger(n) && n >= 0 ? [[key, n]] : [];
    })) as Partial<Record<Resource, number>>;
    if (!Object.keys(values).length) { setFeedback({ tone: 'error', text: 'Indiquez au moins une quantité.' }); return; }
    void grant(values);
  };
  const submitShips = (event: FormEvent) => {
    event.preventDefault();
    const n = Number(count);
    if (!Number.isInteger(n) || n < 1 || n > 1000) { setFeedback({ tone: 'error', text: 'Entre 1 et 1 000 vaisseaux.' }); return; }
    void run({ kind: 'ships', colony_id: colony.id, ships: { [ship]: n } },
      () => `${n} × ${SHIPS[ship] ?? ship} ajouté${n > 1 ? 's' : ''} à la garnison de ${colony.name}.`);
  };
  const full = Number(colony.capacity);

  return <>
    <button type="button" className="d-icon-btn d-sandbox-btn" aria-label="Outils de la partie de test" aria-expanded={open}
      title="Partie de test" onClick={() => onToggle(!open)}>Test</button>
    {open && <div className="d-popover d-popover--sandbox" role="dialog" aria-label="Outils de la partie de test">
      <strong>Partie de test</strong>
      <p>Outils réservés aux parties de test : rien de tout cela n’existe dans une partie normale.</p>
      {status.colonies.length > 1 && <label className="d-sb-row">Colonie
        <select value={colony.id} onChange={event => setColonyId(event.target.value)}>
          {status.colonies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}

      <form className="d-sb-block" onSubmit={submitResources} aria-label="Ressources">
        <span className="d-sb-title">Ressources de {colony.name}</span>
        <div className="d-sb-grid">{RESOURCES.map(([key, label]) => <label key={key}>{label}
          <input type="number" inputMode="numeric" min={0} max={full} placeholder="inchangé" value={amounts[key]}
            onChange={event => setAmounts(old => ({ ...old, [key]: event.target.value }))} /></label>)}</div>
        <div className="d-sb-actions">
          <button type="submit" className="d-btn" disabled={pending}>Appliquer</button>
          <button type="button" className="d-btn" disabled={pending} onClick={() => void grant({ alloys: full, flux: full, data: full })}>Remplir au maximum</button>
        </div>
      </form>

      <form className="d-sb-block" onSubmit={submitShips} aria-label="Vaisseaux">
        <span className="d-sb-title">Vaisseaux en garnison</span>
        <div className="d-sb-grid d-sb-grid--2">
          <label>Classe<select value={ship} onChange={event => setShip(event.target.value)}>
            {status.ship_classes.map(c => <option key={c} value={c}>{SHIPS[c] ?? c}</option>)}</select></label>
          <label>Nombre<input type="number" inputMode="numeric" min={1} max={1000} value={count} onChange={event => setCount(event.target.value)} /></label>
        </div>
        <div className="d-sb-actions"><button type="submit" className="d-btn" disabled={pending}>Ajouter</button></div>
      </form>

      <div className="d-sb-block">
        <span className="d-sb-title">Accélérateur</span>
        <p>Termine immédiatement les constructions, recherches et commandes de vaisseaux en cours et en file.</p>
        <div className="d-sb-actions"><button type="button" className="d-btn d-btn-primary" disabled={pending}
          onClick={() => void run({ kind: 'finish' }, result => summary(result as Finished))}>Tout terminer maintenant</button></div>
      </div>
      {feedback && <p className={`d-sb-feedback d-sb-feedback--${feedback.tone}`} role={feedback.tone === 'error' ? 'alert' : 'status'}>{feedback.text}</p>}
      <button type="button" className="d-btn" onClick={() => onToggle(false)}>Fermer</button>
    </div>}
  </>;
}
