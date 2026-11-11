"""Low-fidelity wireframes for UX01 (structure only, no visual direction)."""
import sys, html
OUT = sys.argv[1]
def esc(t): return html.escape(t)
class W:
    def __init__(s, name, w=1280, h=800, title=""):
        s.name, s.w, s.h, s.parts = name, w, h, []
        s.title = title
    def box(s, x, y, w, h, label="", kind="panel", lines=()):
        fill = {"panel": "#f4f6f8", "map": "#e3ebf3", "accent": "#d7f3f6", "warn": "#fff1d6", "primary": "#1f8fb8", "nav": "#e9edf1"}[kind]
        stroke = "#1f8fb8" if kind in ("accent", "primary") else "#8a97a6"
        s.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        color = "#ffffff" if kind == "primary" else "#1d2b3a"
        if label:
            s.parts.append(f'<text x="{x+10}" y="{y+20}" font-size="13" font-weight="700" fill="{color}">{esc(label)}</text>')
        for i, l in enumerate(lines):
            s.parts.append(f'<text x="{x+10}" y="{y+40+i*17}" font-size="11.5" fill="#46566a">{esc(l)}</text>')
    def text(s, x, y, t, size=11.5, color="#46566a", weight=400):
        s.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{esc(t)}</text>')
    def star(s, x, y, r=6, dashed=False, own=False):
        d = ' stroke-dasharray="3 2" fill="none"' if dashed else ' fill="#1d2b3a"'
        s.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" stroke="#1d2b3a"{d}/>')
        if own: s.parts.append(f'<circle cx="{x}" cy="{y}" r="{r+5}" fill="none" stroke="#d48a00" stroke-width="1.6"/>')
    def line(s, a, b, dash=False, color="#8a97a6", width=1.4):
        da = ' stroke-dasharray="6 5"' if dash else ""
        s.parts.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" stroke-width="{width}"{da}/>')
    def save(s):
        body = "\n".join(s.parts)
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s.w} {s.h}" width="{s.w}" height="{s.h}" font-family="system-ui, sans-serif" role="img" aria-label="{esc(s.title)}">
<title>{esc(s.title)}</title>
<rect width="{s.w}" height="{s.h}" fill="#ffffff"/>
{body}
</svg>
'''
        open(f"{OUT}/{s.name}.svg", "w").write(svg)

def shell(w, active, title):
    w.box(0, 0, w.w, 56, "", "nav")
    w.text(16, 34, "ECHOSPHERE", 15, "#1d2b3a", 800)
    w.text(160, 24, "Univers · Empire ▾", 11, "#46566a")
    w.text(160, 42, "Colonie active ▾ · Alliages · Flux · Données (stock, +/h) — valeurs serveur", 11, "#46566a")
    w.box(w.w-300, 12, 120, 32, "🔔 Alertes 3", "warn")
    w.box(w.w-170, 12, 154, 32, "Commandant ▾", "panel")
    items = ["Empire", "Galaxie", "Colonies", "Recherche", "Flottes", "Rapports", "Diplomatie"]
    w.box(0, 56, 170, w.h-56, "", "nav")
    for i, it in enumerate(items):
        k = "accent" if it == active else "nav"
        w.box(10, 72+i*46, 150, 38, it, k)
    w.text(190, 88, title, 20, "#1d2b3a", 700)

# 1. Galaxy command map — desktop
w = W("01-galaxie-commandement", title="Wireframe — Galaxie, carte de commandement (bureau)")
shell(w, "Galaxie", "Galaxie — carte de commandement")
w.box(190, 104, 230, 34, "🔍 Rechercher un système", "panel")
w.box(430, 104, 420, 34, "Filtres : Tous · Mes colonies · Mes flottes · Signaux · Menaces", "panel")
w.box(190, 148, 720, 520, "", "map")
pts = {"Aube": (330, 330), "Vesta": (470, 250), "Lyra": (650, 290), "Orion": (430, 450), "Cygne": (620, 470), "Draco": (240, 420)}
for a, b in [("Aube","Vesta"),("Aube","Orion"),("Vesta","Lyra"),("Orion","Cygne"),("Aube","Draco"),("Lyra","Cygne")]:
    w.line(pts[a], pts[b])
w.line(pts["Aube"], pts["Vesta"], color="#d48a00", width=3); w.line(pts["Vesta"], pts["Lyra"], color="#d48a00", width=3)
for n, p in pts.items():
    w.star(*p, own=(n=="Aube")); w.text(p[0]+12, p[1]+4, n, 12, "#1d2b3a", 600)
w.star(820, 210, dashed=True); w.text(832, 214, "Signal", 11, "#6b7a8c")
w.box(300, 300, 22, 16, "", "primary"); w.text(306, 312, "3", 10, "#fff", 700)
w.text(560, 270, "▲ mission (position estimée)", 10.5, "#1d7a4e")
w.box(200, 616, 300, 42, "Légende · Zoom + − · Recentrer · Liste", "panel")
w.box(930, 104, 330, 564, "Panneau contextuel", "panel", [
    "1. Système sélectionné : Lyra (cartographié)",
    "   Planètes connues · vos flottes ici",
    "2. Actions possibles (désactivées = raison) :",
    "   [Déplacer une flotte] [Coloniser…] [Attaquer…]",
    "─── après choix d'une action ───",
    "Étapes ● Cible ● Flotte ○ Unités ○ Vérifier",
    "3. Flotte : cartes radio (lieu, unités adaptées)",
    "4. Unités : toutes par défaut, − / + ",
    "5. Résumé serveur : sauts, étapes, durée,",
    "   arrivée, carburant, bataille, « à savoir »",
    "6. [ Confirmer : déplacer une flotte ]",
    "Échap ou [Annuler] revient aux actions",
])
w.box(190, 680, 1070, 100, "Vos flottes (dock) — où, quoi, vers où", "panel", [
    "[Escadre Héliade · En déplacement · Aube → Lyra · 1 h 12] [Garnison · Aube] [Sonde Kepler · Vesta]  [Localiser]",
    "Clic = la carte se centre et le panneau montre la flotte et ses actions (rappel, protocole, détail)",
])
w.save()

# 2. Galaxy mobile
w = W("02-galaxie-mobile", 390, 844, "Wireframe — Galaxie mobile avec feuille d’actions")
w.box(0, 0, 390, 52, "", "nav"); w.text(12, 32, "ECHOSPHERE", 14, "#1d2b3a", 800); w.box(270, 10, 108, 32, "🔔 3", "warn")
w.box(0, 52, 390, 430, "", "map")
mp = {"Aube": (110, 230), "Vesta": (200, 160), "Lyra": (300, 200), "Orion": (160, 330)}
for a, b in [("Aube","Vesta"),("Vesta","Lyra"),("Aube","Orion")]: w.line(mp[a], mp[b])
w.line(mp["Aube"], mp["Vesta"], color="#d48a00", width=3); w.line(mp["Vesta"], mp["Lyra"], color="#d48a00", width=3)
for n, p in mp.items(): w.star(*p, r=8, own=(n=="Aube")); w.text(p[0]+12, p[1]+4, n, 12, "#1d2b3a", 600)
w.text(12, 470, "Pincer pour zoomer · toucher un système", 10.5)
w.box(0, 470, 390, 314, "Feuille d’actions (glisse vers le haut)", "panel", [
    "Lyra · cartographié · 1 planète connue",
    "Étapes ● ● ○ ○",
    "Flotte : (•) Escadre Héliade  ( ) Garnison",
    "Unités : Frégate  [−] 2/2 [+]",
    "Résumé serveur : 2 sauts · 36 min · 12 Flux",
])
w.box(16, 690, 358, 44, "Confirmer : déplacer une flotte", "primary")
w.box(0, 784, 390, 60, "", "nav")
for i, it in enumerate(["Empire", "Galaxie", "Flottes", "Plus"]):
    w.box(8+i*96, 792, 88, 44, it, "accent" if it == "Galaxie" else "nav")
w.save()

# 3. Empire dashboard
w = W("03-empire", title="Wireframe — Tableau de bord Empire")
shell(w, "Empire", "Empire — ce qui demande votre attention")
w.box(190, 110, 1070, 90, "À faire maintenant (3)", "warn", [
    "⚠ Force hostile annoncée sur Aube Prime — bataille dans 18 h  [Voir la défense]",
    "◇ Proposition de pacte de la Ligue Aurorale  [Répondre]     ✓ Recherche terminée : Technologie A  [Choisir la suivante]",
])
w.box(190, 214, 520, 220, "Colonies", "panel", ["Aube Prime · 9/12 secteurs · file 2/3 · fin 14:20", "Vesta II · 3/10 secteurs · file vide  [Construire]", "[Ouvrir la colonie]"])
w.box(730, 214, 530, 220, "Flottes", "panel", ["2 en mission · 3 stationnées", "Escadre Héliade → Lyra · arrivée 13:36", "Éclaireur → Signal · cartographie 12:35", "[Ouvrir la carte de commandement]"])
w.box(190, 448, 520, 200, "Recherche", "panel", ["Active : Technologie B · 2 h 10", "Suivante : Technologie C", "[Voir l’arbre]"])
w.box(730, 448, 530, 200, "Derniers rapports", "panel", ["Cartographie de Draco · 11:05", "Rencontre frontalière à Vesta · 09:40", "[Tous les rapports]"])
w.box(190, 662, 1070, 110, "Prochaines échéances (frise)", "panel", ["12:35 cartographie ── 13:36 arrivée Lyra ── 14:20 construction ── 06:00+1 bataille annoncée"])
w.save()

# 4. Fleets management
w = W("04-flottes-gestion", title="Wireframe — Flottes, écran de gestion")
shell(w, "Flottes", "Flottes — gestion")
w.box(190, 110, 1070, 40, "Onglets : Flottes · Production · Missions · Protocoles frontaliers", "panel")
w.box(190, 164, 380, 600, "Liste des flottes", "panel", ["Filtre : toutes · stationnées · en mission", "▸ Escadre Héliade · en déplacement", "▸ Garnison Aube Prime · Aube", "▸ Sonde Kepler · Vesta", "▸ Pionnier · Aube (cargo 600)"])
w.box(590, 164, 670, 600, "Fiche de la flotte sélectionnée", "panel", [
    "Garnison Aube Prime · Aube · garnison",
    "Composition : 3 Intercepteurs · 1 Sonde",
    "Cargo : vide · capacité 0",
    "Actions principales : [Envoyer depuis la carte] [Rentrer]",
    "Organisation : [Diviser…] [Fusionner…] [Charger…] [Décharger…]",
    "Protocole (flotte opérationnelle) : Surveillance ▾  + explication",
    "Historique : missions et rapports de cette flotte",
])
w.save()

# 5. Colony
w = W("05-colonie", title="Wireframe — Colonie")
shell(w, "Colonies", "Aube Prime")
w.box(190, 110, 1070, 40, "Sous-navigation canonique : Vue d’ensemble · Infrastructures · Orbite · Défense   | Colonie ▾", "panel")
w.box(190, 164, 1070, 80, "Ressources de la colonie (stock, production, capacité)", "panel", ["Alliages ███████░░ 77 % · Flux ████░░░░ 40 % · Données ██░░░░░ 20 %"])
w.box(190, 258, 640, 500, "Secteurs (grille 12) — cliquer un secteur = ses actions", "map", ["[Extraction 3] [Réacteur 2] [Nœud 1] [libre +] [libre +] …", "Secteur choisi → panneau : améliorer / construire / coût / durée serveur"])
w.box(850, 258, 410, 240, "File de construction (3)", "panel", ["1. Réacteur de Flux 3 · fin 14:20 ▓▓▓░", "2. Nœud de données 2 · en attente", "[Annuler…] (aperçu remboursement serveur)"])
w.box(850, 512, 410, 246, "Menaces et défense", "warn", ["Force hostile annoncée · bataille 06:00", "Défense : système futur (Q30–Q38)"])
w.save()

# 6. Research
w = W("06-recherche", title="Wireframe — Arbre de recherche")
shell(w, "Recherche", "Recherche")
w.box(190, 110, 1070, 60, "Active : Technologie B · 2 h 10 restantes ▓▓▓▓░   Suivante : Technologie C  [Changer]", "accent")
for i, d in enumerate(["Ingénierie", "Énergétique", "Calcul", "Xénoscience"]):
    x = 190 + i*270
    w.box(x, 184, 250, 36, d, "panel")
    for j in range(2):
        w.box(x+20, 240+j*130, 210, 90, f"Technologie {j+1}", "accent" if j == 0 else "panel", ["acquise / disponible / verrouillée", "[Rechercher…]"])
    w.line((x+125, 330), (x+125, 370))
w.box(190, 640, 1070, 120, "Détail de la technologie choisie", "panel", ["Effet · prérequis · coût et durée calculés par le serveur · colonie source ▾", "[Lancer] ou [Programmer ensuite]"])
w.save()

# 7. Reports & alerts
w = W("07-rapports-alertes", title="Wireframe — Rapports et alertes")
shell(w, "Rapports", "Rapports et événements")
w.box(190, 110, 1070, 40, "Filtres : Tout · Missions · Combats · Frontière · Diplomatie · Colonies   | Non lus seulement", "panel")
w.box(190, 164, 520, 600, "Fil chronologique", "panel", ["● 12:35 Cartographie terminée — Signal → Draco Nord", "● 11:05 Rencontre frontalière à Vesta (embuscade, victoire)", "● 09:40 Pacte accepté — Ligue Aurorale", "● 08:00 Bataille d’Aube Prime — défense tenue", "…"])
w.box(730, 164, 530, 600, "Rapport sélectionné", "panel", ["Titre, lieu (lien carte), instant", "Ce que vous savez (selon le serveur)", "Forces engagées / pertes / survivants", "Liens : [Voir sur la carte] [Voir la flotte]"])
w.save()

# 8. Diplomacy
w = W("08-diplomatie", title="Wireframe — Diplomatie")
shell(w, "Diplomatie", "Diplomatie")
w.box(190, 110, 1070, 70, "Propositions en attente (1)", "warn", ["Ligue Aurorale propose un pacte · expire dans 20 h  [Accepter] [Refuser]"])
w.box(190, 194, 520, 570, "Civilisations connues", "panel", ["Concorde · Pacte actif depuis 2 j", "Ligue Aurorale · Aucun accord · proposition reçue", "Empire inconnu (signature) · détecté à Vesta"])
w.box(730, 194, 530, 570, "Fiche de la civilisation", "panel", ["Emblème · portrait (cosmétique, selon droits)", "État : aucun accord / pacte", "Faits datés : dernier acte hostile, contact depuis", "Actions : [Proposer un pacte] [Rompre…] (confirmation)", "Historique"])
w.save()
print("ok")
