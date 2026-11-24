// Rend un SVG dans une balise <img>, comme GitHub, à une largeur donnée.
// usage : node shoot.js <svg> <png> [largeur=900] [ms=3000] [dpr=2] [motion]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const [,, svg, out, width = '900', at = '3000', dpr = '2', motion = 'no-preference'] = process.argv;
(async () => {
  const dark = !/light/.test(path.basename(svg));
  const bg = dark ? '#0d1117' : '#ffffff';
  const html = path.join(path.dirname(svg), '.page-' + path.basename(svg) + '.html');
  fs.writeFileSync(html, `<body style="margin:0;background:${bg}"><img id="i" src="${path.basename(svg)}" style="display:block;width:${width}px"></body>`);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +width, height: 800 }, deviceScaleFactor: +dpr, reducedMotion: motion, colorScheme: dark ? 'dark' : 'light' });
  await p.goto('file://' + html);
  await p.waitForFunction(() => { const i = document.getElementById('i'); return i.complete && i.naturalWidth > 0; });
  await p.waitForTimeout(+at);
  await (await p.$('#i')).screenshot({ path: out });
  await b.close(); fs.unlinkSync(html);
})().catch(e => { console.error(String(e)); process.exit(1); });
