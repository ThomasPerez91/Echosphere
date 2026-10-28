# Planètes et colonies

**Statut : Décision validée pour les secteurs ; Balance provisoire pour le départ v0.1, capacités futures variables.**


Une planète est un lieu physique ; une colonie est son exploitation par un empire. Cette distinction
conceptuelle évite de confondre exploration d'un monde et possession. L'identité de l'occupant
et le transfert de contrôle devront être arbitrés avant les migrations métier (Q04 et Q07).

## Capacité et spécialisation

Chaque secteur exploitable accueille une infrastructure. Aucune grille, aucun placement spatial.
Orientation : planète standard de 9 à 18 secteurs, départ autour de 12. Ce ne sont pas des limites
codées. Quelques emplacements orbitaux existent séparément des secteurs de surface.
L'empire se spécialise par ses choix de colonies ; pas de classe obligatoire Mineur/Guerrier/Scientifique.

## Traits naturels

Ressources abondantes, particularité énergétique, faible gravité, environnement difficile ou
position stratégique sont des exemples provisoires. Effets modérés et compromis : éviter un monde
objectivement parfait. La compatibilité des traits et leur distribution restent Q04.

## Charge de gestion

Orientation : une planète au départ, 2–3 tôt, 4–6 à mi-parcours, environ 8–12 tard avant une
éventuelle automatisation. Ce sont des ordres de grandeur de charge cognitive, pas des verrous
réglementaires définis. La cadence de colonisation dépend de Q07.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Étape 5A et défense future

La colonie de référence v0.1 fixe 12 secteurs, 2 slots orbitaux réservés et Command Core hors
secteurs. Les quatre infrastructures initiales et tous les chiffres proviennent de game_data.
Chaque infrastructure a un sector_index unique ; son upgrade ne consomme pas de nouveau secteur.
Voir [Économie v0.1](colony-economy-v0.1.md) pour stocks, production, stockage, file et annulations.

La [défense planétaire](planetary-defense.md) appartient à la colonie : infrastructure stratégique
persistante à modules limités, avec coût d’opportunité surface/orbite. Aucun système défensif actif,
réparation ou occupation orbitale dans le lot actuel. Pas de tables de défense anticipées.

## Portée des 12 secteurs / 2 orbitaux

**Balance provisoire** : ces chiffres concernent uniquement la planète initiale de référence v0.1,
non l’ensemble des futures planètes. **Orientation validée** : leurs capacités pourront varier ;
secteurs abstraits, spécialisation émergente par allocation, pas de classe de planète imposée.
**Implémenté** : initialize_colony contrôle aujourd’hui la capacité du ruleset de référence ; il ne
constitue pas encore un initialiseur général de planètes variées. Voir [audit #5](../06-handoff/pr-5-audit.md).
