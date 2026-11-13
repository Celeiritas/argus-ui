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
// noIdb: 'throw' = IndexedDB blocked, 'hang' = it never answers. sessionStorage "t-next" = the address the next subscribe() gives
// (a browser that dropped its address and makes a new one).
function standIn({mode, sub, noStorage, noIdb}) {
  window.__t = {asked: 0, subscribed: 0, unsub: 0};
  if (noStorage) for (const k of ['localStorage', 'sessionStorage']) Object.defineProperty(window, k, {configurable: true, get() { throw new DOMException('blocked', 'SecurityError'); }});
  if (noIdb === 'throw') Object.defineProperty(window, 'indexedDB', {configurable: true, get() { throw new DOMException('blocked', 'SecurityError'); }});
  if (noIdb === 'hang') Object.defineProperty(window, 'indexedDB', {configurable: true, value: {open: () => ({})}});
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
  PushManager.prototype.subscribe = async function (o) { __t.subscribed++; __t.keyLength = new Uint8Array(o.applicationServerKey).length; ss.set('t-sub', ss.get('t-next') || JSON.stringify(sub)); return made(); };
}
async function phone(b, {mode = 'ok', width = 412, height = 900, login = OWNER, ua = PHONE_UA, noStorage = false, noIdb = '', sub} = {}) {
  const ctx = await b.newContext({viewport: {width, height}, userAgent: ua, extraHTTPHeaders: {'Tailscale-User-Login': login, 'X-Forwarded-For': '192.0.2.20'}});
  await ctx.addInitScript(standIn, {mode, sub: sub || phoneKeys('phone-1').sub, noStorage, noIdb});
  return ctx;
}
async function open(ctx, where = 'phone', wait = 1500) {
  const p = await ctx.newPage(); p.errors = []; p.on('pageerror', e => p.errors.push(String(e)));
  p.posts = []; p.sent = [];
  p.on('request', r => { if (r.method() !== 'POST') return; const at = new URL(r.url()).pathname.replace(/.*\/api\//, 'api/'); p.posts.push(at);
    let body = null; try { body = JSON.parse(r.postData() || 'null'); } catch (e) {} p.sent.push({path: at, body}); });
  await p.goto(BASE + where); await p.waitForTimeout(wait); return p;
}
const heading = p => p.locator('#main .pstate').textContent();
const status = async p => (await p.request.get(BASE + 'api/push/status')).json();
const idOf = e => crypto.createHash('sha256').update('argus-push:' + e).digest('hex').slice(0, 16);   // the server's device id
// what this browser keeps for a new address (IndexedDB "elaia", store "push", key "device"; alerts.js and sw.js deviceStore)
const kept = q => q.evaluate(() => new Promise(z => { const o = indexedDB.open('elaia', 1); o.onupgradeneeded = () => o.result.createObjectStore('push');
  o.onerror = () => z({error: String(o.error)}); o.onsuccess = () => { const g = o.result.transaction('push').objectStore('push').get('device'); g.onsuccess = () => { o.result.close(); z(g.result || {}); }; }; }));
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

      // A new address while Elaia is closed: the real worker's own listener, the real IndexedDB it shares with the page, the
      // real server. The event is dispatched by hand (Chromium has no way to make the browser fire it), and it brings the new
      // address itself, because a real subscribe() would contact the browser maker's push service.
      const kOld = phoneKeys('sw-old'), kNew = phoneKeys('sw-new');
      const r0 = await ctx.request.post(BASE + 'api/push/subscribe', {data: {subscription: kOld.sub, label: 'Android phone, Chrome', kinds: ['broke']}});
      const key = (await (await ctx.request.get(BASE + 'api/push/status')).json()).key;
      check(await worker.evaluate(() => typeof deviceStore === 'function' && typeof resubscribe === 'function'), 'the worker has its new-address handler');
      await worker.evaluate(r => deviceStore('put', r), {id: idOf(kOld.sub.endpoint), key});
      check((await kept(p)).id === idOf(kOld.sub.endpoint), 'what the worker keeps, the page reads (one store for both)');
      const after = await worker.evaluate(async ([s, login]) => {
        // Tailscale Serve adds the login to every request on the phone; here the worker's own fetch adds it, as the test page's do
        const f = self.fetch.bind(self); self.fetch = (u, o = {}) => f(u, {...o, headers: {...(o.headers || {}), 'Tailscale-User-Login': login, 'X-Forwarded-For': '192.0.2.20'}});
        let w; const e = new Event('pushsubscriptionchange'); e.waitUntil = x => { w = x; }; e.newSubscription = {endpoint: s.endpoint, toJSON: () => s};
        self.dispatchEvent(e); await w; self.fetch = f; return deviceStore('get');
      }, [kNew.sub, OWNER]);
      const s = await (await ctx.request.get(BASE + 'api/push/status')).json(), nd = s.devices.find(d => d.id === idOf(kNew.sub.endpoint));
      check(r0.status() === 200 && !s.devices.some(d => d.id === idOf(kOld.sub.endpoint)) && !!nd && nd.label === 'Android phone, Chrome' && JSON.stringify(nd.kinds) === '["broke"]',
        `pushsubscriptionchange in the real worker: the old record is replaced by the new address, keeping its name and switches (${JSON.stringify(s.devices.map(d => [d.id, d.label, d.kinds]))})`);
      check(after.id === idOf(kNew.sub.endpoint) && after.key === key, `and the worker keeps the new id with the same server key (${JSON.stringify(after)})`);
      // Removed (on another device, or by the sender after a dead address): the next new address must not sign it back up
      // (review F3, fix round 1; on 0b294e4 it came back as "This device" with every kind on)
      await ctx.request.post(BASE + 'api/push/forget', {data: {id: idOf(kNew.sub.endpoint)}});
      const kThird = phoneKeys('sw-third');
      const after2 = await worker.evaluate(async ([s, login]) => {
        const f = self.fetch.bind(self); self.fetch = (u, o = {}) => f(u, {...o, headers: {...(o.headers || {}), 'Tailscale-User-Login': login, 'X-Forwarded-For': '192.0.2.20'}});
        let w; const e = new Event('pushsubscriptionchange'); e.waitUntil = x => { w = x; }; e.newSubscription = {endpoint: s.endpoint, toJSON: () => s};
        self.dispatchEvent(e); await w; self.fetch = f; return deviceStore('get');
      }, [kThird.sub, OWNER]);
      const s2 = await (await ctx.request.get(BASE + 'api/push/status')).json();
      check(!s2.devices.some(d => d.id === idOf(kThird.sub.endpoint) || d.id === idOf(kNew.sub.endpoint)),
        `a removed device: its worker does not sign it back up at a new address (${JSON.stringify(s2.devices.map(d => [d.id, d.label]))})`);
      check(after2.id === idOf(kNew.sub.endpoint), `and the kept id stays as it was (${JSON.stringify(after2)})`);
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
    check(/Daily summary: off/.test(await p.locator('#main .psay').textContent()), 'a switch: it says what changed');

    // ---- a test buzz reaches the (fake) push service, encrypted, and reads right ----
    got.length = 0;
    await p.locator('[data-do=test]').click(); await p.waitForTimeout(1500);
    check(/within a few seconds, also when Elaia is closed/.test(await p.locator('#main .psay').textContent()), 'test buzz: it says what to expect');
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

    // ---- the fix round (R8 findings 2, 3, 4, 7): each of these failed on the reviewed head ----
    // 2: the answer to a tap shows where the thumb is: inside the visible screen, above the bottom bar, in the panel used
    const inView = q => q.evaluate(() => { const e = document.querySelector('#main .psay'); if (!e) return {ok: false, why: 'no sentence on the page'};
      const r = e.getBoundingClientRect(), bar = document.querySelector('#tabbar'), limit = bar && bar.offsetHeight ? bar.getBoundingClientRect().top : innerHeight;
      return {ok: r.top >= 0 && r.bottom <= limit, why: `${e.textContent} at ${r.top | 0}-${r.bottom | 0}, bar at ${limit | 0}`, text: e.textContent, panel: e.closest('.ppanel')?.getAttribute('aria-labelledby')}; });
    const heard = q => q.evaluate(() => new Promise(z => requestAnimationFrame(() => requestAnimationFrame(() => z(document.querySelector('#phoneSay')?.textContent || '')))));
    for (const [w, h] of [[412, 915], [360, 800]]) {
      if (w === 360) await new Promise(z => setTimeout(z, 10500));   // one test buzz per 10 seconds
      const kf = phoneKeys(`fix-${w}`), fc = await phone(b, {width: w, height: h, sub: kf.sub}), q = await open(fc);
      const step = async (what, act, panel, re) => {
        await act(); await q.waitForTimeout(900);
        const v = await inView(q);
        check(v.ok && re.test(v.text) && v.panel === panel, `${w}x${h} ${what}: the answer shows in its panel (${panel}), on screen above the bar (${v.why})`);
        check((await heard(q)) === v.text, `${w}x${h} ${what}: a screen reader hears the same sentence once`);
      };
      await step('Turn on', () => q.locator('[data-do=on]').click(), 'pstate-h', /^Done\. Send a test buzz to see one\.$/);
      await step('a switch', () => q.locator('.pswitch', {hasText: 'Daily summary'}).click(), 'pkinds-h', /Daily summary: off/);
      if (w === 412) await shot(q, 'p2-412-after-switch');
      await step('Send a test buzz', () => q.locator('[data-do=test]').click(), 'ptest-h', /within a few seconds/);
      if (w === 412) await shot(q, 'p2-412-after-test');
      await step('a second test at once (refused)', () => q.locator('[data-do=test]').click(), 'ptest-h', /One test buzz every 10 seconds/);
      const ko = phoneKeys(`fix-other-${w}`);
      await q.request.post(BASE + 'api/push/subscribe', {data: {subscription: ko.sub, label: 'Android tablet, Chrome', kinds: ['summary']}});
      await q.reload(); await q.waitForTimeout(1500);
      await step('Remove', () => q.locator('.pdevices [data-do=forget]').first().click(), 'pothers-h', /gets no more alerts/);
      await step('Turn off', () => q.locator('[data-do=off]').click(), 'pstate-h', /^Done\. This phone gets no more alerts\.$/);
      check(q.errors.length === 0, `${w}x${h}: no page errors ` + q.errors.join(' | '));
      await fc.close();
    }

    // 3: keyboard: focus stays on the control (or on the one that took its place); two Spaces on a switch are two changes
    {
      const kk = phoneKeys('keys'), kc = await phone(b, {sub: kk.sub}), q = await open(kc);
      const focused = () => q.evaluate(() => { const e = document.activeElement; return e === document.body ? 'body' : e.dataset.do ? 'do=' + e.dataset.do : e.dataset.kind ? 'kind=' + e.dataset.kind : e.id || e.tagName; });
      await q.locator('[data-do=on]').focus(); await q.keyboard.press('Enter'); await q.locator('#main .pstate.on').waitFor({timeout: 8000}); await q.waitForTimeout(400);
      check(await focused() === 'do=test', `Enter on "Turn on alerts": focus goes to "Send a test buzz", which took its place (${await focused()})`);
      const sw = q.locator('.pswitch[data-kind=summary]'); const before = q.posts.length;
      await sw.focus(); await q.keyboard.press('Space'); await q.keyboard.press('Space'); await q.waitForTimeout(1500);
      check(q.posts.slice(before).filter(x => x === 'api/push/kinds').length === 2, `two Spaces on a switch: two changes sent (${q.posts.slice(before).join()})`);
      check(await q.locator('.pswitch[data-kind=summary]').getAttribute('aria-checked') === 'true' && JSON.stringify(((await status(q)).devices.find(d => d.id === crypto.createHash('sha256').update('argus-push:' + kk.sub.endpoint).digest('hex').slice(0, 16)) || {}).kinds) === '["broke","needs-yes","summary"]', 'two Spaces on a switch: off and on again, the page and the server agree');
      check(await focused() === 'kind=summary', `after the switch, focus is still on it (${await focused()})`);
      await q.locator('.pswitch[data-kind=needs-yes]').focus(); await q.keyboard.press('Enter'); await q.waitForTimeout(900);
      check(await focused() === 'kind=needs-yes' && await q.locator('.pswitch[data-kind=needs-yes]').getAttribute('aria-checked') === 'false', `Enter on a switch: changed, focus stays (${await focused()})`);
      await q.locator('.pswitch[data-kind=needs-yes]').press('Enter'); await q.waitForTimeout(900);
      await q.locator('[data-do=test]').focus(); await q.keyboard.press('Enter'); await q.waitForTimeout(900);
      check(await focused() === 'do=test', `Enter on "Send a test buzz": focus stays (${await focused()})`);
      const k2 = phoneKeys('keys-other'), k3 = phoneKeys('keys-third');
      for (const k of [k2, k3]) await q.request.post(BASE + 'api/push/subscribe', {data: {subscription: k.sub, label: 'Android tablet, Chrome', kinds: ['summary']}});
      await q.reload(); await q.waitForTimeout(1500);
      await q.locator('.pdevices [data-do=forget]').first().focus(); await q.keyboard.press('Enter'); await q.waitForTimeout(1200);
      check(await focused() === 'do=forget' && await q.locator('.pdevices li').count() === 1, `Enter on "Remove": focus goes to the next Remove (${await focused()})`);
      await q.keyboard.press('Enter'); await q.waitForTimeout(1200);
      check(await focused() === 'pothers-h', `Enter on the last "Remove": focus goes to the list's heading (${await focused()})`);
      // 4: no silent dead time: "Turn off" 1.5 seconds after a test buzz works
      await q.waitForTimeout(10500);
      await q.locator('[data-do=test]').click(); await q.waitForTimeout(1500);
      await q.locator('[data-do=off]').focus(); await q.keyboard.press('Enter');
      await q.locator('#main .pstate.off').waitFor({timeout: 4000}).catch(() => {});
      check(await q.locator('#main .pstate').textContent() === 'Alerts are off on this phone', `"Turn off" 1.5 s after a test buzz works at once (${await q.locator('#main .pstate').textContent()})`);
      check(await focused() === 'do=on', `Enter on "Turn off": focus goes to "Turn on alerts", which took its place (${await focused()})`);
      check(q.errors.length === 0, 'keyboard: no page errors ' + q.errors.join(' | '));
      await kc.close();
    }
    // 4: while a tap is being carried out the other buttons read unavailable, and a tap on them says so
    {
      const kb = phoneKeys('busy'), bc = await phone(b, {sub: kb.sub}), q = await open(bc);
      await bc.route('**/api/push/subscribe', async r => { await new Promise(z => setTimeout(z, 1500)); await r.continue(); });
      await q.locator('[data-do=on]').click(); await q.waitForTimeout(500);
      const ad = await q.locator('#main .phone .pbtn').evaluateAll(es => es.map(e => e.getAttribute('aria-disabled')));
      check(ad.length > 0 && ad.every(x => x === 'true'), `while turning on, every button reads unavailable (${ad.join()})`);
      await q.waitForTimeout(2500);
      check(await q.locator('#main .phone .pbtn[aria-disabled]').count() === 0, 'and every one is available again right after');
      await bc.close();
    }
    // 7: on a computer it "can show an alert", Today's link says "Set up alerts"
    {
      const dc = await phone(b, {width: 1440, ua: DESK_UA, sub: phoneKeys('desk').sub}), q = await open(dc, '', 1800);
      check(await q.locator('#phoneHint span').textContent() === 'Your computer can show an alert when something needs you.' && await q.locator('#phoneHint a').textContent() === 'Set up alerts', `computer, Today: "${await q.locator('#phoneHint').innerText()}"`);
      await q.goto(BASE + 'phone'); await q.waitForTimeout(1500);
      check(/^Your computer can show an alert when Elaia needs you: .* It does not show one when Argus fixed something by itself/.test(await q.locator('.plead').textContent()), 'computer: the lead says "can show an alert"');
      check(await q.locator('h1').textContent() === 'Phone alerts', 'computer: the page is still called Phone alerts');
      await q.locator('[data-do=on]').click(); await q.locator('#main .pstate.on').waitFor({timeout: 8000});
      check(await q.locator('#pkinds-h').textContent() === 'What shows an alert on this computer' && await q.locator('[data-do=test]').textContent() === 'Send a test alert', 'computer: the switches\' heading and the test button say alert, not buzz');
      await shot(q, 'p2-1440-computer');
      await dc.close();
    }

    // ---- a new address retires its own old record (2026-11-12: one phone had two records, the old one receiving nothing) ----
    const forgetAll = async q => { for (const d of (await status(q)).devices) await q.request.post(BASE + 'api/push/forget', {data: {id: d.id}}); };
    {
      const ka = phoneKeys('same-phone-old'), kb = phoneKeys('same-phone-new'), rc = await phone(b, {sub: ka.sub}), q = await open(rc);
      await forgetAll(q); await q.reload(); await q.waitForTimeout(1200);
      await q.locator('[data-do=on]').click(); await q.locator('#main .pstate.on').waitFor({timeout: 8000});
      const key = (await status(q)).key;
      check(JSON.stringify(await kept(q)) === JSON.stringify({id: idOf(ka.sub.endpoint), key}), `Turn on: this browser keeps its id and the server's key where the service worker can read them too (${JSON.stringify(await kept(q))})`);
      await q.locator('.pswitch', {hasText: 'Daily summary'}).click(); await q.waitForTimeout(800);
      // the browser drops the address (as when notifications are switched off and on): the page has none, the server still has the old record
      await q.evaluate(s => { sessionStorage.removeItem('t-sub'); sessionStorage.setItem('t-next', JSON.stringify(s)); }, kb.sub);
      await q.reload(); await q.waitForTimeout(1500);
      check(await heading(q) === 'Alerts are off on this phone' && (await status(q)).devices.length === 1, `the address is gone: the page says off, the server still has the old record (${await heading(q)})`);
      const n0 = q.sent.length;
      await q.locator('[data-do=on]').click(); await q.locator('#main .pstate.on').waitFor({timeout: 8000});
      const sent = q.sent.slice(n0).find(x => x.path === 'api/push/subscribe');
      check(!!sent && sent.body.replaces === idOf(ka.sub.endpoint) && !('kinds' in sent.body), `Turn on again: the page names the record it replaces (${sent && JSON.stringify({replaces: sent.body.replaces, kinds: sent.body.kinds})})`);
      const s2 = await status(q);
      check(s2.devices.length === 1 && s2.devices[0].id === idOf(kb.sub.endpoint), `one record for this phone, at its new address (${s2.devices.map(d => d.id).join()})`);
      check(JSON.stringify((s2.devices[0] || {}).kinds) === '["broke","needs-yes"]', `and it keeps what he chose to buzz (${JSON.stringify((s2.devices[0] || {}).kinds)})`);
      check((await kept(q)).id === idOf(kb.sub.endpoint), 'the kept id is now the new one');
      check(await q.locator('.pdevices li').count() === 0 && /No other device/.test(await q.locator('#main').textContent()), 'no old copy left under "Your other devices"');
      await q.locator('[data-do=off]').click(); await q.locator('#main .pstate.off').waitFor({timeout: 5000});
      check(JSON.stringify(await kept(q)) === '{}', `Turn off: the kept id is cleared, so a later Turn on replaces nothing (${JSON.stringify(await kept(q))})`);
      check(q.errors.length === 0, 'a new address: no page errors ' + q.errors.join(' | '));
      await rc.close();
    }
    // the page works when IndexedDB is blocked or never answers (the kept id is a help, never a condition)
    for (const how of ['throw', 'hang']) {
      const kn = phoneKeys('no-idb-' + how), nc = await phone(b, {sub: kn.sub, noStorage: true, noIdb: how}), q = await open(nc);
      await q.locator('[data-do=on]').click(); await q.locator('#main .pstate.on').waitFor({timeout: 12000}).catch(() => {});
      check(await heading(q) === 'Alerts are on for this phone' && (await status(q)).devices.some(d => d.id === idOf(kn.sub.endpoint)), `no storage (IndexedDB ${how === 'throw' ? 'blocked' : 'never answers'}): Turn on still works (${await heading(q)})`);
      await q.locator('[data-do=off]').click(); await q.locator('#main .pstate.off').waitFor({timeout: 12000}).catch(() => {});
      check(await heading(q) === 'Alerts are off on this phone' && !(await status(q)).devices.some(d => d.id === idOf(kn.sub.endpoint)), `no storage (IndexedDB ${how}): Turn off still works`);
      check(q.errors.length === 0, `no storage (IndexedDB ${how}): no page errors ` + q.errors.join(' | '));
      await nc.close();
    }
    // "Your other devices": when each last took a message, and an old copy of this device pointed out next to its Remove.
    // The old copy's dates are set in the server's devices file (it is read on every request), as the 2026-11-12 one was.
    const DEVICES = path.join(HOME, '.local', 'state', 'argus-ui', 'push-devices.json');
    const backdate = (id, fields) => { const ds = JSON.parse(fs.readFileSync(DEVICES, 'utf8')); for (const d of ds) if (d.id === id) Object.assign(d, fields); fs.writeFileSync(DEVICES, JSON.stringify(ds, null, 1)); };
    const rowsOf = q => q.locator('.pdevices li').evaluateAll(es => es.map(e => ({id: e.querySelector('[data-do=forget]')?.dataset.id, name: e.querySelector('b').textContent,
      said: e.querySelector('small').textContent, old: e.querySelector('.pold')?.textContent || ''})));
    // Names are what label() makes: platform and browser only, so two live devices of the same kind share one (review F1).
    const dayOf = (q, iso) => q.evaluate(iso => new Date(iso).toLocaleDateString([], {month: 'long', day: 'numeric'}), iso);
    const SLOW = "The phone maker's message service did not answer in time. Elaia tried twice.";   // say_failure('timeout') in server/push.py
    // every Remove keeps its word inside its own border, and all of them are one width (review F4)
    const removeFits = q => q.locator('.pdevices [data-do=forget]').evaluateAll(es => es.map(e => { const r = document.createRange(); r.selectNodeContents(e);
      const t = r.getBoundingClientRect(), o = e.getBoundingClientRect(); return {fits: t.left >= o.left && t.right <= o.right, w: Math.round(o.width)}; }));
    for (const [w, h, ua, name] of [[412, 915, PHONE_UA, 'phone'], [360, 800, PHONE_UA, 'phone'], [1920, 1080, DESK_UA, 'computer']]) {
      const kn = phoneKeys(`list-${w}-this`), ko = phoneKeys(`list-${w}-old`), kt = phoneKeys(`list-${w}-other`), kf = phoneKeys(`list-${w}-newer`), kl = phoneKeys(`list-${w}-live`);
      const lc = await phone(b, {width: w, height: h, ua, sub: kn.sub}), q = await open(lc);
      await forgetAll(q);
      await q.locator('[data-do=on]').click(); await q.locator('#main .pstate.on').waitFor({timeout: 8000});
      const mine = (await status(q)).devices.find(d => d.id === idOf(kn.sub.endpoint)), L = mine.label, OTHER = name === 'phone' ? 'Windows computer, Chrome' : 'Android phone, Chrome';
      check(L === (name === 'phone' ? 'Android phone, Chrome' : 'Windows computer, Chrome'), `${w}x${h}: this device's name is the one label() makes (${L})`);
      for (const [k, label] of [[ko, L], [kt, OTHER], [kf, L], [kl, L]]) await q.request.post(BASE + 'api/push/subscribe', {data: {subscription: k.sub, label, kinds: ['summary']}});
      const y = new Date(); y.setDate(y.getDate() - 1); y.setHours(8, 0, 8, 0);
      const made2 = new Date(+y - 864e5).toISOString();
      backdate(idOf(ko.sub.endpoint), {made: made2, last_ok: y.toISOString()});                    // the same name, yesterday 08:00 was its last
      // 1) Right after Turn on this device has taken nothing yet: a same-named device that took yesterday's summary is not
      //    called a copy of it (on 0b294e4 the set-up time stood in for a delivery, and it was)
      await q.reload(); await q.waitForTimeout(1500);
      let rows = await rowsOf(q);
      check(rows.length === 4 && !rows.some(r => r.old), `${w}x${h}: just turned on, nothing taken yet: no row is called an old copy (${rows.map(r => r.name + ': ' + r.old).join(' | ')})`);
      // 2) This device took a message 5 minutes ago; kl, live with the same name, took the same one 2 s earlier; kt's last
      //    try failed after it took yesterday's; kf has the same name and has taken nothing yet
      const t0 = new Date(Date.now() - 5 * 6e4);
      backdate(idOf(kn.sub.endpoint), {last_ok: t0.toISOString()});
      backdate(idOf(kl.sub.endpoint), {made: made2, last_ok: new Date(+t0 - 2000).toISOString()});
      backdate(idOf(kt.sub.endpoint), {made: made2, last_ok: y.toISOString(), last_error: SLOW});
      await q.reload(); await q.waitForTimeout(1500);
      rows = await rowsOf(q); const row = k => rows.find(r => r.id === idOf(k.sub.endpoint)) || {};
      const eight = await q.evaluate(iso => new Date(iso).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}), y.toISOString());   // 8:00 AM in the browser's own words
      const set2 = `Set up ${await dayOf(q, made2)}.`, setNow = `Set up ${await dayOf(q, new Date().toISOString())}.`;
      check(rows.length === 4 && rows.filter(r => r.name === L).length === 3, `${w}x${h}: four other devices listed, three with this device's name (${rows.map(r => r.name).join(' | ')})`);
      check(row(ko).said === `${set2} Last message delivered to its message service: yesterday, ${eight}.` && row(ko).old === `If this is an old copy of this ${name}, Remove it.`,
        `${w}x${h}: the older same-named one says when it was set up and last took a message, and the hint is an "if" (${row(ko).said} / ${row(ko).old})`);
      check(row(kl).said.startsWith(`${set2} Last message delivered to its message service: `) && !row(kl).old,
        `${w}x${h}: two live devices with one name, the same broadcast seconds apart: not called a copy (${row(kl).said})`);
      check(row(kf).said === `${setNow} No message delivered to its message service yet.` && !row(kf).old, `${w}x${h}: the same name, nothing taken yet: not called a copy (${row(kf).said})`);
      check(row(kt).said === `${set2} Last try: ${SLOW} Last message delivered to its message service: yesterday, ${eight}.` && !row(kt).old,
        `${w}x${h}: an error row shows the failed try and the last success together (${row(kt).said})`);
      check(!/reached|arrived|showed|on the phone|on your phone/i.test(await q.locator('.pdevices').innerText()), `${w}x${h}: no row claims a message reached the device itself`);
      check(!/push|subscription|endpoint|vapid|service worker/i.test(await q.locator('#main').innerText()), `${w}x${h}: no technical word anywhere a person reads`);
      check(await q.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${w}x${h}: no sideways scroll`);
      check((await targets(q)).length === 0, `${w}x${h}: every control at least 44 px ` + (await targets(q)).join(', '));
      const fit = await removeFits(q);
      check(fit.length === 4 && fit.every(f => f.fits) && Math.max(...fit.map(f => f.w)) - Math.min(...fit.map(f => f.w)) <= 1,
        `${w}x${h}: every Remove keeps its word inside its button, all one width (${JSON.stringify(fit)})`);
      const c = await contrast(q, '.pdevices');
      check(c.bad.length === 0 && c.n >= 8, `${w}x${h}: the device list's text at least 4.5 to 1 (computed, ${c.n} texts, lowest ${c.min}) ${c.bad.join(', ')}`);
      const listEnd = x => x.evaluate(() => document.querySelector('.pdevices').scrollIntoView({block: 'end'}));   // every row in the picture, above the bottom bar
      await listEnd(q); await q.waitForTimeout(200);
      await shot(q, `${w}x${h}-devices-fix1`);
      if (w === 412) {
        // the same two live devices seen from the other one: this device is not called a copy there either
        const oc = await phone(b, {mode: 'subscribed', width: w, height: h, ua, sub: kl.sub}), o = await open(oc);
        await o.evaluate(async () => { await navigator.serviceWorker.register('sw.js'); await navigator.serviceWorker.ready; });
        await o.reload(); await o.waitForTimeout(1500);
        const there = await rowsOf(o), back = there.find(r => r.id === idOf(kn.sub.endpoint)) || {};
        check(await heading(o) === 'Alerts are on for this phone' && there.length === 4 && back.name === L && !back.old && there.filter(r => r.old).map(r => r.id).join() === idOf(ko.sub.endpoint),
          `two live devices with one name, seen from the other: neither is called a copy, only the older one is (${there.map(r => r.name + ': ' + (r.old || '-')).join(' | ')})`);
        await listEnd(o); await o.waitForTimeout(200);
        await shot(o, `${w}x${h}-devices-fix1-other-live`);
        check(o.errors.length === 0, 'the other live device: no page errors ' + o.errors.join(' | '));
        await oc.close();
        await q.locator(`.pdevices [data-do=forget][data-id="${idOf(ko.sub.endpoint)}"]`).click(); await q.waitForTimeout(1200);
        const left = await rowsOf(q);
        check(left.length === 3 && !left.some(r => r.old) && !(await status(q)).devices.some(d => d.id === idOf(ko.sub.endpoint)), `Remove next to the hint: the old copy is gone (${left.map(r => r.name).join(' | ')})`);
      }
      check(q.errors.length === 0, `${w}x${h}: no page errors ` + q.errors.join(' | '));
      await q.locator('[data-do=off]').click(); await q.waitForTimeout(1200);
      await forgetAll(q); await lc.close();
    }
    // 1: a phone turned on before there was a people file still counts afterwards (picture; the server side is in push_test.py)
    {
      const kp = phoneKeys('before-people'), pc = await phone(b, {sub: kp.sub}), q = await open(pc);
      await q.locator('[data-do=on]').click(); await q.locator('#main .pstate.on').waitFor({timeout: 8000});
      fs.mkdirSync(CONF, {recursive: true}); const PF = path.join(CONF, 'people.json');
      fs.writeFileSync(PF, JSON.stringify({people: [{id: 'owner-one', name: 'Owner One', role: 'owner', logins: [OWNER]}, {id: 'learner-two', name: 'Learner Two', role: 'learner', logins: [LEARNER]}]}));
      const t2 = new Date(Date.now() + 9000); fs.utimesSync(PF, t2, t2);
      try {
        await q.reload(); await q.waitForTimeout(1800);
        check(await q.evaluate(() => S.person) === 'owner-one' && await heading(q) === 'Alerts are on for this phone', `after a people file: still "Alerts are on for this phone" (${await heading(q)})`);
        await shot(q, 'p2-412-after-people-file');
      } finally { fs.renameSync(PF, path.join(CONF, `people.json.set-aside-${Date.now()}`)); }
      await q.locator('[data-do=off]').click(); await q.waitForTimeout(1200);
      await pc.close();
    }

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

    // ---- a new address while Elaia is closed (sw.js pushsubscriptionchange), every case, with a stand-in browser ----
    {
      const KEY = Buffer.concat([Buffer.from([4]), crypto.randomBytes(64)]).toString('base64url'), OLD = 'f1d8771f00000000';
      const mk = e => ({endpoint: e, toJSON: () => ({endpoint: e, keys: {p256dh: 'p', auth: 'a'}})});
      const world = ({store = {}, current = null, made = mk('https://push.example/new'), ok = true, statusKey = KEY} = {}) => {
        const w = {store: {...store}, puts: [], subscribed: [], fetched: [], listeners: {}};
        const self = {addEventListener: (t, f) => { (w.listeners[t] = w.listeners[t] || []).push(f); }, clients: {claim() {}}, skipWaiting() {},
          registration: {scope: 'https://home.example/argus/', pushManager: {getSubscription: async () => current,
            subscribe: async o => { w.subscribed.push(Buffer.from(Array.from(o.applicationServerKey)).toString('base64url') + (o.userVisibleOnly ? '' : ' (not user-visible)')); return made; }}}};
        const box = {self, URL, Promise, String, JSON, crypto: crypto.webcrypto, TextEncoder, atob, setTimeout, clearTimeout,
          fetch: async (u, o = {}) => { w.fetched.push({url: String(u), method: o.method || 'GET', body: o.body ? JSON.parse(o.body) : null, credentials: o.credentials, type: (o.headers || {})['Content-Type']});
            return String(u).endsWith('api/push/status') ? {ok: true, json: async () => ({key: statusKey})} : {ok, json: async () => ({})}; }};
        vm.createContext(box); vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'web', 'sw.js'), 'utf8'), box);
        box.deviceStore = async (op, rec) => { if (op === 'put') { w.puts.push(rec); w.store = rec; } if (op === 'clear') w.store = {}; return op === 'get' ? w.store : {}; };
        w.box = box; w.change = async ev => { let p; for (const f of w.listeners.pushsubscriptionchange || []) f({...ev, waitUntil: x => { p = x; }}); return p; };
        return w;
      };
      const posts = w => w.fetched.filter(f => f.method === 'POST');
      let w = world({store: {id: OLD, key: KEY}}); await w.change({}); let pp = posts(w);
      check(w.subscribed.join() === KEY && pp.length === 1 && pp[0].url === 'https://home.example/argus/api/push/subscribe' && pp[0].credentials === 'same-origin' && pp[0].type === 'application/json'
        && pp[0].body.replaces === OLD && pp[0].body.subscription.endpoint === 'https://push.example/new' && !('label' in pp[0].body) && !('kinds' in pp[0].body)
        && pp[0].body.only_if_known === true,
        `new address, the event names no old one: it signs up again with the kept key and replaces the kept id, only if that record is still there (${JSON.stringify(pp.map(x => x.body))})`);
      check(w.store.id === idOf('https://push.example/new') && w.store.key === KEY, 'and it keeps the new id, with the same key, for the next change');
      w = world({store: {id: '0123456789abcdef', key: KEY}});
      await w.change({oldSubscription: {endpoint: 'https://push.example/old', options: {}}, newSubscription: mk('https://push.example/given')}); pp = posts(w);
      check(w.subscribed.length === 0 && pp.length === 1 && pp[0].body.replaces === idOf('https://push.example/old') && pp[0].body.subscription.endpoint === 'https://push.example/given',
        `the event brings both addresses: no new sign-up, the old address's record is the one replaced (${JSON.stringify(pp.map(x => x.body.replaces))})`);
      w = world({}); await w.change({}); pp = posts(w);
      check(w.fetched[0].url === 'https://home.example/argus/api/push/status' && w.subscribed.join() === KEY && pp.length === 1 && !('replaces' in pp[0].body),
        `nothing kept (Elaia before 4.43): it asks the server for its key, signs up and names no record (${w.fetched.map(x => x.method + ' ' + x.url).join(', ')})`);
      w = world({store: {id: idOf('https://push.example/same'), key: KEY}, current: mk('https://push.example/same')}); await w.change({}); pp = posts(w);
      check(w.subscribed.length === 0 && pp.length === 1 && !('replaces' in pp[0].body), 'the same address as before: the server is told, nothing is replaced');
      w = world({store: {id: OLD, key: KEY}, ok: false}); await w.change({});
      check(w.puts.length === 0 && w.store.id === OLD, 'the server says no: the old id stays kept, so the page\'s next Turn on still names it');
      w = world({statusKey: ''}); await w.change({});
      check(w.subscribed.length === 0 && posts(w).length === 0, 'no key anywhere: nothing signed up, nothing sent');
      w = world({store: {id: OLD, key: KEY}}); w.box.fetch = async () => { throw new TypeError('offline'); };
      let settled = false; await w.change({}).then(() => { settled = true; });
      check(settled && w.puts.length === 0, 'offline: the event still finishes, and the old id stays kept');
      check((w.listeners.pushsubscriptionchange || []).length === 1 && (w.listeners.activate || []).length === 2, 'sw.js listens for a new address, and keeps the current id when a new version takes over');
      w = world({current: mk('https://push.example/current')}); await w.box.keepCurrent();
      check(w.store.id === idOf('https://push.example/current') && w.store.key === '', 'a new version of the worker keeps the current id when none is kept (an install from before 4.43)');
      w = world({store: {id: OLD, key: KEY}, current: mk('https://push.example/current')}); await w.box.keepCurrent();
      check(w.puts.length === 0, 'and leaves a kept id alone');
    }
  } finally { await new Promise(z => fake.close(z)); }
});
