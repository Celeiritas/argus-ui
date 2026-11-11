// Phone alerts (docs/phone-alerts.md): the page <base>/phone, owner only, and Today's one quiet line that leads to it.
// The phone buzzes for three kinds only: something stopped working, something needs his yes, the daily summary. The words a
// person reads never say "push", "subscription", "endpoint", "VAPID" or "service worker".
// The permission question comes only from a tap on "Turn on alerts on this phone", never on page load.
const phoneAlerts = (() => {
  const KINDS = [['broke', 'Something stopped working', 'A program on the server stopped doing its job.'],
    ['needs-yes', 'Something needs my yes', 'Argus waits for you before it restarts something.'],
    ['summary', 'Daily summary', 'One short message each morning about the day before.']];
  const PHONE = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent), THING = PHONE ? 'phone' : 'computer';
  const HINT_KEY = 'elaia-phone-hint';
  let st = null, me = null, msg = '', busy = false, last = '', asked = 0, installEv = null;
  // Chrome offers to install the page: keep the offer for our own button (Today and this page stay quiet otherwise)
  addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEv = e; if (here === 'phone') draw(); });
  addEventListener('appinstalled', () => { installEv = null; if (here === 'phone') draw(); });

  const can = () => isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const perm = () => { try { return can() ? Notification.permission : 'default'; } catch (e) { return 'default'; } };
  const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
  // the id the server gives this browser's address (the same sum, so the address itself never comes back to the page)
  const idOf = async endpoint => hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode('argus-push:' + endpoint))).slice(0, 16);
  const keyBytes = k => { const s = atob(k.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - k.length % 4) % 4)); return Uint8Array.from(s, c => c.charCodeAt(0)); };
  async function registration() { try { return await navigator.serviceWorker.getRegistration(url('')); } catch (e) { return null; } }
  async function subscription() { const r = can() && await registration(); try { return r ? await r.pushManager.getSubscription() : null; } catch (e) { return null; } }
  async function send(path, body) {
    try {
      const r = await fetch(url('api/push/' + path), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      const j = await r.json().catch(() => ({})); return {ok: r.ok && j.ok !== false, ...j, msg: j.msg || j.error || ''};
    } catch (e) { return {ok: false, msg: 'Elaia could not reach the server. Check that this ' + THING + ' is online, then try again.'}; }
  }
  // what the server says (available, this person's devices) and what this browser has; one question at a time
  async function load() {
    const sub = await subscription(), id = sub ? await idOf(sub.endpoint) : '';
    try {
      const r = await fetch(url('api/push/status' + (id ? '?device=' + id : '')), {cache: 'no-store'});
      st = r.ok ? await r.json() : {available: false, why: 'Elaia could not ask the server about alerts. Reload this page to try again.', devices: []};
    } catch (e) { st = {available: false, why: 'Elaia could not reach the server. Check that this ' + THING + ' is online, then reload this page.', devices: []}; }
    me = {sub, id, dev: (st.devices || []).find(d => d.this) || null}; asked = Date.now();
    return st;
  }
  const when = iso => { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString([], {month: 'long', day: 'numeric'}) + ', ' + d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}); };
  // where this device stands, in one of: unavailable, untrusted, cannot, blocked, on, off
  function state() {
    if (!st) return 'asking';
    if (!st.available) return 'unavailable';
    if (!can()) return 'cannot';
    if (perm() === 'denied') return 'blocked';
    if (me.sub && me.dev) return 'on';
    return st.trusted ? 'off' : 'untrusted';
  }
  const steps = list => `<ol class="psteps">${list.map(s => `<li>${s}</li>`).join('')}</ol>`;
  const INSTALL_STEPS = steps(['Open Elaia in Chrome on your phone.',
    'Tap the three dots <b>⋮</b> at the top right, then <b>Add to home screen</b> (it may say <b>Install app</b>).',
    'Open Elaia from its new icon on your home screen, come back to <b>Phone alerts</b> and tap <b>Turn on alerts on this phone</b>.']);
  const ALLOW_STEPS = steps(['Tap the small icon to the left of the web address. In the installed Elaia: hold its icon on the home screen and tap <b>App info</b>.',
    'Tap <b>Permissions</b> (or <b>Notifications</b>), then <b>Notifications</b>.',
    'Choose <b>Allow</b> (or turn on <b>Show notifications</b>), then come back here and tap <b>Turn on alerts on this phone</b>.']);
  function thisDevice(s) {
    const install = installEv ? `<button type="button" class="pbtn" data-do="install">Install Elaia on this ${THING}</button>` : '';
    const on = `<button type="button" class="pbtn primary" data-do="on">Turn on alerts on this ${THING}</button>`;
    const say = {
      asking: ['Checking this ' + THING + '…', ''],
      unavailable: ['Phone alerts are not available', `<p>${esc(st?.why)}</p>`],
      cannot: [`This browser cannot do it yet: add Elaia to your home screen first`, `<p>Three steps, in Chrome on Android:</p>${INSTALL_STEPS}${install}`],
      blocked: ['Notifications are blocked for this page', `<p>This ${THING} said no to notifications for Elaia earlier. To allow them again, in Chrome on Android:</p>${ALLOW_STEPS}`],
      untrusted: [`Alerts are off on this ${THING}`, `<p>${esc(st?.untrusted_why)}</p>${install}`],
      off: [`Alerts are off on this ${THING}`, `<p>One tap, then your ${THING} asks whether Elaia may send notifications: say <b>Allow</b>.</p><div class="prow">${on}${install}</div>`],
      on: [`Alerts are on for this ${THING}`, `<p>On since ${esc(when(me?.dev?.made))}.</p>${install}`],
    }[s];
    return `<section class="ppanel" aria-labelledby="pstate-h"><h2 class="pstate ${s}" id="pstate-h">${say[0]}</h2>${say[1]}</section>`;
  }
  function kinds() {
    const d = me.dev, mine = new Set(d.kinds || []);
    return `<section class="ppanel" aria-labelledby="pkinds-h"><h2 id="pkinds-h">What buzzes on this ${THING}</h2><ul class="pswitches">${KINDS.map(([k, label, what]) =>
      `<li><button type="button" class="pswitch" role="switch" aria-checked="${mine.has(k)}" data-kind="${k}"><span class="pk"><b>${label}</b><small>${what}</small></span><span class="ptrack" aria-hidden="true"><span class="pknob"></span></span></button></li>`).join('')}</ul></section>`;
  }
  function test() {
    const d = me.dev, res = d.last_error ? `<p class="pres bad">Last try: ${esc(d.last_error)}</p>` : d.last_ok ? `<p class="pres">Last message delivered to your ${THING}'s message service: ${esc(when(d.last_ok))}.</p>` : '';
    return `<section class="ppanel" aria-labelledby="ptest-h"><h2 id="ptest-h">Try it</h2><p>It should arrive within a few seconds, also when Elaia is closed.</p>
      <div class="prow"><button type="button" class="pbtn" data-do="test">Send a test buzz</button><button type="button" class="pbtn" data-do="off">Turn off on this ${THING}</button></div>${res}</section>`;
  }
  function others() {
    const list = (st?.devices || []).filter(d => !d.this);
    return `<section class="ppanel" aria-labelledby="pothers-h"><h2 id="pothers-h">Your other devices</h2>${list.length
      ? `<ul class="pdevices">${list.map(d => `<li><span><b>${esc(d.label || 'A device')}</b><small>${d.last_error ? esc(d.last_error) : 'On since ' + esc(when(d.made))}</small></span><button type="button" class="pbtn" data-do="forget" data-id="${esc(d.id)}" aria-label="Remove ${esc(d.label || 'this device')}">Remove</button></li>`).join('')}</ul>`
      : '<p>No other device gets alerts.</p>'}</section>`;
  }
  function draw() {
    if (here !== 'phone') return;
    const s = state();
    const html = `<section class="phone" aria-label="Phone alerts">
      <p class="plead">Your ${THING} can buzz when Elaia needs you: when something stops working, when something waits for your yes, and once a day with a short summary. It does not buzz when Argus fixed something by itself; that stays on the page and goes into the summary.</p>
      ${thisDevice(s)}${s === 'on' ? kinds() + test() : ''}${st && st.available ? others() : ''}
      <p class="psay" id="psay" role="status" aria-live="polite">${esc(msg)}</p></section>`;
    if (html === last) return;
    const f = document.activeElement, key = f?.closest?.('#main') && (f.dataset.do ? `[data-do="${f.dataset.do}"]${f.dataset.id ? `[data-id="${f.dataset.id}"]` : ''}` : f.dataset.kind ? `[data-kind="${f.dataset.kind}"]` : '');
    $('#main').innerHTML = html; last = html;
    if (key) $('#main ' + key)?.focus();            // a redraw keeps keyboard focus on the same control
  }
  const say = t => { msg = t; draw(); };
  const label = () => { const ua = navigator.userAgent;
    return (/Android/.test(ua) ? 'Android phone' : /iPhone|iPad/.test(ua) ? 'iPhone or iPad' : /Windows/.test(ua) ? 'Windows computer' : /Mac/.test(ua) ? 'Mac' : 'Device')
      + (/SamsungBrowser/.test(ua) ? ', Samsung Internet' : /Firefox/.test(ua) ? ', Firefox' : /Edg\//.test(ua) ? ', Edge' : /Chrome/.test(ua) ? ', Chrome' : ''); };

  async function turnOn() {
    let p = perm();
    try { p = await Notification.requestPermission(); } catch (e) { p = perm(); }
    if (p === 'denied') return say('');                // the blocked state says how to allow them again
    if (p !== 'granted') return say('Alerts stay off: the question closed without an answer. Tap the button again when you are ready.');
    say('Getting this ' + THING + ' ready…');
    let reg, sub;
    try { reg = await navigator.serviceWorker.register(url('sw.js')); await navigator.serviceWorker.ready; }
    catch (e) { return say('This ' + THING + ' could not get ready for alerts. Reload the page and try again.'); }
    try { sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: keyBytes(st.key)}); }
    catch (e) { return say('This ' + THING + ' could not sign up for alerts. Check that it is online, then try again.'); }
    const r = await send('subscribe', {subscription: sub.toJSON(), label: label(), kinds: KINDS.map(k => k[0])});
    if (!r.ok) { try { await sub.unsubscribe(); } catch (e) {} await load(); return say(r.msg || 'The server did not turn alerts on. Try again.'); }
    await load(); say(`Alerts are on for this ${THING}. Send a test buzz to see one.`);
  }
  async function turnOff() {
    const id = me.dev?.id;
    try { await me.sub?.unsubscribe(); } catch (e) {}
    const r = id ? await send('forget', {id}) : {ok: true};
    await load(); say(r.ok ? `Alerts are off on this ${THING}.` : r.msg);
  }
  async function toggle(b) {
    const k = b.dataset.kind, now = new Set(me.dev.kinds), was = now.has(k);
    if (was) now.delete(k); else now.add(k);
    b.setAttribute('aria-checked', String(!was));
    const r = await send('kinds', {id: me.dev.id, kinds: KINDS.map(x => x[0]).filter(x => now.has(x))});
    if (r.ok && r.device) { me.dev = r.device; st.devices = st.devices.map(d => d.id === r.device.id ? r.device : d);
      const w = KINDS.find(x => x[0] === k)[1]; say(`${w}: ${was ? 'off' : 'on'}.`); }
    else { b.setAttribute('aria-checked', String(was)); say(r.msg || 'That did not change. Try again.'); }
  }
  async function testBuzz() {
    const r = await send('test', {id: me.dev.id}); say(r.msg || 'The test buzz was not sent. Try again.');
    if (r.ok) { await wait(6000); if (here === 'phone') { await load(); draw(); } }
  }
  async function forget(id) {
    const d = st.devices.find(x => x.id === id), r = await send('forget', {id});
    await load(); say(r.ok ? `${d?.label || 'That device'} gets no more alerts.` : r.msg);
  }
  document.addEventListener('click', async e => {
    const b = e.target.closest('#main .phone button'); if (!b || busy) return;
    busy = true; b.disabled = true;
    try {
      if (b.dataset.kind) await toggle(b);
      else if (b.dataset.do === 'on') await turnOn();
      else if (b.dataset.do === 'off') await turnOff();
      else if (b.dataset.do === 'test') await testBuzz();
      else if (b.dataset.do === 'forget') await forget(b.dataset.id);
      else if (b.dataset.do === 'install' && installEv) { const ev = installEv; installEv = null; ev.prompt(); try { await ev.userChoice; } catch (x) {} draw(); }
    } finally { busy = false; b.disabled = false; last = ''; draw(); }
  });
  // the page: draw from what is known, then ask (the 15 s refresh asks again at most every 15 s, and never during a tap)
  async function show() { draw(); if (!busy && Date.now() - asked > 14000) { await load(); draw(); } }

  // Today: one quiet line for the owner when alerts could be on here and are off on this device; "Not now" hides it for good
  // on this device (localStorage, in try/catch: without storage the line simply can come back next time)
  const dismissed = () => { try { return localStorage.getItem(HINT_KEY) === 'off'; } catch (e) { return false; } };
  let hintAsked = false;
  async function hint() {
    const el = $('#phoneHint'); if (!el) return;
    const want = here === 'home' && role() === 'owner' && can() && perm() !== 'denied' && !dismissed();
    if (!want) { el.hidden = true; return; }
    if (!hintAsked) { hintAsked = true; await load(); }
    const show = st && st.available && st.trusted && !(me.sub && me.dev);
    if (!show || el.dataset.drawn) { el.hidden = !show; return; }
    el.dataset.drawn = '1';
    el.innerHTML = `<span>Your ${THING} can buzz when something needs you.</span><a href="${esc(url('phone'))}">Set up phone alerts</a><button type="button" data-hint-off>Not now</button>`;
    el.hidden = false;
    el.querySelector('[data-hint-off]').onclick = () => { try { localStorage.setItem(HINT_KEY, 'off'); } catch (e) {} el.hidden = true; };
  }
  return {show, hint, draw, state: () => state()};
})();
