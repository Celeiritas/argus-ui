// Desktop / Game mode (docs/modes.md): the pill beneath the server on Today when modes.json sets it up
// (tests/run.sh points ARGUS_MODES at tests/fixtures/modes.json: fake-desktop-shell, fake-game-session, fake-to-desktop,
// fake-to-game). The current mode is lit in its colour; holding the other one starts its switch unit (the fake systemctl
// writes each start to starts.log); when the fake units flip, the pill follows; when the switch unit fails, the note says so
// (the fake turns InactiveEnterTimestampMonotonic "now" into the monotonic clock). The server side (the file, the probe, every
// answer of POST api/mode, a learner's 403 and her state without modes) is tests/modes_test.py.
const fs = require('fs'), path = require('path');
const {BASE, check, page, noOverflow, units, run} = require('./lib');
const STARTS = path.join(process.env.FIXTURES, 'starts.log');
const started = () => { try { return fs.readFileSync(STARTS, 'utf8').split(/\r?\n/).filter(Boolean); } catch (e) { return []; } };
// the four fake units: the desktop shell, the game session, and the two switch units
const set = (desk, game, toDesk = 'inactive', toGame = 'inactive') => units(u => {
  u['fake-desktop-shell'].ActiveState = desk; u['fake-game-session'].ActiveState = game;
  u['fake-to-desktop'].ActiveState = toDesk; u['fake-to-game'].ActiveState = toGame;
});
const pill = p => p.evaluate(() => {
  const box = document.getElementById('modes'), r = box.getBoundingClientRect(), segs = [...box.querySelectorAll('.mode-seg')];
  return {shown: !box.hidden && r.height > 0, label: box.getAttribute('aria-label'), role: box.getAttribute('role'), top: r.top, bottom: r.bottom,
          inHeader: !!box.closest('header'), note: document.getElementById('modeNote').textContent,
          segs: segs.map(s => ({tag: s.tagName, text: s.textContent.trim(), mode: s.dataset.mode, on: s.classList.contains('on'), disabled: !!s.disabled,
                                bg: getComputedStyle(s).backgroundColor, ink: getComputedStyle(s).color, w: s.getBoundingClientRect().width,
                                h: s.getBoundingClientRect().height, right: s.getBoundingClientRect().right}))};
});
const lit = async (p, id, ms = 12000) => p.waitForFunction(id => {
  const on = document.querySelector('#modePill .mode-seg.on'); return on && on.dataset.mode === id && !document.getElementById('modeNote').textContent;
}, id, {timeout: ms}).then(() => true, () => false);
async function holdPointer(p, loc, ms = 3400) {
  const bb = await loc.boundingBox(); await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await p.mouse.down(); await p.waitForTimeout(ms); await p.mouse.up();
}
const newStarts = async (before, ms = 6000) => { const t = Date.now(); while (Date.now() - t < ms) { if (started().length > before) break; await new Promise(r => setTimeout(r, 100)); } return started().slice(before); };

