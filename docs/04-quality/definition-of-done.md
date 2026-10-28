# Definition of Done

**Statut : règle de travail.**

## Chaque changement

- Périmètre explicite, pas de feature non documentée ; hypothèses et arbitrages identifiés.
- Règles critiques côté serveur, UTC et PostgreSQL source de vérité.
- Tests pertinents ajoutés/actualisés ; lint, tests et build passent.
- Cas d'échec, reprise et concurrence couverts selon le risque.
- Responsive mobile et desktop, clavier, chargement/erreur vérifiés pour un changement UI.
- Documentation et ADR actualisés si le comportement ou une décision structurelle change.
- Aucun secret, logs sensibles, code généré inutile ou dépendance non justifiée.
- PR compréhensible : comportement final, validation réelle et limites ; pas de merge automatique.

## Étapes 1–2

Configuration validée, sondes compatibles, sessions et transactions explicites. Modèles/migration
cohérents, contraintes cross-universe et unicité vérifiées sur PostgreSQL réel, migration réversible
sur base jetable et absence de dérive ORM. Aucun endpoint métier non autorisé. context.md/progress.md
à jour ; branches de travail et CI ciblent develop, releases réservées à master.

## Étape 0 (historique)

Tous les fichiers demandés existent, liens valides et questions ouvertes centralisées.
README et AGENTS suffisent à reprendre le projet. Frontend placeholder responsive, backend minimal,
.env.example, Dockerfiles, Compose PostgreSQL persistant sans port DB publié et probes présentes.
Qualité backend/frontend et CI disponibles ; commandes WSL2 et URLs documentées.
Les services doivent être vérifiés selon les moyens disponibles et toute absence de test Docker
réel est signalée. Aucun gameplay, auth, Redis, WebSocket ni moteur temporel implémenté.

La livraison distante n'est terminée qu'après publication de la branche et ouverture d'une PR
vers master laissée non fusionnée. Un refus d'accès GitHub doit être rapporté comme blocage ; un
bundle local ne vaut ni push ni PR. La CI configurée n'est pas une CI passée tant qu'elle n'a pas tourné.

Voir [stratégie de tests](testing-strategy.md) et [contribution](../../CONTRIBUTING.md).
