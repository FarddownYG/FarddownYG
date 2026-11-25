"""Le système de design du profil : « carte noire ».

Noir chaud, crème, or — et un rouge vermillon, celui des cœurs et des carreaux,
réservé aux aiguilles, aux feux et à la flamme. Tout ce qui est commun aux
cartes de statistiques (build-stats.py) et aux planches fixes
(build-assets.py) vit ici : palettes, feuille SVG, cadre, motifs.

Python pur, sans dépendance : ce module tourne dans la CI.
"""
import json
import math
import os

from typo import Typo, _n

# ------------------------------------------------------------------ palettes

SOMBRE = dict(
    nom="dark",
    fond="#0F0D0B", surface="#171410", creux="#0A0908", trait="#2B251C",
    encre="#EFE4CB", doux="#B8AC92", discret="#857B69",
    o="#D2AE6D", o_haut="#F2DCA6", o_bas="#8E6E38",
    rouge="#E2583E", rouge_bas="#8C2C1C",
    # skyline : journée vide, puis quatre niveaux d'activité
    niveaux=("#1E1A15", "#4A3E28", "#7D6638", "#B08F4E", "#E3C582"),
)
CLAIR = dict(
    nom="light",
    fond="#F6EFE0", surface="#FFFBF0", creux="#EBE2CE", trait="#DDD1B8",
    encre="#1B1712", doux="#5C5346", discret="#8D8371",
    o="#9A7430", o_haut="#C29B4E", o_bas="#6B4F1E",
    rouge="#B93A22", rouge_bas="#7A2414",
    # en clair l'ordre s'inverse : la plus forte activité est la plus sombre
    niveaux=("#E9E0CC", "#E6D2A2", "#CFA95A", "#A07A32", "#6A4F1C"),
)
PALETTES = (SOMBRE, CLAIR)

# Silhouette de pique, dans une boîte 1000×1200 (x 120..880, y 70..1140).
PIQUE = ("M500,70 C560,250 880,420 880,650 C880,790 780,870 680,870 C610,870 560,830 535,780 "
         "C545,930 590,1050 665,1110 L665,1140 L335,1140 L335,1110 C410,1050 455,930 465,780 "
         "C440,830 390,870 320,870 C220,870 120,790 120,650 C120,420 440,250 500,70 Z")

# Flamme de la série en cours, dans une boîte de 18×18.
FLAMME = ("M9,0 C10.4,4 14.1,6.1 14.1,10.8 C14.1,14.8 11.8,17.6 9,17.6 "
          "C6.2,17.6 3.9,14.8 3.9,10.8 C3.9,8 6.3,6.6 6.9,3.4 "
          "C7.6,7 9.3,7.5 9.6,5.2 C9.9,3 8.4,1.8 9,0 Z")

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
ABBR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]
NNBSP = " "   # espace fine insécable : séparateur de milliers français


def fr(n):
    return "{:,}".format(int(n)).replace(",", NNBSP)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def teinte(hexa, facteur):
    """Assombrit (facteur < 1) une couleur #RRGGBB."""
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c * facteur)))) for c in (r, g, b))


