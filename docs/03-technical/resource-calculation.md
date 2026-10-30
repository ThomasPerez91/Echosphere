# Calcul différé exact des ressources

**Statut : représentation technique de l'étape 3 implémentée ; équilibrage toujours ouvert (Q03).**

Trois clés internes seulement : alloys, flux, data, correspondant aux noms de travail Alliages,
Flux, Données. Le socle historique étape 3 n’imposait pas de valeurs ; les valeurs v0.1
sont désormais fournies par game_data au domaine Colony 5A.

## Représentation

Stocks et taux sont des entiers signés PostgreSQL BIGINT non négatifs en **micro-unités** :
1 unité de jeu = 1 000 000 micro-unités. Les taux sont exprimés par heure. Les timestamps sont
aware et normalisés UTC. La durée est calculée en microsecondes par jours/secondes/microsecondes,
sans conversion float. Cette précision est un choix technique réversible, pas une quatrième ressource.

`q, reste = divmod(taux_micro_par_heure × durée_microsecondes + reste_précédent, 3_600_000_000)`

`stock_suivant = stock_précédent + q`

Le reste entier est persisté ; le jeter à chaque lecture permettrait à la fréquence des lectures de
modifier le résultat. Les tests comparent un calcul long à mille calculs courts. La multiplication
utilise les entiers Python ; tout stock final hors BIGINT est refusé explicitement plutôt que tronqué.
Pas de taux négatif/entretien dans ce socle : son modèle métier reste Q03.

## Capacité optionnelle

Le socle générique accepte une capacité explicite nullable. Pour ses usages historiques, NULL
signifie absence de plafond configuré. Si elle est fournie, le stock sature au plafond et le surplus,
y compris son reste fractionnaire, est écarté. Cela évite de récupérer des heures de surplus après
une dépense. Le domaine 5A fixe les plafonds provisoires de sa référence et Logistics Center ; entretien et
évolutions supplémentaires restent ouverts.
Une absence de durée écoulée ne modifie ni stock ni reste. Un temps antérieur est refusé.

## Changements de taux et rattrapage

À un événement t1, le moteur règle [t0,t1] avec l'ancien taux, applique le nouveau puis poursuit
[t1,t2]. En retard de plusieurs heures, il emploie l'heure logique des événements, pas celle du poll.
Les trois ressources partagent settled_at économique ; cursor_at du stream est distinct. Tout ancrage incohérent bloque l'événement.
Les coûts, multiplicateurs, valeurs initiales et durées sont versionnés dans game_data v0.1 pour
Colony. L’initialisation générique historique reste un service interne à valeurs explicites.

## Concurrence et commandes futures

Toutes les écritures passent sous le verrou EventStream référencé par ColonyTimeline. Les futurs services de dépense
rattraperont d'abord les événements jusqu'à l'instant de commande et exigeront complete=True avant
vérification des fonds, dépense et enregistrement dans une seule transaction. Aucun endpoint de
ressources, bouton de récolte ou calcul critique navigateur n'est ajouté maintenant.

Q03 est partiellement cadrée : représentation/arrondis et balance v0.1 implémentés ; les chiffres
restent provisoires, entretien et rééquilibrage ouverts. L'historique et le stockage des événements sont définis dans le moteur temporel.

[Moteur temporel](event-engine.md) · [Économie](../01-game-design/resources-economy.md) · [Questions](../05-project/open-questions.md)

## Économie Colony v0.1

Les niveaux et le scaling utilisent des fractions entières. Coûts et durées de base : plafond à
chaque pas en micro-unités/microsecondes ; production/capacité : plancher. Durée effective plafond
à l’activation, bonus industriel courant et vitesse de construction snapshotée. Production perdue
au stockage plein, reste remis à zéro. Tous les changements de taux/capacité sont précédés d’un
règlement à la date logique. Aucun float ni plafond de niveau 5. Les chiffres sont dans game_data.
Remboursement théorique 100/80 %, plancher micro-unité ; crédit plafonné par ressource, excédent
définitivement perdu et annoncé avant confirmation, sans refus pour saturation (Q39 close). Voir [économie v0.1](../01-game-design/colony-economy-v0.1.md).
