#!/usr/bin/env python3
"""Calcule toutes les statistiques du profil et en fait des cartes SVG.

Deux cartes, toutes issues d'UNE seule lecture du calendrier de contributions
public de GitHub :

    skyline    l'année en relief, un cube par jour ; total, record en une
               journée, plus longue série, série actuelle
    bord       le tableau de bord : meilleure semaine et meilleur mois sur deux
               cadrans à aiguille, compteur du total, trente derniers jours,
               jours actifs, moyenne par jour actif

Chaque carte sort en quatre fichiers : bureau et mobile (suffixe -m), thème
sombre et thème clair. Le texte est composé en tracés par typo.py à partir de
l'atlas glyphes.json ; le système de design vit dans dessin.py. Python pur,
aucune dépendance.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dessin import (ABBR, FLAMME, MOIS, PALETTES, Feuille, arc, cadre, fr,  # noqa: E402
                    horodatage, pique, polaire, quantieme, rosace, teinte)
from typo import _n  # noqa: E402

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
        elif an == aujourdhui.year:
            # L'année en cours est la seule qui compte pour la fraîcheur. Si les
            # deux sources ont échoué sur elle mais que les années closes
            # viennent du cache, `jours` n'est pas vide : sans cet arrêt, on
            # publierait un total amputé de l'année et un skyline arrêté au 31
            # décembre précédent, présenté comme « les 12 derniers mois ».
            raise SystemExit("année %d illisible, cartes inchangées :\n  %s"
                             % (an, "\n  ".join(erreurs)))
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

    # Trente derniers jours, et nombre de jours écoulés depuis la première
    # contribution — la fenêtre finit sur la dernière journée connue, jamais
    # avant aujourd'hui.
    fin = max(_jour(max(actifs)), date.today())
    trente = sum(jours.get((fin - timedelta(days=k)).isoformat(), 0) for k in range(30))

    return {
        "jours": jours,
        "trente": trente,
        "ecoules": (fin - _jour(min(actifs))).days + 1,
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


def jour_fr(iso):
    d = _jour(iso)
    return "%s %s %d" % (quantieme(d.day), ABBR[d.month - 1], d.year)


def court(iso):
    d = _jour(iso)
    return "%s %s" % (quantieme(d.day), ABBR[d.month - 1])


def periode(d1, d2, ref):
    """« 12 juil. – 13 août », avec l'année dès que la période sort de l'année
    de `ref` (la dernière journée connue). Sans elle, une série de l'an passé
    se lirait comme tombant dans la frise des douze derniers mois, qui porte
    les mêmes noms de mois."""
    a, b = _jour(d1), _jour(d2)
    fin = jour_fr(d2) if b.year != _jour(ref).year else court(d2)
    if d1 == d2:
        return fin              # une série d'un jour n'est pas « du 25 au 25 »
    debut = jour_fr(d1) if a.year != b.year else court(d1)
    return "%s – %s" % (debut, fin)


def mois_fr(iso):
    a, m = iso.split("-")
    return "%s %s" % (MOIS[int(m) - 1], a)


def pluriel(v, mot):
    return mot if v <= 1 else mot + "s"


def decimal(v):
    return ("%.1f" % v).replace(".", ",")


# ------------------------------------------------------------------- rendu
#
# Tout le texte est composé en tracés (typo.py) : même dessin sur tous les
# appareils, largeurs exactes. Chaque carte existe en deux mises en page —
# bureau (900 de large) et mobile (450 de large, plus haute, texte plus gros
# à l'écran) — que le README choisit par <picture> selon la largeur de l'écran.
#
# Règle d'animation, valable partout : chaque élément porte son état FINAL en
# attribut ; l'animation part d'ailleurs et y revient. Sans CSS, ou en
# mouvement réduit, la carte s'affiche donc complète.

ANIM = (
    # entrée d'un chiffre, glyphe par glyphe (unités de police : 300 = 0,3 em)
    ".n{animation:n .7s cubic-bezier(.2,.8,.2,1) both}"
    "@keyframes n{from{opacity:0;transform:translateY(300px)}}"
)
SANS_ANIM = "@media (prefers-reduced-motion:reduce){%s{animation:none}}"


def _bloc(f, x, y, ancre, label, valeur, unite, detail, flamme=False, corps=48, depart=0.9,
          place=None):
    """Un chiffre et sa légende. Renvoie (éléments, boîte occupée).

    Les largeurs sont exactes : la boîte sert à réserver la place du bloc dans
    le cadrage du skyline, sans marge de sécurité pour une police de repli.
    place : largeur disponible ; si le chiffre et son unité n'y tiennent pas,
    l'unité saute (le libellé suffit) plutôt que de déborder sur le voisin."""
    p = f.p
    wl = f.largeur("texte", label, 13.5) + (17 if flamme else 0)
    wv = f.largeur("titre", valeur, corps)
    wu = f.largeur("texte", unite, 15)
    if place is not None and wv + 9 + wu > place:
        unite, wu = "", -9
    wd = f.largeur("mono", detail, 10.5)
    w = max(wl, wv + 9 + wu, wd)

    def cale(largeur):
        return x - largeur if ancre == "end" else x

    base = y + 16 + f.t.capitale("titre", corps)
    o, lx = [], cale(wl)
    if flamme:
        o.append('<path d="%s" transform="translate(%s %s) scale(0.78)" fill="%s"/>'
                 % (FLAMME, _n(lx), _n(y - 12.8), p["rouge"]))
        lx += 17
    o.append(f.texte("texte", label, 13.5, lx, y, fill=p["doux"]))
    vx = cale(wv + 9 + wu)
    o.append(f.texte("titre", valeur, corps, vx, base, fill=p["o"], cascade=(depart, 0.055)))
    if unite:
        o.append(f.texte("texte", unite, 15, vx + wv + 9, base, fill=p["encre"]))
    o.append(f.texte("mono", detail, 10.5, cale(wd), base + 22, fill=p["discret"]))
    gauche = cale(w)
    return o, (gauche - 6, y - 16, gauche + w + 6, base + 28)


