# Modes de jeu et familles d'univers

**Statut : familles produit et compatibilité architecturale validées ; modes multijoueurs futurs.**

Universe constitue la frontière d'une instance de jeu. Ni « un univers = un utilisateur », ni
« un processus serveur = un univers ». Plusieurs instances pourront coexister et progresser sans
qu'un joueur ou son navigateur soit connecté. Ce document n'ajoute aucun mode au code.

| Famille | Cible | Contraintes et statut |
| --- | --- | --- |
| Solo | Un humain avec plusieurs civilisations IA | Base du MVP initial |
| Partie multijoueur privée | Amis, environ 2 à X humains | Futur ; X et règles non décidés |
| Univers multijoueur persistant | Univers partagé pouvant accueillir beaucoup de joueurs | Futur ; continu, aucune durée maximale obligatoire |

## Solo, MVP initial

Construire la boucle du joueur face à des IA autonomes soumises aux mêmes règles et à une connaissance
limitée. « MVP solo » ne signifie pas que Universe possède implicitement un owner unique. La gestion
des comptes, de participation et d'autorisation n'est pas livrée par l'étape 3.

## Parties privées futures

Possibilités à discuter : invitations, nombre de places, IA optionnelles, vitesse/ruleset, durées
courtes/moyennes/longues et conditions de fin configurables. Ce sont des questions, pas un catalogue
validé. Aucune décision sur pause, départ en équipe, empire partagé, alliances ou changement de joueur.

## Univers persistants futurs

Fonctionnement continu indépendant des connexions et sans durée maximale obligatoire. Rejoindre
une instance déjà active doit rester possible architecturalement ; modalités de late join, protection
d'un nouveau joueur, rattrapage et accès exact restent ouverts. La comparaison à OGame concerne
uniquement la persistance : Echosphere conserve son gameplay original, sans grille ni récolte manuelle.
La stabilité économique et la protection hors connexion exigent encore des arbitrages.

## Participation et configuration futures

Une future association Account/User ↔ UniverseMembership ↔ éventuellement Empire ↔ rôle/permissions
pourra représenter contrôle d'empire, plusieurs joueurs, éventuel partage si validé, spectateur/admin
si nécessaire. Ni cette table ni Empire.owner_user_id ne sont implémentés actuellement.

Vitesses économie/recherche/déplacement, taille de galaxie, PvP, capacité d'accueil, inscription et fin
pourront relever d'une configuration Universe ou d'un ruleset/version. Pas de singleton gameplay
serveur. La configuration technique de connexion PostgreSQL peut être commune ; elle ne fixe pas
les règles des parties. Valeurs et politique de version restent à décider.

## Questions à arbitrer

Q19–Q29 distinguent règles privées, nombre de joueurs, partage d'empire, victoire/durée, join/leave,
late join, protection des nouveaux, vitesses, pause privée, équipes et dimensionnement persistant.
Aucune de ces décisions ne doit être prise par un agent pour faciliter une implémentation anticipée.

[Vision](../00-product-vision.md) · [ADR 0006](../adr/0006-universe-game-instance.md) · [Questions ouvertes](../05-project/open-questions.md)

## Compte global et plusieurs parties — décision validée, non implémentée

Un utilisateur peut participer simultanément à plusieurs univers et y avoir des empires différents.
User → UniverseMembership → Universe → éventuellement Empire/rôles/permissions ; le partage d’empire
reste Q21. Entrée via Portal/lobby puis handoff vers GameSession propre au Game Backend.
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) cadre les frontières, pas les règles de join/leave.
Parties rapides/intermédiaires/classiques/persistantes sont des exemples de vitesses configurables,
sans valeurs supplémentaires validées. v0.1 reste ×1 ; autres tests de vitesse ne sont pas des presets produit.
