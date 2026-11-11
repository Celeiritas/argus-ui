// Watch that points at the trouble (docs/home.md "Trouble first", "The satellite eye"; docs/checks.md): the server's watch loop
// (one-second rounds) finds a container with a dead copy of its drive. Watch puts one block per broken thing first, in three plain
// lines, with one press-and-hold fix; every check shows while it works too; "What happened lately" lists the events. One of Argus's
// eyes travels to the first broken block and glares at it, his other eyes look there and not at the pointer, a polite sentence says
// it, and it comes home when all is well. Checked at 360x800, 412x915 and 1440x900, with reduced motion, and for contrast.
const {BASE, check, page, noOverflow, shot, units, run} = require('./lib');
const fs = require('fs'), path = require('path');
const T = path.dirname(process.env.FIXTURES), HOME = path.join(T, 'home'), FX = process.env.FIXTURES, POD = path.join(T, 'pod');
const CHECKS = path.join(HOME, '.config/argus-ui/checks.json'), UNITS = path.join(FX, 'units.json');
const mi = name => fs.copyFileSync(path.join(FX, 'watch', name + '.mountinfo'), path.join(POD, 'jellyfin.mountinfo'));
const pod = [process.env.PYTHON || 'python3', path.join(FX, 'fake_podman.py')];
// the page asks again until the trouble block for Jellyfin is (or is not) there
const until = async (p, sel, want) => { for (let i = 0; i < 30; i++) { await p.evaluate(() => refresh()); await p.waitForTimeout(400); if ((await p.locator(sel).count() > 0) === want) return true; } return false; };
const JB = '.tblock[data-trouble="check-jellyfin"]';
// boxes of the words and buttons in the eyed block, and the eye's box: none may overlap
const overlap = p => p.evaluate(() => {
  const b = document.querySelector('.tblock.eyed'), e = b && b.querySelector('.sat svg'); if (!e) return {none: true};
  const er = e.getBoundingClientRect(), br = b.getBoundingClientRect(), hits = [];
  const range = document.createRange();
  for (const el of b.querySelectorAll('h3, .tw, .tl, button')) {
    const rects = el.matches('button') ? [el.getBoundingClientRect()] : (range.selectNodeContents(el), [...range.getClientRects()]);
    for (const r of rects) if (r.width && r.left < er.right && r.right > er.left && r.top < er.bottom && r.bottom > er.top) hits.push(el.className || el.tagName);
  }
  return {hits, inside: er.left >= br.left && er.right <= br.right + 1 && er.top >= br.top, w: Math.round(er.width), h: Math.round(er.height), at: [Math.round(er.left - br.left), Math.round(er.top - br.top)]};
});
// WCAG contrast of each element's text against what is behind it (the nearest backgrounds, composited over the night colour)
const contrast = (p, sel) => p.evaluate(s => {
  const rgb = c => (c.match(/[\d.]+/g) || []).map(Number), lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
  return [...document.querySelectorAll(s)].filter(e => e.getClientRects().length).map(e => {
    const layers = []; for (let n = e; n; n = n.parentElement) { const c = rgb(getComputedStyle(n).backgroundColor); if (c.length && (c[3] ?? 1) > 0) layers.push(c); if ((c[3] ?? 1) >= 1 && c.length) break; }
    let bg = [28, 33, 39]; for (const c of layers.reverse()) { const a = c[3] ?? 1; bg = bg.map((v, i) => v * (1 - a) + c[i] * a); }
    const fg = rgb(getComputedStyle(e).color), a = lum(fg.slice(0, 3)), b = lum(bg), r = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    return {s: e.className || e.tagName, r: Math.round(r * 100) / 100};
  });
}, sel);
run(async b => {
  const saved = fs.readFileSync(UNITS);
  fs.mkdirSync(POD, {recursive: true}); mi('container-dead-shutdown'); fs.writeFileSync(path.join(POD, 'jellyfin.readable'), '/media/a.mp4\n');
  fs.mkdirSync(path.dirname(CHECKS), {recursive: true});
  fs.writeFileSync(CHECKS, JSON.stringify({checks: [
    {id: 'jellyfin', title: 'Jellyfin', job: 'mnemosyne-jellyfin', mount: '/mnt/media', container: {name: 'jellyfin', file: '/media/a.mp4', runtime: pod}, fix: {restart: ['jellyfin'], say: 'Jellyfin'}},
    {id: 'media-drive', title: 'The media drive', job: 'mnemosyne-media-drive', mount: '/mnt/media'},
    {id: 'hermes-media-drive', title: 'Media on its drive', job: 'hermes-media', mount: '/mnt/media'}]}));
  // Element.animate is watched, so the test sees the eye's one travel (its length) without racing it
  const spy = () => { const a = Element.prototype.animate; window.__trips = []; Element.prototype.animate = function (k, o) { if (this.closest?.('.sat')) window.__trips.push({ms: typeof o === 'number' ? o : o?.duration, it: o?.iterations || 1}); return a.call(this, k, o); }; };
  try {
    const p = await page(b, 1440, 900); await p.addInitScript(spy);
    await p.goto(BASE + 'argus?night=1'); await p.waitForTimeout(600);
    check(await until(p, JB, true), 'the watch finds Jellyfin broken and Watch shows a block for it');
    // --- slice 3: trouble first, three plain lines, the one fix, every check, what happened lately
    const firstTop = await p.evaluate(() => [document.querySelector('#main > *').className, document.querySelector('.tblock')?.dataset.trouble]);
    check(firstTop[0] === 'trouble' && firstTop[1] === 'check-jellyfin', `trouble comes first on Watch, Jellyfin first in it (${firstTop.join(', ')})`);
    const blk = (await p.locator(JB).textContent()).replace(/\s+/g, ' ');
    check(/Jellyfin runs, but cannot read its drive/.test(blk) && /Mnemosyne · Watch · since/.test(blk), 'line 1: what is wrong, whose, and since when: ' + blk.slice(0, 90));
    check(/Argus: Did not restart it and waits for your yes\./.test(blk) && /You: Hold the button to restart Jellyfin once\. Argus looks again for up to 90 seconds and tells you if it helped\./.test(blk), 'lines 2 and 3: what Argus did (his name said once), what you can do (one restart, then what follows)');
    check(!/Argus: Argus/.test(await p.locator('#main').textContent()), 'no "Argus: Argus" anywhere');
    check(await p.locator(`${JB} button.fixbtn.hold`).count() === 1 && /Restart Jellyfin/.test(await p.locator(`${JB} button.fixbtn`).textContent()), 'one press-and-hold button: Restart Jellyfin');
    check(await p.locator('.tblock[data-trouble^="task-"]').count() >= 1 && await p.locator('.tblock button').count() === 1, 'a failed task gets its block too, without a fix button');
    check(await p.locator('.crow.ok[data-check="media-drive"]', {hasText: 'Works'}).count() === 1, 'a check that works is shown too: "Works" and since when, as a compact row');
    check(/Works · since/.test(await p.locator('.card[data-job="hermes-media"] .worksline').textContent().catch(() => '')), "a check on a task's card: one line, Works · since …");
    check(await p.locator('.crow.bad[data-check="jellyfin"]').count() === 1 && await p.locator('.card.alert-only').count() === 0, 'the broken check without a card is a red row, not a second card');
    await p.locator('#lately .ev').first().waitFor({timeout: 15000}).catch(() => {});
    const ev = (await p.locator('#lately .ev').first().textContent()).replace(/\s+/g, ' ');
    check(/Jellyfin runs, but cannot read its drive/.test(ev) && /(just now|minutes? ago) · \w{3}, \w{3} \d+/.test(ev), 'What happened lately: the event as a sentence, with a relative and an exact time: ' + ev.slice(0, 120));
    check(await p.locator('#lately time[datetime]').count() >= 1, 'each time is a <time> with the exact moment');
    // --- slice 4: the satellite eye
    const trips = await p.evaluate(() => window.__trips);
    check(trips.length >= 1 && trips[0].ms >= 600 && trips[0].ms <= 900 && trips[0].it === 1, `the eye traveled once, ${trips[0]?.ms} ms, not looped`);
    // the pulse is a CSS animation on a newly arrived eye (a refresh in between draws it again without one): measure the rule itself
    const pulse = await p.evaluate(() => { const s = document.createElement('span'); s.className = 'sat glaring'; s.innerHTML = '<svg></svg>'; document.body.append(s);
      const c = getComputedStyle(s.firstChild), r = [c.animationName, parseFloat(c.animationDuration) * Number(c.animationIterationCount)]; s.remove(); return r; });
    check(pulse[0] === 'satglare' && pulse[1] > 0 && pulse[1] <= 5, `its glare pulses for ${pulse[1]} s, then holds still (at most 5)`);
    await p.evaluate(() => refresh()); await p.waitForTimeout(500);
    check(await p.evaluate(() => window.__trips.length) === trips.length && !await p.locator('.sat').evaluate(e => e.classList.contains('glaring')), 'a refresh with the same trouble: no new travel, no new pulse');
    check(await p.locator('.tblock.eyed').getAttribute('data-trouble') === 'check-jellyfin' && await p.locator('.sat').getAttribute('aria-hidden') === 'true', 'the eye sits at the first broken block, hidden from screen readers');
    check(/^\d more$/.test((await p.locator('.satn').textContent()).trim()), 'a small count says how many more: ' + await p.locator('.satn').textContent());
    check(await p.evaluate(() => document.getElementById('argus').classList.contains('sat-out')), "his red eye is out: its lid shows shut");
    const said = await p.locator('#satSay').textContent();
    check(/^Jellyfin is running but not working(, and \d more things? needs? a look|\. Now \d things need a look)\.$/.test(said) && await p.locator('#satSay').getAttribute('aria-live') === 'polite', 'one polite sentence says the same: ' + said);
    // his other eyes look at the block, not at the pointer: the pointer is at the top right, the block below him
    await p.mouse.move(1430, 4); await p.waitForTimeout(80); await p.mouse.move(1435, 6); await p.waitForTimeout(700);
    const look = await p.evaluate(() => { const ir = document.querySelector('#argus .eye.top .iris').getAttribute('transform').match(/-?[\d.]+/g).map(Number); return ir; });
    check(look[1] > 0, `while something is wrong his eyes look down at the block, not up at the pointer (iris ${look.join(', ')})`);
    for (const [w, h] of [[1440, 900], [412, 915], [360, 800]]) {
      const q = w === 1440 ? p : await page(b, w, h); if (q !== p) { await q.goto(BASE + 'argus?night=1'); await q.locator(JB).waitFor({timeout: 10000}).catch(() => {}); await q.waitForTimeout(900); }
      const o = await overlap(q);
      check(!o.none && o.hits.length === 0 && o.inside, `${w}x${h}: the eye (${o.w}x${o.h} at ${o.at}) sits in the block's corner and covers none of its words or its button ${JSON.stringify(o.hits)}`);
      if (w === 360) check(await noOverflow(q), '360: no sideways scrolling');
      const small = await q.evaluate(() => [...document.querySelectorAll('.fixbtn, #satEdge:not([hidden]), #lately a, .tblock a')].map(e => e.getBoundingClientRect()).filter(r => r.width && (r.width < 44 || r.height < 44)).length);
      check(small === 0, `${w}: every new target is at least 44 px`);
      if (w === 412) {
        await shot(q, 'W-watch-trouble-412-night');
        await q.evaluate(() => scrollTo(0, document.body.scrollHeight)); await q.waitForTimeout(500);
        const edge = q.locator('#satEdge');
        check(await edge.isVisible() && (await edge.boundingBox()).height >= 44 && (await edge.boundingBox()).width >= 44, 'scrolled away: an edge marker with an arrow, 44 px');
        await shot(q, 'W2-watch-edge-full-412-night');
        const name0 = await edge.getAttribute('aria-label'), w0 = (await edge.boundingBox()).width;
        await q.waitForTimeout(5400);
        const sm = await edge.boundingBox();
        check(w0 > 60 && await edge.evaluate(e => e.classList.contains('small')) && Math.round(sm.width) === 44 && Math.round(sm.height) === 44 && await edge.getAttribute('aria-label') === name0,
          `the marker is the pill "Look" (${Math.round(w0)} px) for 5 s, then an arrow-only round button of 44 px with the same name (${Math.round(sm.width)}x${Math.round(sm.height)})`);
        await shot(q, 'W2-watch-edge-small-412-night');
        await edge.click(); await q.waitForTimeout(900);
        const vis = await q.locator('.tblock.eyed').evaluate(e => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; });
        check(vis && await edge.isHidden(), 'a tap on it scrolls back to the broken block, and the marker goes');
        await q.evaluate(() => scrollTo(0, document.body.scrollHeight)); await q.waitForTimeout(300); await shot(q, 'W-watch-lately-412-night');
        await q.evaluate(() => scrollTo(0, 0));
      }
      if (w !== 1440) await q.close();
    }
    await shot(p, 'W-watch-trouble-1440-night');
    const cs = [...await contrast(p, '.trouble h2, .tblock h3, .tw, .tl, .tl b, .fixbtn .hold-label, .satn, .cw b, .cw span, .worksline, .worksline b, .et, .eb, .ew, .lately h2')];
    const low = cs.filter(c => c.r < 4.5);
    check(cs.length >= 10 && !low.length, `contrast of the new text is at least 4.5:1 (lowest ${Math.min(...cs.map(c => c.r))}) ${JSON.stringify(low)}`);
    for (const night of [0]) { const d = await page(b, 412, 915); await d.goto(BASE + `argus?night=${night}`); await d.locator(JB).waitFor({timeout: 10000}).catch(() => {}); await d.waitForTimeout(900); await shot(d, 'W-watch-trouble-412-day'); await d.close();
      const e = await page(b, 1440, 900); await e.goto(BASE + `argus?night=${night}`); await e.locator(JB).waitFor({timeout: 10000}).catch(() => {}); await e.waitForTimeout(900); await shot(e, 'W-watch-trouble-1440-day'); await e.close(); }
    // W2 point 1: one round where Argus cannot look inside the container (podman exits 125): the block, the alarm and the eye stay
    const JM = path.join(POD, 'jellyfin.mountinfo'), JA = JM + '.set-aside';
    const trips0 = await p.evaluate(() => window.__trips.length);
    fs.renameSync(JM, JA);
    let held = false;
    for (let i = 0; i < 30 && !held; i++) { await p.evaluate(() => refresh()); await p.waitForTimeout(400); held = await p.evaluate(() => !!(S.watch.find(w => w.id === 'jellyfin') || {}).unsure); }
    const u1 = await p.evaluate(() => [document.querySelectorAll('.tblock[data-trouble="check-jellyfin"]').length, document.getElementById('argus').classList.contains('glare'),
      document.getElementById('satSay').textContent, window.__trips.length, document.querySelectorAll('.tblock.eyed .sat').length, (document.querySelector('.tblock[data-trouble="check-jellyfin"] .unsure') || {}).textContent]);
    check(held && u1[0] === 1 && u1[1] && !/All is well/.test(u1[2]) && u1[3] === trips0 && u1[4] === 1,
      `an unknown round: the block stays, Argus still glares, nothing says all is well, the eye stays and does not travel again (${JSON.stringify(u1.slice(0, 5))})`);
    check(/^Argus has not been able to look again since \d{1,2}:\d\d [AP]M\.$/.test(u1[5] || ''), 'and the block says when Argus last could look: ' + u1[5]);
    await shot(p, 'W2-watch-unknown-round-1440-night');
    fs.renameSync(JA, JM);
    for (let i = 0; i < 30 && held; i++) { await p.evaluate(() => refresh()); await p.waitForTimeout(400); held = await p.evaluate(() => !!(S.watch.find(w => w.id === 'jellyfin') || {}).unsure); }
    check(!held && await p.evaluate(() => window.__trips.length) === trips0, 'Argus looks again: the sentence goes, still no new travel');
    // the page's own guard: nothing red left, but a row is unknown or stale: the page stays as it was
    await p.evaluate(() => { busy = true; S.jobs.forEach(j => { if (j.state === 'failed') j.state = 'ok'; j.works = j.works === false ? null : j.works; });
      S.watch.forEach(w => { if (w.works === false) { w.works = null; w.code = 'stale'; } }); S.alerts = []; render(); });
    const g = await p.evaluate(() => [document.querySelectorAll('.tblock').length, document.getElementById('argus').classList.contains('glare'), document.getElementById('argus').classList.contains('sat-out'), document.getElementById('satSay').textContent, window.__trips.length]);
    check(g[0] === 0 && g[1] && g[2] && !/All is well/.test(g[3]) && g[4] === trips0, `no trouble left but a row is stale: no "All is well", the alarm and the eye stay out, no travel (${JSON.stringify(g)})`);
    await p.evaluate(() => { busy = false; }); await p.evaluate(() => refresh()); await p.waitForTimeout(800);
    // W2 point 3: a second and a third thing break while one is shown: a new pulse each time, and the count said again
    const pulsing = () => p.evaluate(() => { const s = document.querySelector('.sat'); return s && s.classList.contains('glaring') && s.querySelector('svg').getAnimations().length > 0; });
    const extra = (id, title) => ({id, title, job: '', unit: '', mount: '', works: false, code: 'no-answer', reason: 'does not answer at its web address', since: new Date().toISOString(),
      fix: false, fix_say: '', drive: false, again: false, unsure: '', title_line: `${title} runs, but does not answer at its web address`, detail: '', note: '', fixing: false, queued: false});
    const told = [];
    await p.evaluate(() => { busy = true; render(); });
    const n0 = await p.evaluate(() => troubleItems().length);
    for (const [id, title] of [['extra-one', 'Extra One'], ['extra-two', 'Extra Two']]) {
      await p.evaluate(r => { S.watch.push(r); render(); }, extra(id, title)); await p.waitForTimeout(150);
      told.push([await p.locator("#satSay").textContent(), await pulsing()]);
    }
    check(told[0][0] === `Extra One is running but not working. Now ${n0 + 1} things need a look.` && told[0][1], 'a second (or later) thing breaks: one new pulse, and it is said with the count: ' + told[0][0]);
    check(told[1][0] === `Extra Two is running but not working. Now ${n0 + 2} things need a look.` && told[1][1], 'and the next one too: ' + told[1][0]);
    await p.evaluate(() => { S.watch = S.watch.filter(w => w.id !== 'extra-one'); render(); }); await p.waitForTimeout(150);
    const left = await p.locator('#satSay').textContent();
    check(left === `Jellyfin is running but not working, and ${n0} more thing${n0 === 1 ? ' needs' : 's need'} a look.` && !await pulsing(), 'one leaves, others remain: the new count, no pulse: ' + left);
    await p.evaluate(() => { S.watch = S.watch.filter(w => !w.id.startsWith('extra-')); busy = false; }); await p.evaluate(() => refresh()); await p.waitForTimeout(800);
    // the hold button calls the route once (answered here, so nothing really restarts; tests/watch_routes_test.py runs the real one)
    let calls = 0; await p.route('**/api/watch/fix', r => { calls++; r.fulfill({json: {ok: true, msg: 'Restarting Jellyfin. Argus looks again for up to 90 seconds and tells you how it went.'}}); });
    const fb = p.locator(`${JB} button.fixbtn`); const bb = await fb.boundingBox();
    await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2); await p.mouse.down(); await p.waitForTimeout(3400); await p.mouse.up(); await p.waitForTimeout(800);
    check(calls === 1, `holding Restart Jellyfin calls api/watch/fix once (${calls})`);
    check(/Restarting Jellyfin/.test(await p.locator('#toastText').textContent()), 'and the toast says what the server said');
    await p.unroute('**/api/watch/fix');
    // Today with trouble: the same three lines and the same fix, one row per broken thing
    const td = await page(b, 412, 915); await td.goto(BASE + '?night=1'); await td.locator('.need[data-key="check-jellyfin"]').waitFor({timeout: 10000}).catch(() => {});
    const tr = (await td.locator('.need[data-key="check-jellyfin"]').textContent()).replace(/\s+/g, ' ');
    check(/Jellyfin runs, but cannot read its drive/.test(tr) && /You: Hold the button/.test(tr) && await td.locator('.need[data-key="check-jellyfin"] button.fixbtn.hold').count() === 1, 'Today: the same block, with its fix button');
    check(await td.locator('.sat').count() === 0, 'Today has no satellite eye (it is Watch\'s)');
    await td.waitForTimeout(400); await shot(td, 'W-today-trouble-412-night'); await td.close();
    // a learner never sees any of it
    const ln = await page(b, 412, 915); await ln.goto(BASE + '?night=1'); await ln.waitForTimeout(800);
    await ln.evaluate(() => { S.role = 'learner'; render(); }); await ln.waitForTimeout(300);
    check(await ln.locator('.sat, .fixbtn, .need[data-key^="check-"], #satEdge:not([hidden])').count() === 0 && (await ln.locator('#satSay').textContent()) === '', 'a learner: no eye, no fix, no rows about the owner\'s programs, no sentence');
    await ln.close();
    // reduced motion: no travel and no pulse, the eye is simply at the block
    const rm = await b.newPage({viewport: {width: 412, height: 915}, reducedMotion: 'reduce'}); await rm.addInitScript(spy);
    await rm.goto(BASE + 'argus?night=1'); await rm.locator('.tblock.eyed .sat').waitFor({timeout: 10000}).catch(() => {}); await rm.waitForTimeout(500);
    const rmt = await rm.evaluate(() => [window.__trips.length, getComputedStyle(document.querySelector('.sat svg')).animationName, document.querySelectorAll('.tblock.eyed .sat').length]);
    check(rmt[0] === 0 && rmt[1] === 'none' && rmt[2] === 1, `reduced motion: the eye is there with no travel and no pulse (${rmt.join(', ')})`);
    await shot(rm, 'W-watch-reducedmotion-412'); await rm.close();
    // W2 point 4: the drive is gone: its block comes first (the eye goes to the cause), Jellyfin is one line under it, nobody waits for a yes
    const HG = path.join(FX, 'watch', 'host-good.mountinfo'), good = fs.readFileSync(HG);
    fs.copyFileSync(path.join(FX, 'watch', 'host-missing.mountinfo'), HG);
    try {
      check(await until(p, '.tblock[data-trouble="check-media-drive"]', true), 'the drive is gone: it gets a block');
      await p.waitForTimeout(300);
      const d = await p.evaluate(() => [document.querySelector('.tblock.eyed')?.dataset.trouble, [...document.querySelectorAll('.tblock')].map(b => b.dataset.trouble), document.querySelector('.trouble').textContent.replace(/\s+/g, ' ')]);
      check(/^check-(media-drive|hermes-media-drive)$/.test(d[0]) && !d[1].includes('check-jellyfin') && /Also waiting for this drive: Jellyfin/.test(d[2]), `the drive's block is first and has the eye; Jellyfin is folded under it (${d[1].join(', ')})`);
      check(!/waits for your yes/i.test(d[2]) && !/Restart Jellyfin/.test(d[2]) && /a restart would not help until it is back|Cannot bring a drive back/.test(d[2]), 'no "waits for your yes" and no restart button while the drive is gone');
      await shot(p, 'W2-watch-drive-gone-1440-night');
    } finally { fs.writeFileSync(HG, good); }
    check(await until(p, '.tblock[data-trouble="check-media-drive"]', false), 'the drive is back: its block goes');
    // the trouble ends: the eye goes home and the sentence says so
    mi('container-good'); units(u => Object.values(u).forEach(v => { if (v.Result !== 'success') v.Result = 'success'; if (v.ActiveState === 'failed') v.ActiveState = 'inactive'; }));
    check(await until(p, '.tblock', false), 'all well: the trouble blocks go');
    await p.waitForTimeout(900);
    check(await p.locator('.sat').count() === 0 && !await p.evaluate(() => document.getElementById('argus').classList.contains('sat-out')), 'the eye has come home');
    check(/All is well again/.test(await p.locator('#satSay').textContent()), 'and the sentence says so: ' + await p.locator('#satSay').textContent());
    check(/Works again/.test(await p.locator('.crow[data-check="jellyfin"]').textContent()), 'the row says "Works again"');
    await shot(p, 'W-watch-allwell-1440-night');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  } finally { fs.rmSync(CHECKS, {force: true}); fs.writeFileSync(UNITS, saved); if (process.env.ARGUS_EVENTS) fs.writeFileSync(process.env.ARGUS_EVENTS, ''); }   // works.test.js counts the events from an empty file
});