# ------------------------------------------------------------------- skyline
#
# Portage statique de « Contribution Skyline » (21st.dev, @kedhareswer) : une
# année de contributions vue en isométrique, un cube par jour, haut comme
# l'activité de ce jour-là. L'original est un composant React dessiné sur
# canvas. Un README n'exécutant aucun JavaScript, tout ce qui demandait une
# interaction disparaît — rotation, survol, bascule 2D/3D. Ce qui se dit en SVG
# pur reste : la même caméra, le même ordre de peinture, les trois faces
# ombrées, et la montée des barres en vague du plus ancien au plus récent,
# rejouée en CSS au chargement de l'image (animations pilotées par variables,
# voir plus bas pourquoi pas SMIL).

SKY_CS = SKY_SN = math.cos(math.radians(45))   # lacet de la caméra
SKY_SE = math.sin(math.radians(34))            # élévation
SKY_CE = math.cos(math.radians(34))
SKY_CUBE = 0.9         # côté d'un cube en cases ; le reste fait le joint
SKY_HAUT = 7.2         # hauteur de la journée record, en cases
SKY_DALLE = 0.2        # épaisseur d'une journée vide
SKY_ATTENTE = 0.35     # avant que la vague parte, en secondes
SKY_DUREE = 1.4        # durée de la vague
SKY_VAGUE = 0.42       # part de la vague passée à attendre son tour
SKY_SCENE = (28, 58, 872, 548)          # zone de dessin, bureau : x0, y0, x1, y1
SKY_SCENE_MOBILE = (12, 54, 438, 304)   # mobile : la scène seule, chiffres dessous
# Débord, en pixels, des faces latérales sous les faces peintes après elles.
# Chaque face est lissée séparément : deux faces qui se touchent bord à bord
# laissent passer le fond sur leur arête, un filet clair très visible sur les
# barres sombres du thème clair. La face du dessous dépasse donc un peu sous
# celle qui la recouvre — droite sous gauche, les deux sous le dessus.
SKY_DEBORD = 0.6


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
    # Jamais avant aujourd'hui : une donnée manquante en fin de série ne doit
    # pas faire reculer la fenêtre en silence. Jamais après non plus, sauf si
    # le lendemain porte déjà des contributions (fuseau du compte en avance sur
    # l'UTC) : la page de GitHub liste parfois demain, vide, et la frise se
    # terminait alors par une case qui n'existe pas encore.
    fin = max(_jour(max(k for k, v in jours.items() if v > 0)), date.today())
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


def _blocs_skyline(f, r, mobile):
    """Les quatre chiffres du skyline : (éléments, boîtes réservées)."""
    nc, c1, c2 = r["courante"]
    nl, l1, l2 = r["longue"]
    ref = max(r["jours"])
    textes = [
        ("Total", fr(r["total"]), pluriel(r["total"], "contribution"),
         "depuis le %s" % jour_fr(r["premier"]), False),
        ("Record en une journée", fr(r["record"]), pluriel(r["record"], "contribution"),
         jour_fr(r["record_date"]), False),
        ("Plus longue série", fr(nl), pluriel(nl, "jour"), periode(l1, l2, ref) if nl else "—", False),
        ("Série actuelle", fr(nc), pluriel(nc, "jour"), periode(c1, c2, ref) if nc else "—", True),
    ]
    if mobile:
        places = [(26, 338, "start"), (236, 338, "start"), (26, 444, "start"), (236, 444, "start")]
        corps = 38
    else:
        X0, Y0, X1, Y1 = SKY_SCENE
        places = [(X1 - 4, Y0 + 22, "end"), (X1 - 4, Y0 + 122, "end"),
                  (X0 + 4, Y1 - 172, "start"), (X0 + 4, Y1 - 72, "start")]
        corps = 48
    elements, boites = [], []
    for i, ((x, y, ancre), (label, valeur, unite, detail, flamme)) in enumerate(zip(places, textes)):
        o, boite = _bloc(f, x, y, ancre, label, valeur, unite, detail, flamme, corps, 1.0 + 0.16 * i,
                         place=196 if mobile else None)
        elements += o
        boites.append(boite)
    return elements, boites


