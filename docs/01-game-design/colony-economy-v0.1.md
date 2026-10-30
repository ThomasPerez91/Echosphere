# Colony — Économie v0.1

**Statut : règles demandées pour l’étape 5A ; balance v0.1 provisoire, à simuler.**

Source exécutable : [game_data v0.1](../../game_data/rulesets/v0.1/colony.json),
[catalogue](../../game_data/rulesets/v0.1/infrastructures.json),
[ressources](../../game_data/rulesets/v0.1/resources.json). Chargement strict JSON/Pydantic sans
nouvelle dépendance. Ces valeurs sont un point de départ d’équilibrage, pas des constantes Python.

## Colonie de référence

Départ de référence v0.1 seulement : 12 secteurs, 2 slots orbitaux réservés pour plus tard, Command Core hors secteurs (conceptuel,
sans bâtiment/table ajouté). Secteurs 1–4 : Extraction Complex I, Flux Reactor I, Data Node I,
Industrial Complex I ; 8 libres. Stocks : 2000 Alliages, 1500 Flux, 750 Données. Production initiale :
120/100/60 par heure. Capacité sans Logistics Center : 10 000 de chaque ressource.
Le service initialise une colonie existante sur une planète de capacité conforme au ruleset ;
il ne génère pas d’univers, ne colonise pas et ne crée pas d’identité utilisateur. Ce contrôle
actuel est limité à la référence ; il n’impose pas 12/2 à toutes les futures planètes.

## Catalogue et niveaux continus

Extraction Complex, Flux Reactor et Data Node sont répétables ; Industrial Complex et Logistics
Center sont limités à un exemplaire chacun par colonie. Une infrastructure occupe un sector_index
explicite. Un nouvel exemplaire consomme un secteur ; un upgrade garde son secteur. Les réservations
dans la file comptent pour les secteurs et l’unicité. Les prérequis éventuels doivent être achevés.

Les niveaux 1–5 sont seulement l’early game de référence. Aucune limite à cinq niveaux : progression
continue jusqu’aux limites de représentation ou aux conditions du ruleset, sans plafond de design
implicite. Les parties de plusieurs mois/années et différents rythmes restent compatibles.

| Niveau | Extraction : Alliages/h | Réacteur : Flux/h | Data Node : Données/h |
| --- | ---: | ---: | ---: |
| 1 | 120 | 100 | 60 |
| 2 | 210 | 175 | 105 |
| 3 | 360 | 300 | 180 |
| 4 | 600 | 500 | 300 |
| 5 | 960 | 800 | 480 |

Les taux s’additionnent sans rendement décroissant ; deux Extraction II produisent 420 Alliages/h.

| Niveau cible producteur | Alliages | Flux | Données | Durée de base |
| --- | ---: | ---: | ---: | --- |
| 1 | 250 | 120 | 0 | 2 min |
| 2 | 800 | 350 | 50 | 15 min |
| 3 | 2600 | 1100 | 250 | 1 h 30 |
| 4 | 8500 | 3600 | 1000 | 6 h |
| 5 | 28000 | 12000 | 4000 | 18 h |

L’upgrade paie uniquement le niveau cible. Dès le niveau 6, récurrence sur le niveau précédent :
coût ×1,38 ; durée ×1,28 ; production ×1,12. Valeurs configurées par infrastructure.

## Industrie et logistique

| Niveau | Bonus construction | Coût A/F/D | Durée de base |
| --- | ---: | --- | --- |
| 1 | +10 % | 400 / 250 / 75 | 8 min |
| 2 | +20 % | 1000 / 600 / 150 | 20 min |
| 3 | +35 % | 3200 / 1800 / 600 | 2 h |
| 4 | +55 % | 11000 / 6000 / 2000 | 8 h |
| 5 | +80 % | 36000 / 20000 / 7000 | 24 h |

Après 5 : coût ×1,40, durée ×1,30, +5 points de pourcentage de bonus par niveau (6 : +85 %,
10 : +105 %). `durée effective = durée de base / (vitesse construction × (1 + bonus))`.
Le bonus n’est évalué qu’au démarrage effectif : Industrial II puis Extraction III dans la file
font bénéficier Extraction du nouveau bonus. Un chantier actif n’est jamais recalculé en cours.

