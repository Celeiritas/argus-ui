// Argus UI - core: helpers, routing, sound, toasts, confirm dialog, rendering the task cards, Argus's eyes.
// Load order matters (classic scripts share one global scope): core, scene, powers, olympus, plugins, home, main.
let S = INIT, busy = false, realmsAt = null;   // realmsAt: the section the bar was last scrolled to
const $ = (s, e = document) => e.querySelector(s), $$ = (s, e = document) => [...e.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const wait = ms => new Promise(z => setTimeout(z, ms));
const RM = matchMedia('(prefers-reduced-motion: reduce)');      // reduced motion: skip particles/strikes, fade only
// works at http://<host>:8095/ and at https://<host>.<tailnet>.ts.net/argus/  (agent pages: <base>/<agent>)
const MOUNT = /^\/argus(\/|$)/.test(location.pathname) ? '/argus/' : '/';
const REST = location.pathname.slice(MOUNT.length - (location.pathname === '/argus' ? 1 : 0)).replace(/^\/+|\/+$/g, '');
const AGENT_KEYS = (S?.personas || []).map(p => p.key);
const PAGES = ['olympus', 'home'];                            // sections that are not agents (Home: docs/home.md)
const PLUGINS = S?.plugins || [];                             // LeafyPlugins: each has its own section (docs/leafy-plugin.md)
const here = [...AGENT_KEYS, ...PAGES, ...PLUGINS.map(p => p.id)].includes(REST.split('/')[0]) ? REST.split('/')[0] : null;
const plugin = PLUGINS.find(p => p.id === here) || null;
const BASE = MOUNT;
if (location.pathname === '/argus') history.replaceState(null, '', '/argus/');
const url = p => BASE + p;
// sections that are not about watching: Argus shrinks to the corner and the section's agent takes the centre
const SIDE = ['mentor', 'olympus', 'home'];
const side = SIDE.includes(here) || !!plugin, onOlympus = here === 'olympus';     // Olympus: a playground where the powers act on the scene
document.body.classList.toggle('side', side); document.body.classList.toggle('play', onOlympus);
let gaze = null, drag = null, armed = null, justDragged = false;   // what Argus watches; drag/armed belong to the god tools (powers.js)                                                // Argus watches whatever you throw on Olympus

/* ---------- sound ---------- */
let soundOn = true; try { soundOn = localStorage.getItem('argus-sound') !== 'off'; } catch (e) {}
const SFX = {freeze: 'static/sfx/freeze.mp3', thaw: 'static/sfx/thaw.mp3', bolt: 'static/sfx/bolt.mp3', hammer: 'static/sfx/hammer.mp3', burn: 'static/sfx/burn.mp3',
  seed: 'static/sfx/seed.mp3', bow: 'static/sfx/bow.mp3', arrowhit: 'static/sfx/arrowhit.mp3', dirt: 'static/sfx/dirt.mp3', rattle: 'static/sfx/rattle.mp3', bonedeath: 'static/sfx/bonedeath.mp3'};
const audio = Object.fromEntries(Object.entries(SFX).map(([k, v]) => { const a = new Audio(v); a.preload = 'auto'; a.volume = .8; return [k, a]; }));
function play(k) { if (!soundOn) return; try { const a = audio[k]; a.currentTime = 0; a.play().catch(() => {}); } catch (e) {} }
// overlapping copies (five seeds landing at once), or a sound made in the browser when the file isn't installed
function playOr(k, fallback) { if (!soundOn) return; const a = audio[k]; if (!a || a.error || a.networkState === 3) return fallback && fallback();
  try { const n = a.cloneNode(); n.volume = a.volume; n.play().catch(() => fallback && fallback()); } catch (e) {} }
function muteLabel() { $('#mute').textContent = soundOn ? 'Mute sounds' : 'Unmute sounds'; }
$('#mute').onclick = () => { soundOn = !soundOn; try { localStorage.setItem('argus-sound', soundOn ? 'on' : 'off'); } catch (e) {} muteLabel(); };
muteLabel();
let actx = null;
function alarmChime() {        // two soft beeps, made in the browser (no sound file needed)
  if (!soundOn) return;
  try {
    actx ||= new (window.AudioContext || window.webkitAudioContext)();
    [[880, 0], [660, .16], [880, .32]].forEach(([f, t]) => {
      const o = actx.createOscillator(), g = actx.createGain(), at = actx.currentTime + t;
      o.type = 'triangle'; o.frequency.value = f; o.connect(g); g.connect(actx.destination);
      g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(.12, at + .01); g.gain.exponentialRampToValueAtTime(.001, at + .14);
      o.start(at); o.stop(at + .15);
    });
  } catch (e) {}
}

/* ---------- toast (with an optional action, e.g. Undo) ---------- */
function toast(text, action) {
  const e = $('#toast'), b = $('#toastAct'); $('#toastText').textContent = text;
  b.hidden = !action; if (action) { b.textContent = action.label; b.onclick = () => { e.classList.remove('show'); action.fn(); }; }
  e.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove('show'), action ? 8000 : 4000);
}
// plain-language results; failures say what happened and what to do next, never blame the person
const SAY = {
  freeze: {ok: j => `${j} is stone: stopped, and its timer is paused.`, verb: 'freeze'},
  thaw: {ok: j => `${j} is thawed and back on its schedule.`, verb: 'thaw'},
  bolt: {ok: (j, m) => m.includes('restart') ? `${j} restarted.` : `${j} is running now.`, verb: 'run'},
};
function failText(act, job, msg) {
  if (/frozen/.test(msg)) return `${job} is stone, so it can't run. Thaw it first, then run it.`;
  if (/no answer/.test(msg)) return `Couldn't reach the server to ${SAY[act].verb} ${job}. Check that it's on, then try again.`;
  return `Couldn't ${SAY[act].verb} ${job} (${msg}). Try again in a moment.`;
}

