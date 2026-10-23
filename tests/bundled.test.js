// Bundled plugins and agent sections (docs/leafy-plugin.md): tests/bundled-fixtures/ is installed next to Elaia (ARGUS_BUNDLED).
// heracles claims the theme's Heracles section ("agent": true); the bundled demo-server is replaced by the owner's own copy.
const {BASE, check, page, noOverflow, run} = require('./lib');
const fs = require('fs'), path = require('path');
run(async b => {
  const p = await page(b);
  const st = await (await p.request.get(BASE + 'api/state')).json();
  const her = st.plugins.find(x => x.id === 'heracles'), demo = st.plugins.find(x => x.id === 'demo-server');
  check(her && her.agent === true && her.name === 'Heracles' && her.subtitle === 'Strength', 'agent plugin: listed, with the agent\'s name and subtitle from the theme');
  check(demo && demo.version === '0.0.1-test' && demo.name === 'Demo Server', 'bundled: your plugin wins over a bundled one with the same id');
  check(!st.plugins.some(x => x.id === 'chronos'), 'an agent\'s name without "agent": true is skipped');
  const log = fs.readFileSync(path.join(path.dirname(process.env.FIXTURES), 'server.log'), 'utf8');
  check(/loaded server plugin heracles 0\.0\.1-bundled \(bundled\)/.test(log) && !/must not load/.test(log), 'bundled: the log marks it bundled, and the replaced copy never ran');

  await p.goto(BASE); await p.waitForTimeout(600);
  const pill = p.locator('#realms a.realm', {hasText: 'Heracles'});
  check(await pill.count() === 1 && /static\/icons\/heracles\.png$/.test(await pill.locator('img').getAttribute('src')), 'agent plugin: one pill, with the agent\'s icon');
  await pill.click(); await p.waitForURL(/\/heracles$/);
  await p.locator('#her-where', {hasText: 'from bundled'}).waitFor({timeout: 5000});
  check(true, 'agent plugin: its page runs in the agent\'s section and its API answers from the bundled folder');
  check(/theme found/.test(await p.locator('#her-where').textContent()), 'ctx.theme_dir: the plugin finds the installed theme (theme.json, decks)');
  check(await p.locator('.title h1').textContent() === 'Heracles' && /heracles\.png$/.test(await p.locator('#hero').getAttribute('src')) && !(await p.locator('#hero').isHidden()),
    'agent plugin: the title and hero are the agent\'s');
  check(await p.locator('body.side').count() === 1, 'agent plugin: a side page (Argus in the corner)');
  check((await p.request.get(BASE + 'plugins/heracles/plugin.py')).status() === 404 && (await p.request.get(BASE + 'plugins/heracles/page.js')).status() === 200,
    'bundled: plugin.py is never served, the page script is');
  check((await (await p.request.get(BASE + 'api/heracles/status')).json()).line === '2 workouts this week', 'agent plugin: api/<id>/status gives Home its line');
  const men = st.plugins.find(x => x.id === 'mentor');
  check(men && men.agent && men.kind === 'server', 'Mentor is a bundled server plugin that took over the agent section');
  check(/loaded server plugin mentor [\d.]+ \(bundled\)/.test(log), 'Mentor: loaded from the bundled folder');
  check((await p.request.get(BASE + 'plugins/mentor/mentor.py')).status() === 404 && (await p.request.get(BASE + 'plugins/mentor/plugin.py')).status() === 404, 'Mentor: its Python files are never served');
  check(/due|to learn|waiting|Nothing due/.test((await (await p.request.get(BASE + 'api/mentor/status')).json()).line), 'Mentor: api/mentor/status gives Home its line');
  await p.goto(BASE); await p.waitForTimeout(500);
  const pills = await p.locator('#realms a.realm b').allTextContents();
  check(pills.filter(t => t === 'Mentor').length === 1 && pills.indexOf('Mentor') === pills.indexOf('Argus') + 1, 'Mentor: one pill, still right after Argus');

  await p.goto(BASE + 'home'); await p.waitForTimeout(800);
  const tile = p.locator('.tile', {has: p.locator('.tname b', {hasText: 'Heracles'})});
  check(await tile.count() === 1 && /2 workouts this week/.test(await tile.textContent()), 'Home: one tile for the agent plugin, with its status line');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'heracles'); await ph.locator('#her-where').waitFor({timeout: 5000});
  check(await noOverflow(ph), 'phone: no sideways scrolling');
});
