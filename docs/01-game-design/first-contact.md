# Présence frontalière et premier contact

**Statut : orientation produit pré-MVP validée le 02/11/2026 (Q57, Q58), décisions D1–D7 validées
le même jour. Lot 13B démarré en avance sur une branche dédiée (B00–B07 implémentés, non validés à
l'exécution) : [plan](../05-project/step-13b-plan.md).** Provenance : instruction utilisateur explicite accompagnant la validation de Q18.
Ce document est la référence canonique : Flottes, Fog, Combat, IA et Recherche y renvoient sans
recopier de règles divergentes. Il n'autorise aucune implémentation pendant l'étape 13.

## Place dans la roadmap

Lot **13B — Présence frontalière & Premier contact**, après l'étape 13 Relations minimales et avant
l'étape 14, sans renuméroter 14–17. Il commence seulement après fusion et validation de l'étape 13.
Raison : l'UX sessions courtes (14) doit intégrer alertes de frontière, contacts inconnus,
détections, incidents et replis automatiques.

Critère de sortie futur : Q57/Q58 arbitrées dans leur détail runtime, transit par saut observable,
détection déterministe, quatre protocoles, auto-engagement et repli reproductibles, aucune fuite de
Fog, mêmes règles pour humains et IA.

## FC1 — Flotte stationnée en frontière

Une flotte opérationnelle (TASK) peut rester STATIONED dans un système connu, notamment en bordure
de Fog, avec un `first_contact_protocol`. Le protocole reste actif tant que la flotte est
stationnée, que le protocole n'est pas changé et que la flotte n'est ni repartie, ni détruite, ni
fusionnée. Cette présence vise à terme surveillance, défense, contrôle de passage et premier
contact. Ce n'est pas une Colony. Une flotte stationnée ne rend pas le système MONITORED de façon
permanente sans règle explicite.

## Les quatre protocoles

| Protocole | Détection et alerte | Engagement automatique | Particularités |
| --- | --- | --- | --- |
| `SURVEILLANCE` (FC2) | Oui | Jamais ; se défend si elle est attaquée | Empire inconnu : « signature étrangère détectée », sans identité |
| `AMBUSH` (FC3) | Comme SURVEILLANCE | Seulement contre une flotte d'un Empire **connu** et ennemi selon les faits/relations du futur contrat | Jamais contre un inconnu ; jamais sous pacte actif |
| `INTERCEPTION` (FC4) | Comme SURVEILLANCE | Toute flotte étrangère détectée, même inconnue ou supérieure | Aucune comparaison de puissance : posture volontaire ; acte hostile ; contact par le rapport de combat |
| `FRIENDLY_CONTACT` (FC5) | Oui | Jamais | Transmet volontairement identité d'Empire, système et date ; contact réciproque. Repli automatique si l'autre flotte agit avec hostilité (FC6) |

- **Détection ≠ contact nommé** : détecter une flotte d'un Empire inconnu ne donne pas son identité.
- Le sens d'« ennemi connu » pour AMBUSH sera fixé en 13B à partir de Q18, sans réintroduire un
  état diplomatique permanent (Q18 n'a que `NO_AGREEMENT` et `PACT`, l'hostilité est un fait daté).
- **FRIENDLY_CONTACT** ne révèle jamais stocks, infrastructures, technologies, autres flottes ni
  autres colonies.

## FC6 — Repli du protocole amical

Si la flotte étrangère déclenche une action hostile, la flotte en `FRIENDLY_CONTACT` tente un repli
déterministe, physique, soumis au moteur Flottes : ni téléportation ni disparition. Destination à
arbitrer en 13B ; préférence documentée : **système précédent de la route**, puis repli éventuel
vers un système connu accessible.

## FC7–FC8 — Détection et technologie d'espionnage

Détection déterministe, sans aléa. Chaque camp a un niveau de détection/espionnage :

| Comparaison | Résultat |
| --- | --- |
| notre niveau > niveau adverse | nous détectons ; l'adversaire ne nous détecte pas automatiquement |
| niveaux égaux | détection mutuelle |
| notre niveau < niveau adverse | nous ne détectons pas ; il traverse sans déclencher notre protocole |

Le principe d'une technologie de détection est validé. Restent ouverts pour 13B (Q58) : nom,
domaine Research, nombre de niveaux, coûts, durées, bonus annexes, séparation éventuelle
détection/furtivité. L'arbre Research v0.8 n'est pas modifié.

## FC9 — Passage dans les systèmes intermédiaires

Une flotte stationnée doit pouvoir détecter et intercepter une flotte qui **entre** dans son
système, y compris comme simple étape de sa route. Le moteur Flottes actuel ne matérialise pas ces
passages : 13B devra auditer les étapes de mission, les événements par saut, la présence logique en
transit, la concurrence de plusieurs flottes, l'ordre temporel, les fences Combat, le rappel, le
carburant et la reprise après crash. Interdit : simuler une interception intermédiaire au départ ou
à l'arrivée finale. Le serveur doit connaître la date logique d'entrée dans chaque système traversé.

## FC10–FC12 — Contrôle de passage, Fog et pactes

- **Bloquer** signifie contrôler un passage par détection et réaction, jamais un mur absolu.
  SURVEILLANCE ne bloque jamais ; AMBUSH/INTERCEPTION n'agissent que sur une flotte détectée.
- Une détection de flotte ne révèle ni colonie du système, ni propriétaire de planète, ni
  ressources, Research, routes ou autres flottes. Une observation de flotte datée séparée pourra
  être créée ; le Fog reste l'information effectivement obtenue.
- Un **pacte actif prime** sur AMBUSH et INTERCEPTION : aucune bataille interdite par un pacte à
  l'instant logique pertinent, avec les garanties de Q18 B7 (aucune fuite, indépendance de l'ordre
  des workers, dates logiques).

