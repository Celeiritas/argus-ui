// On a phone (4.52.0, docs/home.md "On a phone"): Today fits one screen in the owner's order of what matters, and Watch's
// groups that are all well fold to one line each. Wider screens keep their layout. The fixture: a failed task (so something
// needs you), then the same page made quiet by routes, as in tests/today-layout.test.js.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); });
async function quiet(p) {
  await p.route('**/api/state', async r => { const res = await r.fetch(), j = await res.json();
    (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(w => { if (w.works === false) w.works = true; });
    j.alerts = []; await r.fulfill({response: res, json: j}); });
}
// ten things that happened, newest first, for "What happened lately"
const EVENTS = {since: new Date(Date.now() - 864e5).toISOString(), events: Array.from({length: 10}, (_, i) => ({at: new Date(Date.now() - (i + 1) * 6e5).toISOString(), level: 'good', title: `Event ${i + 1}`}))};
const top = (p, s) => p.evaluate(s => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : null; }, s);
run(async b => {
  // 1. Today on a 412 px phone, with something that needs you
  const t = await page(b, 412, 915); await t.goto(BASE); await settled(t); await t.locator('.needs .need').first().waitFor({timeout: 5000});
  const order = await t.evaluate(() => [...document.querySelector('#main .home').children].map(e => e.className.split(' ')[0] + (e.classList.contains('first') ? '.first' : '')));
  check(await t.locator('.home.phone').count() === 1, 'a phone draws Today in its own order (.home.phone)');
  check(order.filter(c => c !== 'people-problem')[0] === 'needs.first', `what needs you comes first (${order.join(', ')})`);
  check(await t.locator('.home .places').count() === 0, 'no Sections tiles on a phone (the bottom bar reaches every section)');
  check(order[order.length - 1] === 'open', `Open is last (${order.join(', ')})`);
  check(await t.locator('.home .open #editToday').count() === 1, 'Edit Today sits beside Open\'s heading');
  check(await t.locator('.home .open .openlink small').evaluateAll(s => s.every(e => getComputedStyle(e).display === 'none')), "Open's chips without their small words");
  const ql = t.locator('.home > a.qline[data-id="mentor"]');
  check(await ql.count() === 1 && /Mentor/.test(await ql.textContent()) && /\/mentor$/.test(await ql.getAttribute('href')), `a quiet section with something to say is one line: "${(await ql.count()) ? (await ql.textContent()).replace(/\s+/g, ' ').trim() : 'none'}"`);
  const qh = await ql.evaluate(e => Math.round(e.getBoundingClientRect().height)).catch(() => 0);
  check(qh >= 44, `and a 44 px target (${qh} px)`);
  check(/^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), /.test(await t.locator('#sub').textContent()), `the date is short ("${await t.locator('#sub').textContent()}")`);
  const hd = await t.evaluate(() => { const r = s => document.querySelector(s)?.getBoundingClientRect(), m = document.querySelector('#modes');
    return {h1: r('.title h1'), sub: r('#sub'), modes: m && !m.hidden ? r('#modes') : null}; });
  check(hd.sub.top >= hd.h1.bottom - 1, 'the greeting and date sit under the name');
  if (hd.modes) check(Math.abs((hd.modes.top + hd.modes.bottom) / 2 - (hd.h1.top + hd.h1.bottom) / 2) < 16 && hd.modes.left > hd.h1.right, 'the Desktop/Game switch shares the name\'s line');
  check(await noOverflow(t), '412: no sideways scrolling');
  await shot(t, 'phone-today-412-needs');
  await t.setViewportSize({width: 375, height: 812}); await t.waitForTimeout(300);
  check(await noOverflow(t), '375: no sideways scrolling');
  // turning wider draws the computer layout again, and back
  await t.setViewportSize({width: 1024, height: 768}); await t.waitForTimeout(400);
  check(await t.locator('.home.phone').count() === 0 && await t.locator('.home .places').count() === 1, 'wider than a phone: the Sections tiles are back');
  await t.setViewportSize({width: 412, height: 915}); await t.waitForTimeout(400);
  check(await t.locator('.home.phone').count() === 1, 'narrow again: the phone order again');
  check(t.errors.length === 0, `no page errors (${t.errors.join(' | ')})`);
  await t.close();

  // 2. Today when nothing needs you: one band says it and the server's line, and all of Today is above the bottom bar
  const c = await page(b, 412, 915); await quiet(c); await c.goto(BASE); await c.evaluate(() => refresh()); await settled(c); await c.waitForTimeout(500);
  const calm = c.locator('.home > .needs.calm');
  if (await c.locator('.home .now').count()) {
    check(await calm.count() === 1 && /Nothing needs you/.test(await calm.locator('#needs-h').textContent()) && await calm.locator('.now').count() === 1, 'one band: "Nothing needs you" and the server\'s line');
    check(await c.locator('.home > .now').count() === 0, 'and no second band for the server');
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
  await shot(w, 'phone-watch-412');
  // a computer keeps every group open, devices after them, and every event
  await w.setViewportSize({width: 1440, height: 900}); await w.waitForTimeout(400);
  check(await w.locator('.persona.folded').count() === 0 && await w.locator('.latemore').count() === 0 && await evs() === 10, 'on a computer nothing is folded and every event shows');
  check(await top(w, '#devices') > await top(w, '.persona'), 'and Devices stay after the groups');
  await w.close();
});
