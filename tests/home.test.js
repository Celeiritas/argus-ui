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
  const task = p.locator('.need[data-key^="task-"]');           // one row per broken thing (4.40.0): what, since, what Argus did, what you can do
  const t1 = (await p.locator('.need').first().textContent()).replace(/\s+/g, ' ');
  check(/rename failed/.test(t1) && await p.locator('.need').first().locator('a.go').textContent() === 'Look at it on Watch', 'the failed thing comes first, with "Look at it on Watch": ' + t1);
  check(/Argus: Does not restart a failed task by himself\./.test(t1) && /You: Read its log on its card, then press Run to try again\./.test(t1), 'in plain words: what Argus did and what you can do');
  check(/\/argus\/argus$/.test(await task.first().locator('a.go').getAttribute('href')), 'and the button goes to Watch');
  check(await need('deploy waiting').locator('a.go').textContent() === 'Review app 9.9.9' && /Approvals · Zeus/.test(await need('deploy waiting').textContent()), 'a section that needs you: its line, its plain name, its verb-first button');
  const place = t => p.locator('.place', {hasText: t});
  for (const t of ['Spartamelee', 'Demo Server']) check(await place(t).count() === 1, `a card for ${t}`);
  // one place for each fact (4.44.0): Watch (a failed task), Approvals (a deploy) and Heracles (workouts) have rows above, so no card
  await p.waitForFunction(() => !/Checking…|Asking every section/.test(document.querySelector('#main .home').textContent));
  const listed = await p.evaluate(() => [...document.querySelectorAll('.needlist .need .go')].map(a => a.getAttribute('href').replace(/.*\//, '')));
  check(await place('Study').count() === 1, 'Study (nothing due) keeps its card');
  for (const [t, id] of [['Watch', 'argus'], ['Approvals', 'throne'], ['Heracles', 'heracles']])
    check(listed.includes(id) && await place(t).count() === 0, `${t} has a row above (${listed.join(', ')}), so it has no card under Sections`);
  check(await place('Playground').count() === 1 && await place('Playground').locator('.pl').textContent() === 'Powers, weather, seasons'
    && /\/olympus$/.test(await place('Playground').getAttribute('href')), 'a card for the Playground, with what it is');
  await place('Demo Server').locator('.pl', {hasText: '1 ping answered · all well'}).waitFor({timeout: 5000});
  check(true, "a server plugin's card shows its status line");
  check(await need('Demo Server').count() === 0, 'a plugin whose status does not say "needs" stays out of the list');
  check(/Version 0\.0\.1-test/.test(await place('Spartamelee').textContent()), "a static plugin's card shows its version");
  const order = await p.locator('.placelist .place .pw b').allTextContents(), inBar = await p.evaluate(() => sections().map(e => e.word));
  check(order.length >= 3 && order.every((t, i) => !i || inBar.indexOf(order[i - 1]) < inBar.indexOf(t)), `cards in the bar's order (${order.join(', ')})`);
  const hits = await p.locator('#main a').evaluateAll(as => as.map(a => a.getBoundingClientRect()).filter(r => r.width && (r.height < 44 || r.width < 44)).length);
  check(hits === 0, 'every link on Today is at least 44 by 44 px');

  // the Open row: links to other pages on this machine (~/.config/argus-ui/links.json), after the rows; unsafe hrefs dropped
  const LK = path.join(path.dirname(process.env.FIXTURES), 'home/.config/argus-ui/links.json');
  fs.mkdirSync(path.dirname(LK), {recursive: true});
  fs.writeFileSync(LK, JSON.stringify([{name: 'Sound Lab', what: 'Studio', href: '/studio-test/'}, {name: 'Bad', what: 'x', href: 'javascript:alert(1)'}]));
  await p.evaluate(() => refresh()); await p.waitForTimeout(700);
  const lk = p.locator('#moreAway a.srow');
  check(await lk.count() === 1 && await lk.getAttribute('href') === '/studio-test/' && /Sound Lab/.test(await lk.textContent()) && await p.locator('#realms a.realm.link').count() === 0 && await p.locator('#realmMore').isVisible(),
    'a link from links.json sits in More under Other pages, not as a pill of its own (4.44.0); an unsafe href is dropped');
  const op = p.locator('.open .openlink');
  check(await op.count() === 1 && await op.getAttribute('href') === '/studio-test/' && /Sound Lab\s*Studio/.test(await op.textContent()), 'and on Today in the Open row');
  const ys = await p.evaluate(() => ['.needs', '.open', '.places'].map(s => document.querySelector('.home ' + s).getBoundingClientRect()));
  check(ys[1].top >= ys[0].top && ys[2].top >= ys[1].bottom - 1, 'Today reads in order: the state and its rows, Open, then the sections');
  fs.unlinkSync(LK); await p.evaluate(() => refresh()); await p.locator('.home .open').waitFor({state: 'detached', timeout: 3000}).catch(() => {});
  check(await p.locator('#moreAway .srow').count() === 0 && await p.locator('.home .open').count() === 0, 'no links file, no links and no Open row');

  // the media players (4.44.0): their addresses come from ~/.config/argus-ui/media.json on the host, never from the repository
  const MD = path.join(path.dirname(process.env.FIXTURES), 'home/.config/argus-ui/media.json');
  fs.writeFileSync(MD, JSON.stringify({audiobookshelf: 'http://books.example:13378/', jellyfin: 'https://films.example/web/', qbittorrent: 'https://x.example/', Bad: 'javascript:alert(1)'}));
  await p.evaluate(() => refresh()); await p.locator('.home .open .openlink').first().waitFor({timeout: 3000}).catch(() => {});
  const md = await p.locator('.home .open .openlink').evaluateAll(as => as.map(a => [a.textContent.replace(/\s+/g, ' ').trim(), a.getAttribute('href'), a.getAttribute('rel'), a.getAttribute('target')]));
  check(JSON.stringify(md) === JSON.stringify([['JellyfinFilms and shows', 'https://films.example/web/', 'noopener noreferrer', null], ['AudiobookshelfAudiobooks and podcasts', 'http://books.example:13378/', 'noopener noreferrer', null]]),
    'Open: a row for Jellyfin and one for Audiobookshelf from media.json, plain links with rel="noopener noreferrer"; other keys and unsafe addresses dropped ' + JSON.stringify(md));
  fs.unlinkSync(MD); await p.evaluate(() => refresh()); await p.locator('.home .open').waitFor({state: 'detached', timeout: 3000}).catch(() => {});
  check(await p.locator('.home .open').count() === 0, 'no media.json, no rows for the players');

  // one line on what the server is doing now (4.44.0), only from what it knows: a timer's run in progress, the game guard's record
  const now = () => p.locator('.home .needs p.now').textContent().then(t => t.trim(), () => '');
  check(await now() === 'The server: busy: Hermes media' && await p.locator('.home .quiet').count() === 0, `under the state, the server's line says what runs now ("${await now()}")`);
  const RM_ = path.join(path.dirname(process.env.FIXTURES), 'home/.config/leafy/realm.json'), GG = path.join(path.dirname(process.env.FIXTURES), 'home/.local/state/medusa-gameguard/frozen-by-me.json');
  fs.mkdirSync(path.dirname(RM_), {recursive: true}); fs.mkdirSync(path.dirname(GG), {recursive: true});
  fs.writeFileSync(RM_, JSON.stringify({SERVER: 'Shelf'})); fs.writeFileSync(GG, JSON.stringify(['mnemosyne-ollama']));
  await p.evaluate(() => refresh()); await p.locator('.home p.now', {hasText: 'game'}).waitFor({timeout: 3000}).catch(() => {});
  check(await now() === 'Shelf: a game is running, the local AI is paused; busy: Hermes media', `with a game on, it says so, by the name in realm.json ("${await now()}")`);
  fs.unlinkSync(RM_); fs.unlinkSync(GG); await p.evaluate(() => refresh()); await p.locator('.home p.now', {hasText: 'The server'}).waitFor({timeout: 3000}).catch(() => {});
  check(await now() === 'The server: busy: Hermes media', 'the game over, the line is back');

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
    const bar = [...document.querySelectorAll('#realms .realm:not(.over) .dot, #realmMore:not([hidden]) .dot')].reduce((t, d) => t + (parseInt(d.textContent, 10) || 1), 0); return [line, bar]; });   // a folded pill's count is in More's
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
  const back = await p.locator('.placelist .place .pw b').allTextContents();
  check(back.slice(0, 3).join(' ') === 'Watch Study Approvals', `with their rows gone, Watch, Study and Approvals have their cards again, first, in the bar's order (${back.slice(0, 4).join(', ')})`);
  check(/^All \d+ tasks well$/.test(await place('Watch').locator('.pl').textContent()), "Watch's card says all is well");
  // a learner whose one section has a row above: nothing under Sections, so no Sections heading either
  await p.route('**/api/mentor/status', r => r.fulfill({json: {line: '3 due', needs: true, action: 'Study 10 minutes'}}));
  await p.evaluate(() => { S.role = 'learner'; render(); }); await p.locator('.need', {hasText: '3 due'}).waitFor({timeout: 3000}).catch(() => {});
  check(await need('3 due').count() === 1 && await p.locator('#places-h').count() === 0 && await p.locator('.home .places').count() === 0,
    'a learner with Study in the list: no empty Sections heading');
  check(await p.locator('.home p.now').count() === 0 && await p.locator('.home .open').count() === 0, "and no server line and no Open row: those are the owner's");
  await p.unroute('**/api/mentor/status'); await p.route('**/api/mentor/status', r => r.fulfill({json: {line: 'Nothing due', needs: false, action: ''}}));
  await p.evaluate(() => home.show()); await p.locator('#places-h').waitFor({timeout: 3000}).catch(() => {});
  check(await p.locator('#places-h').count() === 1 && await place('Study').count() === 1 && await p.locator('.placelist .place').count() === 1, 'and with nothing due, Study is her one card under Sections');
  await p.unroute('**/api/mentor/status'); await p.evaluate(() => { delete S.role; render(); });
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
