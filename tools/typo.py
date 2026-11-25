"""Composition de texte en tracés, à partir de l'atlas glyphes.json.

Python pur, aucune dépendance : c'est ce module que la CI exécute. L'atlas
fournit, pour chaque police, le contour de chaque caractère (en unités de
police, axe y déjà retourné), sa chasse, les paires de crénage et les
ligatures. On en tire des textes rendus à l'identique sur tous les appareils,
et dont la largeur est connue au dixième de pixel — ce qui permet de caler une
mise en page sans jamais deviner.

Chaque glyphe utilisé est défini une fois dans un <defs id="glyphes">, puis
rappelé par <use>. Les identifiants dérivent de la police et du caractère,
pas de l'ordre d'écriture : deux rendus du même texte donnent le même fichier.
"""
import json
import os

_ICI = os.path.dirname(os.path.abspath(__file__))
_PREFIXES = {"titre": "t", "texte": "x", "ital": "i", "mono": "m", "mono-gras": "g"}
# espaces que les polices n'ont pas toutes : fraction de l'espace ordinaire
_ESPACES = {" ": 1.0, " ": 0.55, " ": 0.55}


def _n(v):
    """Nombre au plus court : 12.0 → 12, 3.250 → 3.25."""
    return ("%.2f" % v).rstrip("0").rstrip(".") if v % 1 else "%d" % v


class Typo:
    def __init__(self, chemin=None):
        with open(chemin or os.path.join(_ICI, "glyphes.json"), encoding="utf-8") as f:
            self.polices = json.load(f)["polices"]
        self.vus = {}

    def raz(self):
        """À appeler avant chaque document : les <defs> ne se partagent pas."""
        self.vus = {}

    # ------------------------------------------------------------- mesure

    def _glyphe(self, police, cle):
        p = self.polices[police]
        if cle in p["l"]:
            return p["l"][cle]
        if cle in p["g"]:
            return p["g"][cle]
        if cle in _ESPACES:
            return [p["g"][" "][0] * _ESPACES[cle], ""]
        raise KeyError("caractère %r absent de la police %r" % (cle, police))

    def suite(self, police, texte, corps, approche=0.0, tab=False):
        """Glyphes posés : [(clé, x)] en unités de police, et la largeur en px.

        approche : interlettrage en px au corps demandé. tab : chaque chiffre
        est centré dans une case de la largeur du plus large, sans crénage —
        pour les colonnes et les compteurs."""
        p = self.polices[police]
        upm = p["upm"]
        suivi = approche * upm / corps
        case = max(p["g"][c][0] for c in "0123456789") if tab else 0
        poses, x, i, prec = [], 0.0, 0, None
        while i < len(texte):
            cle = texte[i]
            for lig in ("ffi", "ffl", "ff", "fi", "fl"):
                if texte.startswith(lig, i) and lig in p["l"] and not suivi:
                    cle = lig
                    break
            chasse = self._glyphe(police, cle)[0]
            if tab and cle.isdigit():
                poses.append((cle, x + (case - chasse) / 2.0))
                x += case + suivi
                prec = None
            else:
                if prec is not None:
                    x += p["k"].get(prec + cle[0], 0)
                poses.append((cle, x))
                x += chasse + suivi
                prec = cle[-1]
            i += len(cle)
        if poses:
            x -= suivi
        return poses, x * corps / upm

    def largeur(self, police, texte, corps, approche=0.0, tab=False):
        return self.suite(police, texte, corps, approche, tab)[1]

    def capitale(self, police, corps):
        """Hauteur des capitales en px : pour centrer verticalement un texte."""
        p = self.polices[police]
        return p["cap"] * corps / p["upm"]

    # ------------------------------------------------------------- écriture

    def ref(self, police, cle):
        """Identifiant du glyphe dans les <defs> ; l'enregistre au passage."""
        ident = _PREFIXES[police] + "".join("%x" % ord(c) for c in cle)
        self.vus[ident] = (police, cle)
        return ident

    def ecrire(self, police, texte, corps, x, y, ancre="start", approche=0.0, tab=False,
               fill=None, attrs="", cascade=None):
        """Un <g> de <use>, ligne de base en y. ancre : start, middle ou end.

        cascade=(départ, pas) en secondes : chaque glyphe reçoit la classe « n »
        et un retard croissant, pour une entrée lettre à lettre (la feuille de
        style de l'appelant définit l'animation « n »)."""
        poses, largeur = self.suite(police, texte, corps, approche, tab)
        if ancre == "end":
            x -= largeur
        elif ancre == "middle":
            x -= largeur / 2.0
        ech = corps / self.polices[police]["upm"]
        visibles = [(cle, gx) for cle, gx in poses if self._glyphe(police, cle)[1]]
        uses = "".join(
            '<use href="#%s"%s%s/>' % (
                self.ref(police, cle), ' x="%s"' % _n(gx) if gx else "",
                ' class="n" style="animation-delay:%ss"' % _n(cascade[0] + i * cascade[1]) if cascade else "")
            for i, (cle, gx) in enumerate(visibles))
        return '<g transform="translate(%s %s) scale(%s)"%s%s>%s</g>' % (
            _n(x), _n(y), ("%.5f" % ech).rstrip("0"), ' fill="%s"' % fill if fill else "",
            " " + attrs if attrs else "", uses)

    def defs(self):
        """Les contours de tous les glyphes écrits depuis le dernier raz()."""
        return '<defs id="glyphes">%s</defs>' % "".join(
            '<path id="%s" d="%s"/>' % (ident, self._glyphe(police, cle)[1])
            for ident, (police, cle) in sorted(self.vus.items()))
