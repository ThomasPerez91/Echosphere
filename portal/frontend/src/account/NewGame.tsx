import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Icon } from '../theme/Icon';
import { Pending } from '../site/Site';
import { Link, paths } from '../router';

/** AI profiles the Game server knows today (app.ai.rules.PROFILES); 0 to 3 opponents per universe. */
const profiles = {
  economic_cautious: { label: 'Prudent', text: 'Développe son économie, défend ses mondes, n’attaque jamais.' },
  expansionist: { label: 'Expansionniste', text: 'Explore et colonise vite, cherche les mondes libres.' },
} as const;
type Profile = keyof typeof profiles;

const errors: Record<string, string> = {
  invalid_creation: 'Vérifiez le nom (3 à 60 caractères) et les adversaires.',
  family_unavailable: 'Ce type de partie n’est pas encore disponible.',
  creation_request_conflict: 'Cette demande a déjà été envoyée avec d’autres choix. Rechargez la page.',
  creation_unavailable: 'La création de partie est indisponible pour le moment.',
  csrf_denied: 'Votre connexion a changé. Rechargez la page puis réessayez.',
};

/**
 * « Nouvelle partie » (UX-API-02): a SOLO universe with 0 to 3 AI opponents. One request id per
 * form, so a double click or a retry after a lost answer never creates two universes.
 */
export function NewGame({ csrf, onCreated, onExpired }: { csrf: string; onCreated: () => void; onExpired?: () => void }) {
  const [name, setName] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(crypto.randomUUID());
  // New choices = new request; the same choices retried after a lost answer reuse the same id.
  const fresh = () => { requestId.current = crypto.randomUUID(); };
  const [opponents, setOpponents] = useState<Profile[]>(['economic_cautious', 'expansionist']);
  const setCount = (count: number) => setOpponents(current => Array.from({ length: count }, (_, i) => current[i] ?? (i % 2 ? 'expansionist' : 'economic_cautious')));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const trimmed = name.trim();
    if (trimmed.length < 3 || trimmed.length > 60) { setError(errors.invalid_creation); return; }
    setPending(true); setError('');
    try {
      const response = await fetch('/api/lobby/universes', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ request_id: requestId.current, name: trimmed, family: 'solo', profiles: opponents }),
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

      <fieldset>
        <legend>Adversaires dirigés par l’IA</legend>
        <div className="p-choice-row" role="radiogroup" aria-label="Nombre d’adversaires">
          {[0, 1, 2, 3].map(count => <label key={count} className={`p-choice${opponents.length === count ? ' is-on' : ''}`}>
            <input type="radio" name="opponents" checked={opponents.length === count} onChange={() => { setCount(count); fresh(); }} />{count === 0 ? 'Aucun' : count}
          </label>)}
        </div>
        {opponents.map((profile, index) => <label key={index} className="p-opponent">Adversaire {index + 1}
          <select value={profile} onChange={event => { const value = event.target.value as Profile; setOpponents(current => current.map((p, i) => i === index ? value : p)); fresh(); }}>
            {(Object.keys(profiles) as Profile[]).map(id => <option key={id} value={id}>{profiles[id].label}</option>)}
          </select>
          <small>{profiles[profile].text}</small>
        </label>)}
        <p className="p-account-help">Les IA suivent les mêmes règles que vous : elles ne reçoivent ni ressource ni flotte gratuite.</p>
      </fieldset>

      <div className="p-new-game-facts">
        <p><Icon name="infinity" /><span><b>Univers persistant</b> : il continue d’avancer quand vous n’êtes pas connecté.</span></p>
        <p><Icon name="planet" /><span><b>Départ</b> : une colonie de départ, des systèmes à découvrir autour de vous.</span></p>
        <p><Icon name="clock" /><span><b>Début</b> : immédiat, dès la création.</span></p>
      </div>

      <div className="p-family-row">
        <span className="p-chip p-live">Solo</span>
        <span className="p-chip" title="Implémentation backend nécessaire">Multijoueur — à venir (invitation par lien ou email, jusqu’à 10 joueurs)</span>
      </div>
      <Pending compact what="Taille de carte et placement des Empires : options à venir. Aujourd’hui, carte standard." />
      <button type="submit" className="p-btn p-btn-primary" disabled={pending}>
        <Icon name="rocket" />{pending ? 'Création…' : 'Créer la partie'}</button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  </section>;
}
