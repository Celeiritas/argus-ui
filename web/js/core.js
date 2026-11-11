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
const PAGES = ['olympus', 'home'];                            // sections that are not agents (Today, once called Home: docs/home.md)
const PLUGINS = S?.plugins || [];                             // LeafyPlugins: each has its own section (docs/leafy-plugin.md)
// Elaia opens on Today (here = 'home'): the bare address and its old name <base>/home. Watch is Argus's section, <base>/argus;
// <base>/<agent> is Watch showing one agent's tasks, and <base>/argus/argus Argus's own.
const SEG = REST.split('/');
const here = [...AGENT_KEYS, ...PAGES, ...PLUGINS.map(p => p.id)].includes(SEG[0]) ? SEG[0] : 'home';
const plugin = PLUGINS.find(p => p.id === here) || null;
const BASE = MOUNT;
if (location.pathname === '/argus') history.replaceState(null, '', '/argus/');
const url = p => BASE + p;
// Watch's address, written out: on a server mounted at / the address /argus is the mount itself, and the server drops a
// leading /argus either way, so /argus/argus is Watch at both mounts
const WATCH = '/argus/argus';
// sections that are not about watching: Argus shrinks to the corner and the section's agent takes the centre
const SIDE = ['mentor', 'olympus', 'home'];
const side = SIDE.includes(here) || !!plugin, onOlympus = here === 'olympus';     // Olympus: a playground where the powers act on the scene
const only = side ? null : here === 'argus' ? (SEG[1] === 'argus' ? 'argus' : null) : here;   // Watch: one agent's tasks, or all (null)
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
function muteLabel() { $$('#mute,#muteMore').forEach(b => b.textContent = soundOn ? 'Mute sounds' : 'Unmute sounds'); fitRealms(); }   // the strip's, and the More sheet's on a phone
// many sections on a laptop: before the bar wraps, the pills drop their second line (still read out), then the weather goes,
// then (4.28.0) the bar becomes one row that scrolls sideways like a phone's, with Mute sounds held at its right end
function fitRealms() {
  const bar = $('.realms'), first = bar.querySelector('.realm'), last = $('#mute');
  const wraps = () => last.getBoundingClientRect().top >= first.getBoundingClientRect().bottom;
  bar.classList.remove('compact', 'bare', 'scroll');
  if (getComputedStyle(bar).display === 'none') return;                                 // a phone: the bottom bar has the sections
  if (!first || getComputedStyle(bar).flexDirection === 'column' || !wraps()) return;   // the ultrawide rail is a column
  bar.classList.add('compact'); if (wraps()) bar.classList.add('bare'); if (wraps()) bar.classList.add('scroll');
}
let fitAt; addEventListener('resize', () => { cancelAnimationFrame(fitAt); fitAt = requestAnimationFrame(fitRealms); });
// a scrolling bar on a laptop: the mouse wheel moves it sideways (a phone swipes)
$('.realms').addEventListener('wheel', e => { const bar = e.currentTarget;
  if (bar.classList.contains('scroll') && Math.abs(e.deltaY) > Math.abs(e.deltaX)) { bar.scrollLeft += e.deltaY; e.preventDefault(); } }, {passive: false});
$('#mute').onclick = $('#muteMore').onclick = () => { soundOn = !soundOn; try { localStorage.setItem('argus-sound', soundOn ? 'on' : 'off'); } catch (e) {} muteLabel(); };
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
  freeze: {ok: j => `${j} is paused (frozen): stopped, and its timer waits.`, verb: 'pause'},
  thaw: {ok: j => `${j} is resumed and back on its schedule.`, verb: 'resume'},
  bolt: {ok: (j, m) => m.includes('restart') ? `${j} restarted.` : `${j} is running now.`, verb: 'run'},   // the server restarts an always-on task
};
function failText(act, job, msg) {
  if (/frozen/.test(msg)) return `${job} is paused (frozen), so it can't run. Resume it first, then run it.`;
  if (/no answer/.test(msg)) return `Couldn't reach the server to ${SAY[act].verb} ${job}. Check that it's on, then try again.`;
  return `Couldn't ${SAY[act].verb} ${job} (${msg}). Try again in a moment.`;
}

