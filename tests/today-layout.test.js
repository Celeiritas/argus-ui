// Today at a glance (4.45.0, docs/home.md; one column at every width since 4.54.0, "One way to each place"): no Sections tiles
// and no Open row at any width (links and media are in More), one line per section with news, the server's band in the theme's
// colours, the last thing on every page clear of the phone's bottom bar, and the strip's count clear of its pill's label.
// The fixture: two media players and two links (placeholders), the server's name in realm.json; every section quiet (the
// morning when nothing needs you), one with a line too long for one row and one with a single word too long for it.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CFG = path.join(HOME, '.config/argus-ui');
const MD = path.join(CFG, 'media.json'), LK = path.join(CFG, 'links.json'), RM = path.join(HOME, '.config/leafy/realm.json');
const LONG = 'Backing up the server now; no word from the backup of your computer yet, so nothing is copied off-site';
const WORD = 'Supercalifragilisticexpialidociousworkoutplannerline';
// a route handler whose page closed while its request was in flight (the next check already started) ends quietly;
// anything else still throws (CI 2f48fef: TargetClosedError from route.fetch failed the whole run)
const settle = fn => async r => { try { await fn(r); } catch (e) { if (!/closed|disposed/i.test(String(e && e.message))) throw e; } };
const LINKS = [{name: 'Notes', what: 'Pages', href: '/notes-test/'}, {name: 'Studio Test', what: 'Studio', href: '/studio-test/', section: true}];
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); });
// every section quiet but two long lines; no failed task, no failed check and no alert
// (own: each section keeps its own line, only quiet; need: Chiron asks for him, so the server's band stands on its own)
async function quiet(p, own = false, need = false) {
  if (own) await p.route('**/api/*/status', settle(async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); }));
  else {
    await p.route('**/api/*/status', r => r.fulfill({json: {line: 'All quiet', needs: false, action: ''}}));
    await p.route('**/api/demo-server/status', r => r.fulfill({json: {line: LONG, needs: false, action: ''}}));
    await p.route('**/api/chiron/status', r => r.fulfill({json: need ? {line: '1 workout skipped', needs: true, action: 'Plan a workout'} : {line: WORD, needs: false, action: ''}}));
  }
  await p.route('**/api/state', settle(async r => { const res = await r.fetch(), j = await res.json();
    (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(w => { if (w.works === false) w.works = true; });
    j.alerts = []; await r.fulfill({response: res, json: j}); }));
}
async function today(b, w, h, own = false, need = false) {
  const p = await page(b, w, h); await quiet(p, own, need); await p.goto(BASE);
  await p.evaluate(() => refresh()); await settled(p);         // the page opens on the state it was served with (INIT); this asks again, quiet
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
  return p;
}
// WCAG 2 contrast of two computed colours ("rgb(r, g, b)")
const lum = c => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
const anyGap = s => new RegExp(s.split('').map(c => /\s/.test(c) ? '\\s*' : c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*').join(''));
const THEME = {bg: 'rgb(58, 42, 94)', name: 'rgb(123, 216, 143)', words: 'rgb(203, 184, 255)', border: 'rgb(91, 74, 133)'};
// the calm band: "Nothing needs you" and the server's line in one panel, in the band's colours
const calmBand = p => p.evaluate(() => { const c = document.querySelector('.home > .needs.calm'), n = c && c.querySelector('.now'), nm = n && n.querySelector('.nowname');
  if (!c || !n || !nm) return null; const s = getComputedStyle(c);
  return {bg: s.backgroundColor, border: s.borderTopColor, h: c.querySelector('#needs-h').textContent, name: getComputedStyle(nm).color, words: getComputedStyle(n).color, nameText: nm.textContent,
    size: getComputedStyle(n).fontSize, weights: [getComputedStyle(nm).fontWeight, getComputedStyle(n).fontWeight].join(),
    alone: !document.querySelector('.home > .now') && document.querySelectorAll('.home .needs').length === 1}; });
run(async b => {
  fs.mkdirSync(CFG, {recursive: true}); fs.mkdirSync(path.dirname(RM), {recursive: true});
  fs.writeFileSync(MD, JSON.stringify({jellyfin: 'https://films.example/web/', audiobookshelf: 'https://books.example/'}));
  fs.writeFileSync(LK, JSON.stringify(LINKS)); fs.writeFileSync(RM, JSON.stringify({SERVER: 'Shelf'}));
  try {
    const t = await today(b, 412, 915);
    check(/Nothing needs you/.test(await t.locator('#needs-h').textContent()), `the fixture: nothing needs you (${(await t.locator('.home .needs').textContent()).replace(/\s+/g, ' ').slice(0, 300)})`);

    // 1. a phone: no tiles, no Open, and the whole of Today above the bottom bar
    const px = v => Math.round(v);
    const lastFit = p => p.evaluate(() => { scrollTo(0, 0); const r = s => document.querySelector(s).getBoundingClientRect(), k = [...document.querySelectorAll('.home > *')].filter(e => e.offsetHeight);
      return {first: k[0] && k[0].className, last: k.length ? k[k.length - 1].className : '', bottom: k.length ? r('.home > :last-child').bottom : 0, bar: r('.tabbar').top, tiles: document.querySelectorAll('.home .places, .placelist, .home .open').length}; });
    const fit = await lastFit(t);
    check(fit.tiles === 0 && fit.bottom <= fit.bar, `412 x 915: with nothing needing you, no tiles or Open and all of Today above the bottom bar (${fit.first} to ${fit.last}, ends at ${px(fit.bottom)}, bar at ${px(fit.bar)})`);
    const o = await today(b, 412, 915, true), of = await lastFit(o);
    check(of.tiles === 0 && of.bottom <= of.bar, `412 x 915: with the sections' own lines too (ends at ${px(of.bottom)}, bar at ${px(of.bar)})`);
    // a " · " keeps its dot on the line before, so a wrapped line never starts with it
    const dots = await o.evaluate(() => [...document.querySelectorAll('.news .qline .qt')].map(q => q.textContent).filter(s => s.includes('·')));
    check(dots.length >= 1 && dots.every(s => !/ ·/.test(s) && / ·/.test(s)), `a " · " keeps its dot on the line before (${JSON.stringify(dots)})`);
    await o.close();

    // 2. the section lines at 600 px: each one link, 44 px or more, its mark, its name 16/600 and its line 14 px under it
    const w6 = await today(b, 600, 915);
    const qs = await w6.locator('.news .qline').evaluateAll(es => es.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width), Math.round(r.height)]; }));
    check(qs.length >= 3 && qs.every(x => x[2] >= 44 && x[1] >= 44) && new Set(qs.map(x => x[0])).size === 1 && await w6.locator('.newslist li').evaluateAll(ls => ls.every(l => l.querySelectorAll('a').length === 1)),
      `600: one line a row, one column, each line one link at least 44 by 44 px (${JSON.stringify(qs)})`);
    const mark = await w6.locator('.news .qline').first().evaluate(a => { const m = a.querySelector('img,svg'), w = a.querySelector('.qw b'), l = a.querySelector('.qt'), c = a.querySelector('svg.chev');
      return [Math.round(m.getBoundingClientRect().width), getComputedStyle(w).fontSize, getComputedStyle(w).fontWeight, getComputedStyle(l).fontSize, l.getBoundingClientRect().top >= w.getBoundingClientRect().bottom - 1, !!c && Math.round(c.getBoundingClientRect().width)]; });
    check(JSON.stringify(mark) === '[28,"16px","600","14px",true,16]', `a line: a 28 px mark, the name 16/600, its line 14 px under it, the 16 px chevron (${JSON.stringify(mark)})`);
    // nothing is cut: a long line wraps, and one word wider than the row breaks inside the row, never past its edge
    const lines = await w6.evaluate(() => [...document.querySelectorAll('.news .qline .qt')].map(q => ({text: q.textContent.replace(/ /g, ' '), fits: q.scrollWidth <= q.clientWidth + 1,
      rows: Math.round(q.getBoundingClientRect().height / parseFloat(getComputedStyle(q).lineHeight)), inRow: q.getBoundingClientRect().right <= q.closest('.qline').getBoundingClientRect().right + 1})));
    const long = lines.find(l => l.text === LONG), word = lines.find(l => l.text === WORD);
    check(long && long.rows >= 2 && long.fits && long.inRow, `600: a long line wraps to ${long && long.rows} rows, all of it shown`);
    check(word && word.fits && word.inRow, '600: one word wider than the row breaks inside the row');
    check(await w6.getByRole('link', {name: anyGap(LONG)}).count() === 1 && await w6.getByRole('link', {name: anyGap(WORD)}).count() === 1, "each line's link says its whole line");
    check(await noOverflow(w6), '600: no sideways scrolling');

    // 3. the server's band, calm: "Nothing needs you" and the server's line in one panel at every width (4.54.0), in the theme's
    // colours, every text 4.5:1 or more; a theme without colours (themes/starter) gets the page's own neutral ones
    for (const [w, h] of [[412, 915], [600, 915], [1440, 900]]) {
      const p = w === 412 ? t : w === 600 ? w6 : await today(b, w, h);
      const c = await calmBand(p);
      check(c && c.h === 'Nothing needs you' && c.nameText === 'Shelf' && c.alone, `${w}: one band holds "Nothing needs you" and the server's line from realm.json, no second band (${JSON.stringify(c)})`);
      check(c && c.bg === THEME.bg && c.name === THEME.name && c.words === THEME.words && c.border === THEME.border && ratio(c.name, c.bg) >= 4.5 && ratio(c.words, c.bg) >= 4.5,
        `${w}: the calm band in the theme's colours, each text 4.5:1 or more (${c && [c.bg, c.name, c.words, c.border].join(', ')})`);
      check(c && c.size === '16px' && c.weights === '600,400', `${w}: 16 px, the name 600 and the words 400 (${c && c.size}, ${c && c.weights})`);
      if (w === 1440) { await shot(p, 'today-1440-calm'); await p.close(); }
    }
    await w6.evaluate(() => [...document.querySelectorAll('style')].filter(s => /--server-bg/.test(s.textContent)).forEach(s => s.remove()));
    const nb = await calmBand(w6), nn = nb ? ratio(nb.name, nb.bg) : 0, nw = nb ? ratio(nb.words, nb.bg) : 0;
    check(nb && nb.bg === 'rgb(35, 42, 49)' && nn >= 4.5 && nw >= 4.5, `without the theme's colours the band is neutral (${nb && nb.bg}; name ${nn.toFixed(2)}:1, words ${nw.toFixed(2)}:1)`);
    await w6.close();
    // something needs him: the server's line is a band of its own under the list, across Today, in the theme's colours
    for (const w of [412, 1440]) {
      const p = await today(b, w, 900, false, true);
      const bd = await p.evaluate(() => { const n = document.querySelector('.home > p.now'), nm = n && n.querySelector('.nowname'), h = document.querySelector('.home'), s = document.querySelector('.home .needs');
        if (!n || !nm) return null; const c = getComputedStyle(n), r = n.getBoundingClientRect();
        return {bg: c.backgroundColor, words: c.color, name: getComputedStyle(nm).color, text: n.textContent, under: r.top >= s.getBoundingClientRect().bottom - 1,
          dl: r.left - s.getBoundingClientRect().left, dw: r.width - h.getBoundingClientRect().width, cursor: c.cursor, role: n.getAttribute('role'), anim: c.animationName + ' ' + c.transitionDuration}; });
      check(bd && bd.text.startsWith('Shelf: ') && bd.under && Math.abs(bd.dl) <= 1 && Math.abs(bd.dw) <= 1, `${w}: with a row to do, the server's band stands under the list, across Today (${JSON.stringify(bd)})`);
      check(bd && bd.bg === THEME.bg && bd.name === THEME.name && bd.words === THEME.words && ratio(bd.name, bd.bg) >= 4.5 && ratio(bd.words, bd.bg) >= 4.5, `${w}: in the theme's colours, 4.5:1 or more`);
      check(bd && bd.cursor === 'auto' && !bd.role && /^none 0s/.test(bd.anim), `${w}: not a button and not moving (${bd && [bd.cursor, bd.role, bd.anim]})`);
      await p.close();
    }
    await t.close();

    // 4. one column at every width, no tiles, no Open, links and media off Today (they are in More), no sideways scrolling
    for (const [w, h] of [[360, 800], [375, 812], [600, 800], [915, 412], [1024, 768], [1920, 1080]]) {
      const q = await today(b, w, h, true);
      const lay = await q.evaluate(() => ({tiles: document.querySelectorAll('.home .places, .placelist, .home .open, .home #editToday').length,
        links: document.querySelectorAll('.home a[href*="films.example"], .home a[href*="books.example"], .home a[href="/notes-test/"], .home a[href="/studio-test/"]').length,
        lefts: [...new Set([...document.querySelectorAll('.home > *')].filter(e => e.offsetHeight).map(e => Math.round(e.getBoundingClientRect().left)))]}));
      check(!lay.tiles && !lay.links && lay.lefts.length === 1, `${w} x ${h}: one column, no tiles, no Open, no links on Today (${JSON.stringify(lay)})`);
      check(await noOverflow(q), `${w} x ${h}: no sideways scrolling`);
      await q.close();
    }

    // 5. the last thing on every page scrolls clear of the phone's bottom bar
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

    // 6. the strip's count keeps clear of its pill's label ("1" touched the A of Approvals), with two digits too
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
