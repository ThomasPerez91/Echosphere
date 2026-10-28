# Versions, intégration et releases

**Statut : workflow master validé ; versions de releases futures indicatives.**

master est l'intégration stable. Toute évolution : synchroniser master, branche courte work/feature,
CI, PR vers master, revue, puis merge uniquement sur autorisation. Pas de develop permanente et pas
de branche empilée pour contourner une fondation non intégrée. Tags/releases identifiées plus tard.
Le code porte encore 0.0.1 de développement ; aucun nouveau tag ou release n'est créé par ce lot.

## Préparer une release identifiée

Sur un commit intégré et validé : identifier version applicative, migrations et version des données,
notes de changement et incompatibilités, contrôles de restauration/rollback. Exécuter les checks et
le démarrage neuf. Tag et publication demandent une instruction explicite ; master n'est pas réservé
à la veille d'une release. Le premier MVP pourra être nommé v0.1.0, sans engagement de calendrier.

Compatibilité des univers, versions de rulesets et migration des données/payloads restent Q13/Q14.
Les futures familles multijoueurs n'imposent pas de durée maximale aux univers persistants.
Ne pas annoncer une CI verte sans vérifier la tête réelle. Ne pas supprimer une branche contenant
des écarts à conserver ; une branche historique n'est pas une étape obligatoire du workflow.

[Roadmap](roadmap.md) · [Definition of Done](../04-quality/definition-of-done.md)
