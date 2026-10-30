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
- Même DoD pour ChatGPT Work, Codex et Claude Code ; bloc « Reprise rapide » de progress à jour.

## Revue croisée

Quand une revue est demandée : SHA relu noté, anomalies prouvées et classées publiées dans la PR,
réponses confirmée/contestée/hors lot, corrections suivies des tests relancés et de la CI du nouveau
SHA, puis validation du relecteur sur ce SHA. Aucune Bloquante/Majeure ouverte sans arbitrage
utilisateur. Procédure : [protocole de collaboration](../06-handoff/work-codex-handoff.md).

## Passation documentaire historique PR #5

Même branche #5 si état attendu, pas de nouveau code/migration/game_data/dépendance/Compose/test.
Sources et accès partiels qualifiés, pas de conversation privée publiée. Références canoniques,
index des décisions, ADR 0008, Q01–Q39 préservées/Q40–Q56 ouvertes, lecture Work/Codex et prochain
point de reprise cohérents. Check liens/index et diff autorisé ; CI réelle de tête observée.
PR mise à jour et laissée non fusionnée. WSL2/protection DDoS non revendiqués comme testés.

## Étape 5D — API Colony sécurisée et UI

Routes authentifiées par GameSession, autorisées par GameAccess/EmpireBinding/permission dans la
transaction, sans appel Portal ; règles déléguées aux services 5A, sans recalcul HTTP/React.
Idempotence, concurrence, Q39 et sessions testées sur PostgreSQL ; UI réelle sans donnée fictive,
mutations explicites uniques, clavier et 320/390/768/1440 vérifiés dans le viewport. Recette réelle
boucle jouable + Portal coupé, suites/smokes et CI du SHA publiés ; aucune migration ou création
de partie produit implicite. Fusion sur instruction seulement ; étape 6 non commencée.

## Étape 5C — comptes/lobby et accès

Comptes/MFA/sessions, opérations sensibles et outboxes testés sur Accounts dédiés ; séparation
Game/Accounts effective, contrôles mTLS et idempotence prouvés. Ticket signé court/unique, pré-auth
et sessions Game locales bornées, activité explicite et révocations sans résurrection ; jeux de
clés en recouvrement/retrait testés. Parcours UI réels, mobile/clavier, erreurs/expiration, aucun
secret navigateur ni fausse partie ; statuts pending/acknowledged véridiques.

Deux chaînes Alembic sans dérive et ancien historique immuable ; suites des deux backends et
frontends, quatre smokes et CI du SHA publié effectivement observés. Recette Portal arrêté avec
session Game utilisable et worker en progrès, révocation persistée livrée après reprise ; restauration
des deux DB dans des bases de test isolées. Clôture locale pour revue ≠ feu vert production : reports
Q48/Q49/Q55, charge/restauration opérationnelle/rotation des secrets restent explicites. Pas d’API
Colony 5D ni de merge/déploiement sans instruction distincte. Preuves dans progress/PR ; aucune
revue indépendante simulée par l’auteur du lot.

## Étape 5B — contrats documentaires

Décisions validées et provenance dans identity-contracts ; Q40–Q56 distinguent contrats clos,
détails délégués et reports explicites Q48/Q49/Q55. Q01–Q39 conservées, seul cadrage Q16 actualisé.
ADR 0008, sécurité, API, modèle, roadmap et reprise cohérents, sans propositions obsolètes présentées
comme questions produit courantes. Corrections MFA/sessions configurables/CORS préservées.
Diff documentaire et unique ajout REQUIRED de check_docs.py, sans implémentation 5C/5D.
Check documentaire/liens, diff/confidentialité et CI de la tête publiée observée ; aucun test futur
présenté comme passé. Sortie 5B atteinte et intégrée via PR #6 (`63bb7d1`) ; contrats toujours
non implémentés. La réalisation de 5C relève de son lot autorisé et de ses validations propres.

## Étape 5A

PR #4 intégrée et CI master verte avant la branche. Ruleset réel strict, niveaux 1–5 et >5,
arrondis/représentation et vitesses par instance testés. Secteurs, unicité, file, réservation,
annulation, concurrence/idempotence, crash/reprise, bonus et stockage testés avec PostgreSQL.
0004 additive, roundtrip vide, refus peuplé et absence de dérive ; Docker contient les données.
UI Colony quatre sous-sections responsive/clavier sans fausse partie. Défense documentée seulement,
Q30–Q39 ouvertes ; aucune API gameplay, faux user, Combat ou défense active. PR vers master non fusionnée.

## Étape 4

Shell aux largeurs 320/390/768/1440, navigation clavier, focus, historique et liens directs vérifiés.
Readiness : chargement, échec, timeout, réponse invalide/tardive, démontage et reprise. Aucun stock
fictif ou ordre de jeu. Lint/tests/build/docs et tests navigateur en CI ; recette visuelle des captures.
Limites tactiles, lecteur d’écran réel et WSL2 signalées. Q15 reste ouverte pour validation produit.

## Étapes 1–2

Configuration validée, sondes compatibles, sessions et transactions explicites. Modèles/migration
cohérents, contraintes cross-universe et unicité vérifiées sur PostgreSQL réel, migration réversible
sur base jetable et absence de dérive ORM. Aucun endpoint métier non autorisé. context.md/progress.md
à jour ; branches de travail depuis master, PR/CI vers master ; tags/releases identifiées plus tard.

## Étape 3

Horloge injectable, calcul exact stable à la fréquence de lecture, production segmentée aux dates
logiques. Ordre/verrou par colonie, reprises avant/après commit et isolation des workers vérifiés sur
PostgreSQL. Pas d'avancement au-delà d'une échéance bloquée ou du budget de rattrapage. Retry borné,
diagnostic sans payload sensible et relance explicite. Migrations et runtime Compose vérifiés.
Décisions Q03/Q13 cadrées sans fermer les paramètres métier ou le multi-agrégat. Aucun nouvel endpoint
public non protégé. PR #2 fusionnée sur master avant la correction de PR #3.

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
