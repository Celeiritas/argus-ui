// Memory (docs/memory.md, ui-plan §10): the bundled plugin reads the fixture snapshot folder (tests/run.sh copies
// tests/fixtures/memory/Server-brain/ into the throwaway HOME's ~/.mnemosyne/), lists three snapshots and never the decoys,
// tells 3-2-1 honestly, and Back up now is a hold that works by keyboard, refuses while a game runs, then starts the job.
// 1.1.0, plain words: each copy is one sentence (no status words, never "secrets"), and Today's line is one sentence. The
// three scenarios at the end write their own snapshot folder and PC marker, dated from today (named in memory.json), so
// their sentences never depend on how old the fixture is.
const {BASE, check, page, noOverflow, shot, units, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home');
const GUARD = path.join(HOME, '.local/state/medusa-gameguard/frozen-by-me.json');
const BRAIN = 'mnemosyne-server-brain', OFFSITE = 'mnemosyne-server-offsite';
const CONFIG = path.join(HOME, '.config/argus-ui/memory.json');
const MINE = path.join(HOME, 'backups'), SNAPS = path.join(MINE, 'Server-brain'), MARKER = path.join(MINE, 'last-backup.json');
const STATUS_WORDS = /\b(Done|Old|None|Unknown|Not yet|Failed|Not run)\b/;
const KEYS = 'your passwords and keys are left out on purpose: you back those up by hand, typing the passphrase';
const WATCH = 'look at its weekly job under Mnemosyne on the Argus page';
const brain = () => JSON.parse(fs.readFileSync(path.join(process.env.FIXTURES, 'units.json')))[BRAIN];
async function hold(p, btn, ms) { await btn.focus(); await p.keyboard.down('Space'); await p.waitForTimeout(ms); await p.keyboard.up('Space'); }

// times the way the server words them (plugin.py stamp()), from this machine's clock: the server runs in the same zone
const pad = n => String(n).padStart(2, '0');
function day(back, h, mi = 0) { const d = new Date(); d.setHours(h, mi, 0, 0); d.setDate(d.getDate() - back); return d; }
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const clock = d => `${d.getHours() % 12 || 12}:${pad(d.getMinutes())} ${d.getHours() < 12 ? 'AM' : 'PM'}`;
const weekday = (d, form = 'long') => d.toLocaleDateString('en-US', {weekday: form});
const stamp = (d, back) => back < 7 ? `${weekday(d)}, ${clock(d)}`
  : `${d.toLocaleDateString('en-US', {month: 'short'})} ${d.getDate()}${d.getFullYear() !== new Date().getFullYear() ? `, ${d.getFullYear()}` : ''}, ${clock(d)}`;
const systemd = d => `${weekday(d, 'short')} ${ymd(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}:00 MST`;

// one scenario: snapshots [days back, bytes], the PC's marker (or none), the off-site task (or none)
let made = [];
function scenario({snaps, marker, offsite}) {
  made.forEach(f => fs.rmSync(f, {force: true})); made = [];       // only the files this test wrote, inside the throwaway HOME
  fs.mkdirSync(SNAPS, {recursive: true}); fs.mkdirSync(path.dirname(CONFIG), {recursive: true});
  for (const [back, size] of snaps) { const f = path.join(SNAPS, `Server-brain_${ymd(day(back, 4))}_0400.tar.gz`); fs.writeFileSync(f, 'x'.repeat(size)); made.push(f); }
  if (marker) { fs.writeFileSync(MARKER, JSON.stringify(marker)); made.push(MARKER); }
  fs.writeFileSync(CONFIG, JSON.stringify({folder: '~/backups/Server-brain', pc_marker: '~/backups/last-backup.json'}));
  units(u => { u[BRAIN].ActiveState = 'inactive'; if (offsite) u[OFFSITE] = offsite; else delete u[OFFSITE]; });
}
const say = (p, k) => p.locator(`.mem-copies li[data-key="${k}"] .say`).textContent({timeout: 3000}).catch(() => null);   // a missing sentence fails a check, not the run

run(async b => {
  units(u => { u[BRAIN] = {Result: 'success', ActiveState: 'inactive', ExecMainStartTimestamp: 'Sun 2026-11-08 04:00:00 MST',
    ExecMainExitTimestamp: 'Sun 2026-11-08 04:03:10 MST', timer: true, timer_on: true, timer_en: true, Description: 'Mnemosyne - weekly brain snapshot'}; });
  try {
    const p = await page(b);
    await p.goto(BASE + 'memory'); await p.locator('.mem-shelf .mem-jar').first().waitFor({timeout: 5000});
    check(await p.locator('#realms a.realm[data-id="memory"] b').textContent() === 'Mnemosyne' && await p.locator('#realms a.realm', {hasText: 'Backups'}).count() === 0, 'a Mnemosyne pill in the section bar, her name its only title (4.45.0)');
    check(await p.locator('.title h1').textContent() === 'Mnemosyne' && /mnemosyne\.png$/.test(await p.locator('#hero').getAttribute('src')) && !(await p.locator('#hero').isHidden()), 'the page heading says Mnemosyne, under her medallion');
    check(/~\/\.mnemosyne\/Server-brain\//.test(await p.locator('#mem-where').textContent()), 'it says which folder it reads');
    check(await p.locator('.mem-shelf .mem-jar').count() === 3 && await p.locator('.mem-list li').count() === 3, 'three snapshots on the shelf and in the list; the decoys are not listed');
    const list = await p.locator('.mem-list').textContent();
    check(/Nov 8, 4:00 AM/.test(list) && ['600', '1,200', '900'].every(n => list.includes(`(${n} bytes)`)), 'each with its time and exact size in bytes');
    check(await p.locator('.mem-shelf .mem-jar').last().evaluate(e => e.classList.contains('newest')), 'oldest on the left, the newest on the right and marked');
    const hs = await p.locator('.mem-shelf .mem-bar').evaluateAll(bs => bs.map(x => x.getBoundingClientRect().height));
    check(hs[1] > hs[2] && hs[2] > hs[0], `bar height follows size (${hs.map(Math.round).join(', ')} px)`);
    const facts = await p.locator('.mem-facts').textContent();
    check(/Last snapshot/.test(facts) && /Next run\s*Oct 25/.test(facts) && /3 snapshots, 2\.6 KB in all/.test(facts), 'last snapshot, next run from the timer, count and total');
    const kind = k => p.locator(`.mem-copies li[data-key="${k}"]`).getAttribute('data-kind');
    check(/^(fresh|stale)$/.test(await kind('server')) && /^The server(?: took|'s newest snapshot)/.test(await say(p, 'server'))
      && await say(p, 'pc') === `No word has come from your PC's weekly backup yet (the PC sends word each time one finishes); ${KEYS}.`
      && await say(p, 'offsite') === "The server's backups are not copied outside your home yet: the job that will do that is planned but not built.",
      '3-2-1 in sentences: the server\'s snapshots, no word from the PC yet (never a guess), nothing outside the home yet');
    check(await p.locator('.mem-copies .mark[aria-hidden="true"]').count() === 3 && await p.locator('.mem-copies li .name').count() === 3, 'each copy has a mark and a name, never colour alone');
    const named = await p.locator('.mem-copies li').evaluateAll(ls => ls.map(l => [l.getAttribute('aria-label'), l.querySelector('.say')?.textContent]));
    check(named.length === 3 && named.every(([a, s]) => a && a === s) && await p.getByRole('listitem', {name: await say(p, 'pc'), exact: true}).count() === 1, "each row's accessible name is its sentence");
    const read = await p.locator('.memory').innerText();
    check(!STATUS_WORDS.test(read) && !/secret/i.test(read + named.flat().join(' ')), `no status word and never "secrets" on the page${STATUS_WORDS.test(read) ? ': ' + read.match(STATUS_WORDS)[0] : ''}`);

    const btn = p.locator('#mem-backup'), why = p.locator('#mem-why');
    check((await btn.boundingBox()).height >= 44 && /Jellyfin/.test(await p.locator('#mem-note').textContent()), 'Back up now: 44 px, and says what it pauses');
    await hold(p, btn, 700); await p.waitForTimeout(300);
    check(brain().ActiveState === 'inactive', 'let go early: nothing is started');

    fs.mkdirSync(path.dirname(GUARD), {recursive: true}); fs.writeFileSync(GUARD, JSON.stringify(['mnemosyne-ollama']));
    await hold(p, btn, 3400);
    await why.filter({hasText: 'game is running'}).waitFor({timeout: 4000}).catch(() => {});
    check(/game is running/.test(await why.textContent()) && brain().ActiveState === 'inactive', 'held by keyboard while a game runs: refused, nothing started');

    fs.writeFileSync(GUARD, '[]');
    await hold(p, btn, 3400);
    await why.filter({hasText: 'Backup started'}).waitFor({timeout: 4000}).catch(() => {});
    check(/Backup started/.test(await why.textContent()) && brain().ActiveState === 'active', 'held by keyboard with no game: the brain job is started');
    await p.locator('.mem-shelf .filling').waitFor({timeout: 8000}).catch(() => {});
    check(await p.locator('.mem-shelf .filling').count() === 1 && /Backing up now/.test(await p.locator('#mem-facts').textContent()), 'and a new jar fills on the shelf');
    check(await kind('server') === 'running' && /^The server is taking a new snapshot of itself now; its newest finished one is from /.test(await say(p, 'server'))
      && await p.locator('.mem-copies li[data-key="server"] .mark').textContent() === '↻', 'while it runs, the server\'s row says so, with its own mark');
    await shot(p, 'memory');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

    const h = await page(b);
    await h.goto(BASE); await h.locator('.place[data-id="memory"]').locator('.pl', {hasText: 'Backing up'}).waitFor({timeout: 5000}).catch(() => {});
    check(await h.locator('.place[data-id="memory"]').locator('.pl').textContent() === "Backing up the server now; no word from your PC's backup yet. The server has no copy outside your home yet.",
      "Today: Mnemosyne's card shows Memory's line, the running backup first");
    await p.close(); await h.close();              // their 15-second refreshes would only slow the checks below

    const ph = await page(b, 375, 760);
    await ph.goto(BASE + 'memory'); await ph.locator('.mem-shelf .mem-jar').first().waitFor({timeout: 5000}); await ph.waitForTimeout(300);
    check(await noOverflow(ph), '375 px: no sideways scrolling');
    check((await ph.locator('#mem-backup').boundingBox()).height >= 44, '375 px: the button keeps its 44 px');
    check(await ph.locator('.mem-facts dd').evaluateAll(ds => ds.every(d => d.scrollWidth <= d.clientWidth + 1)), '375 px: no number is cut off');
    await shot(ph, 'memory-375');
    check(ph.errors.length === 0, '375 px: no page errors ' + ph.errors.join(' | '));

    // ---- 1.1.0, plain words: three scenarios, each read on the page and on Today, at 360, 375 and 412 px
    const fine = {Result: 'success', ActiveState: 'inactive', ExecMainStartTimestamp: systemd(day(3, 5, 30)), ExecMainExitTimestamp: systemd(day(3, 5, 41)), Description: 'Mnemosyne - a copy outside the home'};
    const pcFresh = {at: `${ymd(day(3, 5))}T05:00:00`, sets: 6, bytes: 123456789};
    const scenarios = [
      {name: 'fine', snaps: [[2, 1500], [9, 1200]], marker: pcFresh, offsite: fine, rows: {
        server: `The server took its newest snapshot of itself 2 days ago (${stamp(day(2, 4), 2)}) and keeps 2 of them, 2.6 KB in all.`,
        pc: `Your PC's weekly backup finished 3 days ago (${stamp(day(3, 5), 3)}) with 6 sets of files, 117.7 MB; ${KEYS}.`,
        offsite: `The server's backups were last copied outside your home 3 days ago (${stamp(day(3, 5, 30), 3)}).`},
        marks: '✓✓✓', today: "Backups are fresh: the server 2 days ago, your PC 3 days ago. The server's backups were copied outside your home 3 days ago.", needs: false},
      {name: 'pc-never-heard', snaps: [[2, 1500], [9, 1200]], marker: null, offsite: null, rows: {
        server: `The server took its newest snapshot of itself 2 days ago (${stamp(day(2, 4), 2)}) and keeps 2 of them, 2.6 KB in all.`,
        pc: `No word has come from your PC's weekly backup yet (the PC sends word each time one finishes); ${KEYS}.`,
        offsite: "The server's backups are not copied outside your home yet: the job that will do that is planned but not built."},
        marks: '✓?✕', today: "The server backed up 2 days ago; no word from your PC's backup yet. The server has no copy outside your home yet.", needs: false},
      {name: 'server-older-than-a-week', snaps: [[10, 1500], [17, 1200]], marker: pcFresh, offsite: null, rows: {
        server: `The server's newest snapshot of itself is from 10 days ago (${stamp(day(10, 4), 10)}), older than a week, so ${WATCH}.`,
        pc: `Your PC's weekly backup finished 3 days ago (${stamp(day(3, 5), 3)}) with 6 sets of files, 117.7 MB; ${KEYS}.`,
        offsite: "The server's backups are not copied outside your home yet: the job that will do that is planned but not built."},
        marks: '!✓✕', today: "The server's backup is older than a week (10 days ago); your PC backed up 3 days ago. The server has no copy outside your home yet.", needs: true, action: 'Check backups'},
      {name: 'pc-older-than-a-week', snaps: [[2, 1500], [9, 1200]], marker: {at: `${ymd(day(12, 5))}T05:00:00`, sets: 6, bytes: 123456789}, offsite: null, rows: {
        server: `The server took its newest snapshot of itself 2 days ago (${stamp(day(2, 4), 2)}) and keeps 2 of them, 2.6 KB in all.`,
        pc: `Your PC's weekly backup last finished 12 days ago (${stamp(day(12, 5), 12)}), older than a week, so check its scheduled task on your PC; ${KEYS}.`,
        offsite: "The server's backups are not copied outside your home yet: the job that will do that is planned but not built."},
        marks: '✓!✕', today: "Check your PC's backup: it last finished 12 days ago; the server backed up 2 days ago. The server has no copy outside your home yet.", needs: true,
        action: "Check the PC's backup", verdict: "Check your PC's backup"}];
    for (const s of scenarios) {
      scenario(s);
      const q = await page(b, 412, 915);
      await q.goto(BASE + 'memory'); await q.locator('.mem-copies li[data-key="server"]').waitFor({timeout: 5000}); await q.waitForTimeout(300);
      const got = {server: await say(q, 'server'), pc: await say(q, 'pc'), offsite: await say(q, 'offsite')};
      const bad = Object.keys(s.rows).filter(k => got[k] !== s.rows[k]);
      check(!bad.length, `${s.name}: each row says its sentence${bad.map(k => `\n        ${k}: ${got[k]}\n        want: ${s.rows[k]}`).join('')}`);
      const marks = (await q.locator('.mem-copies .mark').allTextContents()).join('');
      check(marks === s.marks, `${s.name}: the marks ${s.marks} (${marks})`);
      check(await noOverflow(q), `${s.name}, 412 px: no sideways scrolling`);
      const text = await q.locator('.memory').innerText();
      check(!STATUS_WORDS.test(text) && !/secret/i.test(text), `${s.name}: no status word, never "secrets"${STATUS_WORDS.test(text) ? ': ' + text.match(STATUS_WORDS)[0] : ''}`);
      if (s.name === 'server-older-than-a-week') check(/older than a week: look at its weekly job under Mnemosyne/.test(await q.locator('#mem-facts').textContent()), `${s.name}: the warning above says the same, in the same words`);
      await q.locator('.mem-321').scrollIntoViewIfNeeded(); await shot(q, `memory-${s.name}`);
      check(q.errors.length === 0, `${s.name}: no page errors ` + q.errors.join(' | '));
      await q.close();
      for (const w of [360, 375]) {
        const n = await page(b, w, 800);
        await n.goto(BASE + 'memory'); await n.locator('.mem-copies li[data-key="server"]').waitFor({timeout: 5000}); await n.waitForTimeout(300);
        const fits = await n.locator('.mem-copies li').evaluateAll(ls => ls.every(l => l.scrollWidth <= l.clientWidth + 1 && l.getBoundingClientRect().right <= innerWidth));
        check(await noOverflow(n) && fits, `${s.name}, ${w} px: no sideways scrolling, every sentence wraps inside its row`);
        await n.close();
      }
      const t = await page(b, 412, 915);
      // Today: the line is in one place (4.44.0): the row in Needs you when it needs you, else Mnemosyne's card
      await t.goto(BASE); const card = t.locator('.place[data-id="memory"]').locator('.pl'), row = t.locator('.need', {hasText: s.today});
      await (s.needs ? row : card.filter({hasText: s.today})).waitFor({timeout: 5000}).catch(() => {});
      await t.waitForFunction(() => !/Checking…|Asking every section/.test(document.querySelector('#main .home').textContent), null, {timeout: 5000}).catch(() => {});
      if (!s.needs) check(await card.textContent() === s.today, `${s.name}: Today's line: ${await card.textContent()}`);
      check(s.needs ? await row.count() === 1 && await row.locator('a.go').textContent() === (s.action || 'Check backups') && await card.count() === 0 : await row.count() === 0,
        `${s.name}: ${s.needs ? 'Needs you shows the line with ' + (s.action || 'Check backups') + ', and no Mnemosyne card' : 'nothing in Needs you'}`);
      await t.close();
      if (s.verdict) for (const [w, h] of [[360, 800], [412, 915], [1440, 900]]) {        // a card shows only the start of the line, a row all of it: the verdict must be in what shows
        const v = await page(b, w, h); await v.goto(BASE);
        const pl = s.needs ? v.locator('.need', {hasText: s.verdict}).locator('.nb p') : v.locator('.place[data-id="memory"]').locator('.pl');
        await pl.filter({hasText: s.verdict}).waitFor({timeout: 5000}).catch(() => {});
        const shown = await pl.evaluate(el => { const n = el.lastChild, r = document.createRange(), box = el.getBoundingClientRect(); let i = 0;
          for (; i < n.length; i++) { r.setStart(n, i); r.setEnd(n, i + 1); if (r.getBoundingClientRect().right > box.right + 0.5) break; } return i; });
        check(shown >= s.verdict.length, `${s.name}, ${w} px: Today's ${s.needs ? 'row' : 'card'} shows the verdict first (${shown} of ${s.verdict.length} characters visible)`);
        await v.close();
      }
    }
  } finally {
    units(u => { delete u[BRAIN]; delete u[OFFSITE]; });     // the later checks see the fixtures as they were
    fs.rmSync(GUARD, {force: true}); fs.rmSync(CONFIG, {force: true});
    made.forEach(f => fs.rmSync(f, {force: true}));
  }
});
