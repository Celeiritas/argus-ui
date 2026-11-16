// Edit Today (4.50.0, web/js/today-edit.js, server/today.py, docs/home.md "Edit Today"): the owner shows, hides, orders and
// renames Today's tiles and Open's links, makes groups in Open, and switches each section's reminders off or on. A mode with a
// clear Done and Cancel; Move up / down buttons are the keyboard path; a god's tile keeps its god's name; Mentor never reminds,
// Zeus always does (4.50.1: on and locked, even when today.json says otherwise); Mnemosyne's switch says what off drops.
// Saved on the server (one Today on every device), so the checks read it back after a reload. A learner has no Edit button
// (the server's 403 is in tests/today_edit_test.py and tests/gate_test.py). Every check here leaves today.json at the default.
// Pictures (numbered, at 412 and 1920 px): SHOTS, or EDIT_SHOTS when set (a folder of their own).
const {BASE, check, page, noOverflow, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CFG = path.join(HOME, '.config/argus-ui');
const MD = path.join(CFG, 'media.json'), LK = path.join(CFG, 'links.json'), TD = path.join(CFG, 'today.json');
const LINKS = [{name: 'Notes', what: 'Pages', href: '/notes-test/', group: 'Tools'}, {name: 'Sound Lab', what: 'Studio', href: '/studio-test/', group: 'Studio'},
  {name: 'Files', what: 'Shared files', href: '/files-test/', group: 'Tools'}];
const NAME = '<b>Lab</b> & co';                      // typed by the owner: drawn as words, never as HTML
const settle = fn => async r => { try { await fn(r); } catch (e) { if (!/closed|disposed/i.test(String(e && e.message))) throw e; } };
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); }, null, {timeout: 8000}).catch(() => {});
const OUT = process.env.EDIT_SHOTS || process.env.SHOTS;
const shot = (p, name) => OUT && p.screenshot({path: path.join(OUT, name + '.png'), fullPage: false});
const save = (p, body) => p.request.post(BASE + 'api/today', {data: body});
async function today(b, w, h) {
  const p = await page(b, w, h);
  // the realm quiet: every section's own line, needing nothing; no alerts, no failed checks (Today as on a calm morning)
  await p.route('**/api/*/status*', settle(async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); }));
  await p.route('**/api/state*', settle(async r => { const res = await r.fetch(), j = await res.json();
    (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(w => { if (w.works === false) w.works = true; });
    j.alerts = []; await r.fulfill({response: res, json: j}); }));
  await p.goto(BASE); await p.waitForLoadState('load');
  if (p.errors.length) throw new Error('the page failed to load: ' + p.errors.join(' | '));
  await p.evaluate(() => refresh()); await settled(p);
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
  return p;
}
const tiles = p => p.locator('#main .placelist .place').evaluateAll(as => as.map(a => a.dataset.id));
const row = (p, id) => p.locator(`#main .edit .edrow[data-id="${id}"]`);
const lrow = (p, href) => p.locator(`#main .edit .edrow[data-key="link:${href}"]`);
const small = p => p.locator('#main .edit').evaluate(ed => [...ed.querySelectorAll('button, input:not([type=checkbox]), label.check, label.edswitch')]
  .filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 20) || e.getAttribute('aria-label') || e.className, Math.round(r.width), Math.round(r.height)]; })
  .filter(([, w, h]) => w < 44 || h < 44));