/* ---------- confirm dialog: only when an action would interrupt a task that is running right now ---------- */
function confirmInterrupt(act, job) {
  return new Promise(done => {
    const d = $('#confirm'), back = document.activeElement;
    $('#cTitle').textContent = act === 'freeze' ? `Pause running task "${job}"?` : `Restart task "${job}"?`;
    $('#cBody').textContent = act === 'freeze'
      ? `It's working right now. Pausing stops this run and holds its timer. Resuming turns it back on, but this run won't continue.`
      : `It's an always-on task. Restarting stops it and starts it again, so anything it's doing right now is cut short.`;
    $('#cOk').textContent = act === 'freeze' ? 'Pause task' : 'Restart task';
    const close = v => { d.close(); back?.focus?.(); done(v); };
    $('#cOk').onclick = () => close(true); $('#cCancel').onclick = () => close(false);
    d.oncancel = e => { e.preventDefault(); close(false); };          // Esc = Cancel
    d.onclick = e => { if (e.target === d) close(false); };            // click outside = Cancel
    d.showModal(); $('#cCancel').focus();                             // Cancel gets focus, never the destructive button
  });
}
const isRunning = c => c.dataset.state === 'running';

/* ---------- sections: one order for the phone's bottom bar, its More sheet and the wide screen's strip ---------- */
// Each place says the plain word first and the realm's name second, where it differs (docs/home.md "Finding your way").
const WORDS = {home: {word: 'Today'}, argus: {word: 'Watch', realm: 'Argus'}, mentor: {word: 'Study', realm: 'Mentor'},
  throne: {word: 'Approvals', realm: 'Zeus', icon: 'zeus'}, memory: {word: 'Backups', realm: 'Mnemosyne', icon: 'mnemosyne'},
  olympus: {word: 'Playground', realm: 'Olympus'}};
