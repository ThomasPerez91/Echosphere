# Calcul différé des ressources

**Statut : principe validé ; précision et plafonds ouverts.**


Pour un taux constant pendant l'intervalle :

`stock(t) = stock(t0) + taux_par_seconde × (t - t0)`

Toutes les dates sont UTC. L'unité temporelle et la précision sont explicites ; aucun flottant
binaire non maîtrisé pour un stock persistant. Type numérique, arrondis et stockage restent Q03.

## Mutation d'un taux

Avant d'achever un bâtiment à `t1`, régler `[t0,t1]` avec l'ancien taux, puis utiliser le nouveau
taux pour `[t1,t2]`. Lors d'un rattrapage, segmenter à chaque événement qui modifie les taux.
Ne jamais appliquer rétroactivement le taux courant à toute l'absence du joueur.

## Écritures concurrentes

À la demande de dépense, charger/verrouiller l'agrégat, appliquer ses événements dus, calculer son
stock effectif, vérifier le coût et persister stock/date/ancrage dans la même transaction.
Deux onglets ou une IA et une requête ne doivent pas dépenser les mêmes fonds. Les lectures peuvent
projeter un état sans écrire ; cette projection ne remplace pas le règlement autoritaire des mutations.

## Cas à trancher et tester

Stockage maximum, saturation puis dépense, entretien, absence de longue durée, changement de taux,
arrondi de petits incréments, horloge incohérente. Interdire les deltas négatifs ou les traiter selon
une politique explicite ; ne pas créer de perte silencieuse. Un compteur frontend est uniquement
une estimation, recalée sur les réponses du serveur.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
