// Watch page (Argus's section, <base>/argus): task cards, trouble first, Zeus's bolt runs a task, Medusa pauses one, Argus raises
// the alarm, plain words on the buttons, 44 px controls, phone layout.
const {BASE, check, page, center, drag, noOverflow, shot, units, run} = require('./lib');
// every control a thumb can hit, smaller than 44 px either way
const small = p => p.evaluate(() => [...document.querySelectorAll('main a[href],main button,main summary,header button,header [role=link],nav a,.tabbar a,.tabbar button')]
  .filter(e => { const r = e.getBoundingClientRect(); return r.width && r.height && getComputedStyle(e).visibility !== 'hidden'; })
  .map(e => { const r = e.getBoundingClientRect(); return {t: (e.getAttribute('aria-label') || e.textContent).trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height)}; })
  .filter(x => x.w < 44 || x.h < 44));
run(async b => {
  const p = await page(b);
  await p.goto(BASE + 'argus'); await p.waitForTimeout(1000);
  check(await p.locator('.card').count() >= 5, 'task cards are shown');
  check(await p.locator('.title h1').textContent() === 'Watch' && /^Argus · /.test(await p.locator('#sub').textContent()) && /^Watch · /.test(await p.title()), 'the heading says Watch, with Argus under it');
  const h = await (await p.request.get(BASE + 'api/health')).json();
  check(h.ok === true && /^\d+\.\d+\.\d+$/.test(h.version) && h.uptime_s >= 0, 'api/health answers with the version and uptime');
  check(await p.locator('nav.chips a').count() >= 3, 'agent tabs are shown');
  check(await p.locator('#argus').evaluate(e => e.classList.contains('glare')), 'Argus glares: a fixture task has failed');
  check(!(await p.locator('#alarm').isHidden()), 'alarm badge is visible');
  // trouble first: the group with the failed task comes first, and in it the failed card
  const first = await p.locator('section.persona').first().getAttribute('aria-labelledby'), firstCard = p.locator('section.persona').first().locator('.card').first();
  check(first === 'h-hermes' && await firstCard.getAttribute('data-state') === 'failed', `trouble first: the failed task's group (${first}) and card come first`);
  const states = await p.locator('section.persona').first().locator('.card').evaluateAll(cs => cs.map(c => c.dataset.state));
  const rank = s => ({failed: 0, running: 1, ok: 2})[s] ?? 3;
  check(states.every((s, i) => !i || rank(states[i - 1]) <= rank(s)), `in a group: failed, then running, then ok (${states.join(', ')})`);
  // plain words: Pause / Resume, Run for a task that ends, Restart for an always-on one; "frozen", never "stone"
  check(await p.locator('.card[data-job="hermes-mail"] button[data-act="bolt"]').textContent() === 'Restart', 'an always-on task says Restart');
  check(await p.locator('.card[data-job="hermes-sort"] button[data-act="bolt"]').textContent() === 'Run' && await p.locator('.card[data-job="hermes-sort"] button[data-act="freeze"]').textContent() === 'Pause', 'a task that runs and ends says Run, and Pause');
  const gap = await p.locator('.card[data-job="hermes-sort"]').evaluate(c => c.querySelector('[data-act=bolt]').getBoundingClientRect().left - c.querySelector('[data-act=freeze]').getBoundingClientRect().right);
  check(gap >= 8, `Pause and Run stand apart (${Math.round(gap)} px)`);
  check(/Pause \/ resume/.test(await p.locator('#medusaHome .hint').textContent()) && /Medusa/.test(await p.locator('#medusaHome .hint small').textContent()), "Medusa's tool says Pause / resume, her name small");
  const sm = await small(p);
  check(sm.length === 0, 'every control is at least 44 by 44 px ' + JSON.stringify(sm));
  // bolt: drag a bolt from the medallion onto a task that is not running
  let [x, y] = await center(p.locator('.card[data-state="ok"]')); await drag(p, '#boltHome', x, y); await p.waitForTimeout(1800);
  check(/running now|restarted/.test(await p.locator('#toastText').textContent()), "Zeus's bolt runs the task");
  check(!(await p.locator('#bolt').evaluate(e => e.classList.contains('floating'))), 'the bolt medallion stays home');
  // Medusa: pause a task that can be paused and is not running
  [x, y] = await center(p.locator('.card[data-canfreeze="true"]:not([data-state="running"])')); await drag(p, '#medusaHome', x, y); await p.waitForTimeout(3000);
  check(/is paused \(frozen\)/.test(await p.locator('#toastText').textContent()), 'Medusa pauses (freezes) the task');
  await p.evaluate(() => refresh()); await p.waitForTimeout(600);
  const fz = p.locator('.card[data-state="frozen"]').first();
  check(await fz.locator('.pill').textContent() === 'frozen' && await fz.locator('button[data-act="thaw"]').textContent() === 'Resume' && /\d+ frozen/.test(await p.locator('.ph .counts').allTextContents().then(t => t.join(' '))), 'a paused card says frozen and offers Resume; the group counts it as frozen');
  await shot(p, 'watch');
  // a failed task whose state says why shows it in words
  await p.evaluate(() => { const j = S.jobs.find(j => j.state === 'failed') || S.jobs[0]; j.state = 'failed'; j.reason = 'could not reach the share'; render(); });
  check(/Why: could not reach the share/.test(await p.locator('.card[data-state="failed"] .why').first().textContent()), 'a failed card says why, when the server sends a reason');
  // all well: the alarm goes away
  units(u => Object.values(u).forEach(v => { if (v.Result !== 'success') v.Result = 'success'; }));
  await p.evaluate(() => refresh()); await p.waitForTimeout(800);
  check(!(await p.locator('#argus').evaluate(e => e.classList.contains('glare'))), 'Argus calms down when nothing has failed');
  check(await p.locator('#alarm').isHidden(), 'and the alarm badge goes away');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  for (const w of [360, 412]) {
    const ph = await page(b, w, 800); await ph.goto(BASE + 'argus'); await ph.waitForTimeout(800);
    check(await noOverflow(ph), `phone ${w}: no sideways scrolling`);
    const a = await ph.locator('.argus').boundingBox();
    check(a.height <= 100, `phone ${w}: Argus is about 96 px high (${Math.round(a.height)})`);
    check(await ph.locator('#boltHome .hint').isVisible() && await ph.locator('#medusaHome .hint').isVisible(), `phone ${w}: the two round tools have their words`);
    const psm = await small(ph);
    check(psm.length === 0, `phone ${w}: every control is at least 44 by 44 px ` + JSON.stringify(psm));
    if (w === 412) await shot(ph, 'watch-phone');
  }
});
