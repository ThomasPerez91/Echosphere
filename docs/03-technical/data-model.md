# Modèle de données conceptuel

**Statut : futur ; aucune table métier créée.**


| Concept | Responsabilité et relations proposées |
| --- | --- |
| Universe | Seed, version de génération, règles/version des données |
| Empire | Appartient à un univers ; pilotage humain ou IA |
| System / Route | Nœud et liaison du graphe, propres à un univers |
| Planet | Monde physique d'un système, traits et capacité |
| Colony | Exploitation d'une planète par un empire |
| Infrastructure | Occupation d'un secteur ou emplacement orbital de colonie |
| Research | État de recherche global d'empire |
| Fleet / Mission | Unités engagées et mouvement planifié |
| Knowledge / Report | Projection par empire et information datée |
| ScheduledEvent | Échéance persistante et référence métier |

Ce tableau organise les discussions ; noms SQL, colonnes et cardinalités détaillées restent à
concevoir aux étapes concernées. L'identité/authentification humaine n'est pas implémentée.

## Invariants à porter dans les futures migrations

Références cohérentes au même univers, absence de stock négatif, occupation de secteur valide,
une exploitation active d'un monde selon les règles à définir, unicité d'effet d'un événement.
Utiliser `timestamptz`, UTC applicatif et contraintes DB en complément des services.
L'historique d'occupation et les collisions de colonisation relèvent de Q07.

Proposition : IDs opaques, index des échéances et clés de visibilité par empire. Choix des types
numériques et précision monétaire/ressources à arrêter en Q03. Ne pas créer toutes ces tables
simplement parce que le diagramme conceptuel les mentionne.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
