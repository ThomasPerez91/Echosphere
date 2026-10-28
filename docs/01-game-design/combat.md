# Combat MVP

**Statut : futur ; règles ouvertes.**


Le conflit est optionnel dans la boucle, mais un combat minimal fait partie du MVP final. Les unités
et dommages doivent être produits et résolus par les règles communes ; pas de flotte IA gratuite.
Aucune mécanique de combat n'est implémentée à l'étape 0.

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
jetables. Ciblage, pertes, défense/flotte et intégrité restent Q30–Q38 ; aucun moteur actif en 5A.
