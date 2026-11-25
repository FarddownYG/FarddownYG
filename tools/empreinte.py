#!/usr/bin/env python3
"""Empreinte des cartes, horodatage exclu.

Chaque carte porte l'heure de son calcul : deux rendus successifs diffèrent
donc toujours, même quand aucun chiffre n'a bougé. Comparer les cartes privées
de leur horodatage permet de ne republier que sur un vrai changement, au lieu
de pousser une branche toutes les deux minutes pour rien.

Deux morceaux sont retirés avant de comparer : le groupe <g id="maj">, qui
contient l'horodatage, et le bloc <defs id="glyphes">, qui liste les contours
des caractères employés — donc aussi ceux des chiffres de l'heure.

Usage :
    empreinte.py DOSSIER
"""
import glob
import hashlib
import os
import re
import sys

dossier = sys.argv[1] if len(sys.argv) > 1 else "out"
h = hashlib.sha256()
for chemin in sorted(glob.glob(os.path.join(dossier, "*.svg"))):
    with open(chemin, encoding="utf-8") as f:
        svg = re.sub(r'<g[^>]*\bid="maj"[^>]*>.*?</g>', "", f.read(), flags=re.S)
        svg = re.sub(r'<defs id="glyphes">.*?</defs>', "", svg, flags=re.S)
        h.update(svg.encode("utf-8"))
print(h.hexdigest()[:16])
