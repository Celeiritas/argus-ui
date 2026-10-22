// Test stand-in for a LeafyPlugin: loads its own JSON, then tries what a plugin must not be able to do.
const out = document.getElementById('out');
out.dataset.boot = String(Math.random());          // changes if the frame is ever reloaded
out.dataset.loaded = (await (await fetch('data.json')).json()).hello;
let freeze = 'blocked';
try {
  const r = await fetch('../../api/freeze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job: 'hermes-sort' }) });
  freeze = String(r.status);
} catch (e) { /* blocked by CORS: also fine */ }
let state = 'blocked';
try { await (await fetch('../../api/state')).json(); state = 'read'; } catch (e) { /* expected */ }
let server = 'blocked';      // a server plugin's API is Elaia's, not a static plugin's
try { await (await fetch('../../api/demo-server/ping')).json(); server = 'read'; } catch (e) { /* expected */ }
Object.assign(out.dataset, { freeze, state, server });
out.textContent = 'ready';
