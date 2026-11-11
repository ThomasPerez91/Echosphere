# Passation — refonte UX/UI (pour ChatGPT Work ou tout autre agent)

**Statut : passation écrite par Claude le 03/11/2026, mise à jour après UX04 (carte de commandement réelle). Règles communes :
[AGENTS.md](../../AGENTS.md). Plan et décisions : [refonte UX/UI](../02-ux-ui/redesign/README.md).**

## Où en est le chantier

| Champ | Valeur |
| --- | --- |
| Branche | `work/ux-redesign`, créée depuis `b97bd0e` (tête de `work/step-13b-first-contact`) |
| PR | [#19](https://github.com/ThomasPerez91/Echosphere/pull/19) **Draft**, base `work/step-13b-first-contact` (dépend de #17, elle-même de #16) |
| Tête et CI | Voir le bloc « Reprise rapide — refonte UX » de [progress](../../progress.md) |
| Écrivain actif | Aucun après cette passation ; **un seul agent à la fois** sur cette branche |
| Hors périmètre | master, branches de #16/#17/#18, backend, migrations, `game_data`, règles |

## Ce qui est livré

- UX00 audit, UX01 navigation et 8 wireframes, UX02 directions et tokens, UX03 prototype.
- Décisions utilisateur D-UX-1 à D-UX-7 transcrites ([plan](../02-ux-ui/redesign/README.md)).
- [UX04](../02-ux-ui/redesign/ux04-live-command-map.md) : carte de commandement branchée sur les vraies
  projections dans Galaxie, derrière l’interrupteur « Nouvelle carte de commandement » / « Carte classique »
  (défaut : classique). Composants dans `frontend/src/command/`, prototype conservé.
- Contrat [UX-API-01](../03-technical/ux-api-01-mission-path.md) (chemin de mission) et plan
  d’implémentation backend ; **non implémenté**, aucune PR ouverte.

## Ce qui attend l’utilisateur

1. Recette en univers réel de la nouvelle carte (procédure dans UX04) ; tant qu’elle n’est pas faite,
   le parcours n’est pas « validé en univers réel ».
2. Autoriser (ou non) une PR backend séparée pour UX-API-01, branche suggérée `work/ux-api-01-mission-path`.
3. Décider quand la nouvelle carte devient l’affichage par défaut et quand retirer le raccourci
   « Envoyer une flotte ici » de la carte classique.

## Comment reprendre

```bash
git fetch origin && git switch work/ux-redesign   # vérifier d'abord : git status propre, SHA = PR #19
cd frontend && npm ci && npm run lint && npm test && npm run build
npx playwright install chromium && npx playwright test e2e/live-command.spec.ts e2e/prototype.spec.ts
npm run prototype                                  # comparaison : http://localhost:5173/prototype/
```

Règles à garder :

- `src/command/` ne doit jamais importer `src/prototype/` (seuls les tests utilisent ses fixtures).
- Aucune règle métier côté client : trajets, coûts, durées, refus = réponses serveur ; après une
  commande acceptée, relire les projections, ne jamais fabriquer de mission.
- Fog of War : n’afficher que les projections de l’Empire ; positions interpolées libellées « estimée ».
- D-UX-4/5 : aucune unité de garnison engagée sans choix explicite ; attaque sans unité par défaut.
- Parité clavier/mobile (cibles 44 px, feuille du bas ≤ 960 px, pas de survol seul).
- Ne jamais présenter un test comme exécuté sans run réel ou CI vérifiée sur le SHA.

## Prochaine tâche recommandée

Recette locale UX04 (Compose + navigateur), puis, sur autorisation, UX-API-01 dans une PR backend
séparée ; ensuite écran Rapports centralisé + cloche (D-UX-6).

## Pièges connus

- Les projections Galaxie (coordonnées, routes) et Flottes (systèmes, flottes, missions) sont
  séparées : joindre par identifiant de système, même Empire.
- `MissionView` et `Quote` n’ont pas de chemin : sans UX-API-01, nombre de sauts et ligne indicative ;
  `Quote.path` est optionnel côté client et supprimé s’il est mal formé.
- La colonisation depuis une garnison ne règle pas le cargo sur la carte (écran Flottes pour cela).
- La Fast CI ne se déclenche pour cette PR que grâce à l’entrée temporaire `work/step-13b-first-contact`
  dans `.github/workflows/ci.yml` ; la retirer au rebase sur master.
- Fast CI sur `6ba6d89` : lint sans avertissement, 114 tests Vitest (dont 14 du prototype), build.
