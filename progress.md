# Progression — Echosphere

Mise à jour : 2026-10-31. [Contexte](context.md), [passation](docs/06-handoff/README.md).

## Reprise rapide

| Champ | État au 31/10/2026 — S01–S07 |
| --- | --- |
| Objectif | Étape 8 System View : projection depuis Knowledge existante, sans nouvelle mécanique |
| Branche / base / PR | work/step-8-system-view ; PR #11 brouillon ; master 773e05c0971a78719b5ba1d1baca05df3aa7fb12 |
| Tête | S00 740dd8dd888ce8c32c771283e7afa238edbca710 publié avant code ; présent commit = checkpoint S01–S07 |
| Agent | Codex local, seul écrivain autorisé ; précédent travail étape 7 consigné Claude Code |
| Réalisé | Contrats/plan, projection détail sans rattrapage/avancement de stream, routes Knowledge et observations datées, liens propres colony.read ; UI interne Galaxy, retour/cadrage, deep-link Colony ciblé |
| Fichiers | app/galaxy/system_view.py et api.py, composants/hooks/client/navigation/CSS/tests UI ; nouveau test_system_view.py ; trois docs canoniques et smoke Galaxy étendu |
| Validation locale | PostgreSQL dédiée echosphere_system_test : 275 Game réussis, dont 10 System View ; Ruff et Alembic sans dérive ; frontend lint 0 erreur (warning préexistant useGameSession), 50 Vitest, build, 21 Chromium dont 4 System View 320/390/768/1440 ; captures 320/1440 examinées |
| CI | Post-merge 41220568486 success 5/5 vérifié ; CI de ce checkpoint à observer après publication |
| Limites / suite | S08 recette HTTPS réelle et régressions Chromium complètes puis S09 revue/CI/passation ; Portal inchangé ; zéro migration/grant/game_data ; étape 9 non commencée ; aucun merge |

## S07/S08 — renforcement de reprise, 31/10/2026

Relecture : une sélection Colony doit invalider aussi la génération des lectures précédentes,
pas seulement leur AbortController. Correction ciblée et deux tests réussis : deep-link vers une
autre colonie et refus 404, ancienne réponse reçue ensuite ignorée. Frontend : 50 Vitest/build/lint
réussis ; 21 Chromium complets réussis (dont 4 System View). Le test backend de permissions a été
renforcé avec une nouvelle session valide au nouvel epoch, pour distinguer refus d’accès et simple
session révoquée : 10 System View réussis après correction du ticket de test (epoch initial erroné).
Aucun défaut runtime d’autorisation démontré par cet échec de fixture.

Première recette locale HTTPS Galaxy/System réussie : connaissance propre/lien, planètes comparées
à Knowledge, page fermée et preuve DB avant nouvelle vue, Portal arrêté et refus 401 détail ; projet
jetable supprimé. Nouvelle image finale et recette en cours pour inclure le dernier correctif Colony.
CI de tête fonctionnelle 67345aa en cours ; aucun Ready ni succès CI final présumé.

## S01–S07 — projection, navigation et UI System View, 31/10/2026

Audit des modèles Knowledge/API/fog/permissions, docs/ADR et références visuelles demandé effectué.
Schéma existant suffisant, zéro migration. Nouveau contrat métier/technique et plan S00–S09.
GET détail sépare l’accès System View du catch_up Galaxy : sous stream verrouillé, lecture des
snapshots autorisés seulement ; test prouve qu’une mission échue reste active sans rapport jusqu’au
worker et que le curseur n’avance pas. Refresh monitoring existant conservé. DETECTED minimal,
UNKNOWN/étranger/absent 404 identique, anciennes observations conservées sans enrichissement live.
Liens Colony : uniquement observation actuelle + colony.read + colonie propre dans planète connue ;
sinon présence générique, aucun détail Colony ajouté. Routes depuis Knowledge du même Empire.

Sous-route native Galaxy Universe/Empire/System, aucun huitième domaine. SVG illustratif avec
liste équivalente, sélection/clavier/tactile, dates complètes et panneaux empilés mobile. Retour
conservant Empire/sélection/cadrage en mémoire ; deep-links autonomes après reload/historique.
Le lien Colony sélectionne explicitement la bonne colonie, et une sélection efface l’ancien scope
avant lecture pour éviter une ancienne projection après refus. Aucun POST au montage System View.

Validation réellement exécutée en conteneurs isolés : 275 Game PostgreSQL / Ruff / Alembic check,
48 Vitest, lint sans erreur, build, 4 Chromium spécifiques dont historique/refresh/focus/tactile et
absence de débordement. Pas de nouvelle suite Portal locale (code inchangé). Recette réelle S08
et CI finale non encore obtenues à ce checkpoint, aucune clôture S09 revendiquée.

## S00 — synchronisation après fusion étape 7, 31/10/2026

GitHub réel vérifié : #10 MERGED, tête 1bcb2ba, merge master 773e05c, CI post-merge
41220568486 success cinq jobs. Local propre et synchronisé, master ff-only puis création de
work/step-8-system-view, sans réutiliser la branche fusionnée. Aucun travail local non publié.
Premier checkpoint documentaire avant toute implémentation substantielle étape 8.

## Checkpoints étape 7 avant fusion (historiques)

### Ancienne reprise rapide étape 7

| Champ | État au 31/10/2026 — étape 7 G02–G10 réalisés, PR #10 |
| --- | --- |
| Branche / base / PR | work/step-7-galaxy-exploration ; PR #10 ; master 437844e4 ; aucun merge |
| Tête | Tête fonctionnelle 53a7657 ; ce commit ne modifie que progress, sa CI est à relire sur PR #10 |
| Agent | Claude Code local (WSL2), écrivain unique depuis la reprise du travail local Codex |
| Réalisé | G03 persistance/migration 0008, G04 Knowledge, G05 Exploration, G06 API/permissions, G07 UI Galaxie, G08 hardening, G09 smoke réel, G10 revue/docs |
| Validation locale | PostgreSQL 17 jetables : 265 Game (dont 20 Galaxy), 123 Portal ; ruff ; frontend lint 0 erreur, 37 Vitest (aussi sous 0,3 CPU), build, 17 Chromium (Galaxy ×4 largeurs) ; smokes Galaxy, Colony et Research réels réussis |
| CI | a3e7187 4/5 et acf5eb2 push 4/5 : frontend KO, timeouts jsdom sur runner lent (corrigé globalement) ; e307175 PR 5/5 ; **53a7657 push 41195739026 et PR 41195743056 : 5/5 success**, smoke Galaxy réussi en CI |
| Limites | Smokes Compose sur projet par défaut (smoke_compose/portal/control/handoff) vérifiés par CI seulement, pour ne pas toucher la pile locale existante ; noms générés provisoires ; Q09 ouverte ; étape 8 non commencée |
| Suite | PR #10 Ready for review ; attendre une autorisation explicite de merge ; étape 8 non commencée |

## G07–G10 — UI, hardening, recette réelle et revue, 31/10/2026

G07 : écran Galaxie branché dans le shell (remplace le placeholder), client API validant strictement
la non-fuite (DETECTED sans structure, aucune référence orpheline), hook `useGalaxy` (générations,
abort, clé conservée après résultat inconnu, relectures bornées à l’échéance), carte SVG + HTML
(pan pointeur/tactile limité à la carte, zoom molette/boutons/clavier, recentrage, nœuds
focusables), liste textuelle équivalente, détail par état, devis serveur, confirmation irrévocable,
missions/rapports. L’ébauche Codex a été conservée dans l’historique (a3e7187) puis remplacée.

G08 : Vitest (StrictMode sans commande, sélection clavier/commande CSRF unique, même clé après
résultat inconnu et nouvelle clé après refus, 401, réponse tardive d’un autre Empire, validateur
anti-fuite) et Chromium 320/390/768/1440 (clavier, pan souris/tactile CDP sans défilement de page,
molette, cibles ≥ 44 px, liste, dialogue/Escape/focus, pas de défilement horizontal). Revue visuelle
des captures : marqueurs DETECTED d’une même cellule écartés pour éviter le chevauchement.
Côté serveur, les courses/participants/Universes/expiration/corruption sont couverts par G03–G06.

G09 : `scripts/smoke_galaxy_compose.py` + `galaxy_game_fixture.py` + `galaxy_browser.mjs`, ajoutés
à la CI. Exécution locale réelle réussie : carte limitée à 4 systèmes connus sur 40, débit exact,
page fermée, redémarrage du worker, mission completed/MAPPED/rapport observés **en base avant
réouverture**, Portal API/contrôle arrêtés, nouvelle expédition terminée page fermée, zéro requête
Portal, puis expiration → 401 sur lecture et commande alors que l’expédition acceptée juste avant
se termine. Projet/volumes jetables supprimés. Smokes Colony et Research locaux réussis ; en CI
(53a7657), les sept smokes dont Galaxy sont verts.

G10 : revue complète du diff (migration, modèle, générateur non modifié, Knowledge, non-fuite,
Exploration, permissions, locks, UI, tests, docs). Anomalies corrigées listées dans l’entrée de
reprise ci-dessous et dans les commits ; test Research Vitest rendu robuste au runner lent (même
assertion). Docs : [contrat technique](docs/03-technical/galaxy-api-ui.md), plan, canoniques
Galaxie/Exploration/Fog, modèle, temps, contrôle Portal/Game, index et passation.

## Reprise Claude Code — récupération Codex et revue G03–G06, 31/10/2026 (checkpoint 603646c/a3e7187)

État trouvé : branche à jour avec origin (e5d51ae), aucune divergence ni commit local, mais
modifications Codex non commitées : app/galaxy (models, world, service, api), migration 0008,
tests d’intégration Galaxy, propagation des permissions (Game, schéma, Portal, CHECK), TimeEngine,
smokes (révision Alembic) et ébauche frontend non branchée (GalaxyView, galaxy/api.ts).
Ligne de base avant toute correction : ruff OK et 257 tests Game réussis sur PostgreSQL jetable.
Ces éléments n’étaient pas validés avant cette revue ; ils le sont dans les limites ci-dessous.

Anomalies trouvées et corrigées par Claude Code :

- **Majeure** : DTO `Binding` (max_length) et schéma partagé (maxItems) bloqués à 6 droits pour
  9 permissions possibles ; corrigés à 9, schéma toujours égal au modèle Pydantic (test existant).
- **Majeure** : `map_system` flushait MAPPED avant la structure ; révélé par le nouveau CHECK
  `ck_system_knowledge_structure` (DETECTED sans structure, MAPPED/MONITORED avec structure).
- Handler : chemin persistant vérifié (contiguïté source → destination) ; corruption → retry, aucun effet.
- Rapport figé enrichi : chemin, routes incidentes révélées, voisins (approximatifs, `new`).
- `colony_id` des missions masqué sans colony.read (comme Research) ; nom d’Empire projeté.
- Migration 0008 : colonnes Knowledge dans le DDL figé (plus d’add_column a posteriori), CHECK
  capacités/traitement de rapport ; downgrade toujours refusé si données ou grants Galaxy.

Tests ajoutés : non-fuite exhaustive (aucun id/nom UNKNOWN ou structure non cartographiée dans carte,
liste, détail, missions, avant et après découverte), refus sans effet (MAPPED, chemin inconnu,
colonie/Empire étrangers, fonds insuffisants, même clé autre corps), cookie d’un autre Universe,
expiration sans arrêt de mission acceptée, deux participants (capacité partagée, clés séparées),
dépenses Exploration/Research/Colony simultanées sans deadlock, génération concurrente unique,
corruption de chemin et downgrade refusé par grants seuls ; test Portal de l’allowlist.

## G02 — générateur et corpus de robustesse, 31/10/2026

Version galaxy-v1 : quatre lobes initiaux à distance protégée, réseau central seedé, positions
entières avec jitter déterministe, tirages pondérés puis garanties des mondes ; budget structurel
initial identique entre zones (tirages corrélés), sans réservation gameplay des candidats. Cette
corrélation assure les quatre métriques d’équité sans prétendre à des planètes indépendantes.
Variation des noms/mondes/positions/connexions entre seeds. SHA-256 compteur/rejection sampling,
tri canonique, pas d’horloge/hash Python/UUID. Gate finale indépendante : connexité, degrés, ponts,
distances, séparation/routes, mondes/capacités/sites/équité et deux sorties disjointes par max-flow.
64 tentatives maximum, erreur explicite sans relâchement ; corpus intégral conservé dans les tests.

Mesure locale conteneur Python 3.12, seeds `galaxy-v1-corpus-0000` à taille du corpus exclue :

| Systèmes / sites | Seeds | Échecs | Moyenne ms | p95 ms | Tentatives max |
| --- | --- | --- | --- | --- | --- |
| 40 / 4 | 1 000 | 0 | 5,151 | 7,873 | 2 |
| 30 / 1 | 100 | 0 | 2,019 | 2,555 | 6 |
| 30 / 4 | 100 | 0 | 2,128 | 3,157 | 6 |
| 50 / 1 | 100 | 0 | 32,741 | 82,735 | 6 |
| 50 / 4 | 100 | 0 | 31,694 | 81,953 | 9 |

Toutes les sorties satisfont Q06 ; aucune seed retirée, aucune relaxation. Diamètre maximal 10
sur standard, moyenne des chemins maximale 4,489744 ; bords 50 maximum 4,499592. Aucun benchmark
production revendiqué. Golden hash, inter-processus/PYTHONHASHSEED, variabilité, corruptions finales,
bornes, versions inconnues et erreur après 64 essais testés. 29 tests ciblés réussis ; pas encore
de migration ou intégration PostgreSQL pour le nouveau domaine. v0.1/v0.2 octets inchangés.

## Correctif CI préalable à G02 — 31/10/2026

Validation utilisateur Q06/Exploration reçue avec amendements (4 sites candidats par défaut,
aucune réservation gameplay, corpus 1 000 seeds standard et 100 par configuration de bord).
Avant code substantiel : cinq runners CI épinglés ubuntu-24.04, sans modifier Playwright/dépendances.
Logs G01 b55d54c vérifiés : seuls frontend/portal-frontend échouent à l’installation Chromium,
Ubuntu 26.04 non supporté ; backend/portal-backend/compose-smoke réussis. Attendre 5/5 vert
sur le correctif avant G02 ; validation produit à consolider pendant cette attente.

## G01 — audit et propositions avant implémentation, 31/10/2026

Plan durable G00–G10 avec schéma préparatoire, dépendances, risques, matrice sécurité/concurrence/
reprise et recette worker autonome/Portal arrêté. Q06 propose 40 systèmes (30–50), degrés 2–4,
cycles sans pont, connexité et distances bornées, géométrie déterministe, mondes variés garantis,
sites de départ comparables et version explicite. **Proposition non validée**, aucun algorithme
final ni catalogue exécutable. Exploration propose une capacité d’expédition abstraite unique,
financement Colony, échéance réelle et révélation structurelle locale sans catalogue Fleet.
Coût/durée/rappel/frontière à valider explicitement ; aucun arbitrage Q09 implicite.

Lectures : AGENTS/CLAUDE/context/progress, index/passation/protocole/roadmap/registre, tous les
canoniques métier demandés, modèle/temps/sécurité, ADR pertinents, modèles Universe/Empire/System/
Planet/EventStream/ScheduledEvent et patterns Colony/Research API/UI/idempotence/worker, migrations
et tests PostgreSQL pertinents ; guide visuel et deux images examinés. Détails et emplacements dans
le plan. Environnement WSL2 identifié par uname ; pas de test fonctionnel de pile déduit du noyau.
Checks documentaires et diff réellement exécutés, suites fonctionnelles non relancées pour ce diff.
Arrêt utilisateur respecté à G01 : validation nécessaire avant G02, aucune étape 8 et aucun merge.

## G00 — synchronisation post-merge Research, 31/10/2026

Instruction utilisateur : synchroniser le clone puis commencer étape 7, avec arrêt produit explicite
après G00/G01. PR #9/base/head/merge et CI post-merge vérifiés réellement ; fetch effectué.
Ancienne branche locale 5D `b9425ce` en retard de deux commits, aucun commit non publié.
Master locale `ff6ef89` avancée en fast-forward à `437844e4`, identique à origin/master ;
branche étape 7 créée depuis cet arbre propre. Branches anciennes préservées, aucun reset/force/merge.
Restriction sandbox initiale sur .git/réseau résolue par exécution autorisée ; aucune donnée perdue.
Les statuts d’étape 6 deviennent historiques sans réécrire leurs preuves de livraison.

## Checkpoint Research antérieur à la fusion #9 (historique)

### Reprise rapide Research avant fusion

