# Défense planétaire

**Statut : décisions produit Q30–Q38 closes le 31/10/2026 ; aucune défense implémentée avant son lot.**
Provenance : arbitrages utilisateur explicites de finalisation de PR #8. Aucun catalogue chiffré,
table, module runtime, drain de Flux ou effet de combat ajouté dans cette mission.

## Réseau et espace (Q30/Q31/Q38)

Réseau défensif persistant à capacité dédiée, augmentable, avec coût réel en espace Colony.
Familles canoniques : **Point Defense**, **Anti-Ship**, **Shield**, **Sensor / Electronic Warfare**,
**Support / Repair**. Emplacements : **SURFACE**, **ORBITAL**.
La surface consomme une capacité/un secteur réel ; l’orbite de vrais slots orbitaux. Le coût
d’opportunité économique et spatial est réel, sans réserve gratuite implicite. Les chiffres,
catalogue précis, coûts et croissance restent à équilibrer dans le futur ruleset.

## Combat, dommages et énergie (Q32–Q36)

Défense locale planète/orbite ; elle ne devient jamais une flotte, mais peut combattre avec une
flotte alliée présente. Réparations avec ressources et temps, priorités ; recharge énergétique de
bouclier distincte de la réparation structurelle.

États du réseau : **NORMAL / ALERT / COMBAT**. Consommation de Flux accrue selon systèmes et état.
Flux insuffisant : dégradation/désactivation déterministe des systèmes énergétiques.
États des modules : **OPERATIONAL / DAMAGED / DISABLED / DESTROYED**.
Le ciblage fin dépend du renseignement ; sinon les dégâts se distribuent selon catégorie,
exposition, doctrine et type d’arme. Aucun moteur de résolution n’est développé ici.

## Renseignement et interface (Q37)

Renseignement lié à [Q08](fog-of-war.md), données datées et vieillissantes, aucune omniscience.
Les seuils/statistiques seront des paramètres de leur lot, pas une décision déduite d’un mockup.

La défense reste dans Colony : Vue d’ensemble / Infrastructures / Orbite / Défense, sans huitième
domaine global. La section actuelle affiche « Défense — système futur », sans données inventées,
commande, table DefenseNetwork/DefenseModule ou gameplay défensif.

[Registre Q30–Q38](../05-project/open-questions.md) · [Combat](combat.md) ·
[Planètes](planets-colonies.md) · [Navigation](../02-ux-ui/information-architecture.md)
