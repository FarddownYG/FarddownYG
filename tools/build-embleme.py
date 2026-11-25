#!/usr/bin/env python3
"""L'as de pique en filigrane (outil de dessin, pour le développement).

usage : python3 tools/build-embleme.py > tools/embleme.json

Le filigrane est un travail d'orfèvre : un cordon dessine la forme, quelques
grandes volutes de fil maître l'habitent, puis chaque vide est comblé de
spirales de fil fin serrées les unes contre les autres, et de grains dans les
interstices. Ce script procède de la même façon :

  1. le pourtour — cordon, rang de perles, liseré — suit la silhouette à
     distance constante (courbes de niveau d'un champ de distance) ;
  2. l'ossature — axe, médaillon, volutes en C — est posée à la main ;
  3. la dentelle est un empilement glouton : à chaque tour, le plus grand
     cercle qui tient encore dans le vide restant reçoit une spirale qui part
     de son point de contact, comme une vrille naît d'une tige.

Seule la moitié gauche est calculée ; la droite en est le miroir exact.

Dépendance : numpy. La CI n'exécute pas ce script : elle lit embleme.json,
que dessin.embleme() sait poser dans une feuille.
"""
import json
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dessin import PIQUE, _d, lisse  # noqa: E402

PAS = 2.0                  # maille du champ de distance
JEU = 2.0                  # vide entre deux fils
FIL = 3.4                  # fil de dentelle
MAITRE = 7.0               # fil des grandes volutes
CORDON = 8.0               # fil du pourtour
RANG = 14.6                # axe du rang de perles
LISERE = 22.4              # axe du liseré intérieur
BORD = 24.0                # limite intérieure du pourtour
PASFIN = 8.6               # pas des spirales de dentelle
CENTRE = (500.0, 648.0)    # médaillon
R_MED = 84.0
R_MAX, R_SPIRALE, R_OEILLET, R_MIN = 38.0, 10.0, 5.6, 2.6


# ------------------------------------------------------------- géométrie

def silhouette():
    """La silhouette en polyligne dense : un point par unité environ."""
    j = re.findall(r"[MCLZ]|-?\d+(?:\.\d+)?", PIQUE)
    pts, i, cur = [], 0, None
    while i < len(j):
        c = j[i]
        i += 1
        if c == "M":
            cur = (float(j[i]), float(j[i + 1]))
            i += 2
            pts.append(cur)
        elif c == "L":
            p = (float(j[i]), float(j[i + 1]))
            i += 2
            n = max(1, int(math.hypot(p[0] - cur[0], p[1] - cur[1])))
            pts += [(cur[0] + (p[0] - cur[0]) * k / n, cur[1] + (p[1] - cur[1]) * k / n) for k in range(1, n + 1)]
            cur = p
        elif c == "C":
            a = [float(v) for v in j[i:i + 6]]
            i += 6
            n = int(math.hypot(a[4] - cur[0], a[5] - cur[1]) * 1.4) + 8
            for k in range(1, n + 1):
                t = k / n
                u = 1 - t
                pts.append((u ** 3 * cur[0] + 3 * u * u * t * a[0] + 3 * u * t * t * a[2] + t ** 3 * a[4],
                            u ** 3 * cur[1] + 3 * u * u * t * a[1] + 3 * u * t * t * a[3] + t ** 3 * a[5]))
            cur = (a[4], a[5])
    return np.array(pts[:-1])          # le dernier point referme sur le premier


XS = np.arange(0, 500 + PAS, PAS)
YS = np.arange(0, 1200 + PAS, PAS)
X, Y = np.meshgrid(XS, YS)


def distances(points):
    """Distance de chaque maille au plus proche des points donnés."""
    P = np.asarray(points, dtype=float)
    fx, fy = X.ravel(), Y.ravel()
    out = np.empty(fx.shape)
    for s in range(0, fx.size, 2000):
        dx = fx[s:s + 2000, None] - P[None, :, 0]
        dy = fy[s:s + 2000, None] - P[None, :, 1]
        out[s:s + 2000] = np.sqrt((dx * dx + dy * dy).min(axis=1))
    return out.reshape(X.shape)


def interieur(poly):
    """Mailles situées dans le polygone (balayage ligne à ligne)."""
    dedans = np.zeros(X.shape, bool)
    x0, y0 = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
    for i, y in enumerate(YS):
        yy = y + 0.013
        m = (y0 <= yy) != (y1 <= yy)
        xc = np.sort(x0[m] + (yy - y0[m]) * (x1[m] - x0[m]) / (y1[m] - y0[m]))
        for a, b in zip(xc[::2], xc[1::2]):
            dedans[i, (XS >= a) & (XS <= b)] = True
    return dedans


