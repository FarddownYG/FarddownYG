export const meta = {
  name: 'concours-embleme',
  description: 'Four construction strategies for an ornate filigree ace of spades compete; two judges rank them; the winner is polished',
  phases: [
    { title: 'Dessin', detail: 'four artists, one construction strategy each' },
    { title: 'Jury', detail: 'two judges with distinct lenses rank the emblems' },
    { title: 'Polissage', detail: 'a fresh agent applies the jury critiques to the winner' },
  ],
}

const ROOT = '/tmp/claude-0/-home-user-FarddownYG/de2b9f54-4389-5797-bb2c-39426a7712b5/scratchpad/embleme'

const BRIEF = `
You are drawing ONE vector emblem: an ORNATE FILIGREE ACE OF SPADES. It is the centrepiece of a personal brand
(the GitHub profile of Yanis, a cybersecurity engineer and founder; his symbol is the ace of spades, which for him
means surpassing oneself and sharpening a little more every day). He once showed a reference image, now lost, described
as "an ornate filigree ace of spades, cream on warm black", and said "this is the one I want". A first attempt months
ago was rejected as TOO AIRY: sparse, thin, uniform wires. So: density, hierarchy and craftsmanship are the point.

WHERE IT WILL BE USED
- on a playing-card face in the profile hero, about 330 px tall on desktop and 150 px on mobile;
- as the avatar (GitHub crops it to a circle; it is shown from 460 px down to 40 px);
- cream ink on warm black in dark mode, near-black ink on cream paper in light mode (same file, both polarities).
It must read as a SPADE instantly at 40 px and reward a close look at 1000 px.

AESTHETIC
Baroque / Victorian engraving, wrought-iron filigree, banknote guilloché, ornamental tattoo flash. Precise, symmetric,
premium. Thick-thin modulation like an engraver's burin or a calligrapher's pen: prefer TAPERED FILLED RIBBONS
(centreline + varying half-width, emitted as a closed filled path) over uniform-width strokes. Clear hierarchy:
a bold confident structure, a middle layer of ornament, fine detail last.
Anti-goals: thin uniform wires; random-looking noodles; clip-art; kinks or flat spots in curves; lines that cross by
accident; floating disconnected bits; empty holes next to crowded knots; anything asymmetric; skulls, letters, text.

HARD CONTRACT for the file emblem.svg (a checker enforces it)
- Root exactly: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200"> ... </svg>. Transparent background.
- Allowed elements only: g, path, circle, ellipse, rect, line, polyline, polygon, defs, use, clipPath, mask, symbol.
  NOT allowed: text, image, filter, style, script, foreignObject, gradients, animate*, the style="" attribute.
- Paint only with fill="currentColor" / stroke="currentColor" / "none" (inside a <mask>, #fff and #000 are allowed).
  The host sets the ink colour. For a few GOLD accents put class="or" on an element or group and still paint it with
  currentColor (the host recolours that class). Use gold sparingly (pearls, a heart medallion, a hairline), 0-12% of ink.
- Exact mirror symmetry about the vertical axis x=500: build the right half, mirror it (emit mirrored coordinates or
  wrap in <g transform="matrix(-1 0 0 1 1000 0)">; <use> is allowed).
- Stay inside x 80..920, y 40..1160. The reference silhouette (file ${ROOT}/outils/silhouette.txt, one SVG path) spans
  x 120..880, y 70..1140; keep its proportions and bounding box so the emblem drops into the layout slot. You may
  refine the outline's curves.
- Wrap the artwork in top-level groups <g data-ordre="K"> with K from 0 (appears first: main outline / stem) to at
  most 24 (last: finest details, pearls). The host will stagger an entrance animation in that order.
- At most 160 KB, coordinates rounded to 1 decimal, ideally fewer than 600 elements.
- emblem.svg must be produced by a deterministic generator: python3 gen.py > emblem.svg. Python standard library only
  (math is all you need); if you use randomness, use random.Random(FIXED_SEED).

TOOLS
- Preview + contract check + metrics:   python3 ${ROOT}/outils/apercu.py <your directory>
  It writes apercu-sombre.png (cream on warm black), apercu-clair.png (ink on cream) and apercu-tailles.png (the
  emblem at 320 / 160 / 80 / 40 px tall, on both grounds), and prints: weight, element counts, ink coverage inside the
  reference silhouette, overflow outside it, left/right symmetry error, and contract violations.
- LOOK at your renders with the Read tool on the PNG files, every iteration. Judge them like an art director:
  the 320-px and 40-px tiles in apercu-tailles.png matter as much as the big one.
- A minimal example of the contract is in ${ROOT}/exemple/ (gen.py + emblem.svg). Do not edit other directories.

PROCESS
Work only inside your own directory. Sketch the plan in comments at the top of gen.py, get a first render early, then
iterate: at most 10 preview renders in total, so make each one count; stop as soon as it is genuinely good.
Before you finish, the checker must print "contrat : respecté".
`

