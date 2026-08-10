#!/usr/bin/env python3
"""Génère header-dark.svg et header-light.svg : même géométrie, deux palettes.
Animations SMIL/CSS uniquement, zéro JS, zéro ressource externe."""
import sys

CELL = 7.75          # largeur d'un caractère du terminal (mono 13px)
PILL_CELL = 8.7      # largeur d'un caractère des pills (mono 12px + letter-spacing)
DUR = 16.0           # durée totale du cycle
CHAR = 0.075         # durée de frappe d'un caractère

SPADE = ("M100,8 C96,34 60,64 42,92 C28,114 26,132 34,148 C44,166 70,172 86,158 "
         "C92,152 96,146 97,140 C95,172 86,196 68,212 C64,216 66,220 71,220 "
         "L129,220 C134,220 136,216 132,212 C114,196 105,172 103,140 "
         "C104,146 108,152 114,158 C130,172 156,166 166,148 C174,132 172,114 158,92 "
         "C140,64 104,34 100,8 Z")

# ---------- contenu du terminal ----------
# (type, texte, texte secondaire éventuel)
LINES = [
    ("cmd", "whoami"),
    ("out", "ingénieur cybersécurité · fondateur de Classor ·", "classor.fr"),
    ("cmd", "ls ~/build"),
    ("out", "jeux/  logiciels/  outils/"),
    ("cmd", "cat ~/.origin"),
    ("out", "depuis toujours : coder des outils, en vivre"),
    ("cmd", "cat creed"),
    ("creed", "« celui qui tire doit être prêt à recevoir la balle »", "— Lelouch, Code Geass"),
]
# instants de départ (secondes) pour chaque ligne, dans l'ordre
STARTS = [0.70, 1.45, 1.90, 3.05, 3.45, 4.85, 5.25, 6.40]
CURSOR_AT = 6.55

BASE_Y = [350, 374, 398, 422, 446, 470, 494, 518]
PY = 196            # ordonnée de la rangée de pills
TX = 84.0            # marge gauche du contenu du terminal

DARK = dict(
    name="dark",
    bg=("#0C0F15", "#10141D", "#151B28"),
    card_stroke="#2A3140", inner_stroke="#232A36", inner_op="0.5",
    index="#E8EAF0", pip="#C8A96A",
    steel=("#EEF1F6", "#B9C2D0", "#8A93A5", "#A7B0C0"),
    edge=(("#FFFFFF", "0.9"), ("#7C8698", "0.6")),
    steel_text=("#F4F6FA", "#C4CCD9", "#97A1B2"),
    kicker="#C8A96A", rule="#2A3140", pulse="#C8A96A",
    pill_stroke="#3A4150", pill_fill="#E8EAF0", pill_fill_op="0.04",
    pill_icon="#C8A96A", pill_text="#C6CCD8",
    sheen_op="0.55", glow=("#C8A96A", "0.14"),
    emblem_filter='<feDropShadow dx="0" dy="0" stdDeviation="14" flood-color="#C8A96A" flood-opacity="0.16"/>',
    card_shadow=None,
)

LIGHT = dict(
    name="light",
    bg=("#FAF7EE", "#F6F1E6", "#F0E9D9"),
    card_stroke="#D9D2C2", inner_stroke="#E4DECF", inner_op="0.9",
    index="#14171C", pip="#8C6E33",
    steel=("#1E232D", "#2F3642", "#454E5C", "#333B47"),
    edge=(("#B8934A", "0.9"), ("#6B5527", "0.6")),
    steel_text=("#171B22", "#2A3038", "#3E4654"),
    kicker="#7A5E28", rule="#DDD6C6", pulse="#B8934A",
    pill_stroke="#D3CCBB", pill_fill="#14171C", pill_fill_op="0.03",
    pill_icon="#8C6E33", pill_text="#3A414D",
    sheen_op="0.3", glow=("#B8934A", "0.12"),
    emblem_filter='<feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#3A2F1B" flood-opacity="0.2"/>',
    card_shadow='<feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#332A18" flood-opacity="0.15"/>',
)

