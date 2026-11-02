# Combat MVP

**Statut : Q02 et Q10 closes pour le Combat MVP v0.7 seulement (02/11/2026) ; étape 12 en cours.**
Les sections antérieures restent l'orientation historique ; les décisions ci-dessous priment.


Le conflit est optionnel dans la boucle, mais un combat minimal fait partie du MVP final. Les unités
et dommages doivent être produits et résolus par les règles communes ; pas de flotte IA gratuite.
Aucune mécanique de combat n’est implémentée jusqu’au checkpoint 5A. Résolution automatisée
future, jamais un RTS ; cette mission n’ajoute aucun combat.

## Contraintes validées

Pas de RTS, armées terrestres complexes, logistique militaire ultra détaillée ou cinquante classes
au MVP. Le combat doit rester compréhensible avec peu de rôles, produire un rapport et pouvoir être
simulé sans interface. Les spécialisations ne créent pas d'écarts absurdes.

## Arbitrage requis Q10

Formule de résolution, présence ou absence d'aléatoire, ciblage, retraite, pertes, butin, occupation,
siège et défenses restent ouverts. Un prototype de calcul ne vaut pas validation de ces choix.
La protection hors connexion Q02 doit être traitée avant de permettre une attaque persistante.

## Validation future

Rejouer un affrontement depuis son entrée/version, vérifier conservation des unités et des coûts,
absence de double résolution, résultat explicable, égalité des règles humains/IA et cas limites
(flottes vides, forces très asymétriques, événements simultanés).


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Orientation défense planétaire

Voir [Défense planétaire](planetary-defense.md) : réseau limité de modules persistants, dommages et
réparations envisagés, coût surface/orbite et consommation future de Flux. Pas de piles de canons
jetables. Principes Q30–Q38 validés le 31/10/2026 dans la référence défense ; valeurs et moteur restent futurs.

## Q02/Q10 — décisions Combat MVP v0.7, 02/11/2026

**Validation utilisateur explicite, limitée au ruleset v0.7.** Q02 et Q10 seront à rouvrir pour
toute mécanique de pillage, conquête, occupation, siège ou bombardement. Q03, Q04 (hors
sous-décisions déjà prises), Q14, Q18 et Q25 restent ouvertes ou futures.
[Plan COM00–COM11](../05-project/step-12-plan.md).

### Q02 — protection hors connexion

- **Indépendance de la présence :** la protection ne dépend jamais du statut connecté ou
  déconnecté. Aucune dernière connexion, session active, statut en ligne ni activité navigateur
  n'est révélé ou utilisé.
- **Fenêtre de réaction :** toute ATTACK attend au moins 24 h (`min_warning_seconds = 86400`)
  avant résolution :
  - `travel_arrival_at = started_at + trajet` ;
  - `battle_at = max(travel_arrival_at, started_at + 24 h)` ;
  - le délai est tenu par le worker serveur, jamais par un navigateur.
- **Portée destructive limitée :** seules les unités militaires participant au Combat peuvent être
  détruites. Jamais de destruction de colonie ou de bâtiment, ni de baisse d'infrastructure. Pas de
  vol de ressources ou de cargo, pas de perte de Research, pas de capture ni d'occupation, pas de
  bombardement ni de siège. Une longue absence peut coûter une flotte militaire laissée sur place,
  jamais la progression économique.
- **Protection du nouvel arrivant :** Q25 reste future. Aucun `UniverseMode` ni protection de
  7 jours n'est créé dans ce lot.

### Q10 — résolution déterministe

- **Principe :** automatisée, instantanée au temps logique `battle_at`, sans hasard, critique ni
  esquive, sans action tactique. Même snapshot + même ruleset = même résultat exact.
- **Catalogue v0.7 (balance provisoire, stats Combat dans `combat.json`) :**

| Classe | Coût A/F/D | Fabrication | Saut | Flux/saut | Cargo | Coque | Attaque |
| --- | --- | --- | --- | --- | --- | --- | --- |
| interceptor | 180/90/30 | 30 min | 12 min | 6 | 0 | 100 | 50 |
| frigate | 450/200/80 | 60 min | 18 min | 12 | 0 | 300 | 100 |
| cruiser | 1000/450/180 | 2 h | 25 min | 25 | 0 | 800 | 260 |

