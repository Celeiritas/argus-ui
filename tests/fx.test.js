// The shared effects (web/js/fx.js) and hold to confirm (web/js/hold.js), docs/fx.md: each effect plays and cleans up after
// itself, reduced motion skips it; a hold sends only when held to the end (pointer, Space/Enter, or two clicks from a screen reader).
// The hold is driven through tests/plugin-fixtures/demo-server, so it also checks that a server plugin gets both (api.fx, api.holdConfirm).
const {BASE, check, page, center, run} = require('./lib');
run(async b => {
  const p = await page(b);
  await p.goto(BASE); await p.waitForTimeout(800);
  const fxCount = () => p.evaluate(() => document.querySelectorAll('#fx > *').length);
  const before = await fxCount();
  let r = await p.evaluate(async () => { const done = fx.burst([200, 200], {n: 12}); const during = document.querySelectorAll('#fx > .p').length; await done; return during; });
  check(r >= 12 && await fxCount() === before, `a burst draws its pieces (${r}) and removes them when it has played`);
  r = await p.evaluate(async () => { const done = fx.motes([100, 300], [600, 300], {n: 10}); const during = document.querySelectorAll('#fx > .p').length; await done; return during; });
  check(r >= 10 && await fxCount() === before, 'motes swirl from one place to another and are gone after');
  r = await p.evaluate(async () => { const c = document.querySelector('.card'); const done = fx.glint(c); const during = document.querySelectorAll('#fx > .p').length; await done; return [during, !!c.isConnected]; });
  check(r[0] >= 1 && r[1] && await fxCount() === before, 'a glint sweeps once across a card and leaves it as it was');
  r = await p.evaluate(async () => { const c = document.querySelector('.card'); const done = fx.pieces(c, {cols: 3, rows: 2}); const during = document.querySelectorAll('#fx > .p').length; await done; return [during, !!c.isConnected]; });
  check(r[0] >= 6 && r[1] && await fxCount() === before, 'pieces fall away from a card; the card itself stays (the caller decides)');
  check(await p.evaluate(() => typeof particle === 'function' && typeof boltFx === 'function' && ROCK.length === 3), 'the old helpers still answer to their names (powers.js and olympus.js use them)');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  // ---- hold to confirm, in a server plugin's page
  await p.goto(BASE + 'demo-server'); await p.locator('#demo-hold').waitFor();
  check(await p.locator('.plugin-body').getAttribute('data-fx') === 'burst motes glint pieces bolt', 'a server plugin gets the shared effects as api.fx');
  const btn = p.locator('#demo-hold'), held = p.locator('#demo-held'), [x, y] = await center(btn);
  check(/hold 3 seconds/.test(await btn.getAttribute('aria-label')) && await btn.locator('.hold-label').textContent() === 'Send held echo', 'the button keeps its label and says it must be held');
  check((await btn.boundingBox()).height >= 44, 'it keeps a 44 px hit area');

  const wide = (await btn.boundingBox()).width;
  await p.mouse.move(x, y); await p.mouse.down(); await p.waitForTimeout(1200);
  check(Math.abs((await btn.boundingBox()).width - wide) < 1, 'while held the button keeps its width (it must not shrink out from under the finger)');
  check(/^Hold… [12]$/.test(await btn.locator('.hold-label').textContent()) && await btn.evaluate(e => +getComputedStyle(e).getPropertyValue('--p') > .2), 'while held: the ring fills and the label counts down');
  if (process.env.SHOTS) await btn.screenshot({path: require('path').join(process.env.SHOTS, 'hold.png')});
  check(await p.locator('#argus').evaluate(e => e.classList.contains('wide')), 'while held: Argus opens his eyes wide');
  await p.mouse.up(); await p.waitForTimeout(300);
  check(await held.textContent() === '' && /Let go early: nothing was sent/.test(await p.locator('#toastText').textContent()), 'let go early: nothing is sent, and the page says so');
  check(await btn.locator('.hold-label').textContent() === 'Send held echo', 'the label comes back');
  check(!await p.locator('#argus').evaluate(e => e.classList.contains('wide')), 'let go: his eyes go back to normal');

  await p.mouse.down(); await p.mouse.move(x, y - 200); await p.waitForTimeout(3300); await p.mouse.up();
  check(await held.textContent() === '', 'sliding off the button cancels the hold');
  await p.evaluate(() => { window.moved = []; const a = Element.prototype.animate; Element.prototype.animate = function (k, o) { if (this.id) moved.push(this.id); return a.call(this, k, o); }; });
  await p.mouse.move(x, y); await p.mouse.down(); await p.waitForTimeout(3300); await p.mouse.up();
  await held.filter({hasText: 'held echo 1: held'}).waitFor({timeout: 3000});
  check(true, 'held for 3 seconds: it sends, once');
  const moved = await p.evaluate(() => moved);
  const hero = await p.locator('#hero').evaluate(e => !e.hidden && e.offsetWidth > 0);   // a plugin with an icon shows its medallion
  check(moved.includes('argus') && moved.includes('hero') === hero && await p.locator('.plugin-body').evaluate(e => e.dataset.argus) === 'function', `it worked: Argus nods, with the section's medallion if it has one (moved: ${moved.join(', ')}); plugins get api.argus`);

  await btn.focus(); await p.keyboard.down('Enter'); await p.waitForTimeout(600); await p.keyboard.up('Enter'); await p.waitForTimeout(200);
  check(await held.textContent() === 'held echo 1: held', 'keyboard: a short Enter sends nothing');
  await p.keyboard.down(' '); await p.waitForTimeout(3300); await p.keyboard.up(' ');
  await held.filter({hasText: 'held echo 2'}).waitFor({timeout: 3000});
  check(true, 'keyboard: Space held for 3 seconds sends');

  await btn.evaluate(e => e.click()); await p.waitForTimeout(200);       // a screen reader's click: no press behind it
  check(/^Click again to send held echo$/.test(await btn.locator('.hold-label').textContent()) && await held.textContent() === 'held echo 2: held', 'a click that cannot be held arms the button and sends nothing');
  await btn.evaluate(e => e.click());
  await held.filter({hasText: 'held echo 3'}).waitFor({timeout: 3000});
  check(true, 'a second click within 5 seconds confirms');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  // ---- reduced motion: no particles, no ring; the hold still works by its words
  const q = await page(b); await q.emulateMedia({reducedMotion: 'reduce'});
  await q.goto(BASE); await q.waitForTimeout(800);
  r = await q.evaluate(async () => { const t = performance.now(); await fx.burst([200, 200]); await fx.motes([0, 0], [300, 300]); await fx.pieces(document.querySelector('.card'));
    return [document.querySelectorAll('#fx > .p').length, performance.now() - t]; });
  check(r[0] === 0 && r[1] < 100, 'reduced motion: burst, motes and pieces draw nothing and finish at once');
  await q.goto(BASE + 'demo-server'); const qb = q.locator('#demo-hold'); await qb.waitFor();
  check(await qb.locator('.hold-ring').evaluate(e => getComputedStyle(e).display) === 'none', 'reduced motion: no ring');
  const [qx, qy] = await center(qb); await q.mouse.move(qx, qy); await q.mouse.down(); await q.waitForTimeout(1200);
  check(/^Hold… [12]$/.test(await qb.locator('.hold-label').textContent()), 'reduced motion: the countdown words still show');
  await q.waitForTimeout(2100); await q.mouse.up();
  await q.locator('#demo-held', {hasText: 'held echo 1'}).waitFor({timeout: 3000});
  check(true, 'reduced motion: holding still sends');
  check(!await q.evaluate(() => document.getElementById('argus').getAnimations().length), 'reduced motion: Argus does not nod');
  check(q.errors.length === 0, 'no page errors ' + q.errors.join(' | '));
});
