// Leafy Controllers (docs/controllers.md): the bundled controllers plugin reads tests/fixtures/controllers-sysfs/four (run.sh sets
// ARGUS_CONTROLLERS_SYSROOT) with tests/fixtures/controllers.json as the slot map. Four rows with the right words, Home's place,
// the empty state, phone width. And what is left of the old name (the section was called Pads until 4.33.0): the old address
// <base>/pads lands here, and the page says so while an old name is still in use (the server side: tests/controllers_test.py).
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
run(async b => {
  const p = await page(b);
  const st = await (await p.request.get(BASE + 'api/state')).json();
  const pl = st.plugins.find(x => x.id === 'controllers');
  check(pl && pl.kind === 'server' && pl.name === 'Controllers' && !pl.agent, 'Controllers is a server plugin with its own section');
  check(!st.plugins.some(x => x.id === 'pads' || x.name === 'Pads'), 'no section is called Pads any more');
  const log = fs.readFileSync(path.join(path.dirname(process.env.FIXTURES), 'server.log'), 'utf8');
  check(/loaded server plugin controllers [\d.]+ \(bundled\)/.test(log), 'Controllers: loaded from the bundled folder');
  const list = await (await p.request.get(BASE + 'api/controllers/list')).json();
  check(list.ok && list.controllers.length === 4 && list.connected === 3 && list.virtual === 1, 'api/controllers/list: four controllers, three real and one Steam virtual');
  check(list.notice === '' && !('pads' in list), 'api/controllers/list: new names in use, so no old-name notice');
  const status = await (await p.request.get(BASE + 'api/controllers/status')).json();
  check(status.line === '3 connected · 1 Steam virtual' && status.needs === false, 'api/controllers/status: Home\'s line, never "needs you"');

  await p.goto(BASE + 'controllers'); await p.locator('.controllers .controller').first().waitFor({timeout: 5000});
  check(await p.locator('.title h1').textContent() === 'Controllers', 'the page heading says Controllers');
  check(await p.locator('a.realm[aria-current="page"] b').textContent() === 'Controllers', 'the sections bar marks Controllers as the open section');
  const rows = await p.locator('.controllers .controller').evaluateAll(els => els.map(e => ({
    slot: e.querySelector('.slot').textContent.trim(), name: e.querySelector('.who b').textContent.trim(),
    mode: e.querySelector('.mode').textContent.replace('Mode: ', '').trim(), kind: e.querySelector('.kind').textContent.trim(),
    rumble: e.querySelector('.rumble').textContent.trim(), icons: e.querySelectorAll('svg.ico').length})));
  const want = [
    ['P1', 'Main controller', 'SInput', 'Real', 'Rumble works'],
    ['P2', 'Valve Software Steam Controller', 'Steam', 'Real', 'Rumble works'],
    ['Retro', 'GameCube controller', 'Unknown (2dc8:3019)', 'Real', 'No rumble'],
    ['No slot', 'Microsoft X-Box 360 pad 0', 'Xbox 360', 'Steam virtual', 'Rumble works'],
  ];
  check(rows.length === 4, `four rows (got ${rows.length})`);
  want.forEach((w, i) => { const r = rows[i] || {};
    check(r.slot === w[0] && r.name === w[1] && r.mode === w[2] && r.kind === w[3] && r.rumble === w[4],
      `row ${i + 1}: ${w.join(' · ')} (got ${[r.slot, r.name, r.mode, r.kind, r.rumble].join(' · ')})`); });
  check(rows.every(r => r.icons === 2), 'real/virtual and rumble each have an icon next to the word');
  check(/3 connected · 1 Steam virtual/.test(await p.locator('.ctrlsum').textContent()), 'the summary line under the heading');
  check(await p.locator('.ctrlnote', {hasText: 'Steam virtual:'}).count() === 1, 'a Steam virtual controller brings the one-line explanation');
  // "pad" is left only inside the name the kernel gives Steam's copy ("Microsoft X-Box 360 pad 0"): a Pad is a synth sound
  const words = (await p.locator('.plugin-server').innerText()).replace(/Microsoft X-Box 360 pad \d+/g, '');
  check(/Controllers on this machine/.test(words) && !/\bpads?\b/i.test(words), 'the section says controller everywhere, never pad');
  check(await p.locator('.ctrlnote.oldname').count() === 0, 'no old-name notice on the page while only new names are in use');
  const btn = p.locator('.ctrlcheck');
  check((await btn.boundingBox()).height >= 44 && await btn.textContent() === 'Check again', '"Check again": verb first, 44 px tall');
  await btn.focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
  check(await p.evaluate(() => document.activeElement && document.activeElement.classList.contains('ctrlcheck')), 'keyboard: Enter re-reads and focus stays on the button');
  await shot(p, 'controllers-desktop');

  // the empty state: swap the fixture's device list for a keyboard-only one; the plugin reads on every request
  const dev = path.join(process.env.FIXTURES, 'controllers-sysfs', 'four', 'proc', 'bus', 'input', 'devices');
  const saved = fs.readFileSync(dev);
  try {
    fs.copyFileSync(path.join(process.env.FIXTURES, 'controllers-sysfs', 'none', 'proc', 'bus', 'input', 'devices'), dev);
    await btn.click(); await p.locator('.controllers .empty', {hasText: 'No controllers connected'}).waitFor({timeout: 5000});
    check(/Test hint: press the Home button\./.test(await p.locator('.controllers .empty').textContent()), 'empty state: "No controllers connected" with the wake hint from controllers.json');
    check((await (await p.request.get(BASE + 'api/controllers/status')).json()).line === 'No controllers connected', 'Home\'s line says so too');
  } finally { fs.writeFileSync(dev, saved); }

  // the old address (one release): the server answers <base>/pads with a redirect that browsers do not remember
  const moved = await p.request.get(BASE + 'pads', {maxRedirects: 0});
  check(moved.status() === 301 && moved.headers()['location'] === 'controllers' && moved.headers()['cache-control'] === 'no-store',
    `old address <base>/pads: 301 to controllers, not cached (got ${moved.status()} ${moved.headers()['location']})`);
  check((await p.request.get(BASE + 'api/pads/list', {maxRedirects: 0})).status() === 404, 'api/pads is gone: the page asks api/controllers');
  await p.goto(BASE + 'pads'); await p.locator('.controllers .controller').first().waitFor({timeout: 5000});
  check(new URL(p.url()).pathname === new URL(BASE).pathname + 'controllers' && await p.locator('.controllers .controller').count() === 4,
    `an old bookmark to <base>/pads opens the Controllers section (landed on ${new URL(p.url()).pathname})`);

  // an old name still in use (pads.json, ARGUS_PADS, ARGUS_PADS_SYSROOT): the list's answer carries a notice and the page shows it.
  // The server under test runs on new names, so the answer gets the longest notice added on its way to the page.
  const notice = 'Old names still in use: ARGUS_PADS_SYSROOT (now ARGUS_CONTROLLERS_SYSROOT), ARGUS_PADS (now ARGUS_CONTROLLERS), pads.json (now controllers.json). This is the last release that reads old names.';
  const withNotice = async route => { const r = await route.fetch(), j = await r.json(); await route.fulfill({response: r, json: {...j, notice: notice + ' <i>x</i>'}}); };
  await p.route('**/api/controllers/list', withNotice);
  await p.locator('.ctrlcheck').click(); await p.locator('.ctrlnote.oldname').waitFor({timeout: 5000});
  const note = p.locator('.ctrlnote.oldname');
  check((await note.textContent()).startsWith(notice) && await note.getAttribute('role') === 'status', 'old names in use: the page says which, and what each is called now');
  check(await note.locator('i').count() === 0 && /<i>x<\/i>/.test(await note.textContent()), 'the notice is shown as text, never as markup');
  check(await p.locator('.controllers .controller').count() === 4, 'the controllers are still listed under the notice');
  await shot(p, 'controllers-old-name-desktop');

  const ph = await page(b, 375, 760);
  await ph.route('**/api/controllers/list', withNotice);
  await ph.goto(BASE + 'controllers'); await ph.locator('.ctrlnote.oldname').waitFor({timeout: 5000});
  check(await noOverflow(ph), 'phone: the old-name notice wraps, no sideways scrolling');
  await shot(ph, 'controllers-old-name-phone');
  await ph.unroute('**/api/controllers/list', withNotice); await p.unroute('**/api/controllers/list', withNotice);

  await p.goto(BASE + 'home'); await p.waitForTimeout(800);
  const place = p.locator('.place', {hasText: 'Controllers'});
  check(await place.count() === 1 && /3 connected · 1 Steam virtual/.test(await place.textContent()), 'Home: a Controllers place with its line');
  check(await place.getAttribute('href') === new URL(BASE).pathname + 'controllers' && await p.locator('.place', {hasText: /\bPads\b/}).count() === 0,
    'Home: the place opens <base>/controllers and none is called Pads');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  await ph.goto(BASE + 'controllers'); await ph.locator('.controllers .controller').first().waitFor({timeout: 5000});
  check(await ph.locator('.ctrlnote.oldname').count() === 0 && await noOverflow(ph), 'phone: no sideways scrolling');
  const facts = await ph.locator('.controllers .controller').first().evaluate(e => { const r = e.getBoundingClientRect(), f = e.querySelector('.facts').getBoundingClientRect(); return f.right <= r.right + 1 && f.left >= r.left - 1; });
  check(facts, 'phone: the mode, kind and rumble words wrap inside the row');
  check(ph.errors.length === 0, 'phone: no page errors ' + ph.errors.join(' | '));
  await shot(ph, 'controllers-phone');
});
