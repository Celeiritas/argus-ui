// People and roles in the real page (docs/people.md): a people file is put into the test server's HOME for the length of
// this check, and browsers come in "through Tailscale Serve" (tests/run.sh starts the server as the Serve user, with
// ARGUS_DEV) with their own login: the owner, a learner and a stranger. Nothing is injected into the page: what each sees
// comes from the server. The file is moved aside at the end, so every later check sees the page without people again.
const {BASE, check, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CONF = path.join(HOME, '.config', 'argus-ui');
const FILE = path.join(CONF, 'people.json');
const OWNER = 'owner@example.com', LEARNER = 'learner@example.com', STRANGER = 'stranger@example.com';
const PEOPLE = {people: [{id: 'owner-one', name: 'Owner One', role: 'owner', logins: [OWNER]},
                         {id: 'learner-two', name: 'Learner Two', role: 'learner', logins: [LEARNER]}]};
// Study shows for her only when the Mentor in this build opens paths to learners ("roles" in its plugin.json, #44)
const mentor = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'plugins', 'mentor', 'plugin.json'), 'utf8'));
const STUDY = Object.values((mentor.roles || {}).get || {}).includes('learner');
let n = 0;
const write = doc => { fs.writeFileSync(FILE, typeof doc === 'string' ? doc : JSON.stringify(doc)); const t = new Date(Date.now() + 1000 * ++n); fs.utimesSync(FILE, t, t); };
const as = (b, login, from = '192.0.2.20', width = 412) => b.newContext({viewport: {width, height: 860},
  extraHTTPHeaders: {'Tailscale-User-Login': login, 'X-Forwarded-For': from}});
async function open(ctx, where = '') {
  const p = await ctx.newPage(); p.errors = []; p.on('pageerror', e => p.errors.push(String(e)));
  const r = await p.goto(BASE + where); await p.waitForTimeout(1200); return [p, r];
}
const slots = p => p.locator('#tabbar .tab b').allTextContents();
const landed = p => new URL(p.url()).pathname === new URL(BASE).pathname;