- **Production :** celle des Flottes, inchangée :
  - file de 3, dont 1 actif ;
  - quantité de 1 à 20 ;
  - paiement immédiat, annulation 100/80, sortie en garnison.

  Ni chantier, ni emplacement orbital, ni entretien.
- **Matchups (bps) :**

| Attaquant ↓ / cible → | interceptor | frigate | cruiser |
| --- | --- | --- | --- |
| interceptor | 10000 | 7500 | 15000 |
| frigate | 15000 | 10000 | 7500 |
| cruiser | 7500 | 15000 | 10000 |

- **Rounds simultanés :**
  1. Effectifs vivants figés au début du round.
  2. Chaque classe cible la classe ennemie vivante ayant son meilleur multiplicateur ; une égalité
     se départage dans l'ordre canonique des classes.
  3. Dégâts = effectif × attaque × matchup, en entiers. Une unité détruite coûte coque × 10000.
     Les dégâts partiels s'accumulent d'un round à l'autre. Le surplus envoyé sur une classe éteinte
     est perdu, sans changement de cible dans le round.
  4. Pertes appliquées simultanément ; aucun premier tir.
- **Fin :** dès qu'un camp n'a plus d'unité militaire. Issues possibles : `attacker_win`,
  `defender_win`, `mutual_destruction`, `unopposed` (vraie colonie étrangère visée, aucun
  défenseur militaire). Aucun effet économique.
- **Après la bataille :** aucune coque persistante, les survivants repartent intacts, aucune
  réparation. Pas de retraite pendant le Combat : le défenseur part avant `battle_at`, l'attaquant
  rappelle sa mission avant `battle_at`.
- **Mission ATTACK :** une planète connue d'un système MAPPED ou mieux, un chemin connu, des
  classes militaires seulement et un cargo nul.
  - **Sans fuite :** le lancement ne révèle jamais si la planète est vide, occupée ou défendue. Sans
    cible étrangère au lancement, la mission est acceptée puis échoue `target_unavailable` à
    l'échéance et revient, au même coût.
  - **Défenseur lié au lancement :** le défenseur est figé en interne au lancement, sous le verrou
    planète partagé avec COLONIZE. Une colonie apparue ensuite n'est jamais combattue.
  - **Locale :** une autre planète du même système, avec 0 saut, 0 carburant et
    `battle_at = started_at + 24 h`.
  - **Coût :** carburant aller-retour payé au départ par la colonie d'attache,
    `2 × sauts × Σ(effectif × Flux/saut)`. Pas de second débit, pas de remboursement.
- **Rappel :** possible tant que `now < battle_at`.
  - en transit : rappel symétrique ;
  - arrivée mais avant bataille : retour = rappel + trajet ;
  - locale : stationnement immédiat.
- **Retour :** les survivants rentrent automatiquement au système d'origine en un trajet (déjà
  payé). En local, ils stationnent aussitôt. Une flotte opérationnelle vidée passe `DESTROYED`
  (ligne conservée). Une garnison vide reste stationnée sans unité.
- **Défenseurs :** à `battle_at`, toutes les unités militaires de toutes les flottes STATIONED de
  l'Empire défenseur dans le système cible (garnisons et flottes opérationnelles). Les civils sont
  ignorés : ils ne tirent pas, ne subissent rien et n'apparaissent pas au rapport. Le défenseur
  peut réagir avant `battle_at` avec les commandes normales.
- **Pertes défenseur :** agrégées par classe, puis réparties entre les flottes au plus fort reste
  déterministe selon les effectifs d'avant Combat (départage par id de flotte).
- **Rang :** plusieurs attaques se départagent au rang `(battle_at, started_at, engagement_id)`.
  Une attaque moins bien classée ne dépasse jamais une meilleure encore active sur le même système.
- **Rapports :** après la bataille seulement, ils révèlent l'Empire adverse, les compositions
  militaires engagées, les pertes, les survivants, l'issue et `battle_at`. Jamais les stocks,
  infrastructures, Research, cargo, flottes civiles ou autres colonies. Observation datée, sans
  MONITORED permanent ni voisin révélé.
- **Alerte du défenseur lié :** « Force hostile en approche », avec planète, système, `battle_at` et
  état (en attente ou annulée). Ni attaquant, ni origine, ni route, ni composition.
- **Hors périmètre :** butin, occupation, siège, bombardement, conquête, modules de défense
  (Q30–Q38 restent reportés au runtime), relations (étape 13), offensive IA (Q18 ouverte).
