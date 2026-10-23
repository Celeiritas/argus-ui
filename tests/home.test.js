// Home (docs/home.md): what needs *you*. A greeting, a "Needs you" list (alerts, failed tasks, sections that need you)
// with verb-first buttons, then the places with their one line. Keyboard, focus across redraws, phone.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const AL = path.join(path.dirname(process.env.FIXTURES), 'home/.local/state/argus-ui/alerts');
run(async b => {
  const p = await page(b);
  await p.goto(BASE); await p.waitForTimeout(600);
  const pill = p.locator('#realms a.realm', {hasText: 'Home'});
  check(await pill.count() === 1 && await p.locator('#realms a.realm').first().textContent() === 'HomeOverview', 'the Home pill comes first in the section bar');
  check(await p.locator('.card').count() >= 5, 'Watch is still the default page');
  await pill.click(); await p.waitForURL(/\/home$/); await p.waitForTimeout(800);
  check(await pill.getAttribute('aria-current') === 'page' && /^Good (morning|afternoon|evening|night)$/.test(await p.locator('.title h1').textContent()), 'Home greets you by the time of day');
  check(/(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)/.test(await p.locator('#sub').textContent()), 'and gives the date (and the weather when there is some)');
  check(await p.locator('.card').count() === 0 && await p.locator('.tile').count() === 0, 'Home is not a grid of cards: that is Watch');
  check(await p.locator('body.side').count() === 1, 'it is a side page (Argus in the corner)');

  const need = t => p.locator('.need', {hasText: t});
  check(await need('task failed').count() === 1 && await need('task failed').locator('a.go').textContent() === 'Look at 1 failed task', 'Needs you: the failed task, with "Look at 1 failed task"');
  check(/\/argus\/$/.test(await need('task failed').locator('a.go').getAttribute('href')), 'and the button goes to Watch');
  check(/^Needs you\s*\d+$/.test((await p.locator('#needs-h').textContent()).trim()), 'the heading counts what needs you');
  const place = t => p.locator('.place', {hasText: t});
  for (const n of ['Watch', 'Mentor', 'Olympus', 'Spartamelee', 'Demo Server']) check(await place(n).count() === 1, `a place for ${n}`);
  await place('Demo Server').locator('small', {hasText: '1 ping answered · all well'}).waitFor({timeout: 5000});
  check(true, "a server plugin's place shows its status line");
  check(await need('Demo Server').count() === 0, 'a plugin whose status does not say "needs" stays out of the list');
  check(/due|to learn|waiting|Nothing due/.test(await place('Mentor').locator('small').textContent()), "Mentor's place shows what is due");
  check(/Version 0\.0\.1-test/.test(await place('Spartamelee').textContent()), "a static plugin's place shows its version");
  check((await place('Olympus').boundingBox()).height >= 44 && (await need('task failed').locator('a.go').boundingBox()).height >= 44, '44 px hit areas');
  const order = await p.locator('.placelist .place b').allTextContents();
  check(order[0] === 'Watch' && order[1] === 'Mentor' && order[2] === 'Olympus', 'places in the section bar\'s order: Watch, Mentor, Olympus, then plugins');

  fs.mkdirSync(AL, {recursive: true});
  fs.writeFileSync(path.join(AL, 'zeus.json'), JSON.stringify({job: 'zeus-approve', level: 'alert', message: 'Janus could not verify the approval; the request is held', link: 'demo-server'}));
  await p.evaluate(() => refresh()); await p.waitForTimeout(700);
  const first = p.locator('.need').first();
  check(/Janus could not verify/.test(await first.textContent()) && await first.locator('a.go').textContent() === 'Open Demo Server', 'an alert comes first, with its link as the button');
  await shot(p, 'home');
  fs.rmSync(path.join(AL, 'zeus.json'), {force: true});

  await place('Olympus').focus(); await p.evaluate(() => refresh()); await p.waitForTimeout(500);
  check(await p.evaluate(() => document.activeElement?.getAttribute('href')?.endsWith('olympus')), 'the refresh keeps keyboard focus');
  await p.keyboard.press('Enter'); await p.waitForURL(/\/olympus$/);
  check(true, 'Enter on a place opens its section');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'home'); await ph.waitForTimeout(800);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  await shot(ph, 'home-phone');
});
