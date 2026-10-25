// LeafyPlugins (docs/leafy-plugin.md): the demo plugin in tests/plugin-fixtures/ gets a pill and a section,
// its frame loads its own files, survives the refresh, and is sandboxed away from Argus's powers.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
run(async b => {
  const p = await page(b);
  await p.goto(BASE); await p.waitForTimeout(600);
  const pill = p.locator('#realms a.realm', {hasText: 'Spartamelee'});
  check(await pill.count() === 1, 'the plugin has a pill in the section bar');
  check(await p.locator('#realms .realm.soon', {hasText: 'Spartamelee'}).count() === 0, 'it replaces the theme\'s "coming later" pill');

  await pill.click(); await p.waitForURL(/\/spartamelee$/); await p.waitForTimeout(800);
  check(await p.locator('body.side').count() === 1, 'the plugin page is a side page (Argus in the corner)');
  check(await p.locator('.title h1').textContent() === 'Spartamelee', 'the page title is the plugin name');
  const frame = p.locator('iframe.plugin-frame');
  check((await frame.getAttribute('sandbox') || '').split(' ').sort().join(' ') === 'allow-pointer-lock allow-popups allow-scripts', 'the frame is sandboxed without allow-same-origin');
  const out = p.frameLocator('iframe.plugin-frame').locator('#out');
  await out.filter({hasText: 'ready'}).waitFor({timeout: 5000});
  check(await out.getAttribute('data-loaded') === 'from the plugin folder', 'the plugin loads its own module script and JSON');
  check(await out.getAttribute('data-freeze') !== '200', 'the plugin cannot use Medusa: its POST to api/freeze is refused');
  check(await out.getAttribute('data-state') === 'blocked', 'the plugin cannot read api/state');
  check(await out.getAttribute('data-server') === 'blocked', 'the plugin cannot read a server plugin\'s API');
  const st = await (await p.request.get(BASE + 'api/state')).json();
  check(st.jobs.find(j => j.job === 'hermes-sort')?.state !== 'frozen', 'and the task it tried to freeze is untouched');

  const boot = await out.getAttribute('data-boot');
  await p.evaluate(() => refresh()); await p.waitForTimeout(500);
  check(await p.frameLocator('iframe.plugin-frame').locator('#out').getAttribute('data-boot') === boot, 'the refresh keeps the frame (a game would keep running)');
  check(!(await p.locator('#hero').isVisible()), 'no empty icon box when the plugin has no icon');
  check(await p.locator('.plugin-full').isVisible() && (await p.locator('.plugin-bar').boundingBox()).y + 40 < 900, 'the frame and its bar fit the window');
  await shot(p, 'plugin');

  const bad = async path => (await p.request.get(BASE + path)).status();
  check(await bad('plugins/spartamelee/plugin.json') === 404, 'plugin.json is not served');
  // Raw paths (Playwright would tidy the dots away before sending): .. must not leave the plugin folder.
  const rawGet = path => new Promise(ok => { const u = new URL(BASE);
    require('http').get({host: u.hostname, port: u.port, path: u.pathname + path}, r => { r.resume(); ok(r.statusCode); }).on('error', () => ok(0)); });
  check(await rawGet('plugins/spartamelee/../../static/theme.json') === 404 && await rawGet('plugins/spartamelee/../spartamelee/plugin.json') === 404,
    '.. cannot leave the plugin folder, and plugin.json stays private');
  check(await bad('plugins/nope/') === 404, 'an unknown plugin is a 404');
  const r = await p.request.get(BASE + 'plugins/spartamelee/app.js');
  check(/text\/javascript/.test(r.headers()['content-type']) && r.headers()['access-control-allow-origin'] === '*'
    && /sandbox/.test(r.headers()['content-security-policy'] || ''), 'plugin files: JS type, CORS for the sandbox, CSP sandbox even when opened alone');
  const redir = await p.request.get(BASE + 'plugins/spartamelee', {maxRedirects: 0});
  check(redir.status() === 301 && /plugins\/spartamelee\/$/.test(redir.headers()['location']), 'plugins/<id> redirects to plugins/<id>/ so relative URLs work');

  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  const ph = await page(b, 375, 760); await ph.goto(BASE + 'spartamelee'); await ph.waitForTimeout(800);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
  check(await ph.locator('.plugin-full').evaluate(e => e.getBoundingClientRect().height >= 36), 'phone: the full screen button keeps its hit area');

  // ---- server plugins: tests/plugin-fixtures/demo-server (works) and demo-broken (fails on import) ----
  const s = await page(b);
  await s.goto(BASE); await s.waitForTimeout(600);
  const spill = s.locator('#realms a.realm', {hasText: 'Demo Server'});
  check(await spill.count() === 1, 'server plugin: it has a pill in the section bar');
  check(await s.locator('#realms .realm', {hasText: 'Demo Broken'}).count() === 0, 'server plugin: one whose plugin.py fails to load gets no pill');
  await spill.click(); await s.waitForURL(/\/demo-server$/);
  const body = s.locator('.plugin-server .plugin-body');
  await s.locator('#demo-ping', {hasText: 'pong from demo-server'}).waitFor({timeout: 5000});
  check(true, 'server plugin: its page script runs inside the page and reads its own API');
  check(await s.locator('body.side').count() === 1 && await s.locator('.title h1').textContent() === 'Demo Server', 'server plugin: a side page titled with the plugin name');
  check(await s.locator('iframe').count() === 0, 'server plugin: no frame, the page script runs in Elaia\'s page');
  check(await s.locator('#demo-ping').evaluate(e => getComputedStyle(e).letterSpacing) === '3px', 'server plugin: its style sheet loads');
  await s.locator('#demo-echo').click();
  await s.locator('#demo-out', {hasText: 'echo: hello'}).waitFor({timeout: 3000});
  check(true, 'server plugin: a POST from its page passes Elaia\'s checks and reaches post()');
  await s.evaluate(() => refresh()); await s.waitForTimeout(400);
  check(await body.getAttribute('data-shows') === '1' && await body.getAttribute('data-refreshes') === '1', 'server plugin: the 15 s refresh calls refresh(), not show() again');
  check(s.errors.length === 0, 'server plugin: no page errors ' + s.errors.join(' | '));
  await shot(s, 'plugin-server');

  const api = BASE + 'api/demo-server/';
  const ping = await s.request.get(api + 'ping?q=hi', {headers: {'Tailscale-User-Login': 'someone@example.com'}});
  const pj = await ping.json();
  check(ping.status() === 200 && pj.pong && pj.q === 'hi' && pj.data_dir_ok, 'server plugin: GET api/<id>/ping answers, with the query and a data folder made by init()');
  check(pj.user === 'someone@example.com', 'server plugin: ctx.headers carries Tailscale-User-Login');
  check((await (await s.request.get(api + 'status')).json()).line === '1 ping answered · all well', 'server plugin: api/<id>/status gives the Home line');
  check((await s.request.get(api + 'nope')).status() === 404, 'server plugin: its own 404 comes through');
  const boom = await s.request.get(api + 'boom');
  check(boom.status() === 500 && (await boom.json()).msg === 'plugin error', 'server plugin: an exception is a 500 "plugin error", not a crash');
  check((await s.request.get(BASE + 'api/health')).status() === 200, 'and Elaia keeps answering after it');
  const post = (headers, data) => s.request.post(api + 'echo', {headers: {'Content-Type': 'application/json', ...headers}, data});
  check((await post({Origin: 'http://evil.example', 'Sec-Fetch-Site': 'cross-site'}, {text: 'x'})).status() === 403, 'server plugin: a cross-site POST is refused');
  check((await post({'Content-Type': 'text/plain'}, '{"text":"x"}')).status() === 415, 'server plugin: a POST that is not JSON is refused');
  check((await post({}, {text: 'x'.repeat(5000)})).status() === 200, 'server plugin: "max_body": 8192 lets a 5 KB POST through (4.23.0)');
  check((await post({}, {text: 'x'.repeat(9000)})).status() === 413, 'server plugin: a POST over its max_body is refused');
  check((await s.request.post(BASE + 'api/freeze', {headers: {'Content-Type': 'application/json'}, data: {job: 'x'.repeat(5000)}})).status() === 413, 'Elaia\'s own POSTs keep the 4 KB limit');
  check((await s.request.get(BASE + 'plugins/demo-server/plugin.py')).status() === 404, 'server plugin: plugin.py is never served');
  check((await s.request.get(BASE + 'plugins/demo-server/page.js')).status() === 200, 'server plugin: its page script is served');
  check((await s.request.get(BASE + 'api/demo-broken/ping')).status() === 404 && (await s.request.get(BASE + 'demo-broken')).status() === 404,
    'server plugin: the broken one has no API and no section');
  const log = fs.readFileSync(path.join(path.dirname(process.env.FIXTURES), 'server.log'), 'utf8');
  check(/skipped server plugin demo-broken/.test(log) && /loaded server plugin demo-server/.test(log), 'server plugin: the log says which loaded and which was skipped');

  const sph = await page(b, 375, 760); await sph.goto(BASE + 'demo-server');
  await sph.locator('#demo-ping', {hasText: 'pong'}).waitFor({timeout: 5000});
  check(await noOverflow(sph), 'server plugin, phone: no sideways scrolling');
});
