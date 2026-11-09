import { useState } from 'react';
import { Icon } from '../theme/Icon';
import { Pending } from '../site/Site';
import { Link, paths } from '../router';

/** AI profiles the Game server knows today (app.ai.rules.PROFILES); 0 to 3 opponents per universe. */
const profiles = {
  economic_cautious: { label: 'Prudent', text: 'Développe son économie, défend ses mondes, n’attaque jamais.' },
  expansionist: { label: 'Expansionniste', text: 'Explore et colonise vite, cherche les mondes libres.' },
} as const;
type Profile = keyof typeof profiles;

/**
 * « Nouvelle partie »: the choices a player will make once the Portal can create a universe on its
 * own. Today a universe is created by an operator (provision, bootstrap, access); the form shows
 * exactly what the server will need and does not pretend to create anything.
 */
export function NewGame() {
  const [name, setName] = useState('');
  const [opponents, setOpponents] = useState<Profile[]>(['economic_cautious', 'expansionist']);
  const setCount = (count: number) => setOpponents(current => Array.from({ length: count }, (_, i) => current[i] ?? (i % 2 ? 'expansionist' : 'economic_cautious')));

  return <section className="p-panel p-new-game" aria-labelledby="new-game-title">
    <div className="p-p-head"><h2 id="new-game-title"><Icon name="plus" />Nouvelle partie</h2>
      <div className="p-tools"><Link to={paths.games} className="p-btn p-btn-sm">Retour à mes parties</Link></div></div>
    <form className="p-tab-pad p-new-game-form" onSubmit={event => event.preventDefault()} aria-describedby="new-game-pending">
      <label>Nom de l’univers
        <input value={name} onChange={event => setName(event.target.value)} maxLength={60} placeholder="Par exemple : Frontière d’Orion" aria-describedby="name-help" />
      </label>
      <p id="name-help" className="p-account-help">Entre 3 et 60 caractères. Il apparaîtra dans « Mes parties » et en haut de l’écran de jeu.</p>

      <fieldset>
        <legend>Adversaires dirigés par l’IA</legend>
        <div className="p-choice-row" role="radiogroup" aria-label="Nombre d’adversaires">
          {[0, 1, 2, 3].map(count => <label key={count} className={`p-choice${opponents.length === count ? ' is-on' : ''}`}>
            <input type="radio" name="opponents" checked={opponents.length === count} onChange={() => setCount(count)} />{count === 0 ? 'Aucun' : count}
          </label>)}
        </div>
        {opponents.map((profile, index) => <label key={index} className="p-opponent">Adversaire {index + 1}
          <select value={profile} onChange={event => setOpponents(current => current.map((p, i) => i === index ? event.target.value as Profile : p))}>
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

      <div id="new-game-pending"><Pending what="Création d’un univers depuis le Portal : à brancher sur le backend (création de l’univers, démarrage de la partie et accès à votre Empire). En attendant, une partie se crée avec la procédure opérateur de recette." /></div>
      <button type="submit" className="p-btn p-btn-primary" disabled title="Implémentation backend nécessaire">
        <Icon name="rocket" />Créer la partie</button>
    </form>
  </section>;
}
