// Leafy Pads (docs/pads.md): the bundled pads plugin reads tests/fixtures/pads-sysfs/four (run.sh sets ARGUS_PADS_SYSROOT)
// with tests/fixtures/pads.json as the slot map. Four rows with the right words, Home's place, the empty state, phone width.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
run(async b => {
  const p = await page(b);
  const st = await (await p.request.get(BASE + 'api/state')).json();
  const pl = st.plugins.find(x => x.id === 'pads');
  check(pl && pl.kind === 'server' && pl.name === 'Pads' && !pl.agent, 'Pads is a server plugin with its own section');
  const log = fs.readFileSync(path.join(path.dirname(process.env.FIXTURES), 'server.log'), 'utf8');
  check(/loaded server plugin pads [\d.]+ \(bundled\)/.test(log), 'Pads: loaded from the bundled folder');
  const list = await (await p.request.get(BASE + 'api/pads/list')).json();
  check(list.ok && list.pads.length === 4 && list.connected === 3 && list.virtual === 1, 'api/pads/list: four pads, three real and one Steam virtual');
  const status = await (await p.request.get(BASE + 'api/pads/status')).json();
  check(status.line === '3 connected · 1 Steam virtual' && status.needs === false, 'api/pads/status: Home\'s line, never "needs you"');

  await p.goto(BASE + 'pads'); await p.locator('.pads .pad').first().waitFor({timeout: 5000});
  const rows = await p.locator('.pads .pad').evaluateAll(els => els.map(e => ({
    slot: e.querySelector('.slot').textContent.trim(), name: e.querySelector('.who b').textContent.trim(),
    mode: e.querySelector('.mode').textContent.replace('Mode: ', '').trim(), kind: e.querySelector('.kind').textContent.trim(),
    rumble: e.querySelector('.rumble').textContent.trim(), icons: e.querySelectorAll('svg.ico').length})));
  const want = [
    ['P1', 'Main pad', 'SInput', 'Real', 'Rumble works'],
    ['P2', 'Valve Software Steam Controller', 'Steam', 'Real', 'Rumble works'],
    ['Retro', 'GameCube pad', 'Unknown (2dc8:3019)', 'Real', 'No rumble'],
    ['No slot', 'Microsoft X-Box 360 pad 0', 'Xbox 360', 'Steam virtual', 'Rumble works'],
  ];
  check(rows.length === 4, `four rows (got ${rows.length})`);
  want.forEach((w, i) => { const r = rows[i] || {};
    check(r.slot === w[0] && r.name === w[1] && r.mode === w[2] && r.kind === w[3] && r.rumble === w[4],
      `row ${i + 1}: ${w.join(' · ')} (got ${[r.slot, r.name, r.mode, r.kind, r.rumble].join(' · ')})`); });
  check(rows.every(r => r.icons === 2), 'real/virtual and rumble each have an icon next to the word');
  check(/3 connected · 1 Steam virtual/.test(await p.locator('.padsum').textContent()), 'the summary line under the heading');
  check(await p.locator('.padnote', {hasText: 'Steam virtual:'}).count() === 1, 'a Steam virtual pad brings the one-line explanation');
  const btn = p.locator('.padcheck');
  check((await btn.boundingBox()).height >= 44 && await btn.textContent() === 'Check again', '"Check again": verb first, 44 px tall');
  await btn.focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
  check(await p.evaluate(() => document.activeElement && document.activeElement.classList.contains('padcheck')), 'keyboard: Enter re-reads and focus stays on the button');
  await shot(p, 'pads-desktop');

  // the empty state: swap the fixture's device list for a keyboard-only one; the plugin reads on every request
  const dev = path.join(process.env.FIXTURES, 'pads-sysfs', 'four', 'proc', 'bus', 'input', 'devices');
  const saved = fs.readFileSync(dev);
  try {
    fs.copyFileSync(path.join(process.env.FIXTURES, 'pads-sysfs', 'none', 'proc', 'bus', 'input', 'devices'), dev);
    await btn.click(); await p.locator('.pads .empty', {hasText: 'No pads connected'}).waitFor({timeout: 5000});
    check(/Test hint: press the Home button\./.test(await p.locator('.pads .empty').textContent()), 'empty state: "No pads connected" with the wake hint from pads.json');
    check((await (await p.request.get(BASE + 'api/pads/status')).json()).line === 'No pads connected', 'Home\'s line says so too');
  } finally { fs.writeFileSync(dev, saved); }

  await p.goto(BASE + 'home'); await p.waitForTimeout(800);
  const place = p.locator('.place', {hasText: 'Pads'});
  check(await place.count() === 1 && /3 connected · 1 Steam virtual/.test(await place.textContent()), 'Home: a Pads place with its line');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'pads'); await ph.locator('.pads .pad').first().waitFor({timeout: 5000});
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  const facts = await ph.locator('.pads .pad').first().evaluate(e => { const r = e.getBoundingClientRect(), f = e.querySelector('.facts').getBoundingClientRect(); return f.right <= r.right + 1 && f.left >= r.left - 1; });
  check(facts, 'phone: the mode, kind and rumble words wrap inside the row');
  await shot(ph, 'pads-phone');
});
