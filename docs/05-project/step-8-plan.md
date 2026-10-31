# Étape 8 — Vue détaillée des systèmes connus

**S00–S09 autorisés le 31/10/2026 sans validation intermédiaire**, sauf véritable arbitrage produit.
Base master `773e05c0971a78719b5ba1d1baca05df3aa7fb12`, étape 7 intégrée via PR #10, CI post-merge
41220568486 success cinq jobs. Branche unique work/step-8-system-view, [PR #11](https://github.com/ThomasPerez91/Echosphere/pull/11) brouillon.
S00 publié avant code : `740dd8d`. Aucun merge autorisé ; étape 9 non commencée.

| Ticket | Travail et preuve attendue |
| --- | --- |
| S00 | Réalisé : master/PR/CI vérifiées, branche propre et checkpoint documentaire poussé |
| S01 | Contrats produit/technique, audit Knowledge/permissions/navigation ; zéro migration retenue |
| S02 | Détail serveur depuis Knowledge, datations/routes/présences propres, aucune complétion au GET |
| S03 | Galaxy → System, deep-links Universe/Empire/System, retour/contexte et Colony autorisée |
| S04 | UI sobre étoile/mondes connus, liste et panneaux datés, aucune donnée illustrative |
| S05 | Responsive 320/390/768/1440, clavier/tactile/focus, liste équivalente et historique |
| S06 | Non-fuite UNKNOWN/DETECTED, scopes/permissions/session, anciennes observations non réenrichies |
| S07 | Tests PostgreSQL, UI/Chromium, lint/build, Alembic et régressions pertinentes |
| S08 | Smoke réel étendu : worker hors page, preuve DB avant détail, Portal coupé/session expirée |
| S09 | Revue/docs/passation, SHA distant et CI exacte, Ready seulement après succès ; aucun merge |

[Contrat produit](../01-game-design/system-view.md), [technique](../03-technical/system-view.md).

## Audit S01 sur 773e05c

SystemKnowledge/PlanetKnowledge conservent déjà toute la structure requise et leurs dates.
RouteKnowledge a deux FK vers la connaissance Empire ; aucun besoin de nouvelle table.
Observation MONITORED = own_colony_ids ; le nom/planète/lien d’une Colony exigent une vérification
actuelle colony.read, sans enrichir les observations MAPPED anciennes.

`Galaxy.read` appelle catch_up avant tout détail actuellement : séparer la branche System View
pour ne pas terminer une Exploration à l’ouverture. Conserver la lecture Galaxy générale.
`service.project_system` lit déjà les snapshots ; l’étendre par composition, sans changer les
rapports Exploration figés ni la projection générale. Aucun credential ou appel Portal ajouté.

Shell à fragments : Galaxy ne reconnaît pas encore de sous-route. Ajouter une route interne
explicite et conserver ses sept destinations. Le retour garde son contexte en mémoire, tandis
que le deep-link demeure autonome après refresh. Le hook Colony sélectionne aujourd’hui la
première colonie : cibler explicitement la vraie Colony du lien et effacer la projection précédente
avant toute lecture de sélection, pour ne pas afficher un ancien scope après refus.

## Validation à exécuter

PostgreSQL : UNKNOWN/étranger/inexistant identiques ; DETECTED minimal ; MAPPED structure copiée,
aucun Planet live supplémentaire ; MONITORED propre/daté ; perte de monitoring et ancien last_seen ;
colony.read présent/absent, aucune colonie étrangère ; binding/session/Universe/Empire/refus/révocation ;
mission due encore active après GET détail, puis worker → MAPPED ; aucune activité session en lecture.

Vitest : états et datations, refus/404/absence de droit, routes et liens, StrictMode GET seulement,
réponses tardives/autre Empire/Universe, navigation et retour. Chromium quatre largeurs : clavier,
tactile, deep-link/refresh/précédent/suivant/focus, sélection et absence de débordement.

Suite Game PostgreSQL complète et Alembic check ; frontend lint/Vitest/build/Chromium ; docs/diff ;
smokes existants conservés en CI et smoke Galaxy/System réel local isolé. Portal inchangé si aucun
contrat modifié : CI complète conservée, aucune nouvelle migration/grant. Captures hors Git.

## Checkpoint S01–S07 — 31/10/2026

Contrats et implémentation réalisés : projection détail sans catch-up, routes Knowledge, présence
propre générique/autorisation Colony séparée, UI et deep-links avec retour/cadrage conservé.
Zéro migration/permission supplémentaire. Validation locale : 275 tests Game PostgreSQL, Ruff et
Alembic check ; 48 Vitest, lint sans erreur (seul warning préexistant useGameSession), build et
4 Chromium System View aux largeurs requises. Captures 320/1440 examinées ; aucun fake runtime.
S08 recette réelle et S09 CI/passation restent à terminer.
