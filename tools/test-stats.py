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

# Panne survenue : la grille publique servie par GitHub est restée figée plus de
# deux heures sur la journée en cours (81 contributions) pendant que GraphQL en
# comptait 93. Les deux sources ne peuvent différer que par un décalage de
# fuseau, qui ne change pas un total, ou par un retard de publication : un total
# supérieur désigne donc la source la plus avancée, et c'est elle qui doit
# gagner. Sinon le chiffre du jour ne bouge plus, quelle que soit la cadence.
actif = (fin - timedelta(days=1)).isoformat()
avance = dict(sain)
avance[actif] = sain[actif] + 12
bs.via_page = lambda d, f: dict(sain)
bs.via_graphql = lambda d, f: dict(avance)
verifie("une grille en retard cède la place à GraphQL",
        sum(bs.calendrier().values()) == sum(avance.values()),
        "total retenu : %d" % sum(bs.calendrier().values()))

# ... sans pour autant jeter la journée que GraphQL ne couvre pas encore : à
# 23 h UTC le lendemain a déjà commencé dans le fuseau du compte, la grille le
# connaît, GraphQL non. La jeter amputerait la série d'un jour.
demain = (fin + timedelta(days=1)).isoformat()
grille_avec_demain = dict(sain)
grille_avec_demain[demain] = 7
bs.via_page = lambda d, f: dict(grille_avec_demain)
bs.via_graphql = lambda d, f: dict(avance)
obtenu_demain = bs.calendrier().get(demain)
verifie("la journée que GraphQL ne couvre pas encore est conservée",
        obtenu_demain == 7, "valeur : %s" % obtenu_demain)
bs.compte_cree_le, bs.via_page, bs.via_graphql = _cree, _page, _gql

# --- 2 bis. La journée en avance sur l'UTC ne doit pas être jetée -------------
# Panne survenue : la grille du profil contenait bien le 11 août (fuseau de
# Paris), mais le filtre final coupait à « aujourd'hui en UTC » et la supprimait
# juste après l'avoir récupérée.
print("Conservation de la journée en avance sur l'UTC")
avec_demain = dict(sain)
avec_demain[(fin + timedelta(days=1)).isoformat()] = 9
_cree, _page, _gql = bs.compte_cree_le, bs.via_page, bs.via_graphql
bs.compte_cree_le = lambda: fin - timedelta(days=59)
bs.via_page = lambda d, f: dict(avec_demain)
bs.via_graphql = lambda d, f: dict(avec_demain)
garde = bs.calendrier()
verifie("la journée du lendemain UTC est conservée",
        garde.get((fin + timedelta(days=1)).isoformat()) == 9,
        "valeur : %s" % garde.get((fin + timedelta(days=1)).isoformat()))
bs.compte_cree_le, bs.via_page, bs.via_graphql = _cree, _page, _gql

# --- 2 ter. Cache des années révolues -----------------------------------------
# Le mode boucle recalcule toutes les deux minutes. Les années closes ne
# changent plus : les relire à chaque tour quadruplerait les appels à GitHub
# sans rien apprendre. Mais l'année en cours, elle, doit être relue à chaque
# fois — un cache trop gourmand figerait justement le chiffre du jour, soit
# exactement le défaut qu'on cherche à corriger.
print("Cache des années révolues")
import tempfile

appels = []
_cree, _page, _gql, _cache_dir = bs.compte_cree_le, bs.via_page, bs.via_graphql, bs.CACHE
with tempfile.TemporaryDirectory() as tmp:
    bs.CACHE = tmp
    bs.compte_cree_le = lambda: date(fin.year - 1, 3, 1)

    def fausse_source(d, f):
        appels.append(d.year)
        return {(d + timedelta(days=i)).isoformat(): 2 for i in range((f - d).days + 1)}

    bs.via_page = bs.via_graphql = fausse_source
    premier = bs.calendrier()
    annees_1 = sorted(set(appels))
    appels.clear()
    second = bs.calendrier()
    annees_2 = sorted(set(appels))

verifie("le premier passage lit les deux années", annees_1 == [fin.year - 1, fin.year],
        "années lues : %s" % annees_1)
verifie("le second ne relit que l'année en cours", annees_2 == [fin.year],
        "années lues : %s" % annees_2)
verifie("le cache ne change aucun chiffre", premier == second)
bs.compte_cree_le, bs.via_page, bs.via_graphql, bs.CACHE = _cree, _page, _gql, _cache_dir

# --- 3. Calcul des séries ----------------------------------------------------
# La série en cours ne doit pas être cassée par une journée d'aujourd'hui encore
# vide : elle n'est pas finie.
print("Calcul des séries")
j = {(fin - timedelta(days=i)).isoformat(): 3 for i in range(1, 6)}
j[fin.isoformat()] = 0
courante, longue = bs.series(j)
verifie("aujourd'hui encore vide ne casse pas la série", courante[0] == 5,
        "série calculée : %s" % courante[0])

# Panne survenue : le runner vit en UTC, le calendrier du profil dans le fuseau
# du compte. À 23 h UTC il est déjà le lendemain à Paris ; partir de « aujourd'hui
# en UTC » ignorait cette journée et amputait la série d'un jour.
demain = (fin + timedelta(days=1)).isoformat()
javance = {(fin - timedelta(days=i)).isoformat(): 3 for i in range(0, 5)}
javance[demain] = 4
verifie("une journée en avance sur l'UTC (fuseau du compte) est comptée",
        bs.series(javance)[0][0] == 6, "série calculée : %s" % bs.series(javance)[0][0])

# ... mais une série réellement interrompue doit bien retomber à zéro
vieux = {(fin - timedelta(days=i)).isoformat(): 3 for i in range(5, 12)}
verifie("une série interrompue depuis plus d'un jour retombe à zéro",
        bs.series(vieux)[0][0] == 0, "série calculée : %s" % bs.series(vieux)[0][0])

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
