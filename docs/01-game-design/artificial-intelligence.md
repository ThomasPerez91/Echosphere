# Civilisations IA

**Statut : règles communes validées ; Utility/Goals orienté.**


L'IA est un acteur économique et stratégique autonome : elle explore, construit, recherche,
colonise et déplace ses flottes. Elle combat selon les règles communes. Commerce et négociation
avancés se développeront après le MVP ; des relations minimales sont prévues à l'étape 13.

## Moteur initial

Pas de LLM. Orientation : Utility AI / Goal-based AI déterministe et testable. Trois profils simples
peuvent suffire : expansionniste, économique/prudent, agressif. Paramètres envisagés : aggression,
expansion, economy, research, risk, diplomacy. Coefficients et cadence restent Q11.

## Équité vérifiable

Un humain et une IA demandent la même commande métier, par exemple un futur
`StartConstructionCommand`. Aucun crédit de ressources ni création d'unités réservé aux bots.
Les IA disposent d'une connaissance limitée et ne consultent pas le monde complet pour décider.
Le budget d'analyse peut différer mais pas les coûts, prérequis ou conditions de possession.

## Observabilité future

Enregistrer objectif, candidats accessibles, score et raison du choix sans exposer les secrets aux
joueurs. Rejouer une décision sur état figé. Les conditions de départ équitables restent Q11 ;
aucun handicap caché ne doit être ajouté au motif de rendre une partie plus difficile.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)
