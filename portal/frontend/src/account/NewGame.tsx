import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Icon } from '../theme/Icon';
import { Link, paths } from '../router';

/** AI profiles the Game server knows today (app.ai.rules.PROFILES). */
const profiles = {
  economic_cautious: { label: 'Prudent', text: 'Développe son économie, défend ses mondes, n’attaque jamais.' },
  expansionist: { label: 'Expansionniste', text: 'Explore et colonise vite, cherche les mondes libres.' },
} as const;
type Profile = keyof typeof profiles;
const PROFILE_ORDER: Profile[] = ['economic_cautious', 'expansionist'];
const AI_LABELS: Record<Profile, string> = { economic_cautious: 'IA prudentes', expansionist: 'IA expansionnistes' };

/** Q61 map sizes and their Empire caps (players + AI); Game's ruleset stays the authority. */
const SIZES = [[100, 4], [300, 12], [500, 20], [1000, 40], [2000, 40]] as const;
const MAX_HUMANS = 10, MAX_AI = 30;
const grouped = (n: number) => n >= 1000 ? `${Math.floor(n / 1000)} ${String(n % 1000).padStart(3, '0')}` : String(n);
const capOf = (size: number) => SIZES.find(([s]) => s === size)?.[1] ?? 4;

const errors: Record<string, string> = {
  too_many_empires: 'Trop d’Empires pour cette taille de galaxie : choisissez une carte plus grande ou moins d’IA.',
  invalid_creation: 'Vérifiez le nom (3 à 60 caractères) et les adversaires.',
  invalid_empire_name: 'Le nom d’Empire doit compter 2 à 40 caractères visibles.',
  family_unavailable: 'Ce type de partie n’est pas encore disponible.',
  creation_request_conflict: 'Cette demande a déjà été envoyée avec d’autres choix. Rechargez la page.',
  creation_unavailable: 'La création de partie est indisponible pour le moment.',
  sandbox_unavailable: 'Les parties de test ne sont pas proposées sur ce serveur.',
  csrf_denied: 'Votre connexion a changé. Rechargez la page puis réessayez.',
};

/**
 * « Nouvelle partie » (UX-API-02, Q61): SOLO or multi, a galaxy size and AI opponents within its
 * Empire cap. One request id per
 * form, so a double click or a retry after a lost answer never creates two universes.
 */
