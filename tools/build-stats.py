#!/usr/bin/env python3
"""Calcule toutes les statistiques du profil et en fait des cartes SVG.

Deux cartes, deux thèmes chacune, toutes issues d'UNE seule lecture du
calendrier de contributions public de GitHub :

    skyline    l'année en relief, un cube par jour ; dans les coins : total,
               record en une journée, plus longue série, série actuelle
    records    meilleure semaine · jours actifs · moyenne · meilleur mois

Aucun service tiers : les instances publiques gratuites tombent ou servent
du cache, et rien ne permet alors de savoir si un chiffre est à jour. Ici
tout est recalculé à chaque exécution, et chaque carte porte la date et
l'heure de son calcul — la fraîcheur est visible, donc vérifiable.

Usage :
    build-stats.py DOSSIER_SORTIE [--demo]

--demo génère des données synthétiques : sert à vérifier la mise en page
sans accès réseau. Ne jamais l'utiliser en production.

En cas d'échec réseau, le script sort en erreur SANS rien écrire : des
cartes valides ne sont jamais remplacées par des cartes vides.
"""
import json
import math
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

LOGIN = os.environ.get("LOGIN") or "FarddownYG"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
UA = "FarddownYG-profile-stats"

# Dossier de cache des années révolues. Vide = pas de cache, c'est le défaut :
# une exécution isolée relit tout. Le mode boucle le renseigne, car recalculer
# les années closes toutes les deux minutes n'apporte rien et multiplie par
# quatre le nombre d'appels à GitHub. Le cache est créé dans l'espace de
# travail du job, donc jeté à chaque redémarrage : les années closes sont
# relues au moins une fois par heure, ce qui rattrape d'éventuels commits
# antidatés.
CACHE = os.environ.get("CACHE_ANNEES") or ""

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
ABBR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]
NNBSP = " "  # espace fine insécable : séparateur de milliers français


# ---------------------------------------------------------------- récupération

def _get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def compte_cree_le():
    """Date de création du compte, pour savoir jusqu'où remonter."""
    try:
        d = json.loads(_get("https://api.github.com/users/%s" % LOGIN,
                            {"Accept": "application/vnd.github+json"}))
        return datetime.strptime(d["created_at"], "%Y-%m-%dT%H:%M:%SZ").date()
    except Exception:
        return date.today() - timedelta(days=365 * 3)


def via_graphql(debut, fin):
    """Filet de sécurité. Attention : GraphQL découpe les journées en UTC,
    alors que le calendrier du profil les découpe dans le fuseau du compte.
    Une contribution faite en début de nuit locale bascule donc la veille en
    UTC, ce qui peut créer un trou et casser une série. À n'utiliser que si
    la page publique est illisible."""
    if not TOKEN:
        raise RuntimeError("pas de jeton")
    q = ("query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){"
         "contributionsCollection(from:$f,to:$t){contributionCalendar{"
         "weeks{contributionDays{date contributionCount}}}}}}")
    payload = json.dumps({"query": q, "variables": {
        "l": LOGIN, "f": debut.isoformat() + "T00:00:00Z", "t": fin.isoformat() + "T23:59:59Z"}})
    r = json.loads(_get("https://api.github.com/graphql",
                        {"Authorization": "bearer " + TOKEN,
                         "Content-Type": "application/json"},
                        payload.encode()))
    if "errors" in r:
        raise RuntimeError("GraphQL : %s" % r["errors"][:1])
    cal = r["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return {d["date"]: d["contributionCount"]
            for w in cal["weeks"] for d in w["contributionDays"]}