| Champ | État au 31/10/2026 |
| --- | --- |
| Branche / PR / base | work/step-6-research, unique PR #9, base master 0e2ca11322a85452ad6860a4a35099bbc22a4689 ; GitHub réel prioritaire |
| Tête fonctionnelle auditée | d958661299ad8fe54a6bac590fbd2ecbb017de39 ; ce checkpoint final ne modifie que la documentation, tête/CI exacte à relire dans PR #9 |
| Dernier agent | ChatGPT Work, seul écrivain de ce checkout ; aucune branche ou PR supplémentaire |
| Décisions | Q05 **Clos produit — implémentation étape 6**, validation explicite utilisateur ; autres Qxx conservées |
| Réalisé | R02–R07 : catalogue complet v0.2, migration 0007, stream/file/acquis Empire, réservations/snapshots/annulations/effets, API/permissions Game et Portal, UI connectée responsive/clavier ; R08 recette réelle réussie, R09 relecture/CI/passation réalisés |
| Références | [Contrat](docs/01-game-design/research.md), [plan](docs/05-project/step-6-plan.md), [API/UI/recette](docs/03-technical/research-api-ui.md) |
| Validation locale | Ruff Game/scripts et docs OK ; 63 tests unitaires Game réussis, intégrations ignorées (PostgreSQL absent) ; frontend lint sans erreur (warning préexistant useGameSession), 31 Vitest et 13 Chromium réussis, build OK |
| CI observée | Tête fonctionnelle d958661 : [CI PR 41149331793](https://github.com/ThomasPerez91/Echosphere/actions/runs/41149331793) success, cinq jobs ; 226 tests Game, 119 Portal, 31 Vitest Game/13 Chromium et 30 Vitest Portal/14 Chromium ; smokes complets dont Research et Portal coupé. CI du checkpoint documentaire à vérifier sur sa tête avant Ready |
| Limites | Docker/PostgreSQL absents localement : intégrations/smokes via CI, aucune recette WSL2 déclarée faite. Création complète de partie, adoption v0.2 d’univers existants, laboratoires/IA/étape 7 hors lot |
| Prochaine action si #9 ouverte | Relire tête/CI et revue ; R09 terminé, Ready for review après CI verte du checkpoint final. Ne merger que sur autorisation explicite |
| Prochaine action si #9 fusionnée | Synchroniser master, recette locale WSL2/Docker/Codex ; ne pas recréer #9 ni reprendre sa branche fusionnée. Nouveau développement/étape 7 seulement sur instruction |

## Validation Q05 et réalisation R02–R09 — 31/10/2026

Contrat validé : file Empire 1+1 ; colonie payeuse explicite ; débit complet à l’acceptation même
pour la suivante ; refunds queued 100 % / active 80 % théoriques, capacité plafonnée, excédent perdu,
cascade dépendante. Catalogue 8 technologies I/II, bonus 5/10 % net par effet. Snapshot complet coût,
durée effective, source et règles figé à l’acceptation : aucune acquisition ne modifie une réservation.
Pas de laboratoire. Droits read/start/cancel distincts, colony.read pour financement/remboursement,
aucun besoin de construct ou privilège admin implicite. R02–R09 autorisés sans arrêt intermédiaire.

Implémentation dans backend/app/research, migration additive 0007 et game_data/rulesets/v0.2 ;
coordination de devis Colony, TimeEngine existant et contrôle privé Game/Portal/schéma v1 étendus.
Frontend Research dans le shell, source/Empire distincts, confirmations, preview complète,
retry même intention ; rafraîchissement des stocks Colony après commande.
Les fichiers v0.1 et migrations 0001–0006 sont inchangés ; aucune dépendance/Docker/Compose ajouté.

Recette réelle ajoutée à CI : projet jetable *_test, HTTPS/login/handoff/permissions réels,
réservation de deux recherches, navigateur fermé jusqu’aux acquis worker et effets Colony ; arrêt
Portal API/contrôle, nouveau lancement puis page fermée jusqu’à l’achèvement worker observé en base,
effets et expiration. Sans intercept, sans assimilation à un parcours produit de création de partie.

Historique : R00/R01 ci-dessous ont respecté l’arrêt Q05 avant code. Leurs mentions « Q05 ouverte »,
« aucun Research livré » et « attendre validation » sont historiques depuis la validation utilisateur.

## R09 — relecture et clôture de livraison sur PR #9, 31/10/2026

R00–R09 réalisés après validation Q05. Relecture du domaine, des scopes/FK/permissions, ordre des
locks, montants exacts/snapshots, cascade/refunds, handler sans second stream, UI et procédures.
Corrections issues de revue : noms Alembic CHECK, inventaires de migration des smokes, CSRF du test
second participant, protection contre réponses dépassées et snapshots incohérents. Une définition
persistée incohérente relève du retry technique, jamais d’une annulation/blocage gameplay silencieux.

Tête fonctionnelle **d958661299ad8fe54a6bac590fbd2ecbb017de39**, CI PR **41149331793 success**.
Le checkpoint présent ajoute uniquement la passation finale ; sa CI et son SHA sont ceux affichés
sur PR #9. Ready for review après ce dernier vert, comme autorisé par l’utilisateur ; aucune fusion.

Preuves CI : 226 tests Game PostgreSQL, dont 25 intégrations Research et 10 tests de catalogue ;
119 tests Portal. Frontend Game : lint sans erreur, 31 Vitest, build et 13 Chromium ; Portal :
30 Vitest, build, lint et 14 Chromium. Alembic upgrade/idempotence/check, roundtrip à vide, refus de
downgrade avec état/grants et scopes financiers testés. check_docs : 80 documents, liens locaux OK.
Les avertissements FastAPI TestClient et useGameSession sont préexistants ; aucun échec masqué.

Compose : smokes Game, Portal, contrôle mTLS, handoff/C09 avec backup/restore, Colony/Q39 et Research
réussis. Research HTTPS réelle : deux réservations, navigateur fermé jusqu’aux deux acquis worker,
durée suivante inchangée malgré Calcul I, coût Colony réduit par Ingénierie ; Portal API/contrôle
arrêtés, lecture/lancement puis nouvelle fermeture jusqu’à l’acquisition **observée en base avant
réouverture**, effet Énergétique réel et refus 401 après expiration simulée. Zéro appel gameplay
Portal, pas d’intercept dans cette recette. Projets/bases/volumes jetables de recette supprimés.

Local Work : 63 tests Game réussis, intégrations ignorées faute de PostgreSQL ; frontend Game
31 Vitest/build/lint/13 Chromium exécutés. Docker/PostgreSQL non disponibles dans Work, donc preuves
intégrées issues de CI. **Recette locale WSL2/Docker/Codex non effectuée dans ce lot.** Aucun chiffre
de charge garanti. Aucun laboratoire, IA, étape 7, migration silencieuse de ruleset, dépendance ou
changement Docker/Compose ajouté. Les fichiers v0.1 et migrations 0001–0006 publiées sont inchangés.
La dernière relecture a aussi corrigé un report documentaire erroné sur les pages Colony et contrôle
Portal/Game : contenu antérieur rétabli depuis ff95c13, seuls les ajouts Research prévus conservés.
Leur diff final a été relu contre cette version et les titres des documents existants contrôlés.

Après fusion #9 seulement : master synchronisée et recette locale WSL2/Docker/Codex ; pas de reprise
ou recréation de branche #9 fusionnée. Prochain développement fonctionnel uniquement sur instruction.

## R00 — synchronisation post-merge 5D, 31/10/2026

Instruction utilisateur : reprendre master après fusion #8, créer work/step-6-research et une seule
PR brouillon pour tout le lot ; publier ce premier checkpoint avant implémentation substantielle.
GitHub contrôlé : #8 MERGED, ancienne tête d15dfda858cc829efa681572f420e9095fda5ace, merge/master
0e2ca11322a85452ad6860a4a35099bbc22a4689. [CI post-merge 41144706921](https://github.com/ThomasPerez91/Echosphere/actions/runs/41144706921)
observée completed/success avant publication du checkpoint. Aucun code métier commencé pendant
l’attente. Liste des PR ouvertes vide ; branche étape 6 absente avant sa création depuis master.
Fetch, master locale fast-forward, arbre propre puis branche étape 6 créée au SHA du merge :
aucune reprise depuis la branche 5D, aucune divergence/travail local perdu ni branche supprimée.

5D D00–D09 et Q39 intégrées à master : première boucle Colony jouable, preview des pertes/cascade,
API sous GameSession, progression worker et panne Portal. Les preuves détaillées ci-dessous restent
celles de leurs SHA ; leurs mentions « PR #8 non fusionnée » et « étape 6 non commencée » sont
historiques. Étape 6 démarre **documentairement seulement** : Q05 doit être proposée et validée par
l’utilisateur avant migration/backend/UI Research. Aucun autre arbitrage produit modifié.

Validation du checkpoint : documents/liens et whitespace, diff Markdown uniquement, invariants Qxx
conservés. Aucune suite fonctionnelle locale relancée pour ces statuts ; la CI de cette nouvelle
tête devra être observée après publication et consignée dans l’unique PR du lot.

## R01 — proposition Q05 et plan durables, 31/10/2026

Premier checkpoint R00 **098ab078889ca7a41b5ed77055663a439670ccdf** publié avant cette préparation ;
[PR #9](https://github.com/ThomasPerez91/Echosphere/pull/9) créée en brouillon, unique. Sa [CI 41145436851](https://github.com/ThomasPerez91/Echosphere/actions/runs/41145436851)
est observée completed/success ; elle vérifie le code 5D inchangé, pas un système Research.

Références demandées relues : AGENTS/CLAUDE/context/progress intégral, roadmap/registre,
recherche/boucle/progression/balance, moteur temporel/modèle/sécurité/API Colony, code Empire/
EventStream/ScheduledEvent/scheduler/worker/rulesets, GameSession/accès/bindings, frontend Game et
patterns de tests 3/5A/5D. Guide visuel et images design-system/research-view inspectés ; aucun
catalogue, technologie, valeur ou nombre de places du mockup promu en règle produit.

Nouveau [plan étape 6](docs/05-project/step-6-plan.md) : R00–R09, critères/tests futurs, verrou Q05,
modèle Empire et financement Colony séparés, compatibilité v0.1/nouveau ruleset sans migration
silencieuse, extension ciblée des permissions 5C et ordre de verrous multi-stream à démontrer.
**Points concrets** : stocks attachés à Colony ; seuls trois droits Colony acceptés dans les DTO,
CHECK SQL, schéma JSON et allowlist Portal ; scheduler sans ordre global entre streams et handler
sans second lock. Aucun de ces points n’est résolu par du code ou un backfill dans ce checkpoint.

[Q05 dans research.md](docs/01-game-design/research.md) : proposition cohérente de 1 active + 1 suivante,
paiement intégral depuis une colonie explicitement choisie, annulation théorique 100/80 avec crédit
plafonné/perte et cascade dépendante, technologies uniques/non exclusives, snapshots à acceptation,
blocage explicite d’une suivante invalide, permissions séparées et laboratoire futur sans cumul
implicite. Huit technologies proposées avec modestes effets réellement applicables aux nouveaux
ordres Colony/Research ; noms/chiffres à équilibrer, aucun game_data ajouté. La proposition ne
modifie pas Q01/Q39 ni Q26 : **Q05 reste ouverte**, aucune validation déduite du code ou de la CI.

Aucune migration, backend/API/UI Research, catalogue exécutable, effet runtime, test fonctionnel,
dépendance ou Compose modifié. Les tests R02–R09 listés sont futurs et non exécutés. Contrôles locaux
de ce diff : check_docs (79 documents/liens), git diff --check, Q01–Q56 uniques, seules les mentions
Q05 et le statut de lot changés au registre ; autres arbitrages conservés. Suites fonctionnelles
locales non relancées pour du Markdown ; CI complète propre à la tête publiée à observer dans PR #9.
Aucun code métier avant arbitrage explicite. **Travail arrêté à Q05 comme demandé par l’utilisateur**,
PR #9 maintenue en brouillon, aucune fusion ni étape 7.

## Historique du lot 5D — intégré via PR #8

### Ancien bloc de reprise 5D (historique, remplacé)

| Champ | État |
| --- | --- |
| Branche / PR / base | work/step-5d-secure-colony-ui · PR #8 · base master ff6ef89 ; vérifier GitHub pour état brouillon/revue |
| Tête et CI | Source Q39 de72c181e6ba35e07ce9c397824a3e45d34e16de : CI PR 41143478865 et push 41143467685 success (5/5). Ce checkpoint documentaire suit la source ; sa propre tête/CI est consignée dans PR #8 après observation |
| Dernier agent | ChatGPT Work, écrivain unique de ce checkout ; reprise des commits publiés Claude Code |
| Travail réalisé | Q39 crédit plafonné/perte définitive, preview autoritative et cascade Q01 détaillée, reçus réels idempotents ; arbitrages produit consolidés |
| Décisions | Q01 construction, Q08, Q17, Q19–Q39 et Q55 closes dans leur portée au registre ; modes/fog/défense futurs, performance non démontrée |
| Fichiers modifiés | Services/projection Colony, tests Game, client/confirmation/formatage/tests UI, smoke Colony ; docs produit/tech/qualité/registre/passation et AGENTS/context/progress |
| Tests réellement exécutés | Local Work : Ruff backend/scripts ; Game 53 passed / 138 skipped (pas de PostgreSQL), frontend lint 0 erreur (avertissement préexistant), 26 Vitest, build, 9 Chromium 320/390/768/1440 ; 78 documents/liens ; git diff --check. CI de72c18 : Game 191 passed, Portal 119 passed ; Game 26 Vitest/9 Chromium, Portal 30 Vitest/14 Chromium ; Alembic deux plans sans dérive et smokes Game/Portal/mTLS/handoff/Colony-Q39 verts. SQL/Alembic/smokes non exécutés localement |
| Anomalies / corrections restantes | Pas de Bloquante/Majeure restante identifiée à la relecture et aux 5 jobs verts de de72c18 ; vérifier aussi la CI du présent checkpoint documentaire. Docker/PostgreSQL absents du Work courant ; limites navigateurs/charge/support/production conservées |
| Prochaines tâches | Revue finale utilisateur de #8, Ready for review après CI verte de sa tête finale. Aucun merge sans instruction ; après fusion autorisée, vérifier master/CI puis checkpoint du lot Recherche sur nouvelle branche issue de master propre |


## Complément pré-revue Q39 et arbitrages — 31/10/2026

Instruction utilisateur explicite : modifier le code sur la branche existante #8, consolider les
arbitrages et finaliser la revue, sans nouvelle branche/PR ni fusion. GitHub vérifié : #8 ouverte,
brouillon, mergeable, tête b9425ce, master ff6ef89 ; aucun commentaire/fils de revue existant.
Arbre local propre avant reprise, aucun travail non publié écrasé.

Q39 : `recoverable_refunds` partagé par projection et commande, après rattrapage et sous verrou du
stream pour application ; montant crédité limité par ressource, perte définitive sans réserve.
Allocation de la place commune en ordre de file, reçus par ordre contenant le crédit réel, replay
sans nouveau crédit même si de la place se libère. Sommes théoriques transitoires en entiers Python,
sans overflow BIGINT ; persistance toujours bornée. Aucune migration, dépendance, modification de
ruleset/game_data, Docker/Compose ou code Portal.

UI : remboursement théorique/récupérable/perte affichés avant confirmation ; tous les upgrades
dépendants listés avec infrastructure/secteur/niveau, aucun indépendant ajouté. Présentation exacte
jusqu’à la micro-unité, aucune règle économique React. Estimation datée, recalcul Game à acceptation.
Tests ajoutés : saturation mono/multi-ressources, 100/80, cascade 3 ordres et indépendant préservé,
concurrence de cascades, retry après réponse perdue/place libérée, rollback SAVEPOINT après crédit,
allocation exacte et théorique au-delà de BIGINT. Smoke réel Colony étendu à l’overflow avec Portal
arrêté, crédit nul à capacité et retry ; setup limité à sa base jetable. Exécuté avec succès en CI
sur de72c18 (non exécuté localement).

Q01 construction/cascade/pacing, Q08, Q17, Q19–Q39 et Q55 transcrites depuis l’instruction du
31/10/2026 : décisions closes distinctes des paramètres initiaux balançables et implémentations
futures. Q02/Q03/Q04/Q05/Q10/Q14 et support/configuration production gardent leur portée non tranchée.
Aucun fog, mode, défense, pause, admission ou parcours de partage développé par implication.

Relecture du diff complet de #8 contre master ff6ef89 : services partagés 5A, GameSession→GameAccess→
EmpireBinding→colonie, origine/CSRF/enveloppes strictes et permissions distinctes, verrou principal
avant stream et contrôle des révocations 5B/5C conservés. Fixtures uniquement dans tests/recettes
avec garde de base, aucun nouveau faux compte/donnée runtime. UI/clavier/viewport vérifiés,
captures confirmation inspectées à 320 et 1440. Pas d’autre agent de revue lancé ; cette relecture
Work ne constitue pas une certification de sécurité ni un benchmark.

Environnement Work : Python 3.12/Node/Chromium natifs, ni Docker/socket ni PostgreSQL local.
Premier lancement Chromium avant fin du téléchargement du navigateur impossible ; relancé après
installation avec succès. Test de formatage initialement sensible aux espaces fines françaises,
corrigé dans le test ; aucun échec local restant. Les intégrations SQL et smokes ne sont jamais
présentés comme exécutés localement. Suite Portal inchangée, couverte par CI complète.

Les checkpoints 5D ci-dessous décrivent leur ancien SHA ; leurs refus Q39/statuts Qxx sont historiques
et remplacés par ce complément. Étape 6 Recherche non commencée. Après une autorisation distincte
de fusion : vérifier master/CI, nouveau lot sur master synchronisée avec checkpoint documentaire
avant implémentation ; références research-view.png/design-system.png.

### Validation du complément publiée et observée

[CI PR 41143478865](https://github.com/ThomasPerez91/Echosphere/actions/runs/41143478865) et
[CI push 41143467685](https://github.com/ThomasPerez91/Echosphere/actions/runs/41143467685)
**completed/success, 5/5 jobs** sur de72c181e6ba35e07ce9c397824a3e45d34e16de.
Game 191 tests PostgreSQL/unitaires ; Portal 119 tests ; Game 26 Vitest/9 Chromium et Portal
30 Vitest/14 Chromium ; 78 docs/liens. Alembic Game et Accounts : « No new upgrade operations
detected ». Smokes : Game/DB panne-reprise, Portal/DB isolées, mTLS/control, handoff et Colony.
Logs Colony relus : boucle page fermée/worker, gameplay sans Portal, Q39 perte annoncée avant clic,
annulation à capacité et retry sans crédit, puis 401 à expiration. Relecture terminée sans anomalie
Bloquante/Majeure restante identifiée. Ce commit de checkpoint n’ajoute aucun changement fonctionnel ;
vérifier sa propre CI dans la description PR avant passage en revue. Ne pas merger sans instruction.

## Historique 5D — API Colony sécurisée et UI Colony interactive

**Statut : D00–D09 réalisés ; PR #8 prête pour revue finale (non fusionnée).** Instruction utilisateur du 2026-10-30 : réaliser 5D de bout
en bout sur une seule branche/PR, sans merge, sans étape 6. Environnement : Claude Code local/WSL2.

### D09 — recette complète et clôture, 2026-10-30

Contenu final validé localement : backend Game **178 passed** (echosphere_5d_game_test), Ruff
check backend+scripts et format app/tests ; frontend Game ESLint 0 erreur (1 avertissement
préexistant), **24 Vitest**, build ; Chromium **9 passed** (copie hors dépôt). Pile conservée
recréée avec les images 5D, volumes préservés : Alembic Game 0006_game_sessions et Accounts
p0005_control sans dérive (aucune migration 5D) ; smoke_compose, smoke_portal_compose,
smoke_control_compose et smoke_handoff_compose réussis (code 0), recette smoke_colony_compose
réussie (D08). Correctif : ordre d’imports Ruff de la fixture Colony (la CI de f837554 l’aurait
signalé). Portal non modifié : ses suites ne sont pas relancées localement et restent couvertes
par la CI. Documentation de clôture : roadmap, contexte, API, sécurité, économie, stratégie de
tests, DoD, index des décisions, lacunes, passation, plan.

Conclusion : 5D atteint son critère de sortie (boucle jouable réelle et Portal coupé démontrés) ;
PR #8 prête pour revue finale après CI verte du SHA publié. Aucune fusion, étape 6 non commencée.

### D08 — boucle réelle et Portal coupé, 2026-10-30

`scripts/smoke_colony_compose.py`, `scripts/colony_browser.mjs`, `scripts/colony_game_fixture.py`
(test-only, base `echosphere_colony_game_test` exigée) ; étape ajoutée au job CI compose-smoke.
Exécution locale réelle après `docker compose build` de l’arbre : **réussie (code 0)** — login/lobby/
handoff, réservation immédiate, achèvement par le worker page fermée, production mise à jour,
action suivante, Portal API + worker de contrôle arrêtés (Portal /api/ready en erreur) avec lecture,
construction acceptée, worker progressant et zéro requête vers Portal, puis 401 et UI d’expiration
à l’échéance simulée en base de test. Captures /tmp/echosphere-colony-artifacts inspectées (hors
dépôt). Projet temporaire et volumes supprimés, pile conservée intacte.

### D05–D07 — UI Colony connectée, responsive et erreurs, 2026-10-30

Frontend Game : `src/colony/api.ts` (client validant), `src/colony/format.ts` (présentation exacte
BigInt, libellés, messages d’erreur), `src/hooks/useColony.ts`, `src/components/ColonyScreen.tsx`,
câblage App/ColonyView (top bar ressources, Empire réel), tokens rapprochés de la référence
visuelle. Projection backend complétée par `free_indices`. Détail : [canonique](docs/03-technical/colony-api-ui.md).

Tests réellement exécutés (node:22, conteneurs) : tsc, ESLint 0 erreur (1 avertissement préexistant
useGameSession), Vitest **24 passed** (16 antérieurs + 8 Colony : rendu sans mutation sous
StrictMode, double clic unique, retry même clé après issue inconnue, refus expliqué + relecture,
annulation confirmée/refus Q39, lecture seule sans boutons, 401 → relecture session, échéance →
lecture sans POST). Test d’échéance C08 adapté pour ne compter que les lectures de session.
Chromium **9 passed** (5 shell + 4 Colony 320/390/768/1440 : débordement, atteignabilité réelle
du centre des boutons, clavier, construction, file, annulation non confirmée, sous-vues). Captures
inspectées à 320 et 1440 ; artefacts hors dépôt.

### D01–D04 — API Colony autorisée, commandes et concurrence, 2026-10-30

[Canonique](docs/03-technical/colony-api-ui.md). Service 5A refactoré sans changement de règle :
codes publics stables sur ColonyError (messages inchangés), `plan_order`/`colony_state`,
`cancellation_plan`/`refund_fits`, `effective_duration_us` partagés par commandes et projection.
`app/colony/projection.py` (lecture, montants micro-unités en chaînes) et `app/colony/api.py` :
liste, détail, construction, annulation sous `/game/{univers}/colonies`. Chaîne GameSession →
GameAccess → EmpireBinding → colonie dans une transaction, verrou principal puis stream, commandes
classées activité explicite, clé idempotente préfixée par participation. Horloge injectable
`app.state.clock` (SystemClock par défaut) partagée avec l’accès C07. Aucune migration, dépendance,
game_data ni Compose modifiés.

Tests réellement exécutés : `backend/tests/integration/test_colony_api.py` **28 passed** ; suite Game
complète **177 passed** puis 178 avec la course d’amélioration (echosphere_5d_game_test dédiée) ;
Ruff app/tests. Projection, non-fuite (autre compte/univers/Empire, inconnu, sans lecture), cookie
d’un autre univers, lecture seule ≠ construction, construction sans annulation, réservation unique,
replay/conflit de clé, espace de clés par participation, enveloppe stricte (origine/CSRF/type/extra/
booléen/query/clé), file pleine, secteur/contiguïté, unicité, ressources insuffisantes, achèvement
par worker puis action suivante, rattrapage paresseux sans worker, 100/80, Q39 atomique, ordre
achevé non annulable, doubles clics/dernier slot/amélioration/annulations concurrents, sessions
expirées/suspendues/révoquées, saturation avant dépense.

### D00 — synchronisation post-merge, 2026-10-30

GitHub vérifié avant écriture : PR #7 closed/merged, master = origin/master
ff6ef894bf8c8da9ea14b293d8c63fa503fa07f0 (parents 63bb7d1, 5d438ab), CI push 41123867271 success
(5/5 jobs). Arbre propre, aucun worktree supplémentaire, aucune PR ouverte. Branche
work/step-5d-secure-colony-ui créée depuis ce master. Suite Game de référence : **150 passed**
(echosphere_5d_game_test, conteneur PostgreSQL 17 jetable sur réseau isolé, aucune donnée conservée).

## Lot précédent — 5C : Portal Account/Lobby foundation (fusionné, PR #7)

**Statut : C01–C09 réalisés ; revue et validations finales Claude effectuées, 5C prêt pour revue finale de PR #7 (non fusionnée).**
5B documentaire terminé et intégré à master via PR #6 ; contrats validés, sous-ensembles comptes/sessions/MFA/lobby/contrôle privé/handoff C02–C07 implémentés sur PR #7 seulement.
L’utilisateur autorise 5C et exige présentation du cadrage avant implémentation substantielle ; 5D exclu.
Aucune nouvelle fusion autorisée. Environnement : Codex local/WSL2.
Les checkpoints pré-code ci-dessous sont historiques ; l’état actuel de C07 est décrit en premier.

### Revue et validations finales Claude — C08/C09, 2026-10-30

Agent : Claude Code local (WSL2), écrivain unique après arrêt de Codex. État vérifié avant écriture :
PR #7 OPEN/brouillon, base master 63bb7d1, tête locale = distante 237c97c1e0dc1e39dc78cfd1c292591eb429b2f3,
arbre propre, aucun worktree ni fichier non commité ; CI 237c97c push 41116382297/PR 41116392662 success.

Revue du diff 35067f8..237c97c (56 fichiers) : reçus chiffrés 15 min sans pouvoir d’authentification,
cookies `__Host-` sans Set-Cookie tardif effaçant une connexion plus récente, POST JSON corps vide/CSRF/
origine, pages de transfert à nonce CSP, timers passifs relisant le serveur, générations/abort contre
les réponses tardives et StrictMode. **R1 (Mineure, confirmée et corrigée)** : après un login normal, le
serveur efface le reçu mais l’UI conservait l’ancien statut « en attente » (onLogin sans remontage de
RevocationStatus), contrairement au canonique C08. Test de reproduction ajouté, en échec avant la
correction et réussi après. Aucune autre anomalie démontrée ; remarques non bloquantes : avertissements
ESLint react-hooks (compteur de génération, dépendance Lobby) et capture pleine page 320 où la barre
mobile fixe recouvre un bouton (artefact de capture, pas de défaut d’UI démontré). L’absence d’autre
anomalie détectée n’est pas une garantie ; aucune revue croisée Codex de R1.

Validations réellement exécutées par Claude (conteneurs node:22-bookworm, copies hors dépôt) :
Game frontend sur 237c97c lint 0 erreur, 16 tests, build, 5 Chromium ; Portal frontend sur 237c97c
29 tests/build/14 Chromium, puis après R1 lint 0 erreur, 30 tests, build, 14 Chromium. Pile reconstruite
depuis l’arbre final (volumes conservés) : Alembic Game 0006_game_sessions et Accounts p0005_control sans
dérive ; smoke_compose, smoke_portal_compose, smoke_control_compose et smoke_handoff_compose réussis
(code 0), recette C09 complète incluse. Pile conservée de nouveau running/healthy. Suites backend non
relancées par Claude : backend inchangé depuis les 150 Game/119 Portal de Codex sur 237c97c ; la CI du
SHA final les réexécute. Bases echosphere_c08_* conservées par Codex non supprimées (pas d’instruction).

Conclusion : 5C est terminé côté implémentation et recette locale, **prêt pour revue finale** dès que la
CI du SHA final est observée verte (consignée dans PR #7). Ni fusion, ni sortie de brouillon, ni 5D sans
instruction ; production, Q48/Q49/Q55 et charge hostile restent hors clôture.

### Relais explicite Codex → Claude — C08/C09, 2026-10-30

Utilisateur : enchaîner C08/C09, puis demande de stopper pour préserver les crédits et transmettre
à Claude. Arrêt du développement ; vérification Portal déjà lancée terminée (119 réussites).
Checkpoint publié pour protéger le travail, **pas une déclaration de clôture 5C**. Aucun merge,
5D, nouvelle branche, reset/clean/stash/force-push ou suppression de données conservées.

Reprise initiale propre/synchronisée sur 35067f8, documentation Claude préservée. C08 : handoff
POST automatique avec CSP nonce et secours manuel, entrée dans le shell React scoped par univers,
contexte réel/échéances, JSON même origine/CSRF, erreurs HTML lisibles et actions explicites. Timers
passifs lisant le serveur sans renouvellement ; Portal bootstrap distingue panne/absence de session,
courses StrictMode/annulation corrigées. Reçu de déconnexion chiffré purpose/scope/source/15 min,
clé receipt.key séparée et cookie HttpOnly ; aucune autorité de connexion. GET statut sans identité,
acknowledged uniquement après tous les acquittements C06. Ancien reçu effacé à la connexion/autres
opérations sensibles pour éviter un faux suivi ; UI réinitialisée. Cookies de session déjà révoqués
non effacés par une réponse tardive, remplaçables par une authentification normale, sans résurrection.
Pas de nouvelle table, dépendance, migration, règle produit, mécanique ou fixture runtime.

C09 : nouvelle recette dans scripts/smoke_handoff_compose.py et handoff_browser.mjs : projet Compose
aléatoire sans ports hôtes, bases *_test et volumes propres ; arrêt Portal API et contrôle, Game
encore accessible, construction test acceptée puis terminée par le worker réel (c09_game_fixture.py
strictement gardé par nom DB test). Reprise API puis logout avec livraison arrêtée, état pending ;
reprise worker de contrôle, receipt acknowledged, ancienne GameSession refusée. pg_dump/pg_restore
réalisés pour chaque DB vers echosphere_restore_test et têtes Alembic vérifiées ; DB restaurées jamais
servies comme applications. Projet temporaire supprimé. Production/support/modes restent différés.

Validations réellement obtenues (journaux /tmp, non versionnés) :

- /tmp/echosphere-c09-game.log : **150 passed**, 1 warning Starlette/httpx ; clés en recouvrement puis
  retrait local testé. /tmp/echosphere-c09-portal-checked.log : **119 passed**, même warning.
- /tmp/echosphere-c09-game-ui.log : npm ci/lint, **16 tests**, build et **5 Chromium** réussis.
  /tmp/echosphere-c09-portal-final-ui.log : npm ci/lint, **29 tests**, build réussis ;
  /tmp/echosphere-c09-portal-ui.log : **14 Chromium** réussis. Les derniers ajustements de nettoyage
  de reçu/MFA nécessitent relecture et vérification frontend finale ; ne pas les présumer exécutés.
- /tmp/echosphere-c09-browser-final.log : recette HTTPS C09 complète réussie à 320/1440, panne réelle,
  progression worker, révocation retardée/acquittée et restore. Captures dans
  /tmp/echosphere-handoff-artifacts ; à inspecter pour la revue finale. Aucun test Windows matériel,
  Safari/Firefox, lecteur d’écran ni charge hostile revendiqué.
- Compose build/up --wait et Alembic check des deux plans réussis ; Game 0006_game_sessions,
  Accounts p0005_control. **Les trois autres smokes Game/Portal/mTLS n’ont pas encore été relancés
  sur C08/C09**, contrairement à la recette handoff étendue. Attendre fin des suites avant les smokes
  qui coupent PG : incident de chevauchement déjà documenté en C07.
- 76 documents/liens et diff valides. Sections 1–8 5B et 56 lignes Qxx comparées inchangées.

Corrections de tests/recette : attente du bootstrap au login ; identité de requête courante pour
ignorer le rejet StrictMode ancien ; les mocks doivent distinguer le GET de statut et les POST CSRF.
Le test de reçu altère un octet chiffré, pas seulement le padding Base64. Les anciennes assertions
« aucun Set-Cookie après reset » distinguent désormais suppression du reçu et émission interdite
d’un cookie de login. Les sondes de panne doivent utiliser Chromium, ses règles DNS ne s’appliquant
pas au client Node APIRequestContext. Diagnostics expurgés des headers Cookie/Authorization.

Reste concret pour Claude :

1. Vérifier ce SHA, PR #7/base/CI et arbre local ; lire AGENTS/context/progress puis canoniques C08/C09.
2. Relire le diff complet depuis 35067f8, notamment reçus/cookies tardifs, bootstrap StrictMode,
   timer de session, JSON natif et protocole du test C09. Aucun relecteur indépendant encore attesté.
3. Finir la cohérence des statuts : quelques docs disent C08 livré/C09 clôture tandis que context
   et progress doivent rester « en cours » tant que CI finale non observée. Ne pas annoncer production prête.
4. Lint final + suites frontend finales, puis checks nécessaires selon les résultats ; tests backend
   déjà passés ci-dessus. Ne pas lancer panne PG pendant une suite. Exécuter les trois autres smokes,
   éventuellement revalider la recette finale après toute correction runtime.
5. Vérifier services/volumes et nettoyer seulement les DB de suites dédiées echosphere_c08_game_test
   et echosphere_c08_accounts_test après usage (elles sont conservées pour le relais).
6. Commit/push des corrections ciblées, observer la CI du SHA final, actualiser PR #7 et progress.
   Conclure si 5C est terminé/prêt pour revue finale avant merge ; aucune fusion, aucun début de 5D.

### Protocole de sécurité multi-agents et relais — documentaire, 2026-10-30

Instruction utilisateur « Reprend » puis protocole de sécurité et de relais sur épuisement des crédits.
Agent : Claude Code local (WSL2). État vérifié avant écriture : PR #7 OPEN/brouillon, tête locale =
distante 49799e4b42b2831720764ea57a6c3b7aa3495bf5 (C07 Codex), arbre propre, aucun fichier modifié
hors commits, CI 49799e4 push/PR success. Rien à préserver hors Git ; aucune réécriture de fichier
entier, éditions ciblées seulement.

Ajouts : priorité Codex/Work principaux et Claude en relais ou revue indépendante, sans effet sur
permissions/validation ; contrôles obligatoires avant écriture et commandes destructives interdites ;
reprise depuis l’état réellement accessible (disque Codex, GitHub pour Work), inventaire fait/reste,
suspension sur divergence/conflit avec résolution préservant les deux versions ; relecteur sans
modification directe sans nouvelle autorisation ; checkpoints intermédiaires sans secret ni
temporaire, non assimilables à validation/fusion ; relais concret Codex → Claude Code → Work.
[AGENTS](AGENTS.md) résume, le [protocole](docs/06-handoff/work-codex-handoff.md) détaille ; CLAUDE.md
inchangé. Validations : check_docs.py et git diff --check ; aucun test fonctionnel (aucun code).

### C07 — handoff et sessions Game, 2026-10-30

Instruction utilisateur : intégrer d’abord le brief visuel, puis poursuivre C07. Reprise GitHub réelle :
PR #7 OPEN/brouillon, tête 7a00c7ba656a22aca67e47f758b1d99ebfa54b5e, base master 63bb7d1 ; fetch/ff-only
sans divergence, CI C06 push 41098495003 et PR 41098504081 success. Dossier visuel préexistant non
suivi, six PNG et README vide ; images inspectées et octets conservés dans 2286c35 (guide/AGENTS/index).

Pendant le démarrage C07, des modifications Claude Code ont été observées dans le même répertoire.
Écritures suspendues ; utilisateur confirme explicitement que Codex peut reprendre seul. Aucun reset,
stash ou écrasement : documentation Claude conservée/publiée séparément dans 97e8ccc, avec provenance.
Même branche work/step-5c-portal-account-lobby ; aucune nouvelle branche, fusion ni 5D.

[Canonique C07](docs/03-technical/game-handoff.md) et contracts/handoff/v1.schema.json : Ed25519 via
PyJWT 2.15.1, clés publiques locales prédistribuées et type/algorithme/origines/claims stricts. Ticket
60 s maximum, sans credential/permission client ; pré-auth 5 min liée au cookie et univers ; POST de
navigation, CSRF et email vérifié, aucun ticket URL/localStorage/log. Secrets de signature 0600 en
volume Portal propre, Game public seul, distincts de mTLS et MFA/mail. Hôtes de cookies distincts
exigés même si ports différents. Anciennes dépendances figées conservées, ajout JWT/crypto Game.

Migration Game additive 0006_game_sessions (pré-auth, jti consommés, sessions, FK composite de scope
renforcée sur GameAccess) ; Accounts p0005_control inchangée. Historique publié immuable ; downgrade
peuplé refusé. Vérification locale puis principal verrouillé, contrôle générations/état/dates et
consommation atomique. Courses avec révocation, quotas et rejeu contrôlés ; réponse perdue impose un
nouveau parcours. Réentrée d’une session active : rotation opaque sans repousser absolu/borne d’accès.
Ancien cookie d’un autre compte encore valide refusé ; déjà révoqué par Portal, il ne bloque pas le
nouveau compte légitime. Aucune connexion ou credential Accounts dans Game, pas de dépendance Portal
par lecture Game ; futurs appels 5D devront garder locked et EventStream dans la même transaction.

Game 8 h absolues/2 h inactif et accès capturé à l’entrée ; lectures automatiques sans effet,
action explicite serveur/CSRF seule actualisant l’inactivité. Cookie host-only/HttpOnly/Secure par
univers. Cap initial configurable dix univers/appareil, comptage sérialisé sans éviction/membership
cap. Révocations C06 compte/appareil/membership appliquées aux vraies sessions ; logout Game ciblé
conserve Portal/autres univers/appareils et interdit les cérémonies déjà en vol de ce slot.

Lobby relié au circuit, participation active/acquittée/vérifiée seulement ; renouvellement explicite
inchangé dans l’outbox, entrée pending jusqu’au receipt, jamais renouvellement en GET ou réactivation
implicite. Vue Game native minimale avec nom d’univers, échéances, actualisation explicite, retour
lobby et logout ; aucun stock/file/Empire factice. Palette et focus cohérents avec le shell ; adaptation
complète du shell React et simplification du parcours restent C08.

Validations réellement exécutées :

- Ruff backend/scripts/Portal, **148 tests Game et 118 Portal** complets sur echosphere_c07_game_test
  et echosphere_c07_accounts_test ; aucun ignoré. Schémas, signatures/clés/origines/type/scopes/cookie,
  consommation concurrente unique, expirations exactes, générations, logout ciblé, quotas concurrents,
  rollback, FK inter-comptes, requêtes automatiques/explicites et cookies déjà révoqués. Historiques,
  roundtrips/Alembic check et refus de downgrade peuplé ; warning Starlette/httpx connu.
- Portal frontend : npm ci/lint, **25 tests**, build et **14 Chromium** réussis. Lien d’entrée et
  confirmation explicite/pending testés ; captures Game inspectées à 320/1440, sans débordement.
- Compose config/build/up --wait ; Alembic Game 0006_game_sessions et Accounts p0005_control sans
  dérive. Smokes Game, Portal HTTPS/CORS/pannes croisées, privé mTLS/outbox/replay/révocations réussis.
  Nouvelle recette Chromium **HTTPS réel à 320 et 1440, sans API interceptée** : compte fixture
  uniquement en DB *_test du projet temporaire, provision/grant via worker mTLS, POST entre origines,
  cookies isolés, absence ticket URL, GET sans activité, actualisation explicite sans repousser absolu,
  retour lobby, logout Game conservant Portal et nouvelle entrée. Aucun port hôte ni CA/hosts modifiés.
  Projet/volumes temporaires supprimés par la recette, données courantes préservées.
  Recette finale relancée après les derniers ajustements de contexte/refus CSRF et réussie.
  Caddy conservé redémarré pour charger son fichier modifié ; TLS/routage des deux origines et
  refus 401 de la nouvelle API Game sans session vérifiés. Deux DB de suites supprimées après succès ;
  bases conservées contrôlées : users=0 et game_principals=0, aucune fixture runtime.
- **74 documents/liens**, diff propre ; comparaison binaire des six PNG, Q01–Q56 et sections 1–8 de
  5B inchangées. Aucun domaine Colony/simulation, game_data, frontend Game ou migration ancienne modifié.

Corrections de recette consignées : contexte Docker ignorait portal dans le premier build des outils
(corrigé par contexte Portal), PYTHONPATH absent au premier lancement (collecte impossible, non succès).
Le shell C06 ne chargeait pas ses cibles FK en processus autonome : import explicite et test séparé.
Le vrai navigateur a montré Origin null sous no-referrer au POST de transfert : strict-origin adopté
sur ces seules pages, sans accepter null ni ouvrir CORS ; CSP Game autorise ses lectures same-origin.
Un smoke de panne PG a été lancé trop tôt pendant une suite Portal : 3 échecs/11 erreurs de connexion
à l’arrêt du serveur, non retenus comme succès ; DB dédiée recréée après la panne et suite complète
relancée avec 118 réussites. Relecture des logs CI de 061fd17 : le test SQL inter-comptes rencontrait
l’unicité du slot avant la FK visée. Le test a été renforcé pour libérer le slot concurrent et exiger
le nom exact de la FK ; scénario ciblé réellement réussi sur une troisième DB *_test supprimée ensuite.
Aucun code runtime modifié par cette précision de test. Aucun défaut WSL2 démontré par ces erreurs de commande/ordonnancement.

Limites : vue C07 minimale hors intégration React complète, erreurs/expiration/parcours/suivi après
logout à affiner C08 ; production/rotation/nettoyage/backups/recette de charge à C09 et lots prévus.
Pas de commande Colony ni preuve de gameplay sous panne Portal (5D), support/MFA totale, modes ou
Empire partagé ajoutés. Pas de Safari/Firefox, appareil physique, lecteur d’écran ni charge hostile
attestés. Q48/Q49/Q55 conservées. C07 livré ; C08/C09 nécessaires avant clôture 5C, PR #7 brouillon,
aucun merge autorisé. CI propre au commit à observer après publication et consigner dans la PR.

### Collaboration multi-agents — documentaire, 2026-10-30

Instruction utilisateur : valider les quatre corrections de l’analyse du 30/10 et formaliser la
collaboration ChatGPT Work / Codex / Claude Code, sur la branche de PR #7, sans nouvelle branche ni
fusion. Agent : Claude Code local (WSL2). GitHub relu avant modification : PR #7 OPEN/brouillon, tête
locale/distante 7a00c7ba656a22aca67e47f758b1d99ebfa54b5e, base master 63bb7d1, arbre propre.

**CI de C06 observée sur 7a00c7b** : push 41098495003 et pull_request 41098504081 completed/success,
jobs backend, frontend, portal-backend, portal-frontend et compose-smoke. Cette CI vaut pour 7a00c7b
seulement ; le commit documentaire suivant a sa propre CI, consignée dans PR #7 après observation.

Livré, documents seulement : [protocole commun](docs/06-handoff/work-codex-handoff.md) (rôles et
environnements, reprise, checkpoint « Reprise rapide », revue croisée avec criticités/contestation/
revalidation, branches et worktrees, démarrage local avec Portal et smokes, vérifications Game+Portal) ;
CLAUDE.md important AGENTS.md sans duplication ; AGENTS généralisé aux trois agents, consignes PR #5
ramenées à l’historique ; renvois README/CONTRIBUTING/docs/DoD/index des décisions. Aucun code, test,
migration, dépendance, game_data ou configuration Docker modifié ; docs/visual-reference/ non suivi,
étranger à ce lot, laissé hors commit. Suite inchangée : C07, C08, C09 puis clôture de 5C.

Reprise Codex : modifications documentaires apparues pendant le démarrage C07 ; écritures suspendues,
puis utilisateur confirme que Codex peut reprendre seul. Modifications Claude préservées, check_docs
et diff relus par Codex ; publication documentaire séparée. C07 local en cours et non validé à ce
checkpoint, aucun code C07 inclus dans ce commit. Le dossier visuel a entre-temps été intégré par
Codex dans 2286c35 ; la mention « non suivi » ci-dessus décrit le début du travail Claude.

### Références visuelles — checkpoint documentaire avant C07, 2026-10-30

Instruction utilisateur jointe : intégrer les six PNG déjà présents sous docs/visual-reference,
sans modifier les images, puis poursuivre C07. GitHub relu : PR #7 OPEN/brouillon, tête 7a00c7b,
base master 63bb7d1 ; fetch/ff-only sans changement. CI push 41098495003 et PR 41098504081 success.
Seul ajout local préexistant : dossier visuel non suivi, dont le README était vide ; conservé et intégré.

README visuel créé : direction cible, mapping des six écrans, principes, ordre d’autorité et usage
agents/responsive ; section opérationnelle AGENTS et lien dans docs/README. Images inspectées,
PNG 1672×941 toutes présentes, noms attendus, octets conservés. Écarts explicités : population,
stabilité, piles de défenses, capacités/chiffres, catalogue, accélération et navigation illustratifs
ne remplacent ni règles produit, ni game_data, ni UX canonique. Aucun code/CSS/contrat/Qxx changé.

Validation réellement exécutée : python3 scripts/check_docs.py (72 documents et liens),
git diff --check ; chemins des six PNG vérifiés et empreintes conservées. Aucun test fonctionnel
relancé pour ce seul checkpoint documentaire. Branche existante conservée, aucune fusion.
Suite autorisée : cadrage technique puis implémentation C07 selon 5B, sans 5D.

### C06 — lobby et contrôle privé Portal→Game, 2026-10-30

Instruction utilisateur « Continue » après C05. GitHub réel relu : PR #7 OPEN/brouillon, tête locale/
distante 348d0a0cb23d7ef6ef789bd0ed051d64569a972c, master/base
63bb7d1c902e9c0fbae3497d4a36c107a80eb611. Fetch/ff-only déjà synchronisés, arbre propre, branche
work/step-5c-portal-account-lobby conservée. CI C05 push 41071464090 et PR 41071472286 success
observées ; dernier travail publié Codex local C05, aucune autre tête ou modification concurrente.
Pas d’agent délégué, nouvelle branche, merge ou 5D. Périmètre C06 présenté avant code substantiel.

[Canonique C06](docs/03-technical/portal-game-control.md), schéma versionné contracts/portal-game/v1 :
références/memberships/outbox Portal, droits/bindings/ledger/epochs Game, aucune connexion SQL
Portal→Game. Migration Accounts p0005_control (trois tables), Game 0005_game_access (cinq tables),
révisions précédentes immuables et downgrade peuplé refusé. Aucun domaine Colony/simulation,
game_data ou frontend Game modifié ; aucune API gameplay ni GameSession anticipée.

Processus privé du même monolithe Game : game-control, TLS 9443 sans port hôte ; l’API publique
ne monte pas /internal. mTLS obligatoire puis empreinte du certificat réellement vérifié extraite
par l’adaptateur H11 Uvicorn et épinglée au service portal-control. Aucun header/forwarded scheme
ne prouve l’identité ; autorisation avant lookup de résultat. PKI dev séparée, CA clés privées
réservées à init, feuilles Game/Portal dans volumes propres RO ; aucune clé client Portal dans Game.
PORTAL_CONTROL_TARGETS explicite, vérification CA/nom DNS, pas de redirect/fallback HTTP. Nouveau
worker Portal/pool/réseau propre, aucun besoin des clés email/TOTP. CPU/charge hostile non attestés.

Intention + snapshot complet + livraison dans transaction Accounts ; effet + déduplication + résultat
immuable dans transaction Game. Révision inférieure ignorée, identique contradictoire refusée ;
état/bindings modifiés exigent access_epoch supérieur, renouvellement inchangé ne révoque pas.
Portal_confirmed_at/valid_until originaux conservés lors de retries/réconciliation ; huit heures
non glissantes, confirmation future refusée, ancien grant ne ressuscite pas un accès suspendu.
Game valide les Empires/scopes/FK et permissions explicites ; aucun owner, rôle ou droit par défaut.

Timeout après commit : receipt de même opération récupérable ; aucun nouvel identifiant ou date sur
retry. Acquittement validé/atomique, reçu ancien ne rabaisse pas la projection. Réconciliation
inférieur/absent relivre le même état ; supérieur/contradictoire reste pending pour investigation,
aucune intention Portal adoptée depuis Game. Sources C03–C05 durablement matérialisées par cible,
revocation acknowledged seulement après tous les acquittements ; compte/appareil indépendants.
Une source déjà matérialisée mais non acquittée ne bloque pas les sources suivantes. Tombstones/
ledger distincts de l’audit 90 jours. Branchement aux véritables sessions et portée session : C07.

Lobby : seulement ses participations, état vide réel, pending/applied/expiration/statuts et dates,
aucune entrée disponible avant handoff. GET sans activité/renouvellement, refresh volontaire classé
serveur. Message après logout prudent, acquittements consultables au lobby connecté ; suivi anonyme
complet à C07/C08. Orchestration technique via shell Accounts pour opérateur déjà autorisé, UUID et
bindings explicites ; aucune route publique create/join, génération jouable ou fixture runtime.

Validations réellement exécutées :

- Ruff backend/scripts/Portal, format des ajouts ; **112 tests Game** (101 antérieurs + 11 C06) et
  **105 tests Portal** (93 antérieurs + 12 outbox/lobby), aucun ignoré, bases dédiées
  echosphere_c06_game_test/echosphere_c06_accounts_test. Concurrence, ordre, scopes/FK, replay/conflict,
  durée, rollback, fan-out sans famine/abandon sur retrait de cible, receipt invalide/perdu, réconciliation et lecture sans activité.
  Roundtrips/absence de dérive et downgrade peuplé refusé ; warning Starlette/httpx connu.
- Frontend Portal npm ci/lint, **24 tests**, build et **14 Chromium** réussis ; état vide/pending/
  acquitté, erreur privée masquée, refresh clavier 320/1440, nom long sans débordement, captures
  inspectées. API interceptée distincte du transport réel ; parcours C01–C05 préservés.
- Connexion mTLS réelle du worker vers listener réussie. Recette control dédiée : deux bases *_test,
  réseau/listener/volume temporaires ; client Portal n’utilisant que sa DB et le HTTP Game. Clients
  sans certificat/mauvaise CA/certificat non épinglé même CA, nom DNS erroné/header forgé refusés ;
  contrat/corps refusés, provisionnement/accès réel, acquittement perdu et récupéré, ancien grant sans
  résurrection, révocations et réconciliation. Ressources temporaires supprimées, volumes conservés.
- Docs : 71 références/liens, Q01–Q56 et décisions 5B sections 1–8 inchangées. ADR 0008 : statut de
  réalisation partielle actualisé, aucune décision modifiée. Secrets/périmètre et diff relus.

Recette finale Compose config/build/up --wait et trois smokes réussis : Game, Portal HTTPS/CORS/
pannes croisées, contrôle mTLS/livraison sur bases temporaires. Accounts p0005_control et Game
0005_game_access sans dérive ; migrations/init Exited(0), bases/APIs/frontends/Mailpit healthy et
workers/listener running. Volumes et confiance CA/hosts hôte préservés ; bases conservées sans
fixture de compte/univers ajoutée. Les deux bases de suites sont supprimées après validations.
Tête C06 : commit portant ce checkpoint ; SHA publié et CI exacte à consigner dans PR #7 après
observation, aucune CI configurée présentée comme exécutée. Environnement Docker/WSL2 fonctionnel
pour ces recettes, aucun parcours Windows graphique revendiqué.
Interruption puis reprise sur instruction « Reprend » : la revue automatique a échoué sur limite
d’usage, sans rejet de sécurité. Aucun contournement ; contrôle repris après rétablissement. Les
105 tests Portal déjà lancés ont été relus comme réussis, puis recette finale du worker relancée.
Échecs intermédiaires corrigés : Compose refusait network_mode et networks simultanés pour init
(réseau interne conservé), format/imports Ruff, header de certificat brut avec retours ligne invalide
pour le test HTTP forgé (valeur synthétique non secrète), erreurs de sous-processus désormais expurgées
pour ne pas imprimer environnement/arguments. Aucun échec présenté comme recette réussie.

Limites : feuilles PKI dev 30 jours sans renouvellement silencieux, rotation et configuration
production/C09/Q49 à préparer ; adaptateur H11 lié à Uvicorn figé. Pas de handoff/GameSession,
commande Colony, parcours complet navigateur HTTPS→partie, charge hostile, perte physique de DB ou
restauration sauvegarde testés. Q48 support, Q49 email/configuration et Q55 modes inchangés. Suite
**C07 handoff sécurisé et GameSessions**, puis C08/C09. 5C non terminé, PR #7 reste brouillon ;
aucune fusion ni implémentation 5D.

### C05 — MFA TOTP/WebAuthn et récupération limitée, 2026-10-30

Instruction utilisateur « Vasy enchaine » après C04. GitHub réel relu avant modification : PR #7
OPEN/brouillon, tête locale/distante de45031169b09774c75028239e522cee3bcea68b, master
63bb7d1c902e9c0fbae3497d4a36c107a80eb611. Arbre propre, fetch et ff-only déjà synchronisés.
CI C04 push 41061047172 et PR 41061054401 completed/success, cinq jobs chacun observés. Dernier
travail publié : Codex local C04 ; aucune autre tête publiée ni agent concurrent identifié. Même
branche work/step-5c-portal-account-lobby ; aucune fusion, nouvelle branche ou implémentation 5D.

[Canonique C05](docs/03-technical/portal-mfa.md) : MFA joueur facultative, TOTP unique/cinq WebAuthn
nommables, vrais facteurs requis au login et step-up par action. PyOTP 2.10, py_webauthn 2.8 et
@simplewebauthn/browser 14 ; aucune crypto de vérification maison. TOTP 160 bits/six chiffres/30 s,
±1 pas et dernier pas consommé sous verrou User ; WebAuthn challenge 256 bits/cinq minutes, RP/origine
exacts, UV obligatoire, compte/session/action/paramètres/epoch liés, clés publiques/compteur seulement.
Secrets TOTP chiffrés avec clé MFA distincte de la clé email, fichiers privés hors Git et DB.
Dix secours aléatoires 160 bits, empreintes seules, affichage à génération en mémoire, jamais logs
ou stockage navigateur. Régénération invalide tout l’ancien jeu.

Effets 5B préservés : activation/réduction/remplacement/désactivation/récupération révoquent globalement ;
ajout d’un facteur et régénération volontaire avec facteur existant conservent sessions et epoch.
Audit/notices pour toutes ces modifications ; les notices sans secret n’annoncent pas de déconnexion
obligatoire pour ces deux opérations. Facteurs/preuves/secours/génération/intention Game/notices
atomiques sous verrou User ; refus ou erreur ne laisse pas d’effet partiel.

Récupération : mot de passe + secours unique + pré-auth/CSRF, cookie opaque distinct limité 15 min,
aucune PortalSession ni autorité compte/Game/admin. Facteurs perdus invalidés dès entrée ; MFA reste
exigée. Restauration du facteur, nouveau jeu de secours et connexion normale obligatoire. Perte
totale bloquée sans procédure approuvée. Privilèges : WebAuthn obligatoire (deux en production),
TOTP insuffisant ; récupération doit réenrôler WebAuthn et conserve un verrou privilégié persistant,
sans endpoint de levée ni procédure support inventée. Aucun privilège attribué par une API publique.

Intégration C04 : step-up avec facteur existant et assurance recontrôlée, email MFA avec preuve forte
remplaçant celle de l’ancienne adresse, nouvelle adresse toujours à confirmer en une heure commune ;
reset mot de passe autorisé sans retirer les facteurs, aucune reconnexion/MFA bypassée. Cooldown
progressif persistant 100→1000 ms configurable en plus des quotas compte/IP/opération ; refus avant
échéance sans délai repoussé, pas de verrou permanent. Échecs connus audités sans preuve privée,
audit 90 jours distinct des compteurs et générations anti-rejeu. Worker efface les seeds provisoires
expirés et purge challenges/capacités/cooldowns expirés ; notifications email locales seulement.

Migration additive Accounts p0004_mfa : six tables facteurs/secours/challenges/récupération/cooldown,
assurance sur step-up/demande email et verrou de récupération privilégiée User. Révisions publiées
p0000–p0003 immuables, aucun backend/frontend/game_data Game modifié. Migration et downgrade vide
testés uniquement sur Accounts echosphere_c05_test, créée puis supprimée après la recette ; aucun downgrade/volume supprimé sur données à garder.

Validations locales réellement exécutées sur C05 :

- Ruff Portal et backend/scripts, format vérifié ; **93 tests backend Portal réussis, aucun ignoré**,
  PostgreSQL dédiée RUN_DB_TESTS=1. Dix-huit scénarios MFA : signatures réelles/RP/origine/UV/rejeu,
  TOTP et secours concurrents, scopes/action/expiration, plafonds, transaction interrompue, récupération
  sans autorité normale, privilèges bloqués, email avec MFA, notices/cooldown/purge et activité serveur.
  Warning Starlette/httpx connu ; aucun vérificateur cryptographique simulé.
- npm ci/lint, **21 tests frontend**, build TypeScript/Vite et **12 Chromium** réussis. Bibliothèque
  WebAuthn réelle avec authentificateur virtuel et API interceptée : enrôlement puis connexion à
  320 px, aucune donnée privée en stockage navigateur. Captures inspectées ; autres parcours
  préservés, clavier/same-site et absence de débordement. Métadonnées inchangées du lockfile npm
  préservées, npm ci vérifié après nettoyage de ce diff.
- Compose config/build/up --wait, Accounts **p0004_mfa** et Game **0004** sans dérive ; init des
  deux clés privées sans écrasement de l’existante. Bases/APIs/frontends/Mailpit healthy, workers
  running, migrations/init Exited(0). Smokes Game et Portal/TLS réellement réussis, avec reprise
  après pannes des bases ; volumes préservés, aucun changement de confiance CA/hosts hôte.
- **70 documents/liens**, git diff --check et revue de confidentialité/périmètre. Lignes Q01–Q56,
  décisions sections 1–8 identity-contracts, ADR et code/données Game comparés inchangés à de45031.
  Base conservée vérifiée sans User ; aucun compte de démonstration ni donnée runtime ajoutée.

Tête C05 : commit portant ce checkpoint ; SHA publié et CI exacte à consigner dans PR #7 après
observation. La configuration du workflow ne vaut pas résultat exécuté. Limites :
pas de parcours complet navigateur HTTPS → vraie API → authentificateur matériel, de test téléphone
physique/Safari/Firefox/lecteur d’écran, de charge hostile ou délivrabilité publique attestés ; C09
reste nécessaire. Outils exécutés en conteneurs Docker depuis WSL2 ; Python/Node hôtes non utilisés.
Aucun blocage WSL2/Docker restant ; le refus DNS du réseau interne était attendu par son isolation.

Les suites intermédiaires 85, puis 90/91, 92 et 93 tests sont
distinguées des vérifications finales. Échecs intermédiaires corrigés : cooldown absent des horloges
de tests anciens, collecte Docker sans module local, dépendances tentées sur réseau Accounts interne
sans DNS externe (installation déplacée dans une image préparée avant isolation), quota horaire
atteint par le scénario d’enrôlement massif (quota élevé seulement dans ce test de plafond), imports/
longueurs Ruff et mocks d’interface consommés par la nouvelle lecture MFA. Aucun échec présenté réussi.

Suite : **C06 memberships/lobby et interface interne privée mTLS**, puis C07 handoff/sessions Game.
Intentions Game toujours pending : aucun transport/acquittement ni nouvelle fenêtre de huit heures.
Q48 support, Q49 fournisseur/configuration production et Q55 modes restent différés. 5C non terminé,
PR #7 reste en brouillon ; 5D non commencé et aucune fusion autorisée.

### C04 — opérations sensibles sans MFA, 2026-10-30

Instruction utilisateur « enchaine » après C03. État réel relu avant modification : PR #7 OPEN/
brouillon, tête locale/distante d752f8e429f6a9a6deede04baf67d6eb020380f8, base master
63bb7d1c902e9c0fbae3497d4a36c107a80eb611. Arbre propre, fetch et merge ff-only déjà synchronisés ;
CI C03 push 41057087993 et PR 41057096982 success observées. Même branche
work/step-5c-portal-account-lobby, aucun agent délégué ou autre tête publiée détecté, aucune fusion.

[Canonique C04](docs/03-technical/portal-account-security.md) : step-up mot de passe actuel par
session/action/paramètres, cinq minutes absolues et usage unique. Liaison HMAC avec le secret de
session, aucun mot de passe ou checksum non salé en DB. Changement volontaire, reset 30 min/dernier
jeton unique, changement email deux confirmations liées/une heure commune et déconnexion globale.
Toutes PortalSessions révoquées y compris courante après succès sensible, step-ups invalidés,
intention Game globale/epoch monotone et notifications sans secrets persistées dans la transaction.
Reset/changement mot de passe annule l’email pending ; email changé invalide anciens resets et
vérifications. Identité globale conservée, aucune connexion automatique ou restauration d’email.
La demande email reste pending jusqu’aux deux preuves ; session à l’origine encore valide requise.

Migration Accounts additive p0003 : step_up_grants/password_reset_requests/email_change_requests/
account_revocations/security_email_outbox, génération globale et guards de politique User. Flags
MFA/privilégié n’accordent aucun privilège : login/password-only et mutations refusés si actifs,
demande reset générique sans lien ; preuves réelles C05 obligatoires avant ces variantes. Aucun
MFA/administrateur fictif, support inventé ou nouvelle décision produit. Consommateur Game C06/C07
absent : révocations pending, UI fidèle sans promesse distante instantanée ni nouveau délai huit heures.
Le login relit génération/adresse/credential après lock, refus d’une connexion ancienne en vol.

Worker local : seconde file de sécurité chiffrée Fernet, destinataire/IDs/type/token vérifiés,
retry sans extension et effacement après SMTP/annulation/expiration, alternance des files sans
starvation. Notifications à l’ancienne/nouvelle adresse avec lien non secret de parcours sécurité,
pas de credential/token sensible. Mailpit local seulement ; fournisseur/production Q49 inchangés.
UI : récupération, fragments retirés immédiatement, nouvelle saisie/confirmation du mot de passe,
paramètres sensibles, deux confirmations email, logout global et nouvelle connexion explicite.
Réponses privées invalides non affichées, aucun secret en stockage navigateur. Aucune fixture runtime.

Validations locales réellement exécutées (images Python 3.12 / Node 22) :

- Ruff backend/scripts réussi et **75 tests backend Portal réussis, aucun ignoré**, base dédiée
  echosphere_c04_test créée/supprimée. Scopes de preuves, exacts 5/30/60 min, deux resets/confirmations
  concurrents, réémission et invalidations croisées, unicité d’adresse sans fusion, rollback complet
  si notification échoue, garde MFA/privilèges, logout global vs login en vol, SMTP retry/expiry/
  payload effacé et deux workers ; suites C02/C03 conservées.
- Migrations/check/roundtrip et refus de downgrade peuplé sur cette base uniquement. P0003 générée
  depuis le schéma dédié p0002 puis relue/complétée (checks/guard). Aucun downgrade de base conservée,
  révision publiée p0000–p0002 ni migration Game modifiée. Pas de nouvelle dépendance.
- Frontend : npm ci, lint sans warning nouveau, **18 tests**, build et **11 Chromium** réussis.
  Récupération/double confirmation 320/1440, login/refresh/logout et anciennes recettes conservés,
  clavier et absence de débordement/stockage navigateur ; captures inspectées. API UI interceptée,
  distincte des intégrations API/PostgreSQL et du SMTP TCP réel couvert dans la suite conservée.
- Compose config/build/up --wait, Alembic check Accounts p0003 et Game 0004 sans dérive ; deux
  smokes réellement réussis avec TLS strict, CORS/refus, cookie/challenge, pannes indépendantes et
  reprise. Volumes préservés, aucune confiance CA/hosts modifiée. Base Accounts conservée sans User.
- **69 documents**/liens valides, git diff --check et confidentialité/périmètre relus. Lignes Q01–Q56,
  sections de décisions 1–8 identity-contracts et ADR 0008 comparés inchangés à d752f8e ; aucun
  backend/frontend/game_data Game modifié. Statuts d’implémentation seulement actualisés.

Échecs intermédiaires corrigés : collecte pytest avec deux noms de fichier identiques (nouveau
fichier renommé), imports/variable/format Ruff, droits du fichier migration généré root dans Docker
rétablis sur ce seul fichier, warning Fast Refresh résolu par extraction du helper, débordement
select/form à 320 px détecté par Chromium puis corrigé et recette complète relancée. Les passages
en échec ne sont pas présentés comme réussis. La première suite complète 73 backend a précédé
les deux derniers cas ajoutés, puis le passage final 75 a réussi.

CI de cette tête à observer après commit/push, puis résultat/SHA exacts à consigner dans PR #7 ;
la configuration du workflow inchangée ne vaut pas preuve exécutée. Suite : **C05 MFA TOTP/WebAuthn,
secours/récupération et preuves renforcées**, selon les contrats validés. C04 est livré sans MFA ;
aucune route MFA utilisable sans preuve. Livraison Game C06/C07 et recette complète C09 restent futures.
Limites : pas de navigateur hôte HTTPS complet, Windows/tactile/lecteur d’écran, charge/DDoS ou
remise email publique attestés. Plancher anti-énumération 150 ms, pas de temps constant garanti en
charge. Intention Game pending, support Q48/configuration Q49/modes Q55 conservés. Outils en Docker
WSL2 utilisables pour ces commandes ; pas de nouvelle branche, merge, déploiement ou début de 5D.

### C03 — connexion, appareils et sessions Portal, 2026-10-30

Instruction utilisateur « On poursuit » après C02. GitHub réel vérifié avant modification : PR #7
OPEN/brouillon, tête locale/distante 2025490b2e51f62519125bf2c859ebfc4cc9c3ba, base master
63bb7d1c902e9c0fbae3497d4a36c107a80eb611. Fetch et merge ff-only : déjà synchronisée, arbre propre.
CI C02 push 40942091538 et PR 40942099627 success observées. Dernier lot attesté : Codex local C02 ;
aucune autre tête publiée ni agent délégué. Même branche work/step-5c-portal-account-lobby, pas de merge.

Livré : [C03 canonique](docs/03-technical/portal-sessions.md), modules Portal sessions/API, migration
Accounts p0002 additive (browser_profiles, account_devices, portal_sessions, login_challenges,
logout_requests), login/challenge, cookies __Host- Secure/HttpOnly/host-only/SameSite Strict,
CSRF lié au secret/challenge, rotation sans report de l’absolu. Sessions Portal sept jours absolus /
72 h inactives, vérification avant activité, aucune résurrection. GET/bootstrap/readiness/flags client
ne comptent pas ; action explicite de navigation/actualisation dédiée avec CSRF. Profil navigateur
opaque, cap initial dix appareils configurable, comptage concurrent sous verrou User et aucune
éviction silencieuse. Même profil/onglets partagent la session ; cookies effacés ne révoquent pas
l’ancien état serveur. Quotas login/bootstrap persistants et distincts des demandes email.

Déconnexion ciblée : Portal révoqué + intention Game appareil/compte/session/epoch atomique. FK
composites et génération monotone ; répétition sans nouvelle génération ni cible étrangère. Aucun
transport/acquittement Game encore implémenté : état pending/UI fidèle, consommateur et tests
inter-plans C06/C07 futurs. Pas de logout tous appareils sans step-up futur, aucun reset/changement
email/MFA/membership/handoff/commande Colony dans C03. Les comptes non vérifiés peuvent accéder à
ce Portal minimal, jamais à Game (aucun handoff disponible). Aucune identité/partie runtime fictive.

Frontend : connexion, erreurs/cap avec action possible, connexions actives, actualisation volontaire
et fermeture ciblée. CSRF uniquement en mémoire, aucun stockage navigateur. Rotation dans un autre
onglet : relecture de la preuve sans rejouer l’action refusée ; réponse automatique tardive antérieure
à la connexion ignorée. Présence d’un onglet ou bootstrap automatique sans maintien de session.
Documentation/indexs/AGENTS/context/roadmap/passation et smoke TLS mis à jour ; contrats de décisions
5B et lignes Q01–Q56 inchangés, seuls statuts d’implémentation actualisés. Aucun code/dépendance ou
migration Game modifié ; p0000/p0001 Portal et ADR 0008 inchangés. Pas de nouvelle dépendance.

Tests locaux réellement exécutés dans les images Python 3.12/Node 22 :

- Backend : Ruff réussi ; **53 tests réussis, aucun ignoré** sur echosphere_c03_test dédiée,
  dont échéances exactes/rotation/non-activité, challenge concurrent unique, cap concurrent sans
  éviction, périmètres, FK de compte/session, génération monotone et rollback session/intention.
  Upgrade/check/roundtrip et downgrade peuplé refusé. Base jetable recréée lors de l’affinage de la
  migration encore non publiée, puis supprimée après recette ; aucune base conservée downgradée.
  Warning Starlette/httpx connu, sans échec.
- Frontend : npm ci, lint, **14 tests**, build et **9 scénarios Chromium** réussis : parcours C02
  préservés, login/refresh explicite/logout 320/1440, quatre largeurs clavier/retry et same-site natif.
  Captures inspectées ; UI à API interceptée distincte des tests HTTP/API/PostgreSQL.
- Compose initialement arrêté hors workers, remis en marche par up --build --wait ; volumes et
  données préservés. Deux bases/APIs/frontends/Mailpit healthy, workers running, migrate et
  secrets-init Exited(0). Alembic check Portal p0002 et Game 0004 sans dérive.
- smoke_compose.py et smoke_portal_compose.py réussis : TLS strict/noms, routage, CORS et pannes
  croisées/reprises. Extension C03 vérifie challenge/cookie sous TLS et refus sans session/mauvaise
  origine ; aucun compte créé, seulement des challenges anonymes expirables. Base Accounts
  conservée vérifiée à zéro User. Aucun changement hosts ou magasin de confiance hôte.
- 68 documents requis/liens valides, git diff --check sans erreur ; Qxx et décisions 5B comparées à
  2025490, aucun fichier Game ou migration Portal déjà publiée modifié. Secrets/artefacts exclus.

Échecs intermédiaires corrigés : format/tri/longueur Ruff et option Testing Library non typée dans
un test frontend (tests alors verts, build TypeScript en échec ; nouveau build réussi ensuite).
Aucune suite en échec n’est présentée comme passée. Source CI configurée inchangée, résultats de
la nouvelle tête à observer après commit/push puis consigner dans PR #7 avec son SHA effectif.

Limites : pas de recette complète navigateur hôte HTTPS, Windows/tactile/lecteur d’écran ou charge
attestée. Smokes TLS réels et scénarios UI interceptés sont séparés. Logout Game reste pending jusqu’à
C06/C07, aucune révocation distante annoncée instantanée ; procédures/fournisseur production Q49,
support Q48 et modes Q55 inchangés. WSL2/Docker utilisables pour les commandes exécutées, outils en
conteneurs jetables. Suite : **C04 opérations sensibles/step-up**, itérative avec C05 MFA selon le
plan ; aucune route sensible utilisable sans ses preuves. 5D exclu, PR #7 reste en brouillon.

### C02 — comptes et vérification email, 2026-10-29

Instruction utilisateur « enchaine » après livraison de C01. Reprise GitHub : PR #7 OPEN/brouillon,
branche/base/tête work/step-5c-portal-account-lobby / 63bb7d1c902e9c0fbae3497d4a36c107a80eb611 /
79500f65728ef14a302b8e400f3f43e05792517f, arbre propre et branche synchronisée après fetch.
CI C01 push 40935556492 et PR 40935563025 relues success, cinq jobs chacune. Pas d’agent délégué.

Livré : [C02](docs/03-technical/portal-registration.md), comptes UUID stables/credentials Argon2id,
inscription et vérification initiale 24 h unique, renvoi invalidant l’ancienne génération. Mot de
passe requis à la confirmation/au renvoi contre la préinscription par un tiers. Réponses non
énumérables, pas d’auto-login. Contrôle Pwned Passwords par préfixe HTTPS/padding, panne refusée 503.
Migration Accounts p0001 additive (six tables) ; création credential/preuve/outbox/audit atomique,
quota PostgreSQL distinct/concurrent, erreurs sans entrée privée, Origin/JSON stricts et corps borné.
Outbox Fernet, clé privée persistante Docker hors Git, retry sans extension de validité, payload
effacé après SMTP/annulation/expiration. Worker dédié + récepteur Mailpit isolé sans relais externe.
UI du récepteur via local-edge sur loopback 8025 ; SMTP reste réseau interne sans port publié.
Première tentative de publication directe du port Mailpit sur réseau interne inaccessible localement ;
corrigée par ce proxy, puis vérifiée réellement. Volumes et données Game conservés.
Formulaires Portal inscription/renvoi/confirmation, token de fragment retiré immédiatement de l’URL,
secrets uniquement en mémoire, mobile/clavier. Aucune connexion/session/MFA/membership/handoff,
fixture runtime, compte créé dans la base conservée ou API Colony. C03 est la suite ; 5D exclu.

Choix techniques sous délégation 5B, sources primaires dans C02. Argon2id 64 MiB/3 passes/p1 : cinq
calculs hash+verify successifs, médiane locale 160 ms dans l’image Python 3.12 (pas une mesure de
charge production). Appel réel Pwned Passwords avec mot de passe jetable généré : réponse reçue,
non compromis, aucune valeur privée imprimée. Aucun fournisseur email de production sélectionné.

Validations locales exécutées :

- Backend Portal : Ruff réussi et **36 tests réussis, aucun ignoré**, dont intégrations sur
  echosphere_c02_test dédiée : upgrade/check/roundtrip, refus de downgrade peuplé, atomicité,
  inscriptions/confirmations/renvois/quota concurrents, expiration exacte, SMTP TCP réel en panne
  puis reprise, deux workers et effacement des payloads. Base de test supprimée après recette.
  Passage initial sans opt-in : 16 réussis/17 ignorés avant les deux derniers tests ajoutés,
  distinct de la suite complète. Warning Starlette/httpx connu, sans échec.
- Frontend Portal : npm ci, ESLint, **8 tests** et build réussis. Chromium jetable Node 22/Debian :
  **7 scénarios réussis**, quatre largeurs clavier/retry, same-site natif, formulaires inscription/
  renvoi/confirmation 320 et 1440, fragment retiré et absence de stockage navigateur ; captures
  320/1440 inspectées. API UI interceptée ; intégrations API/PostgreSQL/SMTP testées séparément.
- Compose config/build/up --wait réussis ; Game et Accounts sans dérive Alembic ; deux smokes
  réellement passés, TLS strict/noms/routage/CORS et pannes indépendantes avec reprise.
  Aucun downgrade de base conservée, suppression de volume, modification hosts ou magasin CA.
- Documentation : 67 documents requis/liens valides, diff sans whitespace ; tables Q01–Q56 et
  sections de décisions 5B conservées, seulement statuts d’implémentation actualisés. Aucun code,
  dépendance ou migration backend/frontend/game_data Game modifié. Secrets et artefacts exclus.

Échecs intermédiaires corrigés : import bootstrap TypeScript manquant ; tri/format Ruff ; parsing
Compose après insertion incorrecte ; premier pytest lancé sans installation de package dans une
image Python brute (relancé via python -m pytest). Aucun de ces passages n’est présenté comme réussi.
Première tête C02 d965ca9 : CI push 40941610709 et PR 40941616489 observées success, cinq jobs chacune
et journaux relus (101/11/5 Game, 36/8/7 Portal, deux smokes). Le journal a révélé une tentative
de contrôle de version Mailpit, bloquée par son réseau isolé : contrôle désactivé explicitement.
CI de cette correction de configuration à observer après push ; workflow configuré ne vaut pas résultat exécuté.
Résultat effectif/SHA publiés dans PR #7 après observation, sans boucle de commits de checkpoint.

Limites : SMTP au moins une fois, doublon possible après acceptation avant commit ; pas de remise
publique démontrée. Dépendance de contrôle de mots de passe externe, refus temporaire si indisponible.
Procédures de clés/production et fournisseur Q49 futurs ; support Q48 et modes Q55 inchangés.
Pas de recette navigateur hôte HTTPS, Windows/tactile/lecteur d’écran, charge ou DDoS attestée.
WSL2/Docker fonctionnels pour ces commandes ; outils Python/Node exécutés en conteneurs jetables.

### C01 — socle Portal séparé, 2026-10-29

Instruction utilisateur « alors go » après présentation du plan et confirmation qu’aucun arbitrage
ne bloque C01. Reprise : PR #7 OPEN/brouillon, tête/base 8122cf77d3fb00a8cd5d4c0fa332f42d9d1a2253 /
63bb7d1c902e9c0fbae3497d4a36c107a80eb611 ; fetch, branche synchronisée/propre. CI push 40930143792
et PR 40930208556 observées success. Aucun agent délégué ni travail concurrent détecté.

Livré sur work/step-5c-portal-account-lobby, pas sur master : portal/backend (FastAPI, config PORTAL_*,
engine/pool/metadata indépendants, sondes sans détails privés), Accounts PostgreSQL/rôle/secret/volume/
réseau propres, migration p0000_portal_baseline initialisant uniquement portal_alembic_version.
portal/frontend : écran de préparation responsive, readiness propre au Portal et retry explicite.
Compose garde les cinq services Game et ajoute portal-postgres/migrate/backend/frontend/local-edge.
Caddy : deux origines HTTPS locales, CA dans volumes Docker, admin et installation de confiance hôte
désactivées. Aucun compte, User, session, Argon2id, MFA, outbox, mTLS S2S ou API Colony ajouté.
Aucun changement game_data/migrations/services métier ou lockfile Game ; contrats et Qxx inchangés.

Tests locaux réellement exécutés dans les versions Docker prévues, sans Python/Node installés hôte :

- Backend Portal : Ruff portal_app/migrations/tests et scripts réussi ; premier pytest sans opt-in
  8 réussis/1 intégration ignorée ; passage complet 9 réussis/aucun ignoré sur base dédiée
  echosphere_c01_<identifiant>_test créée puis supprimée, aucun downgrade de la base conservée.
  Upgrade répété/check/downgrade/base/upgrade et timezone UTC vérifiés. Un warning Starlette/httpx.
- Frontend Portal : npm ci, ESLint, 4 tests et build réussis. Lock autonome, Vitest 4.1.12/Vite 7.3.7 ;
  npm audit initial 0 vulnérabilité. Génération du lock avec npm 12 après échec interne npm 10
  « edgesOut » ; consommation ultérieure par npm ci de Node 22 réussie, aucun outil installé hôte.
- Chromium Debian jetable : 5 scénarios réussis, dont 320/390/768/1440 clavier/focus/retry et absence de
  débordement et classement same-site des hôtes sur serveur local réel. Les hôtes définitifs
  portal.echosphere.localhost et game.echosphere.localhost ont un parent commun, conforme à 5B.
  Captures 320/1440 inspectées. Sondes interceptées pour les tests UI ; pas de recette
  graphique Windows, tactile ou lecteur d’écran. Captures hors Git.
- docker compose config --quiet et up --build --wait réussis ; bases/APIs/frontends healthy,
  worker Game running et migrations Game/Portal Exited(0). Caddy observé v2.11.7.
- smoke_portal_compose.py réussi : TLS strict avec CA publique en mémoire/noms vérifiés, deux
  origines/routage et CORS refusé, historiques séparés, panne Accounts sans panne Game puis inverse,
  reprises. smoke_compose.py Game réussi. Alembic check Portal et Game sans dérive, Game reste 0004.
  Volumes de données conservés, aucune CA installée dans Windows/WSL2.

CI étendue : jobs portal-backend/portal-frontend et smoke HTTPS ; jobs Game préservés. Documentation
opérationnelle [portal-foundation](docs/03-technical/portal-foundation.md), références et état courant
actualisés. Le code CI est une recette, pas encore une CI passée sur la nouvelle tête à ce checkpoint.
Checks finaux exécutés : 66 documents/chemins/liens valides, git diff --check sans erreur ; registre
Q01–Q56 et identity-contracts intégralement identiques à 8122cf7. Diff/périmètre/confidentialité relus,
aucun backend/frontend/game_data Game modifié, aucune clé/certificat/artefact privé staged.
Après publication, observer SHA/CI
propres et consigner leurs résultats exacts dans PR #7, sans nouvelle boucle de commits de checkpoint.

Limites : socle local, aucune auth implémentée ; UI Chromium HTTP et smoke TLS réel vérifiés séparément.
Pas de recette HTTPS navigateur hôte ni résilience de commandes Game futures, charge ou isolation
CPU/RAM. Dépréciations dev ESLint/whatwg-encoding et Starlette conservées sans échec ; avis Game
historiques inchangés. C01 ne ferme aucune Qxx supplémentaire. Prochain ticket : C02 comptes,
Argon2id/vérification email et livraison durable, selon 5B, sans choix de fournisseur production imposé.
5D non commencé ; PR #7 à actualiser et laisser non fusionnée.

### Synchronisation après fusion de PR #6 — 2026-10-29

GitHub réel : PR #6 était encore OPEN/brouillon sur 4b17c16494bc9949d3387ccbfb13a2359e74f59e,
malgré la formulation initiale de la demande ; CI push 40924593354 et PR 40924600793 completed/success.
Sur instruction explicite « Merge la PR6 », passage prêt pour revue puis fusion normale, tête attendue
contrôlée. Merge réel : **63bb7d1c902e9c0fbae3497d4a36c107a80eb611**, parents 8214e0b et 4b17c16.
Aucune branche supprimée. Fetch GitHub, bascule master, fast-forward vers origin/master et arbre propre
vérifiés. Nouvelle branche **work/step-5c-portal-account-lobby** créée directement depuis ce merge ;
branche 5B non réutilisée. CI master [40929141873](https://github.com/ThomasPerez91/Echosphere/actions/runs/40929141873)
observée completed/success sur le merge avant publication du checkpoint.

Premier travail de cette branche : références courantes README/context/progress, index docs,
identity-contracts, Qxx, roadmap/backlog, passation/lacunes/décisions, architecture/API/sécurité,
ADR 0008, AGENTS et DoD synchronisées avec l’intégration réelle. Les checkpoints antérieurs ci-dessous
restent des relevés historiques, leurs formulations de revue/brouillon ne décrivent pas le lot courant.
Q40–Q47, Q50–Q54 et Q56 clos pour le cadrage 5B ; reports Q48/Q49/Q55 inchangés. Aucune décision
5B modifiée, aucun compte/auth/Portal ajouté. Diff limité à la synchronisation documentaire.

Validations locales exécutées : `python3 scripts/check_docs.py` réussi, 64 documents/chemins/liens ;
`git diff --check` sans erreur. Q01–Q56 présentes exactement une fois ; toutes les lignes de décision
Qxx strictement identiques au merge. Sections métier 1–8, matrice d’acceptation 10 et sources 11 de
identity-contracts identiques au merge ; seules les mentions de statut/intégration changent.
Diff des 18 fichiers Markdown relu : synchronisation documentaire uniquement, sans décision nouvelle.
Tests backend/frontend, migrations et Compose non relancés pour ce diff documentaire ; aucune
implémentation 5C ni preuve d’authentification testée à ce stade.

Premier checkpoint publié : **1c2749773c3bb3cf7eedf9a0f4013b9ce7c8f98a**, tête distante relue et
arbre propre. CI [40929423582](https://github.com/ThomasPerez91/Echosphere/actions/runs/40929423582)
observée completed/success sur cette tête, jobs backend/frontend/compose-smoke réussis.

### Cadrage 5C présenté avant code substantiel — 2026-10-29

Après publication du premier checkpoint, analyse du dépôt réel (configuration/persistance Game,
migrations, services Colony, shell/Vite, Compose et dépendances). Nouveau
[plan 5C](docs/05-project/step-5c-plan.md) : sous-tickets C00–C09, tables/migrations Accounts séparées,
applications Portal backend/frontend, minimum d’accès Game nécessaire au handoff, frontière 5D et
reports. Plan technique et périmètre proposés pour présentation, pas décision produit supplémentaire.
C01 est le prochain incrément de code ; aucune implémentation substantielle dans ce checkpoint.

Limite de périmètre explicitée : le domaine 5A ne crée pas une partie complète. Lobby fondé sur
participations réelles, sans fixture/public join ; un bouton créant une partie jouable nécessiterait
cadrage de démarrage dédié avant implémentation, sans inventer les questions de modes/progression.
Reports Q48/Q49/Q55 inchangés. Les détails techniques restent délégués, pas de questionnaire par
paramètre. Cadrage documenté séparément du premier commit de synchronisation demandé.

Validation locale du cadrage exécutée : `python3 scripts/check_docs.py` réussi (65 documents et
liens), `git diff --check` sans erreur ; Q01–Q56 et toutes leurs lignes strictement inchangées depuis
le merge 5B, diff Markdown uniquement. Checks fonctionnels non relancés localement pour ces documents. Après publication, observer la CI de sa tête et consigner les résultats dans
la PR du lot. Prochaine action : présentation du plan à l’utilisateur avant code substantiel ; aucun
5D ni nouveau merge autorisé.

## Historique du lot 5B — contrats identité / Portal-Game consolidés

**Statut : 5B documentaire terminé, prêt pour revue finale de PR #6 sous réserve de la CI publiée.**
Contrats validés et non implémentés ; aucun début de 5C et aucun merge autorisé.

### Consolidation finale du bloc 5B — 2026-10-29

Objectif : intégrer la validation utilisateur de l’ensemble des quatorze points, avec trois corrections,
puis revue de cohérence de toute PR #6. Provenance : arbitrage utilisateur explicite, synthétisé dans
le canonique sans conversation brute. Environnement Codex local/WSL2, aucune délégation à des agents.

Reprise vérifiée : branche work/step-5b-identity-contracts propre et synchronisée depuis
10499b6f60f241a5fecc2cfd56c19ff7da548708 ; master/origin master inchangées sur
8214e0bd30a00bf0336264a428e6975d307350ba. PR #6 OPEN/brouillon vers master, non fusionnée ;
CI de départ push 40920709168 et PR 40920717330 completed/success sur 10499b6, trois jobs verts.
Fetch initial refusé par sandbox (.git en lecture seule), puis réussi avec autorisation ; aucun défaut
Git/WSL2 démontré. Aucun travail concurrent ni divergence distante détecté.

Résultat : canonique identity-contracts réécrit pour séparer décisions closes, détails techniques
explicitement délégués et reports. Registre Q40–Q56 consolidé sans renumérotation ni fermeture des
questions gameplay Q01–Q39 ; Q16 actualisée uniquement pour le cadrage identité/autorisation couvert.
Corrections prioritaires : pas de global systématique pour ajout MFA/régénération volontaire des
secours avec step-up existant ; caps 10 appareils/10 univers actifs configurables sans limite de
memberships ; APIs même origine et CORS credentials refusé par défaut, exceptions explicites minimales.
MFA/step-up/secours, compte/email, appareil, handoff/clés, S2S, synchronisation/révocation, permissions,
anti-abus et audit désormais cadrés. Aucun arbitrage produit supplémentaire inventé.

Décisions fermées dans le périmètre 5B : Q40–Q47, Q50–Q54 et Q56. Q48 : contrat MVP clos mais procédures
support renforcé joueur/privilégié différées, aucun déblocage sans approbation. Q49 : flux clos mais
fournisseur/domaines/configuration de production différés. Q55 : règles des modes futurs explicitement
différées ; Q19–Q29/Q21 préservées. Détails techniques délégués à 5C/5D avant code dépendant ; aucun
nouveau questionnaire par bibliothèque/paramètre, aucun bypass ou service payant implicite.

Fichiers : 22 Markdown de consolidation : identity-contracts, registre Qxx, ADR 0008/index, sécurité,
API, modèle, architecture, roadmap/backlog, UX, DoD, index docs/décisions/provenance, README/AGENTS/
context/progress et passation/lacunes. Revue de PR entière
contre master, pas seulement du dernier diff. Anciennes mentions ouvertes/proposées remplacées
pour décisions validées ; checkpoints historiques ci-dessous conservés et identifiés comme tels.
Aucun code métier, test, migration, game_data, dépendance ou Compose modifié par cette consolidation.
Le script check_docs.py déjà changé au début de PR #6 reste limité à son document requis ajouté.

Validation locale exécutée : `python3 scripts/check_docs.py` réussi (64 fichiers, chemins requis et
liens locaux), `git diff --check` sans erreur. Vérification ponctuelle du registre : Q01–Q56 exactement
une fois ; lignes Q01–Q39 identiques à la tête de reprise sauf cadrage Q16 ; toutes Q40–Q56 séparent
clôture/délégation/report. Consolidation Markdown seulement ; PR complète = 22 Markdown + unique ajout
REQUIRED identity-contracts de check_docs.py. Diff complet contre master relu, confidentialité et
renvois/statuts obsolètes contrôlés ; aucune revue ou discussion inline existante sur GitHub.
Après commit/push, relire SHA distant et observer sa propre CI ; résultats exacts à consigner dans
la description de PR #6 après exécution, sans nouvelle boucle de commits de checkpoint.
Aucun test fonctionnel Portal/MFA/GameSession exécuté,
ces mécanismes étant absents. Suites fonctionnelles locales et Docker non relancés pour le diff
documentaire ; les résultats de reprise antérieure restent historiques et distincts.

Prochaine action : revue finale de PR #6 ; fusion uniquement sur instruction. 5C n’a pas commencé.
Après intégration et lot distinct autorisé : cadrer l’incrément compte/lobby 5C, appliquer les détails
techniques délégués et prérequis de son périmètre ; 5D pour l’accès Colony interactif et résilience.

## Historique des checkpoints 5B — superseded pour les statuts ouverts

Les sections suivantes conservent l’état et les preuves à leur date. Les formulations « prochain
arbitrage », « proposition » ou « question ouverte » décrivent ces checkpoints, pas le contrat final
ci-dessus. Les décisions actuelles et reports font foi dans identity-contracts et le registre Qxx.

### Facteurs et récupération MFA Q48 — 2026-10-29

Source : arbitrage explicite utilisateur pour PR #6. Non implémenté : TOTP/WebAuthn MVP, joueur
choisit l’un ou les deux ; un seul secret TOTP actif, remplacement sans accumulation ; jusqu’à
5 credentials WebAuthn nommables. Privilèges plateforme : WebAuthn obligatoire et preuve WebAuthn
sur opérations sensibles, TOTP complémentaire seulement ; prévoir deux WebAuthn en production.
Secours : autre facteur enregistré et codes uniques, générés à activation, régénération invalidant
anciens ; robustes, vérification sans secret exploitable stocké en clair, jamais journalisés.
Perte totale : support renforcé à définir, aucun bypass email/mot de passe. Secours privilégié :
état de récupération sans droits admin, WebAuthn réenregistré + procédure privilégiée requis.
Changements audités et step-up via facteur disponible, identité/gameplay conservés. Q48 reste
partiellement ouverte : crypto/RP, stockage TOTP, format/nombre des codes, support final, effets
sur sessions et step-up détaillé. Aucune autre Q fermée ni mécanisme implémenté.

Reprise : fetch, work/step-5b-identity-contracts propre/synchronisée sur
830f3e41e04daa2a8723707bd9f79555438b1c1f ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête vérifiée : push 40918608285 et PR 40918613929, backend/frontend/compose-smoke verts.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, décisions, références API/ADR/index/
passation/lacunes. Critères futurs : limites en concurrence, secours uniques/régénération, refus
privilégié et audit. Aucun comportement futur testé. Checks locaux : docs/liens, diff, Markdown,
Q01–Q56 uniques et seule ligne Q48 modifiée. Suites backend/frontend/Compose et Ruff non relancées
localement ; observer nouvelle CI après publication et consigner résultats dans PR.
Prochain arbitrage : effets des changements/récupérations MFA sur sessions et fraîcheur/portée
step-up ; support final reste à spécifier sans bypass. Aucun merge ni démarrage de 5C.

### Périmètre MFA Q48 — 2026-10-29 (checkpoint antérieur aux facteurs)

Source : arbitrage explicite utilisateur pour PR #6. Q48 partiellement close, non implémentée :
MFA facultative joueurs MVP via paramètres, exigence normale après activation ; obligatoire avant
fonctions privilégiées plateforme/admin/opération, sans exemption interne ni assimilation aux
rôles Empire. Step-up des comptes équipés avant email, désactivation/remplacement MFA et moyens de
récupération ; logout tous appareils seulement éventuel. Sans MFA, Q40/Q49 inchangées. Identité,
memberships/empires/univers/gameplay conservés. Facteur/nombre, secrets, récupération/codes,
remplacement/réinitialisation et mécanismes précis step-up restent ouverts, aucune autre Q fermée.

Reprise : fetch, branche work/step-5b-identity-contracts propre/synchronisée sur
ce6353a8a4870103bd6d0f7fc696279c364b5d12 ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête vérifiée : push 40917882587 et PR 40917891299, backend/frontend/compose-smoke verts.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, décisions et références
API/ADR 0008/index/passation/lacunes. Critères futurs complétés pour périmètre MFA, refus privilégié
et step-up ; aucun comportement futur exécuté/testé. Checks locaux : docs/liens, diff, périmètre
Markdown et Q01–Q56 uniques, seule ligne Q48 modifiée. Suites backend/frontend/Compose et Ruff
non relancées localement pour ce diff documentaire ; observer CI du nouveau commit après push,
résultats consignés dans PR. Prochain arbitrage à ce checkpoint : facteurs/récupération,
depuis partiellement validés ci-dessus.
Aucune implémentation, console admin ou MFA anticipée, aucun merge PR #6 ni passage à 5C.

### Complément email : échéance, remplacement et sessions — 2026-10-29 (checkpoint antérieur à Q48)

Source : arbitrage explicite utilisateur Q40/Q49 pour PR #6. Non implémenté : demande active unique
par compte, maximum 1 h depuis création, échéance commune aux deux confirmations sans glissement.
Nouvelle demande invalide ancienne/liens/confirmations ; deux nouvelles preuves requises sans mélange.
Succès après toutes validations : adresse active, global_user_id et gameplay conservés ; toutes
sessions Portal/Game révoquées, courante incluse, tous appareils/univers ; connexion normale avec
nouvelle adresse. Notifications aux deux adresses sans credential/token sensible. Game injoignable :
intention persistée/rejouée jusqu’à acquittement, aucune instantanéité prétendue ni reset des 8 h.
Q40/Q49 partiellement ouvertes, mécanismes/fournisseur non choisis ; Q48/Q50/Q53/Q54 non fermées.

Reprise : fetch, work/step-5b-identity-contracts propre/synchronisée sur
a4cb854307cb022bfd907f59ea57c8709cca4835 ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête observée verte : push 40897245953 et PR 40897261938, backend/frontend/compose-smoke.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, décisions et références
API/ADR 0008/index/passation/lacunes. Critères futurs complétés pour échéance commune, remplacement,
non-mélange/concurrence, révocation globale/courante et panne sans extension ; aucun test de ces
mécanismes futurs exécuté. Checks locaux : docs/liens, diff, périmètre Markdown et Q01–Q56 uniques ;
seules lignes Q40/Q49 modifiées. Suites backend/frontend/Compose et Ruff non relancées localement.
Vérifier la CI propre du nouveau commit après publication ; résultats consignés dans PR après observation.
Prochain arbitrage à ce checkpoint : périmètre Q48, désormais partiellement validé ci-dessus ;
facteur et récupération restent ouverts.
Aucun merge de PR #6, implémentation ou démarrage de 5C.

### Changement d’email Q40/Q49 — 2026-10-29 (checkpoint avant complément)

Source : arbitrage explicite utilisateur pour PR #6, synthèse unique des deux réponses identiques.
Non implémenté : session Portal valide, mot de passe actuel ressaisi, confirmations ancienne et
nouvelle adresses ; nouvelle pending jusqu’aux deux confirmations et validation effective. Succès :
notifications aux deux adresses, nouvelle authentification, global_user_id et états de jeu conservés.
Ancienne adresse inaccessible : blocage sans récupération indépendante déjà établie et disponible,
pas de bypass mot de passe seul. Variante MFA conditionnelle à Q48 validée/implémentée, politique
exacte ouverte ; aucun MFA/code de secours/support inventé. Durées/cycle des confirmations et
portée exacte d’invalidation des sessions toujours ouvertes ; aucune autre Qxx fermée par implication.

Reprise : fetch, branche work/step-5b-identity-contracts propre/synchronisée sur
38a2b6ac4f79fb66dc165a843c95c8761eb83b17, PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête vérifiée : push 40896112238 et PR 40896122379, backend/frontend/compose-smoke verts.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, index des décisions et références
API/ADR 0008/index/passation/lacunes. Critères futurs : pas de bascule avec une seule confirmation,
refus sans preuve indépendante, notifications/réauthentification et identité conservée.
Checks locaux : documentation/liens, diff, Q01–Q56 uniques, seules lignes Q40/Q49 modifiées ;
Markdown uniquement. Aucune suite backend/frontend/Compose ou Ruff relancée localement ; aucun
comportement futur testé. Après publication vérifier SHA et CI propres, résultats consignés dans PR.
Prochain arbitrage à ce checkpoint : durées/cycle et sessions, désormais validés dans le complément
ci-dessus ; Q48 reste ouverte. Aucun merge de PR #6, démarrage de 5C ou implémentation.

### Récupération Q40/Q49 — 2026-10-29 (checkpoint antérieur au changement d’email)

Source : arbitrage explicite utilisateur pour PR #6, synthétisé sans transcript. Décision validée,
non implémentée : jeton 30 min maximum depuis émission, unique, expiration serveur ; réémission
invalide tous les anciens liens. Reset réussi : invalidation de toutes les PortalSessions et jetons
de récupération, demande de révocation de toutes les GameSessions tous appareils/univers ; nouvelle
connexion normale sans auto-login, notification email sans mot de passe. Réponse de demande non
énumérable ; memberships/empires/états conservés. Si Game injoignable, révocation persistée/rejouée
jusqu’à acquittement, aucune instantanéité promise, valid_until/8 h jamais relancés au reset.
Seules ces parties Q40/Q49 sont closes ; Q48/Q50/Q53/Q54 restent ouvertes.

Reprise vérifiée : fetch, arbre propre, branche work/step-5b-identity-contracts synchronisée sur
cbf088c5c22974ce0c548fe4faeb2e1b9eec5533 ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête observée verte : push 40892359042 et PR 40892370513, backend/frontend/compose-smoke.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, index des décisions et références
passation/index/API/ADR 0008. Critères futurs ajoutés : frontière 30 min, réémission/consommation
concurrentes, reset global et panne sans extension. Aucun mécanisme futur testé ou implémenté.
Checks locaux : documentation/liens, diff et périmètre Markdown, Q01–Q56 sans trou/doublon et seules
lignes Q40/Q49 modifiées. Suites fonctionnelles backend/frontend/Compose et Ruff non relancées
localement pour ce diff documentaire. Relire SHA distant/CI de la nouvelle tête après push ;
les résultats du commit précédent ne valent pas ceux du nouveau. Résultats publiés dans PR après observation.
Prochain arbitrage à ce checkpoint : changement d’email, depuis partiellement validé ci-dessus ;
durées/cycle et portée des sessions restent ouverts, puis MFA Q48. Aucun merge ni démarrage de 5C.

### Déconnexions Q45 — 2026-10-29 (checkpoint antérieur à la récupération)

Source : validation explicite utilisateur pour PR #6. Comportement produit Q45 clos, non implémenté :
retour lobby sans logout ; déconnexion Game d’une seule session ; compte sur appareil courant
(PortalSession courante + toutes ses GameSessions du compte) ; tous appareils comme action distincte.
Autres appareils préservés lors du logout normal ; memberships/empires/états/progression/actions
acceptées conservés. Révocation globale persistée/rejouée jusqu’à acquittement, état UI en attente
si service injoignable, borne valid_until/8 h inchangée. Aucune autre Qxx close par implication.
Regroupement appareil sous Q41/Q43 ; protocoles sous Q53/Q54 et tickets en vol sous Q42/Q56 ouverts.
Un epoch d’accès commun ne peut implémenter le logout d’un seul appareil : limite explicitée,
sans adopter un nouveau modèle de stockage. Matrice d’acceptation future complétée, aucun test
fonctionnel de ces mécanismes exécuté.

Reprise : fetch, branche work/step-5b-identity-contracts propre et synchronisée sur d879f7e5002d91342f08819ff2bad69ee83ad7d0 ;
PR #6 OPEN/brouillon, base master 8214e0b inchangée. CI de cette tête observée verte :
push 40879933579 et PR 40879939979, backend/frontend/compose-smoke réussis.
Fichiers : contrats, registre Qxx, context/progress, sécurité, API/architecture, ADR 0008, roadmap,
README/index/passation/décisions/lacunes. Résumés périmés corrigés ; Markdown uniquement.
Checks locaux : check documentaire, diff, Q01–Q56 et comparaison des statuts ; seules les décisions
Q45 changent, aucune autre fermeture. Suites fonctionnelles backend/frontend/Compose et Ruff
non relancées localement pour ce diff documentaire ; CI de la nouvelle tête à observer après push.
Prochain arbitrage à ce checkpoint : récupération Q40/Q49, depuis validée dans le complément
ci-dessus ; changement d’email et MFA restent ouverts.
Aucun merge de PR #6, passage à 5C ou implémentation ; résultats CI publiés dans la PR après observation.

### Complément activité Q41/Q43 — 2026-10-29 (checkpoint antérieur à Q45)

Source : arbitrage explicite utilisateur, synthétisé dans identity-contracts et Qxx. Seules les
interactions explicites classées côté serveur réinitialisent l’inactivité ; toutes les catégories
automatiques citées dans le contrat sont exclues. Heure serveur, aucun timestamp client autoritaire ;
aucune modification des maxima absolus ou de valid_until. Q41/Q43 restent partiellement ouvertes,
Q45–Q56 inchangées. Aucune implémentation ni fusion autorisée.

Reprise : fetch effectué, arbre propre, tête locale/distante 5dbd9184509ca6323279365944dea9567207cd17,
PR #6 OPEN/brouillon, base master 8214e0b inchangée. CI de cette tête vérifiée : push 40878132584
et PR 40878144213, backend/frontend/compose-smoke réussis.
Fichiers : identity-contracts, open-questions, context, progress, sécurité, roadmap et index des décisions.
Scénarios futurs complétés : catégories automatiques sans effet, interactions explicites, timestamp
client falsifié, échéance contrôlée avant réinitialisation et maxima inchangés. Aucun test de ces
mécanismes futurs exécuté. Vérifications locales : check documentaire, diff et périmètre Markdown ;
aucune suite fonctionnelle backend/frontend/Compose ni Ruff relancée pour ce complément documentaire.
Après publication, relire SHA distant et CI effective de cette nouvelle tête ; les résultats de
5dbd918 ci-dessus ne prouvent pas la CI du présent commit.
Prochaine décision à ce checkpoint : Q45, depuis arbitrée dans le complément ci-dessus. 5C/5D restent hors de ce lot documentaire.

### Arbitrages utilisateur intégrés — 2026-10-29, checkpoint antérieur à Q45

Source : validation explicite utilisateur pour poursuivre PR #6, synthétisée dans le canonique
identity-contracts.md et le registre Qxx, sans transcript brut. Aucune validation implicite
du reste de la proposition et aucune autorisation de fusion.

- Q40, parties closes : MVP email/mot de passe ; email vérifié avant premier handoff ; récupération
  courte/unique ; Argon2id via bibliothèque maintenue ; global_user_id indépendant de l’email et de
  la méthode. Google/OIDC supplémentaire futur facultatif. Bibliothèque/paramètres et récupération
  détaillée restent ouverts ; fournisseur email et MFA dans leurs Q49/Q48 restent à arbitrer.
- Q41, partie close : Portal 7 jours absolus et **72 heures** d’inactivité, remplaçant la proposition
  initiale de 24 h. Activité sans prolongation du maximum absolu ; cookies/stockage/rotation ouverts.
- Q42, parties closes : ticket de handoff 60 secondes et usage unique. Format, crypto, liaison
  navigateur et mécanismes anti-rejeu toujours ouverts ; aucune durée de récupération déduite.
- Q43, parties closes : Game 8 h absolues/2 h d’inactivité, GameAccess pouvant expirer plus tôt ;
  absolu non prolongé par activité. Stockage et limites simultanées ouverts ; activité arbitrée dans le complément ci-dessus.
- Q44, parties closes : droits au plus 8 h depuis dernière confirmation Portal, non glissants et
  sans reset en panne ; révocation/suspension reçue immédiate ; nouvelles commandes refusées à
  valid_until, univers/workers continuant. Renouvellement avec Portal disponible et nouvelle
  confirmation/handoff valide ; aucune autonomie illimitée. Protocoles/synchronisation non choisis.

Q40–Q44 restent partiellement ouvertes ; Q16/Q21/Q45–Q56 ne sont pas fermées. Les comptes,
sessions et tickets ne sont toujours pas implémentés. La validation de la fenêtre ne vaut pas
acceptation de mTLS, JWT, stockage opaque, cookies, epoch, outbox ou politique de logout.

Poursuite documentaire : expressions des échéances et exemples de confirmation retardée/panne
ajoutés, scénarios futurs de frontière et compte MVP précisés. Aucun test artificiel ou code ajouté.
À ce checkpoint antérieur, l’activité Q41/Q43 restait à arbitrer ; le complément ci-dessus
consigne désormais sa validation explicite.
Les autres questions techniques restent listées pour la suite, pas repoussées implicitement à 5C.

Fichiers de cette continuation : identity-contracts, open-questions, context/progress et références
README/docs/index/architecture/API/sécurité/ADR 0008/roadmap/passation/known-gaps pour éviter des
mentions périmées « durées/login encore proposés ». Diff Markdown uniquement, aucun changement de
code, test, dépendance, migration, ruleset, Compose ou script.

Vérification initiale de cette continuation : arbre propre, branche locale et distante à
2d1efdabac4a5e6396b515f63fc02684869c8ac9 après fetch, PR #6 OPEN/draft sur la même tête vers
master 8214e0b ; seule PR ouverte listée. CI de cette tête relue :
[40873616329](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873616329) et
[40873623209](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873623209), tous les jobs
backend/frontend/compose-smoke réussis. Aucun merge, changement de branche ou travail concurrent.
Checks de cette continuation exécutés : 64 documents/liens valides, git diff --check sans erreur,
Q01–Q56 sans trou/doublon ; comparaison avec HEAD confirmant que seuls les libellés Q40–Q44
changent dans les tableaux du registre et qu’ils restent explicitement partiellement clos.
Relecture des limites/formules/exemples, de la séparation validé/proposé et du diff de confidentialité.
Périmètre Markdown uniquement vérifié. Aucune suite backend/frontend/Compose ou Ruff relancée
localement pour ce changement documentaire ; aucun nouveau mécanisme de session testé.
Publication effectuée sur la même PR #6 brouillon, restée OPEN/non fusionnée :
56e43a9bf5a9100e22ad3c4363095a45b0452db9, SHA distant relu ; master reste 8214e0b.
CI de ces arbitrages : [push 40877809734](https://github.com/ThomasPerez91/Echosphere/actions/runs/40877809734)
et [PR 40877818343](https://github.com/ThomasPerez91/Echosphere/actions/runs/40877818343),
backend/frontend/compose-smoke tous réussis sur cette tête. Description de PR actualisée avec
les décisions partielles et les mécanismes non validés. Ce checkpoint consigne ces résultats
après leur observation ; vérifier également sa propre CI publiée. Aucune CI présentée comme
preuve d’un mécanisme Portal/Game futur, aucun merge ni passage à 5C.

### Base et périmètre initiaux (historique de préparation)

GitHub relu : PR #5 MERGED, tête acde9d358bfe724be61198cd60fd1e72c6e38459, base master,
merge 8214e0bd30a00bf0336264a428e6975d307350ba. Fetch effectué ; master locale propre et identique
à origin/master. Aucune PR ouverte au contrôle, aucune develop. CI master
[40765430216](https://github.com/ThomasPerez91/Echosphere/actions/runs/40765430216) completed/success
sur ce merge, jobs backend/frontend/compose-smoke verts. Dernière livraison consignée : passation
Work par #5 ; cette recette locale lui succède sans attribuer un nom non attesté à son auteur.

Branche : work/step-5b-identity-contracts, créée depuis cette master sans empilement.
Premier commit publié : e3d2f8ec1dcb647a147dc9d885be4f06f9f46802,
[PR #6](https://github.com/ThomasPerez91/Echosphere/pull/6) brouillon OPEN vers master.
Le présent checkpoint documentaire suit ce commit ; consulter aussi sa propre CI publiée.
Aucune fusion, suppression de branche, release ou déploiement autorisé.

Fichiers : nouveau docs/03-technical/identity-contracts.md ; références API/sécurité/modèle/architecture,
index docs/ADR/décisions, README/passation, roadmap/questions/known-gaps, context/progress et liste
des documents requis de scripts/check_docs.py. Aucun code métier, game_data, migration, dépendance,
Compose, composant UI ou test fonctionnel modifié.

### Préparation initiale et statut des propositions (avant les arbitrages ci-dessus)

Contrats proposés : autorités Portal/Game, participation/accès local versionné/bindings d’Empire,
interface interne idempotente avec révisions/outbox/réconciliation, handoff lié au navigateur,
consommation atomique, session opaque et contrôles locaux, concurrence avec révocation, logout,
rotation de clés, isolation et matrice de scénarios futurs. Alternatives et sources OWASP/RFC
publiques consignées. À ce premier checkpoint, aucun protocole, algorithme, fournisseur ni durée
nouveau n’était présenté comme accepté.
Relecture : distinguer la révision de livraison de l’epoch d’invalidation des sessions pour qu’un
renouvellement à droits inchangés ne déconnecte pas les sessions valides ; cookies par univers
proposés pour les onglets multi-parties, limite de sessions/cleanup restant sous Q43.

Arbitrage principal alors proposé : validité locale des droits bornée à 8 h, session Game 8 h absolues/
2 h d’inactivité, ticket 60 s ; autonomie en panne Portal jusqu’aux limites, révocation appliquée
dès livraison mais non instantanée si liaison coupée. Ces valeurs étaient des propositions à revoir,
depuis acceptées uniquement dans le périmètre décrit en tête. Q21 et les questions de modes restent ouvertes. 5C ne commence
pas automatiquement après la rédaction ; recueillir les arbitrages nécessaires et leur provenance.

### Recette de reprise locale réalisée avant création de la branche

Cette recette appartient à la mission de reprise du 2026-10-29, sur master 8214e0b inchangée ;
elle ne valide aucun mécanisme futur de 5B et n’a pas été relancée pour le diff documentaire.

- `python3 scripts/check_docs.py` : 63 documents/liens valides.
- `docker compose ps -a` : postgres/backend/frontend healthy, worker running, migrate Exited (0).
- `docker compose exec backend alembic check` : aucune dérive ; current = 0004_colony_economy head.
- `python3 scripts/smoke_compose.py` : succès, frontend/proxy/sondes et panne/reprise PostgreSQL.
- Backend dans un conteneur Python 3.12 : premier passage 42 réussis/59 ignorés sans RUN_DB_TESTS.
  Passage complet avec base dédiée echosphere_codex_20261029_test : initialement 100 réussis/1 échec
  de chemin game_data, puis 101 réussis après montage de l’arborescence complète en lecture seule.
  La base dédiée a été supprimée ensuite ; aucune suite de downgrade sur la base de jeu.
  Ruff backend/scripts passe. Avertissement Starlette/httpx déprécié observé.
- Frontend conteneur Node 22 : npm ci, lint, 11 tests et build réussis. Les empreintes des fichiers
  App, test, CSS, ColonyView, scénario E2E et package-lock de l’image concordaient avec le dépôt.
- Playwright : installation impossible dans Alpine (apt-get absent), puis 5 scénarios Chromium
  réussis dans un conteneur Debian Node 22 jetable, copie de sources montées en lecture seule.
  Largeurs 320/390/768/1440 et navigation clavier/retry. Aucun test navigateur Windows attesté.
- Chargement du ruleset dans l’image worker : v0.1. Diff et état Git propres à la fin de la recette.

Limites environnement : noyau 6.18.54.1-microsoft-standard-WSL2, Compose v5.6.1, Python hôte 3.14.4,
pas de Node/npm hôte ni backend/.venv. Les tests ont utilisé les versions Docker prévues, sans
installer les outils sur l’hôte. Les premiers accès fetch/socket Docker/localhost ont été refusés
par le bac à sable puis ont réussi avec autorisation ; aucun défaut WSL2 démontré par ces refus.
Pas de recette graphique Windows, tactile, lecteur d’écran, Safari/Firefox, charge massive ou
résilience Portal/Game réel (inexistant). Pile Compose laissée démarrée, volume de jeu conservé.

`npm audit --json` : 3 dépendances affectées (1 modérée, 2 critiques) dans la chaîne de développement
Vitest/@vitest/mocker/tinypool. Aucun correctif automatique effectué. Voir known-gaps pour les avis.

### Validation du premier checkpoint documentaire (historique)

Checks du diff 5B exécutés : 64 documents/liens valides, git diff --check sans erreur,
Q01–Q56 présentes exactement une fois dans les tableaux du registre ; périmètre Markdown et
liste REQUIRED de check_docs.py vérifié. Ruff de scripts/check_docs.py passe dans le conteneur
Python 3.12 avec dépendances de développement figées. Relecture du nouveau contrat, de ses statuts,
de ses liens et du diff de confidentialité effectuée. Aucune suite fonctionnelle relancée pour
ces changements documentaires ; les scénarios 5B sont des critères futurs non exécutés.
Branche publiée, SHA distant e3d2f8e relu, PR #6 brouillon créée et non fusionnée.
[CI push 40873175483](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873175483)
completed/success sur e3d2f8e, jobs backend/frontend/compose-smoke verts. Ces résultats ne prouvent
aucune implémentation des contrats futurs. Le présent checkpoint et les précisions de relecture
suivent cette tête ; leur CI propre reste à relire après publication, sans la présumer réussie.
Prochaine action à ce checkpoint : revue et arbitrage, désormais partiellement effectués comme
consigné en tête ; pas d’implémentation Portal/API Colony sur la seule présence du document.

---

## Lot précédent — passation documentaire Work / Codex (historique)

**Périmètre : documents uniquement**, plus liste des documents requis dans scripts/check_docs.py.
Aucun service, gameplay, migration/SQL, game_data, dépendance, Compose/Docker ou test fonctionnel changé.
Branche existante work/step-5a-colony-domain et PR #5 conservées ; pas de nouvelle branche/PR,
force push, suppression, merge, tag ou déploiement. Environnement de cette livraison : ChatGPT Work.

### État initial vérifié

PR #5 ouverte, mergeable, non fusionnée, tête 5be00da4726abd8fb38bd159deab1f1cf687df52 vers master
54f928e2348781db43b335d4dcf569aadc0db6e9. CI 40721303421 verte (backend/frontend/compose-smoke).
Dernier commit : context/progress seulement après 58e8f7c fonctionnel. Seules master et la branche #5
restent listées ; les anciennes branches work ont disparu, sans action de cette mission. Pas de develop.
Audit code/tests et limites dans [audit #5](docs/06-handoff/pr-5-audit.md).

### Travail et sources

Vision et documents existants enrichis, chiffres v0.1 préservés. 12 secteurs/2 orbitaux explicitement
limités au départ de référence ; Q39 toujours ouverte. Status implémenté/validé/provisoire/proposé/futur
séparés. Architecture actuelle réconciliée avec code, anciennes contradictions signalées superseded.

ADR 0008 créé sans renuméroter 0007 : compte global multi-parties, deux backends Portal/Game isolables,
Accounts DB/Game DB distinctes, interface interne contrôlée sans SQL Portal→Game, GameSession autonome
après ticket court/unique et gameplay direct. Décision validée **non implémentée**, protocoles non choisis.
Q16 partiellement cadrée, Q01–Q39 préservées, Q40–Q56 ouvertes. Roadmap : 5A → 5B contrats identité/
Portal-Game → 5C compte/lobby selon cadrage → 5D API Colony/UI sécurisées. Aucun Portal complet anticipé.

Dossier docs/06-handoff : README, source-map, decision-status, work-codex-handoff, known-gaps,
pr-5-audit. Procédure symétrique fetch/lecture/qualité/commit/push/SHA-CI pour Work et Codex ; reprise
locale WSL2 proposée mais jamais présentée comme testée. AGENTS devient la procédure commune.

Sources : dépôt, PR #1–5/CI/commits, contexte visible et brief de mission ; recherche contextuelle
partielle ciblée a retrouvé des extraits cohérents, pas toutes les conversations originales.
Aucun accès exhaustif au projet ChatGPT attesté. Source secondaire de fichier signalée par recherche
non lue intégralement. Pas de conversation brute, information personnelle/secret/identifiant privé
ou sujet hors Echosphere publié. Les décisions anciennes seulement retrouvées dans GitHub restent
qualifiées selon leur preuve, sans promotion des suggestions d’assistant.

### Vérifications et point de reprise

Check documentaire : 63 fichiers et liens locaux ; index ADR 0001–0008, Q01–Q56 sans trou/doublon,
recherche develop/plafond 5/12-2/backend unique et diff documentaire contre 5be00da. Ruff du script.
Les limitations techniques relevées sont consignées, non corrigées : borne secteur au service,
immutabilité de snapshot par contrat applicatif, initialiseur limité à la référence ; Q39 et UX de
cascade encore à valider. Aucun problème bloquant nouveau démontré par la lecture ciblée.

Passation publiée en deux commits :
- 14fd4db40b3a422228433af7ede9842caa61c363 — docs: consolidate product and Portal-Game isolation decisions.
- 2748d41fba0fdd3fcf09ce2e60c4ad1f07e999cd — docs: add durable Work and Codex handoff procedure.

[CI 40742149137](https://github.com/ThomasPerez91/Echosphere/actions/runs/40742149137) entièrement
verte sur 2748d41 : backend/frontend/compose-smoke, 101 tests backend (42 unitaires + 59 PostgreSQL),
11 frontend, 5 Chromium, build/lint, 63 documents/liens et démarrage/panne-reprise PostgreSQL.
Les tests fonctionnels ne sont pas relancés localement pour la mission docs ; leurs fichiers sont
inchangés. Ces résultats CI ne sont pas une recette WSL2/tactile/charge/anti-DDoS. Le présent commit
de checkpoint suit cette tête validée : vérifier aussi sa propre CI avant toute fusion autorisée.

### Prochaine action selon l’état GitHub réel

L’état GitHub réel prévaut sur les états historiques de ce document.

- **Si PR #5 est encore ouverte** : vérifier sa tête publiée et sa CI, effectuer la revue ;
  merge uniquement sur autorisation explicite. Reprendre sa branche pour une mission sur #5,
  sans créer de nouvelle branche ou PR pour ce lot.
- **Si PR #5 est déjà fusionnée** : synchroniser master, considérer 5A/passation comme intégrées,
  puis effectuer la recette locale WSL2/Docker/Codex selon la procédure de passation. Cette recette
  n’a pas encore été effectuée. Ne pas recréer une branche #5. Le prochain développement fonctionnel
  est 5B (Q16/Q40–Q56), uniquement après instruction, sur une nouvelle branche work/... issue de
  master synchronisée ; ne pas commencer directement une API Colony ou le multijoueur.

Le futur agent ne doit pas déduire une autorisation de merge ou de développement de ce checkpoint.

## Historique du checkpoint fonctionnel 5A (antérieur à la passation)

Les sections suivantes conservent les preuves/limites du lot fonctionnel, pas une déclaration de
nouveaux tests exécutés dans la passation. La séquence 5B historique est affinée plus haut.

## Reprise et autorisation vérifiées

PR #4 fusionnée sur instruction de l’utilisateur : master `54f928e2348781db43b335d4dcf569aadc0db6e9`.
[CI master 40716684879](https://github.com/ThomasPerez91/Echosphere/actions/runs/40716684879)
verte avant création de `work/step-5a-colony-domain`. Brief joint appliqué : Étape 5A uniquement.
[PR #5](https://github.com/ThomasPerez91/Echosphere/pull/5) vers master ; aucune autorisation de fusion.
Aucune develop recréée, branche empilée, release ou déploiement.

## Domaine et règles livrés

- game_data/rulesets/v0.1 : resources.json, colony.json, infrastructures.json. JSON/Pydantic strict,
  clés dupliquées/versions mixtes/extras/mauvais types refusés ; erreur explicite sans fallback.
- Référence : 12 secteurs, 2 slots orbitaux réservés, 4 infrastructures I, 8 secteurs libres,
  Command Core conceptuel hors secteurs. Stocks 2000/1500/750, taux 120/100/60 par heure, capacité 10000.
- Cinq infrastructures configurables : trois producteurs répétables ; industrie/logistique uniques.
  Un secteur par exemplaire, aucun secteur de plus à l’upgrade ; niveaux continus sans plafond 5.
- Niveaux explicites 1–5 puis récurrence : producteurs coût/durée/production ×1,38/1,28/1,12 ;
  industrie ×1,40/1,30 et +5 points de bonus ; logistique ×1,40/1,30/1,18. Aucun facteur en service.
- Entiers micro-unités et microsecondes, fractions exactes. Scaling coût/durée plafond,
  production/capacité plancher, durée effective plafond, remboursement plancher. Refus de dépassement.
- Snapshot complet validé par univers, vitesses rationnelles par instance ×1 ; économie/construction
  actives, recherche/flotte seulement réservées. Pas de singleton ni changement implicite des instances.
- Ordre : snapshot version/coût/durée/type/niveau/secteur/vitesse/remboursements. Réservation à l’entrée,
  trois ordres actif inclus, un actif, clé de commande idempotente, prochain bonus industriel évalué
  à l’activation. Prérequis sur infrastructures achevées ; niveaux contigus avec prédécesseurs réservés.
- Annulation 100 % queued / 80 % active, idempotente. Cascade des upgrades dépendants du même secteur ;
  les autres gardent leur ordre. Démarrage suivant à la date logique d’annulation. Remboursement exact
  impossible faute de stockage : refus atomique sans perte/overflow caché, Q39 pour validation produit.
- Production réglée avant changement de niveau/capacité ; perte de production au plafond, reste nul.
  CONSTRUCTION_COMPLETE réutilise EventStream, SAVEPOINT, retries et worker ; aucune seconde file timer.
- Services internes configure_universe/initialize_colony/enqueue/cancel, scope univers/empire/colonie,
  verrou du stream et catch-up complet avant mutation. Transaction du caller, aucun commit interne.

## Persistance et image

Migration `0004_colony_economy`, migrations 0001–0003 intactes. Tables universe_economies,
colony_economies, colony_infrastructures et construction_orders. FK composites, secteur unique,
niveau >=1, unicité de clé/séquence, index partiel un actif. Capacité de planète et limites du ruleset
vérifiées par les services sous lock ; pas de duplication de game_data dans des CHECK de catalogue.
Upgrade/downgrade/upgrade vide et alembic check ; downgrade peuplé refusé avant DDL, pas de suppression
silencieuse. Pas de backfill fictif des anciennes timelines : leur adoption métier reste hors lot.
Contexte build backend à la racine pour inclure game_data ; .dockerignore et emplacement image explicites.
Compose conserve monolithe API/worker/PostgreSQL, vérifie le chargement des données dans le worker.

## UI et documentation

Colony : Vue d’ensemble / Infrastructures / Orbite / Défense, liens directs #colony/<vue>, sélection
globale Colonie conservée, focus/clavier/historique. Aucune huitième entrée principale, colonie/stock/
bâtiment/timer fictif ou commande de défense. État « Aucun univers / aucune colonie active ».
Défense documentée dans planetary-defense.md : réseau stratégique limité, modules persistants,
coût d’opportunité surface/orbite, dommages/réparation/Flux et révélation par renseignement futurs.
Aucune table DefenseNetwork/Module ou effet actif. Q30–Q38 ajoutées et ouvertes ; Q39 remboursement.
ADR 0007, docs produit/UX/tech/qualité, AGENTS, context et roadmap actualisés. Historique 5A : la mention 5B API/UI était la séquence de ce checkpoint,
**superseded** par 5B contrats / 5C fondation Portal / 5D API/UI (passation, ADR 0008).
Les arbitrages v0.1 ne ferment pas les questions générales d’équilibrage et de modes.

## Validation source vérifiée

Local : Ruff, 42 tests unitaires backend, ESLint, 11 tests frontend, build, 5 scénarios Chromium et
56 documents/liens. Captures Colony/Défense inspectées à 320 et 1440 ; scénarios aux quatre largeurs
320/390/768/1440. Les 59 intégrations PostgreSQL sont à exécuter par la CI, pas revendiquées en local.
101 tests backend collectés au total ; tests antérieurs conservés et complétés.

Première CI source 789aa96 : frontend et Compose verts, backend 98 réussis/1 échec de test.
L’intervalle de saturation logistique était de dix jours, insuffisant pour les Données ; corrigé
à vingt jours. Ajout de tests d’édition réelle du catalogue sans repricing et d’événement étranger.
CI source finale entièrement verte sur `58e8f7cf32c1b2fbfd9568ec2317cc4338ae7642` :
[run 40720967410](https://github.com/ThomasPerez91/Echosphere/actions/runs/40720967410).
101 tests backend réussis (42 unitaires + 59 PostgreSQL), 11 frontend, 5 Chromium, lint/build,
56 documents/liens, migrations/absence de dérive, chargement v0.1 dans l’image et smoke Compose avec
panne/reprise PostgreSQL. Tous les scénarios antérieurs sont conservés. Ce checkpoint documentaire
suit la source validée ; vérifier la CI de sa propre tête avant toute future fusion autorisée.

## Limites et reprise

1. PR #5 prête pour revue, laissée non fusionnée. Vérifier sa tête documentaire finale et sa CI ;
   le code source 58e8f7c est validé par le run indiqué ci-dessus.
2. Règles v0.1 provisoires, pas de simulation d’équilibrage longue ou charge massive revendiquée.
3. Aucun PostgreSQL/Docker local exploitable ; intégrations, migrations et Compose validés sur GitHub.
   Pas de recette WSL2/Docker Desktop, tactile/lecteur d’écran réel, Safari/Firefox.
4. Politique de remboursement au stockage insuffisant à revoir (Q39). Changement de ruleset/vitesse
   d’univers actif et adoption des anciennes timelines nécessitent un lot explicite.
5. Après revue/intégration, cadrer Q16 avant 5B. Aucune API gameplay (lecture ou mutation), identité
   globale factice ou gameplay cliquable. Pas d’auth complète, multijoueur, invitations, PvP,
   espionnage, combat, défense réelle, flotte, recherche ou colonisation implémentés dans ce lot.

## Historique

Étapes 0–4 : PR #1 bootstrap, #2 fondation SQLAlchemy/Alembic et modèles, #3 scheduler générique
corrigé, #4 shell responsive. Fusion #3 : 4ee81dd, CI 52 backend/3 frontend/Compose ; fusion #4 :
54f928e, source 52 backend/10 frontend/5 Chromium/Compose. develop supprimée par l’utilisateur et absence
vérifiée. master = intégration stable, work/... → PR master → revue/autorisation propre à chaque merge.
