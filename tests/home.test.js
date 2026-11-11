// Today (docs/home.md): what needs *you*, and what Elaia opens on. One line with the state in words, the rows that need you
// (the failed thing first, verb-first buttons), the "Open" links, then one one-line card per section (status v2). A met need
// fades out. /home still works. Keyboard, focus across redraws, phone.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const AL = path.join(path.dirname(process.env.FIXTURES), 'home/.local/state/argus-ui/alerts');
run(async b => {
  const p = await page(b);
  await p.goto(BASE); await p.waitForTimeout(800);
  const pill = p.locator('#realms a.realm').first();
  check(await pill.textContent() === 'Today' && await pill.getAttribute('aria-current') === 'page', 'Elaia opens on Today, the first place in the bar');
  check(await p.locator('.card').count() === 0 && await p.locator('.home').count() === 1, 'the bare address is Today, not Watch');
  check(await p.locator('.title h1').textContent() === 'Elaia' && await p.title() === 'Today · Elaia', 'the page is called Elaia');
  check(/^Good (morning|afternoon|evening|night) · (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)/.test(await p.locator('#sub').textContent()), 'under the name: a greeting by the time of day, and the date');
  await p.locator('#sub', {hasText: 'Light rain'}).waitFor({timeout: 3000}).catch(() => {});
  check(/· Light rain · 48°F$/.test(await p.locator('#sub').textContent()), 'and the weather, even when it arrives after the page is drawn');
  check(await p.locator('body.side').count() === 1, 'it is a side page (Argus in the corner)');
  const man = await (await p.request.get(BASE + 'manifest.webmanifest')).json();
  check(man.name === 'Elaia' && man.short_name === 'Elaia' && man.display === 'standalone' && man.start_url === './' && man.scope === './', 'installed from the browser, the app is called Elaia and opens on Today');

  const need = t => p.locator('.need', {hasText: t});
  await need('deploy waiting').waitFor({timeout: 5000});
  const n = await p.locator('.needlist .need').count();
  check((await p.locator('#needs-h').textContent()).trim() === `${n} things need you`, `one line says the state in words ("${(await p.locator('#needs-h').textContent()).trim()}")`);
  const task = p.locator('.need[data-key^="task-"]');           // one row per broken thing (4.39.0): what, since, what Argus did, what you can do
  const t1 = (await p.locator('.need').first().textContent()).replace(/\s+/g, ' ');
  check(/rename failed/.test(t1) && await p.locator('.need').first().locator('a.go').textContent() === 'Look at it on Watch', 'the failed thing comes first, with "Look at it on Watch": ' + t1);
  check(/Argus: Argus does not restart a failed task by himself\./.test(t1) && /You: Read its log on its card, then press Run to try again\./.test(t1), 'in plain words: what Argus did and what you can do');
  check(/\/argus\/argus$/.test(await task.first().locator('a.go').getAttribute('href')), 'and the button goes to Watch');
  check(await need('deploy waiting').locator('a.go').textContent() === 'Review app 9.9.9' && /Approvals · Zeus/.test(await need('deploy waiting').textContent()), 'a section that needs you: its line, its plain name, its verb-first button');
  const place = t => p.locator('.place', {hasText: t});
  for (const t of ['Watch', 'Study', 'Approvals', 'Spartamelee', 'Demo Server']) check(await place(t).count() === 1, `a card for ${t}`);
  check(await place('Playground').count() === 0, 'no card for the playground (it has no news); it is in the bar');
  await place('Demo Server').locator('.pl', {hasText: '1 ping answered · all well'}).waitFor({timeout: 5000});
  check(true, "a server plugin's card shows its status line");
  check(await need('Demo Server').count() === 0, 'a plugin whose status does not say "needs" stays out of the list');
  check(/due|to learn|waiting|Nothing due/.test(await place('Study').locator('.pl').textContent()), "Study's card shows what is due");
  check(/Version 0\.0\.1-test/.test(await place('Spartamelee').textContent()), "a static plugin's card shows its version");
  const order = await p.locator('.placelist .place .pw b').allTextContents();
  check(order[0] === 'Watch' && order[1] === 'Study' && order[2] === 'Approvals', `cards in the bar's order (${order.slice(0, 4).join(', ')})`);
  const hits = await p.locator('#main a').evaluateAll(as => as.map(a => a.getBoundingClientRect()).filter(r => r.width && (r.height < 44 || r.width < 44)).length);
  check(hits === 0, 'every link on Today is at least 44 by 44 px');

  // the Open row: links to other pages on this machine (~/.config/argus-ui/links.json), after the rows; unsafe hrefs dropped
  const LK = path.join(path.dirname(process.env.FIXTURES), 'home/.config/argus-ui/links.json');
  fs.mkdirSync(path.dirname(LK), {recursive: true});
  fs.writeFileSync(LK, JSON.stringify([{name: 'Sound Lab', what: 'Studio', href: '/studio-test/'}, {name: 'Bad', what: 'x', href: 'javascript:alert(1)'}]));
  await p.evaluate(() => refresh()); await p.waitForTimeout(700);
  const lk = p.locator('#realms a.realm.link');
  check(await lk.count() === 1 && await lk.getAttribute('href') === '/studio-test/' && /Sound Lab/.test(await lk.textContent()), 'a link from links.json sits in the section bar; an unsafe href is dropped');
  const op = p.locator('.open .openlink');
  check(await op.count() === 1 && await op.getAttribute('href') === '/studio-test/' && /Sound Lab\s*Studio/.test(await op.textContent()), 'and on Today in the Open row');
  const ys = await p.evaluate(() => ['.needs', '.open', '.places'].map(s => document.querySelector('.home ' + s).getBoundingClientRect()));
  check(ys[1].top >= ys[0].top && ys[2].top >= ys[1].bottom - 1, 'Today reads in order: the state and its rows, Open, then the sections');
  fs.unlinkSync(LK); await p.evaluate(() => refresh()); await p.locator('.home .open').waitFor({state: 'detached', timeout: 3000}).catch(() => {});
  check(await p.locator('#realms a.realm.link').count() === 0 && await p.locator('.home .open').count() === 0, 'no links file, no links and no Open row');

  fs.mkdirSync(AL, {recursive: true});
  fs.writeFileSync(path.join(AL, 'zeus.json'), JSON.stringify({job: 'zeus-approve', level: 'alert', message: 'Janus could not verify the approval; the request is held', link: 'demo-server'}));
  await p.evaluate(() => refresh()); await p.waitForTimeout(700);
  const al = need('Janus could not verify');
  check(await al.count() === 1 && await al.locator('a.go').textContent() === 'Open Demo Server' && /rename failed/.test(await p.locator('.need').first().textContent()), 'an alert gets a row, with its link as the button, after the failed task');
  check(/^Zeus · Watch/.test(await al.locator('small').textContent()), 'an alert row says who in plain words (Zeus · Watch)');
  fs.writeFileSync(path.join(AL, 'hermes.json'), JSON.stringify({job: 'hermes-sort', level: 'alert', message: 'A delivery waits in quarantine'}));
  await p.evaluate(() => refresh()); await need('waits in quarantine').waitFor({timeout: 5000}).catch(() => {});
  const hl = need('waits in quarantine');
  check(/^Hermes · Watch/.test(await hl.locator('small').textContent()) && await hl.locator('a.go').textContent() === 'Look at Hermes on Watch' && /\/argus\/hermes$/.test(await hl.locator('a.go').getAttribute('href')), 'an alert without a link opens Watch showing that agent\'s tasks');
  // one number: the line counts what the bar counts (every task in trouble, every alert, each section that needs you)
  const sums = async () => p.evaluate(() => { drawNav(); const line = parseInt(document.getElementById('needs-h').textContent, 10);
    const bar = [...document.querySelectorAll('#realms .realm .dot')].reduce((t, d) => t + (parseInt(d.textContent, 10) || 1), 0); return [line, bar]; });
  let [line, bar] = await sums();
  check(line === bar && line >= 4, `the line on Today equals the sum of the counts on the bar (${line} = ${bar})`);
  await p.evaluate(() => { S.jobs.forEach((j, i) => { if (i < 3) j.state = 'failed'; }); home.show(); }); await p.waitForTimeout(300);
  [line, bar] = await sums();
  const nf = await p.evaluate(() => S.jobs.filter(j => j.state === 'failed').length);
  check(nf >= 3 && line === bar && await task.count() === nf, `with ${nf} failed tasks too, one row each, each counted (${line} = ${bar})`);
  fs.rmSync(path.join(AL, 'hermes.json'), {force: true}); await p.evaluate(() => refresh()); await p.waitForTimeout(700);
  await shot(p, 'home');
  // a met need fades out where it stood, then is gone
  fs.rmSync(path.join(AL, 'zeus.json'), {force: true});
  await p.evaluate(() => refresh());
  const leaving = await p.waitForFunction(() => { const li = document.querySelector('.need.leaving'); return li && /Janus/.test(li.textContent) && li.getAttribute('aria-hidden') === 'true'; }, null, {timeout: 2000}).then(() => true, () => false);
  check(leaving, 'a met need leaves with a short fade (hidden from screen readers while it goes)');
  await p.waitForTimeout(400);
  check(await need('Janus could not verify').count() === 0, 'and is gone after it');

  // when Needs you empties, Argus gives a slow, contented blink
  await p.evaluate(() => askStatus());   // let any question already on its way come back first
  await p.route('**/api/*/status', r => r.fulfill({json: {line: 'All quiet', needs: false, action: ''}}));   // every section (Heracles, Mentor and the Throne say "needs" in the fixtures)
  await p.evaluate(() => { S.alerts = []; S.jobs.forEach(j => { if (j.state === 'failed') j.state = 'running'; }); home.show(); });
  const content = await p.waitForFunction(() => document.getElementById('argus').classList.contains('content'), null, {timeout: 2000}).then(() => true, () => false);
  await p.locator('#needs-h', {hasText: 'Nothing needs you'}).waitFor({timeout: 2000});
  check(content, 'Needs you emptied: "Nothing needs you", and Argus gives a slow, contented blink');
  await p.waitForTimeout(900); await p.evaluate(() => home.show()); await p.waitForTimeout(300);
  check(!await p.locator('#argus').evaluate(e => e.classList.contains('content')), 'a redraw while it stays empty does not blink again');
  await p.unroute('**/api/*/status'); await p.evaluate(() => refresh()); await p.waitForTimeout(700);
  check(await task.count() === 1, 'the next refresh shows the failed task again');

  await place('Spartamelee').focus(); await p.evaluate(() => refresh()); await p.waitForTimeout(500);
  check(await p.evaluate(() => document.activeElement?.getAttribute('href')?.endsWith('spartamelee')), 'the refresh keeps keyboard focus');
  await p.keyboard.press('Enter'); await p.waitForURL(/\/spartamelee$/);
  check(true, 'Enter on a card opens its section');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  const old = await page(b); await old.goto(BASE + 'home'); await old.waitForTimeout(600);
  check(await old.locator('.home').count() === 1 && await old.locator('#realms a.realm').first().getAttribute('aria-current') === 'page', 'the old address <base>/home still opens Today');

  const ph = await page(b, 375, 760); await ph.goto(BASE); await ph.waitForTimeout(800);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  await shot(ph, 'home-phone');
});
