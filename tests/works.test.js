// "Works, not just runs" (docs/checks.md): the server's watch loop (one-second rounds here) reads checks.json from the throwaway HOME,
// finds a container that holds a dead copy of its drive, and the page says so on a card; when the container is good again the card goes.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const T = path.dirname(process.env.FIXTURES), HOME = path.join(T, 'home'), FX = process.env.FIXTURES, POD = path.join(T, 'pod');
const CHECKS = path.join(HOME, '.config/argus-ui/checks.json'), EVENTS = process.env.ARGUS_EVENTS;   // tests/run.sh sets it, outside HOME
if (!EVENTS) throw new Error('ARGUS_EVENTS is not set (tests/run.sh sets it)');
const mi = name => fs.copyFileSync(path.join(FX, 'watch', name + '.mountinfo'), path.join(POD, 'jellyfin.mountinfo'));
const card = p => p.locator('.card.alert-only', {hasText: 'Running, but not working'});
// a failure counts after 2 one-second rounds in a row (docs/checks.md): ask the page again until the card count is what we wait for
const until = async (p, n) => { for (let i = 0; i < 20; i++) { await p.evaluate(() => refresh()); await p.waitForTimeout(500); if (await card(p).count() === n) return; } };
run(async b => {
  fs.mkdirSync(POD, {recursive: true}); mi('container-dead-shutdown'); fs.writeFileSync(path.join(POD, 'jellyfin.readable'), '/media/a.mp4\n');
  const p = await page(b); await p.goto(BASE); await p.waitForFunction(() => typeof refresh === 'function', null, {timeout: 15000}).catch(() => {}); await p.waitForTimeout(500); console.log('  (page errors: ' + p.errors.join(' | ') + ')');
  check(await card(p).count() === 0, 'no checks file: no works card');
  fs.mkdirSync(path.dirname(CHECKS), {recursive: true});
  fs.writeFileSync(CHECKS, JSON.stringify({checks: [{id: 'jellyfin', title: 'Jellyfin', job: 'mnemosyne-jellyfin', mount: '/mnt/media',
    container: {name: 'jellyfin', file: '/media/a.mp4', runtime: [process.env.PYTHON || 'python3', path.join(FX, 'fake_podman.py')]},
    fix: {restart: ['jellyfin']}}]}));
  try {
    await until(p, 1);
    check(await card(p).count() === 1, 'a container with a dead copy of its drive gets a card');
    const txt = await card(p).textContent();
    check(/Running, but not working: cannot read its drive/.test(txt), 'the card says it plainly: ' + txt.replace(/\s+/g, ' ').trim());
    check(await p.locator('#argus').evaluate(e => e.classList.contains('glare')), 'Argus glares');
    shot(p, 'works');
    const ev = fs.readFileSync(EVENTS, 'utf8').trim().split('\n').map(JSON.parse);
    check(ev.length === 1 && ev[0].kind === 'needs-yes' && ev[0].title === 'Jellyfin runs, but cannot read its drive', 'one needs-yes event, in plain words (' + ev.length + ' event)');
    const ph = await page(b, 375, 760); await ph.goto(BASE); await ph.waitForTimeout(800);
    check(await noOverflow(ph), 'phone: no sideways scrolling with the card');
    mi('container-good');                                              // the container was started again
    await until(p, 0);
    check(await card(p).count() === 0, 'when the container reads its drive again the card goes');
    await p.waitForTimeout(1500);                                      // a few more rounds: still one event each
    const ev2 = fs.readFileSync(EVENTS, 'utf8').trim().split('\n').map(JSON.parse);
    check(ev2.length === 2 && ev2[1].kind === 'recovered', 'and one recovered event is added');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  } finally { fs.rmSync(CHECKS, {force: true}); }
});
