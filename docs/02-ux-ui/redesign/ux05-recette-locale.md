# Recette locale UX05 — Portal, Empire, Colonie, Galaxie, Rapports

**Statut : procédure à exécuter par l’utilisateur (WSL2 + Docker), non encore exécutée.**
Elle valide en univers réel les écrans de la PR #19 avec les backends des PR #20 (trajet des
missions), #21 (historique des constructions) et #22 (création de partie). Rien n’est fusionné : la branche
`recette/ux-weekend` réunit ces PR (puis #24 multi, #25 trajet des missions, #26 état de création, #27 cloche, #28 nom d’Empire / quitter / archiver, #29 distances) pour ce test seulement (aucune PR, aucune CI dédiée ;
chacune des trois têtes a sa Fast CI verte).

## 0. Ce qu’il faut

- Docker Desktop démarré (intégration WSL2), Git ; ports 8443, 8025, 5173 et 8000 libres.
- Une demi-journée au premier passage (builds, premières constructions), puis des passages courts :
  le jeu est asynchrone, certaines actions demandent d’attendre une échéance du serveur.

## 1. Préparer une pile séparée (vos données conservées ne sont pas touchées)

```bash
cd ~/projects/Echosphere
docker compose stop                        # pile conservée : arrêt seulement, volumes gardés
docker compose -p echosphere-demo stop 2>/dev/null || true
git fetch origin
git worktree add ../Echosphere-recette origin/recette/ux-weekend
cd ../Echosphere-recette
cp .env.example .env
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 300
docker compose --profile ai up -d ai-worker
docker compose ps -a
```

Le nom du dossier donne un projet Compose distinct (`echosphere-recette`) avec ses propres volumes.
Ne jamais lancer `down -v` dans le dossier de la pile conservée.

## 2. Compte et partie

