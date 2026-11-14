// Screen sizes (docs/ui-plan.md §14): a phone, a phone on its side, 16:9, and two ultrawides. Each page uses the width it
// has: nothing is squeezed into a one-word column, the sections bar becomes a left rail on ultrawides, and Argus never takes
// more than about a fifth of the height.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
// Find and measure in one step. A locator's evaluate finds the node, then measures it in a second round trip; Today draws
// twice (what it knows, then again when every section has answered), and a redraw between the two steps left a node that
// was no longer on the page, measured as 0 x 0 (the flaky "phone: Home is one column", 4.44.0).
const rect = s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; };
const box = (p, s) => p.evaluate(`(${rect})(${JSON.stringify(s)})`);
const boxes = (p, ...ss) => p.evaluate(`[${ss.map(s => `(${rect})(${JSON.stringify(s)})`).join(',')}]`);
// Today has settled: every section has answered (no "Checking…" card, no "Asking every section…")
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); });
run(async b => {
  for (const [w, h, tag] of [[3440, 1440, 'ultrawide 3440'], [2560, 1080, 'ultrawide 2560']]) {
    const p = await page(b, w, h); await p.goto(BASE + 'home'); await p.locator('.home .places').waitFor(); await p.waitForTimeout(500);
    const rail = await box(p, '.realms'), main = await box(p, 'main');
    check(rail.x === 0 && rail.y === 0 && rail.h >= h - 1 && rail.w <= 220 && main.x >= rail.w, `${tag}: the sections bar is a rail down the left edge, beside the page`);
    const pills = await p.locator('#realms .realm').evaluateAll(es => es.map(e => e.getBoundingClientRect().x));
    check(pills.every(x => Math.abs(x - pills[0]) < 2), `${tag}: the sections stack in one column`);
    const needs = await box(p, '.home .needs'), places = await box(p, '.home .places');
    check(needs.w >= 500 && places.w >= 1000 && places.y > needs.y, `${tag}: Today uses the width: the rows at least 500 px wide, the section cards across the page under them`);
    check(await noOverflow(p), `${tag}: no sideways scrolling`);
    await shot(p, 'layout-' + w + '-home');
    await p.goto(BASE + 'argus'); await p.locator('.card').first().waitFor(); await p.waitForTimeout(300);
    check((await box(p, 'header')).h <= h * 0.25, `${tag}: Argus's header takes at most a quarter of the height (${Math.round((await box(p, 'header')).h)} px)`);
    const cols = await p.locator('.grid').first().evaluate(g => getComputedStyle(g).gridTemplateColumns.split(' ').length);
    check(cols >= 7, `${tag}: Argus fits ${cols} task cards in a row`);
    await shot(p, 'layout-' + w + '-watch');
    await p.goto(BASE + 'demo-server'); await p.locator('.plugin-server .plugin-body').waitFor(); await p.waitForTimeout(300);
    check((await box(p, '.plugin-body')).w >= 1000, `${tag}: a server plugin's page gets the full content width`);
    check(p.errors.length === 0, `${tag}: no page errors ` + p.errors.join(' | '));
  }
  const d = await page(b, 1920, 1080); await d.goto(BASE + 'home'); await d.locator('.home .places').waitFor(); await d.waitForTimeout(300);
  const dbar = await box(d, '.realms'), dn = await box(d, '.home .needs'), dp = await box(d, '.home .places'), dm = await box(d, 'main');
  check(dbar.y === 0 && dbar.w >= 1900, '16:9: the sections bar stays across the top');
  check(dp.y > dn.y && Math.abs(dn.x - dm.x - 16) < 2, '16:9: Today lines up with the page edge (no second gutter), the section cards under the rows');
  await d.goto(BASE + 'argus'); await d.locator('.card').first().waitFor();
  check((await box(d, '.argus')).w <= 1080 * 0.22 + 1, '16:9: Argus is at most about a fifth of the height');
  await shot(d, 'layout-1920-home');

  // the strip on laptops, 16:9 and a phone on its side (4.44.0): one row inside the screen. Second lines go first, then the
  // weather, then the last pills fold into More (never Today or the place you are on); Mute sounds covers no pill and the
  // weather is whole or not on the strip (it is always under the name on Today); nothing
  // scrolls sideways. Before 4.44.0 the strip scrolled under Mute sounds at 1024 and on a phone on its side (915 x 412, 800 x 360).
  const strip = p => p.evaluate(() => { const r = e => e.getBoundingClientRect(), bar = document.querySelector('.realms'), more = document.getElementById('realmMore');
    const shown = [...bar.querySelectorAll('.realm,.wx,.mute')].filter(e => e.offsetWidth), m = r(document.getElementById('mute'));
    const hit = (a, c) => a.left < c.right - 1 && c.left < a.right - 1 && a.top < c.bottom - 1 && c.top < a.bottom - 1;
    return {n: shown.filter(e => e.matches('.realm')).length, row: shown.every(e => r(e).top < r(shown[0]).bottom), inside: shown.every(e => r(e).left >= 0 && r(e).right <= innerWidth),
      clear: shown.every(e => e.id === 'mute' || !hit(r(e), m)), scrolls: bar.scrollWidth > bar.clientWidth + 1,
      over: [...bar.querySelectorAll('#realms .realm.over')].map(e => e.dataset.id), more: !!more && !more.hidden && more.offsetWidth > 0,
      compact: bar.classList.contains('compact'), bare: bar.classList.contains('bare')}; });
  const folded = {};
  for (const [w, h] of [[1920, 1080], [1440, 900], [1280, 720], [1024, 720], [915, 412], [800, 360]]) {
    const lp = await page(b, w, h); await lp.goto(BASE + 'home'); await settled(lp);
    const s = await strip(lp); folded[w] = s.over;
    check(s.row && s.inside && s.clear && !s.scrolls, `${w} x ${h}: the sections strip is one row inside the screen and Mute sounds covers no pill (${s.n} shown${s.compact ? ', second lines hidden' : ''}${s.bare ? ', weather hidden' : ''}${s.over.length ? ', in More: ' + s.over.join(' ') : ''})`);
    check(s.more, `${w} x ${h}: More is on the strip`);
    check(await noOverflow(lp), `${w} x ${h}: the page does not scroll sideways`);
    if (s.over.length) {
      await lp.locator('#realmMore').click(); await lp.locator('#moreSheet[open]').waitFor();
      const rows = await lp.locator('#moreList .srow').evaluateAll(es => es.map(e => e.dataset.id));
      check(s.over.every(id => rows.includes(id)), `${w} x ${h}: every folded place has a row in More (${rows.join(' ')})`);
      await lp.keyboard.press('Escape');
      // the place you are on never folds: open the last folded one and it is on the strip, marked current
      const last = s.over[0], href = await lp.locator(`#realms a.realm[data-id="${last}"]`).getAttribute('href');
      await lp.goto(new URL(href, BASE).href); await lp.waitForTimeout(800);
      const t = await strip(lp);
      check(!t.over.includes(last) && await lp.locator(`#realms a.realm.on[data-id="${last}"]`).isVisible() && t.row && t.inside && t.clear, `${w} x ${h}: on a place that folds elsewhere (${last}), its pill stays on the strip, marked current`);
    }
    if (w === 1024) check(await lp.locator('#realms').getByRole('link', {name: /^Argus(?![a-z])/}).count() === 1
      && (!s.compact || await lp.locator('#realms .realm small').evaluateAll(es => es.every(e => getComputedStyle(e).clipPath !== 'none'))),
      `1024: the Argus pill is named by the god alone (4.45.0); a second line (a link's, a coming one's) hidden here is still read out (compact: ${s.compact})`);
    await shot(lp, `layout-${w}-home`);
    check(lp.errors.length === 0, `${w} x ${h}: no page errors ` + lp.errors.join(' | '));
    await lp.close();
  }
  check(folded[1920].length <= folded[1024].length && folded[1024].length <= folded[800].length, `the wider the window, the fewer pills fold (in More at 1920: ${folded[1920].length}, 1024: ${folded[1024].length}, 800: ${folded[800].length})`);

  // 1920 x 1080, after the review of the first draft of 4.44.0: Today says the weather once (under the name; the strip's goes
  // there), and the strip keeps one shape from page to page (More naming the open page made it wider on Phone alerts alone,
  // and every second line went)
  {
    const wp = await page(b, 1920, 1080), shape = {};
    await wp.route('**/api/sky', r => r.fulfill({json: {sky: 'rain', desc: 'Light rain', is_day: true, temp: 48, unit: 'F', precip: 1, clouds: 90, wind: 10,
      south: false, at: Math.floor(Date.now() / 1000), source: 'Open-Meteo'}}));
    for (const where of ['home', 'argus', 'phone']) {
      await wp.goto(BASE + where); if (where === 'home') await settled(wp);
      await wp.waitForFunction(() => document.getElementById('wxText').textContent.trim(), null, {timeout: 5000}).catch(() => {});
      if (where === 'home') await wp.locator('#sub', {hasText: 'Light rain'}).waitFor({timeout: 3000}).catch(() => {});
      await wp.waitForTimeout(300);
      const s = await strip(wp);
      const wx = await wp.evaluate(() => [document.getElementById('wxText').offsetWidth > 0, /Light rain/.test(document.getElementById('sub').textContent)]);
      const xs = await wp.evaluate(() => [...document.querySelectorAll('#realms .realm')].filter(e => e.offsetWidth).map(e => Math.round(e.getBoundingClientRect().left)));
      shape[where] = {compact: s.compact, over: s.over.join(' '), xs: xs.join(' ')};
      if (where === 'home') check(!wx[0] && wx[1], `1920 x 1080: Today says the weather once, under the name (on the strip: ${wx[0]}, under the name: ${wx[1]})`);
      else check(wx[0], `1920 x 1080: on ${where} the weather is on the strip (${wx[0]})`);
    }
    const same = ['argus', 'phone'].every(k => JSON.stringify(shape[k]) === JSON.stringify(shape.home));
    check(same && !shape.home.compact, `1920 x 1080: the strip has one shape on Today, Argus and Phone alerts, second lines shown (${JSON.stringify(shape)})`);
    await wp.close();
  }

  // a way to Phone alerts at every width that cannot be dismissed (4.44.0): the More that is showing (the phone's bar under
  // 600 px, the strip or the ultrawide rail above) has it, also after "Not now" on Today's line; Esc gives the focus back
  for (const [w, h] of [[375, 812], [412, 915], [800, 360], [915, 412], [1024, 720], [1440, 900], [1920, 1080], [2560, 1080]]) {
    const q = await page(b, w, h); await q.goto(BASE + 'home'); await settled(q);
    const off = q.locator('#phoneHint [data-hint-off]'); if (await off.isVisible()) { await off.click(); await q.reload(); await settled(q); }
    const opener = q.locator('[data-more]:visible').first();
    check(await opener.count() === 1, `${w} x ${h}: a More button is showing`);
    await opener.click(); await q.locator('#moreSheet[open]').waitFor();
    const row = q.locator('#moreList .srow', {hasText: 'Phone alerts'});
    check(await row.isVisible(), `${w} x ${h}: More has Phone alerts`);
    await q.keyboard.press('Escape');   // the dialog's close event comes a moment after the key: wait for it, not for a fixed time
    check(await q.waitForFunction(() => !document.getElementById('moreSheet').open && document.activeElement?.matches('[data-more]') && document.activeElement.getAttribute('aria-expanded') === 'false', null, {timeout: 3000}).then(() => true, () => false),
      `${w} x ${h}: Esc closes More and the focus goes back to it`);
    if (w === 1440) {
      await opener.click(); await row.click(); await q.waitForURL(/\/phone$/); await q.waitForTimeout(500);
      check(await q.locator('#realmMore.on').isVisible() && /Phone alerts/.test(await q.locator('#realmMore').textContent()), '1440: on Phone alerts, the strip\'s More is the current one and names it');
    }
    await q.close();
  }
  // the phone bar's More names the open place in full: "Phone alerts" was cut to "Phone ale…" at 360 px (review of 4.44.0)
  for (const [w, h] of [[360, 800], [375, 812]]) {
    const q = await page(b, w, h); await q.goto(BASE + 'phone'); await q.locator('#tabs .more.on small').waitFor();
    await q.evaluate(() => document.fonts.ready);
    const fit = await q.evaluate(() => { const e = document.querySelector('#tabs .more.on small'); return {text: e.textContent, need: e.scrollWidth, has: e.clientWidth}; });
    check(fit.text === 'Phone alerts' && fit.need <= fit.has, `${w} x ${h}: the phone bar's More says "${fit.text}" in full (${fit.need} px of text in ${fit.has} px)`);
    await q.close();
  }

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'olympus'); await ph.waitForTimeout(800);
  const tb = await box(ph, '.tabbar'), more = ph.locator('.tabbar [data-more]');
  check(tb.y + tb.h >= 759 && tb.w >= 374 && await ph.locator('.realms').isHidden(), 'phone: the sections sit in a bar at the bottom instead of the strip');
  check(await more.evaluate(e => e.classList.contains('on')) && /Olympus/.test(await more.textContent()), 'phone: on a place inside More, the More slot is the current one and names it');
  await ph.goto(BASE + 'home'); await settled(ph);
  const [pn, pp] = await boxes(ph, '.home .needs', '.home .places');
  check(pn && pp && pp.y > pn.y && pn.w >= 340, `phone: Home is one column, full width (rows ${pn && pn.w} px wide)`);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  await ph.goto(BASE + 'argus'); await ph.locator('.card').first().waitFor();
  check((await box(ph, '.argus')).w <= 96, 'phone: Argus is 96 px, so the first task card shows sooner');
  await shot(ph, 'layout-phone-watch');

  const ls = await page(b, 844, 390); await ls.goto(BASE + 'argus'); await ls.locator('.card').first().waitFor();
  const lead = await ls.evaluate(() => (document.querySelector('#main .tblock') ? '.tblock' : '.card'));   // trouble first (4.40.0): the first broken block, else a card
  check((await box(ls, '.argus')).w <= 96 && (await box(ls, lead)).y < 390, `phone on its side: Argus shrinks and the first ${lead === '.tblock' ? 'trouble block' : 'task card'} shows on the first screen`);
  check(await noOverflow(ls), 'phone on its side: no sideways scrolling');

  // the weather in the line under the name stays in its own column on a narrow phone, even one word with no place to break
  // (4.44.0): before, the title's column grew to the word's width and pushed Argus 40 px past the edge of a 360 px screen
  // (the page hides sideways overflow, so the no-scrolling check never saw it)
  for (const w of [412, 360]) {
    const wp = await page(b, w, 800);
    await wp.route('**/api/sky', r => r.fulfill({json: {sky: 'snow', desc: 'Thundersnowwithfreezingdrizzleandsmallhailallafternoon', is_day: true, temp: -12, unit: 'F',
      precip: 1, clouds: 90, wind: 10, south: false, at: Math.floor(Date.now() / 1000), source: 'Open-Meteo'}}));
    await wp.goto(BASE); await wp.locator('#sub', {hasText: 'hail'}).waitFor({timeout: 5000}).catch(() => {});
    const r = await wp.evaluate(() => { const s = document.getElementById('sub'), g = document.createRange(); g.selectNodeContents(s);
      const a = document.getElementById('argus').getBoundingClientRect();
      return {text: s.textContent, right: Math.max(...[...g.getClientRects()].map(x => x.right)), w: innerWidth, al: a.left, ar: a.right}; });
    check(/allafternoon · -12°F$/.test(r.text) && r.right <= r.al && r.ar <= r.w, `${w}: a long weather word wraps; the text stays clear of Argus and Argus stays whole on the screen (text ends at ${Math.round(r.right)}, Argus ${Math.round(r.al)}-${Math.round(r.ar)} of ${r.w} px)`);
    check(await noOverflow(wp), `${w}: no sideways scrolling with it`);
    await wp.close();
  }
});
