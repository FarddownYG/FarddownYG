#!/usr/bin/env python3
"""Empreinte des cartes, horodatage exclu.

Chaque carte porte l'heure de son calcul : deux rendus successifs diffèrent
donc toujours, même quand aucun chiffre n'a bougé. Comparer les cartes privées
de cette ligne permet de ne republier que sur un vrai changement, au lieu de
pousser une branche toutes les deux minutes pour rien.

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
        h.update(re.sub(r"mis à jour le[^<]*", "", f.read()).encode("utf-8"))
print(h.hexdigest()[:16])
