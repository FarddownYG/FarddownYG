#!/usr/bin/env python3
"""Vérifications de build-stats.py, exécutées avant chaque génération.

Un échec ici fait échouer le workflow, donc les cartes en ligne restent
inchangées. C'est voulu : mieux vaut des chiffres figés d'une heure que des
chiffres faux. Chaque test correspond à une panne réellement survenue.
"""
import importlib.util
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

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

# --- 2 quater. Année en cours illisible ---------------------------------------
# Panne relevée en relecture : les deux sources échouent sur l'année en cours
# alors que l'année close vient du cache. `jours` n'était pas vide, le calcul
# continuait sur l'année passée seule — total amputé, et un skyline arrêté au
# 31 décembre présenté comme « les 12 derniers mois ». Rien ne doit être publié.
print("Année en cours illisible")
_cree, _page, _gql, _cache_dir = bs.compte_cree_le, bs.via_page, bs.via_graphql, bs.CACHE
panne = {"active": False}


def source_fragile(d, f):
    if panne["active"] and d.year == fin.year:
        raise OSError("502 Bad Gateway")
    return {(d + timedelta(days=i)).isoformat(): 2 for i in range((f - d).days + 1)}


with tempfile.TemporaryDirectory() as tmp:
    bs.CACHE = tmp
    bs.compte_cree_le = lambda: date(fin.year - 1, 3, 1)
    bs.via_page = bs.via_graphql = source_fragile
    bs.calendrier()                       # remplit le cache de l'année close
    panne["active"] = True
    try:
        bs.calendrier()
        refuse = False
    except SystemExit:
        refuse = True
verifie("une année en cours illisible arrête tout, même avec le cache", refuse)
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
import hashlib
import re
import subprocess
import xml.dom.minidom

SOMBRE, CLAIR = bs.PALETTES
NNBSP = " "


def chiffres(svg):
    """Les grands chiffres d'une carte, relus dans le dessin lui-même.

    Le texte est tracé glyphe par glyphe : l'identifiant de chaque glyphe porte
    le code du caractère. Les chiffres animés (classe « n ») sont les valeurs."""
    lus = []
    for groupe in re.findall(r'<g transform="translate[^>]*>((?:<use [^>]*/>)+)</g>', svg):
        if 'class="n"' in groupe:
            lus.append("".join(chr(int(h, 16)) for h in re.findall(r'href="#[a-z]([0-9a-f]+)"', groupe)))
    return lus


def nu(n):
    return bs.fr(n).replace(NNBSP, "")


r = bs.stats(bs.calendrier_demo())
sorties = dict(bs.rendus(r))
attendues = {"%s%s-%s.svg" % (n, m, t)
             for n in ("skyline", "bord") for m in ("", "-m") for t in ("dark", "light")}
verifie("deux cartes, deux mises en page, deux thèmes", attendues <= set(sorties),
        "manquent : %s" % sorted(attendues - set(sorties)))
