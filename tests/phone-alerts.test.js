// Phone alerts in the real page (web/js/alerts.js, web/sw.js, docs/phone-alerts.md). The server is tests/run.sh's, started
// with ARGUS_PUSH_TEST_ORIGIN pointing at the fake push service this test runs on 127.0.0.1:PUSH_PORT: nothing ever goes to a
// real push service. A real pushManager.subscribe() would contact the browser maker's service, so the browser's side is a
// stand-in made in each page (Notification.permission, requestPermission, PushManager subscribe / getSubscription); its keys are
// real P-256 keys made here, so the test buzz that reaches the fake service is decrypted and read like a phone would.
// The service worker is the real one: a push message is delivered to it with Chromium's own hook (CDP
// ServiceWorker.deliverPushMessage), and its tap handler is run on the notification it showed.
const {BASE, check, shot, run} = require('./lib');
const fs = require('fs'), path = require('path'), http = require('http'), crypto = require('crypto'), vm = require('vm');
const {chromium} = require('playwright');
const PUSH_PORT = +(process.env.PUSH_PORT || 8099), PUSH = `http://127.0.0.1:${PUSH_PORT}`;
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CONF = path.join(HOME, '.config', 'argus-ui');
const OWNER = 'owner@example.com', LEARNER = 'learner@example.com';
const DESK_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36';
const PHONE_UA = 'Mozilla/5.0 (Linux; Android 16; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Mobile Safari/537.36';

