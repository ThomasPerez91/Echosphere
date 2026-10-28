# Frontend

**Statut : shell responsive implémenté à l’étape 4 ; aucune API de gameplay.**

React + TypeScript strict + Vite. Navigation par fragments natifs `#empire`, `#colony`, `#research`,
`#galaxy`, `#fleets`, `#reports`, `#relations` ; liens directs, rechargement et précédent/suivant
sans configuration serveur SPA additionnelle. Destination inconnue : explication et retour Empire.
Pas de dépendance de routage ou d’état global pour ces sept sections statiques.

`src/App.tsx` compose le shell et les vues en préparation. `components/ui.tsx` contient Button,
Badge, Panel et EmptyState, utilisés dans les écrans. `hooks/useReadiness.ts` garde le contrat réseau
séparé du rendu. Pas de chiffres de démonstration ni de calcul métier navigateur ; les ressources
sont explicitement indisponibles tant qu’il n’y a pas de partie/API métier.

## Réseau

Vite utilise `API_PROXY_TARGET` côté serveur : `http://backend:8000` dans Compose,
`http://localhost:8000` hors Docker. Le navigateur appelle `/api/ready` sur son propre origin ;
pas de CORS permissif ni de secret frontend. Aucune variable `VITE_*` ajoutée.

Checking/connected/unavailable : le succès exige HTTP réussi et JSON `{status: "ready"}`. Timeout
5 secondes, annulation au démontage, réponse tardive ignorée. Retry manuel désactivé pendant la
requête. Le statut reste visible sur toutes les sections ; le bouton est dans Empire. Il mesure
API + PostgreSQL au dernier contrôle, pas la progression du worker ni une connexion temps réel.
Aucun polling, cache, mutation ou indicateur simulé. La navigation reste disponible en cas d’erreur.

## Navigation et qualité

Sidebar desktop, barre basse et divulgation « Plus » jusqu’à 800 px. Pas de modal : pas de focus
piégé, Échap replie les sections secondaires et rend le focus au bouton. Après navigation, focus
sur le titre h1 ; lien d’évitement vers main. Les choix sont provisoires pour Q15, carte tactile future.

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Vitest cible `src/**/*.test.{ts,tsx}` ; Playwright cible `e2e/`. Les tests Chromium utilisent une
réponse readiness interceptée pour valider UI/navigation/clavier et largeurs 320/390/768/1440.
La CI Compose conserve la vérification HTTP réelle API/PostgreSQL/proxy et panne/reprise.
Le serveur Vite de Compose reste réservé au développement ; pas de déploiement de production.

## Références

- [Architecture](architecture.md) · [Design system](../02-ux-ui/design-system.md)
- [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Colony Étape 5A

ColonyView réserve quatre sous-sections avec navigation native #colony/<vue>, sélection globale
Colonie conservée, état explicite sans univers/colonie. Aucune requête d’API métier, donnée de démo
ou mutation. Les scénarios Playwright existants couvrent aussi Défense, liens directs et clavier.
La défense reste un système futur. Le domaine interne ne rend pas le frontend interactif en 5A.

## Parcours cible compte/parties — décision validée, future

Landing publique → inscription/login → compte/lobby/liste des parties → créer/rejoindre → sélectionner
Universe → Game UI. Compte global multi-parties, handoff vers session Game autonome. L’application
actuelle est le shell Game ; elle n’implémente ni ces écrans Portal ni une authentification.
L’API/UI Colony interactive est désormais 5D après contrats 5B et fondation 5C selon cadrage.
