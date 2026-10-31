# Research — contrat technique étape 6

**Statut : implémenté sur PR #9, validation finale/recette en cours.**
Contrat produit : [Recherche/Q05](../01-game-design/research.md). Plan et preuves :
[étape 6](../05-project/step-6-plan.md), [progress](../../progress.md).
Aucune fusion implicite ; vérifier GitHub avant reprise.

## Ruleset et catalogue

`game_data/rulesets/v0.2` est un ruleset complet : ressources, Colony, infrastructures et Research.
Les fichiers v0.1 publiés sont inchangés. Un Universe v0.1 garde sa boucle Colony, sans Research ;
son API Research refuse avec `research_unavailable`. Aucun backfill ni adoption à la lecture.
La création complète d’une partie et la migration de rulesets actifs restent hors lot.

Huit technologies uniques, deux par domaine, identifiants `engineering_1/2`, `energy_1/2`,
`computation_1/2`, `xenoscience_1/2`. I = 500 bps ; II = 1000 bps net, maximum acquis par effet,
jamais addition. II requiert I. Catalogue strict : versions, ressources, effets connus, coûts,
bornages, prérequis connus et graphe acyclique. Noms/coûts/durées/bonus restent balançables.

Valeurs initiales par technologie : I 100 Alliages / 80 Flux / 200 Données, 120 secondes ;
II 200 / 160 / 400, 300 secondes, avant effets et vitesse Research de l’instance.
La réduction de coût arrondit au micro-entier supérieur ; durée = plafond de
`base_us × vitesse.dénominateur × (10000 − réduction_bps) / (vitesse.numérateur × 10000)`,
minimum une microseconde. Aucun flottant économique.

## Persistance, transactions et temps

Migration Game **0007_empire_research** après 0006 : `empire_research`, `research_orders`,
`acquired_technologies`, FK composites Empire/Universe/stream et Colony payeuse/Empire/Universe,
index uniques actif, suivante (queued/blocked), technologie non annulée, séquence et clé d’intention.
Downgrade refusé si état Research ou grants Research présents, sans effacement automatique.
Les migrations 0001–0006 ne changent pas. Accounts n’a pas de nouvelle migration.

Initialisation de l’ancrage sérialisée sur Empire, puis commandes sur son EventStream unique.
Ordre de locks : principal Game (HTTP, même lock que révocation) → Research → Colony sources triées
par UUID. Recherche et Colony partagent ResourceBalance ; la réservation n’a aucune caisse Empire.
Rattrapage Research complet avant les stocks sources, puis dépense/prérequis/file/snapshot dans
la transaction du caller. SAVEPOINT des services ; aucun commit interne ou appel Portal.

Snapshot : définition/version, prérequis/effet, coût payé, source, durée de base/effective,
vitesse, bonus acquis et règles 100/80. Aucun recalcul de la suivante après acquisition.
Les effets Ingénierie/Énergétique alimentent la quote métier commune Colony avant acceptation,
et sont conservés dans le snapshot de construction ; les commandes déjà réservées restent intactes.
Le bonus industriel Colony demeure fixé à l’activation comme en 5A, sans bonus Research implicite.

`RESEARCH_COMPLETE` est enregistré dans le TimeEngine/worker existant. Le handler, sous le seul
stream Empire, acquiert une fois et active la suivante à la date logique de fin, sans second débit
ou lock Colony. Une suivante dont les prérequis métier ne permettent plus le départ reste `blocked`,
avec raison explicite et réservation conservée ; pas de dépassement par un successeur. Une erreur
technique lève vers rollback/retry/backoff/blocked opérateur du scheduler, pas vers une annulation.
Le snapshot est également comparé à sa définition/version/vitesse épinglées pour distinguer une
incohérence persistée d’un refus métier de démarrage ; aucun recalcul selon les acquis ultérieurs.

