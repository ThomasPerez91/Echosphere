# Recette locale UX05 — Portal, Empire, Colonie, Galaxie, Rapports

**Statut : procédure à exécuter par l’utilisateur (WSL2 + Docker), non encore exécutée.**
Elle valide en univers réel les écrans de la PR #19 avec les backends des PR #20 (trajet des
missions), #21 (historique des constructions) et #22 (création de partie). Rien n’est fusionné : la branche
`recette/ux-weekend` réunit ces PR (puis #24 multi, #25 trajet des missions, #26 état de création) pour ce test seulement (aucune PR, aucune CI dédiée ;
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

**Rapports**
- Après une construction terminée : elle apparaît dans Rapports (filtre Constructions), avec la bonne
  heure. Missions terminées, recherche acquise, faits diplomatiques s’y retrouvent aussi.

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
