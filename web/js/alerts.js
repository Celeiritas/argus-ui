// Phone alerts (docs/phone-alerts.md): the page <base>/phone, owner only, and Today's one quiet line that leads to it.
// The phone buzzes for three kinds only: something stopped working, something needs his yes, the daily summary. The words a
// person reads never say "push", "subscription", "endpoint", "VAPID" or "service worker".
// The permission question comes only from a tap on "Turn on alerts on this phone", never on page load.
const phoneAlerts = (() => {
  const KINDS = [['broke', 'Something stopped working', 'A program on the server stopped doing its job.'],
    ['needs-yes', 'Something needs my yes', 'Argus waits for you before it restarts something.'],
    ['summary', 'Daily summary', 'One short message each morning about the day before.']];
  // a computer shows an alert, it does not buzz: the words follow the device (the page's name stays "Phone alerts")
  const PHONE = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent), THING = PHONE ? 'phone' : 'computer', BUZZ = PHONE ? 'buzz' : 'show an alert';
  const HINT_KEY = 'elaia-phone-hint';
  let st = null, me = null, msg = {text: '', at: 'state'}, busy = false, last = '', asked = 0, installEv = null;
  // Chrome offers to install the page: keep the offer for our own button (Today and this page stay quiet otherwise)
  addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEv = e; if (here === 'phone') draw(); });
  addEventListener('appinstalled', () => { installEv = null; if (here === 'phone') draw(); });

  const can = () => isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const perm = () => { try { return can() ? Notification.permission : 'default'; } catch (e) { return 'default'; } };
  const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
  // the id the server gives this browser's address (the same sum, so the address itself never comes back to the page)
  const idOf = async endpoint => hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode('argus-push:' + endpoint))).slice(0, 16);
  const keyBytes = k => { const s = atob(k.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - k.length % 4) % 4)); return Uint8Array.from(s, c => c.charCodeAt(0)); };
  // This browser's id and the server's key, kept where this page AND sw.js can read them (IndexedDB "elaia", store "push",
  // key "device"), so a new address can name the record it replaces, also while Elaia is closed. Keep in step with
  // deviceStore in sw.js. Any failure (no storage, a private window, blocked) answers {} within 3 s: alerts work without
  // it; only an old copy can then stay behind, and "Your other devices" points it out.
  function deviceStore(op, rec) {
    return new Promise(done => {
      const t = setTimeout(() => done({}), 3000), end = v => { clearTimeout(t); done(v); };
      try {
        const o = indexedDB.open('elaia', 1);
        o.onupgradeneeded = () => o.result.createObjectStore('push');
        o.onerror = () => end({});
        o.onsuccess = () => {
          const db = o.result;
          try {
            const tx = db.transaction('push', op === 'get' ? 'readonly' : 'readwrite'), s = tx.objectStore('push');
            const q = op === 'put' ? s.put(rec, 'device') : op === 'clear' ? s.delete('device') : s.get('device');
            tx.oncomplete = () => { db.close(); end(op === 'get' && q.result && typeof q.result === 'object' ? q.result : {}); };
            tx.onerror = tx.onabort = () => { db.close(); end({}); };
          } catch (e) { db.close(); end({}); }
        };
      } catch (e) { end({}); }
    });
  }
  let kept = {};                                     // what this page last put there (written again only when it changes)
  const keep = (id, key) => { if (kept.id === id && kept.key === key) return Promise.resolve(); kept = {id, key}; return deviceStore('put', kept); };
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
    if (me.dev && st.key) keep(id, st.key);           // the server knows this address: remember it as this browser's
    return st;
  }
  // One date style on the whole page, so one moment always reads the same: "today", "yesterday" or "November 11", with the
  // time after it where a time is shown ("today, 8:00 AM"). Calendar days, so a clock change never shifts them.
  const relDay = d => { const y = new Date(); y.setDate(y.getDate() - 1);
    return d.toDateString() === new Date().toDateString() ? 'today' : d.toDateString() === y.toDateString() ? 'yesterday' : d.toLocaleDateString([], {month: 'long', day: 'numeric'}); };
  const ago = iso => { const d = new Date(iso); return isNaN(d) ? '' : relDay(d) + ', ' + d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}); };
  const day = iso => { const d = new Date(iso); return isNaN(d) ? '' : relDay(d); };
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
  function thisDevice(s, n) {
    const install = installEv ? `<button type="button" class="pbtn" data-do="install"${dis()}>Install Elaia on this ${THING}</button>` : '';
    const on = `<button type="button" class="pbtn primary" data-do="on"${dis()}>Turn on alerts on this ${THING}</button>`;
    const say = {
      asking: ['Checking this ' + THING + '…', ''],
      unavailable: ['Phone alerts are not available', `<p>${esc(st?.why)}</p>`],
      cannot: [`This browser cannot do it yet: add Elaia to your home screen first`, `<p>Three steps, in Chrome on Android:</p>${INSTALL_STEPS}${install}`],
      blocked: ['Notifications are blocked for this page', `<p>This ${THING} said no to notifications for Elaia earlier. To allow them again, in Chrome on Android:</p>${ALLOW_STEPS}`],
      untrusted: [`Alerts are off on this ${THING}`, `<p>${esc(st?.untrusted_why)}</p>${install}`],
      off: [`Alerts are off on this ${THING}`, `<p>One tap, then your ${THING} asks whether Elaia may send notifications: say <b>Allow</b>.</p><div class="prow">${on}${install}</div>`],
      on: [`Alerts are on for this ${THING}`, `<p>On since ${esc(ago(me?.dev?.made))}.</p>${install}`],
    }[s];
    return `<section class="ppanel" aria-labelledby="pstate-h"><h2 class="pstate ${s}" id="pstate-h" tabindex="-1">${say[0]}</h2>${n}${say[1]}</section>`;
  }
  function kinds(n) {
    const d = me.dev, mine = new Set(d.kinds || []);
    return `<section class="ppanel" aria-labelledby="pkinds-h"><h2 id="pkinds-h">${PHONE ? 'What buzzes on this phone' : 'What shows an alert on this computer'}</h2><ul class="pswitches">${KINDS.map(([k, label, what]) =>
      `<li><button type="button" class="pswitch" role="switch" aria-checked="${mine.has(k)}" data-kind="${k}"><span class="pk"><b>${label}</b><small>${what}</small></span><span class="ptrack" aria-hidden="true"><span class="pknob"></span></span></button></li>`).join('')}</ul>${n}</section>`;
  }
  function test(n) {
    const d = me.dev, res = d.last_error ? `<p class="pres bad">Last try failed: ${esc(d.last_error)}</p>` : d.last_ok ? `<p class="pres">Last message delivered to your ${THING}'s message service: ${esc(ago(d.last_ok))}.</p>` : '';
    return `<section class="ppanel" aria-labelledby="ptest-h"><h2 id="ptest-h">Try it</h2><p>It should arrive within a few seconds, also when Elaia is closed.</p>
      <div class="prow"><button type="button" class="pbtn" data-do="test"${dis()}>${PHONE ? 'Send a test buzz' : 'Send a test alert'}</button><button type="button" class="pbtn" data-do="off"${dis()}>Turn off on this ${THING}</button></div>${n}${res}</section>`;
  }
  // One device row: when it was set up and when its message service last took a message (a failed last try has its own
  // line above, in the warning colour). The server only knows the service took it, never that the device showed it.
  // Devices with one name set up on one day (this device counts) would read the same, so those rows give the time too.
  const lastSeen = (d, time) => [day(d.made) ? `Set up ${esc(time ? ago(d.made) : day(d.made))}.` : '',
    d.last_ok ? `Last message delivered to its message service: ${esc(ago(d.last_ok))}.` : 'No message delivered to its message service yet.'].filter(Boolean).join(' ');
  const nameOf = d => (d.label || '').trim().toLowerCase(), madeOn = d => { const t = new Date(d.made); return isNaN(t) ? '' : t.toDateString(); };
  const twin = (d, all) => !!madeOn(d) && all.some(x => x !== d && nameOf(x) === nameOf(d) && madeOn(x) === madeOn(d));
  const made = d => Date.parse(d.made) || 0;
  // A record with this device's name whose message service last took a message clearly before this device's did: perhaps
  // this device from before its address changed (its message service may still take messages for a while, so the server
  // cannot tell). Only a hint, worded as an "if": names are not unique (every Windows PC on Chrome has the same one), so
  // it needs a delivery on both sides. A device with no delivery yet is never flagged, and two devices that took the same
  // broadcast are seconds apart.
  const fresh = d => Date.parse(d.last_ok) || 0;
  const oldCopy = d => !!me?.dev && nameOf(d) === nameOf(me.dev) && fresh(d) > 0 && fresh(d) < fresh(me.dev) - 60000;
  function othersPanel(n) {
    // newest set-up first, in every view (the server's own order is the order of sign-up, which differs per device)
    const all = st?.devices || [], list = all.filter(d => !d.this).sort((a, b) => made(b) - made(a) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    return `<section class="ppanel" aria-labelledby="pothers-h"><h2 id="pothers-h" tabindex="-1">Your other devices</h2>${n}${list.length
      ? `<ul class="pdevices">${list.map(d => `<li><span><b>${esc(d.label || 'A device')}</b>${d.last_error
        ? `<small class="perr"><strong>Last try failed:</strong> ${esc(d.last_error)}</small>` : ''}<small>${lastSeen(d, twin(d, all))}</small>${oldCopy(d)
        ? `<small class="pold">If this is an old copy of this ${THING}, Remove it.</small>` : ''}</span><button type="button" class="pbtn" data-do="forget" data-id="${esc(d.id)}"${dis()} aria-label="Remove ${esc(d.label || 'this device')}">Remove</button></li>`).join('')}</ul>`
      : '<p>No other device gets alerts.</p>'}</section>`;
  }
  // The answer to a tap appears inside the panel whose control was used, and is scrolled into view above the bottom bar
  // (html has scroll-padding-bottom for it). A screen reader hears it once, from one live region outside the redrawn part.
  const live = (() => { const p = document.createElement('p'); p.className = 'sr'; p.id = 'phoneSay'; p.setAttribute('role', 'status'); p.setAttribute('aria-live', 'polite'); document.body.appendChild(p); return p; })();
  const note = (at, here) => msg.text && at === here ? `<p class="psay">${esc(msg.text)}</p>` : '';
  // While a tap is being carried out the other buttons look and read unavailable (aria-disabled, never disabled: a disabled
  // button loses keyboard focus). The switches are never held: every press counts, in order.
  const dis = () => busy ? ' aria-disabled="true"' : '';
  let focusNext = '';
  const pick = sel => sel.split(', ').map(x => x && $('#main ' + x)).find(Boolean) || null;   // the first of a list that is there                                 // where focus goes when the control that had it is gone after an action
  const FALLBACK = {on: '[data-do="test"]', off: '[data-do="on"], #pstate-h', forget: '[data-do="forget"], #pothers-h', test: '[data-do="on"], #pstate-h', install: '#pstate-h'};
  function draw() {
    if (here !== 'phone') return;
    // the line under the title follows the device too (render() writes the phone's words just before it calls show())
    const sub = $('#sub'); if (sub) sub.textContent = `Argus · what makes your ${THING} ${BUZZ}`;
    const s = state(), others = st && st.available;
    // where the sentence shows: its own panel, or the state panel when that panel is gone (turned off)
    const at = (msg.at === 'kinds' || msg.at === 'test') && s !== 'on' ? 'state' : msg.at === 'others' && !others ? 'state' : msg.at;
    const html = `<section class="phone" aria-label="Phone alerts">
      <p class="plead">Your ${THING} can ${BUZZ} when Elaia needs you: when something stops working, when something waits for your yes, and once a day with a short summary. It does not ${PHONE ? 'buzz' : 'show one'} when Argus fixed something by itself; that stays on the page and goes into the summary.</p>
      ${thisDevice(s, note('state', at))}${s === 'on' ? kinds(note('kinds', at)) + test(note('test', at)) : ''}${others ? othersPanel(note('others', at)) : ''}</section>`;
    if (html === last) return;
    const f = document.activeElement, inPage = !!f?.closest?.('#main .phone');
    const key = inPage ? (f.dataset.do ? `[data-do="${f.dataset.do}"]${f.dataset.id ? `[data-id="${f.dataset.id}"]` : ''}` : f.dataset.kind ? `[data-kind="${f.dataset.kind}"]` : f.id ? '#' + f.id : '') : '';
    $('#main').innerHTML = html; last = html;
    if (!inPage && !focusNext) return;
    // keyboard and screen-reader focus stay on the same control; if it is gone, on the control that took its place
    const to = pick(focusNext) || (key && pick(key)) || (f?.dataset?.do && pick(FALLBACK[f.dataset.do] || '#pstate-h'));
    focusNext = '';
    to?.focus({preventScroll: true});
  }
  function say(text, at = 'state') {
    msg = {text, at}; draw();
    live.textContent = ''; requestAnimationFrame(() => { live.textContent = text; });
    if (text) $('#main .psay')?.scrollIntoView({block: 'nearest'});
  }
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
    // the record this browser had before its address changed (the browser can drop an address, e.g. when notifications are
    // switched off and on): the server retires it if it is his, and this one keeps its choices of what buzzes
    const was = await deviceStore('get'), id = await idOf(sub.endpoint), replaces = was.id && was.id !== id ? String(was.id) : '';
    const r = await send('subscribe', {subscription: sub.toJSON(), label: label(), ...(replaces ? {replaces} : {kinds: KINDS.map(k => k[0])})});
    if (!r.ok) { try { await sub.unsubscribe(); } catch (e) {} await load(); return say(r.msg || 'The server did not turn alerts on. Try again.'); }
    await keep(r.id || id, st.key);
    await load(); focusNext = '[data-do="test"]';     // "Turn on" is gone: the next step, Send a test buzz, takes its place
    say(`Done. ${PHONE ? 'Send a test buzz' : 'Send a test alert'} to see one.`);   // the heading above already says it is on
  }
  async function turnOff() {
    const id = me.dev?.id;
    try { await me.sub?.unsubscribe(); } catch (e) {}
    kept = {}; await deviceStore('clear');             // turned off on purpose: nothing for a later turn-on to replace
    const r = id ? await send('forget', {id}) : {ok: true};
    await load(); focusNext = '[data-do="on"], #pstate-h';
    say(r.ok ? `Done. This ${THING} gets no more alerts.` : r.msg);
  }
  // a switch: shown at once, sent in order (two quick presses are two changes); the server's answer is taken only when no
  // other press is still on its way
  let chain = Promise.resolve(), inFlight = 0;
  function toggle(b) {
    const k = b.dataset.kind, now = new Set(me.dev.kinds), was = now.has(k), w = KINDS.find(x => x[0] === k)[1];
    if (was) now.delete(k); else now.add(k);
    const want = KINDS.map(x => x[0]).filter(x => now.has(x));
    me.dev = {...me.dev, kinds: want}; b.setAttribute('aria-checked', String(!was)); inFlight++;
    chain = chain.then(async () => {
      const r = await send('kinds', {id: me.dev.id, kinds: want}); inFlight--;
      if (!r.ok || !r.device) { await load(); return say(r.msg || 'That did not change. Try again.', 'kinds'); }
      if (!inFlight) { me.dev = r.device; st.devices = st.devices.map(d => d.id === r.device.id ? r.device : d); }
      say(`${w}: ${was ? 'off' : 'on'}.`, 'kinds');
    });
    return chain;
  }
  async function testBuzz() {
    const r = await send('test', {id: me.dev.id}); say(r.msg || `The test ${PHONE ? 'buzz' : 'alert'} was not sent. Try again.`, 'test');
    // a look at the result a few seconds later, after the page is free again (never holding the buttons meanwhile)
    if (r.ok) setTimeout(async () => { if (here === 'phone' && !busy) { await load(); draw(); } }, 6000);
  }
  async function forget(id) {
    const d = st.devices.find(x => x.id === id), r = await send('forget', {id});
    await load(); focusNext = '[data-do="forget"], #pothers-h';
    say(r.ok ? `${d?.label || 'That device'} gets no more alerts.` : r.msg, 'others');
  }
  const panelOf = b => b.dataset.kind ? 'kinds' : b.dataset.do === 'forget' ? 'others' : b.dataset.do === 'test' || b.dataset.do === 'off' ? 'test' : 'state';
  document.addEventListener('click', async e => {
    const b = e.target.closest('#main .phone button'); if (!b) return;
    if (b.dataset.kind) return toggle(b);
    if (busy) return say('One moment: Elaia is still busy with your last tap.', panelOf(b));   // never a silent tap
    busy = true; $$('#main .phone .pbtn').forEach(x => x.setAttribute('aria-disabled', 'true'));
    try {
      if (b.dataset.do === 'on') await turnOn();
      else if (b.dataset.do === 'off') await turnOff();
      else if (b.dataset.do === 'test') await testBuzz();
      else if (b.dataset.do === 'forget') await forget(b.dataset.id);
      else if (b.dataset.do === 'install' && installEv) { const ev = installEv; installEv = null; ev.prompt(); try { await ev.userChoice; } catch (x) {} }
    } finally { busy = false; last = ''; draw(); }
  });
  // the page: draw from what is known, then ask (the 15 s refresh asks again at most every 15 s, and never during a tap)
  async function show() { draw(); if (!busy && !inFlight && Date.now() - asked > 14000) { await load(); draw(); } }

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
    el.innerHTML = `<span>Your ${THING} can ${BUZZ} when something needs you.</span><a href="${esc(url('phone'))}">${PHONE ? 'Set up phone alerts' : 'Set up alerts'}</a><button type="button" data-hint-off>Not now</button>`;
    el.hidden = false;
    el.querySelector('[data-hint-off]').onclick = () => { try { localStorage.setItem(HINT_KEY, 'off'); } catch (e) {} el.hidden = true; };
  }
  return {show, hint, draw, state: () => state()};
})();
