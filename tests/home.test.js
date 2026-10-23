// Home (docs/home.md): a pill on every page, one tile per section with its line, alerts first, keyboard and phone.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const AL = path.join(path.dirname(process.env.FIXTURES), 'home/.local/state/argus-ui/alerts');
run(async b => {
  const p = await page(b);
  await p.goto(BASE); await p.waitForTimeout(600);
  const pill = p.locator('#realms a.realm', {hasText: 'Home'});
  check(await pill.count() === 1 && await p.locator('#realms a.realm').first().textContent() === 'HomeOverview', 'the Home pill comes first in the section bar');
  check(await p.locator('.card').count() >= 5, 'Watch is still the default page');
  await pill.click(); await p.waitForURL(/\/home$/);
  check(await pill.getAttribute('aria-current') === 'page' && await p.locator('.title h1').textContent() === 'Home', 'Home is its own section, marked current');
  check(await p.locator('body.side').count() === 1, 'it is a side page (Argus in the corner)');
  const tile = name => p.locator('.tile', {has: p.locator('.tname b', {hasText: name})});
  for (const n of ['Argus', 'Mentor', 'Olympus', 'Spartamelee', 'Demo Server']) check(await tile(n).count() === 1, `a tile for ${n}`);
  check(/1 task failed/.test(await tile('Argus').locator('.tline').textContent()) && await tile('Argus').evaluate(e => e.classList.contains('needs')), 'Watch\'s tile says a task failed and stands out');
  await tile('Demo Server').locator('.tline', {hasText: '1 ping answered · all well'}).waitFor({timeout: 5000});
  check(true, 'a server plugin\'s tile shows its api/<id>/status line');
  check(/due|to learn|waiting|Nothing due/.test(await tile('Mentor').locator('.tline').textContent()), 'Mentor\'s tile shows what is due');
  check(/Version 0\.0\.1-test/.test(await tile('Spartamelee').textContent()), 'a static plugin\'s tile shows its version');
  check(await p.locator('.home-alerts').count() === 0, 'no alerts box when nothing is up');
  check((await tile('Olympus').boundingBox()).height >= 44, 'tiles keep a 44 px hit area');

  fs.mkdirSync(AL, {recursive: true});
  fs.writeFileSync(path.join(AL, 'zeus.json'), JSON.stringify({job: 'zeus-approve', level: 'alert', message: 'Janus could not verify the approval; the request is held', link: 'demo-server'}));
  await p.evaluate(() => refresh()); await p.waitForTimeout(600);
  const box = p.locator('.home-alerts');
  check(/Janus could not verify/.test(await box.textContent()) && await box.locator('a').textContent() === 'Open Demo Server', 'an alert shows first, with its link');
  check(/1 alert/.test(await tile('Argus').locator('.tline').textContent()), 'and Watch\'s tile counts it');
  await shot(p, 'home');
  fs.rmSync(path.join(AL, 'zeus.json'), {force: true});

  await tile('Olympus').focus(); await p.evaluate(() => refresh()); await p.waitForTimeout(500);
  check(await p.evaluate(() => document.activeElement?.getAttribute('href')?.endsWith('olympus')), 'the refresh keeps keyboard focus on the tile');
  await p.keyboard.press('Enter'); await p.waitForURL(/\/olympus$/);
  check(true, 'Enter on a tile opens its section');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'home'); await ph.waitForTimeout(800);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
});