const STRATEGIES = [
  { key: 'A-rinceaux', coverage: '38-62%', text: `
YOUR CONSTRUCTION STRATEGY: "RINCEAUX" — composed scrollwork, designed by hand.
Write a small library of parametric motif functions that each return a filled ribbon: volute (spiral scroll whose
thickness tapers to a fine curled tip, optionally ending in a bud or teardrop), C-scroll, S-scroll, acanthus leaf,
teardrop, pearl. Then PLACE them deliberately on the right half following the anatomy of the spade: a central-axis
motif (a fleuron / palmette rising toward the tip, a medallion at the heart), a large volute filling each lobe,
shoulder scrolls riding the flanks, tendrils narrowing into the tip, a flourish on the stem and foot. Mirror for the
left half. Big forms first, then secondary curls in the gaps, then pearls. Every scroll springs tangentially from
another form or from the outline: nothing floats. Frame it with a bold outline and an inner hairline.` },
  { key: 'B-croissance', coverage: '38-62%', text: `
YOUR CONSTRUCTION STRATEGY: "CROISSANCE" — procedural vine growth that fills the silhouette.
Flatten the reference silhouette to a polygon and implement an inside / distance-to-edge test. Grow tapering spiral
scrolls (logarithmic spirals, thick at the root, hair-fine at the curled tip, ending in a bud or pearl) on the right
half only: seeds on the central axis and on the inner outline, biggest scrolls first; each new scroll springs
tangentially from an existing stroke, stays inside the silhouette inset, and keeps a minimum clearance from existing
ink (use an occupancy grid). Continue with a middle generation, then small curls, buds and pearls in the remaining
gaps until the coverage target is met. Fixed seed. Then CURATE: tune parameters and seed until it looks designed, not
random — three to five big confident spirals per half, a clear middle generation, a fine fill. Mirror to the left.
Frame it with a bold outline and an inner hairline.` },
  { key: 'C-gravure', coverage: '38-62%', text: `
YOUR CONSTRUCTION STRATEGY: "GRAVURE" — engraved lace and guilloché, like a banknote plate or a watch dial.
Inside a bold outline, compute concentric inward offsets of the silhouette (numerically: flatten, offset along
normals, clean up) and vary their weights to make bands. Fill the bands with engraved patterns clipped by clipPath:
a guilloché rosette (hypotrochoid / epitrochoid families, several phases overlaid) centred on the heart of the spade,
sunburst hatching fading toward the tip, a scalloped or pearl border band, a scale or lattice pattern in the lobes.
Add a focal ornament so it reads as ornament and not as a technical diagram: a fleuron on the axis and two to four
large symmetric scrolls. Precision and rhythm are everything: constant spacing, clean ends, no moiré mush at 320 px
(check the small tiles: fine hatching must merge into an even tone, not noise).` },
  { key: 'D-reserve', coverage: '55-75% (this strategy is a solid mass: ignore the 38-62% guidance printed by the checker)', text: `
YOUR CONSTRUCTION STRATEGY: "RÉSERVE" — a solid spade with the ornament carved out of it (negative space).
Fill the silhouette solid (fill="currentColor") and CUT the filigree out of the mass with a <mask> (white silhouette,
black carved shapes): a carved fleuron along the axis, scroll-shaped slits with tapered ends that curl into the lobes,
teardrops and petals, a carved inner contour line running parallel to the edge, a row of pearl holes following it.
Think damascened steel, papercut, hot-foil stamping. The mass guarantees the silhouette at 40 px; the carving gives
the richness up close. You may add a thin detached outer hairline frame and a few gold accents (class "or") sitting
inside the cut-outs. Carved lines need the same thick-thin elegance as drawn ones: no uniform slots.` },
]

