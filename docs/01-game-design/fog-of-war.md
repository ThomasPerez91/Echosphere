# Brouillard de guerre

**Statut : décision produit Q08 close le 31/10/2026 ; implémentée pour Galaxie/Exploration à l’étape 7 (PR #10, [technique](../03-technical/galaxy-api-ui.md)).**
Provenance : arbitrage utilisateur explicite de finalisation de PR #8.

| État canonique | Sens validé |
| --- | --- |
| UNKNOWN | Aucune connaissance, aucune fuite client |
| DETECTED | Existence et position approximative connues |
| MAPPED | Structure du système connue durablement |
| MONITORED | Information dynamique actuellement actualisée |

Perte de surveillance : **MONITORED → MAPPED**. Les découvertes structurelles ne sont pas oubliées.
Les informations dynamiques vieillissent avec `last_seen_at` ; afficher leur date, pas un état
actuel inventé. Aucun partage automatique du fog entre joueurs, même si une alliance future existe.
UNKNOWN interdit de transmettre les données puis de les masquer en CSS. Cartes, rapports, API et
journaux doivent utiliser la même autorisation de connaissance côté serveur.

Les IA auront la même projection de connaissance que les humains. Seuils numériques de capteurs,
fiabilité et cadence d’observation restent des paramètres des futurs systèmes ; cette décision
n’implémente ni capteurs, ni exploration, ni espionnage.

## Défenses et renseignement futurs

Q37 rattache le renseignement défensif à ces états, avec données datées et vieillissantes.
Q36 conditionne le ciblage fin au renseignement ; aucun détail omniscient de module par défaut.
Voir [défense](planetary-defense.md), [exploration](exploration.md), [temps serveur](../03-technical/event-engine.md)
et [registre](../05-project/open-questions.md).