def via_page(debut, fin):
    """Source principale : la page publique du calendrier, sans authentification.
    C'est exactement la grille affichée sur le profil, donc les chiffres ne
    peuvent pas diverger de ce que voit un visiteur — fuseau horaire compris.
    Deux formats de rendu coexistent selon les versions de GitHub, on gère
    les deux (data-count inline, ou <tool-tip> rattaché par identifiant)."""
    html = _get("https://github.com/users/%s/contributions?from=%s&to=%s"
                % (LOGIN, debut.isoformat(), fin.isoformat()),
                {"X-Requested-With": "XMLHttpRequest"})
    infobulles = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html))
    out = {}
    for tag in re.findall(r"<td[^>]*data-date=[^>]*>", html):
        m = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        if not m:
            continue
        jour = m.group(1)
        mc = re.search(r'data-count="(\d+)"', tag)
        if mc:
            out[jour] = int(mc.group(1))
            continue
        mid = re.search(r'id="([^"]+)"', tag)
        texte = infobulles.get(mid.group(1), "") if mid else ""
        # Le compte est TOUJOURS en tête de l'infobulle : « 7 contributions on
        # July 12th ». Il faut l'ancrer là. Prendre le premier nombre du texte
        # attrape le quantième de « No contributions on July 11th » : toutes les
        # journées vides deviennent actives, le total explose et la série devient
        # continue. C'est exactement ce qui s'est produit en production.
        mn = re.match(r"\s*([\d\s\u00a0\u202f]+?)\s*contribution", texte)
        out[jour] = int(re.sub(r"\D", "", mn.group(1))) if mn else 0
    if not out:
        raise RuntimeError("calendrier illisible")
    return out


