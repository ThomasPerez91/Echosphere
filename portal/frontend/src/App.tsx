import { useReadiness } from './useReadiness';

export default function App() {
  const { status, retry } = useReadiness();
  const message = { checking: 'Vérification du Portal', connected: 'Portal disponible', unavailable: 'Portal indisponible' }[status];

  return <div className="portal-shell">
    <a className="skip-link" href="#main-content">Aller au contenu</a>
    <header><a className="brand" href="/">◈ Echosphere<span>.</span></a><span className="portal-label">ESPACE COMPTE</span></header>
    <main id="main-content" tabIndex={-1}>
      <p className="eyebrow">UN COMPTE, PLUSIEURS HORIZONS</p>
      <h1>Votre prochain univers<br />commence ici.</h1>
      <p className="intro">Le Portal réunira votre compte et vos parties. Le jeu continuera de progresser à son propre rythme.</p>
      <section className="panel" aria-labelledby="foundation-title">
        <p className="eyebrow">FONDATION EN COURS</p>
        <h2 id="foundation-title">Comptes et lobby en préparation</h2>
        <p>L’inscription, la connexion et l’accès aux parties ne sont pas encore disponibles.</p>
      </section>
      <section className="panel connection" aria-labelledby="connection-title">
        <div><h2 id="connection-title">Connexion au Portal</h2><p role="status" aria-live="polite">{message}</p></div>
        <button type="button" onClick={retry} disabled={status === 'checking'}>Vérifier à nouveau</button>
      </section>
    </main>
    <footer>Version de développement · Echosphere</footer>
  </div>;
}