const PRIMARY = ['home', 'argus', 'mentor', 'throne'];        // the phone's bottom bar; every other place is under More
// Who sees which places. Until the server says who is asking, everyone is the owner; a learner sees Today and Study only.
const LEARNER = ['home', 'mentor'];
const role = () => S?.role === 'learner' ? 'learner' : 'owner';
function visible(list, who = role()) { return who === 'owner' ? list : list.filter(e => LEARNER.includes(e.id)); }
// Status v2 of every server plugin (docs/home.md): Today's rows and cards and the counts on the bar.
const STATUS = {};                                            // id -> its last answer (undefined: still asking, null: none)
let statusAsk = null;
function askStatus() {
  return statusAsk ||= Promise.all(PLUGINS.filter(p => p.kind === 'server').map(p => fetch(url(`api/${p.id}/status`), {cache: 'no-store'})
    .then(r => r.json()).then(j => j && j.line ? j : null).catch(() => null).then(v => { STATUS[p.id] = v; }))).then(() => { statusAsk = null; });
}
// what needs you in a place: a number when it is known, true when the place needs you but gives no number, 0 when nothing
function needCount(id) {
  if (id === 'argus') return (S?.jobs || []).filter(j => j.state === 'failed').length + (S?.alerts || []).filter(a => a.level === 'alert').length;
  const s = STATUS[id]; return s && s.needs ? (s.count > 0 ? s.count : true) : 0;
}
const icon = k => `<img src="static/icons/${esc(k)}.png" alt="">`;
const LINK_MARK = `<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#2A9D8F" stroke-width="1.5"/><path d="M20 11h5v5M25 11l-8 8M23 20v4a1 1 0 0 1-1 1H12a1 1 0 0 1-1-1V14a1 1 0 0 1 1-1h4" fill="none" stroke="#A7B6C4" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const BLADES = `<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#A7B6C4" stroke-width="1.5"/><path d="M10 26 26 10M26 26 10 10" stroke="#C9A36A" stroke-width="2" stroke-linecap="round"/><path d="M23 9h4v4M13 9H9v4" stroke="#A7B6C4" stroke-width="1.5" fill="none"/></svg>`;
// Today's mark (four squares) and More's (three dots), in the medallion frame: placeholders until the owner approves art
const HOME_MARK = `<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#A7B6C4" stroke-width="1.5"/><path d="M11 11h6v6h-6zM19 11h6v6h-6zM11 19h6v6h-6zM19 19h6v6h-6z" fill="none" stroke="#C9A36A" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
const MORE_MARK = `<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#A7B6C4" stroke-width="1.5"/><circle cx="11" cy="18" r="2.2" fill="#C9A36A"/><circle cx="18" cy="18" r="2.2" fill="#C9A36A"/><circle cx="25" cy="18" r="2.2" fill="#C9A36A"/></svg>`;
// A plugin's mark: its own icon, its god's medallion (WORDS: the Throne is Zeus's, Memory is Mnemosyne's), the agent's icon when
// it took over an agent's section, or the plain crossed-blades placeholder.
function pluginMark(p) {
  const god = WORDS[p.id]?.icon;
  return p.icon ? `<img src="${esc(url(`plugins/${p.id}/${p.icon}`))}" alt="">` : god && AGENT_KEYS.includes(god) ? icon(god) : p.agent ? icon(p.id) : BLADES;
}
// every place, in order: Today, Watch, Study, Approvals, then Backups, Playground, the other plugins, links to other pages
function sections() {
  const out = [], seen = new Set();
  const add = (id, href, name, mark) => { if (seen.has(id)) return; seen.add(id); const w = WORDS[id] || {}, word = w.word || name;
    out.push({id, href, word, realm: w.realm && w.realm !== word ? w.realm : '', mark}); };
  const sec = id => { const p = PLUGINS.find(x => x.id === id), a = S.personas.find(x => x.key === id);
    if (p) add(id, url(id), p.name, pluginMark(p)); else if (a && SIDE.includes(id)) add(id, url(id), a.name, icon(id)); };
  add('home', url(''), 'Today', HOME_MARK);
  add('argus', WATCH, 'Argus', icon('argus'));
  ['mentor', 'throne', 'memory'].forEach(sec);
  add('olympus', url('olympus'), 'Olympus', icon('olympus'));
  ['controllers', 'spartamelee', 'ariad-node'].forEach(sec);
  PLUGINS.forEach(p => sec(p.id));
  (S.links || []).forEach((x, i) => out.push({id: `link-${i}`, kind: 'link', href: x.href, word: x.name, realm: x.what || 'Opens another page', mark: LINK_MARK}));
  (S.soon || []).filter(x => !PLUGINS.some(p => p.name === x.name)).forEach((x, i) => out.push({id: `soon-${i}`, kind: 'soon', word: x.name, realm: `${x.what} · coming later`, mark: BLADES}));
  return out.map(e => ({...e, on: e.id === 'argus' ? !side : e.id === here, count: e.kind ? 0 : needCount(e.id)}));
}
const sumNeeds = list => { const n = list.reduce((s, e) => s + (e.count === true ? 0 : e.count), 0); return n || list.some(e => e.count === true); };
// a count when something needs you (red for Watch's failures, gold for what waits), said to a screen reader after the name
const badge = (n, cls, id) => n ? `<span class="${cls}"${id ? ` id="${id}"` : ''} aria-hidden="true">${n === true ? '' : n}</span>` : '';
const needSay = n => n ? `<span class="sr">, ${n === true ? 'needs you' : `${n} need${n === 1 ? 's' : ''} you`}</span>` : '';
const words = e => `<b>${esc(e.word)}</b>${e.realm ? `<small>${esc(e.realm)}</small>` : ''}${needSay(e.count)}`;
const cur = e => e.on ? ' aria-current="page"' : '';
function pill(e) {          // the strip on wider screens
  const inner = `${e.mark}${badge(e.count, 'dot', e.id === 'argus' ? 'realmDot' : '')}<span>${words(e)}</span>`;
  return e.kind === 'soon' ? `<span class="realm soon" aria-disabled="true">${inner}</span>`
    : `<a class="realm${e.on ? ' on' : ''}${e.kind === 'link' ? ' link' : ''}" href="${esc(e.href)}" data-id="${esc(e.id)}"${cur(e)}>${inner}</a>`;
}
function tab(e) {           // a slot of the phone's bottom bar
  return `<a class="tab${e.on ? ' on' : ''}" href="${esc(e.href)}" data-id="${esc(e.id)}"${cur(e)}><span class="tabicon">${e.mark}${badge(e.count, 'tabcount')}</span>${words(e)}</a>`;
}
function row(e) {           // a line of the More sheet
  const inner = `${e.mark}<span>${words(e)}</span>${badge(e.count, 'tabcount')}`;
  return `<li>${e.kind === 'soon' ? `<span class="srow soon" aria-disabled="true">${inner}</span>` : `<a class="srow${e.on ? ' on' : ''}" href="${esc(e.href)}" data-id="${esc(e.id)}"${cur(e)}>${inner}</a>`}</li>`;
}
const drawn = {};           // what each part of the bar was last drawn with: unchanged parts are not redrawn (focus stays put)
function put(el, html) { if (!el || drawn[el.id] === html) return false; drawn[el.id] = html; el.innerHTML = html; return true; }
function drawNav() {
  if (!S) return;
  const all = visible(sections()), prim = all.filter(e => PRIMARY.includes(e.id)), more = all.filter(e => !PRIMARY.includes(e.id));
  put($('#realms'), all.map(pill).join(''));
  const open = more.find(e => e.on);   // you are on a place inside More: the More slot is the current one and names it
  put($('#tabs'), prim.map(tab).join('') + (more.length ? `<button class="tab more${open ? ' on' : ''}" type="button" data-more aria-haspopup="dialog" aria-controls="moreSheet" aria-expanded="false"><span class="tabicon">${MORE_MARK}${badge(sumNeeds(more), 'tabcount')}</span><b>More</b>${open ? `<small>${esc(open.word)}</small><span class="sr">, ${esc(open.word)} is open</span>` : ''}${needSay(sumNeeds(more))}</button>` : ''));
  $('#tabbar').style.setProperty('--slots', prim.length + (more.length ? 1 : 0));
  put($('#moreList'), more.filter(e => !e.kind).map(row).join(''));
  const away = more.filter(e => e.kind);
  put($('#moreAway'), away.map(row).join('')); $('#moreAwayH').hidden = !away.length;
  fitRealms(); placeMarker();
  if (realmsAt !== here) {   // a scrolling strip: bring the section you are on into view, once per section
    const bar = $('.realms'), on = bar.querySelector('.realm.on'); if (on) realmsAt = here;   // a plugin's pill may arrive a moment later
    if (on && bar.scrollWidth > bar.clientWidth) bar.scrollLeft += on.getBoundingClientRect().left - bar.getBoundingClientRect().left - (bar.clientWidth - on.offsetWidth) / 2;
  }
}
// the bar's marker sits over the current slot; arriving from another section it slides over from the slot you left (200 ms)
function placeMarker() {
  const bar = $('#tabbar'), m = $('.tabmark', bar), on = bar.querySelector('.tab.on');
  if (!on || !bar.offsetWidth) { m.hidden = true; return; }
  m.hidden = false; const x = on.offsetLeft + on.offsetWidth / 2; m.style.left = x + 'px';
  if (placeMarker.done) return; placeMarker.done = true;
  let from = null; try { from = parseFloat(sessionStorage.getItem('elaia-tab')); sessionStorage.setItem('elaia-tab', String(x / bar.offsetWidth)); } catch (e) {}
  if (from >= 0 && Math.abs(from * bar.offsetWidth - x) > 2 && !RM.matches) { placeMarker.slid = true; m.animate([{transform: `translateX(${from * bar.offsetWidth - x}px)`}, {transform: 'none'}], {duration: 200, easing: 'ease-out'}); }
}
addEventListener('resize', () => requestAnimationFrame(placeMarker));
// More: a sheet with the other places, the links to other pages and the sound switch. Esc, Close or a tap outside closes it.
$('#tabbar').addEventListener('click', e => { const b = e.target.closest('[data-more]'); if (!b) return;
  const d = $('#moreSheet'); b.setAttribute('aria-expanded', 'true'); d.showModal(); ($('.srow.on', d) || $('#moreClose')).focus(); });