def _cache(an, jours=None):
    """Lit (jours=None) ou écrit le cache d'une année. Silencieux : un cache
    illisible ne doit jamais empêcher un calcul, il fait juste retomber sur le
    réseau."""
    if not CACHE or an >= date.today().year:
        return None
    chemin = os.path.join(CACHE, "%d.json" % an)
    try:
        if jours is None:
            with open(chemin, encoding="utf-8") as f:
                return json.load(f)
        os.makedirs(CACHE, exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(jours, f)
    except Exception:
        return None


def calendrier():
    """Toutes les journées depuis la création du compte, fusionnées par année.
    GitHub plafonne chaque requête à un an, d'où le découpage."""
    debut, aujourdhui = compte_cree_le(), date.today()
    jours, erreurs = {}, []
    an = debut.year
    while an <= aujourdhui.year:
        en_cache = _cache(an)
        if en_cache:
            jours.update(en_cache)
            an += 1
            continue
        d = max(debut, date(an, 1, 1))
        f = min(aujourdhui, date(an, 12, 31))
        retenu = None
        for source in (via_page, via_graphql):
            try:
                obtenu = source(d, f)
            except Exception as e:
                erreurs.append("%d/%s : %s" % (an, source.__name__, e))
                continue
            if retenu is None:
                retenu = obtenu
                jours.update(obtenu)
                continue
            # Garde-fou. Les deux sources ne peuvent différer qu'à la marge : un
            # décalage de fuseau déplace quelques contributions d'un jour, il ne
            # change pas un total. Un écart massif dénonce une lecture cassée, et
            # c'est bien ce qui est arrivé — un parseur trop permissif prenait le
            # quantième des journées vides pour un nombre de contributions. On
            # repart alors sur GraphQL, moins juste sur les fuseaux mais jamais
            # absurde, plutôt que de publier n'importe quoi.
            ta, tb = sum(retenu.values()), sum(obtenu.values())
            if tb and not (0.8 <= ta / tb <= 1.25):
                print("ALERTE %d : la grille du profil totalise %d, GraphQL %d. "
                      "Écart hors de portée d'un fuseau horaire : lecture suspecte, "
                      "GraphQL retenu." % (an, ta, tb))
                for k in set(retenu) | set(obtenu):
                    jours[k] = obtenu.get(k, 0)
                retenu = obtenu
                continue
            ecarts = [k for k in set(retenu) | set(obtenu)
                      if retenu.get(k, 0) != obtenu.get(k, 0)]
            if ecarts:
                # Les valeurs des deux sources, pas seulement les dates : c'est
                # ce qui permet de dire si un chiffre manquant vient de notre
                # cadence ou du retard de GitHub à publier sa propre grille.
                detail = " · ".join(
                    "%s grille=%d GraphQL=%d" % (k, retenu.get(k, 0), obtenu.get(k, 0))
                    for k in sorted(ecarts)[-3:])
                print("%d : %d jour(s) où GraphQL (UTC) diffère de la grille du "
                      "profil (fuseau) — %s" % (an, len(ecarts), detail))
                print("%d : totaux par source — grille=%d GraphQL=%d" % (an, ta, tb))
            # La source la plus avancée gagne. Les deux ne peuvent différer que
            # de deux façons : un décalage de fuseau, qui déplace des
            # contributions d'un jour sans changer un total, ou un retard de
            # publication. Un total supérieur ne peut donc venir que du second
            # cas — et il a été observé : la grille servie par GitHub est restée
            # figée plus de deux heures (81 contributions ce jour-là) pendant
            # que GraphQL en comptait 93. Le garde-fou ci-dessus étant passé,
            # l'écart est modéré : c'est un retard, pas une lecture cassée.
            #
            # À égalité on garde la grille, qui date les journées dans le fuseau
            # du compte — exactement comme le graphe du profil.
            if tb > ta:
                print("%d : la grille du profil est en retard sur GraphQL "
                      "(%d contre %d) ; GraphQL retenu." % (an, ta, tb))
                for k in set(retenu) | set(obtenu):
                    # Une journée que GraphQL ne couvre pas encore — le
                    # lendemain de l'UTC, déjà commencé dans le fuseau du
                    # compte — garde la valeur de la grille : la jeter
                    # amputerait la série d'un jour, panne déjà survenue.
                    jours[k] = obtenu.get(k, retenu.get(k, 0))
                retenu = obtenu
        if retenu is not None:
            prefixe = "%d-" % an
            _cache(an, {k: v for k, v in jours.items() if k.startswith(prefixe)})
        an += 1
    if not jours:
        raise SystemExit("échec de récupération, cartes inchangées :\n  " + "\n  ".join(erreurs))
    # Tolérer un jour au-delà de l'UTC. La grille du profil est datée dans le
    # fuseau du compte : à 23 h UTC elle contient déjà le lendemain parisien.
    # Couper à « aujourd'hui en UTC » revenait à jeter cette journée juste après
    # être allé la chercher — c'est ce qui amputait la série d'un jour.
    limite = (aujourdhui + timedelta(days=1)).isoformat()
    return {k: v for k, v in jours.items() if k <= limite}


def calendrier_demo():
    import random
    random.seed(7)
    fin = date.today()
    out = {}
    for i in range(215):
        j = fin - timedelta(days=i)
        n = 0 if random.random() < 0.31 else random.choice([1, 2, 3, 4, 5, 7, 9, 12, 18, 40])
        if i == 96:
            n = 254
        if i < 30:
            n = max(n, 1)
        out[j.isoformat()] = n
    return out


# ------------------------------------------------------------------- calculs

def _jour(iso):
    return date.fromisoformat(iso)


def series(jours):
    """Série en cours et plus longue série.

    La série se compte à rebours depuis la DERNIÈRE journée active, jamais
    depuis « aujourd'hui ». La nuance est décisive : le runner GitHub vit en
    UTC, le calendrier du profil dans le fuseau du compte. À 23 h UTC il est
    déjà le lendemain à Paris, la grille contient donc une journée que l'UTC
    ignore — partir de l'UTC amputait la série d'un jour. Une journée encore
    vide ne la casse pas non plus : elle n'est pas finie.

    La série reste vivante tant que la dernière journée active n'a pas plus
    d'un jour de retard sur l'UTC. Un jour de tolérance suffit à couvrir
    n'importe quel fuseau, de UTC-12 à UTC+14."""
    actifs = sorted(k for k, v in jours.items() if v > 0)
    if not actifs:
        return (0, None, None), (0, None, None)

    fin_serie = _jour(actifs[-1])
    if (date.today() - fin_serie).days > 1:
        courante = (0, None, None)
    else:
        n, d = 0, fin_serie
        while jours.get(d.isoformat(), 0) > 0:
            n += 1
            d -= timedelta(days=1)
        courante = (n, (fin_serie - timedelta(days=n - 1)).isoformat(), fin_serie.isoformat())

    best, best_fin, cur, prev = 0, None, 0, None
    for k in sorted(jours):
        if jours[k] > 0:
            cur = cur + 1 if prev and (_jour(k) - _jour(prev)).days == 1 else 1
            prev = k
            if cur > best:
                best, best_fin = cur, k
        else:
            cur, prev = 0, None
    longue = (best, (_jour(best_fin) - timedelta(days=best - 1)).isoformat(), best_fin) if best else (0, None, None)
    return courante, longue


def stats(jours):
    actifs = {k: v for k, v in jours.items() if v > 0}
    if not actifs:
        raise SystemExit("aucune contribution, cartes inchangées")
    total = sum(jours.values())

    date_record = max(actifs, key=lambda k: actifs[k])
    par_mois = {}
    for k, v in jours.items():
        par_mois[k[:7]] = par_mois.get(k[:7], 0) + v
    meilleur_mois = max(par_mois, key=lambda k: par_mois[k])
    courante, longue = series(jours)

    # Meilleure semaine : sept jours consécutifs, en fenêtre glissante plutôt
    # qu'en semaines du calendrier — une semaine record à cheval sur deux
    # semaines civiles ne doit pas être coupée en deux.
    d, d_fin = _jour(min(jours)), _jour(max(jours))
    suite = []
    while d <= d_fin:
        suite.append((d, jours.get(d.isoformat(), 0)))
        d += timedelta(days=1)
    semaine, fin_semaine, cumul = -1, len(suite) - 1, 0
    for i, (_, v) in enumerate(suite):
        cumul += v - (suite[i - 7][1] if i >= 7 else 0)
        if i >= min(6, len(suite) - 1) and cumul > semaine:
            semaine, fin_semaine = cumul, i

    return {
        "jours": jours,
        "semaine": (semaine, suite[max(0, fin_semaine - 6)][0].isoformat(),
                    suite[fin_semaine][0].isoformat()),
        "total": total,
        "record": actifs[date_record],
        "record_date": date_record,
        "actifs": len(actifs),
        "premier": min(actifs),
        "moyenne": total / len(actifs),
        "mois": meilleur_mois,
        "mois_total": par_mois[meilleur_mois],
        "courante": courante,
        "longue": longue,
        "calcule": datetime.now(timezone.utc),
    }


def fr(n):
    return "{:,}".format(int(n)).replace(",", NNBSP)


def jour_fr(iso):
    d = _jour(iso)
    return "%d %s %d" % (d.day, ABBR[d.month - 1], d.year)


def court(iso):
    d = _jour(iso)
    return "%d %s" % (d.day, ABBR[d.month - 1])


def mois_fr(iso):
    a, m = iso.split("-")
    return "%s %s" % (MOIS[int(m) - 1], a)


def horodatage(dt):
    return "mis à jour le %d %s %d à %02dh%02d UTC" % (
        dt.day, ABBR[dt.month - 1], dt.year, dt.hour, dt.minute)


# ------------------------------------------------------------------- rendu

DARK = dict(bg="#0B0E13", border="#2A3140", gold="#C8A96A", text="#E8EAF0",
            muted="#9AA3B2", dim="#6B7280", rule="#2A3140", grid="#1B212B")
LIGHT = dict(bg="#FBF7EE", border="#D9D2C2", gold="#8C6E33", text="#14171C",
             muted="#5F6672", dim="#8B857A", rule="#E2DACA", grid="#EDE5D4")

SANS = "'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','Cascadia Code','SF Mono',Consolas,'DejaVu Sans Mono',monospace"

# Flamme de la série en cours, dessinée dans une boîte de 18x18.
# La langue de feu latérale est ce qui la rend lisible à petite taille.
FLAMME = ("M9,0 C10.4,4 14.1,6.1 14.1,10.8 C14.1,14.8 11.8,17.6 9,17.6 "
          "C6.2,17.6 3.9,14.8 3.9,10.8 C3.9,8 6.3,6.6 6.9,3.4 "
          "C7.6,7 9.3,7.5 9.6,5.2 C9.9,3 8.4,1.8 9,0 Z")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cadre(w, h, titre, p, r):
    """Contour commun : bordure, titre en or, horodatage discret."""
    return [
        '<svg viewBox="0 0 %d %d" width="%d" height="%d" xmlns="http://www.w3.org/2000/svg" '
        'role="img" aria-label="%s">' % (w, h, w, h, esc(titre)),
        '  <rect x="0.7" y="0.7" width="%.1f" height="%.1f" rx="10" fill="%s" stroke="%s" '
        'stroke-width="1.4"/>' % (w - 1.4, h - 1.4, p["bg"], p["border"]),
        '  <text x="28" y="40" font-family="%s" font-size="11" letter-spacing="3" fill="%s">'
        '// %s</text>' % (MONO, p["gold"], esc(titre.upper())),
        '  <text x="%d" y="40" text-anchor="end" font-family="%s" font-size="10" fill="%s">'
        '%s</text>' % (w - 28, MONO, p["dim"], esc(horodatage(r["calcule"]))),
    ]


def tuile(cx, val, lab, det, p, phare=False, y=128):
    return [
        '  <text x="%g" y="%d" text-anchor="middle" font-family="%s" font-size="42" '
        'font-weight="700" fill="%s">%s</text>'
        % (cx, y, SANS, p["gold"] if phare else p["text"], esc(val)),
        '  <text x="%g" y="%d" text-anchor="middle" font-family="%s" font-size="12" fill="%s">'
        '%s</text>' % (cx, y + 26, SANS, p["muted"], esc(lab)),
        '  <text x="%g" y="%d" text-anchor="middle" font-family="%s" font-size="10.5" fill="%s">'
        '%s</text>' % (cx, y + 46, MONO, p["dim"], esc(det)),
    ]


def carte_records(r, p):
    o = cadre(900, 200, "Records", p, r)
    tuiles = [
        (fr(r["semaine"][0]), "Meilleure semaine",
         "%s – %s" % (court(r["semaine"][1]), court(r["semaine"][2])), True),
        (fr(r["actifs"]), "Jours actifs", "depuis le %s" % jour_fr(r["premier"]), False),
        (("%.1f" % r["moyenne"]).replace(".", ","), "Par jour actif", "en moyenne", False),
        (fr(r["mois_total"]), "Meilleur mois", mois_fr(r["mois"]), False),
    ]
    for i, (val, lab, det, phare) in enumerate(tuiles):
        cx = 24 + 213 * i + 106.5
        if i:
            o.append('  <path d="M%g,84 V178" stroke="%s" stroke-width="1" opacity="0.75"/>'
                     % (24 + 213 * i, p["rule"]))
        o += tuile(cx, val, lab, det, p, phare)
    o.append('</svg>')
    return "\n".join(o) + "\n"


# ------------------------------------------------------------------- skyline
#
# Portage statique de « Contribution Skyline » (21st.dev, @kedhareswer) : une
# année de contributions vue en isométrique, un cube par jour, haut comme
# l'activité de ce jour-là. L'original est un composant React dessiné sur
# canvas. Un README n'exécutant aucun JavaScript, tout ce qui demandait une
# interaction disparaît — rotation, survol, bascule 2D/3D. Ce qui se dit en SVG
# pur reste : la même caméra, le même ordre de peinture, les trois faces
# ombrées, et la montée des barres en vague du plus ancien au plus récent,
# rejouée en SMIL au chargement de l'image.

SKY_CS = SKY_SN = math.cos(math.radians(45))   # lacet de la caméra
SKY_SE = math.sin(math.radians(34))            # élévation
SKY_CE = math.cos(math.radians(34))
SKY_CUBE = 0.9         # côté d'un cube en cases ; le reste fait le joint
SKY_HAUT = 7.2         # hauteur de la journée record, en cases
SKY_DALLE = 0.2        # épaisseur d'une journée vide
SKY_ATTENTE = 0.35     # avant que la vague parte, en secondes
SKY_DUREE = 1.4        # durée de la vague
SKY_VAGUE = 0.42       # part de la vague passée à attendre son tour
SKY_SCENE = (28, 58, 872, 548)   # zone de dessin : x0, y0, x1, y1

# Cinq teintes par thème : journée vide, puis quatre niveaux d'activité. L'or
# du profil en est le sommet ; en clair l'ordre s'inverse, la plus forte
# activité est la plus sombre, comme sur le graphe de GitHub.
SKY_NIVEAUX = {
    DARK["bg"]: ("#23262B", "#4A3F2A", "#7D6639", "#B0904F", "#E0C27F"),
    LIGHT["bg"]: ("#EAE5DA", "#E8D5A6", "#CFAA5C", "#A27C33", "#6B501D"),
}


def _teinte(hexa, facteur):
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(int(round(c * facteur)) for c in (r, g, b))


def _hauteur(n, record):
    """Racine carrée plutôt que linéaire. Une journée record à 322 contre des
    journées ordinaires à 10-20 réduirait tout le reste à une plaine sous une
    seule tour — c'est exactement ce qui avait rendu le premier graphique
    d'activité illisible. La couleur, elle, garde l'échelle des niveaux."""
    return 0.4 + SKY_HAUT * math.sqrt(n / record) if n > 0 and record > 0 else SKY_DALLE


def _niveau(n, seuil):
    """0 pour une journée vide, sinon 1 à 4 par quarts du 95e centile : une
    seule journée hors norme ne doit pas renvoyer toutes les autres au niveau 1."""
    if n <= 0:
        return 0
    return 4 if seuil <= 0 else 1 + min(3, int(n / seuil * 4))


def _grille(jours):
    """Cinquante-trois semaines finissant sur la dernière journée connue — celle
    du fuseau du compte, comme le graphe du profil. Lundi en haut de colonne."""
    fin = _jour(max(jours))
    debut = fin - timedelta(days=364)
    debut -= timedelta(days=debut.weekday())
    cases, d, i = [], debut, 0
    while d <= fin:
        cases.append((d, jours.get(d.isoformat(), 0), i // 7, i % 7))
        d += timedelta(days=1)
        i += 1
    return cases


def _proj(x, y, z):
    return (x * SKY_CS - y * SKY_SN, (x * SKY_SN + y * SKY_CS) * SKY_SE - z * SKY_CE)


def _pts(points):
    return " ".join("%.1f,%.1f" % p for p in points)


def _faces(x0, y0, z, ecran):
    """Les trois faces visibles d'un cube : droite (+x), gauche (+y), dessus."""
    x1, y1 = x0 + SKY_CUBE, y0 + SKY_CUBE
    return (
        [ecran(x1, y0, 0), ecran(x1, y1, 0), ecran(x1, y1, z), ecran(x1, y0, z)],
        [ecran(x0, y1, 0), ecran(x1, y1, 0), ecran(x1, y1, z), ecran(x0, y1, z)],
        [ecran(x0, y0, z), ecran(x1, y0, z), ecran(x1, y1, z), ecran(x0, y1, z)],
    )


def _bloc(x, y, ancre, label, valeur, unite, detail, p, icone=False):
    """Un chiffre en coin, à la manière de l'original : intitulé, grand
    chiffre suivi de son unité sur la même ligne de base, détail dessous.
    Tout est aligné sur le bord du bloc ; l'unité suit le chiffre dans le même
    <text>, ce qui évite d'avoir à mesurer la largeur des glyphes."""
    o, lx = [], x
    if icone:
        # flamme de la série en cours, devant l'intitulé (blocs alignés à gauche)
        o.append('  <path d="%s" transform="translate(%.1f,%.1f) scale(0.78)" fill="%s"/>'
                 % (FLAMME, x, y - 12.6, p["gold"]))
        lx = x + 18
    o.append('  <text x="%.1f" y="%.1f" text-anchor="%s" font-family="%s" font-size="13" '
             'fill="%s">%s</text>' % (lx, y, ancre, SANS, p["muted"], esc(label)))
    o.append('  <text x="%.1f" y="%.1f" text-anchor="%s" font-family="%s">'
             '<tspan font-size="48" font-weight="700" letter-spacing="-1" fill="%s">%s</tspan>'
             '<tspan dx="9" font-size="15" fill="%s">%s</tspan></text>'
             % (x, y + 50, ancre, SANS, p["gold"], esc(valeur), p["text"], esc(unite)))
    o.append('  <text x="%.1f" y="%.1f" text-anchor="%s" font-family="%s" font-size="11" '
             'fill="%s">%s</text>' % (x, y + 72, ancre, MONO, p["dim"], esc(detail)))
    return o


def carte_skyline(r, p):
    cases = _grille(r["jours"])
    semaines = cases[-1][2] + 1
    actifs = sorted(n for _, n, _, _ in cases if n > 0)
    seuil = actifs[int(0.95 * (len(actifs) - 1))] if actifs else 0
    record = actifs[-1] if actifs else 0
    marge = (1 - SKY_CUBE) / 2

    # Cadrage : la scène entière, barres à pleine hauteur et rangée des mois
    # comprises, ajustée à la zone de dessin puis centrée.
    xs, ys = [], []
    for _, n, w, d in cases:
        for (sx, sy) in (_proj(w, d, 0), _proj(w + 1, d, 0), _proj(w, d + 1, 0),
                         _proj(w + 1, d + 1, 0), _proj(w, d, _hauteur(n, record))):
            xs.append(sx)
            ys.append(sy)
    for w in (0, semaines):
        sx, sy = _proj(w, 8.6, 0)
        xs.append(sx)
        ys.append(sy)
    X0, Y0, X1, Y1 = SKY_SCENE
    s = min((X1 - X0) / (max(xs) - min(xs)), (Y1 - Y0) / (max(ys) - min(ys)))
    ox = X0 + ((X1 - X0) - (max(xs) - min(xs)) * s) / 2 - min(xs) * s
    oy = Y0 + ((Y1 - Y0) - (max(ys) - min(ys)) * s) / 2 - min(ys) * s

    def ecran(x, y, z):
        sx, sy = _proj(x, y, z)
        return (ox + sx * s, oy + sy * s)

    H = Y1 + 52
    o = cadre(900, H, "Skyline", p, r)
    teintes = SKY_NIVEAUX[p["bg"]]

    # Une face latérale est l'image d'un rectangle unité par un cisaillement
    # vertical. La pente de son arête basse et sa largeur ne dépendent que de
    # la caméra ; d'un jour à l'autre seule la hauteur change. C'est donc le
    # seul nombre à animer, et il passe par une variable CSS.
    pente = math.degrees(math.atan(SKY_SE))
    l_droite, l_gauche = SKY_SN * s * SKY_CUBE, SKY_CS * s * SKY_CUBE
    h_dalle = SKY_DALLE * SKY_CE * s
    montee = (1 - SKY_VAGUE) * SKY_DUREE

    regles = "".join(".d%d{fill:%s}.g%d{fill:%s}.t%d{fill:%s}"
                     % (k, _teinte(t, 0.68), k, _teinte(t, 0.84), k, t)
                     for k, t in enumerate(teintes))
    # Animations CSS plutôt que SMIL : SMIL ignore prefers-reduced-motion, il
    # aurait fallu doubler chaque barre d'une jumelle immobile. Ici le
    # mouvement réduit se coupe d'une ligne, et chaque élément porte sa
    # géométrie finale en attribut — ce qu'affiche aussi un moteur sans CSS.
    o.append("  <style>%s"
             ".m,.u{animation:%.2fs cubic-bezier(.33,1,.68,1) var(--t) both}"
             ".m{animation-name:m}.u{animation-name:u}"
             "@keyframes m{from{transform:scale(1,%.2f)}to{transform:scale(1,var(--h))}}"
             "@keyframes u{from{transform:translate(0,var(--d))}to{transform:translate(0,0)}}"
             "@media (prefers-reduced-motion:reduce){.m,.u{animation:none}}</style>"
             % (regles, montee, h_dalle))

    # Une journée vide est la même dalle partout : dessinée une fois, réutilisée.
    bx, by = ecran(marge, marge, 0)
    o.append('  <defs><g id="v">' + "".join(
        '<polygon class="%s" points="%s"/>' % (c, _pts([(x - bx, y - by) for x, y in f]))
        for c, f in zip(("d0", "g0", "t0"), _faces(marge, marge, SKY_DALLE, ecran)))
        + '</g></defs>')

    # Ordre du peintre : du plus loin au plus proche de la caméra. La vague
    # part de la semaine la plus ancienne, avec un léger décalage par jour.
    ordre = sorted(cases, key=lambda c: ((c[2] + 0.5) * SKY_SN + (c[3] + 0.5) * SKY_CS, c[2]))
    for _, n, w, d in ordre:
        x0, y0 = w + marge, d + marge
        if n <= 0:
            ux, uy = ecran(x0, y0, 0)
            o.append('  <use href="#v" x="%.1f" y="%.1f"/>' % (ux, uy))
            continue
        k, z = _niveau(n, seuil), _hauteur(n, record)
        h = z * SKY_CE * s
        t = SKY_ATTENTE + ((w / max(1, semaines - 1)) * 0.36 + (d / 6) * 0.06) * SKY_DUREE
        rx, ry = ecran(x0 + SKY_CUBE, y0, 0)
        gx, gy = ecran(x0, y0 + SKY_CUBE, 0)
        o.append(
            '  <g style="--h:%.1f;--d:%.1fpx;--t:%.2fs">'
            '<g transform="translate(%.1f,%.1f) skewY(%.2f)"><rect class="d%d m" x="%.1f" '
            'y="-1" width="%.1f" height="1" transform="scale(1,%.1f)"/></g>'
            '<g transform="translate(%.1f,%.1f) skewY(%.2f)"><rect class="g%d m" '
            'y="-1" width="%.1f" height="1" transform="scale(1,%.1f)"/></g>'
            '<polygon class="t%d u" points="%s"/></g>'
            % (h, h - h_dalle, t,
               rx, ry, -pente, k, -l_droite, l_droite, h,
               gx, gy, pente, k, l_gauche, h,
               k, _pts(_faces(x0, y0, z, ecran)[2])))

    # Mois, sous l'arête avant, alignés à droite sur la première semaine de
    # chacun : ils débordent ainsi vers le vide en contrebas, jamais sur les
    # cubes des semaines suivantes.
    mois, prec = [], None
    for w in range(semaines):
        jour = cases[w * 7][0]
        if jour.month != prec:
            mois.append((w, ABBR[jour.month - 1]))
        prec = jour.month
    if len(mois) > 1 and mois[1][0] - mois[0][0] < 3:
        mois.pop(0)
    for w, lab in mois:
        x, y = ecran(w + 0.5, 7.2, 0)
        if x - len(lab) * 6.1 < X0 - 12:
            continue
        o.append('  <text x="%.1f" y="%.1f" text-anchor="end" font-family="%s" font-size="10" '
                 'fill="%s">%s</text>' % (x - 2, y + 11, MONO, p["dim"], esc(lab)))

    # Les quatre chiffres, dans les deux coins que la diagonale laisse vides.
    def unite(v, mot):
        return mot if v <= 1 else mot + "s"

    nc, c1, c2 = r["courante"]
    nl, l1, l2 = r["longue"]
    o += _bloc(X1 - 4, Y0 + 22, "end", "Total", fr(r["total"]),
               unite(r["total"], "contribution"), "depuis le %s" % jour_fr(r["premier"]), p)
    o += _bloc(X1 - 4, Y0 + 122, "end", "Record en une journée", fr(r["record"]),
               unite(r["record"], "contribution"), jour_fr(r["record_date"]), p)
    o += _bloc(X0 + 4, Y1 - 172, "start", "Plus longue série", fr(nl), unite(nl, "jour"),
               "%s – %s" % (court(l1), court(l2)) if nl else "—", p)
    o += _bloc(X0 + 4, Y1 - 72, "start", "Série actuelle", fr(nc), unite(nc, "jour"),
               "%s – %s" % (court(c1), court(c2)) if nc else "—", p, icone=True)

    # Pied : ce que montre la carte, et la légende des niveaux.
    yp = Y1 + 30
    o.append('  <text x="%d" y="%d" font-family="%s" font-size="10.5" fill="%s">'
             '12 derniers mois · un cube par jour</text>' % (X0, yp, MONO, p["muted"]))
    xd = X1 - 6.3 * 4
    o.append('  <text x="%d" y="%d" text-anchor="end" font-family="%s" font-size="10.5" '
             'fill="%s">Plus</text>' % (X1, yp, MONO, p["dim"]))
    for k in range(4, -1, -1):
        xd -= 8 + 11 if k == 4 else 4 + 11
        o.append('  <rect x="%.1f" y="%d" width="11" height="11" rx="2" fill="%s"/>'
                 % (xd, yp - 9.5, teintes[k]))
    o.append('  <text x="%.1f" y="%d" text-anchor="end" font-family="%s" font-size="10.5" '
             'fill="%s">Moins</text>' % (xd - 8, yp, MONO, p["dim"]))
    o.append('</svg>')
    return "\n".join(o) + "\n"


CARTES = (("skyline", carte_skyline), ("records", carte_records))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    dossier = args[0]
    jours = calendrier_demo() if "--demo" in sys.argv else calendrier()
    r = stats(jours)
    os.makedirs(dossier, exist_ok=True)
    for nom, rendu in CARTES:
        for suffixe, pal in (("dark", DARK), ("light", LIGHT)):
            chemin = os.path.join(dossier, "%s-%s.svg" % (nom, suffixe))
            open(chemin, "w", encoding="utf-8").write(rendu(r, pal))
            print("écrit :", chemin)
    # Trace des dernières journées : si un chiffre paraît faux un jour, cette
    # ligne dit tout de suite ce que GitHub a renvoyé, sans avoir à deviner.
    print("dernières journées vues : " +
          " · ".join("%s=%d" % (k[5:], jours[k]) for k in sorted(jours)[-6:]))
    n, d1, d2 = r["courante"]
    print("total %d · série %d (%s → %s) · plus longue %d · record %d le %s · "
          "%d jours actifs · %.1f/jour"
          % (r["total"], n, d1, d2, r["longue"][0], r["record"], r["record_date"],
             r["actifs"], r["moyenne"]))


if __name__ == "__main__":
    main()
