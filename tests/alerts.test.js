// Alert files (docs/alerts.md) and the registry's name fallback for per-run units (zeus-deploy-<id> -> zeus-deploy.json).
// Everything this file adds (units, registry entries, alert files) is taken away again at the end.
const {BASE, check, page, noOverflow, shot, units, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home');
const THEME = JSON.parse(fs.readFileSync(path.join(path.dirname(process.env.FIXTURES), 'pkg/static/theme.json')));   // the theme may name its own registry
const REG = (THEME.registry || '~/.config/argus-ui/agents').replace(/^~/, HOME), AL = path.join(HOME, '.local/state/argus-ui/alerts');
const put = (dir, name, obj) => { fs.mkdirSync(dir, {recursive: true}); fs.writeFileSync(path.join(dir, name), typeof obj === 'string' ? obj : JSON.stringify(obj)); };
const DEPLOYS = ['zeus-deploy-20261021-090012-argus-ui-3fa9c1b', 'zeus-deploy-20261022-101500-argus-ui-9b0589a'];
const ran = (day, t, result = 'success') => ({Result: result, ActiveState: result === 'success' ? 'inactive' : 'failed', timer: false,
  ExecMainStartTimestamp: `Wed 2026-10-${day} ${t} MDT`, ExecMainExitTimestamp: `Wed 2026-10-${day} ${t} MDT`, Description: 'a systemd-run unit'});
const LOG = () => fs.readFileSync(path.join(path.dirname(process.env.FIXTURES), 'server.log'), 'utf8');

run(async b => {
  let before;
  units(u => { before = JSON.stringify(u); u['hermes-rename'].Result = 'success';                    // start calm: nothing failed
    u[DEPLOYS[0]] = ran(21, '09:00:12'); u[DEPLOYS[1]] = ran(22, '10:15:00'); u['hermes-fetch-github'] = ran(22, '08:00:00'); });
  put(REG, 'zeus-deploy.json', {notes: 'Zeus deploys an approved commit', transient: true});
  put(REG, 'hermes-fetch.json', {notes: 'Fetchers: new things from outside'});
  put(REG, 'hermes-sort.json', {notes: 'Exact entry for hermes-sort'});
  try {
    // ---- registry fallback (#11) ----
    const p = await page(b);
    await p.goto(BASE); await p.waitForTimeout(800);
    const dep = p.locator('.card', {has: p.locator('.job', {hasText: /^deploy$/})});
    check(await dep.count() === 1, 'registry: two zeus-deploy-<id> runs make one card, named after the base entry');
    check(/Zeus deploys an approved commit/.test(await dep.locator('.notes').textContent()), 'registry: the card gets zeus-deploy.json\'s notes');
    check(/9b0589a · latest of 2 runs/.test(await dep.locator('.unit').textContent()), 'registry: the card shows the latest run and how many there are');
    check(await dep.locator('button[data-act="bolt"]').count() === 0 && await dep.locator('button[data-act="freeze"]').count() === 0, 'registry: a transient card has no Run or Freeze');
    check(await p.locator('.card[data-job="hermes-fetch-github"] .notes').textContent() === 'Fetchers: new things from outside', 'registry: a non-transient unit falls back to its prefix entry and keeps its own card');
    check(await p.locator('.card[data-job="hermes-sort"] .notes').textContent() === 'Exact entry for hermes-sort', 'registry: exact-name lookups are unchanged');
    check(await p.locator('.card[data-job="hermes-media"] .notes').count() === 0 || !/Exact entry/.test(await p.locator('.card[data-job="hermes-media"] .notes').textContent()), 'registry: a sibling name does not borrow another task\'s exact entry');
    units(u => { u[DEPLOYS[1]] = ran(22, '10:15:00', 'exit-code'); });
    await p.evaluate(() => refresh()); await p.waitForTimeout(500);
    check(await dep.locator('.pill').textContent() === 'failed' && await p.locator('#argus').evaluate(e => e.classList.contains('glare')), 'registry: the card takes the latest run\'s state (a failed deploy glares)');
    units(u => { u[DEPLOYS[1]] = ran(22, '10:15:00'); });

    // ---- alert files (#8) ----
    put(AL, 'hermes.json', {job: 'hermes-sort', level: 'alert', since: new Date().toISOString(), message: '1 delivery quarantined: .exe files are never allowed', link: 'olympus'});
    await p.evaluate(() => refresh()); await p.waitForTimeout(500);
    const hs = p.locator('.card[data-job="hermes-sort"]');
    check(await p.locator('#argus').evaluate(e => e.classList.contains('glare')), 'alert: Argus glares');
    check(!(await p.locator('#alarm').isHidden()) && await p.locator('#realmDot').textContent() === '1', 'alert: it counts in the alarm badge like a failed task');
    check(await hs.evaluate(e => e.classList.contains('alerted')) && /1 delivery quarantined/.test(await hs.locator('.alert-msg').textContent()), 'alert: the task\'s card shows the message');
    const link = hs.locator('.alert-msg a');
    check(await link.textContent() === 'Open Olympus' && /\/olympus$/.test(await link.getAttribute('href')), 'alert: the card links to the section');
    check((await link.boundingBox()).height >= 44, 'alert: the link keeps a 44 px hit area');
    check(/1 alert: hermes-sort, 1 delivery quarantined/.test(await p.locator('#argus').getAttribute('aria-label')), 'alert: Argus\'s label says what is wrong');
    await shot(p, 'alerts');

    fs.unlinkSync(path.join(AL, 'hermes.json'));
    put(AL, 'zeus.json', {job: 'zeus-approve', level: 'warn', since: '2026-10-21T09:05:00-06:00', message: 'argus-ui 4.9.1 failed and 4.9.0 was put back', link: 'throne'});
    await p.evaluate(() => refresh()); await p.waitForTimeout(500);
    check(!(await p.locator('#argus').evaluate(e => e.classList.contains('glare'))), 'warn: no glare; the alert file going away calmed him');
    check(await p.locator('#alarm').isHidden(), 'warn: and no alarm badge');
    const lone = p.locator('.card.alert-only[data-alert="zeus.json"]');
    check(await lone.count() === 1 && /4\.9\.0 was put back/.test(await lone.textContent()), 'warn: an alert for a job with no card gets a card of its own in its agent\'s section');
    check(await lone.locator('.alert-msg a').count() === 0, 'warn: a link to a section that isn\'t installed is dropped');
    check(await hs.locator('.alert-msg').count() === 0, 'warn: the removed alert is gone from its card');

    put(AL, 'broken.json', '{"job": "hermes-sort", "level": ');
    put(AL, 'badlevel.json', {job: 'hermes-sort', level: 'panic', message: 'x'});
    put(AL, 'stranger.json', {job: 'nobody-here', level: 'alert', message: 'x'});
    await p.evaluate(() => refresh()); await p.waitForTimeout(400); await p.evaluate(() => refresh()); await p.waitForTimeout(400);
    const st = await (await p.request.get(BASE + 'api/state')).json();
    check(st.alerts.length === 1 && st.alerts[0].file === 'zeus.json', 'malformed: broken JSON, an unknown level and an unknown agent are ignored');
    check(!(await p.locator('#argus').evaluate(e => e.classList.contains('glare'))), 'malformed: they never make Argus glare');
    const lines = LOG().split('\n').filter(l => /ignored alert file/.test(l));
    check(['broken.json', 'badlevel.json', 'stranger.json'].every(n => lines.filter(l => l.includes(n)).length === 1), 'malformed: one log line each, not one per refresh');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

    const ph = await page(b, 375, 760); await ph.goto(BASE); await ph.waitForTimeout(800);
    check(await noOverflow(ph), 'phone: no sideways scrolling with an alert card');
  } finally {
    units(u => { for (const k of Object.keys(u)) delete u[k]; Object.assign(u, JSON.parse(before)); });
    for (const [d, n] of [[REG, 'zeus-deploy.json'], [REG, 'hermes-fetch.json'], [REG, 'hermes-sort.json'], [AL, 'hermes.json'], [AL, 'zeus.json'], [AL, 'broken.json'], [AL, 'badlevel.json'], [AL, 'stranger.json']])
      fs.rmSync(path.join(d, n), {force: true});
  }
});
