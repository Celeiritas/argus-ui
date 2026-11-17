// What keeps quiet (4.45.0, server/quiet.py, docs/home.md "Quiet"): Mentor never needs the owner (no row, no button, no count,
// its tile keeps its line), and a failed task he marks "Known, low priority" leaves Today until it works again or fails
// another way; on Argus it stays, in grey, with Unmark. The server side (no buzz, no summary line, a learner's 403, the
// fingerprint) is in tests/quiet_test.py and tests/gate_test.py.
const {BASE, check, page, units, run} = require('./lib');
const JOB = 'hermes-rename';
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); }, null, {timeout: 8000}).catch(() => {});
const known = (p, on) => p.request.post(BASE + 'api/known', {data: {job: JOB, on}});
const jobNow = async p => (await (await p.request.get(BASE + 'api/state')).json()).jobs.find(j => j.job === JOB);
// a route handler whose page closed while its request was in flight (the next check already started) ends quietly;
// anything else still throws (CI 2f48fef: TargetClosedError from route.fetch failed the whole run)
const settle = fn => async r => { try { await fn(r); } catch (e) { if (!/closed|disposed/i.test(String(e && e.message))) throw e; } };
const fail = (u, status = '1') => Object.assign(u[JOB], {Result: 'exit-code', ActiveState: 'failed', ExecMainStatus: status});
run(async b => {
  let saved; units(u => { saved = JSON.stringify(u); });           // given back at the end, for the checks after this one
  // one failed task, every other one well
  units(u => { Object.entries(u).forEach(([k, v]) => { if (k !== JOB && v.Result && v.Result !== 'success') { v.Result = 'success'; if (v.ActiveState === 'failed') v.ActiveState = 'inactive'; } }); fail(u); });
  const p = await page(b, 412, 915);
  try {                                                                // a check that throws must still give the units and the mark back (4.52.0: one throw here failed watch, salience and works after it)
  await known(p, false);                                               // no mark left from an earlier run
  // the realm otherwise quiet (alerts and checks from earlier tests left out, every other section's line kept but needing
  // nothing), and Mentor with six cards due that says it needs him: the page itself must keep Mentor quiet, whatever it says
  await p.route('**/api/state*', settle(async r => { const res = await r.fetch(); const j = await res.json(); j.alerts = []; j.watch = []; await r.fulfill({json: j}); }));
  await p.route('**/api/*/status*', settle(async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); }));
  await p.route('**/api/mentor/status*', r => r.fulfill({json: {line: '6 cards due', needs: true, action: 'Study 10 minutes', count: 6}}));
  await p.goto(BASE); await settled(p); await p.waitForTimeout(400);
  const name = await p.evaluate(j => S.jobs.find(x => x.job === j).name, JOB);
  const row = () => p.locator('#main .need:not(.leaving)', {hasText: name});    // a row that leaves fades out first
  const qline = id => p.locator(`#main .news a.qline[data-id="${id}"]`);   // a section's line on Today (4.54.0: no tiles)

  // ---- 3. Mentor quiet ----
  check(await p.locator('#main .need', {hasText: 'Mentor'}).count() === 0 && await p.locator('#main .need a.go', {hasText: 'Study'}).count() === 0,
    'Mentor with 6 cards due is not in "things need you": no row, no Study button');
  check(await p.locator('#needs-h').textContent() === '1 thing needs you', `the count is the failed task alone (${await p.locator('#needs-h').textContent()})`);
  check(await p.locator('#tabbar .tab[data-id=mentor] .tabcount').count() === 0 && await p.locator('#tabbar .tab[data-id=mentor] .sr').count() === 0, 'no count or dot on Mentor in the bar');
  // a quiet section keeps its line under Sections (docs/home.md "One way to each place")
  const ql = qline('mentor');
  check(await ql.count() === 1 && /6\scards due/.test(await ql.textContent()), `Mentor's line still says it on a phone: "${await ql.textContent().catch(() => '')}"`);
  const real = await (await p.request.get(BASE + 'api/mentor/status')).json();
  check(real.needs === false && real.action === '' && !('count' in real), `the server says the same to the owner: never needs him, no button, no count (${JSON.stringify(real)})`);
  await p.setViewportSize({width: 1440, height: 900}); await p.evaluate(() => render()); await p.waitForTimeout(300);
  check(await p.locator('#realms a.realm[data-id=mentor] .dot').count() === 0, 'no dot on Mentor in the wide strip');
  check(await qline('mentor').count() === 1 && /6\u00a0cards due/.test(await qline('mentor').locator('.qt').textContent()), `on a computer Mentor's line still says it: "${await qline('mentor').locator('.qt').textContent().catch(() => '')}"`);
  await p.setViewportSize({width: 412, height: 915}); await p.evaluate(() => render()); await p.waitForTimeout(300);

  // ---- 4. Known, low priority: from Today's row ----
  const mark = row().locator('button.knownbtn');
  check(await mark.count() === 1 && await mark.textContent() === 'Mark as known' && await mark.getAttribute('data-on') === '1', 'the failed task\'s row on Today has "Mark as known"');
  const hit = await mark.boundingBox();
  check(hit && hit.height >= 44 && hit.width >= 44, `it is at least 44 px (${hit && Math.round(hit.width)} x ${hit && Math.round(hit.height)})`);
  await mark.click();
  await p.waitForFunction(() => document.getElementById('needs-h')?.textContent === 'Nothing needs you', null, {timeout: 6000}).catch(() => {});
  check(await row().count() === 0 && await p.locator('#needs-h').textContent() === 'Nothing needs you', `marked known, it leaves Today: "${await p.locator('#needs-h').textContent()}"`);
  check(!!(await jobNow(p)).known, 'the server keeps the mark');
  check(await p.locator('#toastAct').isVisible() && await p.locator('#toastAct').textContent() === 'Undo' && await p.evaluate(() => document.activeElement?.id === 'toastAct'), 'a toast offers Undo, and focus is on it');
  await p.locator('#toastAct').click();
  await p.waitForFunction(() => document.getElementById('needs-h')?.textContent === '1 thing needs you', null, {timeout: 6000}).catch(() => {});
  check(await row().count() === 1 && !(await jobNow(p)).known && await p.locator('#needs-h').textContent() === '1 thing needs you', 'Undo: the row comes back, the mark is gone');

  // ---- from its card on Argus: grey, "Known, low priority · marked today", Unmark ----
  // on Hermes' own page: on a phone the All view folds a group whose only failure is known (4.52.0, docs/home.md "On a phone"),
  // so there the card stays on its group's page (before, this was the All view at 412 px); the fold is checked below
  const w = await page(b, 412, 915); await w.route('**/api/state*', settle(async r => { const res = await r.fetch(); const j = await res.json(); j.alerts = []; j.watch = []; await r.fulfill({json: j}); }));
  await w.goto(BASE + 'hermes'); await w.waitForTimeout(900);
  const card = w.locator(`.card[data-job="${JOB}"]`);
  await card.locator('button.knownbtn[data-on="1"]').click();
  await card.locator('.knownline').waitFor({timeout: 6000}).catch(() => {});
  // marked, it sorts below the others: the view follows it, the reader keeps his place
  await w.waitForFunction(() => { const y = scrollY, ok = window.__lastY === y; window.__lastY = y; return ok; }, null, {polling: 250, timeout: 4000}).catch(() => {});   // the scroll has settled
  const seen = await card.evaluate(e => { const r = e.getBoundingClientRect(), bar = document.getElementById('tabbar'), b = bar && bar.getClientRects().length ? bar.getBoundingClientRect().top : innerHeight;   /* fixed: no offsetParent */
    return {top: Math.round(r.top), bottom: Math.round(r.bottom), floor: Math.round(b)}; });
  check(seen.top >= 0 && seen.bottom <= seen.floor, `the marked card is in view after it moves, clear of the bottom bar (${JSON.stringify(seen)})`);
  check(await card.evaluate(e => e.classList.contains('known')) && /^Known, low priority · marked today, /.test(await card.locator('.knownline').textContent()),
    `on Argus the card is marked: "${await card.locator('.knownline').textContent().catch(() => '')}"`);
  const pill = await card.locator('.pill').evaluate(e => { const c = v => { const s = document.createElement('span'); s.style.color = `var(${v})`; document.body.append(s); const x = getComputedStyle(s).color; s.remove(); return x; };
    return {cls: e.className, color: getComputedStyle(e).color, frost: c('--frost'), bad: c('--bad')}; });
  check(/known/.test(pill.cls) && pill.color === pill.frost && pill.color !== pill.bad, `its state pill is grey (frost), not red (${JSON.stringify(pill)})`);
  const grey = await card.evaluate(e => { const c = v => { const s = document.createElement('span'); s.style.color = `var(${v})`; document.body.append(s); const x = getComputedStyle(s).color; s.remove(); return x; };
    return {name: getComputedStyle(e.querySelector('.job')).color, value: getComputedStyle(e.querySelector('dd')).color, powder: c('--powder')}; });
  check(grey.name === grey.powder && grey.value === grey.powder, `the whole card is quiet: its name and values in the grey too (${JSON.stringify(grey)})`);
  check(await card.locator('button.knownbtn').textContent() === 'Unmark', 'the card offers Unmark');
  // the phone's All view: Hermes, its only failure known, is one line that counts it and opens Hermes' page
  const a = await page(b, 412, 915); await a.route('**/api/state*', settle(async r => { const res = await r.fetch(); const j = await res.json(); j.alerts = []; j.watch = []; await r.fulfill({json: j}); }));
  await a.goto(BASE + 'argus'); await a.locator('.persona').first().waitFor({timeout: 5000}).catch(() => {});
  const hf = a.locator('.persona.folded', {has: a.locator('#h-hermes')}), hs = await hf.locator('.dom').textContent({timeout: 3000}).catch(() => '');
  check(await hf.count() === 1 && /^All well · .*\b1 known$/.test(hs) && await a.locator(`.card[data-job="${JOB}"]`).count() === 0 && /\/hermes$/.test(await hf.locator('a.ph').getAttribute('href').catch(() => '')),
    `phone, All view: Hermes with only a known failure is one line that counts it and opens its page ("${hs}")`);
  await a.close();
  await card.locator('button.knownbtn').click();
  await card.locator('.knownline').waitFor({state: 'detached', timeout: 6000}).catch(() => {});
  check(!await card.evaluate(e => e.classList.contains('known')) && await card.locator('button.knownbtn').textContent() === 'Mark as known' && !(await jobNow(w)).known, 'Unmark: the card counts again, with "Mark as known"');
  await w.close();

  // ---- it comes back when it works again and then fails, or when it fails another way ----
  check((await known(p, true)).status() === 200 && !!(await jobNow(p)).known, 'marked again');
  // Argus's live line (its More row, core.js placeLine; it had a tile on Today until 4.54.0) counts it as known
  await p.setViewportSize({width: 1024, height: 768}); await p.evaluate(() => refresh());
  await p.waitForFunction(() => /known/.test(placeLine({id: 'argus'})), null, {timeout: 6000}).catch(() => {});
  const al = await p.evaluate(() => placeLine({id: 'argus'}));
  check(/^All \d+ tasks well · 1 known$/.test(al), `Argus's line: "${al}"`);
  await p.setViewportSize({width: 412, height: 915}); await p.evaluate(() => render()); await p.waitForTimeout(300);
  units(u => Object.assign(u[JOB], {Result: 'success', ActiveState: 'inactive', ExecMainStatus: '0'}));
  check(!(await jobNow(p)).known, 'it ran well: the mark is gone');
  units(u => fail(u));
  await p.evaluate(() => refresh()); await row().waitFor({timeout: 6000}).catch(() => {});
  check(!(await jobNow(p)).known && await row().count() === 1, 'it fails again: back on Today');
  check((await known(p, true)).status() === 200, 'marked once more');
  units(u => fail(u, '2'));
  await p.evaluate(() => refresh()); await row().waitFor({timeout: 6000}).catch(() => {});
  check(!(await jobNow(p)).known && await row().count() === 1, 'it fails another way (exit status 2, not 1): back on Today');

  // ---- a learner: no "Mark as known" (the server refuses her too: tests/gate_test.py) ----
  await p.evaluate(() => { S.role = 'learner'; render(); }); await p.waitForTimeout(400);
  check(await p.locator('button.knownbtn').count() === 0, 'a learner sees no "Mark as known"');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  } finally {
    await known(p, false).catch(() => {});
    units(u => { Object.keys(u).forEach(k => delete u[k]); Object.assign(u, JSON.parse(saved)); });
  }
});
