#!/usr/bin/env python3
"""Vérifications de build-stats.py, exécutées avant chaque génération.

Un échec ici fait échouer le workflow, donc les cartes en ligne restent
inchangées. C'est voulu : mieux vaut des chiffres figés d'une heure que des
chiffres faux. Chaque test correspond à une panne réellement survenue.
"""
import importlib.util
import os
import sys
from datetime import date, timedelta

ICI = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bs", os.path.join(ICI, "build-stats.py"))
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)

echecs = []


def verifie(nom, condition, detail=""):
    print(("  ok   " if condition else "  ÉCHEC ") + nom + (" — " + detail if detail else ""))
    if not condition:
        echecs.append(nom)


# --- 1. Lecture de la grille du profil ---------------------------------------
# Panne survenue : le compte était cherché n'importe où dans l'infobulle, donc
# « No contributions on July 11th » rendait 11. Toutes les journées vides
# devenaient actives : total doublé, série continue depuis le 1er janvier.
HTML = """
<td class="ContributionCalendar-day" data-date="2026-07-10" data-level="2" data-count="7"></td>
<td class="ContributionCalendar-day" data-date="2026-07-11" data-level="0" id="c-11"></td>
<td class="ContributionCalendar-day" data-date="2026-07-12" data-level="3" id="c-12"></td>
<td class="ContributionCalendar-day" data-date="2026-12-29" data-level="0" id="c-29"></td>
<td class="ContributionCalendar-day" data-date="2026-06-15" data-level="4" id="c-15"></td>
<td class="ContributionCalendar-day" data-date="2026-03-02" data-level="1" id="c-fr"></td>
<tool-tip for="c-11">No contributions on July 11th.</tool-tip>
<tool-tip for="c-12">23 contributions on July 12th.</tool-tip>
<tool-tip for="c-29">No contributions on December 29th.</tool-tip>
<tool-tip for="c-15">254 contributions on June 15th.</tool-tip>
<tool-tip for="c-fr">1 042 contributions on March 2nd.</tool-tip>
"""

print("Lecture de la grille du profil")
_get_reel = bs._get
bs._get = lambda *a, **k: HTML
lu = bs.via_page(date(2026, 1, 1), date(2026, 12, 31))
bs._get = _get_reel
attendu = {"2026-07-10": 7, "2026-07-11": 0, "2026-07-12": 23,
           "2026-12-29": 0, "2026-06-15": 254, "2026-03-02": 1042}
for jour, valeur in attendu.items():
    verifie("%s = %s" % (jour, valeur), lu.get(jour) == valeur, "lu : %s" % lu.get(jour))

# --- 2. Garde-fou entre les deux sources -------------------------------------
print("Garde-fou entre la grille du profil et GraphQL")
fin = date.today()
sain = {(fin - timedelta(days=i)).isoformat(): (5 if i % 3 else 0) for i in range(60)}
casse = {k: (v if v else int(k[-2:])) for k, v in sain.items()}
decale = dict(sain)
a, b = sorted(sain)[10], sorted(sain)[11]
decale[a], decale[b] = sain[b], sain[a]

_cree, _page, _gql = bs.compte_cree_le, bs.via_page, bs.via_graphql
bs.compte_cree_le = lambda: fin - timedelta(days=59)
bs.via_graphql = lambda d, f: dict(sain)

bs.via_page = lambda d, f: dict(casse)
verifie("une lecture aberrante est rejetée au profit de GraphQL",
        sum(bs.calendrier().values()) == sum(sain.values()))

bs.via_page = lambda d, f: dict(decale)
verifie("un simple décalage de fuseau est accepté",
        sum(bs.calendrier().values()) == sum(decale.values()))
bs.compte_cree_le, bs.via_page, bs.via_graphql = _cree, _page, _gql

# --- 3. Calcul des séries ----------------------------------------------------
# La série en cours ne doit pas être cassée par une journée d'aujourd'hui encore
# vide : elle n'est pas finie.
print("Calcul des séries")
j = {(fin - timedelta(days=i)).isoformat(): 3 for i in range(1, 6)}
j[fin.isoformat()] = 0
courante, longue = bs.series(j)
verifie("aujourd'hui encore vide ne casse pas la série", courante[0] == 5,
        "série calculée : %s" % courante[0])

j2 = {(fin - timedelta(days=i)).isoformat(): 3 for i in range(0, 4)}
j2[(fin - timedelta(days=4)).isoformat()] = 0
j2.update({(fin - timedelta(days=i)).isoformat(): 3 for i in range(5, 15)})
courante2, longue2 = bs.series(j2)
verifie("la série en cours s'arrête au premier trou", courante2[0] == 4,
        "série calculée : %s" % courante2[0])
verifie("la plus longue série est bien la plus longue", longue2[0] == 10,
        "série calculée : %s" % longue2[0])

# --- 4. Les cartes sortent en SVG valide -------------------------------------
print("Génération des cartes")
import xml.dom.minidom
r = bs.stats(bs.calendrier_demo())
for nom, rendu in bs.CARTES:
    for pal in (bs.DARK, bs.LIGHT):
        try:
            xml.dom.minidom.parseString(rendu(r, pal))
            ok, detail = True, ""
        except Exception as e:
            ok, detail = False, str(e)
        verifie("%s : SVG valide" % nom, ok, detail)

print()
if echecs:
    print("%d vérification(s) en échec : %s" % (len(echecs), ", ".join(echecs)))
    sys.exit(1)
print("Toutes les vérifications passent.")