// the whole of it at one width: Today, Edit, a rename, a group, the switches, Done
async function flow(b, w, h, n) {
  const t = await today(b, w, h), tag = `${w}`;
  const before = await tiles(t);
  check(before.includes('demo-server') && before.includes('spartamelee') && before.includes('argus'), `${tag}: the fixture's tiles (${before.join(', ')})`);
  check(await t.locator('#editToday').count() === 1 && (await t.locator('#editToday').boundingBox()).height >= 44, `${tag}: the owner has Edit Today in the Sections heading, 44 px tall`);
  if (w === 412) {
    const fit = await t.evaluate(() => { scrollTo(0, 0); return [document.querySelector('.home .places').getBoundingClientRect().bottom, document.querySelector('.tabbar').getBoundingClientRect().top]; });
    check(fit[0] <= fit[1], `412 x 915: Today with its Edit button still ends above the bottom bar (Sections end ${Math.round(fit[0])}, bar ${Math.round(fit[1])})`);
    await t.evaluate(() => { S.role = 'learner'; render(); });
    check(await t.locator('#editToday').count() === 0, 'a learner has no Edit Today');
    await t.evaluate(() => { S.role = 'owner'; render(); }); await t.waitForTimeout(200);
  }
  await shot(t, `${n}01-today-${tag}`);

  // ---- Edit mode ----
  await t.locator('#editToday').click();
  await t.locator('#main .home.edit').waitFor();
  check(await t.evaluate(() => document.activeElement.id) === 'edit-h', `${tag}: Edit opens with the keyboard on its heading`);
  check(await noOverflow(t), `${tag}: Edit has no sideways scroll`);
  const tiny = await small(t);
  check(!tiny.length, `${tag}: every button, field and switch in Edit is at least 44 by 44 px (${JSON.stringify(tiny.slice(0, 6))})`);
  check(await row(t, 'argus').locator('input[data-f=name]').count() === 0 && /A god's name/.test(await row(t, 'argus').textContent()), `${tag}: a god's tile (Argus) has no name field`);
  check(await t.locator('#main .edit [data-q=mentor]').isDisabled() && !(await t.locator('#main .edit [data-q=mentor]').isChecked()), `${tag}: Mentor's reminders are off and locked`);
  check(await t.locator('#main .edit [data-q=argus]').count() === 0, `${tag}: Argus has no reminders switch (its failures always count)`);
  // Zeus asks for his yes: on and locked, and a screen reader hears why (the owner, 2026-11-16: "Lock Zeus on")
  const zeus = t.locator('#main .edit [data-q=throne]');
  check(await zeus.isChecked() && await zeus.isDisabled() && /^Always reminds you$/.test(await zeus.locator('xpath=..').locator('.edstate').textContent()),
    `${tag}: Zeus's reminders are on and locked, with "Always reminds you"`);
  const zname = await t.evaluate(() => { const i = document.querySelector('#main .edit [data-q=throne]'); return [i.getAttribute('role'), i.labels[0].textContent.replace(/\s+/g, ' ').trim()]; });
  check(zname[0] === 'switch' && /Zeus/.test(zname[1]) && /Always reminds you/.test(zname[1]), `${tag}: Zeus's locked switch keeps its name and state in words (${zname.join(' / ')})`);
  check(await t.evaluate(() => { const i = document.querySelector('#main .edit [data-q=throne]'); i.click(); return i.checked; }), `${tag}: a click on Zeus's locked switch leaves it on`);
  // Mnemosyne: one plain line under the switch, read with it (aria-describedby)
  const mem = t.locator('#main .edit [data-q=memory]'), note = await mem.getAttribute('aria-describedby');
  check(!!note && /backup line out of the daily summary/.test(await t.locator('#' + note).textContent()) && await t.locator('#' + note).isVisible(),
    `${tag}: Mnemosyne's switch says off also leaves the backup line out of the daily summary`);
  const znote = await zeus.getAttribute('aria-describedby');
  check(!!znote && /asks for your yes/.test(await t.locator('#' + znote).textContent()) && await t.locator('#' + znote).isVisible(),
    `${tag}: Zeus's locked switch says why it stays on, read with it`);
  check(await t.locator('#main .edit .ednote').count() === 2, `${tag}: only Mnemosyne and Zeus have a line`);
  await t.evaluate(() => scrollTo(0, 0)); await shot(t, `${n}02-edit-${tag}`);

  // rename a tile (with HTML in it), then move it up by keyboard: the keyboard stays on the button
  await row(t, 'demo-server').locator('input[data-f=name]').fill(NAME);
  await row(t, 'demo-server').scrollIntoViewIfNeeded(); await shot(t, `${n}03-rename-${tag}`);
  const i0 = +(await row(t, 'demo-server').getAttribute('data-i'));
  await row(t, 'demo-server').locator('[data-mv="-1"]').focus(); await t.keyboard.press('Enter');
  const after = await t.evaluate(() => [document.activeElement.closest('.edrow')?.dataset.id, +document.activeElement.closest('.edrow')?.dataset.i, document.activeElement.dataset.mv]);
  check(after[0] === 'demo-server' && after[1] === i0 - 1 && after[2] === '-1', `${tag}: Move up by keyboard moves the tile one up and keeps the keyboard on it (${JSON.stringify(after)}, was ${i0})`);
  check(await row(t, 'demo-server').locator('input[data-f=name]').inputValue() === NAME, `${tag}: a typed name survives a move`);
  // hide a tile by keyboard (Space on Show)
  await row(t, 'spartamelee').locator('input[data-f=shown]').focus(); await t.keyboard.press('Space');
  check(await row(t, 'spartamelee').evaluate(r => r.classList.contains('off')), `${tag}: Space on Show hides a tile (greyed, still listed)`);

  // ---- Open: a new group, a group moved, a link renamed and one hidden ----
  const g = lrow(t, '/files-test/').locator('input[data-f=group]');
  await g.fill('Daily'); await g.press('Enter');
  check(await t.locator('#main .edit .edgname[data-g="Daily"]').count() === 1, `${tag}: typing a new group name on a link makes the group`);
  check(await t.evaluate(() => document.activeElement.dataset.f) === 'group', `${tag}: Enter keeps the keyboard on the link's group field after it moves`);
  await t.locator('#main .edit .edghead [data-g="Daily"][data-mv="-1"]').click();
  const gs = await t.locator('#main .edit .edgname').evaluateAll(es => es.map(e => e.value));
  check(gs[0] === 'Daily', `${tag}: Move up moves the whole group (${gs.join(', ')})`);
  await lrow(t, '/notes-test/').locator('input[data-f=name]').fill('Shared');
  await lrow(t, '/studio-test/').locator('input[data-f=shown]').uncheck();
  await t.locator('#ed-open').scrollIntoViewIfNeeded(); await t.waitForTimeout(100); await shot(t, `${n}04-open-group-${tag}`);
  check(await noOverflow(t), `${tag}: Open's edit rows have no sideways scroll`);

  // ---- Reminders ----
  const sw = t.locator('#main .edit [data-q="demo-server"]');
  check(await sw.isChecked(), `${tag}: a section reminds him by default`);
  await sw.click();
  check(!(await sw.isChecked()) && /never asks/.test(await sw.locator('xpath=..').textContent()), `${tag}: switching it off says so`);
  await t.locator('#ed-quiet').scrollIntoViewIfNeeded(); await t.waitForTimeout(100); await shot(t, `${n}05-reminders-${tag}`);

  // ---- Done ----
  await t.locator('#main .edit .edend [data-ed=done]').click();
  await t.locator('#editToday').waitFor(); await settled(t); await t.waitForTimeout(300);
  check(await t.evaluate(() => document.activeElement.id) === 'editToday', `${tag}: after Done the keyboard is back on Edit Today`);
  const now = await tiles(t);
  check(!now.includes('spartamelee') && now.indexOf('demo-server') >= 0, `${tag}: the hidden tile is gone from Today (${now.join(', ')})`);
  const want = before.filter(x => x !== 'spartamelee'), at = before.indexOf('demo-server'), prev = before[at - 1];
  check(prev === 'spartamelee' ? now.indexOf('demo-server') === want.indexOf('demo-server') : now.indexOf('demo-server') === now.indexOf(prev) - 1, `${tag}: the moved tile stands one higher`);
  const tile = t.locator('#main .place[data-id="demo-server"] .pw b');
  check(await tile.textContent() === NAME && await tile.locator('b').count() === 0, `${tag}: the new name shows as typed, as words (${await tile.innerHTML()})`);
  check(await t.evaluate(nm => sections().find(e => e.id === 'demo-server').word === nm, NAME), `${tag}: the bar, the strip and More use the same name (sections())`);
  const open = await t.locator('#main .open').evaluate(o => [[...o.querySelectorAll('.opengroup')].map(h => h.textContent), [...o.querySelectorAll('.openlink b')].map(b => b.textContent)]);
  check(open[0][0] === 'Daily' && open[0].includes('Tools') && !open[0].includes('Studio'), `${tag}: Open shows the new group first, and no empty group (${open[0].join(', ')})`);
  check(open[1].includes('Shared') && !open[1].includes('Sound Lab') && !open[1].includes('Notes') && open[1].includes('Files'), `${tag}: Open shows the renamed link and not the hidden one (${open[1].join(', ')})`);
  check(await t.evaluate(() => S.quiet.includes('demo-server') && S.quiet.includes('mentor')), `${tag}: the switched-off section is quiet now, Mentor still is`);
  check(await noOverflow(t), `${tag}: Today after Done has no sideways scroll`);
  await t.evaluate(() => scrollTo(0, 0)); await shot(t, `${n}06-done-${tag}`);
  const file = JSON.parse(fs.readFileSync(TD, 'utf8'));
  check(file.tiles.names['demo-server'] === NAME && file.tiles.hidden.includes('spartamelee') && file.open.groups['link:/files-test/'] === 'Daily' && file.quiet.includes('demo-server'),
    `${tag}: today.json holds what he changed (${JSON.stringify(file).slice(0, 200)})`);

  // kept: another page load (another device) shows the same Today
  await t.reload(); await t.evaluate(() => refresh()); await settled(t); await t.waitForTimeout(300);
  check(await t.locator('#main .place[data-id="demo-server"] .pw b').textContent() === NAME && !(await tiles(t)).includes('spartamelee'), `${tag}: a reload shows his Today`);

  // Cancel keeps Today as it was
  await t.locator('#editToday').click(); await t.locator('#main .home.edit').waitFor();
  await row(t, 'demo-server').locator('input[data-f=name]').fill('Something else');
  await t.locator('#main .edit .edtop [data-ed=cancel]').click(); await t.locator('#editToday').waitFor();
  check(await t.locator('#main .place[data-id="demo-server"] .pw b').textContent() === NAME, `${tag}: Cancel leaves Today as it was`);

  // Reset to default, then Done: the default again, and the file says so
  await t.locator('#editToday').click(); await t.locator('#main .home.edit').waitFor();
  await t.locator('#main .edit [data-ed=reset]').click();
  check(await row(t, 'spartamelee').evaluate(r => !r.classList.contains('off')) && await t.locator('#main .edit [data-q="demo-server"]').isChecked(), `${tag}: Reset to default fills Edit with the default`);
  await t.locator('#main .edit .edtop [data-ed=done]').click(); await t.locator('#editToday').waitFor(); await settled(t); await t.waitForTimeout(300);
  const back = await tiles(t);
  check(JSON.stringify(back) === JSON.stringify(before), `${tag}: after Reset and Done, Today is the default again (${back.join(', ')}; ${await t.locator('#main .needs').textContent().then(x => x.replace(/\s+/g, ' ').slice(0, 200))})`);
  check(await t.evaluate(() => !Object.keys(S.today || {}).length && !S.quiet.includes('demo-server')), `${tag}: and nothing of his is left in the state`);
  check(!t.errors.length, `${tag}: no page errors (${t.errors.join(' | ')})`);
  await t.close();
}

run(async b => {
  fs.mkdirSync(CFG, {recursive: true});
  const keep = [MD, LK].map(f => [f, fs.existsSync(f) ? fs.readFileSync(f) : null]);
  fs.writeFileSync(MD, JSON.stringify({jellyfin: 'https://films.example/web/'})); fs.writeFileSync(LK, JSON.stringify(LINKS));
  const q = await page(b, 412, 915); await q.goto(BASE);
  try {
    check((await save(q, {reset: true})).ok(), 'start from the default layout');
    await flow(b, 412, 915, '');
    await flow(b, 1920, 1080, '');

    // a group typed and then a button pressed at once (no Enter, no Tab): leaving the field regroups, and the first press
    // still counts (a Move acts on the same link in its new group; Done saves the new group)
    const f = await today(b, 412, 915);
    await f.locator('#editToday').click(); await f.locator('#main .home.edit').waitFor();
    const order = () => f.locator('#main .edit .edlink').evaluateAll(rs => rs.map(r => r.dataset.key));
    await lrow(f, '/notes-test/').locator('input[data-f=group]').fill('Studio');
    await lrow(f, '/notes-test/').locator('[data-mv="1"]').click();
    const o1 = await order(), focus = await f.evaluate(() => document.activeElement.closest('.edrow')?.dataset.key);
    check(await lrow(f, '/notes-test/').locator('input[data-f=group]').inputValue() === 'Studio' && o1.indexOf('link:/studio-test/') < o1.indexOf('link:/notes-test/') && focus === 'link:/notes-test/',
      `a group typed, then Move down pressed once: the link joins the group and moves down in it, the keyboard on it (${o1.join(', ')}; focus ${focus})`);
    await lrow(f, '/files-test/').locator('input[data-f=group]').fill('Later');
    await f.locator('#main .edit .edtop [data-ed=done]').click();
    const closed = await f.locator('#editToday').waitFor({timeout: 5000}).then(() => true, () => false);
    const kept = closed && JSON.parse(fs.readFileSync(TD, 'utf8'));
    check(closed && kept.open?.groups?.['link:/files-test/'] === 'Later' && kept.open?.groups?.['link:/notes-test/'] === 'Studio',
      `a group typed, then Done pressed once: saved with the new group (${closed ? JSON.stringify(kept.open) : 'still in Edit'})`);
    check(!f.errors.length, `first press after a group: no page errors (${f.errors.join(' | ')})`);
    await f.close();
    check((await save(q, {reset: true})).ok(), 'back to the default layout');

    // a today.json that switches Zeus off by hand (or an older page): Zeus stays on, in the state and in Edit; Done drops it
    fs.writeFileSync(TD, JSON.stringify({v: 1, quiet: ['throne', 'demo-server']}));
    const z = await today(b, 412, 915);
    check(await z.evaluate(() => !S.quiet.includes('throne') && S.quiet.includes('demo-server')), 'throne in today.json: Zeus is not quiet, the rest of the list is');
    await z.locator('#editToday').click(); await z.locator('#main .home.edit').waitFor();
    check(await z.locator('#main .edit [data-q=throne]').isChecked() && !(await z.locator('#main .edit [data-q="demo-server"]').isChecked()), 'throne in today.json: Edit shows Zeus on (and the other switch off)');
    await z.locator('#main .edit .edtop [data-ed=done]').click(); await z.locator('#editToday').waitFor({timeout: 5000}).catch(() => {});
    const zf = JSON.parse(fs.readFileSync(TD, 'utf8'));
    check(JSON.stringify(zf.quiet) === '["demo-server"]' && await z.evaluate(() => !S.quiet.includes('throne')), `Done saves without throne (${JSON.stringify(zf)})`);
    check(!z.errors.length, `Zeus locked: no page errors (${z.errors.join(' | ')})`);
    await z.close();
    check((await save(q, {reset: true})).ok(), 'back to the default layout');

    // the narrowest phone: Edit fits at 375 px
    const s = await today(b, 375, 812);
    await s.locator('#editToday').click(); await s.locator('#main .home.edit').waitFor();
    check(await noOverflow(s), '375: Edit has no sideways scroll');
    await s.close();

    // every tile hidden: Today says so and Edit Today stays, so he can bring them back
    const ids = await (async () => { const x = await today(b, 412, 915); const v = await x.evaluate(() => home.tileList().map(e => e.id)); await x.close(); return v; })();
    check((await save(q, {tiles: {hidden: ids}})).ok(), 'save a layout with every tile hidden');
    const e = await today(b, 412, 915);
    check(await e.locator('#main .places .quiet').textContent().then(s => /Every section is hidden/.test(s)).catch(() => false) && await e.locator('#editToday').count() === 1,
      'every tile hidden: Today says so and still has Edit Today');
    await e.close();

    // a broken today.json: Today shows the default and says so in plain words; saving sets the old file aside
    fs.writeFileSync(TD, '{"v":1,"tiles":');
    const k = await today(b, 412, 915);
    const why = await k.locator('#main .today-problem').textContent().catch(() => '');
    check(/could not be used/.test(why) && /default layout/.test(why) && (await tiles(k)).includes('spartamelee'), `a broken today.json: the default layout, and a line that says so ("${why}")`);
    await shot(k, '07-broken-file-412');
    await k.close();
    check((await save(q, {reset: true})).ok() && fs.readdirSync(CFG).some(f => /^today\.set-aside-\d{8}-\d{4}\.json$/.test(f)), 'Reset over a broken file keeps the old one beside it (today.set-aside-<date>.json)');
  } finally {
    await save(q, {reset: true}).catch(() => {});
    keep.forEach(([f, v]) => v === null ? fs.rmSync(f, {force: true}) : fs.writeFileSync(f, v));
    await q.close();
  }
});
