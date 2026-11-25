#!/usr/bin/env python3
"""Génère les planches fixes du profil : héros, GT-R R32, signature, avatar.

Contrairement aux cartes de statistiques (build-stats.py, recalculées toutes
les deux minutes par la CI), ces planches ne dépendent d'aucune donnée : on
les régénère à la main quand le dessin change, puis on les commite.

    build-assets.py DOSSIER [nom ...]      ex. build-assets.py assets r32

Chaque planche sort en quatre fichiers : bureau et mobile (suffixe -m), thème
sombre et thème clair. Python pur ; le texte passe par typo.py.

Règle d'animation, comme partout : chaque élément porte son état final en
attribut, l'animation part d'ailleurs et y revient. Zéro JavaScript.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dessin import (PALETTES, PIQUE, Feuille, arc, cadre, embleme, lisse, melange, pique, polaire)  # noqa: E402
from typo import _n  # noqa: E402

SANS_ANIM = "@media (prefers-reduced-motion:reduce){%s{animation:none}}"


# ------------------------------------------------------------------ GT-R R32
#
# Planche technique de la Nissan Skyline GT-R (BNR32, 1989-1994) : élévation
# latérale et élévation arrière, cotées. Le dessin est construit à partir des
# dimensions réelles, en millimètres, puis mis à l'échelle — longueur 4 545,
# largeur 1 755, hauteur 1 340, empattement 2 615, pneus de 225/50 R16.
# Aucun logo de marque : la voiture se reconnaît à sa ligne, à son aileron et
# à ses quatre feux ronds.

R32 = dict(L=4545, l=1755, H=1340, E=2615, av=890, roue=316, arche=366)


def _arche(cx, depuis, vers, n=22):
    """Points du passage de roue, d'un coin bas à l'autre en passant par le haut."""
    r, bas = R32["arche"], 240
    a = math.acos((bas - R32["roue"]) / float(r))        # angle depuis la verticale
    a0, a1 = (-a, a) if depuis < vers else (a, -a)
    pts = []
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        pts.append((cx + r * math.sin(t), R32["roue"] + r * math.cos(t)))
    return pts


def _profil():
    """Contour de la caisse vue du côté gauche, l'avant à gauche. Millimètres,
    y vers le haut, x = 0 au point le plus avancé du bouclier."""
    av, ar = R32["av"], R32["av"] + R32["E"]
    demi = math.sqrt(R32["arche"] ** 2 - (R32["roue"] - 240) ** 2)    # demi-ouverture du passage de roue
    haut = [
        (84, 184, "c"),
        (50, 202), (30, 252), (12, 330), (2, 420), (0, 500), (8, 560), (30, 592, "c"),   # bouclier avant
        (98, 600, "c"),                                                            # dessus du bouclier
        (114, 660), (136, 716), (166, 738, "c"),                                   # phare, arête du capot
        (400, 765), (700, 796), (1000, 829), (1300, 868), (1500, 900), (1640, 924, "c"),   # aile et capot
        (1790, 1014), (2000, 1140), (2180, 1246), (2262, 1290),                    # pare-brise
        (2340, 1322), (2480, 1338), (2650, 1340), (2850, 1337), (3000, 1326), (3095, 1308),   # pavillon
        (3300, 1228), (3520, 1139), (3700, 1067), (3765, 1042, "c"),              # lunette arrière
        (3830, 1027), (3900, 1021), (4200, 1010), (4462, 1000, "c"),              # malle
        (4500, 990), (4522, 965), (4530, 900), (4538, 760), (4545, 640),           # poupe
        (4545, 520), (4536, 400), (4515, 322), (4480, 277), (4435, 255, "c"),      # bouclier arrière
        (ar + demi, 240, "c"),
    ]
    arriere = [(x, y) for x, y in _arche(ar, 1, 0)]
    arriere[0] += ("c",)
    arriere[-1] += ("c",)
    bas = [(ar - demi - 14, 192, "c"), (av + demi + 14, 192, "c")]
    avant = [(x, y) for x, y in _arche(av, 1, 0)]
    avant[0] += ("c",)
    avant[-1] += ("c",)
    nez = [(430, 204), (250, 188)]
    return haut + arriere[1:] + bas + avant + nez


R32_VITRE_PORTE = [(1752, 950, "c"), (1900, 1040), (2100, 1160), (2300, 1263), (2350, 1281, "c"),
                   (2500, 1296), (2700, 1300), (2872, 1296, "c"), (2880, 978, "c"), (2300, 964)]
R32_VITRE_CUSTODE = [(2944, 979, "c"), (2940, 1294, "c"), (3040, 1286), (3120, 1262), (3230, 1196),
                     (3340, 1112), (3405, 1040), (3425, 996, "c"), (3200, 988)]
R32_AILERON = [(4168, 1011, "c"), (4205, 1062), (4238, 1118, "c"), (4262, 1134), (4505, 1146, "c"),
               (4516, 1132, "c"), (4496, 1070), (4474, 1001, "c")]
R32_RETRO = [(1776, 960, "c"), (1792, 1030), (1826, 1046), (1900, 1042), (1920, 1006), (1890, 966, "c")]
R32_PHARE = [(106, 624, "c"), (140, 715, "c"), (372, 744, "c"), (352, 664, "c")]
R32_CLIGNO = [(40, 470, "c"), (36, 530, "c"), (190, 532, "c"), (200, 474, "c")]
R32_FEU = [(4486, 812, "c"), (4482, 900, "c"), (4527, 896, "c"), (4533, 812, "c")]
R32_REPETITEUR = [(1385, 556, "c"), (1385, 584, "c"), (1455, 584, "c"), (1455, 556, "c")]
# lignes de caisse : (points, classe de trait)
R32_LIGNES = [
    ([(1640, 908), (1622, 760), (1600, 560), (1590, 300), (1590, 196)], "t2"),      # porte, avant
    ([(2912, 978), (2916, 700), (2925, 420), (2960, 300), (3020, 240)], "t2"),      # porte, arrière
    ([(1290, 262), (3100, 262)], "t3"),                                              # haut du bas de caisse
    ([(560, 800), (1200, 846), (2000, 876), (3000, 902), (3900, 914), (4500, 908)], "t3"),   # ligne de caisse
    ([(30, 592), (300, 596), (505, 566)], "t3"),                                    # joint du bouclier avant
    ([(3890, 588), (4200, 602), (4540, 612)], "t3"),                                # joint du bouclier arrière
    ([(1692, 934), (2285, 1284)], "t3"),                                            # pare-brise, chant du vitrage
    ([(3125, 1294), (3742, 1050)], "t3"),                                           # lunette, chant du vitrage
    ([(4250, 1120), (4500, 1132)], "t3"),                                           # dessous de la lame d'aileron
    ([(30, 420), (250, 428), (500, 410)], "t4"),                                    # nervure du bouclier avant
    ([(380, 736), (700, 768), (1000, 801), (1300, 840), (1500, 872), (1628, 896)], "t4"),   # joint aile-capot
]


def _roue(cx, cy, k, p, T):
    """Une roue de 16 pouces à cinq branches, centrée en (cx, cy) mm."""
    x, y = T(cx, cy)
    r = R32["roue"] * k
    o = ['<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" class="t1"/>' % (x, y, r, p["creux"]),
         '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" class="t3"/>' % (x, y, r * 0.93),
         '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" class="t2"/>' % (x, y, r * 0.69, p["fond"]),
         '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" class="t3"/>' % (x, y, r * 0.64),
         # disque de frein et étrier, derrière les branches
         '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" class="t3"/>' % (x, y, r * 0.47),
         '<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>'
         % (arc(x, y, r * 0.5, 200, 255), p["rouge"], max(1.2, r * 0.07))]
    branches = []
    for i in range(5):
        a = -90 + i * 72
        pts = []
        for da, rr in ((-9, 0.14), (-7.5, 0.60), (-11, 0.635), (11, 0.635), (7.5, 0.60), (9, 0.14)):
            pts.append("%.1f,%.1f" % polaire(x, y, r * rr, a + da))
        branches.append("M" + " L".join(pts) + "Z")
    o.append('<path d="%s" fill="%s" class="or1"/>' % (" ".join(branches), p["surface"]))
    o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" class="or1"/>' % (x, y, r * 0.15, p["surface"]))
    o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y, r * 0.05, p["o"]))
    for i in range(5):                                  # écrous
        ex, ey = polaire(x, y, r * 0.105, -54 + i * 72)
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (ex, ey, max(0.5, r * 0.016), p["o"]))
    return o


def _r32_profil(f, x0, sol, k):
    """Élévation latérale. x0 : abscisse du nez ; sol : ordonnée du sol ; k : px par mm."""
    p = f.p

    def T(x, y):
        return (x0 + x * k, sol - y * k)

    def chemin(points, ferme=False):
        return lisse([T(q[0], q[1]) + tuple(q[2:]) for q in points], ferme)

    av, ar = R32["av"], R32["av"] + R32["E"]
    o = []
    # ombre portée
    ex, ey = T(R32["L"] / 2.0, 0)
    o.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="url(#so)" class="fo"/>'
             % (ex, ey + 2, R32["L"] * k * 0.53, 9))
    # caisse
    o.append('<path d="%s" fill="url(#ca)" class="fo"/>' % chemin(_profil(), True))
    # vitrages
    for forme in (R32_VITRE_PORTE, R32_VITRE_CUSTODE):
        o.append('<path d="%s" fill="url(#vi)" class="fo"/>' % chemin(forme, True))
    # feux
    o.append('<path d="%s" fill="%s" class="fo ph"/>' % (chemin(R32_PHARE, True), p["o_haut"]))
    o.append('<path d="%s" fill="%s" class="fo"/>' % (chemin(R32_CLIGNO, True), p["o"]))
    o.append('<path d="%s" fill="%s" class="fo fe"/>' % (chemin(R32_FEU, True), p["rouge"]))
    # aileron
    o.append('<path d="%s" fill="url(#ca)" class="fo"/>' % chemin(R32_AILERON, True))
    # traits : le contour d'abord, puis le détail
    o.append('<path d="%s" fill="none" class="t1 tr" pathLength="1"/>' % chemin(_profil(), True))
    o.append('<path d="%s" fill="none" class="t1 tr" pathLength="1"/>' % chemin(R32_AILERON, True))
    for forme in (R32_VITRE_PORTE, R32_VITRE_CUSTODE, R32_RETRO):
        o.append('<path d="%s" fill="%s" class="t2 tr" pathLength="1"/>'
                 % (chemin(forme, True), p["surface"] if forme is R32_RETRO else "none"))
    for points, classe in R32_LIGNES:
        o.append('<path d="%s" fill="none" class="%s tr" pathLength="1"/>' % (chemin(points), classe))
    for forme in (R32_PHARE, R32_CLIGNO, R32_FEU, R32_REPETITEUR):
        o.append('<path d="%s" fill="%s" class="t3"/>'
                 % (chemin(forme, True), p["o"] if forme is R32_REPETITEUR else "none"))
    # lèvres des ailes élargies : un filet parallèle à chaque passage de roue
    for cx in (av, ar):
        x, y = T(cx, R32["roue"])
        o.append('<path d="%s" fill="none" class="t3"/>' % arc(x, y, (R32["arche"] + 30) * k, 196, 344))
    # poignée de porte, sortie d'échappement
    hx, hy = T(2745, 874)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1.2" fill="none" class="t3"/>'
             % (hx, hy, 128 * k, 34 * k))
    qx, qy = T(4405, 290)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" class="t2"/>'
             % (qx, qy, 122 * k, 50 * k, 22 * k, p["creux"]))
    # roues
    o += _roue(av, R32["roue"], k, p, T)
    o += _roue(ar, R32["roue"], k, p, T)
    return o, T


def _r32_arriere(f, cx, sol, k):
    """Élévation arrière, centrée en cx."""
    p = f.p

    def T(x, y):
        return (cx + x * k, sol - y * k)

    def miroir(points):
        """Demi-contour (x ≥ 0, du bas vers le haut) → contour fermé symétrique."""
        gauche = [(-q[0], q[1]) + tuple(q[2:]) for q in reversed(points[1:-1])]
        return points + gauche

    def chemin(points, ferme=False):
        return lisse([T(q[0], q[1]) + tuple(q[2:]) for q in points], ferme)

    demi = [(0, 255, "c"), (700, 255), (800, 272), (850, 332), (868, 450), (877, 560), (872, 700),
            (862, 820), (840, 930), (805, 985), (760, 1006, "c"), (735, 1014), (700, 1100), (650, 1222),
            (600, 1300), (540, 1334), (300, 1340), (0, 1340, "c")]
    lunette = [(0, 1052, "c"), (640, 1052), (668, 1066), (660, 1100), (590, 1262), (560, 1296), (520, 1304),
               (0, 1304, "c")]
    o = []
    # pneus
    for s in (-1, 1):
        x, y = T(s * 740 - 112, 290)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" class="t2"/>'
                 % (x, y, 224 * k, 290 * k, 44 * k, p["creux"]))
        for dx in (-56, 0, 56):                       # sculptures de la bande de roulement
            o.append('<path d="%s" fill="none" class="t4"/>' % chemin([(s * 740 + dx, 30), (s * 740 + dx, 240)]))
    ex, ey = T(0, 0)
    o.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="7" fill="url(#so)" class="fo"/>'
             % (ex, ey + 2, R32["l"] * k * 0.6))
    o.append('<path d="%s" fill="url(#ca)" class="fo"/>' % chemin(miroir(demi), True))
    o.append('<path d="%s" fill="url(#vi)" class="fo"/>' % chemin(miroir(lunette), True))
    # bandeau des feux, plaque
    bx, by = T(-772, 936)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" class="t3"/>'
             % (bx, by, 1544 * k, 166 * k, 30 * k, p["creux"]))
    px, py = T(-165, 930)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1.5" fill="%s" class="t3"/>'
             % (px, py, 330 * k, 154 * k, p["surface"]))
    o.append(pique(cx, sol - 853 * k, 86 * k, p["o"], 'class="fo"'))
    # les quatre feux ronds
    for x in (-650, -455, 455, 650):
        fx, fy = T(x, 853)
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="url(#ha)" class="fe"/>' % (fx, fy, 128 * k))
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" class="fo"/>' % (fx, fy, 70 * k, p["rouge_bas"]))
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.2f" class="fo fe"/>'
                 % (fx, fy, 56 * k, p["rouge"], max(1.6, 24 * k)))
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" class="fo fe"/>' % (fx, fy, 20 * k, p["rouge"]))
    # aileron : lame et montants d'extrémité
    lx, ly = T(-800, 1162)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="url(#ca)" class="t1"/>'
             % (lx, ly, 1600 * k, 36 * k, 14 * k))
    for s in (-1, 1):
        o.append('<path d="%s" fill="url(#ca)" class="t2"/>' % chemin(
            [(s * 700, 1004, "c"), (s * 722, 1128, "c"), (s * 792, 1128, "c"), (s * 772, 1004, "c")], True))
    # traits
    o.append('<path d="%s" fill="none" class="t1 tr" pathLength="1"/>' % chemin(miroir(demi), True))
    o.append('<path d="%s" fill="none" class="t2 tr" pathLength="1"/>' % chemin(miroir(lunette), True))
    for pts in ([(-760, 1004), (760, 1004)], [(-866, 742), (866, 742)], [(-862, 420), (862, 420)],
                [(-600, 936), (-610, 1002)], [(600, 936), (610, 1002)]):
        o.append('<path d="%s" fill="none" class="t3"/>' % chemin(pts))
    for y in (1100, 1150, 1200, 1250):          # dégivrage
        d = 640 - (y - 1052) * 0.47
        o.append('<path d="%s" fill="none" class="t4"/>' % chemin([(-d, y), (d, y)]))
    qx, qy = T(-520, 290)
    o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" class="t2"/>' % (qx, qy, 52 * k, p["creux"]))
    # rétroviseurs
    for s in (-1, 1):
        o.append('<path d="%s" fill="%s" class="t3"/>' % (chemin(
            [(s * 838, 968, "c"), (s * 850, 1034), (s * 940, 1040), (s * 958, 990), (s * 925, 964, "c")], True),
            p["surface"]))
        rx, ry = T(s * 700 - 60, 540)                 # catadioptres du bouclier
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1" fill="%s" class="fo"/>'
                 % (rx, ry, 120 * k, 34 * k, p["rouge_bas"]))
    return o, T


def _cote(f, x0, x1, y, texte, corps=8.6):
    """Une cote horizontale : trait, flèches en butée, valeur au milieu."""
    p = f.p
    w = f.largeur("mono", texte, corps) + 12
    m = (x0 + x1) / 2.0
    return [
        '<path d="M%.1f,%.1f V%.1f M%.1f,%.1f V%.1f M%.1f,%.1f H%.1f M%.1f,%.1f H%.1f" class="ct"/>'
        % (x0, y - 5, y + 5, x1, y - 5, y + 5, x0, y, m - w / 2, m + w / 2, y, x1),
        f.texte("mono", texte, corps, m, y + corps * 0.36, ancre="middle", fill=p["doux"]),
    ]


def planche_r32(p, mobile=False):
    W, H = (450, 560) if mobile else (900, 544)
    f = Feuille(W, H, p, "Nissan Skyline GT-R (BNR32)",
                "Planche technique de la Skyline GT-R R32 : élévation latérale et élévation arrière, cotées. "
                "Longueur 4 545 mm, largeur 1 755 mm, hauteur 1 340 mm, empattement 2 615 mm. "
                "Moteur RB26DETT, six cylindres en ligne, 2 568 cm³, biturbo, 280 ch. Surnommée Godzilla : "
                "29 victoires en 29 courses en Groupe A au Japon, de 1990 à 1993. La voiture de mes rêves.")
    cadre(f, "Garage")
    sombre = p["nom"] == "dark"
    f.definis('<linearGradient id="ca" x1="0" y1="0" x2="0" y2="1">'
              '<stop offset="0" stop-color="%s"/><stop offset="0.55" stop-color="%s"/>'
              '<stop offset="1" stop-color="%s"/></linearGradient>'
              % ((melange(p["surface"], p["encre"], 0.10), p["surface"], p["creux"]) if sombre else
                 (p["surface"], melange(p["surface"], p["trait"], 0.5), p["trait"])))
    f.definis('<linearGradient id="vi" x1="0" y1="0" x2="1" y2="1">'
              '<stop offset="0" stop-color="%s"/><stop offset="0.5" stop-color="%s"/>'
              '<stop offset="1" stop-color="%s"/></linearGradient>'
              % ((p["creux"], melange(p["creux"], p["encre"], 0.16), p["creux"]) if sombre else
                 (p["trait"], p["surface"], p["trait"])))
    f.definis('<radialGradient id="so"><stop offset="0" stop-color="#000" stop-opacity="%s"/>'
              '<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>' % ("0.6" if sombre else "0.2"))
    f.definis('<radialGradient id="ha"><stop offset="0.3" stop-color="%s" stop-opacity="0.55"/>'
              '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>' % (p["rouge"], p["rouge"]))
    f.style(".t1,.t2,.t3,.t4,.ct,.or1{stroke-linecap:round;stroke-linejoin:round}"
            ".t1{stroke:%s;stroke-width:1.5}.t2{stroke:%s;stroke-width:1}"
            ".t3{stroke:%s;stroke-width:.8}.t4{stroke:%s;stroke-width:.6;opacity:.6}"
            ".or1{stroke:%s;stroke-width:.9}.ct{stroke:%s;stroke-width:.7;fill:none}"
            % (p["encre"], p["doux"], p["discret"], p["discret"], p["o"], p["discret"]))
    # la gravure se trace, puis les aplats montent, puis les feux s'allument
    f.style(".tr{stroke-dasharray:1;animation:tr 2.6s cubic-bezier(.4,0,.2,1) both}"
            "@keyframes tr{from{stroke-dashoffset:1}}"
            ".fo{animation:fo 1.2s ease-out 1.5s both}@keyframes fo{from{opacity:0}}"
            ".fe{animation:fo 1.2s ease-out 1.5s both,fe 3.2s ease-in-out 3s infinite}"
            "@keyframes fe{50%{opacity:.55}}")
    f.style(SANS_ANIM % ".tr,.fo,.fe")

    if mobile:
        k = 0.0895
        o, _ = _r32_profil(f, 22, 196, k)
        f += o
        f += _cote(f, 22, 22 + R32["L"] * k, 218, "4 545 mm")
        f += _cote(f, 22 + R32["av"] * k, 22 + (R32["av"] + R32["E"]) * k, 240, "empattement 2 615")
        ka = 0.098
        o, _ = _r32_arriere(f, 112, 420, ka)
        f += o
        f += _cote(f, 112 - R32["l"] / 2 * ka, 112 + R32["l"] / 2 * ka, 442, "1 755 mm")
        tx, ty = 232, 304
        f += f.texte("ital", "Skyline GT-R", 27, tx, ty, fill=p["encre"])
        f += f.texte("mono-gras", "BNR32 · 1989 – 1994", 9.6, tx, ty + 22, approche=1.6, fill=p["o"])
        for i, ligne in enumerate(("RB26DETT · 280 ch", "6 cylindres en ligne", "2 568 cm³ · biturbo",
                                   "4 roues motrices", "4 roues directrices")):
            f += f.texte("mono", ligne, 9.6, tx, ty + 48 + i * 17, fill=p["doux"])
        f += f.texte("mono-gras", "« GODZILLA »", 9.2, W / 2.0, H - 92, ancre="middle", approche=2.2, fill=p["o"])
        f += f.texte("mono", "29 victoires en 29 courses · Groupe A, 1990 – 1993", 8.6, W / 2.0, H - 75,
                     ancre="middle", fill=p["doux"])
        f += f.texte("ital", "La voiture de mes rêves.", 17, W / 2.0, H - 40, ancre="middle", fill=p["o"])
    else:
        k = 0.1785
        x0, sol = 44, 318
        o, _ = _r32_profil(f, x0, sol, k)
        f += o
        f += _cote(f, x0, x0 + R32["L"] * k, sol + 24, "4 545 mm")
        f += _cote(f, x0 + R32["av"] * k, x0 + (R32["av"] + R32["E"]) * k, sol + 46, "empattement 2 615 mm")
        ka = 0.0905
        ax, asol = 772, 500
        o, _ = _r32_arriere(f, ax, asol, ka)
        f += o
        f += _cote(f, ax - R32["l"] / 2 * ka, ax + R32["l"] / 2 * ka, asol + 18, "1 755 mm", corps=8)
        tx, ty = 44, 428
        f += f.texte("ital", "Skyline GT-R", 34, tx, ty, fill=p["encre"])
        wt = f.largeur("ital", "Skyline GT-R", 34)
        f += f.texte("mono-gras", "BNR32 · 1989 – 1994", 9.6, tx + wt + 18, ty - 2, approche=1.8, fill=p["o"])
        f += f.texte("mono", "RB26DETT · 6 cylindres en ligne · 2 568 cm³ · biturbo · 280 ch", 9.2, tx, ty + 26,
                     fill=p["doux"])
        f += f.texte("mono", "4 roues motrices · 4 roues directrices · hauteur 1 340 mm", 9.2, tx, ty + 43,
                     fill=p["doux"])
        f += f.texte("mono-gras", "« GODZILLA »", 9.2, tx, ty + 64, approche=2.2, fill=p["o"])
        wg = f.largeur("mono-gras", "« GODZILLA »", 9.2, approche=2.2)
        f += f.texte("mono", "29 victoires en 29 courses · Groupe A, Japon, 1990 – 1993", 9.2, tx + wg + 12, ty + 64,
                     fill=p["doux"])
        f += f.texte("ital", "La voiture de mes rêves.", 17, tx, ty + 96, fill=p["o"])
    return f.rendu()


# ------------------------------------------------------------------- héros

CREDO = "« Celui qui tire doit être prêt à recevoir la balle. »"


def _index(f, x, y):
    """L'indice de coin d'une carte à jouer : un A, un pique dessous."""
    p = f.p
    return [f.texte("titre", "A", 29, x, y, ancre="middle", fill=p["encre"]), pique(x, y + 19, 18, p["o"])]


def _entree_embleme(c):
    """Le filigrane se monte comme chez l'orfèvre : pourtour, ossature, puis la
    dentelle du cœur vers les bords. Les grains d'or scintillent ensuite."""
    nom = c["nom"]
    if nom in ("cordon", "perles", "perle-axe", "lisere"):
        t, scintille = 0.1, False
    elif nom in ("axe", "grains-medaillon", "pique"):
        t, scintille = 0.35, False
    elif nom == "volutes":
        t, scintille = 0.6, False
    else:
        rang = int(nom.rsplit("-", 1)[1])
        t, scintille = 0.85 + rang * 0.13, nom.startswith("grains-")
    if scintille:
        return ' class="em sc" style="animation-delay:%ss,%ss"' % (_n(t), _n(3 + (rang * 5 % 8) * 0.7))
    return ' class="em" style="animation-delay:%ss"' % _n(t)


