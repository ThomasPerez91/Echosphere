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

## Critères de validation

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

## S08/S09 — recette finale et passation

Recette HTTPS réelle réussie avec les images finales : système propre MONITORED, présence et lien,
retour, Exploration acceptée puis page fermée/redémarrage worker, preuve DB MAPPED avant GET détail,
planètes/capacités comparées exactement à Knowledge ; nouvelle lecture Portal arrêté et refus 401
après expiration. Projet/bases/volumes dédiés supprimés, pile conservée intacte.

Régression finale locale : 50 Vitest et 21 Chromium complets réussis ; 275 Game PostgreSQL,
Ruff/Alembic sans dérive, zéro migration/grant. Correction de réponse Colony tardive couverte par
deux tests. CI exacte et verdict Ready à vérifier après publication, consignés dans la PR ; aucun
merge ni démarrage étape 9. Limites : Chromium émulé, pas de recette sur appareil physique ni de
validation de production. Warning ESLint useGameSession préexistant conservé.

Correction S09 : nowrap hérité des métadonnées neutralisé dans System View ; légende/date
repliables à 320 px, 21 Chromium complets réussis après correction. CI des premières têtes
fonctionnelles frontend KO pour ce défaut ; seul le SHA final vert autorise Ready.

## S10 — revue indépendante Claude Code

Revue de f2688b2 : une Majeure (identifiants Colony émis sans colony.read, Galaxy comprise),
deux Mineures (lien Colony caché par la présélection, nowrap Galaxy à 320 px) et des
cosmétiques, corrigées sur la même branche sans migration. Détail et preuves dans
[progress](../../progress.md) ; CI exacte et verdict dans PR #11. Étape 9 non commencée.