def carte_skyline(r, p, mobile=False):
    cases = _grille(r["jours"])
    semaines = cases[-1][2] + 1
    actifs = sorted(n for _, n, _, _ in cases if n > 0)
    seuil = actifs[int(0.95 * (len(actifs) - 1))] if actifs else 0
    record = actifs[-1] if actifs else 0
    marge = (1 - SKY_CUBE) / 2

    W, H = (450, 566) if mobile else (900, 600)
    X0, Y0, X1, Y1 = SKY_SCENE_MOBILE if mobile else SKY_SCENE
    nc, nl = r["courante"][0], r["longue"][0]
    f = Feuille(W, H, p, "Skyline des contributions",
                "%s %s depuis le %s. Record en une journée : %s, le %s. Plus longue série : %s %s. "
                "Série actuelle : %s %s."
                % (fr(r["total"]), pluriel(r["total"], "contribution"), jour_fr(r["premier"]),
                   fr(r["record"]), jour_fr(r["record_date"]), fr(nl), pluriel(nl, "jour"),
                   fr(nc), pluriel(nc, "jour")))
    cadre(f, "Skyline", horodatage(r["calcule"], court=mobile))

    # Les quatre chiffres, établis avant le cadrage : sur bureau ils occupent
    # les deux coins que la diagonale laisse vides, et ces coins sont réservés.
    blocs, boites = _blocs_skyline(f, r, mobile)
    zones = [] if mobile else boites

    # Mois, sous la première semaine de chacun.
    mois, prec = [], None
    for w in range(semaines):
        jour = cases[w * 7][0]
        if jour.month != prec:
            mois.append((w, ABBR[jour.month - 1]))
        prec = jour.month
    if len(mois) > 1 and mois[1][0] - mois[0][0] < 3:
        mois.pop(0)
    corps_mois = 9 if mobile else 10

    # Boîtes de la scène hors échelle : chaque cube à pleine hauteur, et
    # l'ancre de chaque étiquette de mois.
    scene = []
    for _, n, w, d in cases:
        pts = [_proj(x, y, z) for x in (w + marge, w + marge + SKY_CUBE)
               for y in (d + marge, d + marge + SKY_CUBE) for z in (0, _hauteur(n, record))]
        scene.append((min(q[0] for q in pts), min(q[1] for q in pts),
                      max(q[0] for q in pts), max(q[1] for q in pts)))
    ancres = [(_proj(w + 0.5, 7.2, 0), lab, f.largeur("mono", lab, corps_mois)) for w, lab in mois]
    xs = [b[0] for b in scene] + [b[2] for b in scene] + [a[0][0] for a in ancres]
    ys = [b[1] for b in scene] + [b[3] for b in scene] + [a[0][1] + 1.0 for a in ancres]
    lx, ly = max(xs) - min(xs), max(ys) - min(ys)

    def place(s):
        return (X0 + ((X1 - X0) - lx * s) / 2 - min(xs) * s,
                Y0 + ((Y1 - Y0) - ly * s) / 2 - min(ys) * s)

    def empiete(s, ox, oy):
        rects = [(ox + a * s, oy + b * s, ox + c * s, oy + d * s) for a, b, c, d in scene]
        rects += [(ox + q[0] * s - 2 - wl, oy + q[1] * s + 3, ox + q[0] * s - 2, oy + q[1] * s + 13)
                  for q, _, wl in ancres]
        return any(a < z2 and c > z0 and b < z3 and d > z1
                   for a, b, c, d in rects for z0, z1, z2, z3 in zones)

    # Ajusté à la zone de dessin, puis réduit tant qu'un cube ou un mois entre
    # dans le coin d'un chiffre. La diagonale laisse ces coins libres avec les
    # données d'aujourd'hui ; un record à cinq chiffres un lundi d'été suffirait
    # à poser une tour sous un chiffre.
    s = min((X1 - X0) / lx, (Y1 - Y0) / ly)
    ox, oy = place(s)
    for _ in range(40):
        if not empiete(s, ox, oy):
            break
        s *= 0.97
        ox, oy = place(s)

    def ecran(x, y, z):
        sx, sy = _proj(x, y, z)
        return (ox + sx * s, oy + sy * s)

    teintes = p["niveaux"]

    # Une face latérale est l'image d'un rectangle unité par un cisaillement
    # vertical. La pente de son arête basse et sa largeur ne dépendent que de
    # la caméra ; d'un jour à l'autre seule la hauteur change. C'est donc le
    # seul nombre à animer, et il passe par une variable CSS.
    pente = math.degrees(math.atan(SKY_SE))
    l_droite, l_gauche = SKY_SN * s * SKY_CUBE, SKY_CS * s * SKY_CUBE
    h_dalle = SKY_DALLE * SKY_CE * s
    montee = (1 - SKY_VAGUE) * SKY_DUREE

    # Animations CSS plutôt que SMIL : SMIL ignore prefers-reduced-motion, il
    # aurait fallu doubler chaque barre d'une jumelle immobile. Ici le
    # mouvement réduit se coupe d'une ligne, et chaque élément porte sa
    # géométrie finale en attribut — ce qu'affiche aussi un moteur sans CSS.
    f.style("".join(".d%d{fill:%s}.g%d{fill:%s}.t%d{fill:%s}"
                    % (k, teinte(t, 0.68), k, teinte(t, 0.84), k, t) for k, t in enumerate(teintes)))
    f.style(".m,.u{animation:%.2fs cubic-bezier(.33,1,.68,1) var(--t) both}"
            ".m{animation-name:m}.u{animation-name:u}"
            "@keyframes m{from{transform:scale(1,%.2f)}to{transform:scale(1,var(--h))}}"
            "@keyframes u{from{transform:translate(0,var(--d))}to{transform:translate(0,0)}}"
            % (montee, h_dalle))
    f.style(ANIM)
    f.style(SANS_ANIM % ".m,.u,.n")

    # Une journée vide est la même dalle partout : dessinée une fois, réutilisée.
    # Ses côtés montent un peu sous le dessus (voir SKY_DEBORD).
    bx, by = ecran(marge, marge, 0)
    droite, gauche, _ = _faces(marge, marge, SKY_DALLE + SKY_DEBORD / (SKY_CE * s), ecran)
    dessus = _faces(marge, marge, SKY_DALLE, ecran)[2]
    f.definis('<g id="v">' + "".join(
        '<polygon class="%s" points="%s"/>' % (c, _pts([(x - bx, y - by) for x, y in face]))
        for c, face in zip(("d0", "g0", "t0"), (droite, gauche, dessus))) + '</g>')

    # Ordre du peintre : du plus loin au plus proche de la caméra. La vague
    # part de la semaine la plus ancienne, avec un léger décalage par jour.
    ordre = sorted(cases, key=lambda c: ((c[2] + 0.5) * SKY_SN + (c[3] + 0.5) * SKY_CS, c[2]))
    for _, n, w, d in ordre:
        x0, y0 = w + marge, d + marge
        if n <= 0:
            ux, uy = ecran(x0, y0, 0)
            f += '<use href="#v" x="%.1f" y="%.1f"/>' % (ux, uy)
            continue
        k, z = _niveau(n, seuil), _hauteur(n, record)
        h = z * SKY_CE * s
        t = SKY_ATTENTE + ((w / max(1, semaines - 1)) * 0.36 + (d / 6) * 0.06) * SKY_DUREE
        rx, ry = ecran(x0 + SKY_CUBE, y0, 0)
        gx, gy = ecran(x0, y0 + SKY_CUBE, 0)
        f += (
            '<g style="--h:%.1f;--d:%.1fpx;--t:%.2fs">'
            '<g transform="translate(%.1f,%.1f) skewY(%.2f)"><rect class="d%d m" x="%.1f" '
            'y="%.4f" width="%.1f" height="%.4f" transform="scale(1,%.1f)"/></g>'
            '<g transform="translate(%.1f,%.1f) skewY(%.2f)"><rect class="g%d m" '
            'y="%.4f" width="%.1f" height="%.4f" transform="scale(1,%.1f)"/></g>'
            '<polygon class="t%d u" points="%s"/></g>'
            % (h, h - h_dalle, t,
               rx, ry, -pente, k, -l_droite - SKY_DEBORD, -1 - SKY_DEBORD / h,
               l_droite + SKY_DEBORD, 1 + SKY_DEBORD / h, h,
               gx, gy, pente, k, -1 - SKY_DEBORD / h, l_gauche, 1 + SKY_DEBORD / h, h,
               k, _pts(_faces(x0, y0, z, ecran)[2])))

    # Mois, sous l'arête avant, alignés à droite sur la première semaine de
    # chacun : ils débordent ainsi vers le vide en contrebas, jamais sur les
    # cubes des semaines suivantes.
    for w, lab in mois:
        x, y = ecran(w + 0.5, 7.2, 0)
        if x - 2 - f.largeur("mono", lab, corps_mois) < 10:
            continue
        f += '<g class="mois">%s</g>' % f.texte("mono", lab, corps_mois, x - 2, y + 11, ancre="end",
                                                  fill=p["discret"])

    f += blocs

    # Pied : ce que montre la carte, et la légende des niveaux.
    yp = H - 22
    bord = 26 if mobile else X0
    f += f.texte("mono", "12 mois · un cube par jour" if mobile else "12 derniers mois · un cube par jour",
                 10, bord, yp, fill=p["discret"])
    xd = W - bord
    f += f.texte("mono", "Plus", 10, xd, yp, ancre="end", fill=p["discret"])
    xd -= f.largeur("mono", "Plus", 10) + 8
    for k in range(4, -1, -1):
        xd -= 11
        f += '<rect class="leg" x="%.1f" y="%.1f" width="11" height="11" rx="2" fill="%s"/>' % (
            xd, yp - 9.5, teintes[k])
        xd -= 4
    f += f.texte("mono", "Moins", 10, xd - 4, yp, ancre="end", fill=p["discret"])
    return f.rendu()


