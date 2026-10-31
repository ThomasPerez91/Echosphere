# Étape 7 — Galaxie procédurale, exploration et connaissance

**Statut au 31/10/2026 : G00–G10 réalisés sur PR #10 (G03–G10 repris et terminés par Claude Code après le travail local Codex) ; Q06 et Exploration validées avec amendements ; aucun merge.**
Instruction utilisateur : commencer effectivement étape 7, présenter Q06 + Exploration minimale,
puis attendre validation avant générateur/game_data définitifs, migration ou métier Exploration.
Aucun code métier livré par G00/G01. Étape 8 System View non commencée.

Branche unique `work/step-7-galaxy-exploration`, unique [PR #10](https://github.com/ThomasPerez91/Echosphere/pull/10)
en brouillon vers master. Base `437844e4427122a1b8d0387271b5354deadfbe2e`, fusion #9 Research ;
CI post-merge [41152760101](https://github.com/ThomasPerez91/Echosphere/actions/runs/41152760101)
completed/success, cinq jobs effectivement vérifiés. G00 `aa9e259be7496faf3109542712daf68f019612e2`
commité/poussé avant G01. Aucune fusion, suppression de branche, release ou déploiement autorisé.

Références canoniques proposées : [Q06 complète](../01-game-design/galaxy.md#proposition-q06--g01-31102026-en-attente-de-validation),
[Exploration minimale](../01-game-design/exploration.md#proposition-exploration-minimale--g01-31102026).
Q06 close produit dans la portée étape 7 ; Q08 déjà close n’est pas rouverte. Q04/Q07/Q09 gardent leurs sujets différés.

## Plan et critères de sortie

Les tickets G02–G10 sont **autorisés sans confirmation par ticket** après CI préalable 5/5 verte
sur Ubuntu 24.04. Arrêt si contraintes non robustement satisfaisables ou nouvelle décision produit.

| Ticket | Périmètre | Vérification requise et statut |
| --- | --- | --- |
| G00 | Fetch/master ff-only, branche courte, statuts Research historiques et checkpoint poussé | Réalisé ; arbre initial propre, aucune perte locale, post-merge #9 5/5 success |
| G01 | Audit du dépôt, proposition Q06 et engagement Exploration sans Fleet, plan durable | Cadrage publié puis validé explicitement avec amendements ; CI préalable requise |
| G02 | Générateur pur versionné et données strictes ; profil proposé 40 systèmes, bornes 30–50 | Déterminisme canonique/golden fixtures, seeds différentes, connexité/degrés/ponts/distances, géométrie, capacités et métriques d’équité ; aucun résultat revendiqué aujourd’hui ; **Réalisé : 1 000/1 000 standard, 4 × 100 bords, aucun assouplissement (progress)** |
| G03 | Manifeste, positions/routes/mondes/sites et commande explicite de génération ; migration additive | PostgreSQL scopes/contraintes, génération atomique/rejeu/refus de remplacement, ancien Universe inchangé, upgrade/check/roundtrip et refus de downgrade peuplé ; **Réalisé : migration 0008, génération explicite/atomique, rejeu/refus, génération concurrente unique, downgrade protégé** |
| G04 | Knowledge Empire typée et observations datées ; initialisation limitée explicite | UNKNOWN absent, DETECTED approximatif sans détail, MAPPED durable, MONITORED limité puis retour MAPPED, snapshots de rapport et non-partage ; **Réalisé : Knowledge typée, CHECK de structure, non-fuite exhaustive testée, MONITORED → MAPPED** |
| G05 | Exploration indépendante de Fleet, réservation/snapshot/stream/handler | Rattrapage, coût exact, capacité unique, crash/retry/rejeu, application unique et découverte atomique ; aucun autre scheduler ; **Réalisé : coût/durée/capacité/idempotence/concurrence, handler unique, corruption snapshot et chemin** |
| G06 | API Game sous GameSession et permissions explicites, contrat/Portal/CHECK/migration | Chaîne d’autorisation, CSRF, droits distincts, accès direct UNKNOWN indistinguable de l’inexistant, deux participants/Empires/Universes ; **Réalisé : routes Game, 9 permissions propagées (Game/schéma/Portal/CHECK), refus 401/403/404/409** |
| G07 | Galaxy SVG/HTML réelle et liste équivalente dans le shell existant | Pan/zoom, sélection tactile/clavier, légende textuelle, panneau de connaissance et mission datée ; aucune fixture runtime, aucune System View étape 8 ; **Réalisé : carte SVG/HTML connectée, liste, détail, devis, confirmation, missions/rapports** |
| G08 | Concurrence, non-fuite, responsive/accessibilité | 320/390/768/1440, focus/zoom/pan/détail adaptatif, courses lectures/worker/participants/dépenses/révocation, erreurs/logs sans secrets cachés ; **Réalisé : Chromium 320/390/768/1440, clavier/touch/pan/zoom, StrictMode, réponses tardives, courses** |
| G09 | Recette HTTPS réelle sur projet/bases/volumes jetables *_test | Login/handoff, carte limitée, lancement/page fermée, redémarrage worker, découverte observée en base avant réouverture, Portal arrêté/session encore valide, expiration sans arrêt de mission ; **Réalisé : smoke_galaxy_compose réel, preuve DB avant réouverture, Portal coupé, expiration** |
| G10 | Relecture complète, régressions Colony/Research, docs/passation et CI exacte | Tests requis réellement exécutés, CI finale verte, PR Ready après livraison réelle ; attendre instruction distincte de merge ; **Réalisé : revue complète, corrections, docs/passation ; Ready après CI 5/5, merge non autorisé** |

## Audit technique sur master 437844e4

Lecture de conception, pas audit exhaustif de sécurité ni nouvelle recette runtime.
Les emplacements suivants sont ceux du SHA de base ; utiliser les noms de fonctions après évolution.

| Constat vérifié dans le code | Conséquence pour étape 7 |
| --- | --- |
| `backend/app/persistence/models.py:40–91` : Universe seed sans version générateur, StellarSystem sans position, Planet capacités explicites | Ajouter le manifeste et les routes/positions ; ne pas confondre tables existantes et galaxie générée |
| `backend/app/persistence/models.py:93` : Colony FK Empire/Planet/Universe, unicité planète | Réutiliser le financement et les scopes ; ne pas définir la colonisation/occupation historique Q07 |
| `backend/app/simulation/models.py:21,78` : stream générique et ScheduledEvent à FK composites | Adaptateur Exploration typé ; aucun colony_id ajouté à ScheduledEvent |
| `backend/app/simulation/scheduler.py:53,139` : stream lock, SAVEPOINT, retry/blocked et SKIP LOCKED | Handler transactionnel mono-stream, reprise existante ; pas de bail/scheduler parallèle |
| `backend/app/simulation/service.py:154` : TimeEngine compose les trois handlers actuels | Enregistrer EXPLORATION_COMPLETE dans cette composition, utilisée par API et worker |
| `backend/app/research/service.py:60,240,290` : initialisation Empire, Research avant source Colony, snapshot puis handler sans débit | Financement Exploration suit le même invariant et conserve Research → Colony ; ne pas copier un lock Colony vers le handler de fin |
| `backend/app/access/service.py:253` : GameSessions.locked verrouille GamePrincipal puis vérifie état/epochs/échéances | Même transaction autorisation/révocation/acceptation ; aucun appel Portal par commande |
| `backend/app/colony/api.py:50,168,183` et `backend/app/research/api.py:30` : bootstrap/command stricts et erreurs génériques | Réutiliser ces protections et extraire un helper partagé si utile, sans dépendance métier Galaxy→Colony HTTP |
| `backend/app/control/contracts.py`, `models.py`, schéma privé v1, Portal `control/service.py` : allowlists et CHECK JSON explicites | Ajouter galaxy.read/exploration.read/start dans toutes les couches et tests ; aucun backfill des grants |
| `frontend/src/App.tsx` : Galaxy placeholder ; `hooks/useResearch.ts` : intentions, abort/générations, échéances passives | Écran réel seulement G07, sélection d’Empire indépendante de la colonie, aucune mutation au montage ni calcul métier React |

Migrations inspectées : inventaire Game 0001–0007 ; lecture des fondations, du scope générique et
de 0007 Research (CHECK permissions et refus de downgrade). Aucune migration modifiée ici.
Tests PostgreSQL inspectés : conftest (RUN_DB_TESTS et nom *_test), test_world (scopes et roundtrip),
scénarios Research/Colony API (coûts, concurrence, clés membership, deux participants, workers,
corruption et grants/downgrade). Leurs résultats passés ne prouvent aucune future table Galaxy.

Risques concrets à traiter dans les tickets :

- `initialize_colony` ne sait initialiser que la référence ; ne pas l’utiliser sur une planète
  ordinaire variable. Les sites de départ proposent précisément un monde 12/2.
- Le générateur doit comparer des sorties logiques, pas des UUID SQL/date runtime ; ne pas exposer
  des indices séquentiels, seed, digest global, compte total ou slots réservés dans les DTO Galaxy.
- Interroger Knowledge autorisée d’abord ; une jointure vers des données structurelles doit être
  bornée par cette connaissance. Observations/rapports ne relisent jamais le dynamique réel caché.
- Les premières initialisations de streams prennent actuellement Empire : créer explicitement les
  adaptateurs nécessaires avant toute prise de stream lors du provisionnement étape 7 ; tester
  l’interleaving première lecture Research/commande Exploration, sans ordre de locks inversé.
- La grille visuelle DETECTED ne constitue pas le chemin gameplay ; plusieurs marqueurs peuvent
  partager une position approximative sans que l’API fournisse leurs positions exactes pour les séparer.
- Les contraintes Q06 conjointes peuvent exiger de revoir les seuils après mesure multi-seeds :
  tout assouplissement de critère produit doit revenir à l’utilisateur, jamais fallback silencieux.

## Schéma préparatoire, non migration définitive

Noms et répartition indicatifs ; contraintes exactes à finaliser après validation, pas de DDL ici.

| Relation proposée | Intégrité/autorité attendues |
| --- | --- |
| UniverseGalaxy | 1/Universe ; manifeste seed/version/paramètres/snapshot/empreinte ; état validé publié atomiquement, immutable |
| GalaxySystem placement | Extension liée à StellarSystem et Universe ; index logique local unique/Universe, positions entières ; anciens systèmes non peuplés automatiquement |
| GalaxyRoute | Universe, deux systèmes existants par FK composites ; endpoints canoniquement ordonnés, distincts et paire unique ; graphe non orienté |
| GeneratedPlanet / position orbitale | Planet existante liée au bon système/Universe, ordinal local unique ; aucune planète-colonie automatique |
| GalaxyStartingSite | Système et planète cohérents par FK composites ; allocation explicite ultérieure, pas d’Empire fabriqué |
| EmpireExploration | Empire/Universe/stream uniques et cohérents ; capacité et séquence d’intentions, stream dédié à Knowledge/Exploration |
| SystemKnowledge | Empire/Universe/System, état canonique hors UNKNOWN implicite, discovered_at/structure_known_at/last_seen_at, position approximative snapshotée ; pas de fog global sur System |
| RouteKnowledge / PlanetKnowledge | Relations typées par Empire/Universe et parent connu ; aucune route publiée sans deux extrémités connues, aucune planète publiée pour DETECTED |
| SystemObservation | Dernière observation dynamique autorisée, datée et conservée ; snapshots bornés, aucune copie JSON géante de galaxie |
| ExplorationMission / chemin ordonné | Source Colony et Empire/Universe, destination, route/système de chaque saut via FK ; snapshot de coût/durée/règles et engagement, clé membership/intention unique et index partiel 1 active/Empire |
| ExplorationReport / découvertes | 1 rapport/mission, FK au scope Empire/Universe ; références et observations découvertes typées, réponse limitée aux connaissances autorisées |

Deux migrations additives possibles : monde/connaissance puis missions/permissions ; numéro à choisir
sur la chaîne réelle à G03/G06. Aucune réécriture 0001–0007, migration automatique de galaxie ou
downgrade supprimant du gameplay. Ajouter les imports metadata, inventaires de tables et recettes
associés ; tester upgrade répété, absence de dérive, retour à vide et refus avant DDL si état/grants.
Pas de migration Accounts anticipée sans besoin réel ; permissions transportées explicitement.

Provisionnement Game interne explicite d’un Universe neuf, puis véritable Empire/colonie et ses
connaissances : services appelables par opérateur/test/headless, pas un endpoint public create/join.
Le droit de générer n’appartient pas à exploration.start. Recette avec identités réelles via contrôle
mTLS/handoff ; fixtures uniquement dans scripts/tests avec garde *_test. Anciennes parties :
message indisponible fidèle, aucune adoption v0.3 à la lecture ou au démarrage.

## APIs et UI proposées après validation

Reprendre les préfixes réels `/game/{universe_id}` (proxy navigateur `/api/game/...`). Sélection
Empire explicite comme Research, sans supposer le premier binding ou l’Empire de la top bar Colony.

| Route relative proposée | Projection autorisée |
| --- | --- |
| GET `/galaxy` | Empires avec galaxy.read, aucun inventaire omniscient |
| GET `/galaxy/{empire_id}` | Systèmes/routes connus uniquement, états/datations et devis autorisés |
| GET `/galaxy/{empire_id}/systems/{system_id}` | Petit panneau de connaissance, détail selon état ; pas la System View étape 8 |
| GET `/exploration/{empire_id}/missions` | Missions/rapports de l’Empire avec exploration.read |
| POST `/exploration/{empire_id}/missions` | Intention + source Colony + destination explicites, chemin/devis recalculés serveur ; droits selon contrat proposé |

Pas d’endpoint de rappel avant arbitrage. Pagination/compteurs bornés aux seules données connues ;
404 identique pour UNKNOWN/absent/étranger, logs publics génériques, erreurs de validation sans
objets SQL ou snapshot caché. Permissions/révocations/CSRF/bootstrap et no-store comme Research.
Les réponses n’envoient ni carte entière filtrée par React, ni layout omniscient/minimap globale.

Références examinées : design-system.png et galaxy-map.png ; fond navy, routes discrètes, nœuds
identifiables autrement que par couleur, panneau latéral desktop et détail sous carte sur mobile.
SVG + HTML, commandes zoom/recentrage accessibles, liste textuelle équivalente, focus conservé,
pan tactile dans la carte sans capturer le défilement global. Les noms/filtres/présences/territoires
illustratifs du mockup ne créent aucune mécanique ou donnée runtime.

## Matrice de validation à réaliser G02–G10

- Générateur : mêmes entrées complètes/sortie stricte ; seeds distinctes, chaînes Unicode, bornes,
  versions et données modifiées ; sorties stables inter-processus ; 1 000 seeds fixes pour le profil standard 40/4 (0 échec), puis au moins 100 seeds pour chacun
  des bords 30/1, 30/4, 50/1, 50/4 ; métriques et échecs explicitement comptés.
  Tous les succès satisfont chaque invariant ; ne pas ignorer les seeds difficiles pour déclarer
  l’équité. Mesurer temps/échecs avant d’affirmer la robustesse du profil.
- Persistance : routes sans doublon/self-loop/cross-Universe, parent planète cohérent, scopes de
  Knowledge/chemin/rapport, deux générations concurrentes, interruption avant commit, même
  intention rejouée, paramètres contradictoires refusés et évolution du code sans changement ancien.
- Fog : UNKNOWN absent y compris metadata/logs/erreurs, ID direct invisible, DETECTED sans nom/
  coordonnée exacte/planète, routes limitées, MAPPED durable, monitoring retiré avec last_seen_at,
  observation périmée ne remplaçant pas une plus fraîche et ancien rapport sans enrichissement live.
- Autorisation : autre Empire/Universe/compte, aucun binding, permission absente, lecture seule,
  admin plateforme sans droit ; session expirée/révoquée/suspendue ; ancien grant sans nouveaux
  droits, enveloppes CSRF/origine/query strictes et concurrence d’acceptation/révocation.
- Exploration : cible UNKNOWN/inaccessible/déjà cartographiée, source étrangère, chemin connu
  uniquement, débit/slot uniques, même clé même contenu et conflit, intention différente concurrente,
  dépenses Colony/Research concurrentes, deux participants même Empire et deux Empires indépendants.
- Temps : page fermée, redémarrage worker, deux workers, crash/rollback d’application, retry après
  réponse perdue/commit, résultat une fois et découverte atomique, lecture concomitante à échéance,
  répétition de découverte monotone, handler corrompu sans effet partiel, observation datée logiquement.
- UI : API interceptée pour layouts distincte de recette réelle ; quatre largeurs, clavier/liste/
  touch targets, erreurs/retry même intention, absence de mutation StrictMode, course de scope et
  échéances sans faux achèvement client, aucun maintien de session par polling.
- G09 : vrai login/handoff, carte limitée, coût observé, navigateur fermé, worker redémarré et
  rapport/base avant réouverture ; Portal API/contrôle arrêtés puis nouvelle commande avec session
  valide, page fermée jusqu’à découverte ; expiration bloque la commande suivante sans arrêter
  l’expédition acceptée. Projet isolé et bases/volumes jetables, aucun volume conservé touché.
- Régressions : suites Game PostgreSQL, Portal si contrat/permissions touchés, Alembic, lint/tests/
  build/Chromium frontend, docs/liens/diff, smokes Game/Portal/control/handoff/Colony/Research et
  nouveau smoke Galaxy/Exploration. Résultats chiffrés seulement après exécution/CI du SHA concerné.

## Lectures et état réel du checkpoint G01

Lus : AGENTS, CLAUDE, context, progress, index docs, passation/protocole, roadmap/registre,
galaxy/exploration/fog/planets/core-loop/progression/balance, data-model/event-engine/security,
ADR 0002/0004–0008 et index ; contrats techniques Colony/Research, modèles, migrations et tests
PostgreSQL pertinents, protections HTTP/permissions et patterns UI. Guide visuel lu et deux PNG
examinés. Aucun document externe nécessaire pour cet état des lieux interne.

Validation présente : checks documentaires/liens et git diff --check avant publication ; aucune
suite fonctionnelle locale, prototype générateur, simulation multi-seeds, migration, test tactile
ou nouvelle recette Docker exécutés pour G00/G01. Environnement hôte identifié WSL2 par uname ;
cela ne prouve pas une recette de la pile. Le résultat de CI propre à la tête est dans PR #10.

Arrêt demandé : valider/amender Q06 et le contrat Exploration ; après réponse, consigner la
provenance dans leurs canoniques/registre puis G02. Ni Fleet, ni étape 8, ni autres lots anticipés.

## Validation utilisateur et amendements — 31/10/2026

Q06/Exploration closes produit, non encore implémentées. Sites candidats : 4 par défaut, 1–4,
aucune réservation gameplay ni création/affectation multi-Empires. Corpus de robustesse 1 000 +
4 × 100 seeds comme ci-dessus ; aucune relaxation silencieuse. Surveillance locale propre sans
timer artificiel. Coût/durée/engagement/permissions/rapport/stream/ruleset v0.3 validés ; Q09 ouverte.
Correctif préalable cfff5be : cinq jobs ubuntu-24.04, Playwright inchangé. Attendre cinq verts
avant code substantiel ; l’arrêt G01 décrit plus haut devient historique depuis cette validation.

## G02 — réalisé, 31/10/2026

Générateur galaxy-v1 et nouveau ruleset complet v0.3 ; anciens fichiers v0.1/v0.2 inchangés.
Corpus requis intégral : 1 000/1 000 standard et 100/100 pour chaque bord, zéro échec ; mesures
et limites dans progress. Script opérateur `PYTHONPATH=backend python3 scripts/measure_galaxy.py`.
Gate indépendante de la construction et tests de corruption, golden/cross-process/variabilité.
Zones initiales aux budgets structurels corrélés égaux, positions/connexions/noms seedés ; aucune
réservation gameplay. G03–G10 restent à réaliser, aucune API/UI livrée par ce ticket.

## G03–G10 — réalisés, 31/10/2026

Travail local Codex non commité (G03–G05, ébauche G06/G07) récupéré, sauvegardé puis audité par
Claude Code ; corrections et compléments consignés dans [progress](../../progress.md). Contrat
technique livré : [Galaxie/Exploration](../03-technical/galaxy-api-ui.md). Les preuves chiffrées
(suites, Chromium, smokes, CI) sont dans progress et sur la PR, pas déduites de ce plan.
