// Leafy Controllers (docs/controllers.md): the bundled controllers plugin reads tests/fixtures/controllers-sysfs/four (run.sh sets
// ARGUS_CONTROLLERS_SYSROOT) with tests/fixtures/controllers.json as the slot map. Four rows with the right words, Home's place,
// the empty state, a slot map that cannot be read, phone width. And what is left of the old name (the section was called Pads
// until 4.33.0): an old bookmark to <base>/pads lands here; nothing else of it is read since 4.49.0 (tests/controllers_test.py).
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
  check(!('notice' in list) && !('pads' in list), 'api/controllers/list: no old-name notice any more (4.49.0)');
  const status = await (await p.request.get(BASE + 'api/controllers/status')).json();
  check(status.line === '3 connected · 1 Steam virtual' && status.needs === false, 'api/controllers/status: Home\'s line, never "needs you"');

  await p.goto(BASE + 'controllers'); await p.locator('.controllers .controller').first().waitFor({timeout: 5000});
  check(await p.locator('.title h1').textContent() === 'Daedalus' && await p.locator('#sub').textContent() === 'Build · controllers, console', 'the page heading is its god\'s name, Daedalus (4.48.0), and under it what he does');
  check(await p.locator('a.realm[aria-current="page"] b').textContent() === 'Daedalus', 'the sections bar marks Daedalus (Controllers) as the open section');
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

  // the old address: the server answers <base>/pads with a redirect for now (302) that browsers do not remember
  const moved = await p.request.get(BASE + 'pads', {maxRedirects: 0});
  check(moved.status() === 302 && moved.headers()['location'] === 'controllers' && moved.headers()['cache-control'] === 'no-store',
    `old address <base>/pads: 302 to controllers, not cached (got ${moved.status()} ${moved.headers()['location']})`);
  const oldApi = await p.request.get(BASE + 'api/pads/list', {maxRedirects: 0});
  check(oldApi.status() === 404, `api/pads is an unknown address since 4.49.0 (got ${oldApi.status()})`);
  await p.goto(BASE + 'pads'); await p.locator('.controllers .controller').first().waitFor({timeout: 5000});
  check(new URL(p.url()).pathname === new URL(BASE).pathname + 'controllers' && await p.locator('.controllers .controller').count() === 4,
    `an old bookmark to <base>/pads opens the Controllers section (landed on ${new URL(p.url()).pathname})`);

  // a slot map that cannot be read: the list's answer names the file, and the page lists the controllers with No slot under it.
  // The server under test has a good slot map, so this answer is made here (no second trip to the server).
  const broken = {...list, controllers: list.controllers.map(c => ({...c, slot: '', label: ''})), problem: 'controllers.json could not be read (JSONDecodeError)'};
  const withProblem = route => route.fulfill({json: broken});
  await p.route('**/api/controllers/list', withProblem);
  await p.locator('.ctrlcheck').click(); await p.locator('.ctrlnote[role="status"]').waitFor({timeout: 5000});
  check(await p.locator('.ctrlnote[role="status"]').textContent() === 'controllers.json could not be read (JSONDecodeError). Slots are not shown until it is fixed.',
    'a slot map that cannot be read: what is wrong, a full stop, then what follows from it');
  check(await p.locator('.controllers .controller').count() === 4 && await p.locator('.controllers .slot.none').count() === 4, 'the controllers are still listed under it, each with No slot');
  await p.unroute('**/api/controllers/list', withProblem);
  const ph = await page(b, 375, 760);

  await p.goto(BASE + 'home');
  const place = p.locator('.place[data-id="controllers"]');
  await place.filter({hasText: 'connected'}).waitFor({timeout: 5000}).catch(() => {});       /* the line comes with a second request: wait for it, the check below says what is wrong */
  check(await place.count() === 1 && /3 connected\s· 1 Steam virtual/.test(await place.textContent()), 'Home: the Controllers place (called Daedalus since 4.48.0) with its line');
  check(await place.getAttribute('href') === new URL(BASE).pathname + 'controllers' && await p.locator('.place', {hasText: /\bPads\b/}).count() === 0,
    'Home: the place opens <base>/controllers and none is called Pads');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  await ph.goto(BASE + 'controllers'); await ph.locator('.controllers .controller').first().waitFor({timeout: 5000});
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  const facts = await ph.locator('.controllers .controller').first().evaluate(e => { const r = e.getBoundingClientRect(), f = e.querySelector('.facts').getBoundingClientRect(); return f.right <= r.right + 1 && f.left >= r.left - 1; });
  check(facts, 'phone: the mode, kind and rumble words wrap inside the row');
  check(ph.errors.length === 0, 'phone: no page errors ' + ph.errors.join(' | '));
  await shot(ph, 'controllers-phone');
});
