// LeafyPlugins (docs/leafy-plugin.md): the demo plugin in tests/plugin-fixtures/ gets a pill and a section,
// its frame loads its own files, survives the refresh, and is sandboxed away from Argus's powers.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
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
});
