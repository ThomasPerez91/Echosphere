# Vision produit — Echosphere

**Statut : Décision validée pour la vision et les limites, sauf propositions explicitement signalées.**
Source : brief initial conservé dans le dépôt, confirmé/précisé par la mission de passation du
2026-10-28. [Index des décisions](06-handoff/decision-status.md), [provenance](06-handoff/source-map.md).

Echosphere est un jeu de stratégie spatiale **web, asynchrone et persistant**. Développer un empire,
spécialiser ses colonies, explorer un univers partiellement inconnu, rencontrer et influencer des
civilisations autonomes. Solo humain + civilisations IA pour le MVP ; privé/persistant multijoueur futurs.
Universe représente une partie, pas un compte ou un processus. La boucle complète reste à construire.

## Usage et promesse

**Décision validée** : environ dix minutes de gestion quotidienne pour organiser les priorités,
puis pouvoir quitter. Une à deux heures permettent d’analyser, explorer, optimiser et décider ;
rester connecté n’accroît pas artificiellement la production. Pas de bouton de récolte manuelle,
aucun rendement fondé sur les clics. Production et échéances progressent hors ligne ; univers continu.
Le combat est une possibilité de la progression, pas sa seule finalité. Aucun pay-to-win.

Inspiration : progression asynchrone type OGame, **sans clone** de ses mécaniques ni grille de galaxie.
Echosphere ne vise pas un Stellaris web lourd. Les mockups donnent un ton visuel, pas des règles :
nourriture, matière sombre ou biens qui y figureraient n’ajoutent pas de ressource principale.

## Boucle et deux couches

**Décision validée** : Develop → Explore → Discover → Colonize → Encounter → Interact → Strengthen
→ Expand influence → éventuellement Fight → recommencer. Référence : [boucle](01-game-design/core-loop.md).

| Couche | Rôle cible |
| --- | --- |
| Empire | Progression lente/asynchrone : économie, infrastructures, files, recherche et colonies |
| Command | Décisions actives compatibles avec l’asynchrone : missions, renseignement, mouvements, relations |

Le MVP cible réunit production/construction, recherche globale, graphe/exploration/fog, flottes,
colonisation, IA puis combat automatisé minimal et relations compréhensibles. Cela ne signifie pas
que ces systèmes sont livrés par la branche actuelle. Noms, stats et règles non décidées restent Qxx.

## Contraintes et orientations métier

- **Décision validée** : trois ressources cœur seulement, Alliages, Flux, Données.
- **Décision validée** : secteurs abstraits sans grille city-builder ; upgrade dans le même secteur,
  spécialisation émergente sans classe de planète imposée. Capacités variables futures.
- **Implémenté / Balance provisoire** : économie v0.1 interne de PR #5, cinq infrastructures,
  niveaux continus ; 1–5 = early game seulement. 12 secteurs/2 orbitaux = départ de référence,
  pas toutes les planètes. Les facteurs de croissance sont à simuler, pas des constantes définitives.
- **Décision validée, future** : recherche globale d’empire ; domaines Ingénierie/Énergétique/Calcul/
  Xénoscience provisoires ; pas des centaines de technologies au MVP.
- **Décision validée, future** : galaxie graphe 2D avec routes et génération seedée ; 30–50 systèmes
  pour prototype = repère, tailles futures configurables ; hubs/frontières/chokepoints possibles.
- **Orientation validée, future** : UNKNOWN/DETECTED/MAPPED/MONITORED ; humain et IA connaissent
  seulement leur projection, transitions/capteurs/fiabilité non encore fixés.
- **Orientation validée, future** : petit catalogue de rôles de flottes, missions asynchrones,
  pas de designer complexe. Combat automatisé futur, Q02/Q10 à résoudre avant exposition.
- **Orientation validée, future** : réseau défensif stratégique limité à modules persistants,
  coût surface/orbite/économie, dommages/réparations et Flux éventuel ; renseignement progressif.
  Défense dans Colony, pas de huitième entrée globale. Q30–Q38 restent ouvertes.
- **Orientation validée, future** : IA Utility/Goals déterministe/testable sans LLM stratégique,
  mêmes services, économie et fog que l’humain ; pas de spawn gratuit, possibilité de mauvaises
  décisions. Dialogue génératif éventuel facultatif et sans autorité stratégique.

[Économie v0.1](01-game-design/colony-economy-v0.1.md), [planètes](01-game-design/planets-colonies.md),
[recherche](01-game-design/research.md), [galaxie](01-game-design/galaxy.md),
[flottes](01-game-design/fleets.md), [fog](01-game-design/fog-of-war.md),
[défense](01-game-design/planetary-defense.md) et [IA](01-game-design/artificial-intelligence.md)
restent les références détaillées ; leurs propositions ne deviennent pas des décisions par ce résumé.

## Comptes, modes et parcours d’accès

**Décision validée, non implémentée** : compte global, plusieurs parties simultanées par utilisateur.
Landing → inscription/connexion → espace compte/lobby → liste/créer/rejoindre → sélectionner Universe
→ Game UI. User → UniverseMembership → Universe → éventuellement Empire/rôle/permissions ;
Empire.owner_user_id ne suffit pas. Empire partagé reste Q21.

Solo = base MVP. Privé = futur 2 à X humains, invitations/IA/vitesses/fin encore ouvertes. Persistant =
futur, potentiellement beaucoup de joueurs, aucune durée maximale obligatoire, late join préservé
architecturalement mais règles/protection non décidées. Les vitesses pourront varier par ruleset :
rapide, intermédiaire, classique, persistant sont des exemples, sans nouveaux multiplicateurs validés.
Voir [modes](01-game-design/game-modes.md) et [ADR 0008](adr/0008-control-plane-game-data-plane.md).

## Hors périmètre et limites

**Abandonné / hors périmètre MVP** : clone OGame, Stellaris web lourd, RTS temps réel, city-builder
détaillé, simulateur 3D, population/citoyens complexes, logistique physique lourde, armées terrestres
complexes, cinquante classes de vaisseaux, éditeur de vaisseaux avancé. Pas de quatrième ressource
principale sans décision. Diplomatie/commerce/espionnage/alliances avancés = futur/post-MVP ; les
relations IA minimales restent prévues, sans mécanismes inventés pour combler Q18.

## État réel et méthode

Étapes 0–4 intégrées ; 5A et cette passation sont sur PR #5 ouverte au début de mission. Aucun
compte/Portal/API gameplay, défense active, flotte, recherche, colonisation, IA ou combat jouable.
La cible technique sépare Portal et Game avec sessions autonomes, mais le code/Compose n’est pas
refondu ici. [Architecture](03-technical/architecture.md), [ADR 0008](adr/0008-control-plane-game-data-plane.md).

**Proposition de balance** : ratio 80/20 socle/spécialisation, tailles standard futures et seuils
restent à mesurer/valider. Seeds, simulations et playtests vérifieront les hypothèses ; aucune
balance ou garantie de capacité multijoueur n’est prouvée par les tests de construction.
[Roadmap](05-project/roadmap.md), [questions](05-project/open-questions.md), [progress](../progress.md).
