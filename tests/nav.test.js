// Finding your way (docs/home.md): on a phone a bottom bar with Today, Argus, Mentor, Zeus and More; More opens a sheet with
// the rest; wider screens show the same places as a strip. The god's name is the only title (4.45.0); counts only when something needs
// you; keyboard, focus, aria-current; nothing hides behind the bar; the marker moves (not under reduced motion); roles.
const {BASE, check, page, noOverflow, units, run} = require('./lib');
const slots = p => p.locator('#tabbar .tab').evaluateAll(ts => ts.map(t => [t.querySelector('b').textContent, t.querySelector('small')?.textContent || '']));
run(async b => {
  let saved; units(u => { saved = JSON.stringify(u); });          // given back at the end, for the checks after this one
  units(u => Object.entries(u).forEach(([k, v]) => { if (k.startsWith('hermes-')) { v.Result = 'exit-code'; v.ActiveState = 'failed'; } }));   // failed tasks, whatever the checks before did (one may be frozen)
  for (const w of [360, 412]) {
    const p = await page(b, w, 800); await p.goto(BASE); await p.waitForTimeout(1200);
    const s = await slots(p);
    check(JSON.stringify(s) === JSON.stringify([['Today', ''], ['Argus', ''], ['Mentor', ''], ['Zeus', ''], ['More', '']]), `${w}: five slots, one word each, the god's name (4.45.0): ${s.map(x => x.join('/')).join(', ')}`);
    check(await p.locator('.realms').isHidden() && await p.locator('#tabbar').isVisible(), `${w}: the bar is at the bottom; the top strip is gone`);
    const bar = await p.locator('#tabbar').boundingBox();
    check(Math.round(bar.y + bar.height) === 800 && bar.width === w, `${w}: the bar sits on the bottom edge, full width`);
    const sizes = await p.locator('#tabbar .tab').evaluateAll(ts => ts.map(t => { const r = t.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }));
    check(sizes.every(([sw, sh]) => sw >= 44 && sh >= 44), `${w}: every slot is at least 44 by 44 px (${sizes.map(x => x.join('x')).join(' ')})`);
    const cut = await p.locator('#tabbar .tab b').evaluateAll(bs => bs.filter(x => x.scrollWidth > x.clientWidth + 1).map(x => x.textContent));
    check(cut.length === 0, `${w}: no word is cut short ${cut.join(', ')}`);
    check(await p.locator('#tabbar .tab.on').getAttribute('aria-current') === 'page' && /Today/.test(await p.locator('#tabbar .tab.on').textContent()), `${w}: Today is marked as the current place (aria-current)`);
    check(/static\/icons\/zeus\.png$/.test(await p.locator('#tabbar .tab[data-id=throne] img').getAttribute('src')), `${w}: Zeus wears his medallion`);
    const watchCount = (await p.locator('#tabbar .tab[data-id=argus] .tabcount').textContent()).trim(), want = await p.evaluate(() => needCount('argus'));
    check(want > 0 && watchCount === String(want) && await p.locator('#tabbar .tab[data-id=argus] .sr').textContent() === `, ${want} need${want === 1 ? 's' : ''} you`, `${w}: Argus counts the failed task (${watchCount}), and says so to a screen reader`);
    check(await p.locator('#tabbar .tab[data-id=throne] .tabcount').count() === 1 && await p.locator('#tabbar .tab[data-id=home] .tabcount').count() === 0, `${w}: Zeus is marked (a deploy waits); Today carries no count`);
    const fs = await p.locator('#tabbar .tabcount').first().evaluate(e => parseFloat(getComputedStyle(e).fontSize));
    check(fs >= 12, `${w}: the count is at least 12 px text (${fs})`);
    check(await noOverflow(p), `${w}: no sideways scrolling`);
    check(/safe-area-inset-bottom/.test(await p.evaluate(() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } }).map(r => r.cssText).join(' '))), `${w}: the bar keeps clear of the phone's own gesture bar (safe-area padding)`);

    // nothing hides behind the bar: scrolled to the end, the last controls of Watch sit above it
    await p.goto(BASE + 'argus'); await p.waitForTimeout(800);
    const hidden = await p.evaluate(() => { scrollTo(0, document.documentElement.scrollHeight); const top = document.getElementById('tabbar').getBoundingClientRect().top;
      return [...document.querySelectorAll('main a[href],main button,main summary')].filter(e => { const r = e.getBoundingClientRect(); return r.height && r.bottom > top + 1; }).length; });
    check(hidden === 0, `${w}: scrolled to the end of Watch, nothing is behind the bar`);
    for (const where of ['', 'argus']) {
      await p.goto(BASE + where); await p.waitForTimeout(900);
      const under = [];
      for (let i = 0; i < 60; i++) {
        await p.keyboard.press('Tab');
        const f = await p.evaluate(() => { const e = document.activeElement, bar = document.getElementById('tabbar');
          if (!e || e === document.body || bar.contains(e)) return {bar: !!e && bar.contains(e)};
          const r = e.getBoundingClientRect(); return {t: (e.getAttribute('aria-label') || e.textContent).trim().slice(0, 24), bottom: Math.round(r.bottom), top: Math.round(bar.getBoundingClientRect().top)}; });
        if (f.bar) break;
        if (f.bottom > f.top) under.push(`${f.t} ${f.bottom}>${f.top}`);
      }
      check(under.length === 0, `${w}: Tab through ${where || 'Today'}: no focused control is under the bar ${under.join(', ')}`);
    }

    // More: a sheet with the rest; Escape and Close shut it and give focus back to More
    await p.goto(BASE); await p.waitForTimeout(800);
    const more = p.locator('#tabbar [data-more]');
    await more.click(); await p.waitForTimeout(300);
    const sheet = p.locator('#moreSheet');
    check(await sheet.isVisible() && await more.getAttribute('aria-expanded') === 'true', `${w}: More opens the sheet`);
    const rows = await p.locator('#moreList .srow b').allTextContents();
    check(rows[0] === 'Mnemosyne' && rows[1] === 'Olympus' && rows.includes('Controllers') && rows.includes('Spartamelee'), `${w}: the sheet lists the other places: ${rows.join(', ')}`);
    check(/static\/icons\/mnemosyne\.png$/.test(await p.locator('#moreList .srow[data-id=memory] img').getAttribute('src')) && /Mnemosyne/.test(await p.locator('#moreList .srow[data-id=memory]').textContent()), `${w}: Mnemosyne wears her medallion and is named`);
    check(await p.locator('#muteMore').isVisible(), `${w}: the sound switch is in the sheet`);
    const sm = await p.locator('#moreSheet a, #moreSheet button').evaluateAll(es => es.map(e => e.getBoundingClientRect()).filter(r => r.width && (r.width < 44 || r.height < 44)).length);
    check(sm === 0, `${w}: every control in the sheet is at least 44 px`);
    await p.keyboard.press('Escape'); await p.waitForTimeout(200);
    check(!await sheet.isVisible() && await p.evaluate(() => document.activeElement?.dataset.more !== undefined) && await more.getAttribute('aria-expanded') === 'false', `${w}: Escape closes it and focus goes back to More`);
    await more.click(); await p.waitForTimeout(250); await p.locator('#moreClose').click(); await p.waitForTimeout(200);
    check(!await sheet.isVisible(), `${w}: Close closes it`);
    await more.click(); await p.waitForTimeout(250);
    await p.locator('#moreList .srow', {hasText: 'Mnemosyne'}).click(); await p.waitForURL(/\/memory$/); await p.waitForTimeout(600);
    check(await p.locator('#tabbar [data-more]').evaluate(e => e.classList.contains('on')) && /Mnemosyne/.test(await p.locator('#tabbar [data-more] small').textContent()), `${w}: inside More, the More slot is current and names the place`);
    await p.locator('#tabbar [data-more]').click(); await p.waitForTimeout(300);
    check(/255, 226, 122/.test(await p.locator('#moreSheet .srow.on').evaluate(e => getComputedStyle(e).boxShadow)), `${w}: in the sheet, the current place has a gold left edge`);
    await p.keyboard.press('Escape');
    check(p.errors.length === 0, `${w}: no page errors ` + p.errors.join(' | '));
  }

  // the marker slides from the slot you left to the one you are on (200 ms); keyboard reaches every slot
  const p = await page(b, 412, 900); await p.goto(BASE); await p.waitForTimeout(600);
  await p.locator('#tabbar .tab[data-id=mentor]').click(); await p.waitForURL(/\/mentor$/);
  await p.waitForTimeout(100); const slid = await p.evaluate(() => placeMarker.slid === true);
  check(slid, 'arriving from Today, the marker slides over to Mentor');
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
  await q.keyboard.press('Escape'); await q.goto(BASE + 'argus'); await q.waitForTimeout(600);
  check(await q.evaluate(() => { S.jobs[0].state = 'failed'; look.retarget(); return getComputedStyle(document.getElementById('argus'), '::before').animationName; }) === 'none', "reduced motion: Argus's red pulse (drawn in ::before) does not run");

  // a section's count is made a number before it is shown
  check(await p.evaluate(() => { STATUS.throne = {line: 'x', needs: true, count: '2'}; const a = needCount('throne'); STATUS.throne.count = '<img src=x>'; const b = needCount('throne'); return a === 2 && b === true; }), 'a count of "2" shows 2; a count that is not a number shows the plain mark');

  // roles: until the server says who is asking, everyone is the owner; a learner sees Today and Mentor only
  check(await p.evaluate(() => role()) === 'owner', 'no role from the server: the owner');
  await p.goto(BASE); await p.waitForTimeout(500);
  await p.evaluate(() => { S.role = 'learner'; render(); }); await p.waitForTimeout(400);   // the rows a learner does not see fade out first
  check(JSON.stringify((await slots(p)).map(x => x[0])) === '["Today","Mentor"]' && await p.locator('#tabbar [data-more]').count() === 0, 'a learner: the bar shows Today and Mentor, and no More');
  const lr = await p.locator('#main .need:not(.leaving), #main .place').evaluateAll(es => es.map(e => e.querySelector('[data-id]')?.dataset.id || e.dataset.id || e.textContent.trim().slice(0, 20)));
  check(await p.locator('#main .need:not(.leaving) a.go', {hasText: /failed|Review/}).count() === 0 && await p.locator('#main .place[data-id="argus"]').count() === 0, `a learner: no failed tasks, deploys or Argus on Today (${lr.join(' | ')})`);
  await p.setViewportSize({width: 1440, height: 900}); await p.evaluate(() => render());
  check(JSON.stringify(await p.locator('#realms a.realm b').allTextContents()) === '["Today","Mentor"]', 'a learner on a wide screen: the strip shows the same two');
  await p.evaluate(() => { window.chimed = 0; alarmChime = () => { window.chimed++; }; S.jobs.forEach((j, i) => { if (i < 2) j.state = 'failed'; }); look.retarget(); });
  check(await p.locator('#argus').isHidden() && await p.locator('#argus').getAttribute('aria-label') === null && await p.locator('#alarm').evaluate(e => !e.offsetParent), 'a learner: no Argus in the corner, no alarm badge, no words about the owner\'s tasks');
  check(await p.evaluate(() => { S.jobs.forEach(j => { j.state = 'failed'; }); look.retarget(); return window.chimed; }) === 0, 'a learner: no alarm chime when something newly fails');
  for (const deep of ['argus', 'hermes', 'throne', 'memory']) {
    const l = await page(b, 412, 900); await l.goto(BASE + deep); await l.waitForTimeout(400);
    await l.evaluate(() => { S.role = 'learner'; render(); });
    await l.waitForURL(u => new URL(u).pathname === new URL(BASE).pathname, {timeout: 5000}).catch(() => {});
    check(new URL(l.url()).pathname === new URL(BASE).pathname, `a learner who opens ${deep} lands on Today (${new URL(l.url()).pathname})`);
    await l.close();
  }
  const m = await page(b, 412, 900); await m.goto(BASE + 'mentor'); await m.waitForTimeout(400);
  await m.evaluate(() => { S.role = 'learner'; render(); }); await m.waitForTimeout(400);
  check(/\/mentor$/.test(m.url()), 'a learner on Mentor stays there'); await m.close();

  // wide screens: the same places as a strip, in the same order, no bottom bar
  const d = await page(b, 1440, 900); await d.goto(BASE); await d.waitForTimeout(800);
  const strip = await d.locator('#realms a.realm b').allTextContents();
  check(strip.slice(0, 6).join(' ') === 'Today Argus Mentor Zeus Mnemosyne Olympus' && await d.locator('#tabbar').isHidden(), `1440: the strip, in the same order (${strip.slice(0, 7).join(', ')}), and no bottom bar`);
  check(await noOverflow(d), '1440: no sideways scrolling');
  units(u => { Object.keys(u).forEach(k => delete u[k]); Object.assign(u, JSON.parse(saved)); });
});