def planche_heros(p, mobile=False):
    W, H = (450, 692) if mobile else (900, 470)
    f = Feuille(W, H, p, "Yanis — l’as de pique",
                "Un as de pique en filigrane, crème et or sur noir. Yanis : ingénieur cybersécurité, fondateur de "
                "Classor, développeur de jeux vidéo, de logiciels et d'outils. Depuis toujours : coder des outils, "
                "en vivre. " + CREDO + " — Lelouch, Code Geass.")
    cadre(f, None)
    sombre = p["nom"] == "dark"
    f.definis('<radialGradient id="lu"><stop offset="0" stop-color="%s" stop-opacity="%s"/>'
              '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
              % (p["o"], "0.16" if sombre else "0.13", p["o"]))
    f.style(".em{animation:em 1.1s ease-out both}@keyframes em{from{opacity:0}}"
            ".sc{animation:em 1.1s ease-out both,sc 5.6s ease-in-out infinite}@keyframes sc{50%{opacity:.35}}"
            ".n{animation:n .8s cubic-bezier(.2,.8,.2,1) both}"
            "@keyframes n{from{opacity:0;transform:translateY(260px)}}"
            ".ec{stroke-dasharray:.05 .95;animation:ec 9s linear 2.4s infinite both}"
            "@keyframes ec{from{stroke-dashoffset:1;opacity:0}6%{opacity:1}94%{opacity:1}"
            "to{stroke-dashoffset:0;opacity:0}}")
    f.style(SANS_ANIM % ".em,.sc,.n,.ec")

    def apparait(t):
        return 'class="em" style="animation-delay:%ss"' % _n(t)

    # la carte : indices aux deux coins opposés, l'un tête en bas
    coin = _index(f, 43, 61) if not mobile else _index(f, 39, 57)
    f += '<g %s>%s<g transform="rotate(180 %s %s)">%s</g></g>' % (
        apparait(0.2), "".join(coin), _n(W / 2.0), _n(H / 2.0), "".join(coin))

    if mobile:
        eh, ex, ey = 330.0, (W - 275.0) / 2, 44.0
    else:
        eh, ex, ey = 400.0, 54.0, 35.0
    k = eh / 1200.0
    f += '<circle cx="%s" cy="%s" r="%s" fill="url(#lu)"/>' % (_n(ex + 500 * k), _n(ey + 610 * k), _n(eh * 0.52))
    f += embleme(f, ex, ey, eh, _entree_embleme)
    # Une étincelle fait le tour du cordon. Au repos elle est éteinte (opacity
    # en attribut) : sans animation, on ne voit que le filigrane.
    f += ('<path d="%s" transform="translate(%s %s) scale(%s)" fill="none" stroke="%s" stroke-width="7" '
          'stroke-linecap="round" pathLength="1" opacity="0" class="ec"/>'
          % (PIQUE, _n(ex), _n(ey), ("%.5f" % k).rstrip("0"), p["o_haut"]))

    if mobile:
        cx = W / 2.0
        f += f.texte("titre", "YANIS", 74, cx, 452, ancre="middle", approche=3, fill=p["encre"], cascade=(0.7, 0.09))
        f += '<rect x="%s" y="470" width="44" height="2" rx="1" fill="%s" %s/>' % (_n(cx - 22), p["o"], apparait(1.3))
        f += f.texte("texte", "Ingénieur cybersécurité", 18.5, cx, 506, ancre="middle", fill=p["encre"],
                     attrs=apparait(1.4))
        wa = f.largeur("texte", "Fondateur de ", 18.5)
        wb = f.largeur("texte", "Classor", 18.5)
        f += f.texte("texte", "Fondateur de ", 18.5, cx - (wa + wb) / 2, 531, fill=p["encre"], attrs=apparait(1.5))
        f += f.texte("texte", "Classor", 18.5, cx - (wa + wb) / 2 + wa, 531, fill=p["o"], attrs=apparait(1.5))
        f += f.texte("mono", "JEUX VIDÉO · LOGICIELS · OUTILS", 9.4, cx, 561, ancre="middle", approche=2,
                     fill=p["doux"], attrs=apparait(1.6))
        f += f.texte("ital", "Depuis toujours : coder des outils, en vivre.", 14.6, cx, 584, ancre="middle",
                     fill=p["doux"], attrs=apparait(1.7))
        f += '<path d="M60,606H%s" stroke="%s" stroke-width="1" %s/>' % (_n(W - 60), p["trait"], apparait(1.8))
        f += f.texte("ital", CREDO, 13.6, cx, 632, ancre="middle", fill=p["encre"], attrs=apparait(1.9))
        f += f.texte("mono", "— LELOUCH, CODE GEASS", 8.2, cx, 652, ancre="middle", approche=1.8,
                     fill=p["discret"], attrs=apparait(2.0))
    else:
        x0, x1 = 430.0, 792.0
        f += '<g %s>%s%s</g>' % (
            apparait(0.5), pique(x0 + 6, 96.5, 13, p["o"]),
            f.texte("mono-gras", "FARDDOWNYG  ·  AS DE PIQUE", 10.4, x0 + 20, 100, approche=3.2, fill=p["o"]))
        f += f.texte("titre", "YANIS", 106, x0 - 5, 200, approche=4, fill=p["encre"], cascade=(0.7, 0.09))
        f += '<rect x="%s" y="224" width="52" height="2.4" rx="1.2" fill="%s" %s/>' % (_n(x0), p["o"], apparait(1.3))
        f += f.texte("texte", "Ingénieur cybersécurité", 22, x0, 268, fill=p["encre"], attrs=apparait(1.4))
        wa = f.largeur("texte", "Fondateur de ", 22)
        f += f.texte("texte", "Fondateur de ", 22, x0, 298, fill=p["encre"], attrs=apparait(1.5))
        f += f.texte("texte", "Classor", 22, x0 + wa, 298, fill=p["o"], attrs=apparait(1.5))
        f += f.texte("mono", "JEUX VIDÉO · LOGICIELS · OUTILS", 9.8, x0, 332, approche=2.4, fill=p["doux"],
                     attrs=apparait(1.6))
        f += f.texte("ital", "Depuis toujours : coder des outils, en vivre.", 16, x0, 357, fill=p["doux"],
                     attrs=apparait(1.7))
        f += '<path d="M%s,381H%s" stroke="%s" stroke-width="1" %s/>' % (_n(x0), _n(x1), p["trait"], apparait(1.8))
        f += f.texte("ital", CREDO, 15, x0, 408, fill=p["encre"], attrs=apparait(1.9))
        f += f.texte("mono", "— LELOUCH, CODE GEASS", 8.6, x0, 428, approche=1.8, fill=p["discret"],
                     attrs=apparait(2.0))
    return f.rendu()