run(async b => {
  fs.mkdirSync(CONF, {recursive: true}); write(PEOPLE);
  try {
    // ---- the learner, on her phone ----
    const lc = await as(b, LEARNER);
    let [p] = await open(lc);
    const S = await p.evaluate(() => ({role: S.role, person: S.person, name: S.name, jobs: S.jobs.length, alerts: S.alerts.length, links: S.links.length,
      problem: 'people_problem' in S}));
    check(S.role === 'learner' && S.person === 'learner-two' && S.name === 'Learner Two', `learner: the server says who she is (${S.role}, ${S.person})`);
    check(S.jobs === 0 && S.alerts === 0 && S.links === 0 && !S.problem, 'learner: her state has no tasks, alerts, links or owner notices');
    const want = STUDY ? ['Today', 'Study'] : ['Today'];
    check(JSON.stringify(await slots(p)) === JSON.stringify(want) && await p.locator('#tabbar [data-more]').count() === 0,
      `learner: the bar shows ${want.join(' and ')} and no More (${(await slots(p)).join(', ')}; this Mentor opens paths to learners: ${STUDY})`);
    check(await p.locator('#argus').isHidden() && await p.locator('#alarm').evaluate(e => !e.offsetParent), 'learner: no Argus in the corner, no badge');
    check(await p.locator('#peopleProblem').isHidden(), 'learner: no people-file line');
    await p.evaluate(() => refresh()); await p.waitForTimeout(600);
    check(await p.evaluate(() => !window.chimed), 'learner: no chime');
    check(p.errors.length === 0, 'learner: no page errors ' + p.errors.join(' | '));
    await shot(p, 'learner-today-412');
    for (const deep of ['argus', 'throne', 'olympus']) {
      const [q] = await open(lc, deep);
      check(landed(q), `learner: opening ${deep} lands her on Today (${new URL(q.url()).pathname})`);
      await q.close();
    }
    const wide = await (await as(b, LEARNER, '192.0.2.20', 1440)).newPage(); await wide.goto(BASE); await wide.waitForTimeout(1000);
    check(JSON.stringify(await wide.locator('#realms a.realm b').allTextContents()) === JSON.stringify(want), 'learner on a wide screen: the strip shows the same places');
    const log = await p.request.get(BASE + 'api/log/hermes-sort'), bolt = await p.request.post(BASE + 'api/bolt', {data: {job: 'hermes-sort'}});
    check(log.status() === 403 && /Only the owner/.test((await log.json()).error), 'learner: a program log is refused with a sentence');
    check(bolt.status() === 403 && /Only the owner/.test((await bolt.json()).error), 'learner: Restart is refused with a sentence');
    if (STUDY) {
      const [m] = await open(lc, 'mentor');
      check(/\/mentor$/.test(m.url()) && m.errors.length === 0, 'learner: Study opens and stays open, no page errors ' + m.errors.join(' | '));
    }
    await lc.close();

    // ---- the owner, unchanged; then told about a people file that went bad ----
    const oc = await as(b, OWNER);
    [p] = await open(oc);
    check(await p.evaluate(() => S.role === 'owner' && S.person === 'owner-one' && S.jobs.length > 0 && S.people_problem === null), 'owner: everything, as Owner One');
    check((await slots(p)).includes('Watch') && await p.locator('#peopleProblem').isHidden(), 'owner: Watch in the bar, no people-file line while the file is fine');
    write('{"people": [ a typo');
    for (const where of ['', 'argus']) {
      const [q] = await open(oc, where), line = q.locator('#peopleProblem');
      const fsz = await line.evaluate(e => parseFloat(getComputedStyle(e).fontSize));
      check(await line.isVisible() && /keeps the last good copy/.test(await line.textContent()) && fsz === 14,
        `owner on ${where || 'Today'}: one plain 14 px line says the people file cannot be used (${fsz} px)`);
      check(await q.evaluate(() => S.role === 'owner'), `owner on ${where || 'Today'}: still the owner (the last good copy)`);
      await q.close();
    }
    const [m2] = await open(oc, 'olympus');
    check(await m2.locator('#peopleProblem').isHidden(), 'owner elsewhere (Olympus): the line stays on Today and Watch');
    const narrow = await (await as(b, OWNER, '192.0.2.20', 360)).newPage(); await narrow.goto(BASE); await narrow.waitForTimeout(1000);
    check(await narrow.evaluate(() => document.documentElement.scrollWidth <= innerWidth) && await narrow.locator('#peopleProblem').isVisible(),
      'owner at 360 px: the line wraps, no sideways scrolling');
    const [lq] = await open(await as(b, LEARNER));
    check(await lq.locator('#peopleProblem').isHidden() && await lq.evaluate(() => S.role === 'learner'), 'learner meanwhile: still herself, no line');
    write(PEOPLE);
    await oc.close();

    // ---- a stranger, and a program on the server using Serve's front door ----
    const sc = await as(b, STRANGER);
    let r; [p, r] = await open(sc);
    check(r.status() === 403 && /This page is private/.test(await p.textContent('h1')) && (await p.textContent('main')).includes(STRANGER), 'stranger: the private page names the login the server saw');
    await sc.close();
    const self = await as(b, OWNER, '127.0.0.1');
    [p, r] = await open(self);
    check(r.status() === 403 && /came from the server itself/.test(await p.textContent('main')), "the server itself, with the owner's login: not a person");
    const who = await (await p.request.get(BASE + 'api/whoami')).json();
    check(who.from_this_server === true && who.trusted === false && who.role === 'none', 'api/whoami says the request came from the server itself');
    await self.close();
  } finally {
    fs.renameSync(FILE, path.join(CONF, `people.json.set-aside-${Date.now()}`));     // later checks see the page without people
  }
  const back = await b.newContext(); const q = await back.newPage(); await q.goto(BASE); await q.waitForTimeout(600);
  check(await q.evaluate(() => S.role === 'owner' && S.name === 'You'), 'the file moved aside: everyone is the owner again, at once');
  await back.close();
});