// ---- the fake push service: records every message, answers 201 ----
const got = [];
const fake = http.createServer((q, r) => { const b = []; q.on('data', c => b.push(c)); q.on('end', () => { got.push({path: q.url, headers: q.headers, body: Buffer.concat(b)}); r.writeHead(201); r.end(); }); });
// ---- a phone's keys (as pushManager.subscribe makes them) and the decryption a phone does (RFC 8291) ----
function phoneKeys(name) {
  const e = crypto.createECDH('prime256v1'); e.generateKeys(); const auth = crypto.randomBytes(16);
  const b64 = b => b.toString('base64url');
  return {e, auth, sub: {endpoint: `${PUSH}/send/${name}`, expirationTime: null, keys: {p256dh: b64(e.getPublicKey()), auth: b64(auth)}}};
}
function decrypt(body, k) {
  const salt = body.subarray(0, 16), idlen = body[20], asPub = body.subarray(21, 21 + idlen), ct = body.subarray(21 + idlen);
  const secret = k.e.computeSecret(asPub), h = (ikm, salt, info, n) => Buffer.from(crypto.hkdfSync('sha256', ikm, salt, Buffer.from(info, 'binary'), n));
  const ikm = h(secret, k.auth, Buffer.concat([Buffer.from('WebPush: info\0'), k.e.getPublicKey(), asPub]).toString('binary'), 32);
  const d = crypto.createDecipheriv('aes-128-gcm', h(ikm, salt, 'Content-Encoding: aes128gcm\0', 16), h(ikm, salt, 'Content-Encoding: nonce\0', 12));
  d.setAuthTag(ct.subarray(ct.length - 16)); const pt = Buffer.concat([d.update(ct.subarray(0, ct.length - 16)), d.final()]);
  return JSON.parse(pt.subarray(0, pt.lastIndexOf(2)).toString());
}
// ---- the browser's side, made in each page before Elaia's scripts run ----
function standIn({mode, sub, noStorage}) {
  window.__t = {asked: 0, subscribed: 0, unsub: 0};
  if (noStorage) for (const k of ['localStorage', 'sessionStorage']) Object.defineProperty(window, k, {configurable: true, get() { throw new DOMException('blocked', 'SecurityError'); }});
  if (mode === 'cannot') { delete window.PushManager; return; }
  const mem = {};
  const ss = {get: k => { try { return sessionStorage.getItem(k); } catch (e) { return mem[k] ?? null; } }, set: (k, v) => { try { sessionStorage.setItem(k, v); } catch (e) { mem[k] = v; } },
    del: k => { try { sessionStorage.removeItem(k); } catch (e) { delete mem[k]; } }};
  Object.defineProperty(Notification, 'permission', {configurable: true, get: () => mode === 'blocked' ? 'denied' : ss.get('t-perm') || 'default'});
  if (mode === 'subscribed' && !ss.get('t-sub')) { ss.set('t-perm', 'granted'); ss.set('t-sub', JSON.stringify(sub)); }   // a phone where alerts are already on
  Notification.requestPermission = async () => { __t.asked++; if (mode === 'blocked') return 'denied'; ss.set('t-perm', 'granted'); return 'granted'; };
  const made = () => { const s = JSON.parse(ss.get('t-sub') || 'null');
    return s && {endpoint: s.endpoint, toJSON: () => s, unsubscribe: async () => { __t.unsub++; ss.del('t-sub'); return true; }}; };
  PushManager.prototype.getSubscription = async function () { return made(); };
  PushManager.prototype.subscribe = async function (o) { __t.subscribed++; __t.keyLength = new Uint8Array(o.applicationServerKey).length; ss.set('t-sub', JSON.stringify(sub)); return made(); };
}
async function phone(b, {mode = 'ok', width = 412, login = OWNER, ua = PHONE_UA, noStorage = false, sub} = {}) {
  const ctx = await b.newContext({viewport: {width, height: 900}, userAgent: ua, extraHTTPHeaders: {'Tailscale-User-Login': login, 'X-Forwarded-For': '192.0.2.20'}});
  await ctx.addInitScript(standIn, {mode, sub: sub || phoneKeys('phone-1').sub, noStorage});
  return ctx;
}
async function open(ctx, where = 'phone', wait = 1500) {
  const p = await ctx.newPage(); p.errors = []; p.on('pageerror', e => p.errors.push(String(e)));
  p.posts = []; p.on('request', r => { if (r.method() === 'POST') p.posts.push(new URL(r.url()).pathname.replace(/.*\/api\//, 'api/')); });
  await p.goto(BASE + where); await p.waitForTimeout(wait); return p;
}
const heading = p => p.locator('#main .pstate').textContent();
const status = async p => (await p.request.get(BASE + 'api/push/status')).json();
async function targets(p) {        // every control on the page at least 44 x 44 px
  return p.locator('#main .phone button, #main .phone a, #phoneHint a, #phoneHint button').evaluateAll(es => es.filter(e => e.offsetParent)
    .map(e => [e.textContent.trim().slice(0, 30), e.getBoundingClientRect()]).filter(([, r]) => r.width < 44 || r.height < 44).map(([t, r]) => `${t} ${r.width | 0}x${r.height | 0}`));
}
async function contrast(p, sel = '#main .phone') {   // computed: every piece of text against what is behind it (opaque panels)
  return p.evaluate(sel => {
    const rgb = s => (s.match(/[\d.]+/g) || []).map(Number), lum = ([r, g, b]) => [r, g, b].map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
    const bg = e => { let c = [28, 33, 39]; const stack = []; for (let x = e; x; x = x.parentElement) { const v = rgb(getComputedStyle(x).backgroundColor); if (v.length === 4 && v[3] === 0) continue; stack.push(v); if (v.length === 3 || v[3] === 1) break; }
      for (const v of stack.reverse()) { const a = v.length === 4 ? v[3] : 1; c = c.map((x, i) => x * (1 - a) + v[i] * a); } return c; };
    const bad = [], seen = [];
    for (const e of document.querySelectorAll(sel + ' *')) {
      if (!e.offsetParent || ![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
      const f = lum(rgb(getComputedStyle(e).color)), k = lum(bg(e)), ratio = (Math.max(f, k) + .05) / (Math.min(f, k) + .05);
      seen.push(ratio); if (ratio < 4.5) bad.push(`${e.textContent.trim().slice(0, 30)} ${ratio.toFixed(2)}`);
    }
    return {bad, n: seen.length, min: Math.min(...seen).toFixed(2)};
  }, sel);
}

// The service worker in a real browser: Chromium's own hook delivers a push message to it (CDP ServiceWorker.deliverPushMessage),
// it must show a notification, and its tap handler must send the open Elaia window to the alert's place. The headless shell
// that the other checks use answers every notification permission with "denied", so this part runs in Playwright's full
// Chromium build in its new headless mode (channel "chromium", installed by "npx playwright install chromium").
async function serviceWorker() {
  let b2;
  try { b2 = await chromium.launch({channel: 'chromium'}); }
  catch (e) { check(false, 'the full Chromium build could not start, so the service worker was not tried in a browser: ' + e.message.split('\n')[0]); return; }
  try {
    const ctx = await b2.newContext({extraHTTPHeaders: {'Tailscale-User-Login': OWNER, 'X-Forwarded-For': '192.0.2.20'}});
    const origin = new URL(BASE).origin;
    await ctx.grantPermissions(['notifications'], {origin});
    const p = await ctx.newPage(); p.errors = []; p.on('pageerror', e => p.errors.push(String(e)));
    await p.goto(BASE + 'phone'); await p.waitForTimeout(800);
    await p.evaluate(async () => { await navigator.serviceWorker.register('sw.js'); await navigator.serviceWorker.ready; });
    await p.reload(); await p.waitForTimeout(800);
    check(await p.evaluate(() => !!navigator.serviceWorker.controller), 'the service worker looks after the open Elaia page');
    const cdp = await ctx.newCDPSession(p); let regs = [];
    cdp.on('ServiceWorker.workerRegistrationUpdated', e => { regs = regs.concat(e.registrations); });
    await cdp.send('ServiceWorker.enable'); await p.waitForTimeout(500);
    const reg = regs.find(r => r.scopeURL === BASE && !r.isDeleted);
    check(!!reg, "the service worker is registered for Elaia's address");
    if (!reg) return;
    const notes = () => p.evaluate(async () => (await (await navigator.serviceWorker.getRegistration()).getNotifications()).map(n => ({title: n.title, body: n.body, tag: n.tag, url: n.data && n.data.url, icon: n.icon})));
    const msg = {id: 'e1', kind: 'broke', title: 'Media player runs, but cannot read its drive', body: 'The drive was unplugged and came back.', url: 'argus', at: '', tag: 'media'};
    await cdp.send('ServiceWorker.deliverPushMessage', {origin, registrationId: reg.registrationId, data: JSON.stringify(msg)});
    await p.waitForTimeout(1200);
    let ns = await notes();
    check(ns.length === 1 && ns[0].title === msg.title && ns[0].body === msg.body && ns[0].tag === 'media', `a delivered message is shown as a notification (${JSON.stringify(ns.map(n => n.title))})`);
    check(ns.length === 1 && ns[0].url === BASE + 'argus' && /static\/argus-192\.png$/.test(ns[0].icon), `its place is Watch inside Elaia, with the existing icon (${ns[0] && ns[0].url})`);
    await cdp.send('ServiceWorker.deliverPushMessage', {origin, registrationId: reg.registrationId, data: JSON.stringify({...msg, title: 'Media player still cannot read its drive'})});
    await p.waitForTimeout(800); ns = await notes();
    check(ns.length === 1 && ns[0].title === 'Media player still cannot read its drive', 'a newer message about the same thing replaces the older one, it does not stack');
    const worker = ctx.serviceWorkers()[0];
    check(!!worker, 'the service worker can be reached for the tap');
    if (worker) {
      await worker.evaluate(async () => { const n = (await self.registration.getNotifications())[0]; let w; onTap({notification: n, waitUntil: x => { w = x; }}); await w; });
      await p.waitForURL(u => new URL(u).pathname === new URL(BASE + 'argus').pathname, {timeout: 5000}).catch(() => {});
      check(new URL(p.url()).pathname === new URL(BASE + 'argus').pathname, `a tap: the open Elaia window goes to the alert's place (${new URL(p.url()).pathname})`);
      check((await worker.evaluate(async () => (await self.registration.getNotifications()).length)) === 0, 'a tap: the notification closes');
    }
    check(p.errors.length === 0, 'service worker: no page errors ' + p.errors.join(' | '));
  } finally { await b2.close(); }
}

run(async b => {
  await new Promise(z => fake.listen(PUSH_PORT, '127.0.0.1', z));
  try {
    // ---- not available on this server (the server says why, in words) ----
    let ctx = await phone(b);
    await ctx.route('**/api/push/status*', r => r.fulfill({json: {available: false, why: 'Phone alerts are not available on this server: it is missing the part that locks each message for your phone (the Python package "cryptography"). Everything else works as before.', trusted: true, devices: [], kinds: [], key: ''}}));
    let p = await open(ctx);
    check(await heading(p) === 'Phone alerts are not available' && /missing the part/.test(await p.locator('#main .phone').textContent()), 'not available: said in words, with the reason');
    check(await p.locator('[data-do=on]').count() === 0, 'not available: no button that cannot work');
    await shot(p, 'phone-412-unavailable'); await ctx.close();

    // ---- this browser cannot: add Elaia to the home screen first, three steps ----
    ctx = await phone(b, {mode: 'cannot'}); p = await open(ctx);
    check(await heading(p) === 'This browser cannot do it yet: add Elaia to your home screen first', `cannot: the state in words (${await heading(p)})`);
    check(await p.locator('.psteps li').count() === 3 && /Add to home screen/.test(await p.locator('.psteps').textContent()), 'cannot: the three steps for Chrome on Android');
    await shot(p, 'phone-412-cannot'); await ctx.close();

    // ---- blocked: how to allow them again, in the phone's own menu words ----
    ctx = await phone(b, {mode: 'blocked'}); p = await open(ctx);
    check(await heading(p) === 'Notifications are blocked for this page', 'blocked: the state in words');
    check(await p.locator('.psteps li').count() === 3 && /App info/.test(await p.locator('.psteps').textContent()) && /Allow/.test(await p.locator('.psteps').textContent()), 'blocked: three steps to allow them again');
    check(await p.evaluate(() => __t.asked) === 0, 'blocked: nothing asked on page load');
    await shot(p, 'phone-412-blocked'); await ctx.close();

    // ---- Today's quiet line (owner, alerts possible here, off on this device) ----
    const k1 = phoneKeys('phone-1');
    ctx = await phone(b, {sub: k1.sub}); p = await open(ctx, '', 1800);
    check(await p.locator('#phoneHint').isVisible() && /buzz/.test(await p.locator('#phoneHint').textContent()), "Today: the owner sees one quiet line about phone alerts");
    check(/\/phone$/.test(await p.locator('#phoneHint a').getAttribute('href')), "Today: it links to the Phone alerts page");
    check(await p.evaluate(() => __t.asked) === 0, 'Today: no permission question on page load');
    check((await targets(p)).length === 0, "Today's line: its link and button are at least 44 px " + (await targets(p)).join(', '));
    const ch = await contrast(p, '#phoneHint');
    check(ch.bad.length === 0 && ch.n >= 3, `Today's line: its text at least 4.5 to 1 (computed, lowest ${ch.min}) ${ch.bad.join(', ')}`);
    await shot(p, 'today-412-phone-line');
    await p.locator('#phoneHint [data-hint-off]').click();
    check(await p.locator('#phoneHint').isHidden(), 'Today: "Not now" hides the line');
    await p.reload(); await p.waitForTimeout(1500);
    check(await p.locator('#phoneHint').isHidden(), 'Today: and it stays hidden on this device');
    await p.close();

    // ---- off -> on: the question comes only from the tap ----
    p = await open(ctx);
    check(await heading(p) === 'Alerts are off on this phone', `off: the state in words (${await heading(p)})`);
    check(await p.locator('[data-do=on]').textContent() === 'Turn on alerts on this phone', 'off: ONE primary button, "Turn on alerts on this phone"');
    check(await p.locator('.pbtn.primary').count() === 1, 'off: one primary button only');
    check(await p.evaluate(() => __t.asked) === 0 && p.posts.length === 0, 'off: nothing asked and nothing sent on page load');
    await shot(p, 'phone-412-off');
    check((await targets(p)).length === 0, 'off: every control at least 44 px ' + (await targets(p)).join(', '));
    await p.locator('[data-do=on]').click(); await p.locator('#main .pstate.on').waitFor({timeout: 8000});
    check(await p.evaluate(() => [__t.asked, __t.subscribed, __t.keyLength].join()) === '1,1,65', 'on: one question, one sign-up, with the server\'s 65-byte public key');
    check(p.posts.filter(x => x === 'api/push/subscribe').length === 1, 'on: the device was sent to the server once');
    let s = await status(p);
    check(s.devices.length === 1 && s.devices[0].label === 'Android phone, Chrome' && s.devices[0].kinds.length === 3, `on: the server lists this phone (${JSON.stringify(s.devices.map(d => d.label))})`);
    check(!JSON.stringify(s).includes('/send/') && !JSON.stringify(s).includes(k1.sub.keys.auth), 'on: the server never answers the address or the keys');
    check(/^Alerts are on for this phone$/.test(await heading(p)) && /On since/.test(await p.locator('#main .ppanel').first().textContent()), 'on: "Alerts are on for this phone", on since when');
    const sw = await p.locator('.pswitch').evaluateAll(es => es.map(e => [e.getAttribute('role'), e.querySelector('b').textContent, e.getAttribute('aria-checked')].join('|')));
    check(JSON.stringify(sw) === JSON.stringify(['switch|Something stopped working|true', 'switch|Something needs my yes|true', 'switch|Daily summary|true']), 'on: three switches in his own words, all on');
    await shot(p, 'phone-412-on');
    check((await targets(p)).length === 0, 'on: every control at least 44 px ' + (await targets(p)).join(', '));
    const c = await contrast(p);
    check(c.bad.length === 0 && c.n > 10, `on: every piece of text at least 4.5 to 1 (computed, ${c.n} texts, lowest ${c.min}) ${c.bad.join(', ')}`);
    check(!/push|subscription|endpoint|vapid|service worker/i.test(await p.locator('#main').innerText()), 'no technical word anywhere a person reads');

    // ---- a switch calls the route once ----
    const before = p.posts.length;
    await p.locator('.pswitch', {hasText: 'Daily summary'}).click(); await p.waitForTimeout(800);
    check(p.posts.slice(before).join() === 'api/push/kinds', `a switch: exactly one call (${p.posts.slice(before).join()})`);
    check(await p.locator('.pswitch', {hasText: 'Daily summary'}).getAttribute('aria-checked') === 'false', 'a switch: it shows off');
    s = await status(p); check(JSON.stringify(s.devices[0].kinds) === '["broke","needs-yes"]', 'a switch: the server has it');
    check(/Daily summary: off/.test(await p.locator('#psay').textContent()), 'a switch: it says what changed');

    // ---- a test buzz reaches the (fake) push service, encrypted, and reads right ----
    got.length = 0;
    await p.locator('[data-do=test]').click(); await p.waitForTimeout(1500);
    check(/within a few seconds, also when Elaia is closed/.test(await p.locator('#psay').textContent()), 'test buzz: it says what to expect');
    check(got.length === 1 && got[0].path === '/send/phone-1' && got[0].headers['content-encoding'] === 'aes128gcm' && /^vapid t=/.test(got[0].headers.authorization), 'test buzz: one encrypted message to this phone\'s service');
    let m = null; try { m = decrypt(got[0].body, k1); } catch (e) {}
    check(m && m.title === 'Test buzz from Elaia' && m.kind === 'test' && m.url === 'phone', `test buzz: the phone can read it (${m && m.title})`);

    // ---- other devices: listed with Remove ----
    const k2 = phoneKeys('tablet-2');
    const r2 = await p.request.post(BASE + 'api/push/subscribe', {data: {subscription: k2.sub, label: 'Android tablet, Chrome', kinds: ['summary']}});
    check(r2.status() === 200, 'another device turned on (through the route)');
    await p.reload(); await p.waitForTimeout(1500);
    check(await p.locator('.pdevices li').count() === 1 && /Android tablet/.test(await p.locator('.pdevices').textContent()), 'other devices: listed by name, this phone not among them');
    await p.locator('.pdevices [data-do=forget]').click(); await p.waitForTimeout(1200);
    check(await p.locator('.pdevices li').count() === 0 && /No other device/.test(await p.locator('#main').textContent()), 'Remove: gone, and the empty list says so');
    check((await status(p)).devices.length === 1, 'Remove: the server has only this phone');

    // ---- the page at 360 px and at 1440 px ----
    await p.setViewportSize({width: 360, height: 800}); await p.waitForTimeout(300);
    check(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no sideways scroll at 360 px');
    await p.setViewportSize({width: 412, height: 900});
    const wide = await (await phone(b, {width: 1440, ua: DESK_UA, mode: 'subscribed', sub: k1.sub})).newPage();
    await wide.goto(BASE + 'phone'); await wide.evaluate(async () => { await navigator.serviceWorker.register('sw.js'); await navigator.serviceWorker.ready; });
    await wide.reload(); await wide.waitForTimeout(1500); await shot(wide, 'phone-1440');
    check(await wide.locator('#main .pstate').textContent() === 'Alerts are on for this computer', 'on a computer it says computer, not phone');
    check(!/Phone alerts/.test(await wide.locator('#realms').textContent()), '1440: the wide strip stays as it was (Phone alerts lives in the phone\'s More sheet)');
    await wide.context().close();


    // ---- turn off on this phone ----
    await p.locator('[data-do=off]').click(); await p.locator('#main .pstate.off').waitFor({timeout: 5000});
    check((await status(p)).devices.length === 0 && await p.evaluate(() => __t.unsub) === 1, 'Turn off: this phone stops, and the server forgets it');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
    await ctx.close();

    // ---- the page works when storage is not available ----
    ctx = await phone(b, {noStorage: true}); p = await open(ctx, '', 1800);
    check(await p.locator('#phoneHint').isVisible() && p.errors.length === 0, 'no storage: Today and its line still work ' + p.errors.join(' | '));
    await p.locator('#phoneHint [data-hint-off]').click();
    check(await p.locator('#phoneHint').isHidden(), 'no storage: "Not now" still hides it for now');
    await ctx.close();

    // ---- a learner has no way to the page ----
    fs.mkdirSync(CONF, {recursive: true}); const FILE = path.join(CONF, 'people.json');
    fs.writeFileSync(FILE, JSON.stringify({people: [{id: 'owner-one', name: 'Owner One', role: 'owner', logins: [OWNER]}, {id: 'learner-two', name: 'Learner Two', role: 'learner', logins: [LEARNER]}]}));
    const t = new Date(Date.now() + 5000); fs.utimesSync(FILE, t, t);
    try {
      ctx = await phone(b, {login: LEARNER}); p = await open(ctx, '', 1500);
      check(await p.locator('#phoneHint').isHidden(), 'learner: no line about phone alerts on Today');
      check(!/Phone alerts/.test(await p.locator('#tabbar').textContent() + await p.locator('#moreSheet').textContent()), 'learner: Phone alerts is not in her bar or a More sheet');
      const q = await open(ctx, 'phone');
      check(new URL(q.url()).pathname === new URL(BASE).pathname, `learner: the address lands her on Today (${new URL(q.url()).pathname})`);
      const r = await q.request.get(BASE + 'api/push/status');
      check(r.status() === 403 && /Only the owner/.test((await r.json()).error), 'learner: the server refuses her with a sentence');
      await ctx.close();
      const oc = await phone(b, {login: OWNER}); const o = await open(oc, '', 1200);
      await o.locator('#tabbar [data-more]').click(); await o.waitForTimeout(300);
      check(await o.locator('#moreList .srow', {hasText: 'Phone alerts'}).count() === 1, 'owner: Phone alerts is in the More sheet');
      await shot(o, 'more-412-owner');
      await o.locator('#moreList .srow', {hasText: 'Phone alerts'}).click(); await o.waitForURL(/\/phone$/);
      check(await o.locator('h1').textContent() === 'Phone alerts', 'owner: the More sheet opens the page');
      await oc.close();
    } finally { fs.renameSync(FILE, path.join(CONF, `people.json.set-aside-${Date.now()}`)); }

    await serviceWorker();

    // ---- the two listeners as plain functions too (a tap with no Elaia window open; a message that is not JSON) ----
    const calls = [];
    const self = {addEventListener() {}, registration: {scope: 'https://home.example/argus/', showNotification: (t, o) => { calls.push(['show', t, o]); return Promise.resolve(); }},
      clients: {matchAll: async () => [], openWindow: async u => calls.push(['open', u]), claim() {}}, skipWaiting() {}};
    const box = {self, URL, Promise, String, JSON}; vm.createContext(box); vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'web', 'sw.js'), 'utf8'), box);
    let pending; const ev = d => ({data: d, waitUntil: x => { pending = x; }});
    box.onPush(ev({json: () => { throw new Error('not json'); }, text: () => 'plain words'})); await pending;
    check(calls[0][0] === 'show' && calls[0][1] === 'plain words', 'a message that is not JSON still shows a notification');
    box.onPush(ev(null)); await pending;
    check(calls[1][1] === 'Elaia', 'an empty message still shows a notification ("Elaia")');
    box.onPush(ev({json: () => ({title: 'T', url: 'https://evil.example/x'})})); await pending;
    check(calls[2][2].data.url === 'https://home.example/argus/', 'a place outside Elaia opens Today instead');
    box.onTap({notification: {close() {}, data: {url: 'https://home.example/argus/argus'}}, waitUntil: x => { pending = x; }}); await pending;
    check(JSON.stringify(calls[3]) === '["open","https://home.example/argus/argus"]', 'a tap with no Elaia window open opens one at the place');
  } finally { await new Promise(z => fake.close(z)); }
});
