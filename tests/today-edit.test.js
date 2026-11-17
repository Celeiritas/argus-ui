// Edit Today (4.50.0, web/js/today-edit.js, server/today.py, docs/home.md "Edit Today"): the owner shows, hides, orders and
// renames Today's sections and More's links, and switches each section's reminders off or on. A mode with a clear Done and
// Cancel; Move up / down buttons are the keyboard path; a god's section keeps its god's name; Mentor never reminds, Zeus always
// does (4.50.1: on and locked, even when today.json says otherwise); Mnemosyne's switch says what off drops.
// Since 4.54.0 its button is in More's Settings (docs/home.md "One way to each place"), at every width; pressed on another page
// it opens Today with the lists. Only a section that can have a line on Today has Show; links have no groups and no Show.
// Saved on the server (one Today on every device), so the checks read it back after a reload. A learner has no Edit Today
// (the server's 403 is in tests/today_edit_test.py and tests/gate_test.py). Every check here leaves today.json at the default.
// The whole flow runs at 600 px (Edit's narrow rows) and 1920 px; a 412 px phone gets its own checks.
// Pictures (numbered, at 600 and 1920 px): SHOTS, or EDIT_SHOTS when set (a folder of their own).
const {BASE, check, page, noOverflow, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CFG = path.join(HOME, '.config/argus-ui');
const MD = path.join(CFG, 'media.json'), LK = path.join(CFG, 'links.json'), TD = path.join(CFG, 'today.json');
// placeholders only: a section that opens elsewhere, and two plain links (the host's real links.json is never in the repo)
const LINKS = [{name: 'Studio Test', what: 'Studio', href: '/studio-test/', section: true}, {name: 'Notes', what: 'Pages', href: '/notes-test/'},
  {name: 'Files', what: 'Shared files', href: '/files-test/'}];
const NAME = '<b>Lab</b> & co';                      // typed by the owner: drawn as words, never as HTML
const settle = fn => async r => { try { await fn(r); } catch (e) { if (!/closed|disposed/i.test(String(e && e.message))) throw e; } };
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); }, null, {timeout: 8000}).catch(() => {});
const OUT = process.env.EDIT_SHOTS || process.env.SHOTS;
const shot = (p, name) => OUT && p.screenshot({path: path.join(OUT, name + '.png'), fullPage: false});
const save = (p, body) => p.request.post(BASE + 'api/today', {data: body});
async function today(b, w, h, where = '') {
  const p = await page(b, w, h);
  // the realm quiet: every section's own line, needing nothing; no alerts, no failed checks (Today as on a calm morning)
  await p.route('**/api/*/status*', settle(async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); }));
  await p.route('**/api/state*', settle(async r => { const res = await r.fetch(), j = await res.json();
    (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(w => { if (w.works === false) w.works = true; });
    j.alerts = []; await r.fulfill({response: res, json: j}); }));
  await p.goto(BASE + where); await p.waitForLoadState('load');
  if (p.errors.length) throw new Error('the page failed to load: ' + p.errors.join(' | '));
  await p.evaluate(() => refresh()); if (!where) await settled(p);
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
  return p;
}
// Today's lines (one per section with news), and More: the More button that is showing (the strip's or the bottom bar's)
const tiles = p => p.locator('#main .newslist .qline').evaluateAll(as => as.map(a => a.dataset.id));
const moreBtn = p => p.locator('[data-more]:visible').first();
async function openMore(p) { await moreBtn(p).click(); await p.locator('#moreSheet[open]').waitFor({timeout: 3000}); }
async function closeMore(p) { if (await p.locator('#moreSheet[open]').count()) { await p.keyboard.press('Escape'); await p.waitForTimeout(150); } }
async function edit(p) { await openMore(p); await p.locator('#editToday').click(); await p.locator('#main .home.edit').waitFor(); }
const onMore = p => p.evaluate(() => !!document.activeElement?.matches('[data-more]') && !document.getElementById('moreSheet').open);
// a learner's page, drawn and looked at in one step: the 15 s refresh brings the owner's state back, and a check made after
// it would see his More (CI run 44063305461). Her bar may have no More at all; where it has one, its sheet has no Edit Today.
const asLearner = p => p.evaluate(() => { S.role = 'learner'; render();
  const more = [...document.querySelectorAll('[data-more]')].find(b => !b.hidden && b.getClientRects().length);
  if (more) more.click();
  const ed = document.getElementById('editToday'), r = {more: !!more, edit: !!ed.getClientRects().length};
  document.getElementById('moreSheet').close(); S.role = 'owner'; render(); return r; });
