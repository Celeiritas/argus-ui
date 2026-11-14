// Today at a glance (4.45.0, docs/home.md): Sections as compact tiles (two a row on a phone, the line cut at a word to two
// lines), Open's chips under a small label for each kind when there is more than one, the server's band in the theme's
// colours, the last thing on every page clear of the phone's bottom bar, and the strip's count clear of its pill's label.
// The fixture: two media players, links in two groups, the server's name in realm.json; every section quiet (the morning
// when nothing needs you), one with a line too long for its tile and one with a single word too long for it.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CFG = path.join(HOME, '.config/argus-ui');
const MD = path.join(CFG, 'media.json'), LK = path.join(CFG, 'links.json'), RM = path.join(HOME, '.config/leafy/realm.json');
const LONG = 'Backing up the server now; no word from the backup of your computer yet, so nothing is copied off-site';
const WORD = 'Supercalifragilisticexpialidociousworkoutplannerline';
const LINKS = [{name: 'Notes', what: 'Pages', href: '/notes-test/', group: 'Tools'}, {name: 'Sound Lab', what: 'Studio', href: '/studio-test/', group: 'Studio'},
  {name: 'Files', what: 'Shared files', href: '/files-test/', group: 'Tools'}];
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); });
// every section quiet but two long lines; no failed task, no failed check and no alert
// (own: each section keeps its own line, only quiet)
async function quiet(p, own = false) {
  if (own) await p.route('**/api/*/status', async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); });
  else {
    await p.route('**/api/*/status', r => r.fulfill({json: {line: 'All quiet', needs: false, action: ''}}));
    await p.route('**/api/demo-server/status', r => r.fulfill({json: {line: LONG, needs: false, action: ''}}));
    await p.route('**/api/heracles/status', r => r.fulfill({json: {line: WORD, needs: false, action: ''}}));
  }
  await p.route('**/api/state', async r => { const res = await r.fetch(), j = await res.json();
    (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(w => { if (w.works === false) w.works = true; });
    j.alerts = []; await r.fulfill({response: res, json: j}); });
}
async function today(b, w, h, own = false) {
  const p = await page(b, w, h); await quiet(p, own); await p.goto(BASE);
  await p.evaluate(() => refresh()); await settled(p);         // the page opens on the state it was served with (INIT); this asks again, quiet
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
  return p;
}
// WCAG 2 contrast of two computed colours ("rgb(r, g, b)")
const lum = c => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
const anyGap = s => new RegExp(s.split('').map(c => /\s/.test(c) ? '\\s*' : c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*').join(''));
run(async b => {
  fs.mkdirSync(CFG, {recursive: true}); fs.mkdirSync(path.dirname(RM), {recursive: true});
  fs.writeFileSync(MD, JSON.stringify({jellyfin: 'https://films.example/web/', audiobookshelf: 'https://books.example/'}));
  fs.writeFileSync(LK, JSON.stringify(LINKS)); fs.writeFileSync(RM, JSON.stringify({SERVER: 'Shelf'}));
  try {
    const t = await today(b, 412, 915);
    check(/Nothing needs you/.test(await t.locator('#needs-h').textContent()), `the fixture: nothing needs you (${(await t.locator('.home .needs').textContent()).replace(/\s+/g, ' ').slice(0, 300)})`);

    // 1. Sections: compact tiles, two a row on a phone; each one link, 44 px or more; the whole of Today above the bottom bar
    const tiles = await t.locator('.placelist .place').evaluateAll(es => es.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }));
    const row1 = tiles.filter(x => Math.abs(x[0] - tiles[0][0]) < 2).length;
    check(tiles.length >= 8 && row1 === 2, `412: Sections are tiles, two a row (${tiles.length} tiles, ${row1} in the first row, ${tiles[0] && tiles[0][1]} px wide)`);
    check(tiles.every(x => x[1] >= 44 && x[2] >= 44) && await t.locator('.placelist li').evaluateAll(ls => ls.every(l => l.querySelectorAll('a').length === 1)),
      `each tile is one link at least 44 by 44 px (heights ${[...new Set(tiles.map(x => x[2]))].join(', ')})`);
    const mark = await t.locator('.placelist .place').first().evaluate(a => { const m = a.querySelector('img,svg'), w = a.querySelector('.pw b'), l = a.querySelector('.pl');
      return [Math.round(m.getBoundingClientRect().width), getComputedStyle(w).fontSize, getComputedStyle(w).fontWeight, getComputedStyle(l).fontSize, l.getBoundingClientRect().top >= w.getBoundingClientRect().bottom - 1]; });
    check(JSON.stringify(mark) === '[32,"14px","600","12px",true]', `a tile: a 32 px mark, the word 14/600, the line 12 px under it (${JSON.stringify(mark)})`);
    const fit = await t.evaluate(() => { scrollTo(0, 0); const r = s => document.querySelector(s).getBoundingClientRect();
      return {band: [r('.home > .now').top, r('.home > .now').bottom], needs: r('.home .needs').bottom, open: r('.home .open').bottom, places: [r('.home .places').top, r('.home .places').bottom], bar: r('.tabbar').top}; });
    const px = v => Math.round(v);
    check(fit.places[1] <= fit.bar, `412 x 915: with nothing needing you, all of Today is above the bottom bar (band ${px(fit.band[0])}-${px(fit.band[1])}, state to ${px(fit.needs)}, Open to ${px(fit.open)}, Sections ${px(fit.places[0])}-${px(fit.places[1])}, bar at ${px(fit.bar)})`);
    // and with the sections' own lines, most of them two lines long
    const o = await today(b, 412, 915, true);
    const of = await o.evaluate(() => { scrollTo(0, 0); const r = s => document.querySelector(s).getBoundingClientRect();
      return {places: r('.home .places').bottom, bar: r('.tabbar').top, n: document.querySelectorAll('.place .pl').length,
        two: [...document.querySelectorAll('.place .pl')].filter(pl => pl.clientHeight > parseFloat(getComputedStyle(pl).lineHeight) * 1.5).length}; });
    check(of.n >= 8 && of.two >= 5 && of.places <= of.bar, `412 x 915: with the sections' own lines (${of.two} of ${of.n} on two lines) too (Sections end at ${px(of.places)}, bar at ${px(of.bar)})`);
    // the words of a row's tiles line up at the top, whichever line wraps; a wrapped line never starts with the "·" between two facts
    const rows = await o.evaluate(() => { const by = new Map(); document.querySelectorAll('.place').forEach(a => { const y = Math.round(a.getBoundingClientRect().top), w = a.querySelector('.pw b');
      by.set(y, [...(by.get(y) || []), Math.round(w.getBoundingClientRect().top)]); }); return [...by.values()].filter(r => r.length > 1); });
    check(rows.length >= 3 && rows.every(r => Math.max(...r) - Math.min(...r) <= 1), `the words in a row of tiles line up (${JSON.stringify(rows)})`);
    const dots = await o.evaluate(() => [...document.querySelectorAll('.place .pl')].map(pl => pl.textContent).filter(s => s.includes('·')));
    check(dots.length >= 1 && dots.every(s => !/ ·/.test(s) && / ·/.test(s)), `a " · " keeps its dot on the line before (${JSON.stringify(dots)})`);
    await o.close();

    // a line is cut after the last word that fits, never inside a word (one word wider than the tile is the only exception); the
    // link's name keeps the whole line
    const lines = await t.evaluate(() => [...document.querySelectorAll('.place .pl')].map(pl => { const sr = pl.querySelector('.sr'), full = pl.textContent;
      return {full, shown: sr ? full.slice(0, full.length - sr.textContent.length) : full, cut: pl.classList.contains('cut'), after: getComputedStyle(pl, '::after').content,
        fits: pl.scrollHeight <= pl.clientHeight + 1 && pl.scrollWidth <= pl.clientWidth + 1, lines: Math.round(pl.clientHeight / parseFloat(getComputedStyle(pl).lineHeight))}; }));
    const long = lines.find(l => l.full === LONG), word = lines.find(l => l.full === WORD);
    check(lines.every(l => l.fits && l.lines <= 2), `every line shows in two lines at most, nothing hidden past its edge (${lines.filter(l => !l.fits || l.lines > 2).map(l => l.full.slice(0, 24)).join(' | ') || 'all fit'})`);
    check(long && long.cut && /…/.test(long.after) && long.shown.length > 8 && LONG.startsWith(long.shown) && /^[\s,;:·.\-–—]/.test(LONG.slice(long.shown.length)) && /[\p{L}\p{N}]$/u.test(long.shown),
      `a long line is cut after a whole word, with "…" ("${long && long.shown}…")`);
    check(word && word.cut && word.shown.length >= 6 && WORD.startsWith(word.shown), `one word wider than its tile is cut inside it, the one exception ("${word && word.shown}…")`);
    check(await t.getByRole('link', {name: anyGap(LONG)}).count() === 1 && await t.getByRole('link', {name: anyGap(WORD)}).count() === 1, "and each tile's link still says its whole line");
    check(lines.filter(l => l.cut).length === 2, `a line that fits is not cut (${lines.filter(l => l.cut).length} cut)`);

    // 3. the server's band: across Today, lined up with the panels, in the theme's colours, every text 4.5:1 or more
    const band = () => t.evaluate(() => { const n = document.querySelector('.home > p.now'), nm = n && n.querySelector('.nowname'), h = document.querySelector('.home'), s = document.querySelector('.home .needs');
      if (!n || !nm) return null; const c = getComputedStyle(n), cn = getComputedStyle(nm), r = n.getBoundingClientRect();
      return {bg: c.backgroundColor, words: c.color, name: cn.color, border: c.borderTopColor, size: c.fontSize, weights: [cn.fontWeight, c.fontWeight], text: n.textContent, nameText: nm.textContent,
        dl: r.left - s.getBoundingClientRect().left, dw: r.width - h.getBoundingClientRect().width, gap: s.getBoundingClientRect().top - r.bottom,
        panelGap: document.querySelector('.home .open').getBoundingClientRect().top - s.getBoundingClientRect().bottom,
        lines: Math.round((r.height - parseFloat(c.paddingTop) - parseFloat(c.paddingBottom) - parseFloat(c.borderTopWidth) - parseFloat(c.borderBottomWidth)) / parseFloat(c.lineHeight)),
        cursor: c.cursor, role: n.getAttribute('role'), anim: c.animationName + ' ' + c.transitionDuration}; });
    const bd = await band();
    check(bd && bd.nameText === 'Shelf' && bd.text.startsWith('Shelf: '), `the band names the server from realm.json ("${bd && bd.text}")`);
    check(bd && bd.bg === 'rgb(58, 42, 94)' && bd.name === 'rgb(123, 216, 143)' && bd.words === 'rgb(203, 184, 255)' && bd.border === 'rgb(91, 74, 133)',
      `in the theme's colours: background ${bd && bd.bg}, name ${bd && bd.name}, words ${bd && bd.words}, border ${bd && bd.border}`);
    const rn = bd ? ratio(bd.name, bd.bg) : 0, rw = bd ? ratio(bd.words, bd.bg) : 0;
    check(rn >= 4.5 && rw >= 4.5, `each text 4.5:1 or more on the band (name ${rn.toFixed(2)}:1, words ${rw.toFixed(2)}:1)`);
    check(bd && bd.size === '16px' && bd.weights.join() === '600,400', `16 px, the name 600 and the words 400 (${bd && bd.size}, ${bd && bd.weights})`);
    check(bd && Math.abs(bd.dl) <= 1 && Math.abs(bd.dw) <= 1 && Math.abs(bd.gap - bd.panelGap) <= 1 && bd.gap >= 11 && bd.gap <= 17,
      `the band spans Today, lined up with the panel below, the same gap as between the panels (left ${bd && bd.dl}, width ${bd && bd.dw}, gap ${bd && bd.gap}, panels ${bd && bd.panelGap})`);
    check(bd && bd.lines === 1, `on a 412 px phone the band is one line (${bd && bd.lines})`);
    check(bd && bd.cursor === 'auto' && !bd.role && /^none 0s/.test(bd.anim), `not a button and not moving (${bd && [bd.cursor, bd.role, bd.anim]})`);
    // a theme without colours (themes/starter) gets the page's own neutral ones, readable too
    await t.evaluate(() => [...document.querySelectorAll('style')].filter(s => /--server-bg/.test(s.textContent)).forEach(s => s.remove()));
    const nb = await band(), nn = nb ? ratio(nb.name, nb.bg) : 0, nw = nb ? ratio(nb.words, nb.bg) : 0;
    check(nb && nb.bg === 'rgb(35, 42, 49)' && nn >= 4.5 && nw >= 4.5, `without the theme's colours the band is neutral (${nb && nb.bg}; name ${nn.toFixed(2)}:1, words ${nw.toFixed(2)}:1)`);
    await t.reload(); await settled(t);

    // 2. Open stays compact (4.45.0 round 2): no automatic labels; a label only for a links.json "group", inline at the start of
    // its chips on a phone (at most one more line than the same chips without labels), side by side on wide screens
    const groups = () => t.evaluate(() => ({labels: [...document.querySelectorAll('.home .open .opengroup')].map(h => [h.textContent, getComputedStyle(h).fontSize, getComputedStyle(h).fontWeight]),
      lists: [...document.querySelectorAll('.home .open ul.openlist')].map(u => [u.getAttribute('aria-labelledby') ? document.getElementById(u.getAttribute('aria-labelledby')).textContent : '', u.querySelectorAll('a.openlink').length]),
      marks: [...document.querySelectorAll('.home .open a.openlink')].every(a => a.querySelector('svg'))}));
    const openH = () => t.evaluate(() => Math.round(document.querySelector('.home .open').getBoundingClientRect().height));
    const chipRow = () => t.evaluate(() => { const a = document.querySelector('.home .open a.openlink'); return Math.round(a.getBoundingClientRect().height); });
    let g = await groups();
    check(JSON.stringify(g.labels.map(x => x[0])) === '["Tools","Studio"]' && g.labels.every(x => x[1] === '12px' && x[2] === '600'),
      `Open: a label only for each links.json group, none made up ("Watch and listen", "Other pages" gone), labels 12/600 (${JSON.stringify(g.labels)})`);
    check(JSON.stringify(g.lists) === '[["",2],["Tools",2],["Studio",1]]' && g.marks, `the players first with no label, then each group a list named by its label, every chip with its "opens elsewhere" mark (${JSON.stringify(g.lists)})`);
    const labelled = await openH();
    await shot(t, 'today-412-groups');
    // the same chips without their groups: the labels add at most one line on a 412 px phone
    fs.writeFileSync(LK, JSON.stringify(LINKS.map(({group, ...x}) => x)));
    await t.evaluate(() => refresh()); await t.waitForFunction(() => !document.querySelector('.home .open .opengroup'), null, {timeout: 3000}).catch(() => {});
    g = await groups();
    const bare = await openH(), row = await chipRow();
    check(g.labels.length === 0 && JSON.stringify(g.lists) === '[["",5]]', `links with no group: one list, no label, the chips as in 4.44.0 (${JSON.stringify(g)})`);
    check(labelled - bare <= row + 8, `412: the group labels add at most one line to Open (${bare} px without, ${labelled} px with; a line is ${row} px + gap)`);
    fs.writeFileSync(LK, JSON.stringify([...LINKS, {name: 'Garden', what: 'A page with no group', href: '/garden-test/'}]));
    await t.evaluate(() => refresh()); await t.locator('.home .open a.openlink', {hasText: 'Garden'}).waitFor({timeout: 3000}).catch(() => {});
    g = await groups();
    check(g.labels.map(x => x[0]).join() === 'Tools,Studio' && JSON.stringify(g.lists) === '[["",3],["Tools",2],["Studio",1]]',
      `a link without a group sits with the players, unlabelled; no "Other pages" (${g.labels.map(x => x[0]).join(', ')}; ${JSON.stringify(g.lists)})`);
    fs.unlinkSync(LK); await t.evaluate(() => refresh()); await t.waitForFunction(() => !document.querySelector('.home .open .opengroup'), null, {timeout: 3000}).catch(() => {});
    g = await groups();
    check(g.labels.length === 0 && JSON.stringify(g.lists) === '[["",2]]', `with one kind (the players alone), no label (${JSON.stringify(g)})`);
    fs.writeFileSync(LK, JSON.stringify(LINKS));
    await t.close();

    // two a row down to 360 px; more on wider screens
    for (const [w, h, min] of [[360, 800, 2], [915, 412, 4], [1920, 1080, 6]]) {
      const q = await today(b, w, h);
      const xs = await q.locator('.placelist .place').evaluateAll(es => es.map(e => Math.round(e.getBoundingClientRect().top)));
      const n = xs.filter(y => Math.abs(y - xs[0]) < 2).length;
      check(w === 360 ? n === 2 : n >= min, `${w} x ${h}: ${n} tiles a row`);
      // Open's groups sit side by side where they fit, so a wide screen keeps Open about as short as before
      // (the players first, unlabelled, then the groups; flex-end lines them up by their bottoms)
      const blocks = await q.evaluate(() => { const o = document.querySelector('.home .open'); return {w: Math.round(o.getBoundingClientRect().width),
        b: [...o.querySelectorAll('.opengroups > *')].map(e => { const r = e.getBoundingClientRect(); return [r.left, r.bottom, r.width].map(Math.round); })}; });
      const rows = new Set(blocks.b.map(x => x[1])).size;
      if (w >= 915) check(blocks.b.length === 3 && rows < 3, `${w} x ${h}: Open's blocks sit side by side where they fit: ${rows} rows for 3 (Open ${blocks.w} px: ${blocks.b.map(x => x.join(',')).join(' | ')})`);
      check(await noOverflow(q), `${w} x ${h}: no sideways scrolling`);
      await q.close();
    }
    const ph = await today(b, 375, 812);
    check(await noOverflow(ph), '375 x 812: no sideways scrolling with the band, the groups and the tiles');
    await ph.close();

    // 4. the last thing on every page scrolls clear of the phone's bottom bar
    const pb = await page(b, 360, 800); await pb.goto(BASE); await settled(pb);
    const hrefs = [...new Set([...await pb.evaluate(() => sections().filter(e => !e.kind).map(e => e.href)), new URL('phone', BASE).pathname])];
    const under = [];
    for (const h of hrefs) {
      await pb.goto(new URL(h, BASE).href); await pb.waitForTimeout(900);
      const r = await pb.evaluate(() => { scrollTo(0, document.documentElement.scrollHeight); const kids = [...document.querySelectorAll('#main > *')].filter(e => e.offsetHeight && !/fixed|absolute/.test(getComputedStyle(e).position));
        const bar = document.querySelector('.tabbar').getBoundingClientRect().top; return [Math.round(Math.max(0, ...kids.map(e => e.getBoundingClientRect().bottom))), Math.round(bar)]; });
      if (r[0] > r[1]) under.push(`${h.replace(/.*\//, '') || 'today'} ${r[0]} > ${r[1]}`);
    }
    check(hrefs.length >= 8 && !under.length, `360 x 800: on each of ${hrefs.length} pages the last thing scrolls clear of the bottom bar${under.length ? ' (under it: ' + under.join(', ') + ')' : ''}`);
    await pb.close();

    // 5. the strip's count keeps clear of its pill's label ("1" touched the A of Approvals), with two digits too
    for (const [w, h] of [[915, 412], [1920, 1080]]) {
      const q = await page(b, w, h); await q.goto(BASE); await settled(q); await q.evaluate(() => document.fonts.ready);
      const gaps = await q.evaluate(() => { const gap = e => { const d = e.querySelector('.dot'), l = e.querySelector('b'); return d && d.offsetWidth && l && l.offsetWidth ? [l.textContent, d.textContent, Math.round(l.getBoundingClientRect().left - d.getBoundingClientRect().right), Math.round(d.getBoundingClientRect().left - e.getBoundingClientRect().left)] : null; };
        const one = [...document.querySelectorAll('#realms .realm')].map(gap).filter(Boolean), d = document.querySelector('#realms .realm[data-id="throne"] .dot');
        if (d) d.textContent = '12'; return [one, gap(d.closest('.realm'))]; });
      check(gaps[0].length >= 2 && gaps[0].every(x => x[2] >= 6), `${w} x ${h}: each count on the strip keeps 6 px or more from its label (${gaps[0].map(x => `${x[0]} "${x[1]}" ${x[2]} px`).join(', ')})`);
      check(gaps[1] && gaps[1][2] >= 6, `${w} x ${h}: and a two-digit count too (${gaps[1] && gaps[1][2]} px)`);
      const ones = gaps[0].filter(x => x[1].length === 1);
      check(ones.length >= 1 && ones.every(x => x[3] >= 26), `${w} x ${h}: a one-digit count covers no more of its icon than before (starts ${ones.map(x => x[3]).join(', ')} px into the pill)`);
      // the room is made by moving the label, never by widening the pill: a count that comes or goes must not reshape the strip
      const widths = await q.evaluate(() => { const e = document.querySelector('#realms .realm[data-id="throne"]'), d = e.querySelector('.dot'), was = d.textContent;
        const a = e.getBoundingClientRect().width; d.textContent = ''; const z = e.getBoundingClientRect().width; d.textContent = was; return [Math.round(a * 10) / 10, Math.round(z * 10) / 10]; });
      check(widths[0] === widths[1], `${w} x ${h}: a pill is as wide with a count as without one (${widths[0]} / ${widths[1]} px)`);
      if (w === 915) await shot(q, 'today-915-strip');
      await q.close();
    }
  } finally {
    for (const f of [MD, LK, RM]) fs.rmSync(f, {force: true});
  }
});
