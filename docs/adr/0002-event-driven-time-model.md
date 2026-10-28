# 0002 — Temps différé et événements persistants

- Statut : acceptée (brief projet).
- Date de transcription : 2026-10-28.

## Contexte

Le jeu progresse hors connexion, sans calculer chaque planète toutes les secondes. Les longues
absences et redémarrages doivent préserver les actions et la production.

## Décision

Production calculée depuis un ancrage temporel et actions représentées par timestamps/événements
persistants dans PostgreSQL. UTC partout. Effets transactionnels, idempotents et récupérables.
Le moteur est documenté seulement à l'étape 0.

## Conséquences et alternatives

Rattrapage chronologique et segmentation des taux nécessaires. Ordre simultané et stratégie de locks
à préciser en Q13. Ticks globaux à la seconde et timers uniquement en mémoire rejetés : gaspillage
ou perte à la reprise. Aucun scheduler implémenté dans cette PR.

[Architecture](../03-technical/architecture.md) · [Index ADR](README.md)

## Portée et évolution documentaire

Note d’évolution : le texte de cette ADR décrit l’étape 0. Le moteur est **Implémenté depuis
PR #3** et étendu par 5A, voir [ADR 0005](0005-colony-time-engine.md) et [ADR 0007](0007-colony-economy.md).
