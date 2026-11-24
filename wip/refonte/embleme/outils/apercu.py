#!/usr/bin/env python3
"""Vérifie un emblème et en rend les aperçus normalisés.

usage : python3 apercu.py DOSSIER        (DOSSIER contient emblem.svg)

Écrit dans DOSSIER :
  apercu-sombre.png   crème sur noir chaud, 700×840
  apercu-clair.png    encre sur papier crème, 700×840
  apercu-tailles.png  320 / 160 / 80 / 40 px de haut, sombre puis clair
et imprime les mesures (poids, éléments, couverture d'encre, débord).
Code de sortie 1 si le contrat n'est pas respecté.
"""
import os, re, subprocess, sys
import xml.etree.ElementTree as ET

ICI = os.path.dirname(os.path.abspath(__file__))
SHOOT = os.path.join(os.path.dirname(os.path.dirname(ICI)), "shoot.js")
SILHOUETTE = open(os.path.join(ICI, "silhouette.txt")).read().strip()
AUTORISES = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon",
             "defs", "use", "clipPath", "mask", "symbol", "title", "desc"}
SOMBRE = dict(fond="#100E0B", encre="#EFE4CB", o="#D2AE6D")
CLAIR = dict(fond="#F6EFE0", encre="#1B1712", o="#9A7430")


def lire(dossier):
    chemin = os.path.join(dossier, "emblem.svg")
    brut = open(chemin, encoding="utf-8").read()
    racine = ET.fromstring(brut)
    erreurs = []
    if racine.tag != "{http://www.w3.org/2000/svg}svg":
        erreurs.append("la racine doit être <svg xmlns='http://www.w3.org/2000/svg'>")
    if racine.get("viewBox", "").split() != ["0", "0", "1000", "1200"]:
        erreurs.append("viewBox doit valoir « 0 0 1000 1200 » (trouvé : %r)" % racine.get("viewBox"))
    compte = {}
    for el in racine.iter():
        nom = el.tag.split("}")[-1]
        compte[nom] = compte.get(nom, 0) + 1
        if nom not in AUTORISES:
            erreurs.append("élément interdit : <%s>" % nom)
        dans_masque = False
        for attr in ("fill", "stroke", "stop-color", "color"):
            v = el.get(attr)
            if v and v not in ("none", "currentColor", "#fff", "#000", "white", "black", "#ffffff", "#000000") \
                    and not v.startswith("url("):
                erreurs.append("couleur en dur %s=%r sur <%s> : utiliser currentColor (ou la classe « or »)" % (attr, v, nom))
        if el.get("style"):
            erreurs.append("attribut style interdit sur <%s> : utiliser des attributs de présentation" % nom)
    poids = len(brut.encode("utf-8"))
    if poids > 160 * 1024:
        erreurs.append("fichier trop lourd : %.0f Ko (plafond 160 Ko)" % (poids / 1024))
    interieur = brut[brut.index(">", brut.index("<svg")) + 1: brut.rindex("</svg>")]
    return interieur, compte, poids, sorted(set(erreurs))


def hote(interieur, p, w, h, fond=True):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200" width="%d" height="%d">'
            '<style>.or{color:%s}</style>%s<g color="%s">%s</g></svg>'
            % (w, h, p["o"], '<rect width="1000" height="1200" fill="%s"/>' % p["fond"] if fond else "",
               p["encre"], interieur))


def rendre(svg, png, largeur, dossier, nom):
    chemin = os.path.join(dossier, nom)
    open(chemin, "w", encoding="utf-8").write(svg)
    env = dict(os.environ)
    env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["node", SHOOT, chemin, png, str(largeur), "200", "1"], capture_output=True, text=True, env=env)
    os.remove(chemin)
    if r.returncode:
        raise SystemExit("échec du rendu : " + r.stderr[-400:])