const ARTIST_SCHEMA = {
  type: 'object',
  properties: {
    dir: { type: 'string', description: 'absolute path of your directory' },
    summary: { type: 'string', description: 'what you built, in 3-5 sentences' },
    weaknesses: { type: 'string', description: 'honest list of what is still weak' },
    coverage_pct: { type: 'number' },
    size_kb: { type: 'number' },
    contract_ok: { type: 'boolean' },
  },
  required: ['dir', 'summary', 'weaknesses', 'contract_ok'],
}

phase('Dessin')
const drawn = (await parallel(STRATEGIES.map(s => () =>
  agent(`${BRIEF}\n${s.text}\n\nCoverage guidance for your strategy: ${s.coverage}.\nYour directory (create it): ${ROOT}/${s.key}\nFinal deliverables in it: gen.py, emblem.svg, and the three apercu-*.png written by the checker on your final version.`,
    { label: `dessin:${s.key}`, phase: 'Dessin', schema: ARTIST_SCHEMA })
    .then(r => r && r.contract_ok ? { key: s.key, ...r } : (r ? { key: s.key, ...r } : null))
))).filter(Boolean)
log(`${drawn.length}/4 emblems delivered: ${drawn.map(d => d.key + (d.contract_ok ? '' : ' (contract KO)')).join(', ')}`)
if (!drawn.length) return { error: 'no emblem delivered' }

const CANDIDATES = drawn.map(d => `- ${d.key}: directory ${ROOT}/${d.key} — files apercu-sombre.png, apercu-clair.png, apercu-tailles.png, emblem.svg, gen.py. Author's summary: ${d.summary} Author's own list of weaknesses: ${d.weaknesses}`).join('\n')

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string' },
          c1: { type: 'number' }, c2: { type: 'number' }, c3: { type: 'number' }, c4: { type: 'number' },
          strengths: { type: 'string' },
          weaknesses: { type: 'string' },
          fixes: { type: 'array', items: { type: 'string' }, description: 'concrete, actionable fixes, most valuable first' },
        },
        required: ['key', 'c1', 'c2', 'c3', 'c4', 'strengths', 'weaknesses', 'fixes'],
      },
    },
    ranking: { type: 'array', items: { type: 'string' }, description: 'candidate keys, best first' },
    graft: { type: 'string', description: 'ideas from the losers worth grafting onto the winner' },
  },
  required: ['scores', 'ranking', 'graft'],
}

const JUDGES = [
  { key: 'direction-artistique', text: `You are the ART DIRECTOR on the jury. Score each candidate from 0 to 10 on:
c1 = fidelity to the brief: is it unmistakably an ORNATE FILIGREE ace of spades (not a diagram, not a blob, not airy wires)?
c2 = craftsmanship and beauty at large size (apercu-sombre.png): curve quality, thick-thin elegance, finish.
c3 = premium, intentional, not kitsch or generic: would a luxury card maker print it?
c4 = composition: hierarchy, rhythm, even density, balance, no accidental-looking spots.` },
  { key: 'production', text: `You are the PRODUCTION lead on the jury. Score each candidate from 0 to 10 on:
c1 = legibility small: at 80 px and 40 px (apercu-tailles.png) is it instantly a spade, with an even tone rather than noise?
c2 = both polarities: is apercu-clair.png (dark ink on cream) as good as apercu-sombre.png?
c3 = technical cleanliness: run python3 ${ROOT}/outils/apercu.py <dir> yourself for the metrics (symmetry error, overflow, weight, contract), and inspect the renders closely for stray artefacts, kinks, broken joins, clipped shapes.
c4 = fitness as an animated card emblem: sensible data-ordre groups (structure first, detail last), reasonable element count, reads well when cropped to a circle around its upper two thirds (avatar use).` },
]

