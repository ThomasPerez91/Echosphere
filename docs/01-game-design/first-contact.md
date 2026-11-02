# Présence frontalière et premier contact

**Statut : orientation produit pré-MVP validée le 02/11/2026 (Q57, Q58). Lot 13B démarré en
avance sur une branche dédiée (B01–B02 implémentés, non validés) : [plan et arbitrages](../05-project/step-13b-plan.md).** Provenance : instruction utilisateur explicite accompagnant la validation de Q18.
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

## Hors étape 13

L'étape 13 ne crée ni champ de protocole, ni nouvelle mission, ni technologie d'espionnage, ni
furtivité, ni événement de passage, ni auto-interception/embuscade/repli, ni worker de patrouille,
ni UI de protocole, ni ruleset v0.9. Son code reste seulement compatible : contacts orientés,
hostilité comme fait daté, pacte vérifié à une date logique.

## Références

[Relations Q18](relations.md) · [Flottes](fleets.md) · [Brouillard](fog-of-war.md) ·
[Combat](combat.md) · [IA](artificial-intelligence.md) · [Recherche](research.md) ·
[Registre Q57/Q58](../05-project/open-questions.md)
