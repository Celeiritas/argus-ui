// Memory (docs/memory.md, ui-plan §10): the bundled plugin reads the fixture snapshot folder (tests/run.sh copies
// tests/fixtures/memory/Server-brain/ into the throwaway HOME's ~/.mnemosyne/), lists three snapshots and never the decoys,
// tells 3-2-1 honestly, and Back up now is a hold that works by keyboard, refuses while a game runs, then starts the job.
const {BASE, check, page, noOverflow, shot, units, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home');
const GUARD = path.join(HOME, '.local/state/medusa-gameguard/frozen-by-me.json');
const BRAIN = 'mnemosyne-server-brain';
const brain = () => JSON.parse(fs.readFileSync(path.join(process.env.FIXTURES, 'units.json')))[BRAIN];
async function hold(p, btn, ms) { await btn.focus(); await p.keyboard.down('Space'); await p.waitForTimeout(ms); await p.keyboard.up('Space'); }

run(async b => {
  units(u => { u[BRAIN] = {Result: 'success', ActiveState: 'inactive', ExecMainStartTimestamp: 'Sun 2026-11-08 04:00:00 MST',
    ExecMainExitTimestamp: 'Sun 2026-11-08 04:03:10 MST', timer: true, timer_on: true, timer_en: true, Description: 'Mnemosyne - weekly brain snapshot'}; });
  try {
    const p = await page(b);
    await p.goto(BASE + 'memory'); await p.locator('.mem-shelf .mem-jar').first().waitFor({timeout: 5000});
    check(await p.locator('#realms a.realm', {hasText: 'Memory'}).count() === 1, 'a Memory pill in the section bar');
    check(/~\/\.mnemosyne\/Server-brain\//.test(await p.locator('#mem-where').textContent()), 'it says which folder it reads');
    check(await p.locator('.mem-shelf .mem-jar').count() === 3 && await p.locator('.mem-list li').count() === 3, 'three snapshots on the shelf and in the list; the decoys are not listed');
    const list = await p.locator('.mem-list').textContent();
    check(/Nov 8, 4:00 AM/.test(list) && ['600', '1,200', '900'].every(n => list.includes(`(${n} bytes)`)), 'each with its time and exact size in bytes');
    check(await p.locator('.mem-shelf .mem-jar').last().evaluate(e => e.classList.contains('newest')), 'oldest on the left, the newest on the right and marked');
    const hs = await p.locator('.mem-shelf .mem-bar').evaluateAll(bs => bs.map(x => x.getBoundingClientRect().height));
    check(hs[1] > hs[2] && hs[2] > hs[0], `bar height follows size (${hs.map(Math.round).join(', ')} px)`);
    const facts = await p.locator('.mem-facts').textContent();
    check(/Last snapshot/.test(facts) && /Next run\s*Oct 25/.test(facts) && /3 snapshots, 2\.6 KB in all/.test(facts), 'last snapshot, next run from the timer, count and total');
    const word = k => p.locator(`.mem-copies li[data-key="${k}"] .word`).textContent();
    check(/Done|Old/.test(await word('server')) && await word('pc') === 'Unknown' && await word('offsite') === 'Not yet', '3-2-1: server done, PC unknown without its marker, off-site not yet');
    check(await p.locator('.mem-copies .mark[aria-hidden="true"]').count() === 3, 'each copy has a mark and a word, never colour alone');

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
    await shot(p, 'memory');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

    const h = await page(b);
    await h.goto(BASE + 'home'); await h.locator('.place', {hasText: 'Memory'}).locator('small', {hasText: '3 on the server'}).waitFor({timeout: 5000}).catch(() => {});
    check(/3 on the server, 2\.6 KB/.test(await h.locator('.place', {hasText: 'Memory'}).textContent()), "Home: Memory's place shows its line");

    const ph = await page(b, 375, 760);
    await ph.goto(BASE + 'memory'); await ph.locator('.mem-shelf .mem-jar').first().waitFor({timeout: 5000}); await ph.waitForTimeout(300);
    check(await noOverflow(ph), '375 px: no sideways scrolling');
    check((await ph.locator('#mem-backup').boundingBox()).height >= 44, '375 px: the button keeps its 44 px');
    check(await ph.locator('.mem-facts dd').evaluateAll(ds => ds.every(d => d.scrollWidth <= d.clientWidth + 1)), '375 px: no number is cut off');
    await shot(ph, 'memory-375');
    check(ph.errors.length === 0, '375 px: no page errors ' + ph.errors.join(' | '));
  } finally {
    units(u => { delete u[BRAIN]; });              // the later checks see the fixtures as they were
    fs.rmSync(GUARD, {force: true});
  }
});