export function NewGame({ csrf, onCreated, onExpired }: { csrf: string; onCreated: () => void; onExpired?: () => void }) {
  const [name, setName] = useState('');
  const [empireName, setEmpireName] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(crypto.randomUUID());
  // New choices = new request; the same choices retried after a lost answer reuse the same id.
  const fresh = () => { requestId.current = crypto.randomUUID(); };
  // Q61: galaxy size; players + AI never exceed its Empire cap.
  const [size, setSize] = useState(100);
  const [counts, setCounts] = useState<Record<Profile, number>>({ economic_cautious: 1, expansionist: 1 });
  const [family, setFamily] = useState<'solo' | 'private' | 'test'>('solo');
  const [humans, setHumans] = useState(2);
  const [invite, setInvite] = useState<'link' | 'email'>('link');
  const players = family === 'private' ? humans : 1;
  const cap = capOf(size);
  const maxAi = Math.max(0, Math.min(MAX_AI, cap - players));
  const opponents = PROFILE_ORDER.flatMap(id => Array.from({ length: counts[id] }, () => id));
  // Keeps the AI within the remaining room, dropping the last profiles first.
  const fit = (room: number) => setCounts(current => {
    const first = Math.min(current.economic_cautious, room);
    return { economic_cautious: first, expansionist: Math.min(current.expansionist, room - first) };
  });
  const roomFor = (nextSize: number, nextPlayers: number) => Math.max(0, Math.min(MAX_AI, capOf(nextSize) - nextPlayers));
  const chooseFamily = (next: 'solo' | 'private' | 'test') => {
    setFamily(next); fresh();
    const nextPlayers = next !== 'private' ? 1 : Math.min(humans, Math.min(MAX_HUMANS, cap));
    if (next === 'private') setHumans(nextPlayers);
    fit(roomFor(size, nextPlayers));
  };
  const chooseHumans = (next: number) => { setHumans(next); fresh(); fit(roomFor(size, next)); };
  const chooseSize = (next: number) => {
    setSize(next); fresh();
    const nextPlayers = family !== 'private' ? 1 : Math.min(humans, Math.min(MAX_HUMANS, capOf(next)));
    if (family === 'private') setHumans(nextPlayers);
    fit(roomFor(next, nextPlayers));
  };
  const setCount = (id: Profile, value: number) => {
    const other = PROFILE_ORDER.find(p => p !== id)!;
    const clean = Number.isFinite(value) ? Math.max(0, Math.min(Math.trunc(value), maxAi - counts[other])) : 0;
    setCounts(current => ({ ...current, [id]: clean })); fresh();
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const trimmed = name.trim();
    if (trimmed.length < 3 || trimmed.length > 60) { setError(errors.invalid_creation); return; }
    const empire = empireName.split(/\s+/).filter(Boolean).join(' ');
    if (empire && (empire.length < 2 || empire.length > 40)) { setError(errors.invalid_empire_name); return; }
    const named = empire ? { empire_name: empire } : {};
    setPending(true); setError('');
    try {
      const response = await fetch('/api/lobby/universes', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify(family === 'private'
          ? { request_id: requestId.current, name: trimmed, family, size, profiles: opponents, humans, invite, ...named }
          // Test game: a solo game whose world starts almost finished, with the sandbox tools.
          : { request_id: requestId.current, name: trimmed, family: 'solo', size, profiles: opponents, ...named, ...(family === 'test' ? { sandbox: true } : {}) }),
        signal: AbortSignal.timeout(10000) });
      if (response.status === 401) { onExpired?.(); return; }
      if (response.status === 404) { setError('Ce serveur ne sait pas encore créer de partie (mise à jour du Portal nécessaire).'); return; }
      if (response.status === 429) { setError('Trop de créations récentes. Réessayez dans une heure.'); return; }
      const body: unknown = await response.json().catch(() => null);
      const code = body && typeof body === 'object' && 'error' in body && body.error && typeof body.error === 'object' && 'code' in body.error
        ? String(body.error.code) : '';
      if (!response.ok) { setError(errors[code] ?? 'Création non confirmée. Réessayez : la même demande sera réutilisée.'); return; }
      onCreated();
    } catch {
      setError('Création non confirmée. Réessayez : la même demande sera réutilisée, sans créer deux parties.');
    } finally { setPending(false); }
  }

  return <section className="p-panel p-new-game" aria-labelledby="new-game-title">
    <div className="p-p-head"><h2 id="new-game-title"><Icon name="plus" />Nouvelle partie</h2>
      <div className="p-tools"><Link to={paths.games} className="p-btn p-btn-sm">Retour à mes parties</Link></div></div>
    <form className="p-tab-pad p-new-game-form" onSubmit={event => { void submit(event); }} aria-busy={pending}>
      <label>Nom de l’univers
        <input value={name} onChange={event => { setName(event.target.value); fresh(); }} required minLength={3} maxLength={60} placeholder="Par exemple : Frontière d’Orion" aria-describedby="name-help" />
      </label>
      <p id="name-help" className="p-account-help">Entre 3 et 60 caractères. Il apparaîtra dans « Mes parties » et en haut de l’écran de jeu.</p>
      <label>Nom de votre Empire
        <input value={empireName} onChange={event => { setEmpireName(event.target.value); fresh(); }} maxLength={40} placeholder="Par exemple : Concorde d’Aube" aria-describedby="empire-help" />
      </label>
      <p id="empire-help" className="p-account-help">Facultatif, 2 à 40 caractères ; visible des autres Empires. Vous pourrez le changer depuis « Mes parties ».</p>

      <fieldset>
        <legend>Taille de la galaxie</legend>
        <div className="p-choice-row" role="radiogroup" aria-label="Taille de la galaxie">
          {SIZES.map(([systems, empires]) => <label key={systems} className={`p-choice${size === systems ? ' is-on' : ''}`}>
            <input type="radio" name="size" checked={size === systems} onChange={() => chooseSize(systems)} />
            {grouped(systems)} systèmes<small>jusqu’à {empires} Empires</small></label>)}
        </div>
        <p className="p-account-help">Chaque Empire démarre avec un système et sa colonie de base. Impasses et passages obligés font des goulots d’étranglement à tenir.</p>
      </fieldset>

      <fieldset>
        <legend>Type de partie</legend>
        <div className="p-choice-row" role="radiogroup" aria-label="Type de partie">
          {([['solo', 'Solo'], ['private', 'Multijoueur'], ['test', 'Test']] as const).map(([id, label]) => <label key={id} className={`p-choice${family === id ? ' is-on' : ''}`}>
            <input type="radio" name="family" checked={family === id} onChange={() => chooseFamily(id)} />{label}</label>)}
        </div>
        {family === 'test' && <p className="p-account-help">Partie de test, solo : tout est débloqué (bâtiments niveau 10, technologies, galaxie entièrement cartographiée, Empires adverses visibles mais toujours inconnus) et un panneau « Test » en jeu permet de se donner des ressources et des vaisseaux et de terminer immédiatement constructions, recherches et chantiers.</p>}
        {family === 'private' && <>
          <p className="p-account-help">Vous invitez vos amis ; chacun dirige son propre Empire. Alliances, coopération ou trahison se décident en jeu.</p>
          <label className="p-count">Joueurs humains
            <select aria-label="Joueurs humains" value={humans} onChange={event => chooseHumans(Number(event.target.value))}>
              {Array.from({ length: Math.min(MAX_HUMANS, cap) - 1 }, (_, i) => i + 2).map(count => <option key={count} value={count}>{count} joueurs</option>)}
            </select>
          </label>
          <div className="p-choice-row" role="radiogroup" aria-label="Mode d’invitation">
            {([['link', 'Lien à partager'], ['email', 'Invitation par email']] as const).map(([id, label]) => <label key={id} className={`p-choice${invite === id ? ' is-on' : ''}`}>
              <input type="radio" name="invite" checked={invite === id} onChange={() => { setInvite(id); fresh(); }} />{label}</label>)}
          </div>
          <p className="p-account-help">{invite === 'link' ? 'Après la création, générez un lien dans « Mes parties » et envoyez-le à vos amis.' : 'Après la création, saisissez l’adresse email de chaque joueur dans « Mes parties ».'}</p>
        </>}
      </fieldset>

      <fieldset>
        <legend>Adversaires dirigés par l’IA</legend>
        {PROFILE_ORDER.map(id => <label key={id} className="p-opponent">{AI_LABELS[id]}
          <input type="number" inputMode="numeric" aria-label={AI_LABELS[id]} min={0} max={maxAi - counts[PROFILE_ORDER.find(p => p !== id)!]} value={counts[id]}
            onChange={event => setCount(id, Number(event.target.value))} />
          <small>{profiles[id].text}</small>
        </label>)}
        <p className="p-account-help">{opponents.length} adversaire{opponents.length > 1 ? 's' : ''} sur {maxAi} possible{maxAi > 1 ? 's' : ''} : {players + opponents.length} Empire{players + opponents.length > 1 ? 's' : ''} sur {cap} pour cette galaxie.</p>
        <p className="p-account-help">Les IA suivent les mêmes règles que vous : elles ne reçoivent ni ressource ni flotte gratuite.</p>
      </fieldset>

      <div className="p-new-game-facts">
        <p><Icon name="infinity" /><span><b>Univers persistant</b> : il continue d’avancer quand vous n’êtes pas connecté.</span></p>
        <p><Icon name="planet" /><span><b>Départ</b> : une colonie de départ par Empire, des systèmes à découvrir autour de vous.</span></p>
        <p><Icon name="clock" /><span><b>Début</b> : immédiat, dès la création.</span></p>
      </div>

      <p className="p-account-help">Placement des départs : <b>équitable</b> (mêmes ressources proches et au moins deux sorties pour chaque Empire). Les placements dispersé et regroupé viendront ensuite.</p>
      <button type="submit" className="p-btn p-btn-primary" disabled={pending}>
        <Icon name="rocket" />{pending ? 'Création…' : 'Créer la partie'}</button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  </section>;
}
