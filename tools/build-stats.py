#!/usr/bin/env python3
"""Calcule toutes les statistiques du profil et en fait des cartes SVG.

Trois cartes, deux thèmes chacune, toutes issues d'UNE seule lecture du
calendrier de contributions public de GitHub :

    serie      contributions totales · série actuelle · plus longue série
    records    record en une journée · jours actifs · moyenne · meilleur mois
    activite   graphique des 90 derniers jours

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
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

LOGIN = os.environ.get("LOGIN") or "FarddownYG"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
UA = "FarddownYG-profile-stats"

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
ABBR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]
NNBSP = " "  # espace fine insécable : séparateur de milliers français
FENETRE = 90      # jours affichés par le graphique d'activité


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
    """Chemin principal : l'API GraphQL, exacte et stable."""
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
    """Filet de sécurité : la page publique du calendrier, sans authentification.
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
        mn = re.search(r"(\d+)", texte.replace(NNBSP, "").replace(" ", "").replace(" ", ""))
        out[jour] = int(mn.group(1)) if mn else 0
    if not out:
        raise RuntimeError("calendrier illisible")
    return out


def calendrier():
    """Toutes les journées depuis la création du compte, fusionnées par année.
    GitHub plafonne chaque requête à un an, d'où le découpage."""
    debut, aujourdhui = compte_cree_le(), date.today()
    jours, erreurs = {}, []
    an = debut.year
    while an <= aujourdhui.year:
        d = max(debut, date(an, 1, 1))
        f = min(aujourdhui, date(an, 12, 31))
        for source in (via_graphql, via_page):
            try:
                jours.update(source(d, f))
                break
            except Exception as e:
                erreurs.append("%d/%s : %s" % (an, source.__name__, e))
        an += 1
    if not jours:
        raise SystemExit("échec de récupération, cartes inchangées :\n  " + "\n  ".join(erreurs))
    return {k: v for k, v in jours.items() if k <= aujourdhui.isoformat()}


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
    Une journée encore vide ne casse pas la série en cours : elle n'est pas
    finie. On part donc d'hier si aujourd'hui est à zéro — c'est la
    convention de GitHub et des compteurs de série usuels."""
    aujourdhui = date.today()
    depart = aujourdhui if jours.get(aujourdhui.isoformat(), 0) > 0 else aujourdhui - timedelta(days=1)
    n, d = 0, depart
    while jours.get(d.isoformat(), 0) > 0:
        n += 1
        d -= timedelta(days=1)
    courante = (n, (depart - timedelta(days=n - 1)).isoformat(), depart.isoformat()) if n else (0, None, None)

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

    # Moyenne glissante sur 7 jours plutôt que valeurs brutes : une journée
    # record à 254 contre des journées ordinaires à 5-15 écrase la courbe et
    # la rend illisible. Le lissage garde la forme réelle de l'activité ; le
    # record du jour, lui, a sa place sur la carte des records.
    fin = date.today()

    def moy7(d):
        return sum(jours.get((d - timedelta(days=k)).isoformat(), 0) for k in range(7)) / 7.0

    fenetre = [(fin - timedelta(days=i), moy7(fin - timedelta(days=i)))
               for i in range(FENETRE - 1, -1, -1)]

    return {
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
        "fenetre": fenetre,
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

SPADE = ("M100,8 C96,34 60,64 42,92 C28,114 26,132 34,148 C44,166 70,172 86,158 "
         "C92,152 96,146 97,140 C95,172 86,196 68,212 C64,216 66,220 71,220 "
         "L129,220 C134,220 136,216 132,212 C114,196 105,172 103,140 "
         "C104,146 108,152 114,158 C130,172 156,166 166,148 C174,132 172,114 158,92 "
         "C140,64 104,34 100,8 Z")


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


def carte_serie(r, p):
    n, d1, d2 = r["courante"]
    ln, l1, l2 = r["longue"]
    o = cadre(900, 200, "Série", p, r)
    # tuile de gauche et de droite
    o += tuile(150, fr(r["total"]), "Contributions totales",
               "depuis le %s" % jour_fr(r["premier"]), p)
    o += tuile(750, fr(ln), "Plus longue série",
               "%s – %s" % (court(l1), court(l2)) if ln else "—", p)
    o.append('  <path d="M300,84 V178" stroke="%s" stroke-width="1" opacity="0.75"/>' % p["rule"])
    o.append('  <path d="M600,84 V178" stroke="%s" stroke-width="1" opacity="0.75"/>' % p["rule"])
    # tuile centrale : anneau + pique, la série en cours est le chiffre vivant
    o.append('  <circle cx="450" cy="108" r="32" fill="none" stroke="%s" stroke-width="3.5"/>'
             % p["gold"])
    o.append('  <path d="%s" transform="translate(444,58) scale(0.055)" fill="%s"/>'
             % (SPADE, p["gold"]))
    o.append('  <text x="450" y="120" text-anchor="middle" font-family="%s" font-size="34" '
             'font-weight="700" fill="%s">%s</text>' % (SANS, p["text"], fr(n)))
    o.append('  <text x="450" y="154" text-anchor="middle" font-family="%s" font-size="12" '
             'fill="%s">Série actuelle</text>' % (SANS, p["gold"]))
    o.append('  <text x="450" y="174" text-anchor="middle" font-family="%s" font-size="10.5" '
             'fill="%s">%s</text>'
             % (MONO, p["dim"], esc("%s – %s" % (court(d1), court(d2)) if n else "—")))
    o.append('</svg>')
    return "\n".join(o) + "\n"


def carte_records(r, p):
    o = cadre(900, 200, "Records", p, r)
    tuiles = [
        (fr(r["record"]), "Record en une journée", jour_fr(r["record_date"]), True),
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


def carte_activite(r, p):
    W, H = 900, 280
    X0, X1, Y0, Y1 = 60, 872, 72, 226
    pts = r["fenetre"]
    haut = max(1, max(v for _, v in pts))
    pas = (X1 - X0) / (len(pts) - 1)

    def xy(i, v):
        return (X0 + i * pas, Y1 - (v / haut) * (Y1 - Y0))

    o = cadre(W, H, "Activité", p, r)
    # grille et graduations
    for frac in (0, 0.5, 1):
        y = Y1 - frac * (Y1 - Y0)
        o.append('  <path d="M%d,%.1f H%d" stroke="%s" stroke-width="1"/>' % (X0, y, X1, p["grid"]))
        o.append('  <text x="%d" y="%.1f" text-anchor="end" font-family="%s" font-size="10" '
                 'fill="%s">%s</text>' % (X0 - 10, y + 3.5, MONO, p["dim"], fr(round(haut * frac))))
    # aire puis ligne
    coords = [xy(i, v) for i, (_, v) in enumerate(pts)]
    aire = "M%.1f,%d " % (coords[0][0], Y1) + " ".join("L%.1f,%.1f" % c for c in coords) + \
           " L%.1f,%d Z" % (coords[-1][0], Y1)
    o.append('  <path d="%s" fill="%s" fill-opacity="0.13"/>' % (aire, p["gold"]))
    o.append('  <path d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
             % ("M" + " L".join("%.1f,%.1f" % c for c in coords), p["gold"]))
    # sommet de la fenêtre, marqué
    im = max(range(len(pts)), key=lambda i: pts[i][1])
    if pts[im][1] > 0:
        mx, my = coords[im]
        o.append('  <circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>' % (mx, my, p["text"]))
        o.append('  <text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" font-size="10.5" '
                 'fill="%s">%s</text>'
                 % (min(max(mx, X0 + 20), X1 - 20), my - 11, MONO, p["text"],
                    ("%.1f" % pts[im][1]).replace(".", ",")))
    # étiquettes de mois
    vus = set()
    for i, (d, _) in enumerate(pts):
        if d.month not in vus and (i == 0 or d.day <= 7):
            vus.add(d.month)
            o.append('  <text x="%.1f" y="%d" text-anchor="middle" font-family="%s" font-size="10" '
                     'fill="%s">%s</text>' % (xy(i, 0)[0], Y1 + 22, MONO, p["dim"], ABBR[d.month - 1]))
    o.append('  <text x="%d" y="%d" text-anchor="end" font-family="%s" font-size="10.5" fill="%s">'
             'moyenne glissante sur 7 jours · %d derniers jours</text>'
             % (X1, Y1 + 46, MONO, p["muted"], len(pts)))
    o.append('</svg>')
    return "\n".join(o) + "\n"


CARTES = (("serie", carte_serie), ("records", carte_records), ("activite", carte_activite))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    dossier = args[0]
    r = stats(calendrier_demo() if "--demo" in sys.argv else calendrier())
    os.makedirs(dossier, exist_ok=True)
    for nom, rendu in CARTES:
        for suffixe, pal in (("dark", DARK), ("light", LIGHT)):
            chemin = os.path.join(dossier, "%s-%s.svg" % (nom, suffixe))
            open(chemin, "w", encoding="utf-8").write(rendu(r, pal))
            print("écrit :", chemin)
    n = r["courante"][0]
    print("total %d · série %d · plus longue %d · record %d le %s · %d jours actifs · %.1f/jour"
          % (r["total"], n, r["longue"][0], r["record"], r["record_date"],
             r["actifs"], r["moyenne"]))


if __name__ == "__main__":
    main()