def main():
    dossier = os.path.abspath(sys.argv[1])
    interieur, compte, poids, erreurs = lire(dossier)
    tmp = os.path.join(dossier, ".tmp")
    os.makedirs(tmp, exist_ok=True)

    rendre(hote(interieur, SOMBRE, 700, 840), os.path.join(dossier, "apercu-sombre.png"), 700, tmp, "sombre.svg")
    rendre(hote(interieur, CLAIR, 700, 840), os.path.join(dossier, "apercu-clair-light.png"), 700, tmp, "clair-light.svg")
    os.replace(os.path.join(dossier, "apercu-clair-light.png"), os.path.join(dossier, "apercu-clair.png"))

    # planche des tailles : 320, 160, 80, 40 px de haut, sur sombre puis sur clair
    cases, x = [], 20
    for cle, p in (("s", SOMBRE), ("c", CLAIR)):
        for hpx in (320, 160, 80, 40):
            wpx = hpx * 1000 / 1200
            cases.append('<g class="%s" transform="translate(%.1f,%.1f) scale(%.5f)"><g color="%s">%s</g></g>'
                         % (cle, x, 20 + (320 - hpx), hpx / 1200, p["encre"], interieur))
            x += wpx + 24
        x += 30
        if cle == "s":
            coupe = x - 15
    largeur = int(x)
    planche = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d 360" width="%d" height="360">'
               '<style>.s .or{color:%s}.c .or{color:%s}</style>'
               '<rect width="%.1f" height="360" fill="%s"/><rect x="%.1f" width="%.1f" height="360" fill="%s"/>%s</svg>'
               % (largeur, largeur, SOMBRE["o"], CLAIR["o"], coupe, SOMBRE["fond"], coupe, largeur - coupe,
                  CLAIR["fond"], "".join(cases)))
    rendre(planche, os.path.join(dossier, "apercu-tailles.png"), largeur, tmp, "tailles.svg")

    # mesures : couverture d'encre dans la silhouette de référence, débord au-dehors
    from PIL import Image
    blanc = dict(fond="#000000", encre="#FFFFFF", o="#FFFFFF")
    rendre(hote(interieur, blanc, 500, 600), os.path.join(tmp, "encre.png"), 500, tmp, "encre.svg")
    masque = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200" width="500" height="600">'
              '<rect width="1000" height="1200" fill="#000"/><path d="%s" fill="#fff"/></svg>' % SILHOUETTE)
    rendre(masque, os.path.join(tmp, "masque.png"), 500, tmp, "masque.svg")
    # même masque épaissi de 22 unités : un contour posé à cheval sur le bord
    # n'est pas un débord
    large = masque.replace('fill="#fff"/>', 'fill="#fff" stroke="#fff" stroke-width="44" stroke-linejoin="round"/>')
    rendre(large, os.path.join(tmp, "large.png"), 500, tmp, "large.svg")
    e = Image.open(os.path.join(tmp, "encre.png")).convert("L")
    m = Image.open(os.path.join(tmp, "masque.png")).convert("L")
    ml = Image.open(os.path.join(tmp, "large.png")).convert("L").load()
    pe, pm = e.load(), m.load()
    dedans = dehors = aire = hors = 0
    gauche = droite = 0.0
    for y in range(e.size[1]):
        for xx in range(e.size[0]):
            v = pe[xx, y] / 255.0
            if pm[xx, y] > 127:
                aire += 1; dedans += v
            if ml[xx, y] <= 127:
                dehors += v
            total_encre = locals().get("total_encre", 0.0) + v
            if xx < 250: gauche += v
            else: droite += v
    asym = abs(gauche - droite) / max(1.0, gauche + droite)
    # symétrie pixel à pixel
    ecart = 0.0
    for y in range(0, e.size[1], 2):
        for xx in range(0, 250, 2):
            ecart += abs(pe[xx, y] - pe[499 - xx, y]) / 255.0
    ecart /= (e.size[1] / 2) * 125
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)

    print("poids            : %.1f Ko (plafond 160)" % (poids / 1024))
    print("éléments         : " + ", ".join("%s×%d" % kv for kv in sorted(compte.items()) if kv[0] != "svg"))
    print("couverture       : %.0f %% de la silhouette de référence est encrée (cible 38–62 %%)" % (100 * dedans / aire))
    print("débord           : %.1f %% de l'encre tombe à plus de 22 unités hors de la silhouette de référence (cible < 6 %%)" % (100 * dehors / max(1e-9, total_encre)))
    print("symétrie         : écart moyen gauche/droite %.2f %% (0 = parfaite ; cible < 0,5 %%)" % (100 * ecart))
    print("aperçus écrits   : apercu-sombre.png, apercu-clair.png, apercu-tailles.png")
    if erreurs:
        print("\nCONTRAT NON RESPECTÉ :")
        for x in erreurs[:20]:
            print("  - " + x)
        sys.exit(1)
    print("contrat          : respecté")


if __name__ == "__main__":
    main()
