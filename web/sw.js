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
self.addEventListener('push', onPush);
self.addEventListener('notificationclick', onTap);