/* ---------- confirm dialog: only when an action would interrupt a task that is running right now ---------- */
function confirmInterrupt(act, job) {
  return new Promise(done => {
    const d = $('#confirm'), back = document.activeElement;
    $('#cTitle').textContent = act === 'freeze' ? `Freeze running task "${job}"?` : `Restart task "${job}"?`;
    $('#cBody').textContent = act === 'freeze'
      ? `It's working right now. Freezing stops this run and pauses its timer. Thawing turns it back on, but this run won't resume.`
      : `It's an always-on task. Restarting stops it and starts it again, so anything it's doing right now is cut short.`;
    $('#cOk').textContent = act === 'freeze' ? 'Freeze task' : 'Restart task';
    const close = v => { d.close(); back?.focus?.(); done(v); };
    $('#cOk').onclick = () => close(true); $('#cCancel').onclick = () => close(false);
    d.oncancel = e => { e.preventDefault(); close(false); };          // Esc = Cancel
    d.onclick = e => { if (e.target === d) close(false); };            // click outside = Cancel
    d.showModal(); $('#cCancel').focus();                             // Cancel gets focus, never the destructive button
  });
}
const isRunning = c => c.dataset.state === 'running';

/* ---------- render ---------- */
function render() {
  if (!S) return;
  const me = S.personas.find(p => p.key === here);
  if (plugin) {
    $('.title h1').textContent = plugin.name; $('#sub').textContent = plugin.subtitle; document.title = `${plugin.name} · ${S.title || 'Argus'}`;
    $('#hero').hidden = !plugin.icon && !plugin.agent;                 // a plugin that took over an agent's section keeps the agent's icon
    if (plugin.icon || plugin.agent) $('#hero').src = plugin.icon ? url(`plugins/${plugin.id}/${plugin.icon}`) : `static/icons/${plugin.id}.png`;
  } else if (here === 'home') {
    const [hi, today] = home.greet(); $('.title h1').textContent = hi; $('#sub').textContent = today; document.title = `Home · ${S.title || 'Argus'}`;
    $('#hero').hidden = true;
  } else if (side && !onOlympus) {
    $('.title h1').textContent = me.name; $('#sub').textContent = me.domain; document.title = `${me.name} · ${S.title || 'Argus'}`;
    $('#hero').src = `static/icons/${here}.png`;
  } else if (onOlympus) {
    $('.title h1').textContent = 'Olympus'; $('#sub').textContent = 'Playground · powers, weather, seasons'; document.title = `Olympus · ${S.title || 'Argus'}`;
  } else { $('#sub').innerHTML = `${esc(S.subtitle)} · <b>${S.jobs.length}</b> tasks watched · updated ${esc(S.updated)}`; $('.title h1').textContent = S.title || 'Argus'; }
  const realm = (href, key, name, what, on) => `<a class="realm ${on ? 'on' : ''}" href="${href}" ${on ? 'aria-current="page"' : ''}><img src="static/icons/${key}.png" alt="">${key === 'argus' ? '<span class="dot" id="realmDot" hidden></span>' : ''}<span><b>${esc(name)}</b><small>${esc(what)}</small></span></a>`;
  $('#realms').innerHTML = `<a class="realm ${here === 'home' ? 'on' : ''}" href="${url('home')}" ${here === 'home' ? 'aria-current="page"' : ''}>${HOME_MARK}<span><b>Home</b><small>Overview</small></span></a>` +
    realm(url(''), 'argus', 'Argus', 'Watch', !side) +
    SIDE.filter(k => AGENT_KEYS.includes(k)).map(k => { const pl = PLUGINS.find(x => x.id === k), p = S.personas.find(x => x.key === k);
      return pl ? pluginRealm(pl, here === k) : realm(url(k), k, p.name, p.domain.split('·')[0].trim(), here === k); }).join('') +
    realm(url('olympus'), 'olympus', 'Olympus', 'Playground', onOlympus) +
    PLUGINS.filter(p => !SIDE.includes(p.id)).map(p => pluginRealm(p, here === p.id)).join('') +
    (S.soon || []).filter(x => !PLUGINS.some(p => p.name === x.name)).map(x => `<span class="realm soon" aria-disabled="true"><svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#A7B6C4" stroke-width="1.5"/><path d="M10 26 26 10M26 26 10 10" stroke="#C9A36A" stroke-width="2" stroke-linecap="round"/><path d="M23 9h4v4M13 9H9v4" stroke="#A7B6C4" stroke-width="1.5" fill="none"/></svg><span><b>${esc(x.name)}</b><small>${esc(x.what)} · coming later</small></span></span>`).join('');
  if (realmsAt !== here) {   // a phone scrolls the bar sideways: bring the section you are on into view, once per section
    const bar = $('.realms'), on = bar.querySelector('.realm.on'); if (on) realmsAt = here;   // a plugin's pill may arrive a moment later
    if (on && bar.scrollWidth > bar.clientWidth) bar.scrollLeft += on.getBoundingClientRect().left - bar.getBoundingClientRect().left - (bar.clientWidth - on.offsetWidth) / 2;
  }
  const by = {}; S.jobs.forEach(j => (by[j.persona] ||= []).push(j));
  const lone = {}; loneAlerts().forEach(a => (lone[a.job.split('-')[0]] ||= []).push(a));   // alerts with no task card of their own
  const shown = S.personas.filter(p => (by[p.key] || lone[p.key] || p.key === here) && !SIDE.includes(p.key));
  const tab = (k, label) => `<a href="${url(k)}" class="${here === k ? 'on' : ''}" ${here === k ? 'aria-current="page"' : ''}>${esc(label)}</a>`;
  $('#nav').innerHTML = `<a href="${url('')}" class="${here ? '' : 'on'}" ${here ? '' : 'aria-current="page"'}>All</a>` +
    shown.filter(p => !SIDE.includes(p.key)).map(p => tab(p.key, p.name)).join('');
  if (plugin) { look.retarget(); return leafy.show(plugin); }
  if (onOlympus) { look.retarget(); return playground.show(); }
  if (here === 'home') { look.retarget(); return home.show(); }
  const list = here ? shown.filter(p => p.key === here) : shown;
  $('#main').innerHTML = list.map(p => {
    const js = by[p.key] || [], ls = lone[p.key] || [];
    const c = s => js.filter(j => j.state === s).length, na = (S.alerts || []).filter(a => a.level === 'alert' && a.job.split('-')[0] === p.key).length;
    const counts = (na ? [`<span class="failed">${na} alert${na === 1 ? '' : 's'}</span>`] : []).concat(['failed', 'running', 'frozen'].filter(s => c(s)).map(s => `<span class="${s}">${c(s)} ${s === 'frozen' ? 'stone' : s}</span>`)).concat(`${js.length} task${js.length === 1 ? '' : 's'}`).join(' · ');
    return `<section class="persona" aria-labelledby="h-${p.key}"><a class="ph" href="${url(p.key)}"><img src="static/icons/${p.key}.png" alt=""><div><h2 id="h-${p.key}">${esc(p.name)}</h2><div class="dom">${esc(p.domain)}</div></div><div class="counts">${counts}</div></a>
      ${js.length || ls.length ? `<div class="grid">${ls.map(alertCard).join('')}${js.map(card).join('')}</div>` : `<div class="empty"><b>No ${esc(p.name)} tasks yet</b>Background jobs named <code>${esc(p.key)}-…</code> appear here on their own, so you can watch and run them. <a href="https://github.com/Celeiritas/argus-ui#which-jobs-show-up">Learn how to add a task</a></div>`}</section>`;
  }).join('') || `<div class="empty"><b>No tasks found</b>Argus shows systemd --user jobs whose names start with an agent's key. <a href="https://github.com/Celeiritas/argus-ui#which-jobs-show-up">Learn how to add a task</a></div>`;
  $$('.card.frozen').forEach(addStone);
  if (armed) arm(armed, true);
  look.retarget();
}
// A plugin's pill in the section bar: its own icon, the agent's icon when it took over an agent's section, or a plain laurel-and-blades mark.
const pluginMark = p => p.icon ? `<img src="${esc(url(`plugins/${p.id}/${p.icon}`))}" alt="">` : p.agent ? `<img src="static/icons/${esc(p.id)}.png" alt="">`
  : `<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#A7B6C4" stroke-width="1.5"/><path d="M10 26 26 10M26 26 10 10" stroke="#C9A36A" stroke-width="2" stroke-linecap="round"/><path d="M23 9h4v4M13 9H9v4" stroke="#A7B6C4" stroke-width="1.5" fill="none"/></svg>`;
