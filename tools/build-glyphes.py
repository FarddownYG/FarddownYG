#!/usr/bin/env python3
"""Fabrique tools/glyphes.json : l'atlas typographique du profil.

Pourquoi un atlas. Une image SVG affichée par GitHub ne peut charger aucune
police : avec des balises <text>, chaque appareil retombe sur ce qu'il a
(Courier sur un iPhone), et rien ne permet de mesurer un texte pour le caler.
Ici chaque caractère devient un tracé : même dessin partout, largeurs exactes.

Cet outil ne tourne QUE sur le poste de développement, quand on change de
police ou de jeu de caractères. Il dépend de fontTools, brotli et uharfbuzz.
Les générateurs (build-stats.py, build-assets.py) ne lisent que le JSON
produit : ils restent en Python pur, sans dépendance, y compris dans la CI.

Usage :
    npm pack @fontsource/playfair-display @fontsource/jetbrains-mono   # puis extraire
    pip install fonttools brotli uharfbuzz
    build-glyphes.py DOSSIER_DES_POLICES > glyphes.json

DOSSIER_DES_POLICES contient playfair-display/files/*.woff2 et
jetbrains-mono/files/*.woff2 (l'arborescence des paquets @fontsource).

Polices : Playfair Display (Claus Eggers Sørensen) et JetBrains Mono
(JetBrains), toutes deux sous SIL Open Font License 1.1 — voir tools/POLICES.md.
"""
import io
import json
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
import uharfbuzz as hb

# clé de l'atlas → (fichier, mise en forme HarfBuzz, crénage ?)
POLICES = {
    # titres et grands chiffres
    "titre": ("playfair-display/files/playfair-display-latin-800-normal.woff2", True),
    # libellés
    "texte": ("playfair-display/files/playfair-display-latin-500-normal.woff2", True),
    # credo, notes
    "ital": ("playfair-display/files/playfair-display-latin-500-italic.woff2", True),
    # la voix « code » : étiquettes, dates, unités
    "mono": ("jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2", False),
    "mono-gras": ("jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff2", False),
}

CARACTERES = (
    [chr(c) for c in range(0x20, 0x7F)]
    + [chr(c) for c in range(0xA0, 0x100)]
    + list("ŒœŸ–—‘’“”…•‹›€′″")
)
LIGATURES = ("ffi", "ffl", "ff", "fi", "fl")
SEUIL_CRENAGE = 6      # unités sur 1000 : en dessous, invisible à nos corps


def charger(chemin):
    tt = TTFont(chemin)
    tampon = io.BytesIO()
    tt.flavor = None
    tt.save(tampon)
    return tt, hb.Font(hb.Face(tampon.getvalue()))


def former(police, texte, traits):
    buf = hb.Buffer()
    buf.add_str(texte)
    buf.guess_segment_properties()
    hb.shape(police, buf, traits)
    return buf.glyph_infos, buf.glyph_positions


def contour(tt, nom):
    """Tracé du glyphe, axe y retourné (SVG), en unités entières de la police."""
    jeu = tt.getGlyphSet()
    pen = SVGPathPen(jeu, ntos=lambda v: str(int(round(v))))
    jeu[nom].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
    return pen.getCommands()


def atlas(dossier, fichier, crener):
    tt, police = charger(dossier.rstrip("/") + "/" + fichier)
    ordre = tt.getGlyphOrder()
    cmap = tt.getBestCmap()
    os2 = tt["OS/2"]
    upm = police.face.upem
    base = {"kern": True, "liga": False, "calt": False}

    def un(car, traits):
        infos, pos = former(police, car, traits)
        if len(infos) != 1 or infos[0].codepoint == 0:
            return None
        return [pos[0].x_advance, contour(tt, ordre[infos[0].codepoint])]

    # Chiffres alignés (lnum). Playfair n'a pas de chiffres tabulaires : pour
    # les compteurs et les colonnes, typo.py centre chaque chiffre dans une
    # case de largeur fixe.
    glyphes = {}
    for car in CARACTERES:
        if ord(car) not in cmap:
            continue
        g = un(car, {**base, "lnum": True, "pnum": True})
        if g:
            glyphes[car] = g

    paires = {}
    if crener:
        cles = list(glyphes)      # espaces compris : « R T » se crène aussi
        for a in cles:
            for b in cles:
                infos, pos = former(police, a + b, {**base, "lnum": True, "pnum": True})
                if len(infos) != 2:
                    continue
                ecart = pos[0].x_advance + pos[1].x_advance - glyphes[a][0] - glyphes[b][0]
                if abs(ecart) >= SEUIL_CRENAGE * upm / 1000:
                    paires[a + b] = ecart

    ligatures = {}
    if crener:
        for lig in LIGATURES:
            infos, pos = former(police, lig, {**base, "liga": True})
            if len(infos) == 1 and infos[0].codepoint:
                ligatures[lig] = [pos[0].x_advance, contour(tt, ordre[infos[0].codepoint])]

    return {
        "upm": upm,
        "cap": getattr(os2, "sCapHeight", 0) or 700,
        "x": getattr(os2, "sxHeight", 0) or 500,
        "g": glyphes,
        "k": paires,
        "l": ligatures,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sortie = {"polices": {cle: atlas(sys.argv[1], f, k) for cle, (f, k) in POLICES.items()}}
    json.dump(sortie, sys.stdout, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    for cle, p in sortie["polices"].items():
        print("%-10s %3d glyphes, %5d paires, %d ligatures"
              % (cle, len(p["g"]), len(p["k"]), len(p["l"])), file=sys.stderr)


if __name__ == "__main__":
    main()