1. Ouvrir https://portal.echosphere.localhost:8443, « Inscription », créer un compte, puis confirmer
   l’adresse dans Mailpit (http://127.0.0.1:8025).
2. « Nouvelle partie » (PR #22) : un nom, 0 à 3 adversaires IA, « Créer la partie ». « Mes parties »
   affiche « Création en cours », puis la partie avec « Entrer dans cet univers » après quelques
   secondes (le temps que le worker de contrôle livre au jeu puis accorde votre Empire).
3. Si la partie reste « Création en cours » plus d’une minute :
   `docker compose logs --tail=100 portal-control-worker game-control` et envoyer la sortie.

**Multijoueur (PR #24, jusqu’à 4 Empires humains + IA pour l’instant).** Deux comptes suffisent :
une deuxième adresse quelconque (Mailpit reçoit tout), dans une fenêtre de navigation privée.

4. Compte A : « Nouvelle partie » → « Multijoueur », 2 joueurs, « Lien à partager » (ou « Invitation
   par email », au choix, pas les deux), « Créer la partie ».
5. Lien : dans la carte de la partie, « Générer un lien d’invitation », « Copier le lien », puis l’ouvrir dans la fenêtre du
   compte B (connecté) → « Rejoindre la partie » → la partie apparaît dans « Mes parties » de B.
   Email : saisir l’adresse de B, le message arrive dans Mailpit ; B le voit aussi dans « Mes
   parties » (« Accepter » / « Refuser »).
6. Vérifier : « Joueurs : 2 / 2 », un nouveau lien ou une nouvelle invitation est refusé (« Toutes les
   places sont prises »), chacun entre dans l’univers avec son propre Empire.

**Vie d’une partie (PR #28, Q60).**
7. « Nouvelle partie » et « Rejoindre » : remplir « Nom de votre Empire » ; il s’affiche dans « Mes
   parties » et en jeu (profil en haut à droite, Relations des autres joueurs) après quelques
   secondes. « Renommer » depuis la carte de la partie.
8. Multi, compte B : « Quitter la partie » → confirmer. La partie passe sous « Parties quittées » ;
   côté A, l’Empire de B continue (IA, si `ai-worker` tourne) et sa place n’est pas reproposée.
9. Solo : « Archiver la partie » → confirmer. « Consulter cet univers » ouvre le jeu sans pouvoir
   donner d’ordre (boutons refusés par le serveur).

**Nouvelles cartes v0.10 (PR #33/#35/#36).** Toute nouvelle partie utilise le ruleset v0.10.
10. « Nouvelle partie » : choisir une taille de carte (100, 300, 500, 1 000 ou 2 000 systèmes). Le
    nombre d’Empires est plafonné par la taille (100 → 4, 300 → 12, 500 → 20, 1 000 et 2 000 → 40 ;
    10 humains et 30 IA au plus) : un réglage trop grand est refusé à la création.
11. En jeu, Galaxie : la carte a des impasses et des liaisons uniques (goulots) ; aucun Empire n’est
    isolé. Une grande carte (1 000 / 2 000) peut mettre quelques secondes de plus à se créer.

Une création qui n’aboutit pas s’affiche « Création retardée » (jeu injoignable, renvoi automatique)
ou « Création bloquée » (refus du jeu) au lieu de rester « Création en cours » (PR #26).

Les IA ne jouent que si `ai-worker` tourne (`docker compose --profile ai up -d ai-worker`, étape 1).

<details><summary>Procédure opérateur (ancienne méthode, en secours)</summary>

```bash
docker compose exec portal-postgres psql -U echosphere_accounts -d echosphere_accounts \
  -tAc "select id from users where email='VOTRE_EMAIL'"
U=$(cat /proc/sys/kernel/random/uuid)
docker compose exec portal-backend python -m portal_app.control.operator provision \
  --universe-id $U --backend primary --name "Recette UX" --seed recette-ux-1
sleep 10
docker compose exec backend python -m app.ai.worker --bootstrap $U \
  --name "Recette UX" --seed recette-ux-1 --ruleset v0.9
docker compose exec portal-backend python -m portal_app.control.operator set-access \
  --user-id <ID_COMPTE> --universe-id $U --status active --bindings '[{"empire_id":"<EMPIRE_ID>","permissions":["colony.read","colony.construct","colony.cancel","research.read","research.start","research.cancel","galaxy.read","exploration.read","exploration.start","fleet.read","fleet.build","fleet.command","colony.expand","combat.read","combat.attack","relations.read","relations.negotiate"]}]'
```
</details>

## 3. Parcours à vérifier

Pour chaque point : OK, ou capture + ce qui ne va pas. Tester aussi sur téléphone (ou Chrome en
mode appareil, 390 px) et au clavier (Tab, Entrée, Échap).

**Portal**
- Accueil déconnecté : logo, héros, carte de compte, boutons « Connexion »/« Inscription » du haut.
- Connexion, déconnexion, MFA si vous l’utilisez ; « Mes parties » : statut, dates, entrée.

**Jeu — coquille et Empire**
- Logo, nom d’univers (lien vers le Portal), sélecteur de colonie, ressources qui avancent.
- Empire : stocks, production, constructions en cours, mini-carte, alertes, événements récents.

**Colonie**
- Lancer une construction, puis une amélioration ; annuler un ordre (aperçu du remboursement).
- À l’échéance, l’ordre disparaît de la file sans recharger la page (ou après « Actualiser »).

**Recherche et Flottes**
- Lancer une recherche ; construire une sonde, puis un colonisateur et des vaisseaux militaires.

**Galaxie (nouvelle carte par défaut)**
- Fond animé, légende, noms, routes ; recherche d’un système ; filtres.
- Clic sur un système : menu contextuel avec les actions possibles ; Échap le ferme.
- Cartographier un signal avec la sonde ; déplacer une flotte ; coloniser un monde libre ;
  préparer une attaque (résumé serveur) ; rappeler une mission. Après chaque envoi : flotte sur la
  carte et dans « Vos flottes », pas de double envoi si vous cliquez deux fois.
- Flotte en route sur plusieurs sauts : la ligne suit les systèmes réellement traversés (PR #25) ;
  après un rappel, le libellé indique « Retour estimé en miroir de l’aller ».
- La « Carte classique » reste accessible et fonctionne.

**Cloche (PR #27)** — l’icône en haut à droite : pastille de non-lus, attaques annoncées,
constructions et recherches terminées, missions, diplomatie ; un clic ouvre la liste et remet le
compteur à zéro ; chaque entrée mène au bon écran. À la toute première visite, l’historique est
considéré comme déjà lu.

**Distances (PR #29)** — Galaxie, clic sur un système, onglet « Aperçu » : « N sauts » depuis votre
colonie la plus proche (« Inconnue » sans route connue).

**Flottes sur la carte (PR #34)** — un symbole au-dessus d’un système où stationnent vos flottes ;
un clic ouvre la fenêtre de la flotte (composition, mission, changement de protocole). « Déplacer » :
la fenêtre se réduit en haut à gauche, filigrane « Choisir une destination » ; un clic sur un
système choisit, clic droit ou Échap annule et rouvre la fenêtre.

**Opportunités (PR #35/#36)** — Galaxie, système cartographié, onglet « Données » :
- avant prospection, seulement le nombre de signatures ; un signal (non cartographié) n’en montre aucune ;
- « Prospecter » (une sonde, 30 min, 0 saut possible dans votre système) : les gisements (ressource,
  réserve datée, débit) et curiosités apparaissent ;
- « Étudier : <curiosité> » : la flotte doit avoir une sonde **et** une soute (cargo) libre pour
  les Données (sinon refus « soute insuffisante ») ; à la fin, les Données sont dans la soute,
  à décharger sur une colonie ; une deuxième étude de la même curiosité est refusée.
- « Extraire : <gisement> » (PR #37) : flotte avec au moins un Extracteur et de la soute libre ;
  durée réglable (1–24 h) et choix « Rester sur place » / « Revenir au point de départ » (carburant
  aller-retour payé au départ). À la fin, le chargement est en soute ; « Rappeler » pendant
  l’extraction l’arrête et garde ce qui est extrait. Deux flottes sur le même gisement se partagent
  le débit au prorata de leurs Extracteurs.

**Rapports**
- Après une construction terminée : elle apparaît dans Rapports (filtre Constructions), avec la bonne
  heure. Missions terminées, recherche acquise, faits diplomatiques s’y retrouvent aussi.

## 3 bis. Correctifs du 09/11/2026 au soir

- PR #38 (Portail) : fond plein écran sous la navbar en connexion/inscription, logo agrandi, effet
  bouton sur toutes les entrées de navigation, bandeau de statistiques qui ne chevauche plus les
  boutons de « Mes parties ».
- PR #39 (contrôle Portal → Game) : les créations solo restaient « Création bloquée »
  (`invalid_receipt`) ; après mise à jour, les créations en attente aboutissent d’elles-mêmes au
  prochain essai du worker de contrôle (environ une minute).
- PR #41 : cartes « Mes parties » réorganisées (nom et état sur l’illustration, informations alignées,
  état coloré) ; **Supprimer** une partie solo ou une création bloquée (confirmation en deux temps,
  accès révoqué, migration Portal p0009) ; « Prolonger l’accès » remplace « Confirmer de nouveaux
  droits » et n’apparaît que lorsque l’accès (fenêtre de quelques heures) se termine ; carte : toutes
  les étoiles visibles, « Voir toute la galaxie », effet radar retiré ; les créations bloquées
  avant #39 aboutissent.
- PR #42 : onglet Infrastructures réordonné (file, bâtiments existants avec leur niveau suivant
  dans la même ligne, nouvelles constructions avec les indisponibles grisées), stock retiré de
  l’en-tête de colonie, **renommer la colonie** (migration Game 0018), jauge de stockage à la place
  de la courbe 24 h, barres de progression fluides, notifications nouvelles marquées « Nouveau »,
  sélecteurs univers/colonie de même taille, état des services caché sauf s’il est indisponible.
- COL-11 (v0.11, nouvelles parties seulement) : départ avec extraction, réacteur et nœud ;
  premières améliorations en minutes ; Chantier orbital (← industriel 2) requis pour les vaisseaux,
  Centre de recherche (← nœud 3) pour la recherche ; bâtiments clés uniques ; bâtiments verrouillés
  grisés avec « Débloqué par … » ; plafond de niveau selon la planète.
- Flottes (10/11) : une commande de plusieurs vaisseaux livre les unités une à une (« 2 / 5
  livrées ») ; v0.11 : les gisements se régénèrent (10 % par jour). Migration Game 0019.
- **Partie de test** (10/11, migration Game 0020) : dans « Nouvelle partie », type **Test** (solo,
  refusé si le Portal tourne en production). La partie démarre presque terminée : les sept bâtiments
  au niveau 10, toutes les technologies acquises, toute la galaxie cartographiée avec ses routes, une
  garnison avec chaque classe de vaisseau, 250 000 de chaque ressource. Les Empires adverses sont
  visibles sur la carte (anneau « Empire inconnu n ») mais restent inconnus des Relations (aucun
  contact). En jeu, le bouton **TEST** de la barre du haut ouvre les outils : fixer les stocks d’une
  colonie (plafonnés par son stockage) ou « Remplir au maximum », ajouter des vaisseaux en garnison,
  « Tout terminer maintenant » (constructions, recherches et commandes de vaisseaux, files comprises).
  Les trajets de flotte gardent leur durée normale.
- La pile de recette porte le nom de projet Compose `echosphere` sur ce poste : elle partage les
  volumes de la pile conservée. Ne jamais lancer `down -v`.

Lire une création bloquée (lecture seule, base Accounts) :

```bash
docker compose exec -T portal-postgres psql -U echosphere_accounts -d echosphere_accounts -c \
  "select created_at, attempts, last_error, envelope->'message'->>'kind' as kind from control_outbox where state = 'pending' order by created_at;"
```

## 4. En cas de problème

```bash
docker compose ps -a
docker compose logs --tail=200 backend worker frontend portal-backend portal-control-worker
```

Envoyer : l’écran, la largeur (ordinateur ou téléphone), ce qui était attendu, la capture et, si
possible, la console du navigateur (F12 → Console).

## 5. Après la recette

```bash
docker compose down            # dans Echosphere-recette : arrêt, volumes de recette gardés
cd ../Echosphere && docker compose up -d   # pile conservée si besoin
```

Pour tout effacer ensuite (recette seulement) : `docker compose down -v` **dans le dossier
Echosphere-recette**, puis `git worktree remove ../Echosphere-recette`.