# ---------------------------------------------------------- tableau de bord
#
# Les records, présentés comme les compteurs d'une voiture : deux grands
# cadrans dont l'aiguille pointe un record, un compteur kilométrique pour le
# total, un totalisateur partiel pour les trente derniers jours, deux petits
# cadrans annulaires. À l'ouverture, les aiguilles balaient toute l'échelle
# avant de se poser — le contrôle d'allumage d'un vrai tableau de bord.

def _echelle(v):
    """Graduation ronde : (pas entre deux graduations majeures, nombre
    d'intervalles). Le maximum est choisi pour que l'aiguille se pose vers les
    trois quarts de la course : un record doit avoir l'air d'en être un."""
    cible = max(v, 1) / 0.82
    for exposant in range(0, 12):
        for mantisse in (1, 2, 5):
            pas = mantisse * 10 ** exposant
            n = int(math.ceil(cible / float(pas)))
            # De 5 à 10 intervalles : avec 6 pour plancher, une cible entre
            # 20 et 25 (× 10^k) ne convenait à aucun pas — 11 intervalles de 2,
            # 5 de 5 — et le cadran retombait sur 0-8 pour une valeur de 182.
            if 5 <= n <= 10:
                return pas, n
    return 1, 8                 # valeurs de 0 à 3 : l'échelle minimale


