// Devices (4.51.0, docs/devices.md): Argus's list of the owner's devices, a panel on Watch, and its short line on Today.
// The list comes from GET api/devices (the owner's; the server reads ~/.config/argus-ui/devices.json and asks Tailscale,
// cached). Each device has one status from a small fixed set, shown as a word on a badge in that status's colour (the --dev-*
// tokens in argus.css), never colour alone: online, offline, can't tell, and for the server itself its Desktop / Game mode.
// A learner never sees any of it (Watch is not hers, and the line is the owner's only).
const devices = (() => {
  let data = null, failed = false, at = 0, busy = false, scrolled = false;
  const KIND = {pc: 'PC', laptop: 'Laptop', server: 'Server', phone: 'Phone', tablet: 'Tablet', console: 'Console', other: 'Device'};
  const STATUS = ['online', 'offline', 'unknown', 'desktop', 'game'];
  const WORD = {online: 'online', offline: 'offline', unknown: "can't tell"};
  const HELP = 'https://github.com/Celeiritas/argus-ui/blob/main/docs/devices.md';
  const cls = s => STATUS.includes(s) ? s : 'unknown';
  const nb = s => String(s).replace(/ /g, ' ');          // a count and its word stay on one line
  // the result of Check again, said once by a screen reader: one polite live region that is never redrawn (render() rebuilds
  // #main every 15 s, and a region made anew is often not read)
  const live = document.createElement('p'); live.className = 'sr'; live.id = 'devsay'; live.setAttribute('aria-live', 'polite'); document.body.append(live);
  const say = text => { live.textContent = ''; setTimeout(() => { live.textContent = text; }, 60); };
  // [[status, count]] for online / offline / can't tell; this machine in Desktop or Game mode counts as online
  function counts() {
    const n = {}; data.devices.forEach(d => { const s = ['desktop', 'game'].includes(d.status) ? 'online' : cls(d.status); n[s] = (n[s] || 0) + 1; });
    return ['online', 'offline', 'unknown'].filter(s => n[s]).map(s => [s, n[s]]);
  }
  const spoken = () => counts().map(([s, k]) => `${k} ${WORD[s]}`).join(', ');
  // ask the server again, at most every 10 s after the last answer (the page refreshes every 15 s; the server caches
  // Tailscale's answer for 30 s). fresh: Check again (the server asks Tailscale again if its answer is over 5 s old).
  // A request that takes over 12 s is given up, so Check again never stays stuck on a stalled connection.
  async function ask(fresh) {
    if (role() !== 'owner' || busy || (!fresh && Date.now() - at < 10000)) return;
    busy = true; at = Date.now(); if (fresh) drawPanel();
    try {
      const opt = {cache: 'no-store'}; if (AbortSignal.timeout) opt.signal = AbortSignal.timeout(12000);
      const r = await fetch(url('api/devices' + (fresh ? '?fresh=1' : '')), opt); if (!r.ok) throw new Error(r.status); data = await r.json(); failed = false;
    }
    catch (e) { failed = true; }                                  // tried again on the next refresh (10 s on), never in a loop
    finally { busy = false; at = Date.now(); }                    // counted from the answer: a slow one never starts the next at once
    drawPanel(); if (here === 'home') home.draw();
    if (fresh) say(failed ? 'Could not ask the server about your devices.' : data.problem ? 'The device list could not be read.'
      : data.devices?.length ? `Checked. ${data.probe_problem ? `${data.probe_problem}. ` : ''}${spoken()}.` : 'Checked. No devices listed.');
  }
  function drawPanel() {
    const box = $('#devbody'); if (!box) return;
    const had = document.activeElement?.classList?.contains('devagain');
    box.innerHTML = body(); if (had) $('#devbody .devagain')?.focus();
    if (location.hash === '#devices' && !scrolled && data) { scrolled = true; $('#devices')?.scrollIntoView({block: 'start'}); }
  }
  const when = t => { const d = new Date(t); return isNaN(d) ? '' : d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}); };
  // the kind word only when the name does not already say it ("Phone", not "Phone · Phone")
  const says = (name, word) => new RegExp(`(^|[^a-z0-9])${word}([^a-z0-9]|$)`, 'i').test(name);
  function row(d) {
    const s = cls(d.status), kind = KIND[d.kind] || 'Device', parts = says(d.name, kind) ? [] : [esc(kind)];
    if (d.self) parts.push('this machine');
    // the exact time is in the row itself (a phone and the keyboard have no hover)
    if (s === 'offline' && d.last_seen) parts.push(`<time datetime="${esc(d.last_seen)}">last seen ${esc(ago(d.last_seen))} (${esc(exact(d.last_seen))})</time>`);
    if (s === 'unknown' && d.why) parts.push(esc(d.why));
    const meta = parts.length ? `<span>${parts.join(' · ')}</span>` : '';
    return `<li class="dev s-${s}"><span class="dw"><b>${esc(d.name)}</b>${meta}</span><span class="dstat">${esc(d.label || s)}</span></li>`;
  }
  function body() {
    if (!data) return failed ? '<p class="quiet">Could not ask the server about your devices. It tries again with the next refresh.</p>' : '<p class="quiet">Checking your devices…</p>';
    if (data.problem) {
      // where to fix it, as the server read it: its file name, and the device's number when one device is wrong
      const fix = !data.file ? '' : `${data.device ? `Fix device ${esc(data.device)} in ${esc(data.file)}` : `Fix ${esc(data.file)}`} on the server: Argus reads the file again as soon as it changes. <a href="${HELP}">See how to write the list</a>`;
      return `<div class="empty devbad"><b>The device list could not be read</b><span class="devwhy">${esc(data.problem)}</span> ${fix}</div>`;
    }
    if (!data.devices?.length) return `<div class="empty"><b>No devices listed yet</b>Argus shows each of your devices here, and whether it is on, once the server has a list of them. <a href="${HELP}">Learn how to list your devices</a></div>`;
    const t = when(data.checked);
    // Tailscale could not be asked: said once, above the list; its rows say only "Can't tell"
    const probe = data.probe_problem ? `<p class="devprobe">${esc(data.probe_problem)}, so Argus can't tell which devices are on right now.</p>` : '';
    return `${probe}<ul class="devlist">${data.devices.map(row).join('')}</ul><p class="devmeta">${t ? `<span>Checked ${esc(t)}${failed ? ' · could not ask again' : ''}</span>` : ''}<button type="button" class="devagain"${busy ? ' aria-disabled="true"' : ''}>${busy ? 'Checking…' : 'Check again'}</button></p>`;
  }
  // Watch: the panel, after the task groups (core.js render())
  function panel() {
    ask();
    return `<section class="devices" id="devices" aria-labelledby="devices-h"><h2 id="devices-h">Devices</h2><div id="devbody">${body()}</div></section>`;
  }
  // Today: one line with a count for each status in its colour, that opens the list. Only when there is a list to show.
  // When the last ask failed, the line says so instead of counts that may be old.
  function line() {
    if (role() !== 'owner') return '';
    ask();
    if (!data || data.problem || !data.devices?.length) return '';
    const go = `${WATCH}#devices`;
    if (failed) return `<a class="devline" href="${go}" aria-label="Devices: could not reach the server. Open the list"><b>Devices</b><span class="dchips"><span class="dchip">Could not reach the server</span></span></a>`;
    const chips = counts().map(([s, k]) => `<span class="dchip s-${s}"><span class="ddot" aria-hidden="true"></span>${esc(nb(`${k} ${WORD[s]}`))}</span>`).join('');
    return `<a class="devline" href="${go}" aria-label="${esc(`Devices: ${spoken()}. Open the list`)}"><b>Devices</b><span class="dchips">${chips}</span></a>`;
  }
  document.addEventListener('click', e => { if (e.target.closest('#devices .devagain')) ask(true); });
  return {panel, line, ask};
})();
