# Défense planétaire

**Statut : direction de game design validée pour étude ; systèmes et valeurs non implémentés.**

La défense sera une infrastructure stratégique configurable et persistante. Ce n’est pas un
empilement de milliers de canons légers/lourds ou lance-missiles consommables. Une future colonie
pourra avoir un Planetary Defense Network dont la capacité limitée se répartira entre modules.
Noms définitifs, volumes, statistiques et interactions restent ouverts (Q30–Q38).

## Modules envisagés

| Famille | Modules possibles, noms provisoires |
| --- | --- |
| Detection | Sensor Network |
| Orbital Interception | Kinetic Batteries, Autonomous Interceptors, Anti-Missile Defense |
| Planetary Protection | Orbital Shield, Electronic Jamming, Infrastructure Reinforcement |

Cette liste suggère des rôles, pas un catalogue jouable ni une classification définitive.

## Investissement et coût d’opportunité

Surface : un futur Planetary Defense Center pourra occuper un secteur pour la coordination,
la capacité de modules, les réparations et la résilience des infrastructures. Il concurrencera les
investissements économiques. Command Core et orbital ne sont pas assimilés à un secteur de surface.

Orbite : Orbital Bastion, Sensor Array ou Defense Platform pourront prendre un slot orbital.
Ce choix écartera temporairement un chantier naval, du commerce, d’autres capteurs ou une autre
infrastructure orbitale. Ni ces bâtiments ni l’utilisation des deux slots de référence ne sont
implémentés à l’étape 5A.

## Persistance, dommages et énergie

Les modules resteront principalement des infrastructures persistantes endommageables. Un passage
conceptuel d’une intégrité de 100 % à 45 % pourrait imposer des réparations ; ces chiffres illustrent
le principe et ne sont pas des règles. Une campagne pourra progressivement affaiblir les capteurs,
endommager les boucliers et réduire l’interception avant une attaque plus efficace.

Les systèmes avancés pourront consommer du Flux : faible consommation normale, plus forte en
alerte/combat. Cela rendrait la défense coûteuse et ouvrirait des stratégies d’épuisement. Aucun
drain de Flux, mode d’alerte, calcul d’intégrité, réparation ou effet de combat n’existe dans ce lot.
Destruction permanente/temporaire, ciblage et interaction avec flottes sont à décider.

## Renseignement et interface

Le fog of war devra doser l’information : estimation « défenses fortes » au faible renseignement,
bastion détecté/bouclier probable au niveau intermédiaire, puis niveaux de modules, intégrité et
réserve d’énergie estimée au renseignement avancé. Pas d’information omnisciente exposée par défaut.
Espionnage, capteurs et transitions de connaissance ne sont pas développés maintenant.

La défense appartient à Colony, avec Vue d’ensemble / Infrastructures / Orbite / Défense. Pas de
huitième destination principale. Desktop : sous-sections internes ; mobile : accès compact au sein
de la colonie. L’Empire pourra afficher plus tard une synthèse ou des alertes, pas une seconde
interface défensive. Actuellement la section indique « Défense — système futur », sans valeurs ni
commande de construction. Aucune table DefenseNetwork/DefenseModule anticipée.

- [Questions Q30–Q38](../05-project/open-questions.md) · [Combat](combat.md)
- [Fog](fog-of-war.md) · [Planètes](planets-colonies.md) · [Navigation](../02-ux-ui/information-architecture.md)
