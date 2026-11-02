# Echosphere — Art Bible et production des assets
**Statut : décisions artistiques validées le 02/11/2026 ; prototypes en cours, intégration non autorisée.**
**Branche de travail :** `art/asset-library-v01` (dérivée de `master` au commit `067a4e58863b910785764591d8bf3af4b0ec18e0`).
**Responsabilité :** bibliothèque graphique, concepts, nomenclature et préparation des exports — **sans modification du gameplay, des services ou du frontend**.

## 1. Décisions prises

- Echosphere est un jeu spatial navigateur **Free-to-Play** en solo et multijoueur.
- Les **trois directions artistiques sont retenues**, chacune avec le même niveau d'exigence de qualité :
  - **`realiste` — A / Réalisme orbital stylisé : gratuit et standard, pour tous.**
  - **`aristo` — B / Opéra impérial : collection premium, purement cosmétique.**
  - **`cyber` — C / Atlas holographique / convergence synthétique : collection premium, purement cosmétique.**
- Les packs premium transforment l'identité visuelle de l'Empire, **pas ses performances**. Un contenu de base ne doit jamais paraître volontairement dégradé.
- Les joueurs pourront à terme mélanger leurs assets possédés **si leurs contraintes de silhouette, lisibilité et composition sont compatibles**. Les règles d'équipement restent à concevoir et ne sont pas implémentées.
- **Le niveau recherché est concept art réaliste/cinématographique détaillé, jamais un simple pictogramme vectoriel** comme livrable principal. Les sketches vectoriels antérieurs ne sont pas des références de finition.

## 2. Langages visuels

### A — `realiste` : standard gratuit
- **Silhouettes :** ingénierie orbitale crédible, structures fonctionnelles, carénages mécaniques, épaisseur et modules lisibles.
- **Matériaux :** graphite, acier, alliages céramiques, surface légèrement usée, lumières de service ambre et réacteurs cyan contrôlés.
- **Commandants :** portraits humains expressifs, uniformes techniques, ni caricature ni surcharge d'ornements.
- **Vaisseaux :** cohérence de famille mais silhouettes distinctes selon classe ; l'impression d'échelle ne doit pas changer le rôle.
- **Bâtiments :** complexes industriels plausibles, fonctions visibles sans inventer de système jouable.
- **Planètes :** diversité rocheuse, atmosphérique et chromatique **visuelle uniquement** (aucun bonus, biome ou trait ajouté).
- **Cadrage :** réalisme illustratif à distance, priorité aux formes fortes, zones de respiration pour l'interface.

### B — `aristo` : premium opéra impérial
- **Silhouettes :** symétrie monumentale, coques-citadelles, flèches et formes architecturales cérémonielles.
- **Matériaux :** métal sombre, bronze/or patiné, panneaux bordeaux, pierre composite, lumière chaude.
- **Commandants :** vêtements de haute cérémonie et insignes, personnalité identifiable.
- **Vaisseaux et bâtiments :** structures spécifiques, pas une recoloration de la gamme A.
- **Lisibilité :** le rôle `frigate` reste perceptible comme frégate indépendamment du langage décoratif.

### C — `cyber` : premium atlas holographique
- **Silhouettes :** architectures géométriques, structures profilées, panneaux semi-transparents et modules synthétiques.
- **Matériaux :** alliage clair anthracite, polymères, verre technique, cyan/eau froide et lueurs numériques retenues.
- **Commandants :** visages synthétiques ou augmentés avec expressivité ; éviter l'uniformité robotique.
- **Vaisseaux et bâtiments :** géométrie originale cohérente, pas un simple filtre bleu du standard.
- **Lisibilité :** contrastes et luminosités compatibles avec l'UI navy, pas d'effets lumineux gênants.

## 3. Ancrage dans l'interface validée
Références prioritaires :
- `docs/visual-reference/README.md` et `docs/visual-reference/design-system.png` (cible UI, pas catalogue gameplay).
- `docs/02-ux-ui/design-system.md` (tokens actuels : fond `#080e19`, surfaces `#101a2a`, bordure `#2c3c51`, texte `#e2eaf4`, cyan `#83e3e8`, or `#f1d18f`).
- `AGENTS.md`, `context.md`, documents de conception et `game_data/rulesets/v0.7/`.
**Attention :** la couleur cyan est avant tout une ancre de l'interface ; elle n'est pas obligatoire pour toutes les civilisations.

## 4. Catalogue de gameplay de référence vérifié : v0.7
**Classes de vaisseaux** (identifiants immuables pour le mapping) :
`probe` (Sonde), `freighter` (Cargo léger), `colonizer` (Colonisateur),
`interceptor` (Intercepteur), `frigate` (Frégate), `cruiser` (Croiseur).

