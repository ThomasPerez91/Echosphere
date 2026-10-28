# Frontend

**Statut : bootstrap implémenté.**


React + TypeScript strict + Vite. `src/App.tsx` affiche le titre et teste la disponibilité complète
via `/api/ready`. États checking/connected/unavailable, délai de 5 secondes, annulation au démontage
et bouton de nouvelle vérification. Aucune formule métier et aucune ressource fictive affichée.

## Configuration réseau

Vite utilise `API_PROXY_TARGET` côté serveur : `http://backend:8000` dans Compose,
`http://localhost:8000` hors Docker. Le navigateur appelle son propre origin ; pas de CORS permissif
à ajouter. La variable n'est pas une variable `VITE_*` compilée dans le navigateur.

## Évolution

Introduire navigation, cache de requêtes ou état global lorsque les écrans le justifient.
Organiser les features autour des domaines, garder contrats et vues distincts. Aucun calcul critique
côté navigateur ; les compteurs et simulations visuelles sont indicatifs. Réconcilier les mutations
avec l'état confirmé du serveur.

Lint ESLint, build `tsc -b && vite build`, tests Vitest/jsdom et Testing Library. Le serveur Vite de
Compose est réservé au développement. Le build vérifié n'est pas servi en production dans cette étape.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
