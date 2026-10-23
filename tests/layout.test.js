// Screen sizes (docs/ui-plan.md §14): a phone, a phone on its side, 16:9, and two ultrawides. Each page uses the width it
// has: nothing is squeezed into a one-word column, the sections bar becomes a left rail on ultrawides, and Argus never takes
// more than about a fifth of the height.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const box = (p, s) => p.locator(s).first().evaluate(e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; });
run(async b => {
  for (const [w, h, tag] of [[3440, 1440, 'ultrawide 3440'], [2560, 1080, 'ultrawide 2560']]) {
    const p = await page(b, w, h); await p.goto(BASE + 'home'); await p.locator('.home .places').waitFor(); await p.waitForTimeout(500);
    const rail = await box(p, '.realms'), main = await box(p, 'main');
    check(rail.x === 0 && rail.y === 0 && rail.h >= h - 1 && rail.w <= 220 && main.x >= rail.w, `${tag}: the sections bar is a rail down the left edge, beside the page`);
    const pills = await p.locator('#realms .realm').evaluateAll(es => es.map(e => e.getBoundingClientRect().x));
    check(pills.every(x => Math.abs(x - pills[0]) < 2), `${tag}: the sections stack in one column`);
    const needs = await box(p, '.home .needs'), places = await box(p, '.home .places');
    check(needs.w >= 500 && places.w >= 500 && Math.abs(needs.y - places.y) < 2, `${tag}: Home puts Needs you beside Places, each at least 500 px wide (was a one-word column)`);
    check(await noOverflow(p), `${tag}: no sideways scrolling`);
    await shot(p, 'layout-' + w + '-home');
    await p.goto(BASE); await p.locator('.card').first().waitFor(); await p.waitForTimeout(300);
    check((await box(p, 'header')).h <= h * 0.25, `${tag}: Watch's header takes at most a quarter of the height (${Math.round((await box(p, 'header')).h)} px)`);
    const cols = await p.locator('.grid').first().evaluate(g => getComputedStyle(g).gridTemplateColumns.split(' ').length);
    check(cols >= 7, `${tag}: Watch fits ${cols} task cards in a row`);
    await shot(p, 'layout-' + w + '-watch');
    await p.goto(BASE + 'demo-server'); await p.locator('.plugin-server .plugin-body').waitFor(); await p.waitForTimeout(300);
    check((await box(p, '.plugin-body')).w >= 1000, `${tag}: a server plugin's page gets the full content width`);
    check(p.errors.length === 0, `${tag}: no page errors ` + p.errors.join(' | '));
  }
  const d = await page(b, 1920, 1080); await d.goto(BASE + 'home'); await d.locator('.home .places').waitFor(); await d.waitForTimeout(300);
  const dbar = await box(d, '.realms'), dn = await box(d, '.home .needs'), dp = await box(d, '.home .places'), dm = await box(d, 'main');
  check(dbar.y === 0 && dbar.w >= 1900, '16:9: the sections bar stays across the top');
  check(Math.abs(dn.y - dp.y) < 2 && Math.abs(dn.x - dm.x - 16) < 2, '16:9: Home has two columns and lines up with the page edge (no second gutter)');
  await d.goto(BASE); await d.locator('.card').first().waitFor();
  check((await box(d, '.argus')).w <= 1080 * 0.22 + 1, '16:9: Argus is at most about a fifth of the height');
  await shot(d, 'layout-1920-home');

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'olympus'); await ph.waitForTimeout(800);
  const on = await box(ph, '.realm.on');
  check(on.x >= 0 && on.x + on.w <= 375, 'phone: the bar scrolls to show the section you are on (Olympus is past the edge otherwise)');
  await ph.goto(BASE + 'home'); await ph.locator('.home .places').waitFor();
  const pn = await box(ph, '.home .needs'), pp = await box(ph, '.home .places');
  check(pp.y > pn.y && pn.w >= 340, 'phone: Home is one column, full width');
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  await ph.goto(BASE); await ph.locator('.card').first().waitFor();
  check((await box(ph, '.argus')).w <= 128, 'phone: Argus is smaller, so the first task card shows sooner');
  await shot(ph, 'layout-phone-watch');

  const ls = await page(b, 844, 390); await ls.goto(BASE); await ls.locator('.card').first().waitFor();
  check((await box(ls, '.argus')).w <= 96 && (await box(ls, '.card')).y < 390, 'phone on its side: Argus shrinks and a task card shows on the first screen');
  check(await noOverflow(ls), 'phone on its side: no sideways scrolling');
});
