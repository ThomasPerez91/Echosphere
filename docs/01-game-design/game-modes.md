# Modes de jeu et familles d’univers

**Statut : décisions produit Q19–Q29/Q55 closes le 31/10/2026 ; fonctionnalités de modes futures.**
Provenance : instruction utilisateur explicite de finalisation de PR #8. Les caps sont des valeurs
initiales configurables ; aucune capacité de charge n’est démontrée par ces décisions.
Universe reste la frontière d’instance, ni utilisateur ni processus. Le socle comptes/memberships/
bindings existe depuis 5C ; les parcours produit ci-dessous ne sont pas livrés par 5D.

| Famille canonique | Humains, valeurs initiales | Admission | Durée et pause gameplay |
| --- | --- | --- | --- |
| SOLO | 1 humain | Aucune admission extérieure | Open-ended ; pause autorisée |
| PRIVATE | Maximum initial 8 humains | Invisible publiquement par défaut, invitation uniquement | Open-ended par défaut ; pause seulement avec accord de tous les participants humains actifs |
| PERSISTENT | Objectif 200 memberships humaines, référence 50 GameSessions simultanées | CLOSED / APPROVAL / OPEN | Aucune fin automatique ; jamais de pause gameplay |

## Parties et configuration (Q19/Q20/Q22/Q26/Q27/Q28)

PRIVATE est configurable dans les limites d’un ruleset supporté, progresse sans joueur connecté,
et pourra accueillir des IA lorsqu’elles seront implémentées. Aucune condition de victoire
obligatoire MVP ; aucune durée maximale obligatoire par famille. Chaque Empire démarre indépendant,
sans équipe/alliance imposée. Empire partagé et alliance restent deux notions distinctes.

Chaque Universe épingle une version précise du ruleset. Seule vitesse produit initiale : **1x**.
Préparer d’autres profils techniquement sans les activer ; aucune modification silencieuse du
ruleset d’un univers existant. Les multiplicateurs employés par les tests ne sont pas des presets.
En pause, progression gameplay et IA doivent réellement être suspendues. Une maintenance technique
n’est pas une pause gameplay. Aucun système de pause n’est implémenté dans ce lot.

## Décisions utilisateur du 09/11/2026 — création de parties (Q59)

Provenance : retours de recette locale et réponses explicites de l’utilisateur le 09/11/2026.
Elles complètent Q19–Q29/Q55 ; en cas d’écart, **ces décisions priment** sur les valeurs initiales
ci-dessus pour SOLO et PRIVATE.

- **Priorité** : SOLO et parties à plusieurs (famille PRIVATE, appelée « multi » ou « coop » en
  interface) d’abord ; PERSISTENT plus tard.
- **Création en libre-service** depuis le Portal ; un compte peut créer et rejoindre **plusieurs
  parties**. La création ne demande aucune vérification supplémentaire (la confirmation d’adresse
  se fait à l’inscription ; l’entrée dans un univers garde sa règle existante).
- **Multi = un seul mode** : pas de « coop » distincte ni de pacte ou d’équipe imposés ; les
  joueurs s’allient, coopèrent, se trahissent ou s’affrontent en jeu avec les mécanismes existants.
- **Taille PRIVATE** : jusqu’à **10 joueurs humains** (remplace le maximum initial de 8) et de
  l’ordre de **30 IA**, toujours plafonnés selon la taille de la carte.
- **Invitation** : au choix du créateur, **soit un lien** à copier-coller, **soit un envoi par
  email** ; jamais les deux pour une même invitation.
- **Génération de carte** (lot futur) : tailles proposées 100, 300, 500, 1 000 et 2 000 systèmes ;
  placement des Empires au choix (par exemple *Dispersé* : placement aléatoire ; *Regroupé* : les
  Empires joueurs proches) ; nombre maximal de joueurs et d’IA déterminé par la taille.
- **Garde-fou** : rester loin d’un jeu « Stellaris-like » ; le gameplay des grandes cartes et du
  grand nombre d’Empires est à revoir avec l’utilisateur avant d’activer ces options (Q59 ouverte
  sur ce point, comme la démonstration de charge Q29).

## Décisions utilisateur du 09/11/2026 — vie d’une partie (Q60)

Provenance : réponses explicites de l’utilisateur le 09/11/2026 (questions à choix).

- **Abandon en multi** : l’Empire d’un joueur qui quitte une partie en cours est **repris par une
  IA** ; la partie continue pour les autres, l’IA joue avec les mêmes règles (aucun bonus, aucune
  ressource offerte).
- **Abandon en SOLO** : la partie est **archivée**, pas supprimée : retirée des parties actives,
  plus jouable, rapports consultables ; aucune donnée effacée.
- **Notifications en jeu (cloche)** : attaque annoncée, fin de construction et de recherche,
  missions terminées (arrivée, cartographie, colonisation, retour), diplomatie et contact.
  Elles ne sont jamais une autorité : chacune renvoie à l’écran qui porte l’état serveur.
- **Nom d’Empire** : choisi par le joueur à la création et en rejoignant une partie, visible dans
  « Mes parties ».

## Compte global, Empire partagé et départ (Q21/Q23)

Un compte global peut participer simultanément à plusieurs univers : User → UniverseMembership →
Universe → EmpireBinding/permissions. **Un Empire peut être partagé par plusieurs joueurs.**
Les profils conceptuels administrateur d’Empire, opérateur et observateur désignent des ensembles
de permissions ; ils ne les contournent jamais. Aucun Empire.owner_user_id comme autorité unique.
Les bindings/permissions 5C/5D sont le socle existant ; aucune UI de partage n’est livrée ici.

Quitter retire l’accès, sans supprimer automatiquement l’Empire ni son monde. Sans participant
humain, l’Empire devient dormant ; aucune prise de contrôle IA implicite avant le lot IA.

## Late join et protection (Q24/Q25)

PERSISTENT autorise le late join si admissions ouvertes, capacité disponible, point de départ valide,
ruleset compatible et protection nouvel entrant applicable. Le nouvel arrivant crée normalement un
nouvel Empire ; rejoindre un Empire existant relève du partage Q21. PRIVATE exige invitation et
autorisation de late join. Les politiques d’admission ne donnent jamais de droits gameplay directement.

Protection persistent : maximum initial configurable **7 jours réels**, fin anticipée en cas
d’action offensive volontaire. Impossible d’attaquer ou d’être attaqué pendant protection ; économie
et exploration accessibles, aucun bonus caché permanent de production. Le contrat devra articuler
fin de protection et acceptation de la première action offensive dans le lot combat. Q02 (protection
hors connexion générale) reste distincte et ouverte ; aucun combat/protection livré maintenant.

## Charge de référence (Q29)

Objectif architectural initial : 1 Universe persistent, 200 memberships humaines, 50 GameSessions
humaines simultanées, jusqu’à 500 Empires humains + IA à terme. Caps techniques configurables,
**à démontrer par benchmark**, jamais une capacité déjà validée. Voir [performance](../04-quality/performance.md).

[Vision](../00-product-vision.md) · [ADR 0006](../adr/0006-universe-game-instance.md) ·
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) · [Registre](../05-project/open-questions.md)