const row = (p, id) => p.locator(`#main .edit .edrow[data-id="${id}"]`);
const lrow = (p, href) => p.locator(`#main .edit .edrow[data-key="link:${href}"]`);
const small = p => p.locator('#main .edit').evaluate(ed => [...ed.querySelectorAll('button, input:not([type=checkbox]), label.check, label.edswitch')]
  .filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 20) || e.getAttribute('aria-label') || e.className, Math.round(r.width), Math.round(r.height)]; })
  .filter(([, w, h]) => w < 44 || h < 44));

// the whole of it at one width: Today, Edit from More, a rename, a hidden line, More's links, the switches, Done
async function flow(b, w, h, n) {
  const t = await today(b, w, h), tag = `${w}`;
  const before = await tiles(t);
  check(before.includes('demo-server') && before.includes('memory') && !before.includes('spartamelee') && !before.includes('argus'), `${tag}: the fixture's lines: server plugins only (${before.join(', ')})`);
  check(await t.locator('#main #editToday, #main .places, #main .open').count() === 0, `${tag}: no Edit Today, tiles or Open on Today itself`);
  await openMore(t);
  check(await t.locator('#editToday').isVisible() && (await t.locator('#editToday').boundingBox()).height >= 44 && !!(await t.locator('#editToday').evaluate(e => e.closest('#moreSet'))),
    `${tag}: the owner has Edit Today in More's Settings, 44 px tall`);
  await closeMore(t);
  if (w === 600) {
    const l = await asLearner(t); await t.waitForTimeout(200);
    check(!l.edit, `${tag}: a learner has no Edit Today (${JSON.stringify(l)})`);
  }
  await shot(t, `${n}01-today-${tag}`);

  // ---- Edit mode ----
  await edit(t);
  check(await t.evaluate(() => document.activeElement.id) === 'edit-h' && !(await t.locator('#moreSheet[open]').count()), `${tag}: More closes and Edit opens with the keyboard on its heading`);
  await t.waitForTimeout(400);
  check(await t.evaluate(() => document.activeElement.id) === 'edit-h', `${tag}: and the keyboard stays there once More has closed`);
  check(await noOverflow(t), `${tag}: Edit has no sideways scroll`);
  const tiny = await small(t);
  check(!tiny.length, `${tag}: every button, field and switch in Edit is at least 44 by 44 px (${JSON.stringify(tiny.slice(0, 6))})`);
  check(await row(t, 'argus').locator('input[data-f=name]').count() === 0 && /A god's name/.test(await row(t, 'argus').textContent()), `${tag}: a god's section (Argus) has no name field`);
  check(await row(t, 'spartamelee').locator('input[data-f=shown]').count() === 0 && await row(t, 'argus').locator('input[data-f=shown]').count() === 0 && await row(t, 'demo-server').locator('input[data-f=shown]').count() === 1,
    `${tag}: Show only where a line can be on Today (a server plugin), not on Argus or a static plugin`);
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
  // rename a section (with HTML in it), then move it up by keyboard: the keyboard stays on the button
  await row(t, 'demo-server').locator('input[data-f=name]').fill(NAME);
  await row(t, 'demo-server').scrollIntoViewIfNeeded(); await shot(t, `${n}03-rename-${tag}`);
  const i0 = +(await row(t, 'demo-server').getAttribute('data-i'));
  await row(t, 'demo-server').locator('[data-mv="-1"]').focus(); await t.keyboard.press('Enter');
  const after = await t.evaluate(() => [document.activeElement.closest('.edrow')?.dataset.id, +document.activeElement.closest('.edrow')?.dataset.i, document.activeElement.dataset.mv]);
  check(after[0] === 'demo-server' && after[1] === i0 - 1 && after[2] === '-1', `${tag}: Move up by keyboard moves the section one up and keeps the keyboard on it (${JSON.stringify(after)}, was ${i0})`);
  check(await row(t, 'demo-server').locator('input[data-f=name]').inputValue() === NAME, `${tag}: a typed name survives a move`);
  // hide a line by keyboard (Space on Show)
  await row(t, 'memory').locator('input[data-f=shown]').focus(); await t.keyboard.press('Space');
  check(await row(t, 'memory').evaluate(r => r.classList.contains('off')), `${tag}: Space on Show hides a line (greyed, still listed)`);

  // ---- Links in More: renamed and moved; no groups, no Show ----
  check(await t.locator('#ed-open').textContent() === 'Links in More' && await t.locator('#main .edit .edlink input[data-f=group], #main .edit .edlink input[data-f=shown]').count() === 0,
    `${tag}: "Links in More", with no group field and no Show`);
  await lrow(t, '/notes-test/').locator('input[data-f=name]').fill('Shared');
  await lrow(t, '/studio-test/').locator('input[data-f=name]').fill('Studio Renamed');
  await lrow(t, '/files-test/').locator('[data-mv="-1"]').click();
  check(await t.evaluate(() => document.activeElement.closest('.edrow')?.dataset.key) === 'link:/files-test/', `${tag}: Move up keeps the keyboard on the moved link`);
  await t.locator('#ed-open').scrollIntoViewIfNeeded(); await t.waitForTimeout(100); await shot(t, `${n}04-links-${tag}`);
  check(await noOverflow(t), `${tag}: the link rows have no sideways scroll`);

  // ---- Reminders ----
  const sw = t.locator('#main .edit [data-q="demo-server"]');
  check(await sw.isChecked(), `${tag}: a section reminds him by default`);
  await sw.click();
  check(!(await sw.isChecked()) && /never asks/.test(await sw.locator('xpath=..').textContent()), `${tag}: switching it off says so`);
  await t.locator('#ed-quiet').scrollIntoViewIfNeeded(); await t.waitForTimeout(100); await shot(t, `${n}05-reminders-${tag}`);

  // ---- Done ----
  await t.locator('#main .edit .edend [data-ed=done]').click();
  await t.locator('#main .home:not(.edit)').waitFor(); await settled(t); await t.waitForTimeout(300);
  check(await onMore(t), `${tag}: after Done the keyboard is back on More, where Edit Today was`);
  const now = await tiles(t), file = JSON.parse(fs.readFileSync(TD, 'utf8'));
  check(!now.includes('memory') && now.includes('demo-server'), `${tag}: the hidden line is gone from Today (${now.join(', ')})`);
  const ord = file.tiles?.order || [];
  check(ord.indexOf('demo-server') === i0 - 1 && now.every((x, i) => !i || ord.indexOf(now[i - 1]) < ord.indexOf(x)), `${tag}: the moved section stands one higher, and Today's lines follow his order (${now.join(', ')})`);
  const qb = t.locator('#main .qline[data-id="demo-server"] b');
  check(await qb.first().textContent() === NAME && await qb.locator('b').count() === 0, `${tag}: the new name shows as typed, as words (${await qb.first().innerHTML()})`);
  check(await t.evaluate(nm => sections().find(e => e.id === 'demo-server').word === nm, NAME), `${tag}: the bar, the strip and More use the same name (sections())`);
  check(await t.evaluate(() => sections().find(e => e.section)?.word) === 'Studio Renamed' && await t.locator('#realms a.realm.link b').textContent() === 'Studio Renamed',
    `${tag}: the section that opens elsewhere carries his name on the strip`);
  const away = await t.locator('#moreAway a.srow b').allTextContents();
  check(JSON.stringify(away) === '["Files","Shared"]', `${tag}: More's other pages: his names, his order, not the section (${away.join(', ')})`);
  check(await t.evaluate(() => S.quiet.includes('demo-server') && S.quiet.includes('mentor')), `${tag}: the switched-off section is quiet now, Mentor still is`);
  check(await noOverflow(t), `${tag}: Today after Done has no sideways scroll`);
  await t.evaluate(() => scrollTo(0, 0)); await shot(t, `${n}06-done-${tag}`);
  const o = file.open || {};
  check(file.tiles.names['demo-server'] === NAME && file.tiles.hidden.includes('memory') && o.names?.['link:/notes-test/'] === 'Shared' && o.order?.indexOf('link:/files-test/') < o.order?.indexOf('link:/notes-test/')
    && !('groups' in o) && !('hidden' in o) && file.quiet.includes('demo-server'), `${tag}: today.json holds what he changed (${JSON.stringify(file).slice(0, 260)})`);

  // kept: another page load (another device) shows the same Today
  await t.reload(); await t.evaluate(() => refresh()); await settled(t); await t.waitForTimeout(300);
  check(await t.locator('#main .qline[data-id="demo-server"] b').first().textContent() === NAME && !(await tiles(t)).includes('memory'), `${tag}: a reload shows his Today`);

  // Cancel keeps Today as it was, and gives the keyboard back to More
  await edit(t);
  await row(t, 'demo-server').locator('input[data-f=name]').fill('Something else');
  await t.locator('#main .edit .edtop [data-ed=cancel]').click(); await t.locator('#main .home:not(.edit)').waitFor(); await t.waitForTimeout(200);
  check(await t.locator('#main .qline[data-id="demo-server"] b').first().textContent() === NAME && await onMore(t), `${tag}: Cancel leaves Today as it was, the keyboard on More`);

  // Reset to default, then Done: the default again, and the file says so
  await edit(t);
  await t.locator('#main .edit [data-ed=reset]').click();
  check(await row(t, 'memory').evaluate(r => !r.classList.contains('off')) && await t.locator('#main .edit [data-q="demo-server"]').isChecked(), `${tag}: Reset to default fills Edit with the default`);
  await t.locator('#main .edit .edtop [data-ed=done]').click(); await t.locator('#main .home:not(.edit)').waitFor(); await settled(t); await t.waitForTimeout(300);
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
    await flow(b, 600, 915, '');
    await flow(b, 1920, 1080, '');

    // a phone: Edit Today is in More's Settings, 44 px tall; Edit and Done work, and the keyboard goes back to More
    const ph = await today(b, 412, 915);
    await openMore(ph);
    const eh = await ph.locator('#editToday').boundingBox();
    check(!!eh && eh.height >= 44 && await ph.locator('#main #editToday').count() === 0, `412: Edit Today in More's Settings, ${eh && Math.round(eh.height)} px tall, not on Today`);
    await closeMore(ph);
    const l = await asLearner(ph); await ph.waitForTimeout(200);
    check(!l.edit, `412: a learner has no Edit Today (${JSON.stringify(l)})`);
    await shot(ph, '01-today-412');
    await edit(ph); await ph.waitForTimeout(400);
    check(await ph.evaluate(() => document.activeElement.id) === 'edit-h' && await noOverflow(ph) && !(await small(ph)).length, '412: Edit opens with the keyboard on its heading, fits, every control 44 px or more');
    await ph.evaluate(() => scrollTo(0, 0)); await shot(ph, '02-edit-412');
    await ph.locator('#main .edit .edend [data-ed=done]').click(); await ph.locator('#main .home:not(.edit)').waitFor({timeout: 5000}).catch(() => {});
    check(await onMore(ph) && await ph.locator('#main .home.phone').count() === 1, '412: after Done the phone Today is back, the keyboard on More');
    check(!ph.errors.length, `412: no page errors (${ph.errors.join(' | ')})`);
    await ph.close();

    // Edit Today pressed on another page: Today opens with the lists, the keyboard on their heading, the address plain again
    for (const [w, h] of [[412, 915], [1440, 900]]) {
      const x = await today(b, w, h, 'olympus');
      await openMore(x); await x.locator('#editToday').click();
      const went = await x.locator('#main .home.edit').waitFor({timeout: 6000}).then(() => true, () => false);
      await x.waitForTimeout(300);
      check(went && await x.evaluate(() => document.activeElement.id) === 'edit-h' && !/#edit/.test(x.url()) && new URL(x.url()).pathname === new URL(BASE).pathname,
        `${w}: Edit Today from Olympus opens Today with the lists, the keyboard on their heading (${x.url()})`);
      await x.locator('#main .edit .edtop [data-ed=cancel]').click(); await x.locator('#main .home:not(.edit)').waitFor({timeout: 5000}).catch(() => {});
      check(!x.errors.length, `${w}: from another page, no page errors (${x.errors.join(' | ')})`);
      await x.close();
    }

    // a today.json that switches Zeus off by hand (or an older page): Zeus stays on, in the state and in Edit; Done drops it.
    // An older file's Open groups and hidden links are not kept either (4.54.0)
    fs.writeFileSync(TD, JSON.stringify({v: 1, quiet: ['throne', 'demo-server'], open: {groups: {'link:/notes-test/': 'Tools'}, hidden: ['link:/files-test/']}}));
    const z = await today(b, 412, 915);
    check(await z.evaluate(() => !S.quiet.includes('throne') && S.quiet.includes('demo-server')), 'throne in today.json: Zeus is not quiet, the rest of the list is');
    await openMore(z);
    check(JSON.stringify(await z.locator('#moreAway a.srow b').allTextContents()) === '["Notes","Files"]', 'an older file\'s hidden link is in More all the same: More lists every link');
    await closeMore(z);
    await edit(z);
    check(await z.locator('#main .edit [data-q=throne]').isChecked() && !(await z.locator('#main .edit [data-q="demo-server"]').isChecked()), 'throne in today.json: Edit shows Zeus on (and the other switch off)');
    await z.locator('#main .edit .edtop [data-ed=done]').click(); await z.locator('#main .home:not(.edit)').waitFor({timeout: 5000}).catch(() => {});
    const zf = JSON.parse(fs.readFileSync(TD, 'utf8'));
    check(JSON.stringify(zf.quiet) === '["demo-server"]' && !zf.open && await z.evaluate(() => !S.quiet.includes('throne')), `Done saves without throne, groups or hidden links (${JSON.stringify(zf)})`);
    check(!z.errors.length, `Zeus locked: no page errors (${z.errors.join(' | ')})`);
    await z.close();
    check((await save(q, {reset: true})).ok(), 'back to the default layout');

    // the narrowest phone: Edit fits at 375 px
    const s = await today(b, 375, 812);
    await edit(s);
    check(await noOverflow(s), '375: Edit has no sideways scroll');
    await s.close();

    // every line hidden: Today has no Sections part, and Edit Today is still in More, so he can bring them back
    const ids = await (async () => { const x = await today(b, 412, 915); const v = await x.evaluate(() => home.tileList().map(e => e.id)); await x.close(); return v; })();
    check((await save(q, {tiles: {hidden: ids}})).ok(), 'save a layout with every line hidden');
    for (const w of [600, 412]) {
      const e = await today(b, w, 915);
      await openMore(e);
      check(await e.locator('#main .news').count() === 0 && await e.locator('#editToday').isVisible(), `${w}: every line hidden: no Sections part on Today, Edit Today still in More`);
      await e.close();
    }

    // a broken today.json: Today shows the default and says so in plain words; saving sets the old file aside
    fs.writeFileSync(TD, '{"v":1,"tiles":');
    const k = await today(b, 412, 915);
    const why = await k.locator('#main .today-problem').textContent().catch(() => '');
    const dflt = await k.evaluate(() => home.tileList().some(e => e.id === 'memory' && e.shown));
    check(/could not be used/.test(why) && /default layout/.test(why) && dflt, `a broken today.json: the default layout, and a line that says so ("${why}")`);
    await shot(k, '07-broken-file-412');
    await k.close();
    check((await save(q, {reset: true})).ok() && fs.readdirSync(CFG).some(f => /^today\.set-aside-\d{8}-\d{4}\.json$/.test(f)), 'Reset over a broken file keeps the old one beside it (today.set-aside-<date>.json)');
  } finally {
    await save(q, {reset: true}).catch(() => {});
    keep.forEach(([f, v]) => v === null ? fs.rmSync(f, {force: true}) : fs.writeFileSync(f, v));
    await q.close();
  }
});
