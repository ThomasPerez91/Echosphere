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

Formats : **carré 1024 × 1024** (réduit à 512 × 512).

## 1. Bâtiments v0.11

Rien à produire : le **Chantier orbital** utilise `img/batiments/anneau-amarrage.webp` et le
**Centre de recherche** `img/batiments/laboratoire-avance.webp`, déjà présents.

## 2. Vaisseaux (`img/vaisseaux/`)

Vue de trois quarts, vaisseau seul sur fond spatial sombre, même famille de design (coques claires
gris perle, liserés cyan, réacteurs bleus). **Design futuriste épuré : aucune parabole, aucune
grande antenne ni panneau solaire apparent** ; capteurs et émetteurs intégrés à la coque
(lentilles, bandes lumineuses).

| Fichier | Classe | Prompt |
|---|---|---|
| `sonde.webp` | Sonde | Petite sonde d’exploration élancée en forme de goutte, capteurs intégrés en lentilles lumineuses sur la proue, un faisceau de balayage cyan fin devant elle, aucune parabole. |
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

## 5. Vues Recherche, Flottes, Diplomatie (`img/vues/`)

Bannières d’en-tête comme celle de la Colonie (`img/colonie/hero-kareth.webp`) : **format large
2172 × 724** (générer en 1792 × 1024 puis recadrer au centre), sujet sur la droite, partie gauche plus
sombre et calme pour le titre et le texte, aucune interface ni texte.

| Fichier | Vue | Prompt (après le style commun) |
|---|---|---|
| `banniere-recherche.webp` | Recherche | Intérieur d’un centre de recherche futuriste : grande salle circulaire, hologrammes de molécules et de cartes stellaires flottant au-dessus d’une table lumineuse, silhouettes lointaines de chercheurs anonymes, verrières ouvrant sur une planète. |
| `banniere-flottes.webp` | Flottes | Hangar orbital immense ouvert sur l’espace, plusieurs vaisseaux élancés alignés sur des berceaux d’amarrage, un vaisseau qui sort par l’ouverture vers une planète bleue, lumières de piste cyan. |
| `banniere-diplomatie.webp` | Diplomatie | Chambre de négociation en orbite : table en anneau suspendue, projections holographiques de plusieurs emblèmes abstraits (formes géométriques, sans texte), grande baie vitrée sur une nébuleuse, atmosphère solennelle. |

Icônes de relation (optionnel, même style que les icônes SVG existantes, à demander séparément) :
pacte, contact neutre, hostilité, premier contact.

## 6. Plus tard (lots suivants)

Portraits de planètes par type (rocheuse, océanique, glacée, volcanique, gazeuse) pour la Galaxie,
illustrations d’événements (premier contact, embuscade, extraction contestée).