## FC13 — IA future

Aucun choix de protocole IA pendant l'étape 13. Orientation non validée pour 13B :
`economic_cautious` favorise Surveillance / Friendly Contact, `expansionist` Surveillance / Ambush ;
Interception reste une posture volontaire très agressive.

## Décisions D1–D7 — 02/11/2026

**Validées explicitement par l'utilisateur** (PR #17). Elles précisent FC1–FC13 ; implémentation :
[plan 13B](../05-project/step-13b-plan.md), [contrat technique](../03-technical/frontier-api-ui.md).

- **D1 — Niveau initial.** Tous les Empires ont le niveau de détection 0, provisoire avant toute
  technologie (Q58 reste ouverte : aucun catalogue Research). Niveaux égaux : détection mutuelle.
- **D2 — Détection au passage.** À l'entrée réelle d'une flotte dans un système où stationne une
  flotte dotée d'un protocole, évaluée à la date logique `entered_at`, indépendamment du moment de
  traitement. Une entrée annulée ne détecte rien ; un rejeu ne crée aucun doublon ; un passage réel
  est traité après redémarrage ; un protocole activé après le passage ou une flotte partie avant
  ne détectent jamais rétroactivement ; protocoles et présences suivent leur chronologie datée.
- **D3 — Information.** Système, date logique, signature anonyme. L'Empire n'est nommé que s'il
  était déjà connu du détecteur à cet instant ou par divulgation volontaire autorisée
  (FRIENDLY_CONTACT). Jamais composition, effectifs, cargo, origine, destination, itinéraire,
  technologies, ressources, colonies ni indicateur aller/retour. Pas de contact nommé automatique.
- **D4 — Ennemi connu (AMBUSH).** Empire déjà identifié par un contact, ayant commis un acte hostile
  effectivement résolu contre l'Empire du surveillant dans les 72 dernières heures logiques
  (`ambush_hostility_seconds`, ruleset v0.9), et aucun pacte couvrant l'instant de l'engagement.
  Une proposition refusée ne suffit pas. Jamais d'état diplomatique permanent.