**Infrastructures du ruleset :**
`extraction_complex` (Complexe d'extraction), `flux_reactor` (Réacteur de Flux),
`data_node` (Nœud de données), `industrial_complex` (Complexe industriel),
`logistics_center` (Centre logistique).

**Recherches** : les 8 IDs canoniques de `game_data/rulesets/v0.7/research.json` dans 4 domaines (Ingénierie, Énergétique, Calcul, Xénoscience).
**Planètes** : ne pas inventer d'espèce, de trait, de capacité ou de ressource liée à leur apparence. Le rendu cosmétique n'influence pas la connaissance ou les propriétés du monde.
**Défense planétaire** : modules futurs validés conceptuellement mais non implémentés ; ne pas dessiner des batteries jouables supplémentaires dans des rapports v0.7.

## 5. Organisation des fichiers
```text
assets/
  doc.md                      # cette Art Bible, décisions + statut
  README.md                   # navigation et règles des fichiers
  catalogue-proposition.json  # manifeste de design, sans contrat runtime
  realiste/                   # A — gratuit
  aristo/                     # B — premium
  cyber/                      # C — premium
  (dans chaque collection)/
    commandants/
    emblemes/
    vaisseaux/
    batiments/
    planetes/
    orbite/
    recherches/
    rapports/
    diplomatie/
    fonds/
```
Les dossiers vides disposent d'un `.gitkeep` ; ils représentent une **intention de couverture**, pas des fichiers produits.

## 6. Règles de fabrication et d'export (orientations, non architecture adoptée)
- **Source de création** : conserver les originaux de concept art, leur provenance et leur statut. Un collage/planche d'exploration n'est pas un asset isolé détouré.
- **Fichiers browser** : préférer WebP/AVIF optimisés pour les grandes illustrations, PNG/WebP avec alpha quand utile, SVG pour les emblèmes réellement vectoriels. Validation ultérieure par tests de compatibilité et performance du frontend.
- **Tailles de travail proposées** : portrait carré >= 1024 px ; vaisseau vue 3/4 sur fond séparé >= 1536 px large ; décor planète ou bâtiment >= 1536 px ; miniatures 64/128/256 px. Ce ne sont pas encore des exigences runtime.
- **Variantes** : `source`, `preview`, `thumb`, `transparent` uniquement si la sortie correspond effectivement. Ne pas qualifier d'alpha une image ayant un fond opaque.
- **Nomenclature** : `<id-gameplay>__<vue>__vNN.<ext>` (ex. `frigate__three-quarter__v01.webp`) ; le nom du répertoire désigne le thème.
- **ID conceptuel stable** : `<theme>.<categorie>.<gameplay_id>.<variante>` ; la forme définitive d'un catalogue API, les permissions, références de base de données, caches et snapshots seront arbitrés dans un travail technique séparé.
- **Comparaison avant validation** : silhouette reconnaissable aux tailles de rapports, contraste, absence de confusion entre classes, absence de contenu du jeu inventé.
- **Production par lots limités** : première gamme standard représentative, ensuite toutes les classes A, puis déclinaisons B et C par mêmes IDs ; validation artistique entre les lots.

## 7. Rapports et Fog of War
- Combat spatial : portraits, emblèmes, silhouettes et skins effectivement équipés **uniquement pour les informations que le serveur autorise** ; valeurs de jeu et issue inchangées.
- Combat `v0.7` : les rapports ne révèlent que les classes militaires engagées, pertes, survivants, issue et temps de bataille, ainsi que l'Empire opposé. **Pas de bâtiments, stocks, recherches, unités civiles ou colonies supplémentaires adverses.**
- Assaut planétaire illustré avec bâtiments : **projet futur, non disponible en rapport v0.7**. Aucune destruction d'infrastructure, occupation, siège ou pillage implicite.
- Diplomatie : identités, portraits, emblèmes et compositions graphiques si ces données sont autorisées dans les API de relations.
- Rapport historique : prévoir un snapshot ou une résolution de fallback stable pour les skins retirés et une présentation standard quand l'asset manque ; décision technique future, pas de migration de schéma maintenant.
- Aucun contenu visuel ne doit masquer une information obligatoire, tromper sur la classe ou contourner la visibilité du Fog of War.

## 8. Inscriptions sur les coques — proposition à arbitrer
- Champ texte court et optionnel, rendu cosmétique dans la représentation lorsque la taille le permet.
- Normes de contrôle : longueur et alphabet autorisés, filtrage anti-insultes, Unicode confusable, liens interdits, signalement/modération, repli sur une version sûre.
- Texte de flanc **jamais** source de stats, privilège ou identité serveur autoritaire ; les textes peuvent être cachés sur les petites miniatures.
- Une inscription n'est **pas réservée aux payeurs** par principe : le modèle gratuit doit déjà disposer d'une personnalisation valable ; l'offre premium peut ajouter des typographies/ornements.

## 9. Invariants de monétisation
Aucun achat ne modifie : ressources, coûts, production, délais, capacités, statistiques, hitbox, recherches, données stratégiques, visibilité/discrétion, règles et résultats de combat, probabilités, limites, automatisations.
Les packs ne sont pas une espèce ou une faction de gameplay. Les noms alternatifs de technologies sont purement d'affichage et renvoient aux mêmes IDs du ruleset.

## 10. Statuts et validation
- **VALIDÉ :** trio A standard gratuit / B aristo premium / C cyber premium ; ambition réaliste/cinématographique ; pas de Pay-to-Win ; catégories par thème ; présence des cosmétiques dans les rapports selon droits.
- **À VALIDER :** chaque personnage, emblème, coque, architecture, paysage et rendu ; noms commerciaux ; charte de mélange ; prix ; direction définitive des illustrations ; droit/licences de distribution.
- **NON IMPLÉMENTÉ :** boutique, système d'équipement, contrats API, modération, rapports enrichis, cache et migration.
- Le fichier n'autorise aucune action de développement métier ou UI en dehors d'une mission explicite.

## 11. Historique de création
- 2026-11-02 : décisions artistiques consolidées, structure établie sur branche dédiée. Les premières planches photoréalistes de conversation sont des **références exploratoires**, pas des exports intégrables.