# couleurs du terminal : identiques dans les deux thèmes
T_BG, T_STROKE, T_SEP = "#0C0F14", "#232A36", "#202733"
T_TITLE, T_PROMPT, T_CMD = "#7E8794", "#C8A96A", "#E8EAF0"
T_OUT, T_CREED, T_ATTR = "#A3C2A8", "#E8EAF0", "#6B7280"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def typewriter(clip_id, y, n, t0):
    """clipPath animé : n caractères frappés à partir de t0 secondes."""
    total = n * CELL
    vals = ["0"] + ["%.2f" % (CELL * (i + 1)) for i in range(n)] + ["%.2f" % total]
    kts = ["0"] + ["%.5f" % ((t0 + i * CHAR) / DUR) for i in range(n)] + ["1"]
    return ('    <clipPath id="%s"><rect x="%.1f" y="%.1f" height="18" width="0">\n'
            '      <animate attributeName="width" calcMode="discrete" dur="%gs" '
            'repeatCount="1" fill="freeze"\n'
            '        values="%s"\n        keyTimes="%s"/>\n'
            '    </rect></clipPath>' % (clip_id, TX, y - 12, DUR, ";".join(vals), ";".join(kts)))


def reveal(t0, to=1.0):
    return ('<animate attributeName="opacity" calcMode="discrete" dur="%gs" repeatCount="1" '
            'fill="freeze" values="0;%s;%s" keyTimes="0;%.5f;1"/>' % (DUR, to, to, t0 / DUR))


