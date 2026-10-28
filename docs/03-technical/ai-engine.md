# Conception du moteur IA

**Statut : futur ; orientation déterministe.**


Le moteur initial n'utilise pas de LLM. Un décideur Utility/Goals reçoit une observation autorisée,
un profil et un instant logique. Il évalue des objectifs, sélectionne une commande valide puis
passe par le service d'application commun. Les poids ne modifient pas les règles économiques.

## Séparation proposée

Observation filtrée → génération des options connues → score → départage déterministe → commande.
Un ordre stable de départage empêche l'ordre d'une requête SQL de modifier arbitrairement le choix.
Si un aléatoire devient utile, il devra être seedé et enregistré ; ce n'est pas encore décidé.

## Exécution future

Un AI_TURN persistant assure la reprise après crash. Budget de calcul, fréquence et backoff après
commande refusée relèvent de Q11/Q13. Un refus normal, tel qu'une ressource devenue insuffisante,
ne déclenche ni ressources compensatoires ni accès privilégié.

## Tests attendus

État identique et profil identique donnent la même décision ; connaissance cachée inaccessible ;
refus métier identiques à ceux des humains ; autonomie sur plusieurs cycles ; trace expliquant
les scores ; simulations headless sans HTTP. Commerce et diplomatie avancée ne doivent pas être
introduits pour « compléter » l'IA du bootstrap.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
