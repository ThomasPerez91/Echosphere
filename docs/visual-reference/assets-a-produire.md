# Assets à produire (ChatGPT Image)

**Statut : liste de travail du 10/11/2026, tenue à jour au fil des lots.** Les images générées sont
déposées dans `frontend/public/assets/img/<dossier>/<fichier>.webp` (WebP, qualité ~82). Le code
affiche une image de repli tant qu’un fichier manque. Les mockups et images ne décident d’aucune
règle de jeu.

## Style commun (à coller en tête de chaque prompt)

> Illustration de concept art science-fiction, style peinture numérique détaillée et lumineuse,
> cohérente avec l’univers « Echosphere » : palette bleu nuit, cyan électrique et touches d’ambre
> doré, éclairage dramatique, atmosphère calme et majestueuse, technologie élégante et organique
> (formes courbes, anneaux, panneaux lumineux), aucune inscription, aucun texte, aucun logo, aucun
> personnage reconnaissable, aucune référence à une licence existante. Cadrage centré, sujet lisible
> en petit format, fond sombre dégradé sans éléments parasites.

Formats : **carré 1024 × 1024** (réduit à 640 × 640 pour les bâtiments, 512 × 512 pour le reste).

## 1. Bâtiments v0.11 (`img/batiments/`)

Noms retenus (choix de l’utilisateur, 10/11/2026) : **Chantier orbital** (vaisseaux) et **Centre de
recherche** (technologies).

| Fichier | Prompt (après le style commun) |
|---|---|
| `chantier-orbital.webp` | Un chantier spatial en orbite au-dessus d’une planète, immense berceau de construction en arc avec bras robotisés et poutres incandescentes, un vaisseau en cours d’assemblage dans sa cale, étincelles ambrées, halo cyan de la planète en dessous. |
| `centre-de-recherche.webp` | Un centre de recherche sur une colonie planétaire : dôme de verre et tours d’antennes en spirale captant des ondes lumineuses cyan dans le ciel, anneaux de données flottants, petites lumières ambrées aux fenêtres, crépuscule. |

## 2. Vaisseaux (`img/vaisseaux/`)

Vue de trois quarts, vaisseau seul sur fond spatial sombre, même famille de design (coques claires
gris perle, liserés cyan, réacteurs bleus).

| Fichier | Classe | Prompt |
|---|---|---|
| `sonde.webp` | Sonde | Petite sonde d’exploration élancée, grandes antennes et capteurs en éventail, un faisceau de balayage cyan fin devant elle. |
| `cargo-leger.webp` | Cargo léger | Cargo compact et trapu, modules de soute rectangulaires accrochés à une épine centrale, feux de position ambrés. |
| `extracteur.webp` | Extracteur | Vaisseau minier industriel aux bras foreurs repliés, tambour de collecte et réservoirs, poussière d’astéroïde lumineuse autour. |
| `colonisateur.webp` | Colonisateur | Grand vaisseau arche, anneau d’habitat rotatif et serres lumineuses, silhouette douce et rassurante. |
| `intercepteur.webp` | Intercepteur | Chasseur rapide et effilé, ailes en flèche, deux réacteurs intenses, posture agressive mais élégante. |
| `fregate.webp` | Frégate | Vaisseau de guerre moyen, coque allongée blindée, tourelles discrètes, bouclier cyan translucide léger. |
| `croiseur.webp` | Croiseur | Grand croiseur imposant, proue massive, rangées de batteries, multiples réacteurs, impression de puissance. |

## 3. Technologies (`img/technologies/`)

Illustration symbolique d’un concept (objet ou scène), pas d’interface ni de texte.

| Fichier | Technologie | Prompt |
|---|---|---|
| `fabrication-modulaire-1.webp` | Fabrication modulaire I | Bras robotisés assemblant des modules hexagonaux lumineux sur une chaîne en apesanteur. |
| `fabrication-modulaire-2.webp` | Fabrication modulaire II | Atelier orbital automatisé où des modules se combinent seuls en structure complexe, plus grand et plus lumineux. |
| `gestion-energetique-1.webp` | Gestion énergétique I | Cœur de réacteur cyan stabilisé par des anneaux de confinement, arcs d’énergie maîtrisés. |
| `gestion-energetique-2.webp` | Gestion énergétique II | Réseau de réacteurs reliés par des flux lumineux formant une constellation d’énergie. |
| `calcul-scientifique-1.webp` | Calcul scientifique I | Colonne de cristaux de calcul illuminés, motifs de circuits ambrés à l’intérieur. |
| `calcul-scientifique-2.webp` | Calcul scientifique II | Salle de cristaux de calcul en cercle autour d’un noyau holographique de données. |
| `protocoles-analyse-1.webp` | Protocoles d’analyse I | Scanner scrutant un fragment d’artefact flottant, faisceau cyan et symboles abstraits sans texte. |
| `protocoles-analyse-2.webp` | Protocoles d’analyse II | Plusieurs artefacts reliés par des faisceaux d’analyse révélant une carte d’étoiles abstraite. |

## 4. Opportunités de la galaxie (`img/opportunites/`)

| Fichier | Opportunité | Prompt |
|---|---|---|
| `ceinture-metallique.webp` | Ceinture métallique | Ceinture d’astéroïdes métalliques aux reflets argent et ambre devant une étoile lointaine. |
| `nuage-de-flux.webp` | Nuage de flux | Nébuleuse dense de gaz cyan lumineux traversée de filaments d’énergie. |
| `cristaux-memoriels.webp` | Cristaux mémoriels | Astéroïde couvert de cristaux translucides qui scintillent de motifs dorés comme des souvenirs. |
| `anomalie-spatiale.webp` | Anomalie spatiale | Distorsion circulaire de l’espace, étoiles déformées autour d’un anneau de lumière violette et cyan. |
| `epave-ancienne.webp` | Épave ancienne | Carcasse colossale d’un vaisseau inconnu très ancien, couverte de givre, lumières mortes. |
| `structure-inconnue.webp` | Structure d’origine inconnue | Monolithe géométrique impossible flottant dans le vide, arêtes parfaites, lueur intérieure. |
| `signal-artificiel.webp` | Signal artificiel | Balise isolée émettant des pulsations concentriques régulières dans l’espace sombre. |

## 5. Plus tard (lots suivants)

Portraits de planètes par type (rocheuse, océanique, glacée, volcanique, gazeuse) pour la Galaxie,
illustrations d’événements (premier contact, embuscade, extraction contestée).
