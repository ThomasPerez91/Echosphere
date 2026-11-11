import { useState } from 'react';

const errors: Record<string, string> = {
  invalid_empire_name: 'Le nom d’Empire doit compter 2 à 40 caractères visibles.',
  rename_unavailable: 'Le nom ne peut plus être changé dans cette partie.',
  leave_unavailable: 'Cette partie ne peut pas être quittée depuis le Portal.',
  delete_unavailable: 'Une partie multijoueur ne se supprime pas : quittez-la, les autres joueurs continuent.',
  csrf_denied: 'Votre connexion a changé. Rechargez la page puis réessayez.',
};

async function post(path: string, csrf: string, body: object) {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(body), signal: AbortSignal.timeout(10000) });
  const data: unknown = await response.json().catch(() => null);
  const code = data && typeof data === 'object' && 'error' in data && data.error && typeof data.error === 'object' && 'code' in data.error ? String(data.error.code) : '';
  if (!response.ok) throw new Error(code || 'request');
}

/** Q60: the player names the Empire of their seat; Game applies the name through the control outbox. */
export function EmpireName({ csrf, universe, current, canRename, onChanged }: {
  csrf: string; universe: string; current: string | null | undefined; canRename: boolean; onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(current ?? '');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  if (!editing) return <>
    {current ? <dd>{current}</dd> : <dd className="p-na">Nom non choisi</dd>}
    {canRename && <dd><button type="button" className="text-button" onClick={() => { setValue(current ?? ''); setEditing(true); setMessage(''); }}>
      {current ? 'Renommer' : 'Choisir un nom'}</button></dd>}
    {message && <dd role="status" className="p-g-note">{message}</dd>}
  </>;
  const save = async () => {
    const name = value.split(/\s+/).filter(Boolean).join(' ');
    if (name.length < 2 || name.length > 40) { setMessage(errors.invalid_empire_name); return; }
    if (busy) return; setBusy(true); setMessage('');
    try {
      await post(`/api/lobby/universes/${encodeURIComponent(universe)}/empire-name`, csrf, { name });
      setEditing(false); setMessage('Nom enregistré : il s’affichera en jeu dans quelques secondes.'); onChanged();
    } catch (failure) { setMessage(errors[(failure as Error).message] ?? 'Nom non confirmé. Réessayez.'); }
    finally { setBusy(false); }
  };
  return <dd><form className="p-empire-name" onSubmit={event => { event.preventDefault(); void save(); }}>
    <label className="visually-hidden" htmlFor={`empire-${universe}`}>Nom de votre Empire</label>
    <input id={`empire-${universe}`} value={value} maxLength={40} onChange={event => setValue(event.target.value)} autoFocus />
    <button type="submit" className="p-btn p-btn-sm" disabled={busy}>Enregistrer</button>
    <button type="button" className="text-button" onClick={() => setEditing(false)}>Annuler</button>
    {message && <span role="alert" className="form-error">{message}</span>}
  </form></dd>;
}

/**
 * Q60: a solo game is archived (still readable, no longer playable); leaving a multi game hands
 * the player's Empire to a server AI. Both are confirmed in place, never through a browser dialog.
 */
export function LeaveGame({ csrf, universe, name, family, onChanged }: {
  csrf: string; universe: string; name: string; family: 'solo' | 'private'; onChanged: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const solo = family === 'solo';
  const leave = async () => {
    if (busy) return; setBusy(true); setMessage('');
    try { await post(`/api/lobby/universes/${encodeURIComponent(universe)}/leave`, csrf, {}); setConfirming(false); onChanged(); }
    catch (failure) { setMessage(errors[(failure as Error).message] ?? 'Action non confirmée. Réessayez.'); }
    finally { setBusy(false); }
  };
  if (!confirming) return <button type="button" className="p-btn p-btn-sm" onClick={() => setConfirming(true)}>
    {solo ? 'Archiver la partie' : 'Quitter la partie'}</button>;
  return <div className="p-leave" role="group" aria-label={solo ? `Archiver ${name}` : `Quitter ${name}`}>
    <p>{solo
      ? 'La partie sera archivée : vous pourrez encore consulter vos rapports et la carte, mais plus donner d’ordres. Rien n’est effacé.'
      : 'Votre Empire sera repris par une IA qui suit les mêmes règles ; vous ne pourrez plus y revenir. Les autres joueurs continuent.'}</p>
    <button type="button" className="p-btn p-btn-sm p-btn-danger" disabled={busy} onClick={() => { void leave(); }}>
      {solo ? 'Confirmer l’archivage' : 'Confirmer : quitter la partie'}</button>
    <button type="button" className="text-button" onClick={() => setConfirming(false)}>Annuler</button>
    {message && <p role="alert" className="form-error">{message}</p>}
  </div>;
}

/** Recette 09/11/2026: the creator deletes a solo game, or a creation that never started.
 * Confirmed in place; the game leaves every list and its access is revoked. */
export function DeleteGame({ csrf, universe, name, started, onChanged }: {
  csrf: string; universe: string; name: string; started: boolean; onChanged: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const remove = async () => {
    if (busy) return; setBusy(true); setMessage('');
    try { await post(`/api/lobby/universes/${encodeURIComponent(universe)}/delete`, csrf, {}); setConfirming(false); onChanged(); }
    catch (failure) { setMessage(errors[(failure as Error).message] ?? 'Suppression non confirmée. Réessayez.'); }
    finally { setBusy(false); }
  };
  if (!confirming) return <button type="button" className="p-btn p-btn-sm p-btn-quiet-danger" onClick={() => setConfirming(true)}>Supprimer</button>;
  return <div className="p-leave" role="group" aria-label={`Supprimer ${name}`}>
    <p>{started ? 'La partie disparaîtra de vos listes et vous n’y aurez plus accès. Cette action est définitive.'
      : 'Cette création disparaîtra de vos listes ; si le serveur la démarre plus tard, elle restera inaccessible.'}</p>
    <button type="button" className="p-btn p-btn-sm p-btn-danger" disabled={busy} onClick={() => { void remove(); }}>Confirmer la suppression</button>
    <button type="button" className="text-button" onClick={() => setConfirming(false)}>Annuler</button>
    {message && <p role="alert" className="form-error">{message}</p>}
  </div>;
}