def niveau(F, v):
    """La courbe F = v dans la demi-grille : polyligne dense, du haut de l'axe vers le bas."""
    G = F - v
    pts = []
    a, b = G[:, :-1], G[:, 1:]
    ii, jj = np.nonzero((a > 0) != (b > 0))
    t = a[ii, jj] / (a[ii, jj] - b[ii, jj])
    pts += list(zip(XS[jj] + t * PAS, YS[ii]))
    a, b = G[:-1, :], G[1:, :]
    ii, jj = np.nonzero((a > 0) != (b > 0))
    t = a[ii, jj] / (a[ii, jj] - b[ii, jj])
    pts += list(zip(XS[jj], YS[ii] + t * PAS))
    P = np.array(pts)
    reste = np.ones(len(P), bool)
    k = int(np.argmin(np.where(P[:, 0] > 499.9, P[:, 1], 1e9)))
    ordre = [k]
    reste[k] = False
    while reste.any():
        d = np.where(reste, np.hypot(P[:, 0] - P[k, 0], P[:, 1] - P[k, 1]), 1e9)
        k = int(np.argmin(d))
        if d[k] > 9:
            break
        ordre.append(k)
        reste[k] = False
    return P[ordre]


def abscisses(P):
    return np.concatenate([[0.0], np.cumsum(np.hypot(P[1:, 0] - P[:-1, 0], P[1:, 1] - P[:-1, 1]))])


def point_a(P, s, t):
    """Le point d'abscisse curviligne t sur la polyligne P."""
    i = int(np.clip(np.searchsorted(s, t), 1, len(P) - 1))
    u = (t - s[i - 1]) / max(1e-9, s[i] - s[i - 1])
    return P[i - 1] + (P[i] - P[i - 1]) * u


def coins(P, s, fenetre=5.0, seuil=38.0):
    """Indices des angles vifs d'une polyligne dense."""
    ang = np.zeros(len(P))
    for i in range(len(P)):
        if s[i] < fenetre or s[-1] - s[i] < fenetre:
            continue
        u = P[i] - point_a(P, s, s[i] - fenetre)
        v = point_a(P, s, s[i] + fenetre) - P[i]
        ang[i] = abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
    out, i = [], 0
    while i < len(P):
        if ang[i] > seuil:
            j = i
            while j + 1 < len(P) and ang[j + 1] > seuil:
                j += 1
            out.append(i + int(np.argmax(ang[i:j + 1])))
            i = j + 1
        else:
            i += 1
    return out


def regulier(P, pas):
    """Rééchantillonne à pas constant entre les angles vifs, qui restent vifs."""
    s = abscisses(P)
    bornes = [0] + coins(P, s) + [len(P) - 1]
    out = [(P[0][0], P[0][1], "c")]
    for a, b in zip(bornes, bornes[1:]):
        n = max(1, int(round((s[b] - s[a]) / pas)))
        for k in range(1, n + 1):
            q = point_a(P, s, s[a] + (s[b] - s[a]) * k / n)
            out.append((q[0], q[1], "c") if k == n else (q[0], q[1]))
    return out


def spirale(c, R, a0, sens, pas, r_fin, d_deg):
    """Spirale d'Archimède, du dehors (rayon R, angle a0) vers le cœur (rayon r_fin)."""
    total = (R - r_fin) / pas * 360.0
    n = max(1, int(math.ceil(total / d_deg)))
    pts = []
    for k in range(n + 1):
        th = min(total, k * d_deg)
        rho = R - pas * th / 360.0
        a = math.radians(a0 + sens * th)
        pts.append((c[0] + rho * math.cos(a), c[1] + rho * math.sin(a)))
    return pts


def bezier(p0, p1, p2, p3, n):
    out = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


# ------------------------------------------------------------- ossature