run(async b => {
  let saved; units(u => { saved = JSON.stringify(u); });           // given back at the end, for the checks after this one
  set('active', 'inactive');
  const state = await (await (await b.newContext()).request.get(BASE + 'api/state')).json();
  check(state.modes && state.modes.current === 'desktop' && !JSON.stringify(state.modes).includes('fake-'), `the state carries the mode, ids and labels only: ${JSON.stringify(state.modes)}`);
  const name = state.modes && state.modes.name;

  // ---- the pill: at the top, Desktop lit in green, Game a hold button ----
  const p = await page(b, 1440, 900);
  await p.goto(BASE); await p.waitForSelector('#modes:not([hidden])', {timeout: 8000}).catch(() => {});
  let s = await pill(p);
  check(s.shown && !s.inHeader && await p.locator('.home-server #modes').count() === 1, 'the pill belongs to the server on Today, outside the header');
  check(await p.evaluate(() => document.querySelector('#modes').getBoundingClientRect().top >= document.querySelector('.home-server .now').getBoundingClientRect().bottom), 'the pill sits below the server status');
  check(s.role === 'group' && s.label === `${name} mode`, `a group named "${s.label}"`);
  check(s.segs.length === 2 && s.segs[0].mode === 'desktop' && s.segs[1].mode === 'game', 'two halves, in the order of the file');
  check(s.segs[0].on && s.segs[0].tag === 'SPAN' && s.segs[0].text === 'Desktop (current)' && s.segs[0].bg === 'rgb(40, 112, 67)' && s.segs[0].ink === 'rgb(255, 255, 255)',
    `Desktop is lit in green and read out as current (${s.segs[0].text}, ${s.segs[0].bg})`);
  check(s.segs[1].tag === 'BUTTON' && !s.segs[1].on && s.segs[1].text === 'Game' && !s.segs[1].disabled, 'Game is a button');
  check(await p.locator('#modePill button[data-mode-to=game]').getAttribute('aria-label') === 'Switch to Game (hold 3 seconds to confirm)',
    'a verb-first name, press and hold to confirm (holdConfirm)');
  const g = p.locator('#modePill button[data-mode-to=game]');
  await g.evaluate(b => b.click());                                  // a screen reader's click: no press behind it, so it arms the button
  check(await g.locator('.hold-label').textContent() === 'Click again to switch to Game', `armed, verb first: "${await g.locator('.hold-label').textContent()}"`);
  check(s.segs.every(x => x.h >= 44 && x.w >= 44), `44 px hit areas (${s.segs.map(x => `${Math.round(x.w)}x${Math.round(x.h)}`).join(', ')})`);
  for (const at of ['argus', 'olympus', 'mentor', 'memory', 'phone']) {
    await p.goto(BASE + at); await p.waitForTimeout(500);
    const t = await pill(p); check(!t.shown && !t.inHeader, `the pill takes no space on ${at}`);
  }
  await p.goto(BASE); await p.waitForSelector('#modes:not([hidden])', {timeout: 8000}).catch(() => {});

  // ---- a refusal: its words in the toast, nothing started ----
  let before = started().length;
  await p.route('**/api/mode', r => r.fulfill({status: 409, json: {ok: false, msg: 'Box is already switching to Game mode.'}}));
  await holdPointer(p, p.locator('#modePill button[data-mode-to=game]'));
  // wait for the refusal's toast itself: a fixed 300 ms lost the race on a slow CI runner (run 45572287870, empty toast)
  await p.waitForFunction(() => document.querySelector('#toastText')?.textContent, null, {timeout: 6000}).catch(() => {});
  check(await p.locator('#toastText').textContent() === 'Box is already switching to Game mode.', `a refusal says why in the toast: "${await p.locator('#toastText').textContent()}"`);
  check(started().length === before && (await pill(p)).segs[0].on, 'and nothing changes');
  await p.unroute('**/api/mode');

  // ---- hold Game: the fake systemctl starts the switch unit, the pill says it is switching ----
  before = started().length;
  await holdPointer(p, p.locator('#modePill button[data-mode-to=game]'));
  const st = await newStarts(before);
  check(st.length === 1 && st[0] === 'start --no-block fake-to-game.service', `holding Game starts its switch unit, without waiting (${JSON.stringify(st)})`);
  await p.waitForFunction(() => /Switching to Game…/.test(document.getElementById('modeNote').textContent), null, {timeout: 4000}).catch(() => {});
  s = await pill(p);
  check(s.note === 'Switching to Game…' && s.segs.every(x => x.tag === 'SPAN' || x.disabled) && await p.locator('#modePill button:not([disabled])').count() === 0,
    `while it switches: "${s.note}", nothing to press`);
  check(/Switching to Game mode\. The TV goes dark/.test(await p.locator('#toastText').textContent()), 'the toast says what happens');
  check(await p.evaluate(() => getComputedStyle(document.getElementById('modeNote'), '::before').animationName) === 'mode-busy', 'a small dot pulses');
  const leaving = await p.evaluate(() => { const c = getComputedStyle(document.querySelector('#modePill .mode-seg.on')); return {op: c.opacity, edge: c.borderTopStyle}; });
  check(leaving.op === '1' && leaving.edge === 'dashed', `the mode it leaves keeps its full colour and contrast, with a dashed edge (opacity ${leaving.op}, ${leaving.edge})`);

  // ---- the fake units flip: the pill follows, without a reload ----
  set('inactive', 'active');
  check(await lit(p, 'game'), 'the switch is done: Game is lit');
  s = await pill(p);
  check(s.segs[1].on && s.segs[1].bg === 'rgb(40, 112, 67)' && s.segs[1].text === 'Game (current)' && s.segs[0].tag === 'BUTTON' && !s.segs[0].disabled,
    `Game in green (${s.segs[1].bg}), Desktop now the button`);

  // ---- the keyboard: hold Space on Desktop ----
  before = started().length;
  await p.locator('#modePill button[data-mode-to=desktop]').focus();
  check(await p.evaluate(() => getComputedStyle(document.activeElement).outlineStyle !== 'none'), 'the focused half shows its focus');
  await p.keyboard.down('Space'); await p.waitForTimeout(3400); await p.keyboard.up('Space');
  const kt = await newStarts(before);
  check(kt.length === 1 && kt[0] === 'start --no-block fake-to-desktop.service', `holding Space starts the other switch (${JSON.stringify(kt)})`);
  check(await p.waitForFunction(() => document.activeElement && document.activeElement.id === 'modes', null, {timeout: 4000}).then(() => true, () => false),
    'the pill is drawn again as switching: the keyboard stays on it (the group), not lost to the page');
  set('active', 'inactive');
  check(await lit(p, 'desktop'), 'and back in Desktop');
  check(await p.evaluate(() => !!document.activeElement.closest('#modes')), 'still on the pill when the switch is done');

  // ---- a switch that fails: the note and the toast say so at once, and Game can be pressed again ----
  before = started().length;
  await holdPointer(p, p.locator('#modePill button[data-mode-to=game]'));
  check((await newStarts(before)).length === 1, 'holding Game starts its switch unit');
  await p.waitForTimeout(300);                                       // the fake systemctl has saved its own change first
  units(u => { u['fake-to-game'].ActiveState = 'failed'; u['fake-to-game'].InactiveEnterTimestampMonotonic = 'now'; });   // and it fails
  const said = await p.waitForFunction(() => document.getElementById('modeNote').textContent === "Couldn't switch to Game", null, {timeout: 10000}).then(() => true, () => false);
  s = await pill(p);
  check(said && s.segs[0].on && s.segs[1].tag === 'BUTTON' && !s.segs[1].disabled, `a failed switch: "${s.note}", Desktop still lit, Game can be pressed again`);
  check(/couldn't switch to Game mode\. Try again, or check the TV\.$/.test(await p.locator('#toastText').textContent()), `the toast says so: "${await p.locator('#toastText').textContent()}"`);
  check(await p.evaluate(() => getComputedStyle(document.getElementById('modeNote'), '::before').animationName) === 'none', 'its dot stays still');
  units(u => { u['fake-to-game'] = {ActiveState: 'inactive'}; });

  // ---- unknown: muted words, no buttons ----
  set('inactive', 'inactive'); await p.waitForTimeout(2200); await p.evaluate(() => refresh()); await p.waitForTimeout(400);
  s = await pill(p);
  check(s.segs.length === 1 && s.segs[0].text === 'Mode unknown' && await p.locator('#modePill button').count() === 0, `neither runs: "${s.segs.map(x => x.text)}", nothing to press`);

  // ---- a phone: no sideways scroll, the pill on the screen; reduced motion: the dot stays still ----
  set('active', 'inactive');
  const ph = await page(b, 375, 812); await ph.emulateMedia({reducedMotion: 'reduce'});
  await ph.goto(BASE); await ph.waitForSelector('#modes:not([hidden])', {timeout: 8000}).catch(() => {});
  s = await pill(ph);
  check(s.shown && s.segs.every(x => x.right <= 375) && await noOverflow(ph), `375 px: the pill fits and nothing scrolls sideways (right edge ${Math.round(Math.max(...s.segs.map(x => x.right)))})`);
  await ph.evaluate(() => { S.modes = {...S.modes, switching: 'game'}; drawModes(); });
  check(await ph.evaluate(() => getComputedStyle(document.getElementById('modeNote'), '::before').animationName) === 'none', 'reduced motion: the switching dot stays still');
  check(p.errors.length === 0 && ph.errors.length === 0, `no page errors ${JSON.stringify(p.errors.concat(ph.errors))}`);

  fs.writeFileSync(path.join(process.env.FIXTURES, 'units.json'), saved);
});
