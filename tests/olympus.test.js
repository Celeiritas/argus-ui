// Olympus playground: the Ω of twelve, every item does its thing, the trident resets it all; the summit fits on wide screens.
const {BASE, check, page, center, drag, noOverflow, shot, run} = require('./lib');
run(async b => {
  const p = await page(b);
  await p.goto(BASE + 'olympus?season=spring&sky=clear&night=0'); await p.waitForTimeout(1200);
  check(await p.locator('.omega .seat').count() === 12, 'all twelve Olympians are on the Ω');
  check(await p.locator('.omega .seat').nth(6).getAttribute('data-item') === 'bolt', 'Zeus sits at the top');
  check(await p.locator('.groups .beyond').count() === 2, 'Chthonic and Beyond Olympus are separate spots');
  check(!(await p.locator('details.lab').getAttribute('open')), 'scene controls start collapsed');
  const S = await p.evaluate(() => scene.surface()), n = sel => p.locator(sel).count();
  await drag(p, '[data-item=bident]', 600, S - 120); await p.waitForTimeout(1600);
  check(await n('.skel.up') === 1, "Hades' bident raises a skeleton");
  let [x, y] = await center(p.locator('.skel')); await drag(p, '[data-item=bolt]', x, y); await p.waitForTimeout(2300);
  check(await n('.skel') === 0 && await n('.mess[data-kind=ash]') === 1, "Zeus's bolt burns it to ash");
  await drag(p, '[data-item=bident]', 800, S - 120); await p.waitForTimeout(1500);
  [x, y] = await center(p.locator('.skel')); await drag(p, '[data-item=snake]', x, y); await p.waitForTimeout(700);
  check(await n('.skel.statue') === 1, "Medusa's snake turns the skeleton to stone");
  await drag(p, '[data-item=hammer]', x, y); await p.waitForTimeout(700);
  check(await n('.skel') === 0, 'the hammer smashes the stone skeleton');
  await drag(p, '[data-item=hammer]', 1000, S - 60); await p.waitForTimeout(800); await drag(p, '[data-item=hammer]', 1000, S - 60); await p.waitForTimeout(800);
  check(await p.locator('.hole').getAttribute('data-d') === '32', 'two hammer blows dig deeper in the same spot');
  const [dx, dy] = await center(p.locator('[data-item=seeds]'));
  await drag(p, '[data-item=seeds]', 0, 0, [[dx - 40, dy + 40], [dx - 120, dy + 110], [dx - 220, dy + 190], [dx - 320, dy + 260]]); await p.waitForTimeout(1600);
  check(await n('.flower') === 5, "Demeter's seeds sprout five flowers");
  const [ax, ay] = await center(p.locator('[data-item=bow]')); await drag(p, '[data-item=bow]', ax - 200, ay + 120); await p.waitForTimeout(1500);
  check(await n('.arrowstuck') === 1, "Apollo's arrow sticks where it lands");
  [x, y] = await center(p.locator('.tree').nth(1)); await drag(p, '[data-item=bolt]', x, y); await p.waitForTimeout(1200);
  check(await n('.tree.struck') === 1, 'the bolt strikes a tree');
  await shot(p, 'olympus-busy');
  await drag(p, '[data-item=trident]', 700, S - 200); await p.waitForTimeout(3200);
  const left = await p.evaluate(() => ['.skel', '.flower', '.hole', '.mess', '.arrowstuck', '.tree.struck', '.tree.statue'].map(s => document.querySelectorAll(s).length).reduce((a, c) => a + c, 0));
  check(left === 0, "Poseidon's tsunami resets the whole playground");
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  // wide screen: the summit is never cropped
  const uw = await page(b, 2560, 1080); await uw.goto(BASE + 'olympus'); await uw.waitForTimeout(1000);
  const top = await uw.evaluate(() => { const o = document.querySelector('.olympus'), m = o.getScreenCTM(); return [m.d * 84 + m.f, o.getBoundingClientRect().top]; });
  check(top[0] >= top[1] - 1, 'ultrawide: the temple on the summit is inside the picture');
  // phone: the dock leaves the ground reachable
  const ph = await page(b, 375, 760); await ph.goto(BASE + 'olympus'); await ph.waitForTimeout(1000);
  const dockBottom = await ph.evaluate(() => document.querySelector('.dock').getBoundingClientRect().bottom), surf = await ph.evaluate(() => scene.surface());
  check(surf - dockBottom > 150, `phone: open field below the dock (${Math.round(surf - dockBottom)}px)`);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  await shot(ph, 'olympus-phone');
});
