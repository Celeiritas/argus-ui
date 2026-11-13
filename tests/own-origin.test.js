// Its own address (docs/leafy-plugin.md "Its own address", 4.42.0): with own-origin.json the Spartamelee section is a large
// Open button and its links, no frame; the game runs in its own tab on its own origin, keeps its storage, and still cannot
// touch Elaia. Without the file the sandboxed frame stays (tests/plugins.test.js runs against tests/run.sh's server, which has none).
// This check starts its own Elaia from the built package: its own temporary HOME and files, ports picked free at run time.
const {check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path'), net = require('net'), http = require('http');
const {spawn} = require('child_process');

const T = path.dirname(process.env.FIXTURES);                 // tests/run.sh's temporary folder: the package is in T/pkg
const D = fs.mkdtempSync(path.join(T, 'own-origin-'));        // left there with run.sh's logs and screenshots
const HOME = path.join(D, 'home'), CONF = path.join(HOME, '.config', 'argus-ui'), FX = path.join(D, 'fx'), ST = path.join(D, 'state');
for (const d of [path.join(CONF, 'plugins'), FX, ST]) fs.mkdirSync(d, {recursive: true});
fs.cpSync(path.join(__dirname, 'plugin-fixtures'), path.join(CONF, 'plugins'), {recursive: true});
for (const f of ['fake_systemctl.py', 'fake_journal.sh', 'units.json']) fs.copyFileSync(path.join(__dirname, 'fixtures', f), path.join(FX, f));
for (const f of ['fake_systemctl.py', 'fake_journal.sh']) fs.chmodSync(path.join(FX, f), 0o755);
const PY = process.env.PYTHON || 'python3';
let SYSTEMCTL = path.join(FX, 'fake_systemctl.py');
if (process.platform === 'win32') {                           // Windows cannot run a .py file itself (as tests/gate_test.py)
  SYSTEMCTL = path.join(FX, 'systemctl.cmd');
  fs.writeFileSync(SYSTEMCTL, `@"${PY}" "${path.join(FX, 'fake_systemctl.py')}" %*\r\n`);
}

const freePort = () => new Promise((ok, no) => {
  const s = net.createServer(); s.on('error', no);
  s.listen(0, '127.0.0.1', () => { const {port} = s.address(); s.close(() => ok(port)); });
});
const answers = url => new Promise(ok => http.get(url, r => { r.resume(); ok(r.statusCode); }).on('error', () => ok(0)));
async function until(url, what) {
  let last;
  for (let i = 0; i < 150; i++) { if ((last = await answers(url)) === 200) return true; await new Promise(r => setTimeout(r, 100)); }
  throw new Error(`${what} did not start (last answer ${last}; log: ${path.join(D, 'server.log')})`);
}

run(async b => {
  const ports = [];
  while (ports.length < 3) { const n = await freePort(); if (!ports.includes(n)) ports.push(n); }
  const [MAIN, LOCAL, PUBLIC] = ports;
  const conf = path.join(CONF, 'own-origin.json');
  fs.writeFileSync(conf, JSON.stringify({spartamelee: {port: LOCAL, public: PUBLIC,
    links: [{name: 'Frame data', path: 'frames/'}, {name: 'Missing page', path: 'nope/'}]}}));
  const env = {...process.env, HOME, USERPROFILE: HOME, ARGUS_PORT: String(MAIN), ARGUS_OWN_ORIGIN: conf,
    ARGUS_STATIC: path.join(T, 'pkg', 'static'), ARGUS_BUNDLED: path.join(T, 'pkg', 'bundled'),
    ARGUS_SYSTEMCTL: SYSTEMCTL, ARGUS_JOURNALCTL: path.join(FX, 'fake_journal.sh'),
    ARGUS_DEV: '1', ARGUS_WATCH: '0', ARGUS_SUMMARY: '0', ARGUS_EVENTS: path.join(ST, 'events.jsonl'), ARGUS_WATCH_STATE: path.join(ST, 'watch.json')};
  for (const k of ['ARGUS_WEATHER', 'ARGUS_PEOPLE', 'ARGUS_BIND', 'ARGUS_ALLOWED_HOSTS']) delete env[k];
  if (process.getuid) env.ARGUS_SERVE_UID = String(process.getuid());   // as tests/run.sh: this runner counts as Serve
  const log = fs.openSync(path.join(D, 'server.log'), 'w');
  const srv = spawn(PY, [path.join(T, 'pkg', 'argus_ui.py')], {env, stdio: ['ignore', log, log]});
  try {
    const ELAIA = `http://127.0.0.1:${MAIN}/argus/`, OWN = `http://127.0.0.1:${LOCAL}/`;
    await until(ELAIA, 'Elaia'); await until(OWN, 'the own address');
    const p = await page(b);
    await p.goto(ELAIA + 'spartamelee'); await p.waitForTimeout(800);
    const open = p.locator('.plugin-own a.plugin-open');
    check(await open.count() === 1 && /^Open Spartamelee/.test(await open.textContent()), 'the section shows an "Open Spartamelee" button');
    check(await p.locator('#main iframe').count() === 0, 'and no frame');
    check(await open.getAttribute('href') === OWN, 'it points at the own address: this page\'s host name with the plugin\'s port (plain http: the local one)');
    check(await open.getAttribute('target') === '_blank' && /\bnoopener\b/.test(await open.getAttribute('rel') || ''), 'it opens a new tab, with no way back to this one');
    const bb = await open.boundingBox();
    check(bb.height >= 44 && bb.width >= 44, `a large target (${Math.round(bb.width)} x ${Math.round(bb.height)} px)`);
    const more = p.locator('.plugin-own nav.plugin-links a');
    check(await more.count() === 1 && (await more.textContent()).startsWith('Frame data') && await more.getAttribute('href') === OWN + 'frames/',
      'a "Frame data" link to frames/; a configured link with no page behind it is left out');
    await p.evaluate(() => refresh()); await p.waitForTimeout(400);
    check(await p.locator('.plugin-own a.plugin-open').count() === 1, 'the refresh keeps the section');
    let reached = false;
    for (let i = 0; i < 80 && !reached; i++) { await p.keyboard.press('Tab'); reached = await p.evaluate(() => !!document.activeElement?.classList.contains('plugin-open')); }
    check(reached, 'Tab reaches the Open button');
    check(await p.evaluate(() => getComputedStyle(document.activeElement).outlineStyle) !== 'none', 'and the focus shows on it');
    await shot(p, 'plugin-own');

    // Enter opens the game in a new tab, on its own origin
    const [game] = await Promise.all([p.context().waitForEvent('page'), p.keyboard.press('Enter')]);
    const errors = []; game.on('pageerror', e => errors.push(String(e)));
    await game.waitForLoadState(); await game.locator('#out', {hasText: 'ready'}).waitFor({timeout: 5000});
    check(game.url() === OWN, 'Enter opens the game at its own address');
    check(await game.evaluate(() => window.opener === null), 'the game has no handle on Elaia\'s tab');
    const out = game.locator('#out');
    check(await out.getAttribute('data-loaded') === 'from the plugin folder', 'the game loads its own module script and JSON from the root');
    check(await out.getAttribute('data-storage') === 'ok', 'it has storage of its own (the sandbox has none)');
    await game.reload(); await out.filter({hasText: 'ready'}).waitFor({timeout: 5000});
    check(await game.evaluate(() => localStorage.getItem('argus-test')) === 'kept', 'and keeps it across a reload');
    check(await out.getAttribute('data-freeze') !== '200' && await out.getAttribute('data-state') === 'blocked',
      'it has no API of its own address to use (no api/freeze, no api/state there)');

    // the game, on its own origin, tries Elaia's powers and state the ways a page could
    await game.goto(OWN + '?argus=' + encodeURIComponent(ELAIA)); await out.filter({hasText: 'ready'}).waitFor({timeout: 5000});
    check(await out.getAttribute('data-argus-post') !== '200', 'a JSON POST to Elaia\'s api/freeze from the game\'s origin fails');
    check(await out.getAttribute('data-argus-state') === 'blocked', 'it cannot read Elaia\'s api/state');
    const st = await (await p.request.get(ELAIA + 'api/state')).json();
    check(st.jobs.find(j => j.job === 'hermes-sort')?.state !== 'frozen', 'and the task it tried to freeze is untouched');
    check(errors.length === 0, 'the game page had no errors' + (errors.length ? ': ' + errors.join('; ') : ''));

    // its extra page, from Elaia's link, in its own tab
    const [frames] = await Promise.all([p.context().waitForEvent('page'), more.click()]);
    await frames.waitForLoadState();
    check(frames.url() === OWN + 'frames/' && await frames.locator('#frames').textContent() === 'Frame data', 'the Frame data link opens frames/ at the own address');
    await frames.locator('a', {hasText: 'Back to the game'}).click(); await frames.waitForLoadState();
    check(frames.url() === OWN, 'and its relative link leads back to the game');
    await game.close(); await frames.close();

    // phone width
    await p.setViewportSize({width: 375, height: 760}); await p.waitForTimeout(300);
    const pb = await open.boundingBox();
    check(await noOverflow(p) && pb.x >= 0 && pb.x + pb.width <= 375, 'at 375 px the section fits, button included');
    await shot(p, 'plugin-own-phone');
    check(p.errors.length === 0, 'Elaia\'s page had no errors' + (p.errors.length ? ': ' + p.errors.join('; ') : ''));
  } finally { srv.kill(); fs.closeSync(log); }
});