// Home's pill: a plain four-square "overview" mark in the same frame (a placeholder until the owner approves art)
const HOME_MARK = `<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#A7B6C4" stroke-width="1.5"/><path d="M11 11h6v6h-6zM19 11h6v6h-6zM11 19h6v6h-6zM19 19h6v6h-6z" fill="none" stroke="#C9A36A" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
function pluginRealm(p, on) {
  return `<a class="realm ${on ? 'on' : ''}" href="${url(p.id)}" ${on ? 'aria-current="page"' : ''}>${pluginMark(p)}<span><b>${esc(p.name)}</b><small>${esc(p.subtitle || 'Plugin')}</small></span></a>`;
}
/* ---------- alert files (docs/alerts.md): an agent's message on its task's card, or a card of its own ---------- */
const alertsFor = j => (S.alerts || []).filter(a => a.job === j.job || (j.base && a.job === j.base));
const loneAlerts = () => (S.alerts || []).filter(a => !S.jobs.some(j => alertsFor(j).includes(a)));
function sectionName(id) {
  return (S.personas.find(p => p.key === id) || PLUGINS.find(p => p.id === id) || {name: id === 'olympus' ? 'Olympus' : id}).name;
}
function since(t) {
  const d = new Date(t); if (!t || isNaN(d)) return '';
  return d.toDateString() === new Date().toDateString() ? d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}) : d.toLocaleDateString([], {month: 'short', day: 'numeric'});
}
function alertNote(a) {
  const s = since(a.since);
  return `<p class="alert-msg ${a.level}"><b>${a.level === 'alert' ? 'Alert' : 'Warning'}:</b> ${esc(a.message)}${s ? ` <small>since ${esc(s)}</small>` : ''}${a.link ? ` <a href="${url(a.link)}">Open ${esc(sectionName(a.link))}</a>` : ''}</p>`;
}
function alertCard(a) {
  const p = a.job.split('-')[0];
  return `<article class="card alert-only ${a.level === 'alert' ? 'alerted' : 'warned'}" data-alert="${esc(a.file)}" data-canfreeze="false" data-canrun="false" aria-label="${esc(a.job)}, ${a.level === 'alert' ? 'alert' : 'warning'}">
   <div class="top"><div><div class="job">${esc(a.job.slice(p.length + 1))}</div><div class="unit">${esc(a.job)}</div></div><span class="pill ${a.level === 'alert' ? 'failed' : 'warn'}">${a.level === 'alert' ? 'alert' : 'warning'}</span></div>
   ${alertNote(a)}</article>`;
}
function card(j) {
  const fz = j.state === 'frozen', al = alertsFor(j), lvl = al.some(a => a.level === 'alert') ? 'alerted' : al.length ? 'warned' : '';
  return `<article class="card ${fz ? 'frozen' : ''} ${lvl}" data-job="${esc(j.job)}" data-state="${j.state}" data-canfreeze="${j.canfreeze}" data-canrun="${j.canrun !== false}" aria-label="${esc(j.job)}, ${fz ? 'stone (frozen)' : j.state}">
   <div class="top"><div><div class="job">${esc(j.name)}</div><div class="unit">${esc(j.job)}${j.runs > 1 ? ` · latest of ${j.runs} runs` : ''}</div></div><span class="pill ${j.state}">${fz ? 'stone' : j.state}</span></div>
   <dl><dt>Last</dt><dd title="${esc(j.last)}">${esc(j.last)}</dd><dt>Mem</dt><dd>${j.mem}</dd><dt>Next</dt><dd title="${esc(j.next)}">${esc(j.next)}</dd><dt>Wrote</dt><dd>${j.wrote}</dd>${fz ? `<dt>Stone</dt><dd class="wide">since ${esc(j.frozen_at)}</dd>` : ''}</dl>
   ${j.notes ? `<p class="notes">${esc(j.notes)}</p>` : ''}${al.map(alertNote).join('')}
   <div class="actions"><details data-log="${esc(j.job)}"><summary>Show log</summary><pre>Loading…</pre></details>
    ${j.canfreeze ? `<button type="button" data-act="${fz ? 'thaw' : 'freeze'}" aria-label="${fz ? 'Thaw' : 'Freeze'} ${esc(j.job)}">${fz ? 'Thaw' : 'Freeze'}</button>` : ''}
    ${j.canrun === false ? '' : `<button type="button" data-act="bolt" ${fz ? 'disabled' : ''} aria-label="Run ${esc(j.job)}${fz ? ' (thaw it first)' : ''}">Run</button>`}</div></article>`;
}
function markStone(c) { c.dataset.state = 'frozen'; const p = $('.pill', c); if (p) { p.className = 'pill frozen'; p.textContent = 'stone'; } }
function addStone(c) {
  if ($('.stone', c)) return;
  const s = document.createElement('div'); s.className = 'stone';
  s.innerHTML = `<svg viewBox="0 0 100 60" preserveAspectRatio="none"><path d="M8 0 L14 12 L10 22 L18 34 M60 0 L56 10 L64 18 L58 30 L66 44 M92 60 L86 48 L90 40 L82 30 M30 60 L34 50 L28 42" stroke="#22302a" stroke-width=".7" fill="none" opacity=".6" vector-effect="non-scaling-stroke"/></svg>`;
  c.prepend(s);
}
async function refresh() { if (busy) return; try { const r = await fetch(url('api/state'), {cache: 'no-store'}); S = await r.json(); const open = $$('details[open]').map(d => d.dataset.log); render(); open.forEach(k => { const d = $(`details[data-log="${CSS.escape(k)}"]`); if (d) { d.open = true; loadLog(d); } }); } catch (e) {} }
async function post(what, job) { const r = await fetch(url('api/' + what), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job})}); return r.json(); }
async function loadLog(d) { try { const r = await fetch(url('api/log/' + encodeURIComponent(d.dataset.log))); const j = await r.json(); $('pre', d).textContent = j.log || 'Nothing logged yet.'; } catch (e) { $('pre', d).textContent = "Couldn't load the log. Close and reopen it to try again."; } }
document.addEventListener('toggle', e => { if (e.target.matches('details[data-log]') && e.target.open) loadLog(e.target); }, true);
document.addEventListener('click', e => {
  if (armed) { const t = sceneTarget(armed, e.clientX, e.clientY); if (t) { e.preventDefault(); const n = armed; disarm(); return sceneCast(n, t); } }
  const c = e.target.closest('.card');
  if (armed && c && !e.target.closest('details')) { e.preventDefault(); return castArmed(c); }
  const b = e.target.closest('button[data-act]'); if (!b) return;
  if (b.dataset.act === 'bolt') zeusStrike(b.closest('.card')); else medusaCast(b.closest('.card'), b.dataset.act);
});

/* ---------- Argus eyes: follow the pointer, glare at a failed task, calm when all is well ---------- */
const look = (() => {
  const A = $('#argus'), svg = $('svg[viewBox="0 0 234 234"]', A), eyes = $$('.eye', svg).map(g => ({iris: $('.iris', g), max: +g.dataset.max, cx: +g.dataset.cx, cy: +g.dataset.cy}));
  let pointer = null, lastMove = 0, target = null, wander = {x: 0, y: 0, t: 0}, cur = eyes.map(() => [0, 0]), watched = null;   // watched: kept in view ahead of the pointer
  let lastInput = performance.now(), dozeAfter = 60000, drowsy = false, alarmed = false;   // a minute with no input and nothing wrong: he dozes (docs/fx.md "At rest")
  function aim(px, py) {
    const m = svg.getScreenCTM(); if (!m) return;
    eyes.forEach((e, i) => {
      const sx = m.a * e.cx + m.e, sy = m.d * e.cy + m.f;
      const dx = px - sx, dy = py - sy, d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 220);
      const tx = dx / d * e.max * k, ty = dy / d * e.max * .55 * k;
      const ease = RM.matches ? 1 : drowsy ? .06 : .25;                // drowsy: the eyes drift slowly
      cur[i][0] += (tx - cur[i][0]) * ease; cur[i][1] += (ty - cur[i][1]) * ease;
      e.iris.setAttribute('transform', `translate(${cur[i][0].toFixed(2)} ${cur[i][1].toFixed(2)})`);
    });
  }
  let lastBad = null;
  function retarget() {
    // a failed task, or an agent's alert file at level "alert" (docs/alerts.md): both make him glare and count in the badge
    const bad = (S?.jobs || []).filter(j => j.state === 'failed'), up = (S?.alerts || []).filter(a => a.level === 'alert'), n = bad.length + up.length;
    target = $('.card[data-state="failed"]') || $('.card.alerted');
    alarmed = n > 0; A.classList.toggle('glare', alarmed); A.classList.toggle('calm', !n);
    $('#alarm').hidden = !n; $('#alarmN').textContent = n > 1 ? n : '';
    const dot = $('#realmDot'); if (dot) { dot.hidden = !n; dot.textContent = n; }
    const say = n ? [bad.length && `${bad.length} task${bad.length === 1 ? '' : 's'} failed: ${bad.map(j => j.job).join(', ')}`,
      up.length && `${up.length} alert${up.length === 1 ? '' : 's'}: ${up.map(a => `${a.job}, ${a.message}`).join('; ')}`].filter(Boolean).join('. ') : 'all tasks well';
    A.setAttribute('aria-label', side ? `Argus: ${say}. Open the watch page` : `Argus, the watchman: ${say}`);
    if (lastBad !== null && n > lastBad) alarmChime();               // a short alarm only when something newly fails
    lastBad = n;
  }
  if (side) {
    A.setAttribute('role', 'link'); A.tabIndex = 0;
    A.onclick = () => location.href = url('');
    A.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); A.click(); } };
  }
  addEventListener('pointermove', e => { pointer = [e.clientX, e.clientY]; lastMove = performance.now(); }, {passive: true});
  addEventListener('focusin', e => { const r = e.target.getBoundingClientRect?.(); if (r && r.width) { pointer = [r.left + r.width / 2, r.top + r.height / 2]; lastMove = performance.now(); } });  // keyboard users get watched too
  function shut(ms) { A.classList.add('blink'); setTimeout(() => A.classList.remove('blink'), ms); }
  function blink() { if (!RM.matches) shut(drowsy ? 350 : 150); setTimeout(blink, 3500 + Math.random() * 5000); }   // drowsy: slower blinks
  setTimeout(blink, 4000);
  // any input wakes him with a blink; keyboard and touch count as much as the pointer
  function wake() { lastInput = performance.now(); if (drowsy) { drowsy = false; A.classList.remove('drowsy'); shut(150); } }
  ['pointermove', 'pointerdown', 'keydown', 'wheel', 'touchstart', 'focusin'].forEach(ev => addEventListener(ev, wake, {passive: true}));
  function tick(t) {
    if (!drowsy && !RM.matches && !alarmed && !drag && !watched && !gaze && t - lastInput > dozeAfter) { drowsy = true; A.classList.add('drowsy'); }   // never while something failed or is held
    if (drag) aim(drag.x, drag.y);                                   // he watches whatever you carry
    else if (watched?.isConnected) { const r = watched.getBoundingClientRect(); aim(r.left + r.width / 2, r.top + r.height / 2); }   // a button being held
    else if (gaze) aim(gaze.x, gaze.y);
    else if (pointer && t - lastMove < 2500) aim(...pointer);
    else if (target) { const r = target.getBoundingClientRect(); aim(r.left + r.width / 2, r.top + r.height / 2); }
    else if (!RM.matches) { if (t - wander.t > (drowsy ? 6000 : 2600)) { const r = A.getBoundingClientRect(); wander = {x: r.left + r.width / 2 + (Math.random() - .5) * (drowsy ? 300 : 700), y: r.top + r.height / 2 + Math.random() * (drowsy ? 160 : 400), t}; } aim(wander.x, wander.y); }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  // He reacts to what you do (docs/fx.md "Argus reacts"): 'wide' while something is about to happen (a hold), 'rest' after it,
  // 'nod' when it worked, 'wince' when it didn't, 'content' for a slow, contented blink (Needs you emptied). On a side page the
  // section's own medallion (#hero) nods or winces with him.
  // Only moves the art that is there (no new drawings); reduced motion keeps the eyes and drops the movement.
  const MOVES = {nod: [{transform: 'none'}, {transform: 'translateY(7%) rotate(-2deg)'}, {transform: 'none'}, {transform: 'translateY(4%)'}, {transform: 'none'}],
    wince: [{transform: 'none'}, {transform: 'translateX(-4%) rotate(-4deg)'}, {transform: 'translateX(3%) rotate(3deg)'}, {transform: 'translateX(-1%)'}, {transform: 'none'}]};
  function react(kind) {
    A.classList.toggle('wide', kind === 'wide');
    if (kind === 'content') { if (!RM.matches) { A.classList.add('content'); shut(400); setTimeout(() => A.classList.remove('content'), 800); } return; }
    if (!MOVES[kind]) return;
    if (kind === 'wince') shut(220);
    if (RM.matches) return;
    [A, side && $('#hero')].filter(e => e && !e.hidden && e.offsetWidth).forEach(e => e.animate(MOVES[kind], {duration: kind === 'nod' ? 700 : 420, easing: 'ease-in-out'}));
  }
  return {retarget, react, watch: el => { watched = el || null; }, doze: ms => { dozeAfter = ms; }};   // doze: how long before he dozes (tests shorten it)
})();