def planche_signature(p, mobile=False):
    """Le mot de la fin, sans cadre : il se pose sur le fond de la page."""
    W, H = (450, 92) if mobile else (900, 92)
    f = Feuille(W, H, p, "Une lame s’affûte tous les jours", "Signature du profil : un petit pique entre deux filets.")
    cx = W / 2.0
    demi = 150 if mobile else 300
    f.definis('<linearGradient id="fg" x1="0" x2="1"><stop offset="0" stop-color="%s" stop-opacity="0"/>'
              '<stop offset="1" stop-color="%s"/></linearGradient>' % (p["o"], p["o"]))
    f += '<rect x="%s" y="29.5" width="%s" height="1" fill="url(#fg)"/>' % (_n(cx - demi), _n(demi - 22))
    f += '<rect x="%s" y="29.5" width="%s" height="1" fill="url(#fg)" transform="rotate(180 %s 30)"/>' % (
        _n(cx - demi), _n(demi - 22), _n(cx))
    f += pique(cx, 30, 20, p["o"])
    f += '<circle cx="%s" cy="30" r="1.6" fill="%s"/><circle cx="%s" cy="30" r="1.6" fill="%s"/>' % (
        _n(cx - 17), p["o"], _n(cx + 17), p["o"])
    f += f.texte("ital", "une lame s’affûte tous les jours", 16, cx, 66, ancre="middle", fill=p["o"])
    return f.rendu()


