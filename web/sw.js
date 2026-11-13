// Elaia's service worker: lets a phone install the page as an app, and shows phone alerts (docs/phone-alerts.md).
// Always fetches live data: the fetch listener does nothing, so every request goes to the network as usual.
self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());self.addEventListener('fetch',()=>{});

// The place an alert opens: its url is a section id or a path under the page ('' = Today). Only places inside Elaia's own
// address are opened; anything else opens Today.
function alertPlace(u, scope) {
  const base = new URL(scope);
  try {
    const to = new URL(String(u || '').replace(/^\/+/, ''), base);
    return to.origin === base.origin && to.pathname.startsWith(base.pathname) ? to.href : base.href;
  } catch (e) { return base.href; }
}
// A message arrived: ALWAYS show it (a browser may stop delivering to a page that receives a message and shows nothing).
// tag = what it is about, so a newer message about the same thing replaces the older one instead of stacking.
function onPush(e) {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = {title: e.data ? e.data.text() : ''}; }
  const title = String(d.title || 'Elaia').slice(0, 200), tag = String(d.tag || d.kind || 'elaia').slice(0, 64);
  e.waitUntil(self.registration.showNotification(title, {body: String(d.body || '').slice(0, 1000), tag, renotify: true,
    icon: 'static/argus-192.png', data: {url: alertPlace(d.url, self.registration.scope), kind: String(d.kind || '')}}));
}
// A tap on an alert: an open Elaia window comes to the front and goes to the alert's place; with none open, one opens there.
function onTap(e) {
  e.notification.close();
  const place = (e.notification.data && e.notification.data.url) || self.registration.scope;
  e.waitUntil(self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(list => {
    const w = list.find(c => c.url.startsWith(self.registration.scope));
    if (!w) return self.clients.openWindow(place);
    return Promise.resolve(w.focus()).catch(() => w).then(() => w.url === place ? w : w.navigate(place)).catch(() => self.clients.openWindow(place));
  }));
}

// ---- a new address (docs/phone-alerts.md "When the phone gets a new address") ----
// The browser may give this install a new address, or drop the old one (notifications switched off and on, an update).
// Then this signs up again with the same server key and tells the server which record the new address replaces, so the
// old record does not stay behind receiving nothing. It runs while Elaia is closed. Not every browser fires the event;
// the page does the same on its next "Turn on", from the id kept below.
// deviceStore: this browser's id and the server's key in IndexedDB "elaia", store "push", key "device", the one place
// the page (web/js/alerts.js) and this worker can both reach. Keep in step with deviceStore there. Any failure answers {}.
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
// the same id the server and the page give an address (sha256 of 'argus-push:' + address, first 16 hex digits)
async function idOf(endpoint) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('argus-push:' + endpoint));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('').slice(0, 16);
}
function keyBytes(k) { const s = atob(k.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - k.length % 4) % 4)); return Uint8Array.from(s, c => c.charCodeAt(0)); }
async function resubscribe(old, fresh) {
  const scope = self.registration.scope, pm = self.registration.pushManager, was = await deviceStore('get');
  let sub = fresh || await pm.getSubscription().catch(() => null), key = typeof was.key === 'string' ? was.key : '';
  if (!sub) {
    if (!key) {                                        // never kept: ask the server (the same answer the page gets)
      try { key = String((await (await fetch(new URL('api/push/status', scope), {credentials: 'same-origin', cache: 'no-store'})).json()).key || ''); } catch (e) {}
    }
    const k = key ? keyBytes(key) : old && old.options && old.options.applicationServerKey;
    if (!k) return;
    sub = await pm.subscribe({userVisibleOnly: true, applicationServerKey: k});
  }
  const id = await idOf(sub.endpoint), before = old && old.endpoint ? await idOf(old.endpoint) : String(was.id || '');
  // no label or kinds: the record keeps the ones it had. only_if_known: if that record is gone (Remove on another device,
  // or the server dropped a dead address), nothing is added back; Turn on on this device does that, when he wants it.
  const body = {subscription: sub.toJSON(), only_if_known: true};
  if (before && before !== id) body.replaces = before;
  const r = await fetch(new URL('api/push/subscribe', scope), {method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (r.ok) await deviceStore('put', {id, key: key || was.key || ''});
}
function onChange(e) { e.waitUntil(resubscribe(e.oldSubscription || null, e.newSubscription || null).catch(() => {})); }
// a new version of this worker: keep this browser's current id if nothing is kept yet (Elaia before 4.43 kept none), so
// a later new address can name it even if the page is not opened first
async function keepCurrent() {
  try {
    const sub = await self.registration.pushManager.getSubscription(); if (!sub) return;
    const was = await deviceStore('get'); if (!was.id) await deviceStore('put', {id: await idOf(sub.endpoint), key: was.key || ''});
  } catch (e) {}
}
self.addEventListener('activate', e => e.waitUntil(keepCurrent()));
self.addEventListener('push', onPush);
self.addEventListener('notificationclick', onTap);
self.addEventListener('pushsubscriptionchange', onChange);
