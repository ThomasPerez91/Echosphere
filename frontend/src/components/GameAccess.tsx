import type { useGameSession } from '../hooks/useGameSession';
import { Button, Panel } from './ui';

type Access = ReturnType<typeof useGameSession>;
const date = (value: string) => new Date(value).toLocaleString('fr-FR', { timeZoneName: 'short' });
export function GameAccess({ access }: { access: Access }) {
  const { phase, session, portal, busy } = access;
  return <Panel title="Accès à la partie" className="game-access">
    {phase === 'loading' && <p aria-live="polite">Vérification de votre accès…</p>}
    {phase === 'active' && session && <>
      <p>Vous êtes connecté à <strong>{session.universe_name}</strong>. Les actions de jeu ne sont pas encore disponibles.</p>
      <dl><div><dt>Fin de cette session</dt><dd><time dateTime={session.expires_at}>{date(session.expires_at)}</time></dd></div>
        <div><dt>Sans nouvelle interaction</dt><dd><time dateTime={session.idle_expires_at}>{date(session.idle_expires_at)}</time></dd></div>
        <div><dt>Confirmation d’accès valable jusqu’au</dt><dd><time dateTime={session.access_valid_until}>{date(session.access_valid_until)}</time></dd></div></dl>
      <div className="access-actions"><Button disabled={busy} onClick={() => { void access.refresh(); }}>Actualiser mon accès</Button>
        <Button disabled={busy} onClick={() => { void access.logout(); }}>Déconnecter cette partie</Button></div>
      <p>Les lectures automatiques ne prolongent pas votre session. Quitter cet écran conserve votre connexion à cette partie.</p>
    </>}
    {phase === 'expired' && <p role="alert">Votre session a expiré ou a été déconnectée. Retournez au lobby pour entrer à nouveau.</p>}
    {phase === 'signed-out' && <p aria-live="polite">Partie déconnectée. Vos autres parties et votre compte Portal restent connectés.</p>}
    {phase === 'unavailable' && <><p role="alert">Accès non confirmé. Le service est indisponible ou votre connexion a changé.</p>
      <Button disabled={busy} onClick={() => { void access.retry(); }}>Vérifier mon accès</Button></>}
    {portal && <a className="text-link" href={portal} referrerPolicy="no-referrer">Retour au lobby</a>}
  </Panel>;
}
