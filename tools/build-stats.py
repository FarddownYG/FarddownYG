#!/usr/bin/env python3
"""Calcule les records de contributions et en fait deux cartes SVG (dark + light).

Aucun service tiers : les chiffres viennent du calendrier de contributions
public de GitHub, via l'API GraphQL si un jeton est disponible, sinon par
lecture de la page publique. Les cartes servies par des instances publiques
gratuites tombent régulièrement ; celle-ci ne dépend que de GitHub.

Usage :
    build-stats.py sortie-dark.svg sortie-light.svg [--demo]

--demo génère des données synthétiques : sert à vérifier la mise en page
sans accès réseau. Ne jamais l'utiliser en production.

En cas d'échec réseau, le script sort en erreur SANS écrire : une carte
existante n'est jamais remplacée par une carte vide.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

LOGIN = os.environ.get("LOGIN") or "FarddownYG"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
UA = "FarddownYG-profile-stats"

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
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
        return date.today().replace(month=1, day=1) - timedelta(days=365 * 3)


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
        raise SystemExit("échec de récupération, carte inchangée :\n  " + "\n  ".join(erreurs))
    return {k: v for k, v in jours.items() if k <= aujourdhui.isoformat()}


def calendrier_demo():
    import random
    random.seed(7)
    fin = date.today()
    out = {}
    for i in range(215):
        j = fin - timedelta(days=i)
        n = 0 if random.random() < 0.31 else random.choice([1, 2, 3, 4, 5, 7, 9, 12, 18])
        if i == 96:
            n = 47
        if i < 30:
            n = max(n, 1)
        out[j.isoformat()] = n
    return out


# ------------------------------------------------------------------- calculs

def records(jours):
    actifs = {k: v for k, v in jours.items() if v > 0}
    total = sum(jours.values())
    if not actifs:
        raise SystemExit("aucune contribution, carte inchangée")

    date_record = max(actifs, key=lambda k: actifs[k])
    record = actifs[date_record]

    par_mois = {}
    for k, v in jours.items():
        par_mois[k[:7]] = par_mois.get(k[:7], 0) + v
    meilleur_mois = max(par_mois, key=lambda k: par_mois[k])

    premier = min(jours)
    etendue = (date.today() - date.fromisoformat(premier)).days + 1

    return {
        "record": record,
        "record_date": date_record,
        "actifs": len(actifs),
        "etendue": etendue,
        "moyenne": total / len(actifs),
        "mois": meilleur_mois,
        "mois_total": par_mois[meilleur_mois],
        "total": total,
    }


def fr(n):
    return "{:,}".format(int(n)).replace(",", NNBSP)


def jour_fr(iso):
    d = date.fromisoformat(iso)
    return "%d %s %d" % (d.day, MOIS[d.month - 1][:4] + ("." if len(MOIS[d.month - 1]) > 4 else ""),
                         d.year)


def mois_fr(iso):
    a, m = iso.split("-")
    return "%s %s" % (MOIS[int(m) - 1], a)


# ------------------------------------------------------------------- rendu

DARK = dict(bg="#0B0E13", border="#2A3140", gold="#C8A96A", text="#E8EAF0",
            muted="#9AA3B2", dim="#6B7280", rule="#2A3140")
LIGHT = dict(bg="#FBF7EE", border="#D9D2C2", gold="#8C6E33", text="#14171C",
             muted="#5F6672", dim="#8B857A", rule="#E2DACA")

SANS = "'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','Cascadia Code','SF Mono',Consolas,'DejaVu Sans Mono',monospace"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def carte(r, p):
    tuiles = [
        (fr(r["record"]), "Record en une journée", jour_fr(r["record_date"]), True),
        (fr(r["actifs"]), "Jours actifs", "sur %s jours" % fr(r["etendue"]), False),
        (("%.1f" % r["moyenne"]).replace(".", ","), "Par jour actif", "en moyenne", False),
        (fr(r["mois_total"]), "Meilleur mois", mois_fr(r["mois"]), False),
    ]
    o = ['<svg viewBox="0 0 900 200" width="900" height="200" '
         'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Records de contributions">',
         '  <rect x="0.7" y="0.7" width="898.6" height="198.6" rx="10" fill="%s" stroke="%s" '
         'stroke-width="1.4"/>' % (p["bg"], p["border"]),
         '  <text x="28" y="40" font-family=%s font-size="11" letter-spacing="3" fill="%s">'
         '// RECORDS</text>' % ('"%s"' % MONO, p["gold"])]
    for i, (val, lab, det, phare) in enumerate(tuiles):
        cx = 24 + 213 * i + 106.5
        if i:
            x = 24 + 213 * i
            o.append('  <path d="M%g,84 V178" stroke="%s" stroke-width="1" opacity="0.75"/>'
                     % (x, p["rule"]))
        o.append('  <text x="%g" y="128" text-anchor="middle" font-family=%s font-size="42" '
                 'font-weight="700" fill="%s">%s</text>'
                 % (cx, '"%s"' % SANS, p["gold"] if phare else p["text"], esc(val)))
        o.append('  <text x="%g" y="154" text-anchor="middle" font-family=%s font-size="12" '
                 'fill="%s">%s</text>' % (cx, '"%s"' % SANS, p["muted"], esc(lab)))
        o.append('  <text x="%g" y="174" text-anchor="middle" font-family=%s font-size="10.5" '
                 'fill="%s">%s</text>' % (cx, '"%s"' % MONO, p["dim"], esc(det)))
    o.append('</svg>')
    return "\n".join(o) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        raise SystemExit(__doc__)
    jours = calendrier_demo() if "--demo" in sys.argv else calendrier()
    r = records(jours)
    for chemin, pal in zip(args, (DARK, LIGHT)):
        d = os.path.dirname(chemin)
        if d:
            os.makedirs(d, exist_ok=True)
        open(chemin, "w", encoding="utf-8").write(carte(r, pal))
        print("écrit :", chemin)
    print("record %d le %s · %d jours actifs sur %d · %.1f/jour actif · meilleur mois %s (%d)"
          % (r["record"], r["record_date"], r["actifs"], r["etendue"],
             r["moyenne"], r["mois"], r["mois_total"]))


if __name__ == "__main__":
    main()
