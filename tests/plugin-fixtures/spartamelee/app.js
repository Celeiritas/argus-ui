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
let storage = 'blocked';     // the sandbox's opaque origin throws here; its own address keeps notes (4.42.0)
try { localStorage.setItem('argus-test', 'kept'); storage = localStorage.getItem('argus-test') === 'kept' ? 'ok' : 'blocked'; } catch (e) { /* sandboxed */ }
Object.assign(out.dataset, { freeze, state, server, storage });
// On its own address (tests/own-origin.test.js) ?argus=<Elaia's address> makes it try Elaia from another origin, as the game could.
const argus = new URLSearchParams(location.search).get('argus');
if (argus) {
  const tries = {};
  try {                       // JSON POST from another origin: the browser asks first (OPTIONS) and gets no yes
    const r = await fetch(argus + 'api/freeze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job: 'hermes-sort' }) });
    tries.cors = String(r.status);
  } catch (e) { tries.cors = 'blocked'; }
  try {                       // a "simple" POST goes out without asking; Elaia must refuse it (json only, same-origin only)
    await fetch(argus + 'api/freeze', { method: 'POST', mode: 'no-cors', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ job: 'hermes-sort' }) });
    tries.simple = 'sent';
  } catch (e) { tries.simple = 'blocked'; }
  try { await (await fetch(argus + 'api/state')).json(); tries.read = 'read'; } catch (e) { tries.read = 'blocked'; }
  out.dataset.argusPost = tries.cors; out.dataset.argusSimple = tries.simple; out.dataset.argusState = tries.read;
}
out.textContent = 'ready';