phase('Jury')
const verdicts = (await parallel(JUDGES.map(j => () =>
  agent(`An emblem competition. The brief the artists received:\n${BRIEF}\n\n${j.text}\n\nCandidates:\n${CANDIDATES}\n\nLook at every candidate's three PNG previews with the Read tool before scoring (start with all the apercu-tailles.png, then the large ones). Be severe and specific; a 7 means genuinely good, a 9 means you would ship it as is. Rank them and, for each, list concrete fixes. Do not modify any file.`,
    { label: `jury:${j.key}`, phase: 'Jury', schema: JUDGE_SCHEMA })
    .then(v => v && { judge: j.key, ...v })
))).filter(Boolean)

const totals = {}
for (const d of drawn) totals[d.key] = { total: 0, art: 0, n: 0, contract_ok: d.contract_ok }
for (const v of verdicts) for (const s of v.scores) {
  if (!totals[s.key]) continue
  const sum = s.c1 + s.c2 + s.c3 + s.c4
  totals[s.key].total += sum
  totals[s.key].n += 1
  if (v.judge === 'direction-artistique') totals[s.key].art = sum
}
const order = Object.keys(totals).sort((a, b) =>
  (totals[b].contract_ok - totals[a].contract_ok) || (totals[b].total - totals[a].total) || (totals[b].art - totals[a].art))
const winner = order[0]
log(`ranking: ${order.map(k => `${k} ${totals[k].total}`).join(' > ')}`)

const critiques = verdicts.map(v => {
  const s = v.scores.find(x => x.key === winner)
  return `JUDGE ${v.judge}: strengths: ${s ? s.strengths : '-'} | weaknesses: ${s ? s.weaknesses : '-'} | fixes: ${s ? s.fixes.map((f, i) => `(${i + 1}) ${f}`).join(' ') : '-'} | ideas to graft from the other candidates: ${v.graft}`
}).join('\n')

phase('Polissage')
const final = await agent(`${BRIEF}\n\nThe competition is over. The winning emblem is in ${ROOT}/${winner} (gen.py, emblem.svg, previews). The other candidates are in ${order.slice(1).map(k => `${ROOT}/${k}`).join(', ')} if you need to look at an idea the jury wants grafted.\n\nThe jury's notes on the winner:\n${critiques}\n\nYOUR JOB: polish the winner into the final emblem.\n1. Copy the winner's directory to ${ROOT}/final and work only there.\n2. Read gen.py fully, look at its three previews, then apply the jury's fixes in order of value. Keep what the jury praised. Do not redesign it.\n3. Also produce ${ROOT}/final/mini.svg: a SIMPLIFIED companion for 24 to 64 px uses (same contract, same silhouette and bounding box, same viewBox), keeping only the bold structure and two or three key ornaments so that it stays crisp at 32 px. Generate it from the same gen.py with a flag: python3 gen.py --mini > mini.svg.\n4. At most 8 preview renders. The checker (python3 ${ROOT}/outils/apercu.py ${ROOT}/final) must print "contrat : respecté" on the final emblem.svg; for mini.svg, check the contract by temporarily copying it over emblem.svg in a scratch subdirectory and running the checker there.\nReturn what you changed and what remains imperfect.`,
  { label: `polissage:${winner}`, phase: 'Polissage', schema: {
    type: 'object',
    properties: {
      dir: { type: 'string' },
      changes: { type: 'string' },
      remaining: { type: 'string' },
      contract_ok: { type: 'boolean' },
      mini_ok: { type: 'boolean' },
    },
    required: ['dir', 'changes', 'remaining', 'contract_ok', 'mini_ok'],
  } })

return { winner, order, totals, drawn, verdicts, final }
