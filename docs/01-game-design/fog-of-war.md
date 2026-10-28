# Brouillard de guerre

**Statut : connaissance limitée validée ; états conceptuels.**


| État conceptuel | Sens de travail, à préciser en Q08 |
| --- | --- |
| UNKNOWN | Aucune information exploitable |
| DETECTED | Existence détectée, détail non acquis |
| MAPPED | Informations cartographiées, potentiellement anciennes |
| MONITORED | Observation actualisée selon capteurs et règles à définir |

Ces états n'impliquent pas un contrat de visibilité déjà figé. UNKNOWN ne justifie pas d'envoyer
toutes les données au client avec un masque CSS. Les relations entre détection, carte et surveillance
ne sont pas nécessairement un simple compteur monotone.

## Information et temps

Associer une information connue à sa source et à sa date d'observation. Distinguer caractéristiques
stables et présence de flotte potentiellement périmée. La perte de surveillance et la dégradation
d'information restent Q08.

Les IA reçoivent la même projection de connaissance que les humains. Les futurs endpoints,
rapports, journaux accessibles et cartes devront chacun être contrôlés contre les fuites.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Défenses et renseignement futurs

La [défense planétaire](planetary-defense.md) sera révélée progressivement : force estimée, puis
installations probables/détectées, puis modules, intégrité et énergie estimée selon connaissance.
Pas d’omniscience, de capteur ou d’espionnage implémenté à l’étape 5A ; seuils/fiabilité restent ouverts.