for nom, svg in sorted(sorties.items()):
    try:
        xml.dom.minidom.parseString(svg)
        ok, detail = True, ""
    except Exception as e:
        ok, detail = False, str(e)
    verifie("%s : SVG valide" % nom, ok, detail)
    # Un README montre ses SVG dans une balise <img> : ni police ni ressource
    # externe n'y sont chargées. Un <text> y retomberait sur la police de
    # l'appareil, et toute la mise en page calée au pixel partirait de travers.
    verifie("%s : ni police, ni ressource externe" % nom,
            "<text" not in svg and "font-family" not in svg and "url(http" not in svg
            and not re.search(r'(?:href|src)="(?!#)', svg))
    if nom.startswith(("skyline", "bord")):
        verifie("%s : largeur de dessin" % nom, 'viewBox="0 0 %d ' % (450 if "-m-" in nom else 900) in svg)
    verifie("%s : titre et description pour les lecteurs d'écran" % nom,
            'role="img"' in svg and "<title" in svg and "<desc" in svg)
    verifie("%s : poids raisonnable" % nom, len(svg.encode("utf-8")) < 220 * 1024,
            "%d Ko" % (len(svg.encode("utf-8")) // 1024))

# --- 4 bis. Typographie -------------------------------------------------------
# Le texte est composé en tracés à partir d'un atlas de glyphes. Deux pannes
# possibles : une largeur fausse (tout ce qui est calé à droite se décale) et un
# caractère absent de l'atlas (un blanc muet à la place d'une lettre).
print("Typographie")
typo = bs.Feuille(10, 10, SOMBRE, "essai").t
verifie("le mono a une chasse fixe", abs(typo.largeur("mono", "0123", 10) - typo.largeur("mono", "mmmm", 10)) < 1e-6
        and typo.largeur("mono", "0123", 10) > 20)
verifie("les chiffres tabulaires occupent tous la même case",
        abs(typo.largeur("titre", "1111", 40, tab=True) - typo.largeur("titre", "0000", 40, tab=True)) < 1e-6)
try:
    typo.largeur("mono", "→", 10)
    absent = False
except KeyError:
    absent = True
verifie("un caractère absent de l'atlas arrête le rendu au lieu de laisser un blanc", absent)

# --- 5. Skyline --------------------------------------------------------------
print("Skyline")

# La grille s'arrête sur la dernière journée connue, y compris celle déjà
# commencée dans le fuseau du compte, et commence un lundi.
j5 = {(fin - timedelta(days=i)).isoformat(): (i % 4) for i in range(400)}
j5[(fin + timedelta(days=1)).isoformat()] = 2
cases = bs._grille(j5)
verifie("la grille finit sur la dernière journée connue",
        cases[-1][0] == fin + timedelta(days=1), "fin : %s" % cases[-1][0])
verifie("la grille commence un lundi", cases[0][0].weekday() == 0,
        "début : %s" % cases[0][0])
verifie("la grille couvre un an", 365 <= len(cases) <= 371, "%d cases" % len(cases))

# La page du profil liste déjà le lendemain, à zéro, quand le fuseau du compte
# a de l'avance sur l'UTC. Tant qu'il est vide, ce n'est pas une journée à
# montrer : une dalle « demain » au bout de la frise se lit comme un trou.
j5[(fin + timedelta(days=1)).isoformat()] = 0
verifie("un lendemain encore vide n'est pas dessiné", bs._grille(j5)[-1][0] == fin,
        "fin : %s" % bs._grille(j5)[-1][0])

# Hauteurs : la journée record ne doit pas aplatir le reste. Avec une échelle
# linéaire, une journée ordinaire à 15 ferait 5 % de la tour record à 322 ;
# c'est ce qui avait rendu illisible le premier graphique d'activité.
verifie("une journée vide est une dalle", bs._hauteur(0, 322) == bs.SKY_DALLE)
rapport = bs._hauteur(15, 322) / bs._hauteur(322, 322)
verifie("une journée ordinaire reste lisible face au record", rapport >= 0.25,
        "rapport : %.2f" % rapport)

# Niveaux : une seule journée hors norme ne renvoie pas les autres au niveau 1.
actifs = sorted([10] * 99 + [1000])
seuil = actifs[int(0.95 * (len(actifs) - 1))]
verifie("une journée hors norme n'écrase pas les niveaux", bs._niveau(10, seuil) == 4,
        "niveau : %d" % bs._niveau(10, seuil))
verifie("une journée vide est au niveau 0", bs._niveau(0, seuil) == 0)

# Meilleure semaine : sept jours glissants, même à cheval sur deux semaines
# civiles. Le bloc fort va du jeudi au mercredi suivant.
jeudi = fin - timedelta(days=(fin.weekday() - 3) % 7 + 21)
j6 = {(fin - timedelta(days=i)).isoformat(): 1 for i in range(60)}
for i in range(7):
    j6[(jeudi + timedelta(days=i)).isoformat()] = 50
sem = bs.stats(j6)["semaine"]
verifie("la meilleure semaine est la fenêtre glissante la plus forte",
        sem == (350, jeudi.isoformat(), (jeudi + timedelta(days=6)).isoformat()),
        "obtenu : %s" % (sem,))
verifie("les trente derniers jours sont comptés à part", bs.stats(j6)["trente"] == sum(
    v for k, v in j6.items() if k > (fin - timedelta(days=30)).isoformat()),
    "obtenu : %s" % bs.stats(j6)["trente"])

# La grille ne recule jamais sous aujourd'hui, même si la dernière journée
# manque dans les données.
vieilles = {(fin - timedelta(days=i)).isoformat(): 1 for i in range(10, 400)}
verifie("la grille ne recule pas sous aujourd'hui",
        bs._grille(vieilles)[-1][0] == fin, "fin : %s" % bs._grille(vieilles)[-1][0])

# Périodes : l'année apparaît dès qu'elle diffère de celle de la dernière
# journée connue. Sans elle, une série de l'an passé se lirait dans la frise.
verifie("une période de l'année en cours reste courte",
        bs.periode("2026-07-12", "2026-08-13", "2026-10-07") == "12 juil. – 13 août")
verifie("une période d'une autre année porte son année",
        bs.periode("2026-07-12", "2026-08-13", "2027-08-20") == "12 juil. – 13 août 2026")
verifie("une période à cheval sur deux années les nomme",
        bs.periode("2026-12-28", "2027-01-03", "2027-01-05") == "28 déc. 2026 – 3 janv.")

# --- la carte elle-même ---
# Rendu de référence : données de démonstration, date et heure figées.
_date = bs.date
bs.date = type("D", (date,), {"today": classmethod(lambda c: date(2026, 10, 7))})
r = bs.stats(bs.calendrier_demo())
r["calcule"] = datetime(2026, 10, 7, 8, 0, tzinfo=timezone.utc)
svg = bs.carte_skyline(r, SOMBRE)
svg_mobile = bs.carte_skyline(r, SOMBRE, True)
svg_bord = bs.carte_bord(r, SOMBRE)
cases = bs._grille(r["jours"])
bs.date = _date

style = re.search(r"<style>(.*?)</style>", svg).group(1)
verifie("l'horodatage est isolé dans son groupe (l'empreinte en dépend)",
        len(re.findall(r'<g[^>]*\bid="maj"[^>]*>(?:<use [^>]*/>)+</g>', svg)) == 1)

# Animation. Une image clé cassée aplatit toutes les barres pour tout visiteur
# dont le navigateur anime : c'est l'état final qui serait affiché.
verifie("image clé des faces latérales exacte",
        re.search(r"@keyframes m\{from\{transform:scale\(1,[\d.]+\)\}"
                  r"to\{transform:scale\(1,var\(--h\)\)\}\}", style) is not None)
verifie("image clé du dessus exacte",
        "@keyframes u{from{transform:translate(0,var(--d))}to{transform:translate(0,0)}}" in style)
verifie("l'animation part après son délai et garde son état final",
        re.search(r"\.m,\.u\{animation:[\d.]+s cubic-bezier\([^)]*\) var\(--t\) both\}", style)
        is not None)
# Placée avant la règle d'animation, la règle du mouvement réduit serait
# écrasée par elle : la présence du texte ne suffit pas, l'ordre compte.
i_anim = max(style.find(".m,.u{animation:"), style.find(".n{animation:"))
i_reduit = style.find("@media (prefers-reduced-motion:reduce){.m,.u,.n{animation:none}}")
verifie("le mouvement réduit vient après les animations et les coupe",
        0 <= min(style.find(".m,.u{animation:"), style.find(".n{animation:")) and i_anim < i_reduit,
        "positions : animation %d, mouvement réduit %d" % (i_anim, i_reduit))

barres = re.findall(r'<g style="--h:([\d.]+);--d:(-?[\d.]+)px;--t:([\d.]+)s">(.*?)</g>'
                    r'(?=\n|$)', svg, re.M)
coherent = barres and all(
    re.findall(r'scale\(1,([\d.]+)\)', corps) == [h, h] for h, _, _, corps in barres)
verifie("chaque barre porte sa hauteur finale en attribut", bool(coherent),
        "%d barres" % len(barres))
nb_actifs = sum(1 for _, n, _, _ in cases if n > 0)
verifie("une barre animée par journée active", len(barres) == nb_actifs,
        "%d barres pour %d journées actives" % (len(barres), nb_actifs))
verifie("le dessus descend vers la dalle au départ", all(float(d) > 0 for _, d, _, _ in barres))
delais = [float(t) for _, _, t, _ in barres]
verifie("la vague part des semaines anciennes", delais[0] < delais[-1],
        "premier délai %.2f s, dernier %.2f s" % (delais[0], delais[-1]))

# Géométrie. Face droite cisaillée vers le haut à gauche, face gauche vers le
# bas à droite : inverser un signe retourne le pied de toutes les barres.
skews = re.findall(r'skewY\((-?[\d.]+)\)"><rect class="([dg])\d m"', svg)
verifie("face droite cisaillée en négatif, face gauche en positif",
        skews and all((float(a) < 0) == (c == "d") for a, c in skews),
        "%d faces" % len(skews))


def luminance(hexa):
    r_, g_, b_ = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_


teinte = dict(re.findall(r"\.([dgt]\d)\{fill:(#[0-9A-F]{6})\}", style))
verifie("ombrage : dessus plus clair que la gauche, plus clair que la droite",
        all(luminance(teinte["t%d" % k]) > luminance(teinte["g%d" % k]) > luminance(teinte["d%d" % k])
            for k in range(1, 5)))

# Ordre du peintre. À profondeur croissante, la base d'une case descend à
# l'écran : la suite des bases doit donc croître dans l'ordre du document.
# Base d'une dalle : y du <use> ; d'une barre : premier sommet du dessus + h.
bases = []
for m in re.finditer(r'<use href="#v" x="[\d.]+" y="([\d.]+)"/>'
                     r'|<g style="--h:([\d.]+);[^>]*>.*?<polygon class="t\d u" points="[\d.]+,([\d.]+)',
                     svg):
    bases.append(float(m.group(1)) if m.group(1) else float(m.group(3)) + float(m.group(2)))
verifie("ordre du peintre : du fond vers l'avant",
        len(bases) == len(cases) and all(b >= a - 0.25 for a, b in zip(bases, bases[1:])),
        "%d cases lues sur %d" % (len(bases), len(cases)))
verifie("une dalle réutilisée par journée vide",
        '<g id="v">' in svg and svg.count('<use href="#v"') == len(cases) - nb_actifs)
verifie("les mois sont étiquetés", svg.count('<g class="mois">') >= 10,
        "%d étiquettes" % svg.count('<g class="mois">'))

# Les quatre chiffres, chacun à sa place — relus dans le dessin, pas dans la
# description : c'est le dessin que voit le visiteur.
attendus = [nu(r["total"]), nu(r["record"]), nu(r["longue"][0]), nu(r["courante"][0])]
verifie("total, record, plus longue série, série actuelle dans cet ordre",
        chiffres(svg) == attendus, "lus : %s" % chiffres(svg))
verifie("les mêmes chiffres sur mobile", chiffres(svg_mobile) == attendus, "lus : %s" % chiffres(svg_mobile))
desc = re.search(r"<desc[^>]*>(.*?)</desc>", svg).group(1)
verifie("la description les répète pour les lecteurs d'écran",
        all(bs.fr(v) in desc for v in (r["total"], r["record"], r["longue"][0], r["courante"][0])), desc)


def emprises(svg_):
    """Boîte à l'écran de chaque barre : (x0, y0, x1, y1)."""
    out = []
    for h, corps in re.findall(r'<g style="--h:([\d.]+);[^>]*>(.*?)</g>(?=\n|$)', svg_, re.M):
        pts = [tuple(map(float, q.split(","))) for q in
               re.search(r'class="t\d u" points="([^"]+)"', corps).group(1).split()]
        out.append((min(q[0] for q in pts), min(q[1] for q in pts),
                    max(q[0] for q in pts), max(q[1] for q in pts) + float(h)))
    return out


# Coins réservés. Cas relevé en relecture : un record à cinq chiffres un lundi
# d'été posait sa tour sous les chiffres du coin haut-droit.
_date = bs.date
bs.date = type("D", (date,), {"today": classmethod(lambda c: date(2026, 10, 7))})
aj = date(2026, 10, 7)
jc = {(aj - timedelta(days=i)).isoformat(): (8 if i < 270 and i % 3 else 0) for i in range(300)}
lundi = aj - timedelta(days=16 * 7 + aj.weekday())
jc[lundi.isoformat()] = 12345
rc = bs.stats(jc)
rc["calcule"] = datetime(2026, 10, 7, 8, 0, tzinfo=timezone.utc)
svg_coin = bs.carte_skyline(rc, SOMBRE)
svg_coin_mobile = bs.carte_skyline(rc, SOMBRE, True)
zones = bs._blocs_skyline(bs.Feuille(900, 600, SOMBRE, "essai"), rc, False)[1]
bs.date = _date
heurts = sum(1 for b in emprises(svg_coin) for z in zones
             if b[0] < z[2] and b[2] > z[0] and b[1] < z[3] and b[3] > z[1])
verifie("aucune barre sous les quatre chiffres, même avec un record à cinq chiffres",
        len(zones) == 4 and heurts == 0, "%d recouvrement(s)" % heurts)
X0, Y0, X1, Y1 = bs.SKY_SCENE_MOBILE
verifie("sur mobile, la scène reste dans sa zone, au-dessus des chiffres",
        all(X0 - 1 <= b[0] and b[2] <= X1 + 1 and Y0 - 1 <= b[1] and b[3] <= Y1 + 1
            for b in emprises(svg_coin_mobile)))

# --- 6. Tableau de bord --------------------------------------------------------
print("Tableau de bord")
style_b = re.search(r"<style>(.*?)</style>", svg_bord).group(1)
# Règle de toute la maison : chaque élément porte son état final en attribut,
# l'animation part d'ailleurs et y revient. Un moteur qui n'anime pas (ou un
# visiteur en mouvement réduit) voit donc la bonne valeur, jamais l'aiguille
# au repos.
aiguilles = re.findall(r'<g class="ag" transform="rotate\((-?[\d.]+)\)" style="--a:(-?[\d.]+)deg;', svg_bord)
verifie("deux aiguilles, posées sur leur valeur", len(aiguilles) == 2 and all(a == b for a, b in aiguilles),
        "lues : %s" % aiguilles)
verifie("le balayage d'allumage finit sur la valeur", "100%{transform:rotate(var(--a))}" in style_b)
debuts = [style_b.find(".%s{animation:" % c) for c in ("n", "ag", "an", "od")]
i_reduit = style_b.find("@media (prefers-reduced-motion:reduce){.n,.ag,.an,.od{animation:none}}")
verifie("le mouvement réduit vient après les quatre animations", min(debuts) >= 0 and max(debuts) < i_reduit,
        "positions : %s, mouvement réduit %d" % (debuts, i_reduit))
desc_b = re.search(r"<desc[^>]*>(.*?)</desc>", svg_bord).group(1)
verifie("la description porte tous les chiffres du tableau",
        all(bs.fr(v) in desc_b for v in (r["total"], r["semaine"][0], r["mois_total"], r["trente"], r["actifs"])),
        desc_b)
# Une aiguille ne sort jamais de son cadran, quelle que soit la valeur.
for valeur in (0, 1, 7, 99, 100, 101, 529, 9999, 123456):
    pas_, intervalles = bs._echelle(valeur)
    verifie("échelle pour %d : la valeur tient dans le cadran" % valeur,
            pas_ * intervalles >= valeur and 6 <= intervalles <= 10,
            "pas %s × %s intervalles" % (pas_, intervalles))

# Panne relevée en essai de charge : au-delà de 999 999, le compteur à six
# rouleaux perdait son chiffre de tête et affichait 400 000 pour 4 400 000.
feuille = bs.Feuille(900, 440, SOMBRE, "essai")
rouleaux = "".join(bs._compteur(feuille, 450, 260, 4400000, 6, 30, 40))
finals = re.findall(r'<g transform="translate\(0 [\d.]+\) scale[^>]*>(?:<use [^>]*/>)*?<use href="#t([0-9a-f]+)"'
                    r'(?: x="[\d.]+")?/></g>', rouleaux)
verifie("le compteur garde tous ses chiffres au-delà du million",
        "".join(chr(int(h, 16)) for h in finals) == "4400000", "lus : %s" % finals)

# --- 7. Empreinte ---------------------------------------------------------------
# Deux calculs des mêmes données à des heures différentes doivent donner la
# même empreinte, sinon la boucle republie toutes les deux minutes ; et un
# chiffre qui bouge doit la changer, sinon elle ne republie jamais.
print("Empreinte")


def empreinte_de(resultat):
    with tempfile.TemporaryDirectory() as tmp:
        for nom, contenu in bs.rendus(resultat):
            with open(os.path.join(tmp, nom), "w", encoding="utf-8") as fichier:
                fichier.write(contenu)
        return subprocess.run([sys.executable, os.path.join(ICI, "empreinte.py"), tmp],
                              capture_output=True, text=True).stdout.strip()


empreintes = []
for jour_, heure, minute in ((7, 8, 17), (7, 9, 48), (8, 23, 0)):
    r["calcule"] = datetime(2026, 10, jour_, heure, minute, tzinfo=timezone.utc)
    empreintes.append(empreinte_de(r))
verifie("l'empreinte ne dépend que des chiffres, pas de l'heure du calcul",
        bool(empreintes[0]) and len(set(empreintes)) == 1, "empreintes : %s" % empreintes)
r_bouge = dict(r)
r_bouge["total"] = r["total"] + 1
verifie("un chiffre qui bouge change l'empreinte", empreinte_de(r_bouge) != empreintes[0])

# Rendu de référence. Toute modification de géométrie, d'ordre ou de style
# change cette empreinte. Si c'est voulu : regarder le rendu (deux thèmes,
# bureau et mobile, pendant et après l'animation), puis recopier la nouvelle
# valeur ici.
REFERENCE = "9328840d32ab5fb1"
obtenue = hashlib.sha256((svg + svg_bord).encode("utf-8")).hexdigest()[:16]
verifie("le rendu de référence n'a pas bougé", obtenue == REFERENCE, "obtenue : %s" % obtenue)

print()
if echecs:
    print("%d vérification(s) en échec : %s" % (len(echecs), ", ".join(echecs)))
    sys.exit(1)
print("Toutes les vérifications passent.")