Annulation : rattraper d’abord l’échéance (une recherche terminée n’est plus annulable), calculer la
cascade dépendante, verrouiller/rattraper chaque source dans le même ordre, répartir sa place libre
une seule fois via le helper Q39 partagé. Enregistrer les reçus réellement crédités, perte définitive,
acquitter l’événement annulé et démarrer la suivante indépendante à la date logique d’annulation.
Un retry renvoie le reçu stocké, sans nouveau crédit. Aucun remboursement dans le handler de fin.

## API et permissions

Préfixe Game `/game/{universe_id}/research` (navigateur : `/api/game/...`).

| Méthode / chemin relatif | Contrat |
| --- | --- |
| GET vide | Empires lisibles du membership effectif |
| GET `/{empire_id}` | Acquis, bonus, file, huit technologies/options, sources lisibles et stocks, previews d’annulation |
| POST `/{empire_id}/orders` | `idempotency_key`, `technology_id`, `colony_id` explicites |
| POST `/{empire_id}/orders/{order_id}/cancel` | Objet JSON vide ; destination persistée seulement |

GameSession autonome → accès Universe/membership valide → binding Empire → `research.read` pour
lecture et mutations, puis `research.start` ou `research.cancel` distinct. Source/remboursement
exige aussi `colony.read` selon le modèle actuel (binding Empire, donc colonies de cet Empire).
Pas besoin de `colony.construct`, pas de droit admin/controller_type implicite.
Sans lecture : 404 comme Empire inconnu. Source étrangère/invisible refusée avant paiement.
Contrôle privé Game, allowlist Portal et schéma v1 étendus explicitement aux six permissions ;
anciens grants inchangés. Déployer Game/migration et Portal compatibles avant d’accorder les nouveaux
droits via SetAccess ; révisions/epochs, confirmation et bornes existantes conservées.

GET exige `X-Game-Request: bootstrap`, pas de query ni Origin étranger ; POST exige Origin exact,
JSON, CSRF et DTO strict sans champs supplémentaires. Clé de lancement isolée par membership.
Montants micro-unités en chaînes décimales, dates UTC ; `Cache-Control: no-store`.
Réponses 401 session, 403 droit/CSRF/origin, 404 scope, 422 enveloppe, 409 refus métier/conflit,
503 retry technique. Aucune exception SQL ou détail privé exposé. Lectures/timers sans activité ;
commandes explicites seulement, jamais prolongation de l’expiration absolue.

## UI et recette

Écran Research dans le shell existant, quatre domaines, sélection d’Empire et source payeuse
séparées, acquis/active/suivante/prérequis, coûts et durée effective serveur. Confirmation de dépense
et preview d’annulation par destination (théorique/récupérable/perte/cascade). Dialog natif modal,
Escape/retour du focus, responsive 320/390/768/1440. Pas de laboratoire, respec, drag ou fixture runtime.
Timer visuel basé sur dates serveur ; seule la réponse serveur confirme l’acquisition.
Générations/abort pour scopes et lectures dépassées ; aucune mutation au montage/StrictMode.
Retry réseau/5xx garde la clé d’intention ; pas de retry automatique de mutation. Rafraîchir la Colony
après commande pour que les stocks du shell reflètent aussi le financement Research.

Commandes : suites habituelles AGENTS puis `python3 scripts/smoke_research_compose.py` après build
Compose du même arbre. Recette dans un projet unique sans ports hôte, bases strictement
`echosphere_research_game_test` / `echosphere_research_accounts_test`, volumes propres détruits à la fin.
Le contrôle réel crée l’accès ; fixture strictement test pour graphe et vitesses 10x Research/60x Colony.
HTTPS, login/handoff réel, deux réservations, page fermée, achèvement worker, durée suivante inchangée,
effet réel sur quote Colony, Portal API/contrôle arrêtés, nouveau lancement/acquisition/effet puis
refus de session expirée. Aucun intercept API dans cette recette ; les E2E layout interceptés sont distincts.
L’exécution effective et la CI sont consignées dans progress, pas déduites de cette procédure.
