// The page's own font (4.44.0): Nunito comes from static/fonts/ with its licence next to it, kept a year by its hashed name,
// and no page asks a third party for anything while it loads (it used to fetch Google Fonts on every load).
const {BASE, check, page, run} = require('./lib');
const ORIGIN = new URL(BASE).origin;
run(async b => {
  const p = await page(b, 412, 915), asked = [];
  p.on('request', r => asked.push(r.url()));
  for (const where of ['', 'argus', 'mentor', 'olympus', 'phone']) {
    await p.goto(BASE + where); await p.waitForLoadState('networkidle'); await p.evaluate(() => document.fonts.ready);
  }
  const away = [...new Set(asked.filter(u => /^https?:/.test(u) && new URL(u).origin !== ORIGIN))];
  check(away.length === 0, 'Today, Watch, Study, Playground and Phone alerts ask no third party for anything ' + JSON.stringify(away));
  check(!(await p.locator('link[href*="fonts.googleapis"],link[href*="fonts.gstatic"]').count()), 'no Google Fonts link in the page');

  await p.goto(BASE); await p.evaluate(() => document.fonts.ready);
  const f = await p.evaluate(() => ({c400: document.fonts.check('400 14px Nunito'), c600: document.fonts.check('600 16px Nunito'),
    faces: [...document.fonts].filter(x => x.family.replace(/"/g, '') === 'Nunito').map(x => x.status),
    pre: document.querySelector('link[rel=preload][as=font]')?.href || '',
    got: performance.getEntriesByType('resource').map(e => e.name).filter(n => /\/static\/fonts\//.test(n))}));
  check(f.c400 && f.c600 && f.faces.length === 1 && f.faces[0] === 'loaded', 'Nunito 400 and 600 are loaded from the page\'s own file ' + JSON.stringify(f.faces));
  check(/\/static\/fonts\/nunito\.[0-9a-f]{8}\.woff2$/.test(f.pre) && f.got.length === 1 && f.got[0] === f.pre,
    'the preload and the @font-face name the same file, fetched once ' + JSON.stringify(f.got));
  // the heading really draws with Nunito (the font Chromium used for its glyphs), not the system fallback
  const cdp = await p.context().newCDPSession(p); await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const {root} = await cdp.send('DOM.getDocument'), {nodeId} = await cdp.send('DOM.querySelector', {nodeId: root.nodeId, selector: '.title h1'});
  const used = (await cdp.send('CSS.getPlatformFontsForNode', {nodeId})).fonts.map(x => x.familyName);
  check(used.length && used.every(n => /^Nunito( Regular)?$/.test(n)), 'the heading is drawn in Nunito ' + JSON.stringify(used));

  const r = await p.request.get(f.pre), body = await r.body();
  check(r.status() === 200 && r.headers()['content-type'] === 'font/woff2' && body.slice(0, 4).toString() === 'wOF2', 'the font file is served as font/woff2');
  check(r.headers()['cache-control'] === 'public, max-age=31536000, immutable', 'and kept a year: its name carries its hash (' + r.headers()['cache-control'] + ')');
  check((await p.request.get(BASE + 'static/css/argus.css')).headers()['cache-control'] === 'max-age=300', 'a file without a hash in its name keeps the short cache');
  const ofl = await p.request.get(BASE + 'static/fonts/OFL.txt');
  check(ofl.status() === 200 && /SIL OPEN FONT LICENSE Version 1\.1/i.test(await ofl.text()) && /Nunito Project Authors/.test(await ofl.text()), 'the font\'s licence (OFL 1.1, with its copyright line) ships next to it');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
});
