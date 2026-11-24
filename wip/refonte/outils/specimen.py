import sys
sys.path.insert(0, sys.argv[1] + "/lab")
from typo import Police
F = sys.argv[1] + "/fonts/x/"
cands = [
    ("Playfair Display 800", F + "playfair-display/files/playfair-display-latin-800-normal.woff2", F + "playfair-display/files/playfair-display-latin-500-italic.woff2", {}),
    ("Bodoni Moda 700", F + "bodoni-moda/files/bodoni-moda-latin-700-normal.woff2", F + "bodoni-moda/files/bodoni-moda-latin-500-italic.woff2", {}),
    ("Cormorant Garamond 600", F + "cormorant-garamond/files/cormorant-garamond-latin-600-normal.woff2", F + "cormorant-garamond/files/cormorant-garamond-latin-500-italic.woff2", {"lnum": True}),
    ("Cinzel 700", F + "cinzel/files/cinzel-latin-700-normal.woff2", F + "cormorant-garamond/files/cormorant-garamond-latin-500-italic.woff2", {}),
    ("Fraunces 600", F + "fraunces/files/fraunces-latin-600-normal.woff2", F + "fraunces/files/fraunces-latin-400-italic.woff2", {}),
    ("DM Serif Display", F + "dm-serif-display/files/dm-serif-display-latin-400-normal.woff2", F + "dm-serif-display/files/dm-serif-display-latin-400-italic.woff2", {}),
]
mono = Police(F + "jetbrains-mono/files/jetbrains-mono-latin-500-normal.woff2")
W, RH = 1500, 250
o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (W, RH * len(cands), W, RH * len(cands)),
     '<rect width="100%" height="100%" fill="#100E0B"/>']
for i, (nom, gras, ital, tr) in enumerate(cands):
    y = i * RH
    p, pi = Police(gras), Police(ital)
    d, w = mono.forme("// " + nom.upper(), 13, approche=2)
    o.append('<path transform="translate(30,%d)" d="%s" fill="#8C8372"/>' % (y + 30, d))
    d, w = p.forme("YANIS", 120, approche=10)
    o.append('<path transform="translate(30,%d)" d="%s" fill="#EFE4CB"/>' % (y + 150, d))
    d, w2 = p.forme("3 984", 96, traits={**tr, "tnum": True, "lnum": True})
    o.append('<path transform="translate(%d,%d)" d="%s" fill="#D2AE6D"/>' % (560, y + 140, d))
    d, _ = p.forme("338  33  2  17,6", 44, traits={**tr, "tnum": True, "lnum": True})
    o.append('<path transform="translate(%d,%d)" d="%s" fill="#EFE4CB"/>' % (560, y + 205, d))
    d, _ = p.forme("INGÉNIEUR CYBERSÉCURITÉ · FONDATEUR DE CLASSOR", 19, approche=3.2)
    o.append('<path transform="translate(%d,%d)" d="%s" fill="#B9AE96"/>' % (880, y + 70, d))
    d, _ = pi.forme("« Celui qui tire doit être prêt à recevoir la balle. »", 30)
    o.append('<path transform="translate(%d,%d)" d="%s" fill="#EFE4CB"/>' % (880, y + 125, d))
    d, _ = p.forme("Plus longue série · Meilleure semaine", 24)
    o.append('<path transform="translate(%d,%d)" d="%s" fill="#B9AE96"/>' % (880, y + 175, d))
    d, _ = mono.forme("12 juil. – 13 août · mis à jour à 22h47 UTC", 14)
    o.append('<path transform="translate(%d,%d)" d="%s" fill="#8C8372"/>' % (880, y + 215, d))
    o.append('<path d="M0,%d H%d" stroke="#2A251D"/>' % (y + RH, W))
o.append('</svg>')
open(sys.argv[1] + "/lab/specimen-dark.svg", "w", encoding="utf-8").write("\n".join(o))
print("ok")
