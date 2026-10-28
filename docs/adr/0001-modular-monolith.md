# 0001 — Monolithe modulaire

- Statut : acceptée (brief projet).
- Date de transcription : 2026-10-28.

## Contexte

Un produit encore en définition doit pouvoir partager ses transactions et faire évoluer ses règles
sans coordination distribuée. Humains et IA doivent appeler les mêmes services.

## Décision

Un backend Python/FastAPI en monolithe modulaire, PostgreSQL unique source de vérité ; frontend
React/TypeScript/Vite. SQLAlchemy et Alembic lors de la persistance métier. Redis seulement sur besoin.

## Conséquences et alternatives

Les modules restent séparés dans le code et partagent une livraison. Un worker pourra exécuter le même
code dans un processus dédié. Simplicité opérationnelle et transactions communes ; discipline requise
pour éviter un module omniscient. Microservices rejetés au départ : coût sans besoin démontré.

[Architecture](../03-technical/architecture.md) · [Index ADR](README.md)