def melange(a, b, t):
    """Couleur à la fraction t entre a et b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ca, cb))


def pique(cx, cy, h, fill, attrs=""):
    """Un petit pique centré en (cx, cy), haut de h."""
    s = h / 1070.0
    return '<path d="%s" transform="translate(%s %s) scale(%s)" fill="%s"%s/>' % (
        PIQUE, _n(cx - 500 * s), _n(cy - 605 * s), ("%.5f" % s).rstrip("0"), fill,
        " " + attrs if attrs else "")


def polaire(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def arc(cx, cy, r, a0, a1):
    """Arc de cercle de a0 à a1 degrés (sens horaire à l'écran), en `d` SVG."""
    x0, y0 = polaire(cx, cy, r, a0)
    x1, y1 = polaire(cx, cy, r, a1)
    return "M%.2f,%.2f A%s,%s 0 %d 1 %.2f,%.2f" % (x0, y0, _n(r), _n(r), 1 if a1 - a0 > 180 else 0, x1, y1)


def lisse(points, ferme=False):
    """Courbe lisse passant par des points : le `d` SVG (Béziers cubiques).

    Chaque point est (x, y) ou (x, y, "c") pour un angle vif. Entre deux
    angles, la courbe est une spline de Catmull-Rom : on dessine en posant des
    points sur le contour, sans régler de poignées."""
    pts = [(q[0], q[1], len(q) > 2) for q in points]
    if ferme:
        pts.append((pts[0][0], pts[0][1], True))
    d = ["M%s,%s" % (_d(pts[0][0]), _d(pts[0][1]))]
    debut = 0
    for i in range(1, len(pts)):
        if not (pts[i][2] or i == len(pts) - 1):
            continue
        troncon = pts[debut:i + 1]
        if len(troncon) == 2:
            d.append("L%s,%s" % (_d(troncon[1][0]), _d(troncon[1][1])))
        else:
            for j in range(len(troncon) - 1):
                p0 = troncon[max(j - 1, 0)]
                p1, p2 = troncon[j], troncon[j + 1]
                p3 = troncon[min(j + 2, len(troncon) - 1)]
                fin = "%s,%s %s,%s" % (_d(p2[0] - (p3[0] - p1[0]) / 6.0), _d(p2[1] - (p3[1] - p1[1]) / 6.0),
                                       _d(p2[0]), _d(p2[1]))
                if j:
                    # la première poignée est le reflet de la précédente : « S » la sous-entend
                    d.append("S" + fin)
                else:
                    d.append("C%s,%s %s" % (_d(p1[0] + (p2[0] - p0[0]) / 6.0),
                                            _d(p1[1] + (p2[1] - p0[1]) / 6.0), fin))
        debut = i
    return "".join(d) + ("Z" if ferme else "")


def _d(v):
    """Coordonnée au dixième, sans zéro inutile."""
    t = "%.1f" % v
    return t[:-2] if t.endswith(".0") else t


def guilloche(cx, cy, R, k, creux, tours=1, pas=720):
    """Rosace guillochée : une sinusoïde enroulée sur un cercle. k lobes,
    amplitude `creux`. Superposer plusieurs phases donne la moire des cadrans
    de montre et des billets."""
    pts = []
    for i in range(pas * tours + 1):
        t = 2 * math.pi * i / pas
        r = R + creux * math.sin(k * t)
        pts.append("%.1f,%.1f" % (cx + r * math.cos(t), cy + r * math.sin(t)))
    return "M" + " L".join(pts) + "Z"


def rosace(R, couches=3, k=18, pas=200):
    """Le `d` d'une rosace guillochée centrée sur l'origine : plusieurs
    sinusoïdes déphasées enroulées sur des cercles concentriques. À définir
    une fois dans les <defs>, puis à rappeler par <use> : le tracé est lourd."""
    o = []
    for c in range(couches):
        rr = R * (1 - 0.23 * c)
        for phase in range(3):
            pts = []
            for i in range(pas):
                t = 2 * math.pi * i / pas
                r = rr + R * 0.075 * math.sin(k * t + phase * 2 * math.pi / 3)
                pts.append("%.1f,%.1f" % (r * math.cos(t), r * math.sin(t)))
            o.append("M" + " ".join(pts) + "Z")
    return "".join(o)


# ------------------------------------------------------------------- feuille

class Feuille:
    """Un document SVG en construction : corps, styles, dégradés, glyphes.

    Le texte passe par self.t (Typo) ; les contours des glyphes utilisés sont
    rassemblés à la fin dans <defs id="glyphes">, que l'empreinte ignore."""

    _atlas = None

    def __init__(self, w, h, p, titre, desc=""):
        self.w, self.h, self.p = w, h, p
        if Feuille._atlas is None:
            Feuille._atlas = Typo()
        self.t = Feuille._atlas
        self.t.raz()
        self.titre, self.desc = titre, desc
        self.corps, self.css, self.defs = [], [], []

    def __iadd__(self, morceau):
        if isinstance(morceau, (list, tuple)):
            self.corps.extend(morceau)
        else:
            self.corps.append(morceau)
        return self

    def style(self, regles):
        self.css.append(regles)

    def definis(self, element):
        self.defs.append(element)

    def texte(self, police, texte, corps, x, y, **kw):
        return self.t.ecrire(police, texte, corps, x, y, **kw)

    def largeur(self, police, texte, corps, **kw):
        return self.t.largeur(police, texte, corps, **kw)

    def rendu(self):
        w, h = self.w, self.h
        o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
             'role="img" aria-labelledby="t d">' % (w, h, w, h),
             '<title id="t">%s</title><desc id="d">%s</desc>' % (esc(self.titre), esc(self.desc))]
        if self.css:
            o.append("<style>%s</style>" % "".join(self.css))
        if self.defs:
            o.append("<defs>%s</defs>" % "".join(self.defs))
        o.append(self.t.defs())
        o.extend(self.corps)
        o.append("</svg>")
        return "\n".join(o) + "\n"