def avatar(p):
    """La photo de profil : le filigrane seul, cadré pour un recadrage en disque."""
    f = Feuille(1024, 1024, p, "As de pique", "L'as de pique en filigrane, crème et or sur noir.")
    f.definis('<radialGradient id="av" cx="0.5" cy="0.46" r="0.62"><stop offset="0" stop-color="%s"/>'
              '<stop offset="1" stop-color="%s"/></radialGradient>' % (melange(p["fond"], p["o"], 0.10), p["creux"]))
    f += '<rect width="1024" height="1024" fill="url(#av)"/>'
    f += embleme(f, 512 - 880 / 2.4, 66, 880)
    return f.rendu()


PLANCHES = (("heros", planche_heros), ("r32", planche_r32), ("signature", planche_signature))


def rendus(seulement=()):
    for nom, planche in PLANCHES:
        if seulement and nom not in seulement:
            continue
        for mobile in (False, True):
            for p in PALETTES:
                yield "%s%s-%s.svg" % (nom, "-m" if mobile else "", p["nom"]), planche(p, mobile)
    if not seulement or "avatar" in seulement:
        yield "avatar.svg", avatar(PALETTES[0])


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    os.makedirs(sys.argv[1], exist_ok=True)
    for nom, svg in rendus(sys.argv[2:]):
        with open(os.path.join(sys.argv[1], nom), "w", encoding="utf-8") as fichier:
            fichier.write(svg)
        print("écrit : %s (%d Ko)" % (nom, len(svg.encode("utf-8")) // 1024))


if __name__ == "__main__":
    main()