def build(p):
    o = []
    a = o.append
    a('<svg viewBox="0 0 1000 580" fill="none" xmlns="http://www.w3.org/2000/svg" '
      'role="img" aria-labelledby="hTitle">')
    a('  <title id="hTitle">Yanis — l’as de pique : ingénieur cybersécurité, fondateur de '
      'Classor (classor.fr), développeur de jeux et de logiciels</title>')
    a('')
    a('  <defs>')
    a('    <!-- La pique-lame : tracé maître réutilisé (emblème, index de coins, pips) -->')
    a('    <path id="spade" d="%s"/>' % SPADE)
    a('    <clipPath id="spadeClip"><use href="#spade"/></clipPath>')
    a('')
    a('    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">')
    for off, c in zip(("0", "0.55", "1"), p["bg"]):
        a('      <stop offset="%s" stop-color="%s"/>' % (off, c))
    a('    </linearGradient>')
    a('    <linearGradient id="spadeSteel" x1="0" y1="0" x2="0" y2="1">')
    for off, c in zip(("0", "0.45", "0.8", "1"), p["steel"]):
        a('      <stop offset="%s" stop-color="%s"/>' % (off, c))
    a('    </linearGradient>')
    a('    <linearGradient id="steelEdge" x1="0" y1="0" x2="0" y2="1">')
    for off, (c, op) in zip(("0", "1"), p["edge"]):
        a('      <stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (off, c, op))
    a('    </linearGradient>')
    a('    <linearGradient id="steelText" x1="0" y1="0" x2="0" y2="1">')
    for off, c in zip(("0", "0.6", "1"), p["steel_text"]):
        a('      <stop offset="%s" stop-color="%s"/>' % (off, c))
    a('    </linearGradient>')
    a('    <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0">')
    a('      <stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>')
    a('      <stop offset="0.5" stop-color="#FFFFFF" stop-opacity="%s"/>' % p["sheen_op"])
    a('      <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>')
    a('    </linearGradient>')
    a('    <linearGradient id="pulse" x1="0" y1="0" x2="1" y2="0">')
    a('      <stop offset="0" stop-color="%s" stop-opacity="0"/>' % p["pulse"])
    a('      <stop offset="0.5" stop-color="%s" stop-opacity="0.95"/>' % p["pulse"])
    a('      <stop offset="1" stop-color="%s" stop-opacity="0"/>' % p["pulse"])
    a('    </linearGradient>')
    a('    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">')
    a('      <stop offset="0" stop-color="%s" stop-opacity="%s"/>' % p["glow"])
    a('      <stop offset="1" stop-color="%s" stop-opacity="0"/>' % p["glow"][0])
    a('    </radialGradient>')
    a('    <filter id="spadeGlow" x="-40%" y="-40%" width="180%" height="180%">')
    a('      %s' % p["emblem_filter"])
    a('    </filter>')
    if p["card_shadow"]:
        a('    <filter id="cardShadow" x="-20%" y="-20%" width="140%" height="140%">')
        a('      %s' % p["card_shadow"])
        a('    </filter>')
    a('    <clipPath id="ulClip"><rect x="330" y="172.5" width="308" height="4"/></clipPath>')
    a('')
    a('    <!-- Machines à écrire du terminal : fenêtres de clip -->')
    ci = 0
    for i, ln in enumerate(LINES):
        if ln[0] == "cmd":
            ci += 1
            a(typewriter("type%d" % ci, BASE_Y[i], len(ln[1]) + 2, STARTS[i]))
    a('  </defs>')
    a('')
    a('  <style>')
    a('    text { -webkit-user-select: none; user-select: none; }')
    a("    .sans { font-family: 'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif; }")
    a("    .mono { font-family: 'JetBrains Mono','Cascadia Code','SF Mono',Consolas,"
      "'DejaVu Sans Mono',monospace; }")
    a("    .serif { font-family: Georgia,'Times New Roman',serif; }")
    a('    .rise { opacity: 0; animation: rise 0.8s cubic-bezier(0.22,0.61,0.36,1) forwards; }')
    a('    .d1 { animation-delay: 0.1s; } .d2 { animation-delay: 0.25s; }')
    a('    .d3 { animation-delay: 0.4s; } .d4 { animation-delay: 0.55s; }')
    a('    @keyframes rise { from { opacity: 0; transform: translateY(12px); } '
      'to { opacity: 1; transform: translateY(0); } }')
    a('    @media (prefers-reduced-motion: reduce) {')
    a('      .rise { animation: none; opacity: 1; }')
    a('      .sheen-r, .cursor { display: none; }')
    ci = 0
    for i, ln in enumerate(LINES):
        if ln[0] == "cmd":
            ci += 1
            a('      #type%d rect { width: %.2fpx !important; }' % (ci, (len(ln[1]) + 2) * CELL))
    a('      .out { opacity: 1 !important; }')
    a('    }')
    a('  </style>')
    a('')
    a('  <!-- Carte -->')
    a('  <rect x="8" y="8" width="984" height="564" rx="18" fill="url(#bgGrad)" '
      'stroke="%s" stroke-width="1.4"/>' % p["card_stroke"])
    a('  <rect x="20" y="20" width="960" height="540" rx="12" stroke="%s" '
      'stroke-opacity="%s" stroke-width="1"/>' % (p["inner_stroke"], p["inner_op"]))
    a('')
    a('  <!-- Index de coins, comme sur une vraie carte -->')
    a('  <g id="idx">')
    a('    <text x="46" y="60" class="serif" font-size="30" fill="%s" '
      'text-anchor="middle">A</text>' % p["index"])
    a('    <use href="#spade" transform="translate(38.5,68) scale(0.075)" fill="%s"/>' % p["pip"])
    a('  </g>')
    a('  <use href="#idx" transform="rotate(180 500 290)"/>')
    a('')
    a('  <!-- Emblème : la pique comme une lame -->')
    a('  <g class="rise">')
    a('    <ellipse cx="170" cy="160" rx="165" ry="165" fill="url(#glow)"/>')
    a('    <g transform="translate(70,46) scale(1)">')
    a('      <g>')
    a('        <animateTransform attributeName="transform" type="translate" additive="sum"')
    a('          values="0 0;0 -6;0 0" keyTimes="0;0.5;1" dur="7s"')
    a('          calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1" '
      'repeatCount="indefinite"/>')
    a('        <use href="#spade" fill="url(#spadeSteel)" stroke="url(#steelEdge)" '
      'stroke-width="1.5" filter="url(#spadeGlow)"/>')
    a('        <path d="M100,34 C101.6,62 101.6,102 100,140 C98.4,102 98.4,62 100,34 Z" '
      'fill="#C8A96A" opacity="0.5"/>')
    a('        <g clip-path="url(#spadeClip)">')
    a('          <g transform="skewX(-16)">')
    a('            <rect class="sheen-r" x="-70" y="-10" width="44" height="260" '
      'fill="url(#sheen)">')
    a('              <animateTransform attributeName="transform" type="translate"')
    a('                values="0 0;340 0;340 0" keyTimes="0;0.22;1" dur="9s" '
      'repeatCount="indefinite"/>')
    a('            </rect>')
    a('          </g>')
    a('        </g>')
    a('      </g>')
    a('    </g>')
    a('  </g>')
    a('')
    a('  <!-- Bloc identité -->')
    a('  <g class="rise d1">')
    a('    <text x="330" y="104" class="mono" font-size="12" letter-spacing="4" '
      'fill="%s">// L’AS DE PIQUE</text>' % p["kicker"])
    a('  </g>')
    a('  <g class="rise d2">')
    a('    <text x="326" y="162" class="sans" font-size="58" font-weight="800" '
      'letter-spacing="10" fill="url(#steelText)" textLength="210" '
      'lengthAdjust="spacing">YANIS</text>')
    a('    <rect x="330" y="173.5" width="308" height="1.4" fill="%s"/>' % p["rule"])
    a('    <g clip-path="url(#ulClip)">')
    a('      <rect x="260" y="172.8" width="70" height="2.4" fill="url(#pulse)">')
    a('        <animateTransform attributeName="transform" type="translate"')
    a('          values="0 0;400 0;400 0" keyTimes="0;0.45;1" dur="6s" '
      'repeatCount="indefinite"/>')
    a('      </rect>')
    a('    </g>')
    a('  </g>')
    a('')
    a('  <!-- Pills : ce qu’un recruteur doit lire en un coup d’œil -->')
    a('  <g class="rise d3">')

    def pill(x, w, label, icon_body):
        """Pilule : icône 16x16 à gauche, libellé calé à droite, padding 16."""
        tl = len(label) * PILL_CELL
        y = PY
        g = []
        g.append('    <g>')
        g.append('      <rect x="%g" y="%g" width="%g" height="34" rx="17" stroke="%s" '
                 'stroke-width="1.2" fill="%s" fill-opacity="%s"/>'
                 % (x, y, w, p["pill_stroke"], p["pill_fill"], p["pill_fill_op"]))
        g.append('      <g transform="translate(%g,%g)" stroke="%s" fill="none" '
                 'stroke-linecap="round" stroke-linejoin="round">%s</g>'
                 % (x + 16, y + 9, p["pill_icon"], icon_body))
        g.append('      <text x="%.1f" y="%g" class="mono" font-size="12" letter-spacing="1.5" '
                 'fill="%s" textLength="%.1f" lengthAdjust="spacingAndGlyphs">%s</text>'
                 % (x + w - 16 - tl, y + 22, p["pill_text"], tl, label))
        g.append('    </g>')
        return "\n".join(g)

    FLAG = ('<path d="M2,1 V15.4" stroke-width="1.6"/>'
            '<path d="M2,2.6 L13.2,2.6 L10.7,6.8 L13.2,11 L2,11" stroke-width="1.6"/>')
    SHIELD = ('<path d="M8,1 L14,3.5 V7.7 C14,11.3 11.4,13.5 8,14.5 '
              'C4.6,13.5 2,11.3 2,7.7 V3.5 Z" stroke-width="1.6"/>')
    CHEV = ('<path d="M1.5,2.5 l5.5,4.5 -5.5,4.5" stroke-width="1.6"/>'
            '<path d="M10.5,12 h5.5" stroke-width="1.6"/>')
    PAD = ('<path d="M1,8.5 a3,3 0 0 1 3,-3 h8 a3,3 0 0 1 3,3 v1.6 a2.6,2.6 0 0 1 -4.7,1.7 '
           'h-4.6 a2.6,2.6 0 0 1 -4.7,-1.7 z" stroke-width="1.5"/>'
           '<path d="M3.6,8 h2.6 M4.9,6.7 v2.6" stroke-width="1.2"/>'
           '<circle cx="12" cy="7.7" r="1" fill="%s" stroke="none"/>' % p["pill_icon"])

    a(pill(330, 136, "FONDATEUR", FLAG))
    a(pill(479, 170, "CYBERSÉCURITÉ", SHIELD))
    a(pill(662, 118, "BACKEND", CHEV))
    a(pill(793, 127, "GAME DEV", PAD))
    a('  </g>')
    a('')
    a('  <!-- Terminal -->')
    a('  <g class="rise d4">')
    shadow = ' filter="url(#cardShadow)"' if p["card_shadow"] else ''
    a('    <rect x="60" y="286" width="860" height="254" rx="10" fill="%s" stroke="%s" '
      'stroke-width="1.2"%s/>' % (T_BG, T_STROKE, shadow))
    a('    <path d="M61,318 H919" stroke="%s" stroke-width="1"/>' % T_SEP)
    a('    <circle cx="80" cy="302" r="4" fill="#6B7280"/>')
    a('    <circle cx="96" cy="302" r="4" fill="#9AA3B2"/>')
    a('    <circle cx="112" cy="302" r="4" fill="#C8A96A"/>')
    a('    <text x="132" y="306" class="mono" font-size="11" fill="%s">yanis@spade:~</text>'
      % T_TITLE)
    a('')
    ci = 0
    for i, ln in enumerate(LINES):
        y = BASE_Y[i]
        if ln[0] == "cmd":
            ci += 1
            cmd = ln[1]
            a('    <text x="%.2f" y="%d" class="mono" font-size="13" clip-path="url(#type%d)" '
              'fill="%s" textLength="%.2f" lengthAdjust="spacingAndGlyphs">$</text>'
              % (TX, y, ci, T_PROMPT, CELL))
            a('    <text x="%.2f" y="%d" class="mono" font-size="13" clip-path="url(#type%d)" '
              'fill="%s" textLength="%.2f" lengthAdjust="spacingAndGlyphs">%s</text>'
              % (TX + 2 * CELL, y, ci, T_CMD, len(cmd) * CELL, esc(cmd)))
        elif ln[0] == "out":
            a('    <text x="%.2f" y="%d" class="mono out" font-size="13" fill="%s" '
              'textLength="%.2f" lengthAdjust="spacingAndGlyphs" opacity="0">%s%s</text>'
              % (TX, y, T_OUT, len(ln[1]) * CELL, esc(ln[1]), reveal(STARTS[i])))
            if len(ln) == 3:
                # segment d'accent : même révélation, couleur de marque
                a('    <text x="%.2f" y="%d" class="mono out" font-size="13" fill="%s" '
                  'textLength="%.2f" lengthAdjust="spacingAndGlyphs" opacity="0">%s%s</text>'
                  % (TX + (len(ln[1]) + 1) * CELL, y, T_PROMPT, len(ln[2]) * CELL,
                     esc(ln[2]), reveal(STARTS[i])))
        else:
            creed, attr = ln[1], ln[2]
            cw = len(creed) * CELL
            a('    <text x="%.2f" y="%d" class="mono out" font-size="13" font-style="italic" '
              'fill="%s" textLength="%.2f" lengthAdjust="spacingAndGlyphs" opacity="0">%s%s</text>'
              % (TX, y, T_CREED, cw, esc(creed), reveal(STARTS[i], "0.92")))
            ax = TX + cw + 3 * CELL
            a('    <text x="%.2f" y="%d" class="mono out" font-size="13" fill="%s" '
              'textLength="%.2f" lengthAdjust="spacingAndGlyphs" opacity="0">%s%s</text>'
              % (ax, y, T_ATTR, len(attr) * CELL, esc(attr), reveal(STARTS[i] + 0.1)))
            cx = ax + len(attr) * CELL + CELL
    a('    <g class="cursor" opacity="0">')
    a('      %s' % reveal(CURSOR_AT))
    a('      <rect x="%.0f" y="%d" width="8" height="14" fill="#C8A96A">' % (cx, BASE_Y[-1] - 12))
    a('        <animate attributeName="opacity" calcMode="discrete" dur="1.1s" '
      'repeatCount="indefinite" values="1;0;0" keyTimes="0;0.5;1"/>')
    a('      </rect>')
    a('    </g>')
    a('  </g>')
    a('</svg>')
    return "\n".join(o) + "\n"


for pal, path in ((DARK, sys.argv[1]), (LIGHT, sys.argv[2])):
    open(path, "w", encoding="utf-8").write(build(pal))
    print("écrit :", path)