CADRAN_DEBUT, CADRAN_COURSE = 135.0, 270.0   # degrés, sens horaire à l'écran


def _cadran(f, cx, cy, R, valeur, legende, detail, plein=False, depart=0.3, dehors=False):
    """Un grand cadran à aiguille. plein : les graduations portent le nombre
    entier (0, 200, 400…) comme un compteur de vitesse ; sinon le chiffre des
    centaines et un multiplicateur, comme un compte-tours."""
    p = f.p
    pas, n = _echelle(valeur)
    maxi = pas * n

    def angle(v):
        return CADRAN_DEBUT + CADRAN_COURSE * v / maxi

    o = [  # assise sombre, lunette d'or, fond, filet intérieur, guilloché du centre
         '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="5"/>'
         % (_n(cx), _n(cy), _n(R + 3.4), p["creux"]),
         '<circle cx="%s" cy="%s" r="%s" fill="url(#fc)" stroke="url(#lu)" stroke-width="2.4"/>'
         % (_n(cx), _n(cy), _n(R)),
         '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="1"/>'
         % (_n(cx), _n(cy), _n(R - 6.5), p["trait"]),
         '<use href="#gu" transform="translate(%s %s) scale(%s)" opacity="0.22"/>'
         % (_n(cx), _n(cy), _n(R * 0.38 / 50.0))]
    # arc de l'échelle, zone rouge sur le dernier cinquième
    rs = R - 13
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="1"/>'
             % (arc(cx, cy, rs, angle(0), angle(0.8 * maxi)), p["discret"]))
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="3.6"/>'
             % (arc(cx, cy, rs - 1.3, angle(0.8 * maxi), angle(maxi)), p["rouge"]))
    # graduations
    sous = 4 if str(pas)[0] == "2" else 5
    majeures, mineures = [], []
    for i in range(n * sous + 1):
        a = CADRAN_DEBUT + CADRAN_COURSE * i / (n * sous)
        grande = i % sous == 0
        x0, y0 = polaire(cx, cy, R - 16, a)
        x1, y1 = polaire(cx, cy, R - 16 - (0.085 * R if grande else 0.042 * R), a)
        (majeures if grande else mineures).append("M%.1f,%.1f L%.1f,%.1f" % (x0, y0, x1, y1))
    o.append('<path d="%s" stroke="%s" stroke-width="1.8" stroke-linecap="round"/>'
             % (" ".join(majeures), p["encre"]))
    o.append('<path d="%s" stroke="%s" stroke-width="0.9" opacity="0.75"/>'
             % (" ".join(mineures), p["doux"]))
    # chiffres
    plein = plein and maxi < 10000              # au-delà, « 120 000 » ne tient plus sur l'échelle
    facteur = 1 if plein else 10 ** int(math.floor(math.log10(pas)))
    corps_chiffre = R * (0.098 if plein else 0.118)
    h_chiffre = f.t.capitale("titre", corps_chiffre)
    poses = []                                  # (x, y, largeur) des chiffres, pour caler la valeur
    for i in range(n + 1):
        if plein and n > 6 and i % 2:
            continue
        v = i * pas
        etiquette = "%d" % (v // facteur)
        w_chiffre = f.largeur("titre", etiquette, corps_chiffre)
        # Le chiffre recule de sa propre demi-étendue le long du rayon : à 9 h
        # et à 3 h, « 200 » ou « 1000 » posés à distance fixe touchaient leur
        # graduation, et « —200 » se lisait « −200 ».
        a = math.radians(angle(v))
        recul = max(corps_chiffre * (1.0 if plein else 0.82),
                    abs(math.cos(a)) * w_chiffre / 2 + abs(math.sin(a)) * h_chiffre / 2 + 0.03 * R)
        x, y = polaire(cx, cy, R - 16 - 0.085 * R - recul, angle(v))
        f_ch = p["rouge"] if v >= 0.8 * maxi else p["encre"]
        o.append(f.texte("titre", etiquette, corps_chiffre, x, y + h_chiffre / 2, ancre="middle", fill=f_ch))
        poses.append((x, y, w_chiffre))
    if facteur != 1:
        o.append(f.texte("mono", "× %s" % fr(facteur), max(8, R * 0.066), cx, cy - R * 0.34,
                         ancre="middle", approche=0.8, fill=p["discret"]))
    # affichage : le record lui-même
    # Il se loge entre le premier et le dernier chiffre de l'échelle : au-delà
    # de quatre chiffres, le corps diminue pour ne pas les toucher.
    corps_valeur = R * 0.3
    base_valeur = cy + R * 0.52
    libre = 0.74 * R
    for x, y, w_chiffre in poses:
        # un chiffre de l'échelle à la hauteur de la valeur borne sa largeur
        if y + h_chiffre / 2 > base_valeur - f.t.capitale("titre", corps_valeur) and y - h_chiffre / 2 < base_valeur:
            libre = min(libre, 2 * (abs(x - cx) - w_chiffre / 2 - 0.035 * R))
    corps_valeur *= min(1.0, libre / f.largeur("titre", fr(valeur), corps_valeur))
    o.append(f.texte("titre", fr(valeur), corps_valeur, cx, base_valeur, ancre="middle", fill=p["o"],
                     cascade=(depart + 1.5, 0.06)))
    if dehors:
        o.append(f.texte("texte", legende.upper(), 11, cx, cy + R + 24, ancre="middle", approche=1.4,
                         fill=p["doux"]))
        o.append(f.texte("mono", detail, 9.4, cx, cy + R + 40, ancre="middle", fill=p["discret"]))
    else:
        o.append(f.texte("texte", legende.upper(), R * 0.08, cx, cy + R * 0.71, ancre="middle",
                         approche=R * 0.011, fill=p["doux"]))
        # la période s'allonge d'une année dès qu'elle n'est plus de l'année en
        # cours : elle rétrécit plutôt que de mordre sur le filet du cadran
        corps_detail = R * 0.068
        corps_detail *= min(1.0, 0.86 * R / f.largeur("mono", detail, corps_detail))
        o.append(f.texte("mono", detail, corps_detail, cx, cy + R * 0.825, ancre="middle", fill=p["discret"]))
    # aiguille : dessinée vers +x, posée par rotation ; l'attribut porte
    # l'angle final, l'animation balaie l'échelle puis y revient
    L = R - 24
    o.append('<g transform="translate(%s %s)">'
             '<g class="ag" transform="rotate(%.2f)" style="--a:%.2fdeg;--t:%.2fs">'
             '<path d="M-%.1f,-2.6 L%.1f,-0.6 L%.1f,0.6 L-%.1f,2.6 Z" fill="%s"/>'
             '<path d="M-%.1f,0 L%.1f,0 L%.1f,0.6 L-%.1f,2.6 Z" fill="%s"/></g>'
             '<circle r="%.1f" fill="url(#my)" stroke="%s" stroke-width="0.8"/>%s</g>'
             % (_n(cx), _n(cy), angle(valeur), angle(valeur), depart,
                R * 0.14, L, L, R * 0.14, p["rouge"],
                R * 0.14, L, L, R * 0.14, p["rouge_bas"],
                R * 0.085, p["o_bas"], pique(0, 0.2, R * 0.095, p["fond"])))
    # reflet du verre : un croissant clair en haut à gauche
    r_v = R - 9
    x0, y0 = polaire(cx, cy, r_v, 200)
    x1, y1 = polaire(cx, cy, r_v, 318)
    o.append('<path d="M%.1f,%.1f A%s,%s 0 0 1 %.1f,%.1f A%s,%s 0 0 0 %.1f,%.1f Z" fill="url(#vr)"/>'
             % (x0, y0, _n(r_v), _n(r_v), x1, y1, _n(r_v * 1.55), _n(r_v * 1.55), x0, y0))
    return o


def _anneau(f, cx, cy, r, fraction, valeur, legende, detail, depart=0.6):
    """Petit cadran annulaire : un arc d'or qui se trace jusqu'à `fraction`."""
    p = f.p
    tour = 2 * math.pi * r
    trace = max(0.0, min(1.0, fraction)) * tour
    corps = r * 0.6
    corps *= min(1.0, 1.5 * r / f.largeur("titre", valeur, corps))
    return [
        '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="5"/>'
        % (_n(cx), _n(cy), _n(r), p["trait"]),
        '<circle class="an" cx="%s" cy="%s" r="%s" fill="none" stroke="url(#lu)" stroke-width="5" '
        'stroke-linecap="round" stroke-dasharray="%.1f %.1f" transform="rotate(-90 %s %s)" '
        'style="--l:%.1f;--t:%.2fs"/>'
        % (_n(cx), _n(cy), _n(r), trace, tour, _n(cx), _n(cy), trace, depart),
        f.texte("titre", valeur, corps, cx, cy + f.t.capitale("titre", corps) / 2, ancre="middle",
                fill=p["encre"], cascade=(depart + 0.5, 0.06)),
        f.texte("texte", legende.upper(), 10, cx, cy + r + 21, ancre="middle", approche=1.3, fill=p["doux"]),
        f.texte("mono", detail, 8.8, cx, cy + r + 35, ancre="middle", fill=p["discret"]),
    ]


def _compteur(f, cx, y, nombre, cases, lc, hc, depart=0.5, cle="k"):
    """Compteur à rouleaux centré en cx, haut en y : au moins `cases` rouleaux
    de lc × hc. Chaque rouleau porte son chiffre final à sa place ; l'animation
    le fait partir de zéro, les rouleaux de droite tournant davantage.

    Un nombre plus long que prévu reçoit les rouleaux qu'il lui faut — un
    compteur qui perd son chiffre de tête affiche un nombre faux — et ils
    rétrécissent pour garder la largeur prévue."""
    p = f.p
    ecart = 3.0
    prevue = cases * lc + (cases - 1) * ecart
    cases = max(cases, len("%d" % nombre))
    texte = ("%d" % nombre).rjust(cases, "0")
    premier = len(texte) - len("%d" % nombre)        # zéros de tête : éteints
    serre = min(1.0, (prevue * 1.18 - (cases - 1) * ecart) / (cases * lc))
    lc, hc = lc * serre, hc * serre
    large = cases * lc + (cases - 1) * ecart
    x0 = cx - large / 2.0
    corps = hc * 0.74
    ech = corps / 1000.0
    base = hc / 2.0 + f.t.capitale("titre", corps) / 2.0
    atlas = f.t.polices["titre"]["g"]
    f.definis('<clipPath id="c%s"><rect width="%s" height="%s"/></clipPath>' % (cle, _n(lc), _n(hc)))
    f.definis('<linearGradient id="o%s" x1="0" y1="0" x2="0" y2="1">'
              '<stop offset="0" stop-color="%s" stop-opacity="0.85"/>'
              '<stop offset="0.3" stop-color="%s" stop-opacity="0"/>'
              '<stop offset="0.7" stop-color="%s" stop-opacity="0"/>'
              '<stop offset="1" stop-color="%s" stop-opacity="0.85"/></linearGradient>'
              % (cle, p["creux"], p["creux"], p["creux"], p["creux"]))
    o = ['<rect x="%s" y="%s" width="%s" height="%s" rx="5" fill="%s" stroke="%s" stroke-width="1"/>'
         % (_n(x0 - 5), _n(y - 5), _n(large + 10), _n(hc + 10), p["creux"], p["trait"])]
    for i, chiffre in enumerate(texte):
        x = x0 + i * (lc + ecart)
        eteint = i < premier
        rang = i - premier                      # 0 pour le premier chiffre significatif
        tours = 0 if eteint else min(rang, 2)   # les rouleaux de droite tournent plus
        pas_total = 0 if eteint else int(chiffre) + 10 * tours
        uses = []
        for j in range(pas_total + 1):
            c = "%d" % (j % 10) if not eteint else chiffre
            decal = (pas_total - j) * hc / ech
            uses.append('<use href="#%s" x="%s"%s/>' % (
                f.t.ref("titre", c), _n((lc / ech - atlas[c][0]) / 2.0),
                ' y="-%s"' % _n(decal) if decal else ""))
        o.append('<g transform="translate(%s %s)" clip-path="url(#c%s)">'
                 '<rect width="%s" height="%s" fill="%s"/>'
                 '<g%s><g transform="translate(0 %s) scale(%s)" fill="%s"%s>%s</g></g></g>'
                 % (_n(x), _n(y), cle, _n(lc), _n(hc), p["surface"],
                    "" if eteint or not pas_total else
                    ' class="od" style="--n:%spx;--t:%.2fs;--u:%.2fs"' % (_n(pas_total * hc), depart + 0.07 * rang,
                                                                         1.1 + 0.32 * tours + 0.05 * int(chiffre)),
                    _n(base), ("%.5f" % ech).rstrip("0"), p["discret"] if eteint else p["encre"],
                    ' opacity="0.45"' if eteint else "", "".join(uses)))
    # ombres haute et basse : le bombé des rouleaux
    o.append('<rect x="%s" y="%s" width="%s" height="%s" fill="url(#o%s)" pointer-events="none"/>'
             % (_n(x0), _n(y), _n(large), _n(hc), cle))
    return o


def carte_bord(r, p, mobile=False):
    semaine, s1, s2 = r["semaine"]
    ref = max(r["jours"])
    W, H = (450, 690) if mobile else (900, 440)
    # une décimale tant qu'elle se lit ; au-delà de cent, l'entier suffit
    moyenne = decimal(r["moyenne"]) if round(r["moyenne"], 1) < 100 else fr(round(r["moyenne"]))
    f = Feuille(W, H, p, "Tableau de bord des contributions",
                "Meilleure semaine : %s %s (%s). Meilleur mois : %s (%s). "
                "%s %s sur %s. %s %s par jour actif. "
                "%s %s sur les 30 derniers jours. Total : %s."
                % (fr(semaine), pluriel(semaine, "contribution"), periode(s1, s2, ref),
                   fr(r["mois_total"]), mois_fr(r["mois"]),
                   fr(r["actifs"]), "jours actifs" if r["actifs"] > 1 else "jour actif", fr(r["ecoules"]),
                   moyenne, "contributions" if r["moyenne"] >= 2 else "contribution",
                   fr(r["trente"]), pluriel(r["trente"], "contribution"), fr(r["total"])))
    cadre(f, "Tableau de bord", horodatage(r["calcule"], court=mobile))
    f.definis('<linearGradient id="lu" x1="0" y1="0" x2="1" y2="1">'
              '<stop offset="0" stop-color="%s"/><stop offset="0.45" stop-color="%s"/>'
              '<stop offset="1" stop-color="%s"/></linearGradient>' % (p["o_haut"], p["o"], p["o_bas"]))
    f.definis('<radialGradient id="fc" cx="0.5" cy="0.42" r="0.62">'
              '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>'
              % (p["surface"], p["creux"]))
    f.definis('<radialGradient id="my" cx="0.38" cy="0.32" r="0.8">'
              '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>'
              % (p["o_haut"], p["o_bas"]))
    f.definis('<linearGradient id="vr" x1="0" y1="0" x2="0.6" y2="1">'
              '<stop offset="0" stop-color="#FFFFFF" stop-opacity="%s"/>'
              '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
              % ("0.07" if p["nom"] == "dark" else "0.5"))
    f.definis('<path id="gu" d="%s" fill="none" stroke="%s" stroke-width="1.1"/>'
              % (rosace(50, couches=2, k=14), p["o"]))
    f.style(ANIM)
    f.style(".ag{animation:ag 2.3s cubic-bezier(.3,.05,.25,1) var(--t) both}"
            "@keyframes ag{0%%{transform:rotate(%sdeg)}42%%{transform:rotate(%sdeg)}"
            "100%%{transform:rotate(var(--a))}}"
            % (_n(CADRAN_DEBUT), _n(CADRAN_DEBUT + CADRAN_COURSE)))
    f.style(".an{animation:an 1.5s cubic-bezier(.2,.8,.2,1) var(--t) both}"
            "@keyframes an{from{stroke-dashoffset:var(--l)}}")
    f.style(".od{animation:od var(--u) cubic-bezier(.12,.75,.2,1) var(--t) both}"
            "@keyframes od{from{transform:translateY(var(--n))}}")
    f.style(SANS_ANIM % ".n,.ag,.an,.od")

    part = r["actifs"] / float(max(1, r["ecoules"]))
    if mobile:
        R = 98
        f += _cadran(f, 118, 166, R, semaine, "Meilleure semaine", periode(s1, s2, ref),
                     depart=0.3, dehors=True)
        f += _cadran(f, 332, 166, R, r["mois_total"], "Meilleur mois", mois_fr(r["mois"]),
                     plein=True, depart=0.5, dehors=True)
        f += f.texte("mono-gras", "COMPTEUR", 9.5, 225, 346, ancre="middle", approche=3, fill=p["o"])
        f += _compteur(f, 225, 358, r["total"], 6, 36, 48, depart=0.7, cle="k")
        f += f.texte("mono", "contributions depuis le %s" % jour_fr(r["premier"]), 9.6, 225, 430,
                     ancre="middle", fill=p["discret"])
        f += f.texte("mono-gras", "30 DERNIERS JOURS", 9.5, 225, 468, ancre="middle", approche=3, fill=p["o"])
        f += _compteur(f, 225, 480, r["trente"], max(4, len("%d" % r["trente"])), 27, 36, depart=0.9, cle="p")
        f += _anneau(f, 118, 590, 36, part, "%d %%" % round(100 * part), "Jours actifs",
                     "%s sur %s" % (fr(r["actifs"]), fr(r["ecoules"])), depart=1.0)
        f += _anneau(f, 332, 590, 36, min(1.0, r["moyenne"] / max(1.0, float(r["record"])) * 4),
                     moyenne, "Par jour actif", "en moyenne", depart=1.15)
    else:
        R = 130
        f += _cadran(f, 186, 244, R, semaine, "Meilleure semaine", periode(s1, s2, ref),
                     depart=0.3)
        f += _cadran(f, 714, 244, R, r["mois_total"], "Meilleur mois", mois_fr(r["mois"]),
                     plein=True, depart=0.5)
        f += _anneau(f, 393, 144, 34, part, "%d %%" % round(100 * part), "Jours actifs",
                     "%s sur %s" % (fr(r["actifs"]), fr(r["ecoules"])), depart=1.0)
        f += _anneau(f, 507, 144, 34, min(1.0, r["moyenne"] / max(1.0, float(r["record"])) * 4),
                     moyenne, "Par jour actif", "en moyenne", depart=1.15)
        f += f.texte("mono-gras", "COMPTEUR", 8.8, 450, 250, ancre="middle", approche=3, fill=p["o"])
        f += _compteur(f, 450, 260, r["total"], 6, 30, 40, depart=0.7, cle="k")
        f += f.texte("mono", "contributions depuis le %s" % jour_fr(r["premier"]), 8.8, 450, 322,
                     ancre="middle", fill=p["discret"])
        f += f.texte("mono-gras", "30 DERNIERS JOURS", 8.8, 450, 354, ancre="middle", approche=3, fill=p["o"])
        f += _compteur(f, 450, 364, r["trente"], max(4, len("%d" % r["trente"])), 22, 30, depart=0.9, cle="p")
    return f.rendu()


CARTES = (("skyline", carte_skyline), ("bord", carte_bord))


def rendus(r):
    """(nom de fichier, SVG) pour chaque carte, chaque mise en page, chaque thème."""
    for nom, rendu in CARTES:
        for mobile in (False, True):
            for p in PALETTES:
                svg = rendu(r, p, mobile)
                yield "%s%s-%s.svg" % (nom, "-m" if mobile else "", p["nom"]), svg
                # Transition : le README encore en ligne pointe sur records-*.svg.
                # À retirer dès que le nouveau README est publié.
                if nom == "bord" and not mobile:
                    yield "records-%s.svg" % p["nom"], svg


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    dossier = args[0]
    jours = calendrier_demo() if "--demo" in sys.argv else calendrier()
    r = stats(jours)
    os.makedirs(dossier, exist_ok=True)
    for nom, svg in rendus(r):
        chemin = os.path.join(dossier, nom)
        with open(chemin, "w", encoding="utf-8") as fichier:
            fichier.write(svg)
        print("écrit :", chemin)
    # Trace des dernières journées : si un chiffre paraît faux un jour, cette
    # ligne dit tout de suite ce que GitHub a renvoyé, sans avoir à deviner.
    print("dernières journées vues : " +
          " · ".join("%s=%d" % (k[5:], jours[k]) for k in sorted(jours)[-6:]))
    n, d1, d2 = r["courante"]
    print("total %d · série %d (%s → %s) · plus longue %d · record %d le %s · "
          "%d jours actifs · %.1f/jour · meilleure semaine %d · 30 jours %d"
          % (r["total"], n, d1, d2, r["longue"][0], r["record"], r["record_date"],
             r["actifs"], r["moyenne"], r["semaine"][0], r["trente"]))


if __name__ == "__main__":
    main()
