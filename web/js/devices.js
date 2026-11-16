// Devices (4.51.0, docs/devices.md): Argus's list of the owner's devices, a panel on Watch, and its short line on Today.
// The list comes from GET api/devices (the owner's; the server reads ~/.config/argus-ui/devices.json and asks Tailscale,
// cached). Each device has one status from a small fixed set, shown as a word on a badge in that status's colour (the --dev-*
// tokens in argus.css), never colour alone: online, offline, can't tell, and for the server itself its Desktop / Game mode.
// A learner never sees any of it (Watch is not hers, and the line is the owner's only).
const devices = (() => {
  let data = null, failed = false, at = 0, busy = false, scrolled = false;
  const KIND = {pc: 'PC', laptop: 'Laptop', server: 'Server', phone: 'Phone', tablet: 'Tablet', console: 'Console', other: 'Device'};
  const STATUS = ['online', 'offline', 'unknown', 'desktop', 'game'];
  const cls = s => STATUS.includes(s) ? s : 'unknown';
  const nb = s => String(s).replace(/ /g, '\u00a0');          // a count and its word stay on one line
  // ask the server again, at most every 10 s (the page refreshes every 15 s; the server caches Tailscale's answer for 30 s).
  // fresh: Check again (the server asks Tailscale again if its answer is over 5 s old).
  async function ask(fresh) {
    if (role() !== 'owner' || busy || (!fresh && Date.now() - at < 10000)) return;
    busy = true; at = Date.now(); if (fresh) drawPanel();
    try { const r = await fetch(url('api/devices' + (fresh ? '?fresh=1' : '')), {cache: 'no-store'}); if (!r.ok) throw new Error(r.status); data = await r.json(); failed = false; }
    catch (e) { failed = true; }                                  // tried again on the next refresh (10 s on), never in a loop
    busy = false; drawPanel(); if (here === 'home') home.draw();
  }
  function drawPanel() {
    const box = $('#devbody'); if (!box) return;
    const had = document.activeElement?.classList?.contains('devagain');
    box.innerHTML = body(); if (had) $('#devbody .devagain')?.focus();
    if (location.hash === '#devices' && !scrolled && data) { scrolled = true; $('#devices')?.scrollIntoView({block: 'start'}); }
  }
  const when = t => { const d = new Date(t); return isNaN(d) ? '' : d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}); };
  function row(d) {
    const s = cls(d.status), parts = [KIND[d.kind] || 'Device'];
    if (d.self) parts.push('this machine');
    if (s === 'offline' && d.last_seen) parts.push(`last seen ${ago(d.last_seen)}`);
    if (s === 'unknown' && d.why) parts.push(d.why);
    const tip = s === 'offline' && d.last_seen ? ` title="Last seen ${esc(exact(d.last_seen))}"` : '';
    return `<li class="dev s-${s}"><span class="dw"><b>${esc(d.name)}</b><span${tip}>${esc(parts.join(' · ')).replace(/ · /g, '\u00a0· ')}</span></span><span class="dstat">${esc(d.label || s)}</span></li>`;
  }
  function body() {
    if (!data) return failed ? '<p class="quiet">Could not ask the server about your devices. It tries again with the next refresh.</p>' : '<p class="quiet">Checking your devices…</p>';
    if (data.problem) return `<div class="empty devbad"><b>The device list could not be read</b><span class="devwhy">${esc(data.problem)}</span> Fix that line in devices.json on the server: Argus reads the file again as soon as it changes. <a href="https://github.com/Celeiritas/argus-ui/blob/main/docs/devices.md">See how to write the list</a></div>`;
    if (!data.devices?.length) return `<div class="empty"><b>No devices listed yet</b>Argus shows each of your devices here, and whether it is on, once the server has a list of them. <a href="https://github.com/Celeiritas/argus-ui/blob/main/docs/devices.md">Learn how to list your devices</a></div>`;
    const t = when(data.checked);
    return `<ul class="devlist">${data.devices.map(row).join('')}</ul><p class="devmeta">${t ? `<span>Checked ${esc(t)}${failed ? ' · could not ask again' : ''}</span>` : ''}<button type="button" class="devagain"${busy ? ' aria-disabled="true"' : ''}>${busy ? 'Checking…' : 'Check again'}</button></p>`;
  }
  // Watch: the panel, after the task groups (core.js render())
  function panel() {
    ask();
    return `<section class="devices" id="devices" aria-labelledby="devices-h"><h2 id="devices-h">Devices</h2><div id="devbody">${body()}</div></section>`;
  }
  // Today: one line with a count for each status in its colour, that opens the list. Only when there is a list to show.
  function line() {
    if (role() !== 'owner') return '';
    ask();
    if (!data || data.problem || !data.devices?.length) return '';
    const n = {}; data.devices.forEach(d => { const s = ['desktop', 'game'].includes(d.status) ? 'online' : cls(d.status); n[s] = (n[s] || 0) + 1; });
    const word = {online: 'online', offline: 'offline', unknown: "can't tell"};
    const chips = ['online', 'offline', 'unknown'].filter(s => n[s]).map(s => `<span class="dchip s-${s}"><span class="ddot" aria-hidden="true"></span>${esc(nb(`${n[s]} ${word[s]}`))}</span>`).join('');
    return `<a class="devline" href="${WATCH}#devices"><b>Devices</b><span class="dchips">${chips}</span></a>`;
  }
  document.addEventListener('click', e => { if (e.target.closest('#devices .devagain')) ask(true); });
  return {panel, line, ask};
})();
