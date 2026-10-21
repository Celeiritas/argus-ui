// Watch page: task cards, Zeus's bolt runs a task, Medusa freezes one, Argus raises the alarm, phone layout.
const {BASE, check, page, center, drag, noOverflow, shot, units, run} = require('./lib');
run(async b => {
  const p = await page(b);
  await p.goto(BASE); await p.waitForTimeout(1000);
  check(await p.locator('.card').count() >= 5, 'task cards are shown');
  const h = await (await p.request.get(BASE + 'api/health')).json();
  check(h.ok === true && /^\d+\.\d+\.\d+$/.test(h.version) && h.uptime_s >= 0, 'api/health answers with the version and uptime');
  check(await p.locator('nav a').count() >= 3, 'agent tabs are shown');
  check(await p.locator('#argus').evaluate(e => e.classList.contains('glare')), 'Argus glares: a fixture task has failed');
  check(!(await p.locator('#alarm').isHidden()), 'alarm badge is visible');
  // bolt: drag a bolt from the medallion onto a task that is not running
  let [x, y] = await center(p.locator('.card[data-state="ok"]')); await drag(p, '#boltHome', x, y); await p.waitForTimeout(1800);
  check(/running now|restarted/.test(await p.locator('#toastText').textContent()), "Zeus's bolt runs the task");
  check(!(await p.locator('#bolt').evaluate(e => e.classList.contains('floating'))), 'the bolt medallion stays home');
  // Medusa: freeze a task that can be frozen and is not running
  [x, y] = await center(p.locator('.card[data-canfreeze="true"]:not([data-state="running"])')); await drag(p, '#medusaHome', x, y); await p.waitForTimeout(3000);
  check(/is stone/.test(await p.locator('#toastText').textContent()), 'Medusa freezes the task');
  await shot(p, 'watch');
  // all well: the alarm goes away
  units(u => Object.values(u).forEach(v => { if (v.Result !== 'success') v.Result = 'success'; }));
  await p.evaluate(() => refresh()); await p.waitForTimeout(800);
  check(!(await p.locator('#argus').evaluate(e => e.classList.contains('glare'))), 'Argus calms down when nothing has failed');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  const ph = await page(b, 375, 760); await ph.goto(BASE); await ph.waitForTimeout(800);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
});