def cadre(f, etiquette, maj=None, rayon=14):
    """Fond, double filet, étiquette « // TITRE » en or, horodatage discret.

    L'horodatage vit dans <g id="maj"> : l'empreinte le retire, pour ne
    republier que lorsqu'un chiffre a réellement bougé."""
    p, w, h = f.p, f.w, f.h
    f += '<rect x="0.6" y="0.6" width="%s" height="%s" rx="%d" fill="%s" stroke="%s" stroke-width="1.2"/>' % (
        _n(w - 1.2), _n(h - 1.2), rayon, p["fond"], p["trait"])
    f += '<rect x="6.5" y="6.5" width="%s" height="%s" rx="%d" fill="none" stroke="%s" stroke-width="0.7" opacity="0.32"/>' % (
        _n(w - 13), _n(h - 13), rayon - 5, p["o"])
    if etiquette:
        f += f.texte("mono-gras", "// " + etiquette.upper(), 11, 28, 39, approche=3, fill=p["o"])
    if maj:
        f += f.texte("mono", maj, 9.5, w - 28, 39, ancre="end", fill=p["discret"], attrs='id="maj"')


_EMBLEME = None


def embleme(f, x, y, h, attributs=None):
    """Pose l'as de pique en filigrane : sa boîte 1000×1200 est ramenée à la
    hauteur h, coin haut-gauche en (x, y).

    Le dessin vient de embleme.json (produit par build-embleme.py). Chaque
    couche est définie une fois dans les <defs> et rappelée par <use> — deux
    fois quand elle a un miroir : la moitié droite n'est jamais stockée.
    attributs(couche) renvoie les attributs à ajouter à ses <use> (classe
    d'animation, retard), ou une chaîne vide."""
    global _EMBLEME
    if _EMBLEME is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "embleme.json"), encoding="utf-8") as fh:
            _EMBLEME = json.load(fh)
    o = ['<g transform="translate(%s %s) scale(%s)">' % (_n(x), _n(y), ("%.5f" % (h / 1200.0)).rstrip("0"))]
    for k, c in enumerate(_EMBLEME["couches"]):
        f.definis('<g id="e%d" fill="currentColor">%s</g>' % (k, c["svg"]))
        plus = attributs(c) if attributs else ""
        ton = f.p["o"] if c["ton"] == "or" else f.p["encre"]
        o.append('<use href="#e%d" color="%s"%s/>' % (k, ton, plus))
        if c["miroir"]:
            o.append('<use href="#e%d" color="%s" transform="matrix(-1 0 0 1 1000 0)"%s/>' % (k, ton, plus))
    o.append("</g>")
    return "".join(o)


def quantieme(jour):
    """Le jour du mois tel qu'on l'écrit : « 1er », puis 2, 3…"""
    return "1er" if jour == 1 else "%d" % jour


def horodatage(dt, court=False):
    if court:
        return "%s %s %d · %02dh%02d UTC" % (quantieme(dt.day), ABBR[dt.month - 1], dt.year, dt.hour, dt.minute)
    return "mis à jour le %s %s %d à %02dh%02d UTC" % (
        quantieme(dt.day), ABBR[dt.month - 1], dt.year, dt.hour, dt.minute)