| Niveau logistique | Capacité de chaque ressource | Coût A/F/D | Durée de base |
| --- | ---: | --- | --- |
| 0 (absent) | 10000 | — | — |
| 1 | 20000 | 500 / 250 / 50 | 5 min |
| 2 | 35000 | 1400 / 700 / 150 | 30 min |
| 3 | 60000 | 4200 / 2200 / 600 | 2 h 30 |
| 4 | 100000 | 13000 / 7000 / 2200 | 9 h |
| 5 | 160000 | 40000 / 22000 / 8000 | 28 h |

Après 5 : coût ×1,40, durée ×1,30, capacité ×1,18. Le stockage est partagé par type de ressource,
pas un volume commun. Au plafond, production supplémentaire et reste fractionnaire sont perdus ;
aucun overflow caché. Les nouvelles capacités/taux s’appliquent après règlement à la date de fin.

## Arrondis, vitesses et représentation

Calcul serveur uniquement, entiers : 1 unité = 1 000 000 micro-unités, durée en microsecondes,
bonus en points de base (10000 = 100 %), multiplicateurs en fractions positives. Aucun float critique.
Conversion des niveaux explicites exacte ; chaque pas de scaling arrondit le coût et la durée de
base vers le haut à la micro-unité/microseconde, production et capacité vers le bas. Le taux après
vitesse économie est arrondi vers le bas. Durée effective arrondie vers le haut (minimum technique
1 microseconde). Remboursement arrondi vers le bas à la micro-unité.

Exemple Extraction VI : 38640/16560/5520, base 82944 s, production 1075,2 Alliages/h.
Les BIGINT signés et timestamps PostgreSQL/Python imposent un refus explicite d’une valeur ou date
non représentable ; pas de wrap, float, niveau max 5 ou saturation silencieuse d’un coût.

Chaque univers épingle sa copie validée du ruleset et ses vitesses. v0.1 est ×1. Les tests vérifient
économie ×1,5 et construction ×2. research_speed et fleet_speed sont seulement des champs préparés,
sans système associé. Aucune vitesse métier globale. Modifier les fichiers n’altère pas les univers
existants ; changement de ruleset/vitesse d’un univers actif hors lot, à migrer explicitement.

## File, réservation et annulation

Trois ordres maximum, actif inclus ; un seul actif par colonie. Prélèvement immédiat de tous les
coûts et insertion atomiques sous verrou du stream. Aucun second prélèvement au démarrage.
L’ordre conserve version, coûts, durée de base, niveau cible, type, secteur, multiplicateur de
construction et pourcentages de remboursement. L’acceptation exige un niveau contigu en tenant
compte des prédécesseurs réservés ; une file peut contenir un nouveau bâtiment puis son upgrade.
La file ne dépend jamais de la connexion du joueur ou d’une minuterie navigateur.

Annulation QUEUED : 100 % ; ACTIVE : 80 % ; le solde est perdu. Idempotence par identité d’ordre,
remboursement enregistré une seule fois. Annuler un prédécesseur annule aussi ses upgrades dépendants
sur le même secteur avec leurs remboursements propres ; les autres secteurs gardent leur ordre.
Le suivant démarre à la date logique de l’annulation. Les événements déjà échus sont traités avant
la commande : une construction achevée ne peut plus être annulée, même si le worker était en retard.

Cas de stockage insuffisant pour le remboursement : refus atomique et explicite, aucune partie de
l’annulation ou du remboursement n’est appliquée. Dépenser/libérer de la place permet de réessayer.
C’est un choix conservateur d’implémentation en attente de validation produit (Q39), afin de respecter
les 100/80 % sans inventer de stock hors plafond ni perdre un remboursement silencieusement.

## Limites

5D (PR #8) expose ces règles par une [API sécurisée et une UI réelle](../03-technical/colony-api-ui.md),
sans les recalculer : lecture, construction/amélioration et annulation sous GameSession. Toujours
hors périmètre : identité factice, création de partie, défense effective, orbitaux, flotte,
recherche, combat ou multijoueur. Orbite/Défense restent des états futurs explicites. La suite est 5B contrats identité/Portal-Game, 5C compte/lobby selon cadrage, 5D API/UI sécurisées.

- [Domaine et persistance](../03-technical/data-model.md) · [ADR 0007](../adr/0007-colony-economy.md)
- [Défense future](planetary-defense.md) · [Questions](../05-project/open-questions.md)

**Qualification de la cascade** : comportement implémenté, proposition produit/UX encore à confirmer
sous Q01. Les 100/80 % sont les règles v0.1 explicitement demandées ; Q39 garde la saturation ouverte.