def ossature(fin):
    """Les fils maîtres de la moitié gauche : [(points, demi-épaisseur)].

    fin=True : points serrés, pour le champ de distance ; fin=False : points
    espacés, ceux du tracé (la spline les relie)."""
    pas_deg = 2.0 if fin else 45.0
    nb = 60 if fin else 6
    fils = []
    # grande volute en C : une spirale dans le lobe, une autre vers la pointe
    ca, ra = (283.0, 702.0), 100.0
    cb, rb = (418.0, 420.0), 56.0
    bas = spirale(ca, ra, 180, -1, 30.0, 10.0, pas_deg)
    haut = spirale(cb, rb, 180, +1, 25.0, 9.0, pas_deg)
    lien = bezier(bas[0], (bas[0][0], bas[0][1] - 118), (haut[0][0], haut[0][1] + 100), haut[0], nb)
    fils.append((bas[::-1] + lien[1:-1] + haut, MAITRE / 2, [bas[-1], haut[-1]]))
    # crosses de la pointe
    ct = (455.0, 300.0)
    sp = spirale(ct, 30.0, 90, +1, 21.0, 7.0, pas_deg)
    tige = bezier((500.0, 374.0), (489.0, 345.0), (478.0, sp[0][1]), sp[0], nb // 2)
    fils.append((tige[:-1] + sp, MAITRE / 2 - 0.6, [sp[-1]]))
    # crosses du pied
    cf = (444.0, 1062.0)
    sp = spirale(cf, 26.0, 270, -1, 19.0, 7.0, pas_deg)
    tige = bezier((500.0, 984.0), (491.0, 1012.0), (466.0, sp[0][1]), sp[0], nb // 2)
    fils.append((tige[:-1] + sp, MAITRE / 2 - 0.6, [sp[-1]]))
    return fils


AXE = (((500.0, 182.0), (500.0, CENTRE[1] - R_MED)), ((500.0, CENTRE[1] + R_MED), (500.0, 1101.0)))
AXE_DEMI = 2.5


# ------------------------------------------------------------- dessin

def cercle(x, y, r, plein=True, ep=None):
    if plein:
        return '<circle cx="%s" cy="%s" r="%s"/>' % (_d(x), _d(y), _d(r))
    return '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="currentColor" stroke-width="%s"/>' % (
        _d(x), _d(y), _d(r), _d(ep))


def trait(d, ep, extra=""):
    return ('<path d="%s" fill="none" stroke="currentColor" stroke-width="%s" stroke-linecap="round" '
            'stroke-linejoin="round"%s/>' % (d, _d(ep), extra))


def main():
    sil = silhouette()
    gauche = sil[sil[:, 0] <= 501]
    F = distances(gauche)
    F = np.where(interieur(sil), F, -F)

    couches = []

    def couche(nom, ton, miroir, svg):
        if svg:
            couches.append(dict(nom=nom, ton=ton, miroir=miroir, svg="".join(svg)))

    # 1. le pourtour
    couche("cordon", "encre", False, [
        '<clipPath id="ec"><path d="%s"/></clipPath>' % PIQUE,
        '<path d="%s" fill="none" stroke="currentColor" stroke-width="%s" stroke-linejoin="round" '
        'clip-path="url(#ec)"/>' % (PIQUE, _d(2 * CORDON))])

    rang = niveau(F, RANG)
    s = abscisses(rang)
    pas_perle, r_perle = 10.4, 3.5
    perles, t = [], s[-1] - pas_perle
    while t > 0:
        q = point_a(rang, s, t)
        if 500 - q[0] > r_perle + 1:
            perles.append(cercle(q[0], q[1], r_perle))
        t -= pas_perle
    couche("perles", "or", True, perles)
    couche("perle-axe", "or", False, [cercle(500, rang[-1][1], r_perle)])

    couche("lisere", "encre", True, [trait(lisse(regulier(niveau(F, LISERE), 9.0)), 2.6)])

    # 2. l'ossature
    mx, my = CENTRE
    e = 92 / 1070.0
    axe = [trait("M%s,%sL%s,%s" % (_d(a[0]), _d(a[1]), _d(b[0]), _d(b[1])), 2 * AXE_DEMI) for a, b in AXE]
    axe.append(cercle(500, AXE[0][0][1] - 4, 6))
    axe.append(cercle(mx, my, R_MED - 3, False, 6))
    axe.append(cercle(mx, my, 62.5, False, 2.4))
    couche("axe", "encre", False, axe)
    n_med = 46
    couche("grains-medaillon", "or", False, [
        cercle(mx + 70.5 * math.cos(2 * math.pi * (k + 0.5) / n_med), my + 70.5 * math.sin(2 * math.pi * (k + 0.5) / n_med), 3.2)
        for k in range(n_med)])
    couche("pique", "or", False, [
        '<path d="%s" transform="translate(%s %s) scale(%s)"/>' % (PIQUE, _d(mx - 500 * e), _d(my - 3 - 605 * e), "%.4f" % e)])

    volutes = []
    for pts, demi, bouts in ossature(False):
        volutes.append(trait(lisse(pts), 2 * demi))
        volutes += [cercle(b[0], b[1], demi + 2.6) for b in bouts]
    couche("volutes", "encre", True, volutes)

    # 3. la dentelle : champ du plus grand cercle admissible en chaque maille
    D = F - BORD - JEU
    D = np.minimum(D, np.where(X < 499.9, 500 - X - JEU / 2, 1e9))
    D = np.minimum(D, np.hypot(X - mx, Y - my) - R_MED - JEU)
    fixes = []                                   # (x, y, garde) des obstacles posés à la main
    for pts, demi, bouts in ossature(True):
        D = np.minimum(D, distances(pts) - demi - JEU)
        fixes += [(q[0], q[1], demi) for q in pts]
        for b in bouts:
            D = np.minimum(D, np.hypot(X - b[0], Y - b[1]) - (demi + 2.6) - JEU)
            fixes.append((b[0], b[1], demi + 2.6))
    for a, b in AXE:
        n = int(abs(b[1] - a[1]))
        seg = [(500.0, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]
        D = np.minimum(D, distances(seg) - AXE_DEMI - JEU)
        fixes += [(q[0], q[1], AXE_DEMI) for q in seg]
    bouton = (500.0, AXE[0][0][1] - 4)
    D = np.minimum(D, np.hypot(X - bouton[0], Y - bouton[1]) - 6 - JEU)
    fixes.append((bouton[0], bouton[1], 6.0))
    fixes.append((mx, my, R_MED))
    fixes = np.array(fixes)
    gy, gx = np.gradient(F, PAS)

    cercles = []
    while True:
        k = int(np.argmax(D))
        r = float(D.flat[k])
        if r < R_MIN:
            break
        i, j = divmod(k, D.shape[1])
        x, y = float(XS[j]), float(YS[i])
        r = min(r, R_MAX)
        # d'où part la vrille : le plus proche voisin
        cand = [(float(F[i, j]) - BORD, math.degrees(math.atan2(-gy[i, j], -gx[i, j])))]
        if x < 499.9:
            cand.append((500 - x, 0.0))
        d = np.hypot(fixes[:, 0] - x, fixes[:, 1] - y) - fixes[:, 2]
        m = int(np.argmin(d))
        cand.append((float(d[m]), math.degrees(math.atan2(fixes[m, 1] - y, fixes[m, 0] - x))))
        if cercles:
            C = np.array([(c[0], c[1], c[2]) for c in cercles])
            d = np.hypot(C[:, 0] - x, C[:, 1] - y) - C[:, 2]
            m = int(np.argmin(d))
            cand.append((float(d[m]), math.degrees(math.atan2(C[m, 1] - y, C[m, 0] - x))))
        cercles.append((x, y, r, min(cand)[1]))
        D = np.minimum(D, np.hypot(X - x, Y - y) - r - JEU)

    # du cœur vers les bords : c'est l'ordre d'apparition
    NB = 8
    rangs = [dict(fils=[], grains=[], axe=[]) for _ in range(NB)]
    portee = max(math.hypot(c[0] - mx, c[1] - my) for c in cercles)
    for n, (x, y, r, a) in enumerate(cercles):
        g = rangs[min(NB - 1, int(NB * math.hypot(x - mx, y - my) / (portee + 1)))]
        if x > 499.9:                             # sur l'axe : un motif symétrique
            if r >= R_OEILLET:
                g["axe"].append(cercle(x, y, r - FIL / 2, False, FIL))
                g["axe"].append(cercle(x, y, max(1.6, r * 0.3)))
            else:
                g["axe"].append(cercle(x, y, r))
        elif r >= R_SPIRALE:
            ro, ri = r - FIL / 2, 3.2
            pas = min(PASFIN, (ro - ri) / 1.2)
            g["fils"].append(trait(lisse(spirale((x, y), ro, a, 1 if n % 2 else -1, pas, ri, 45.0)), FIL))
            g["grains"].append(cercle(x, y, 2.5))
        elif r >= R_OEILLET:
            g["fils"].append(cercle(x, y, r - 1.3, False, 2.6))
            g["grains"].append(cercle(x, y, max(1.6, r * 0.3)))
        else:
            g["grains"].append(cercle(x, y, r))
    for n, g in enumerate(rangs):
        couche("dentelle-%d" % n, "encre", True, g["fils"])
        couche("grains-%d" % n, "or", True, g["grains"])
        couche("axe-%d" % n, "or", False, g["axe"])

    json.dump(dict(boite=[1000, 1200], silhouette=PIQUE, couches=couches), sys.stdout, ensure_ascii=False,
              separators=(",", ":"))
    sys.stdout.write("\n")
    sys.stderr.write("%d cercles, %d couches, %.0f Ko\n" % (
        len(cercles), len(couches), sum(len(c["svg"]) for c in couches) / 1024.0))


if __name__ == "__main__":
    main()
