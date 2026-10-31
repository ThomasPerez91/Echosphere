# Vue détaillée d’un système connu

**Décision validée par instruction utilisateur du 31/10/2026, étape 8 ; réalisation dans PR du lot.**
La vue met en forme la connaissance existante, sans nouvelle mécanique. [Plan](../05-project/step-8-plan.md),
[contrat technique](../03-technical/system-view.md). Q04/Q07/Q09 restent hors portée.

| Connaissance | Présentation autorisée |
| --- | --- |
| UNKNOWN / étranger / absent | Même 404, aucune information ni détail |
| DETECTED | Informations Galaxy existantes uniquement ; pas de vraie vue détaillée, retour Galaxy/exploration |
| MAPPED | Nom/position connus, date de cartographie, planètes et capacités snapshotées, routes connues ; observations anciennes clairement datées |
| MONITORED | Structure MAPPED et observation actuelle légitime de ses propres colonies uniquement, datée serveur |

Absence d’information ≠ système vide. Utiliser « Aucune donnée de présence disponible » ou
« Aucune présence actuellement observée » selon l’état. Aucune flotte, station, présence étrangère,
population, ressource, trait, anomalie, activité ou propriété de planète inventée.
La structure connue perdure après perte de surveillance et last_seen_at est conservé.

Présence propre déjà autorisée par Knowledge : mention générique possible avec galaxy.read.
Nom, rattachement à une planète et lien vers Colony exigent colony.read et vérification actuelle
Empire/Universe/colonie observée ; sans ce droit, aucun enrichissement Colony. Une ancienne
observation reste ancienne et ne fournit aucun lien d’action présenté comme actuel.

Navigation interne à Galaxy : sélectionner MAPPED/MONITORED → Voir le système. Deep-link avec
Universe/Empire/System explicites, retour Galaxy avec contexte, refresh et historique natifs.
Aucun huitième domaine principal. DETECTED conserve son panneau et son éventuelle exploration.

Composition : en-tête/datations, représentation sobre des mondes autour de l’étoile, liste textuelle
équivalente, présences observées, routes connues en rappel. Orbites dessinées = mise en page seule.
Références design-system/system-view/galaxy-map examinées, contenu illustratif non normatif.
Mobile 320/390/768/1440, panneaux réordonnés, pas de débordement, clavier/focus et cibles de 44 px.

GET de la vue ne cartographie rien, ne termine aucune mission et n’avance aucun stream. Seul le
refresh de monitoring déjà validé peut actualiser une observation locale. Exploration achevée
par le worker rend naturellement la structure disponible ; aucune échéance System View créée.
