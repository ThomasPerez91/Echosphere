# Recette locale UX05 — Portal, Empire, Colonie, Galaxie, Rapports

**Statut : procédure à exécuter par l’utilisateur (WSL2 + Docker), non encore exécutée.**
Elle valide en univers réel les écrans de la PR #19 avec les backends des PR #20 (trajet des
missions) et #21 (historique des constructions). Rien n’est fusionné : la branche
`recette/ux-weekend` réunit les trois PR pour ce test seulement (aucune PR, aucune CI dédiée ;
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

## 2. Compte, univers et accès

1. Ouvrir https://portal.echosphere.localhost:8443, créer un compte, puis confirmer l’adresse dans
   Mailpit (http://127.0.0.1:8025).
2. Identifiant du compte :
   ```bash
   docker compose exec portal-postgres psql -U echosphere_accounts -d echosphere_accounts \
     -tAc "select id from users where email='VOTRE_EMAIL'"
   ```
3. Univers (choisir un nom et une graine, les garder identiques aux deux commandes) :
   ```bash
   U=$(cat /proc/sys/kernel/random/uuid); echo $U
   docker compose exec portal-backend python -m portal_app.control.operator provision \
     --universe-id $U --backend primary --name "Recette UX" --seed recette-ux-1
   sleep 10   # livraison au Game par portal-control-worker
   docker compose exec backend python -m app.ai.worker --bootstrap $U \
     --name "Recette UX" --seed recette-ux-1 --ruleset v0.9
   ```
   La sortie liste les acteurs : le premier (`profile: null`) est l’Empire humain, noter son `empire_id`.
4. Accès avec tous les droits de l’Empire humain :
   ```bash
   docker compose exec portal-backend python -m portal_app.control.operator set-access \
     --user-id <ID_COMPTE> --universe-id $U --status active --bindings '[{"empire_id":"<EMPIRE_ID>","permissions":["colony.read","colony.construct","colony.cancel","research.read","research.start","research.cancel","galaxy.read","exploration.read","exploration.start","fleet.read","fleet.build","fleet.command","colony.expand","combat.read","combat.attack","relations.read","relations.negotiate"]}]'
   ```
5. Dans le Portal, « Actualiser mes parties » : la carte « Recette UX » passe à « Participation
   confirmée par Game », puis « Entrer dans cet univers ».

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