- **D5 — Exception encadrée à Q02.** Le délai de 24 h s'applique toujours à ATTACK contre une
  planète. Une rencontre militaire automatique entre deux flottes physiquement présentes dans le
  même système (AMBUSH, INTERCEPTION) peut être résolue à l'instant logique du passage : jamais
  d'attaque planétaire instantanée, jamais avant l'entrée réelle, flotte réellement stationnée avec
  le protocole actif à cet instant, aucune interception à distance, pacte prioritaire, aucun
  dommage aux colonies/bâtiments/ressources, pertes limitées aux unités militaires, flotte
  exclusivement civile jamais détruite, résolution déterministe par le moteur Combat, rapport après
  résolution, aucun avantage IA. Les protocoles agressifs ne sont activés qu'une fois complets.
- **D6 — Missions.** Une flotte interceptée qui survit poursuit sa mission avec ses pertes ; détruite,
  sa mission est interrompue et ses passages non atteints annulés. Les pertes du surveillant sont
  conservées ; aucune unité ne réapparaît (retour, rappel, rejeu). Ni réparation, ni ravitaillement,
  ni perte civile.
- **D7 — Repli amical.** Destination : 1) système précédent du dernier itinéraire réel de la flotte,
  s'il reste accessible ; 2) sinon système de sa colonie d'attache par un chemin connu ; 3) sinon
  aucune destination inventée : la flotte reste et un repli impossible est enregistré. Moteur Flottes
  habituel, coûts normaux, aucun carburant gratuit ; fonds insuffisants : la flotte reste et l'échec
  est signalé. Déclenchement idempotent (une agression, un repli, un débit) ; une flotte restée sur
  place peut être attaquée selon les règles Combat.

### Arbitrages C01–C05 — 02/11/2026

Exigences C01–C05 **demandées par l'utilisateur** ; les règles de départage ci-dessous sont
**proposées par l'implémentation** (PR #17), sans règle de jeu nouvelle, et restent à confirmer en
revue. Statut : code écrit, tests PostgreSQL écrits non exécutés.

- **Couverture d'une entrée (C04).** Un protocole couvre une entrée à `t` s'il était actif
  *strictement avant* `t` et n'avait pas pris fin *avant* `t` (`started_at < t <= ended_at`). Un
  protocole activé exactement à `t` ne voit pas cette entrée ; un protocole arrêté exactement à `t`
  la voit encore. Aucun changement daté de `t` ou après ne modifie donc ce que `t` a vu.
- **Ordre au même instant (C04).** À un même instant `t` : 1) résolution des entrées (rang
  `entered_at`, mission, ordre du passage ; surveillants par identifiant de flotte), sur l'état
  strictement antérieur à `t` ; 2) replis amicaux à `t` ; 3) bataille planétaire à `t` (Q02
  inchangé, état inclusif comme en v0.7). Une production terminée exactement à `t` n'est pas
  engagée au passage (elle l'est dans la bataille planétaire), différence liée à la nature d'une
  rencontre au franchissement, Q02/Q10 inchangés.
- **Attaque locale (C03).** Une ATTACK de 0 saut lancée dans le système de la flotte amicale est
  l'acte hostile : repli à l'instant du lancement, donc au moins 24 h avant la bataille (Q02
  intact). Aucun repli si l'attaque ne vise pas une planète de l'Empire du surveillant.
- **Retard du worker (C05).** Une entrée échue gèle seulement le stream d'opérations de l'Empire en
  mouvement jusqu'à sa résolution (commandes de cet Empire : `combat_pending`) ; aucune entrée n'est
  omise, résolue sur un état postérieur, ni recalculée après coup.

## Hors étape 13

L'étape 13 ne crée ni champ de protocole, ni nouvelle mission, ni technologie d'espionnage, ni
furtivité, ni événement de passage, ni auto-interception/embuscade/repli, ni worker de patrouille,
ni UI de protocole, ni ruleset v0.9. Son code reste seulement compatible : contacts orientés,
hostilité comme fait daté, pacte vérifié à une date logique.

## Références

[Relations Q18](relations.md) · [Flottes](fleets.md) · [Brouillard](fog-of-war.md) ·
[Combat](combat.md) · [IA](artificial-intelligence.md) · [Recherche](research.md) ·
[Registre Q57/Q58](../05-project/open-questions.md)
