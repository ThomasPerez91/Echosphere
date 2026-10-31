# System View — projection et navigation

**Contrat étape 8, autorisé le 31/10/2026.** [Produit](../01-game-design/system-view.md),
[plan](../05-project/step-8-plan.md). Zéro migration, nouveau droit, scheduler ou donnée de jeu.

Réutiliser GET `/game/{universe}/galaxy/{empire}/systems/{system}` avec galaxy.read.
GameSession/principal → accès effectif/binding → stream Exploration verrouillé → SystemKnowledge
scopée. UNKNOWN/étranger/absent : même 404. DETECTED garde le DTO minimal existant.
MAPPED/MONITORED : projection de SystemKnowledge et PlanetKnowledge snapshotées, jamais jointure
vers StellarSystem/Planet pour enrichir la structure. Pas de catch_up, ni avancement du curseur,
ni scheduler au GET détail ; Galaxy générale et ses commandes gardent leur contrat étape 7.

Ajouts au détail cartographié : server_time, empire_id, permissions utiles, routes vers voisins
connus seulement, observations de présence propre datées et liens Colony facultatifs. Routes
lues depuis RouteKnowledge + SystemKnowledge du même Empire/Universe ; voisin DETECTED sans nom.

Observation source = own_colony_ids existants. MAPPED conserve l’ancien snapshot sans le réenrichir
via Colony live. MONITORED + colony.read : seules colonies propres encore présentes, observées,
dans les planètes connues du système ; leur nom vient de PlanetKnowledge. Cette requête sert à
vérifier le lien d’accès actuel, jamais à découvrir une colonie étrangère ou enrichir le monde.
Sans colony.read : présence générique, aucun détail/lien Colony supplémentaire.

Frontend : fragment `#universe/{universe}/galaxy/system/{empire}/{system}`. Vue dédiée avec GET
détail seulement, annulable/timeout, identité scope vérifiée dans le DTO, réponse tardive ignorée,
pas de mutation au montage/StrictMode ni polling. Galaxy mémorise Empire/sélection/cadrage dans
le shell en mémoire pour le retour ; aucune carte cachée ni cache autoritaire. Deep-link Colony
`#universe/{universe}/colony/overview/{colony}` appelle la lecture autorisée réelle.

Recette : étendre le smoke Galaxy existant (projet/bases/volumes jetables *_test) pour ouvrir le
système de départ, revenir, lancer Exploration/page fermée, preuve DB MAPPED avant lecture,
puis nouvelle System View, Portal coupé et expiration. Comparer planètes/capacités à Knowledge.
Les tests UI interceptés sont distincts de cette recette réelle ; résultats et CI dans progress.
