# Flottes et missions

**Statut : rôles et missions provisoires.**


Peu de classes au MVP. Rôles envisagés : sonde, transport léger, transport lourd, unité légère de
combat, escorte, unité lourde, colonisateur. Noms, statistiques et nombre final restent Q09.
Pas d'éditeur complexe de vaisseaux.

Missions envisagées : déployer, explorer, transporter, coloniser, attaquer, revenir. Chacune a une
destination, une échéance et un état serveur. La liste ne spécifie pas encore les règles de retour.

## Invariants proposés pour la conception

Une unité ne peut être engagée simultanément dans deux missions. Les routes sont validées sur le
graphe et selon les informations disponibles. Le commandement vérifie les coûts et la disponibilité
avant de réserver les unités. Les résultats sont traçables dans les rapports.

## Questions avant l'étape 9

Vitesses, trajet multi-sauts, capacité cargo, consommation de Flux, rappel, fusion/division, passage
en territoire étranger et visibilité restent Q09. Les timestamps remplacent toute simulation
continue de déplacement. Le client anime une projection et ne décide pas des arrivées.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)
