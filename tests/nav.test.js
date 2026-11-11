// Finding your way (docs/home.md): on a phone a bottom bar with Today, Watch, Study, Approvals and More; More opens a sheet with
// the rest; wider screens show the same places as a strip. Plain word first, realm name small; counts only when something needs
// you; keyboard, focus, aria-current; nothing hides behind the bar; the marker moves (not under reduced motion); roles.
const {BASE, check, page, noOverflow, units, run} = require('./lib');
const slots = p => p.locator('#tabbar .tab').evaluateAll(ts => ts.map(t => [t.querySelector('b').textContent, t.querySelector('small')?.textContent || '']));
run(async b => {
  units(u => { u['hermes-rename'].Result = 'exit-code'; });   // one failed task, whatever the checks before did
  for (const w of [360, 412]) {
    const p = await page(b, w, 800); await p.goto(BASE); await p.waitForTimeout(1200);
    const s = await slots(p);
    check(JSON.stringify(s) === JSON.stringify([['Today', ''], ['Watch', 'Argus'], ['Study', 'Mentor'], ['Approvals', 'Zeus'], ['More', '']]), `${w}: five slots, plain word first and the realm small: ${s.map(x => x.join('/')).join(', ')}`);
    check(await p.locator('.realms').isHidden() && await p.locator('#tabbar').isVisible(), `${w}: the bar is at the bottom; the top strip is gone`);
    const bar = await p.locator('#tabbar').boundingBox();
    check(Math.round(bar.y + bar.height) === 800 && bar.width === w, `${w}: the bar sits on the bottom edge, full width`);
    const sizes = await p.locator('#tabbar .tab').evaluateAll(ts => ts.map(t => { const r = t.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }));
    check(sizes.every(([sw, sh]) => sw >= 44 && sh >= 44), `${w}: every slot is at least 44 by 44 px (${sizes.map(x => x.join('x')).join(' ')})`);
    const cut = await p.locator('#tabbar .tab b').evaluateAll(bs => bs.filter(x => x.scrollWidth > x.clientWidth + 1).map(x => x.textContent));
    check(cut.length === 0, `${w}: no word is cut short ${cut.join(', ')}`);
    check(await p.locator('#tabbar .tab.on').getAttribute('aria-current') === 'page' && /Today/.test(await p.locator('#tabbar .tab.on').textContent()), `${w}: Today is marked as the current place (aria-current)`);
    check(/static\/icons\/zeus\.png$/.test(await p.locator('#tabbar .tab[data-id=throne] img').getAttribute('src')), `${w}: Approvals wears Zeus's medallion`);
    const watchCount = (await p.locator('#tabbar .tab[data-id=argus] .tabcount').textContent()).trim(), want = await p.evaluate(() => needCount('argus'));
    check(want > 0 && watchCount === String(want) && await p.locator('#tabbar .tab[data-id=argus] .sr').textContent() === `, ${want} need${want === 1 ? 's' : ''} you`, `${w}: Watch counts the failed task (${watchCount}), and says so to a screen reader`);
    check(await p.locator('#tabbar .tab[data-id=throne] .tabcount').count() === 1 && await p.locator('#tabbar .tab[data-id=home] .tabcount').count() === 0, `${w}: Approvals is marked (a deploy waits); Today carries no count`);
    const fs = await p.locator('#tabbar .tabcount').first().evaluate(e => parseFloat(getComputedStyle(e).fontSize));
    check(fs >= 12, `${w}: the count is at least 12 px text (${fs})`);
    check(await noOverflow(p), `${w}: no sideways scrolling`);
    check(/safe-area-inset-bottom/.test(await p.evaluate(() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } }).map(r => r.cssText).join(' '))), `${w}: the bar keeps clear of the phone's own gesture bar (safe-area padding)`);

    // nothing hides behind the bar: scrolled to the end, the last controls of Watch sit above it
    await p.goto(BASE + 'argus'); await p.waitForTimeout(800);
    const hidden = await p.evaluate(() => { scrollTo(0, document.documentElement.scrollHeight); const top = document.getElementById('tabbar').getBoundingClientRect().top;
      return [...document.querySelectorAll('main a[href],main button,main summary')].filter(e => { const r = e.getBoundingClientRect(); return r.height && r.bottom > top + 1; }).length; });
    check(hidden === 0, `${w}: scrolled to the end of Watch, nothing is behind the bar`);

    // More: a sheet with the rest; Escape and Close shut it and give focus back to More
    await p.goto(BASE); await p.waitForTimeout(800);
    const more = p.locator('#tabbar [data-more]');
    await more.click(); await p.waitForTimeout(300);
    const sheet = p.locator('#moreSheet');
    check(await sheet.isVisible() && await more.getAttribute('aria-expanded') === 'true', `${w}: More opens the sheet`);
    const rows = await p.locator('#moreList .srow b').allTextContents();
    check(rows[0] === 'Backups' && rows[1] === 'Playground' && rows.includes('Controllers') && rows.includes('Spartamelee'), `${w}: the sheet lists the other places: ${rows.join(', ')}`);
    check(/static\/icons\/mnemosyne\.png$/.test(await p.locator('#moreList .srow[data-id=memory] img').getAttribute('src')) && /Mnemosyne/.test(await p.locator('#moreList .srow[data-id=memory]').textContent()), `${w}: Backups wears Mnemosyne's medallion and names her`);
    check(await p.locator('#muteMore').isVisible(), `${w}: the sound switch is in the sheet`);
    const sm = await p.locator('#moreSheet a, #moreSheet button').evaluateAll(es => es.map(e => e.getBoundingClientRect()).filter(r => r.width && (r.width < 44 || r.height < 44)).length);
    check(sm === 0, `${w}: every control in the sheet is at least 44 px`);
    await p.keyboard.press('Escape'); await p.waitForTimeout(200);
    check(!await sheet.isVisible() && await p.evaluate(() => document.activeElement?.dataset.more !== undefined) && await more.getAttribute('aria-expanded') === 'false', `${w}: Escape closes it and focus goes back to More`);
    await more.click(); await p.waitForTimeout(250); await p.locator('#moreClose').click(); await p.waitForTimeout(200);
    check(!await sheet.isVisible(), `${w}: Close closes it`);
    await more.click(); await p.waitForTimeout(250);
    await p.locator('#moreList .srow', {hasText: 'Backups'}).click(); await p.waitForURL(/\/memory$/); await p.waitForTimeout(600);
    check(await p.locator('#tabbar [data-more]').evaluate(e => e.classList.contains('on')) && /Backups/.test(await p.locator('#tabbar [data-more] small').textContent()), `${w}: inside More, the More slot is current and names the place`);
    check(p.errors.length === 0, `${w}: no page errors ` + p.errors.join(' | '));
  }

  // the marker slides from the slot you left to the one you are on (200 ms); keyboard reaches every slot
  const p = await page(b, 412, 900); await p.goto(BASE); await p.waitForTimeout(600);
  await p.locator('#tabbar .tab[data-id=mentor]').click(); await p.waitForURL(/\/mentor$/);
  await p.waitForTimeout(100); const slid = await p.evaluate(() => placeMarker.slid === true);
  check(slid, 'arriving from Today, the marker slides over to Study');
  await p.waitForTimeout(400);
  const mk = await p.evaluate(() => { const m = document.querySelector('.tabmark').getBoundingClientRect(), t = document.querySelector('.tab.on').getBoundingClientRect(); return Math.abs((m.left + m.width / 2) - (t.left + t.width / 2)); });
  check(mk < 2, 'and stops over the current slot');
  await p.goto(BASE + 'argus'); await p.waitForTimeout(600);
  const tabbed = [];
  for (let i = 0; i < 80 && tabbed.length < 5; i++) { await p.keyboard.press('Tab'); const id = await p.evaluate(() => document.activeElement?.closest('#tabbar') ? (document.activeElement.dataset.id || 'more') : null); if (id && !tabbed.includes(id)) tabbed.push(id); }
  check(tabbed.join(' ') === 'home argus mentor throne more', `Tab reaches every slot, in order, after the page (${tabbed.join(' ')})`);
  const ring = await p.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
  check(ring !== 'none', 'a focused slot shows a focus ring');

  // reduced motion: the marker and the sheet just appear
  const q = await page(b, 412, 900); await q.emulateMedia({reducedMotion: 'reduce'});
  await q.goto(BASE); await q.waitForTimeout(400); await q.locator('#tabbar .tab[data-id=argus]').click(); await q.waitForURL(/\/argus\/argus$/); await q.waitForTimeout(100);
  check(await q.evaluate(() => placeMarker.slid !== true && document.querySelector('.tabmark').getAnimations().length === 0), 'reduced motion: the marker does not slide');
  await q.locator('#tabbar [data-more]').click(); await q.waitForTimeout(50);
  check(await q.locator('#moreSheet').evaluate(e => getComputedStyle(e).animationName) === 'none', 'reduced motion: the sheet does not slide up');

  // roles: until the server says who is asking, everyone is the owner; a learner sees Today and Study only
  check(await p.evaluate(() => role()) === 'owner', 'no role from the server: the owner');
  await p.goto(BASE); await p.waitForTimeout(500);
  await p.evaluate(() => { S.role = 'learner'; render(); }); await p.waitForTimeout(400);   // the rows a learner does not see fade out first
  check(JSON.stringify((await slots(p)).map(x => x[0])) === '["Today","Study"]' && await p.locator('#tabbar [data-more]').count() === 0, 'a learner: the bar shows Today and Study, and no More');
  const lr = await p.locator('#main .need:not(.leaving), #main .place').evaluateAll(es => es.map(e => e.querySelector('[data-id]')?.dataset.id || e.dataset.id || e.textContent.trim().slice(0, 20)));
  check(await p.locator('#main .need:not(.leaving) a.go', {hasText: /failed|Review/}).count() === 0 && await p.locator('#main .place', {hasText: 'Watch'}).count() === 0, `a learner: no failed tasks, deploys or Watch on Today (${lr.join(' | ')})`);
  await p.setViewportSize({width: 1440, height: 900}); await p.evaluate(() => render());
  check(JSON.stringify(await p.locator('#realms a.realm b').allTextContents()) === '["Today","Study"]', 'a learner on a wide screen: the strip shows the same two');

  // wide screens: the same places as a strip, in the same order, no bottom bar
  const d = await page(b, 1440, 900); await d.goto(BASE); await d.waitForTimeout(800);
  const strip = await d.locator('#realms a.realm b').allTextContents();
  check(strip.slice(0, 6).join(' ') === 'Today Watch Study Approvals Backups Playground' && await d.locator('#tabbar').isHidden(), `1440: the strip, in the same order (${strip.slice(0, 7).join(', ')}), and no bottom bar`);
  check(await noOverflow(d), '1440: no sideways scrolling');
});
