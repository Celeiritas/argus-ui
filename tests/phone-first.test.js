// On a phone (4.52.0, docs/home.md "On a phone"): Today fits one screen in the owner's order of what matters, and Watch's
// groups that are all well fold to one line each. Wider screens keep their layout. The fixture: a failed task (so something
// needs you), then the same page made quiet by routes, as in tests/today-layout.test.js.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); });
const settle = fn => async r => { try { await fn(r); } catch (e) { if (!/closed|disposed/i.test(String(e && e.message))) throw e; } };
// a player and a link when the server has none (no media.json or links.json in the fixture): since 4.54.0 they are in More, not on Today
const OPEN = {media: [{id: 'jellyfin', name: 'Jellyfin', what: 'Films', href: 'https://films.example/web/'}], links: [{name: 'Notes', what: 'Pages', href: '/notes-test/'}]};
// calm: a calm morning, as in tests/today-layout.test.js: nothing failed, no alerts, every section's own line needing nothing
async function fixture(p, calm) {
  await p.route('**/api/state*', settle(async r => { const res = await r.fetch(), j = await res.json();
    if (!(j.media || []).length && !(j.links || []).length) Object.assign(j, OPEN);
    if (calm) { (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(w => { if (w.works === false) w.works = true; }); j.alerts = []; }
    await r.fulfill({response: res, json: j}); }));
  if (calm) await p.route('**/api/*/status*', settle(async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); }));
}
// ten things that happened, newest first, for "What happened lately"
const EVENTS = {since: new Date(Date.now() - 864e5).toISOString(), events: Array.from({length: 10}, (_, i) => ({at: new Date(Date.now() - (i + 1) * 6e5).toISOString(), level: 'good', title: `Event ${i + 1}`}))};
const top = (p, s) => p.evaluate(s => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : null; }, s);
run(async b => {
  // 1. Today on a 412 px phone, with something that needs you
  const t = await page(b, 412, 915); await fixture(t, false); await t.goto(BASE); await t.evaluate(() => refresh()); await settled(t);   // the first state is inlined in the page: the route counts from the first refresh await t.locator('.needs .need').first().waitFor({timeout: 5000});
  const order = await t.evaluate(() => [...document.querySelector('#main .home').children].map(e => e.className.split(' ')[0] + (e.classList.contains('first') ? '.first' : '')));
  check(await t.locator('.home.phone').count() === 1, 'a phone draws Today in its own order (.home.phone)');
  check(order.filter(c => c !== 'people-problem')[0] === 'needs.first', `what needs you comes first (${order.join(', ')})`);
  // 4.54.0 (docs/home.md "One way to each place"): no tiles, no Open list and no Edit Today on Today; the sections' lines are last
  check(await t.locator('.home .places, .home .place, .home .open, #main #editToday').count() === 0, 'no tiles, no Open list and no Edit Today on Today (they are in More)');
  check(order[order.length - 1] === 'news', `the sections' lines are last (${order.join(', ')})`);
  const ql = t.locator('.home .news a.qline[data-id="mentor"]');
  check(await ql.count() === 1 && /Mentor/.test(await ql.textContent()) && /\/mentor$/.test(await ql.getAttribute('href')), `a quiet section with something to say is one line: "${(await ql.count()) ? (await ql.textContent()).replace(/\s+/g, ' ').trim() : 'none'}"`);
  const qh = await ql.evaluate(e => Math.round(e.getBoundingClientRect().height)).catch(() => 0);
  check(qh >= 44, `and a 44 px target (${qh} px)`);
  const sb = await t.locator('#sub').textContent();      // the greeting, then the date, then the weather
  check(/^Good (morning|afternoon|evening|night) · (Mon|Tue|Wed|Thu|Fri|Sat|Sun), (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}( · |$)/.test(sb), `the date is short ("${sb}")`);
  const hd = await t.evaluate(() => { const r = s => document.querySelector(s)?.getBoundingClientRect(), m = document.querySelector('#modes');
    return {h1: r('.title h1'), sub: r('#sub'), modes: m && !m.hidden ? r('#modes') : null}; });
  check(hd.sub.top >= hd.h1.bottom - 1, 'the greeting and date sit under the name');
  if (hd.modes) check(await t.locator('.home-server #modes').count() === 1 && hd.modes.top >= await t.locator('.home-server .now').evaluate(e => e.getBoundingClientRect().bottom), 'the Desktop/Game switch sits beneath the server status');
  // the visual review (2026-11-17): every row's picture and words start on one line, the broken row's red bar inside the card's
  // padding; the card is solid (the scene does not show through), its words 4.5:1 or more on it
  const al = await t.evaluate(() => { const s = document.querySelector('.home>.needs.first'), sl = s.getBoundingClientRect().left + s.clientLeft;
    return [...s.querySelectorAll('.need')].map(n => ({alert: n.classList.contains('alert'), row: n.getBoundingClientRect().left - sl, mark: n.querySelector('.nmark').getBoundingClientRect().left, words: n.querySelector('.nb').getBoundingClientRect().left})); });
  const spread = k => Math.max(...al.map(a => a[k])) - Math.min(...al.map(a => a[k]));
  check(al.length >= 2 && al.some(a => a.alert) && spread('mark') <= 1 && spread('words') <= 1, `the needs rows' pictures and words share one left edge, the broken one's too (pictures ${al.map(a => Math.round(a.mark)).join('/')}, words ${al.map(a => Math.round(a.words)).join('/')})`);
  check(al.filter(a => a.alert).every(a => a.row > 0), `and its red bar is inside the card (${al.filter(a => a.alert).map(a => Math.round(a.row)).join(', ')} px from its inner edge)`);
  const rgb = c => c.match(/[\d.]+/g).map(Number), lum = c => { const v = rgb(c).slice(0, 3).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return Math.round((x + .05) / (y + .05) * 10) / 10; };
  const nc = await t.evaluate(() => { const s = document.querySelector('.home>.needs.first');
    return {bg: getComputedStyle(s).backgroundColor, text: [...s.querySelectorAll('#needs-h, .need p, .need p small, .need .tl, .need .tl b')].filter(e => e.offsetHeight).map(e => getComputedStyle(e).color)}; });
  const alpha = rgb(nc.bg).length > 3 ? rgb(nc.bg)[3] : 1, lowest = Math.min(...nc.text.map(c => ratio(c, nc.bg)));
  check(alpha === 1 && nc.text.length >= 4 && lowest >= 4.5, `the needs card is solid (${nc.bg}, alpha ${alpha}), its words ${lowest}:1 or more on it`);
  check(await noOverflow(t), '412: no sideways scrolling');
  await shot(t, 'phone-today-412-needs');
  await t.setViewportSize({width: 375, height: 812}); await t.waitForTimeout(300);
  check(await noOverflow(t), '375: no sideways scrolling');
  // turning wider draws the computer layout again, and back
  await t.setViewportSize({width: 1024, height: 768}); await t.waitForTimeout(400);
  check(await t.locator('.home.phone').count() === 0 && await t.locator('.home .places, .home .place').count() === 0 && await t.locator('.home .news a.qline').count() > 0,
    'wider than a phone: the same lines, still no tiles (4.54.0)');
  await t.setViewportSize({width: 412, height: 915}); await t.waitForTimeout(400);
  check(await t.locator('.home.phone').count() === 1, 'narrow again: the phone order again');
  check(t.errors.length === 0, `no page errors (${t.errors.join(' | ')})`);
  await t.close();

  // 2. Today when nothing needs you: one band says it and the server's line, and all of Today is above the bottom bar
  const c = await page(b, 412, 915); await fixture(c, true); await c.goto(BASE); await c.evaluate(() => refresh()); await settled(c); await c.waitForTimeout(500);
  const calm = c.locator('.home > .needs.calm');
  if (await c.locator('.home .now').count()) {
    check(await calm.count() === 1 && /Nothing needs you/.test(await calm.locator('#needs-h').textContent()) && await calm.locator('.now').count() === 1, 'one band: "Nothing needs you" and the server\'s line');
    check(await c.locator('.home > .now').count() === 0, 'and no second band for the server');
    const nl = await calm.locator('.now').evaluate(n => [getComputedStyle(n, '::before').content, n.innerText.trim()]);
    check(/^(none|normal)$/.test(nl[0]) && !/^·/.test(nl[1]), `the server's line starts with its words, no stray "·" ("${nl[1]}", before: ${nl[0]})`);
  } else check(/Nothing needs you/.test(await c.locator('#needs-h').textContent()), 'nothing needs you (no server line in this fixture)');
  const fit = await c.evaluate(() => { scrollTo(0, 0); const kids = [...document.querySelector('#main .home').children];
    return [Math.round(Math.max(...kids.map(e => e.getBoundingClientRect().bottom))), Math.round(document.querySelector('.tabbar').getBoundingClientRect().top)]; });
  check(fit[0] <= fit[1], `412 x 915: all of Today is above the bottom bar (ends ${fit[0]}, bar ${fit[1]})`);
  await shot(c, 'phone-today-412-calm');
  await c.close();

  // 3. Watch on a phone: trouble, then Devices, then the groups; a group that is all well is one line; three events, then Show more
  const w = await page(b, 412, 915); await w.route('**/api/events*', r => r.fulfill({json: EVENTS}));
  await w.goto(BASE + 'argus'); await w.locator('.persona').first().waitFor({timeout: 5000}); await w.locator('.ev').first().waitFor({timeout: 5000});
  const dv = await top(w, '#devices'), p1 = await top(w, '.persona');
  check(dv !== null && dv < p1, `Devices come before the groups (${dv} < ${p1})`);
  const folded = w.locator('.persona.folded'), open = w.locator('.persona:not(.folded)');
  check(await folded.count() >= 1, `groups whose tasks all work are one line each (${await folded.count()} folded, ${await open.count()} open)`);
  check(await folded.locator('.dom').evaluateAll(d => d.every(e => /^All well · /.test(e.textContent))) && await folded.locator('.card').count() === 0, 'each says "All well · …" and shows no cards');
  const fh = await folded.first().locator('a.ph').evaluate(a => [Math.round(a.getBoundingClientRect().height), a.getAttribute('href')]);
  check(fh[0] >= 44 && /\/argus\/\w+$|\/\w+$/.test(fh[1]), `one link, 44 px or more, to its own page (${fh.join(', ')})`);
  check(await w.locator('.persona:not(.folded) .card', {hasText: 'rename'}).count() >= 1, 'a group with a failed task stays open (Hermes, its rename task)');
  check(await w.locator('.persona.folded#h-hermes, .persona.folded [id="h-hermes"]').count() === 0, 'Hermes is not folded');
  const evs = () => w.locator('.ev').evaluateAll(es => es.filter(e => e.offsetHeight).length);
  const more = w.locator('.latemore');
  check(await evs() === 3 && await more.isVisible() && await more.getAttribute('aria-expanded') === 'false', `What happened lately: the three newest, then Show more (${await evs()} shown)`);
  await more.click(); await w.waitForTimeout(100);
  check(await evs() === 10 && await more.getAttribute('aria-expanded') === 'true' && await more.textContent() === 'Show fewer', `Show more opens the rest (${await evs()} shown)`);
  await w.evaluate(() => render()); await w.waitForTimeout(100);
  check(await evs() === 10 && await w.locator('.latemore').getAttribute('aria-expanded') === 'true', 'and stays open across a redraw');
  await w.locator('.latemore').click(); await w.waitForTimeout(100);
  check(await evs() === 3, 'Show fewer folds it again');
  check(await noOverflow(w), 'Watch 412: no sideways scrolling');
  check(w.errors.length === 0, `no page errors on Watch (${w.errors.join(' | ')})`);
  // the visual review (2026-11-17): the marker for what is broken (out of view) sits bottom centre just above the bar on a phone and,
  // in a scroll sweep, never covers a control or a task's state pill (it used to sit on the top card's pill at the top right)
  await w.evaluate(() => scrollTo(0, 0)); await w.waitForTimeout(300);
  const sw = await w.evaluate(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms)), out = {shown: 0, hits: [], off: [], label: ''}, H = document.documentElement.scrollHeight - innerHeight;
    for (let y = 0; y <= H + 40; y += 40) {
      scrollTo(0, Math.min(y, H)); await wait(90);
      const e = document.getElementById('satEdge'); if (!e || e.hidden || getComputedStyle(e).display === 'none') continue;
      out.shown++; const m = e.getBoundingClientRect(), bar = document.getElementById('tabbar').getBoundingClientRect(), vw = document.documentElement.clientWidth;
      if (!out.label && !e.classList.contains('small')) out.label = e.textContent.trim();
      if (Math.abs((m.left + m.right) / 2 - vw / 2) > 2 || m.bottom > bar.top) out.off.push(`${y}: ${Math.round(m.left)}-${Math.round(m.right)} x ${Math.round(m.top)}-${Math.round(m.bottom)}, bar ${Math.round(bar.top)}`);
      for (const x of document.querySelectorAll('a[href],button,summary,input,select,textarea,[role=button],[role=link],[role=switch],.card .pill')) {
        if (x === e || e.contains(x)) continue; const r = x.getBoundingClientRect(); if (!r.width || !r.height) continue;
        if (Math.min(r.right, m.right) > Math.max(r.left, m.left) && Math.min(r.bottom, m.bottom) > Math.max(r.top, m.top)) out.hits.push(`${y}: ${(x.getAttribute('aria-label') || x.textContent).trim().slice(0, 24)}`);
      }
    }
    return out; });
  check(sw.shown >= 3 && sw.hits.length === 0, `412 scroll sweep: the marker shown at ${sw.shown} steps, over no control or state pill ${JSON.stringify(sw.hits.slice(0, 4))}`);
  check(sw.off.length === 0, `and it sits bottom centre, above the bar ${JSON.stringify(sw.off.slice(0, 3))}`);
  check(sw.label === 'See what needs a look' && await w.locator('#satEdge').getAttribute('aria-label') === 'See what needs a look', `its label is verb-first and is its name ("${sw.label}")`);
  await w.evaluate(() => scrollTo(0, 0)); await w.waitForTimeout(300);
  await w.evaluate(() => scrollTo(0, document.documentElement.scrollHeight)); await w.waitForTimeout(500);   // the full pill, for the picture
  await shot(w, 'phone-watch-412');
  // a computer keeps every group open, devices after them, and every event
  await w.setViewportSize({width: 1440, height: 900}); await w.waitForTimeout(400);
  check(await w.locator('.persona.folded').count() === 0 && await w.locator('.latemore').count() === 0 && await evs() === 10, 'on a computer nothing is folded and every event shows');
  check(await top(w, '#devices') > await top(w, '.persona'), 'and Devices stay after the groups');
  await w.close();
});