$('#moreSheet').addEventListener('close', () => { const b = $('#tabbar [data-more]'); b?.setAttribute('aria-expanded', 'false'); b?.focus(); });
$('#moreSheet').addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.close(); });   // the dimmed area around it
$('#moreClose').onclick = () => $('#moreSheet').close();

/* ---------- render ---------- */
function render() {
  if (!S) return;
  const me = S.personas.find(p => p.key === here), name = S.title || 'Elaia';
  const head = (h1, sub, title) => { $('.title h1').textContent = h1; $('#sub').textContent = sub; document.title = `${title} · ${name}`; };
  if (plugin) {
    const w = WORDS[plugin.id] || {}, word = w.word || plugin.name, god = w.icon && AGENT_KEYS.includes(w.icon) ? w.icon : null;
    head(word, w.realm ? [w.realm, plugin.name !== w.realm ? plugin.name : plugin.subtitle].filter(Boolean).join(' · ') : plugin.subtitle, word);
    $('#hero').hidden = !plugin.icon && !plugin.agent && !god;          // a plugin that took over an agent's section keeps the agent's icon
    if (!$('#hero').hidden) $('#hero').src = plugin.icon ? url(`plugins/${plugin.id}/${plugin.icon}`) : `static/icons/${god || plugin.id}.png`;
  } else if (here === 'home') {
    head(name, home.greet().join(' · '), 'Today'); $('#hero').hidden = true;
  } else if (side && !onOlympus) {
    const w = WORDS[here] || {}; head(w.word || me.name, w.realm ? `${w.realm} · ${me.domain}` : me.domain, w.word || me.name);
    $('#hero').src = `static/icons/${here}.png`;
  } else if (onOlympus) {
    head('Playground', 'Olympus · powers, weather, seasons', 'Playground');
  } else {
    $('.title h1').textContent = 'Watch'; document.title = `Watch · ${name}`;
    $('#sub').innerHTML = `Argus · <b>${S.jobs.length}</b> tasks watched · updated ${esc(S.updated)}`;
  }
  drawNav(); askStatus().then(drawNav);
  const by = {}; S.jobs.forEach(j => (by[j.persona] ||= []).push(j));
  const lone = {}; loneAlerts().forEach(a => (lone[a.job.split('-')[0]] ||= []).push(a));   // alerts with no task card of their own
  const shown = S.personas.filter(p => (by[p.key] || lone[p.key] || p.key === only) && !SIDE.includes(p.key));
  const chip = (k, label, href) => `<a href="${href}" class="${only === k ? 'on' : ''}" ${only === k ? 'aria-current="page"' : ''}>${esc(label)}</a>`;
  $('#nav').innerHTML = chip(null, 'All', WATCH) + shown.map(p => chip(p.key, p.name, p.key === 'argus' ? WATCH + '/argus' : url(p.key))).join('');
  if (plugin) { look.retarget(); return leafy.show(plugin); }
  if (onOlympus) { look.retarget(); return playground.show(); }
  if (here === 'home') { look.retarget(); return home.show(); }
  // trouble first: failed (or alerted), then running, then ok, then the rest; groups ordered by their worst card
  const rank = j => j.state === 'failed' || alertsFor(j).some(a => a.level === 'alert') ? 0 : j.state === 'running' ? 1 : j.state === 'ok' ? 2 : 3;
  const worst = p => Math.min(4, ...(by[p.key] || []).map(rank), ...(lone[p.key] || []).map(a => a.level === 'alert' ? 0 : 2));
  const list = (only ? shown.filter(p => p.key === only) : shown).map((p, i) => [p, i]).sort((a, b) => worst(a[0]) - worst(b[0]) || a[1] - b[1]).map(x => x[0]);
  $('#main').innerHTML = list.map(p => {
    const js = (by[p.key] || []).map((j, i) => [j, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(x => x[0]), ls = lone[p.key] || [];
    const c = s => js.filter(j => j.state === s).length, na = (S.alerts || []).filter(a => a.level === 'alert' && a.job.split('-')[0] === p.key).length;
    const counts = (na ? [`<span class="failed">${na} alert${na === 1 ? '' : 's'}</span>`] : []).concat(['failed', 'running', 'frozen'].filter(s => c(s)).map(s => `<span class="${s}">${c(s)} ${s}</span>`)).concat(`${js.length} task${js.length === 1 ? '' : 's'}`).join(' · ');
    return `<section class="persona" aria-labelledby="h-${p.key}"><a class="ph" href="${p.key === 'argus' ? WATCH + '/argus' : url(p.key)}"><img src="static/icons/${p.key}.png" alt=""><div><h2 id="h-${p.key}">${esc(p.name)}</h2><div class="dom">${esc(p.domain)}</div></div><div class="counts">${counts}</div></a>
      ${js.length || ls.length ? `<div class="grid">${ls.map(alertCard).join('')}${js.map(card).join('')}</div>` : `<div class="empty"><b>No ${esc(p.name)} tasks yet</b>Background jobs named <code>${esc(p.key)}-…</code> appear here on their own, so you can watch and run them. <a href="https://github.com/Celeiritas/argus-ui#which-jobs-show-up">Learn how to add a task</a></div>`}</section>`;
  }).join('') || `<div class="empty"><b>No tasks found</b>Argus shows systemd --user jobs whose names start with an agent's key. <a href="https://github.com/Celeiritas/argus-ui#which-jobs-show-up">Learn how to add a task</a></div>`;
  $$('.card.frozen').forEach(addStone);
  if (armed) arm(armed, true);
  look.retarget();
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
// A task's card. Words: "frozen" (Medusa's stone), Pause / Resume, and Run for a task that starts and ends, Restart for an
// always-on one (as the server's bolt does). Pause sits apart from Run (24 px), so a thumb can't hit the wrong one.
const always = j => j.next === 'always on';
function card(j) {
  const fz = j.state === 'frozen', al = alertsFor(j), lvl = al.some(a => a.level === 'alert') ? 'alerted' : al.length ? 'warned' : '';
  const go = always(j) ? 'Restart' : 'Run', why = (j.state === 'failed' || j.works === false) && j.reason;   // why it failed, when the server says
  return `<article class="card ${fz ? 'frozen' : ''} ${lvl}" data-job="${esc(j.job)}" data-state="${j.state}" data-canfreeze="${j.canfreeze}" data-canrun="${j.canrun !== false}" aria-label="${esc(j.job)}, ${fz ? 'frozen (paused)' : j.state}">
   <div class="top"><div><div class="job">${esc(j.name)}</div><div class="unit">${esc(j.job)}${j.runs > 1 ? ` · latest of ${j.runs} runs` : ''}</div></div><span class="pill ${j.state}">${fz ? 'frozen' : j.state}</span></div>
   ${why ? `<p class="why"><b>Why:</b> ${esc(j.reason)}</p>` : ''}
   <dl><dt>Last</dt><dd title="${esc(j.last)}">${esc(j.last)}</dd><dt>Mem</dt><dd>${j.mem}</dd><dt>Next</dt><dd title="${esc(j.next)}">${esc(j.next)}</dd><dt>Wrote</dt><dd>${j.wrote}</dd>${fz ? `<dt>Frozen</dt><dd class="wide">since ${esc(j.frozen_at)}</dd>` : ''}</dl>
   ${j.notes ? `<p class="notes">${esc(j.notes)}</p>` : ''}${al.map(alertNote).join('')}
   <div class="actions"><details data-log="${esc(j.job)}"><summary>Show log</summary><pre>Loading…</pre></details>
    ${j.canfreeze ? `<button type="button" data-act="${fz ? 'thaw' : 'freeze'}" aria-label="${fz ? 'Resume' : 'Pause'} ${esc(j.job)}">${fz ? 'Resume' : 'Pause'}</button>` : ''}
    ${j.canrun === false ? '' : `<button type="button" data-act="bolt" ${fz ? 'disabled' : ''} aria-label="${go} ${esc(j.job)}${fz ? ' (resume it first)' : ''}">${go}</button>`}</div></article>`;
}
function markStone(c) { c.dataset.state = 'frozen'; const p = $('.pill', c); if (p) { p.className = 'pill frozen'; p.textContent = 'frozen'; } }
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
    const say = n ? [bad.length && `${bad.length} task${bad.length === 1 ? '' : 's'} failed: ${bad.map(j => j.job).join(', ')}`,
      up.length && `${up.length} alert${up.length === 1 ? '' : 's'}: ${up.map(a => `${a.job}, ${a.message}`).join('; ')}`].filter(Boolean).join('. ') : 'all tasks well';
    A.setAttribute('aria-label', side ? `Argus: ${say}. Open the watch page` : `Argus, the watchman: ${say}`);
    if (lastBad !== null && n > lastBad) alarmChime();               // a short alarm only when something newly fails
    lastBad = n;
  }
  if (side) {
    A.setAttribute('role', 'link'); A.tabIndex = 0;
    A.onclick = () => location.href = WATCH;
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
