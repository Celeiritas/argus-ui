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
const PAGES = ['olympus', 'home', 'phone'];                   // sections that are not agents (Today, once called Home: docs/home.md; Phone alerts: docs/phone-alerts.md)
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
const SIDE = ['mentor', 'olympus', 'home', 'phone'];
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
// This only hides places in the page; it protects nothing. Every address and api/... still answers to anyone who can reach the
// server: the server's own check comes with sign-in. A learner who opens a place outside her list lands on Today.
const placeOf = () => side ? here : 'argus';
// Status v2 of every server plugin (docs/home.md): Today's rows and cards and the counts on the bar.
const STATUS = {};                                            // id -> its last answer (undefined: still asking, null: none)
let statusAsk = null;
function askStatus() {
  return statusAsk ||= Promise.all(PLUGINS.filter(p => p.kind === 'server').map(p => fetch(url(`api/${p.id}/status`), {cache: 'no-store'})
    .then(r => r.json()).then(j => j && j.line ? j : null).catch(() => null).then(v => { STATUS[p.id] = v; }))).then(() => { statusAsk = null; });
}
// Trouble on Watch, counted once everywhere (the bar, Argus's badge, Today's line): tasks that failed, tasks that run but do not
// do their job (works === false, docs/checks.md), and alert-level alerts that are not already about one of those tasks.
// Checks with no task card of their own (a media program, a drive: docs/checks.md) count too, once each: the alert the server
// makes from such a check is that check, not a second thing.
const jobIs = (j, name) => !!name && (j.job === name || (!!j.base && j.base === name));
const checksFor = j => (S?.watch || []).filter(w => jobIs(j, w.job));
const hasCard = w => (S?.jobs || []).some(j => jobIs(j, w.job));
function trouble() {
  const tasks = (S?.jobs || []).filter(j => j.state === 'failed' || j.works === false);
  const checks = (S?.watch || []).filter(w => w.works === false && w.code !== 'read-hung' && !hasCard(w));
  const alerts = (S?.alerts || []).filter(a => a.level === 'alert' && !checks.some(w => a.file === 'watch-' + w.id) && !tasks.some(j => jobIs(j, a.job)));
  return {tasks, alerts, checks, n: tasks.length + alerts.length + checks.length};
}
// One entry per broken thing, in the page's order (programs that run but do not work first: they have a fix; then failed tasks,
// then agents' alerts), each in three plain lines: what is wrong and since when, what Argus did (or would have done), what you
// can do; and the one fix that checks.json declares, when there is one (docs/home.md "Trouble first").
const agentOf = w => { const k = (w.job || '').split('-')[0]; return AGENT_KEYS.includes(k) && !SIDE.includes(k) ? k : 'argus'; };
const agentName = k => (S.personas.find(p => p.key === k) || {name: k}).name;
const sinceText = t => { const s = since(t); return s ? `since ${s}` : ''; };
const CAN = {'drive-missing': 'Plug the drive in again. Programs that use it may need a restart after that.',
  'drive-dropped': 'Plug the drive in again. Programs that use it may need a restart after that.',
  'drive-readonly': 'The drive needs a look on the server: it stopped taking writes, usually after errors.',
  'unit-down': 'Start it again on the server, or read its log there.', 'no-answer': 'Open its web address to see what it says. A restart often helps.'};
function checkItem(w, j) {
  const agent = j ? j.persona : agentOf(w), can = !/^drive-/.test(w.code) && w.fix;
  const say = w.drive ? (w.title_line || w.reason) : w.code === 'unit-down' ? `${w.title} is not running` : `${w.title} is running but not working`;
  return {key: 'check-' + w.id, agent, who: `${agentName(agent)} · Watch`, what: w.title_line || `${w.title}: ${w.reason}`, when: sinceText(w.since), say,
    did: w.fixing ? 'Restarting it now, as you asked. Argus looks again for up to 90 seconds.' : w.note || (w.fix ? 'Argus did not restart it and waits for your yes.' : 'Argus cannot fix this by himself, so he tells you.'),
    can: w.fixing ? 'Wait a moment: this changes when Argus knows how it went.' : can ? `Hold the button to restart ${w.fix_say}. Argus then looks again and tells you how it went.` : CAN[w.code] || 'Look at it on the server.',
    fix: can && !w.fixing && role() === 'owner' ? {id: w.id, label: `Restart ${w.fix_say}`} : null, href: WATCH};
}
function taskItem(j) {
  const why = j.works_reason || j.reason;
  return {key: 'task-' + j.job, agent: j.persona, who: `${agentName(j.persona)} · Watch`, what: `${j.name} failed${why ? `: ${why}` : ''}`, say: `${j.name} failed`,
    when: j.last && j.last !== '—' ? `last ran ${j.last}` : '', did: 'Argus does not restart a failed task by himself.',
    can: `Read its log on its card, then press ${always(j) ? 'Restart' : 'Run'} to try again.`, fix: null, href: WATCH};
}
function alertItem(a) {
  const k = a.job.split('-')[0], g = S.personas.find(p => p.key === k), name = g ? g.name : k, watch = g && !SIDE.includes(k);
  return {key: `alert-${a.file || a.job}`, agent: k, who: g ? `${name} · Watch` : a.job, what: a.message, say: a.message, when: sinceText(a.since), of: a.link || 'argus',
    did: `${name} raised this; Argus passes it on.`, can: a.link ? `Open ${sectionName(a.link)} to deal with it.` : `Look at ${name}'s tasks on Watch.`, fix: null,
    label: a.link ? `Open ${sectionName(a.link)}` : `Look at ${name} on Watch`, href: a.link ? url(a.link) : watch ? (k === 'argus' ? WATCH + '/argus' : url(k)) : WATCH};
}
function troubleItems() {
  const {tasks, alerts, checks} = trouble(), bad = j => checksFor(j).find(w => w.works === false);
  return [...tasks.filter(bad).map(j => checkItem(bad(j), j)), ...checks.map(w => checkItem(w)), ...tasks.filter(j => !bad(j)).map(taskItem), ...alerts.map(alertItem)];
}
const troubleLines = it => `<p class="tl"><b>Argus:</b> ${esc(it.did)}</p><p class="tl"><b>You:</b> ${esc(it.can)}</p>`;
const fixButton = it => it.fix ? `<button type="button" class="fixbtn" data-fix="${esc(it.fix.id)}">${esc(it.fix.label)}</button>` : '';
function troubleBlock(it) {
  return `<article class="tblock" data-trouble="${esc(it.key)}" aria-labelledby="t-${esc(it.key)}"><h3 id="t-${esc(it.key)}">${esc(it.what)}</h3>
    <p class="tw">${esc(it.who)}${it.when ? ` · ${esc(it.when)}` : ''}</p>${troubleLines(it)}${fixButton(it)}</article>`;
}
// The owner's yes (POST api/watch/fix): only the fix checks.json declares for that check runs. Press and hold, like every
// action that changes what runs; the toast says what the server said, and the next refresh shows "Restarting" on the block.
async function askFix(id) {
  try {
    const r = await fetch(url('api/watch/fix'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id})});
    const j = await r.json(); toast(j.msg || (j.ok ? 'Restarting.' : "Couldn't start the fix. Try again in a moment."));
    setTimeout(refresh, 300); return !!j.ok;
  } catch (e) { toast("Couldn't reach the server to restart it. Check that it's on, then try again."); return false; }
}
function wireFixes() { $$('#main button[data-fix]:not(.hold)').forEach(b => holdConfirm(b, () => askFix(b.dataset.fix))); }
// what needs you in a place: a number when it is known, true when the place needs you but gives no number, 0 when nothing
function needCount(id) {
  if (id === 'argus') return trouble().n;
  const s = STATUS[id], c = Math.floor(Number(s?.count));          // the server's count, if any, made a plain number first
  return s && s.needs ? (c > 0 ? c : true) : 0;
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
  add('phone', url('phone'), 'Phone alerts', icon('argus'));   // the owner's (visible() leaves it out for a learner); More sheet only: alerts.js
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
  put($('#realms'), all.filter(e => e.id !== 'phone').map(pill).join(''));   // Phone alerts: in the phone's More sheet, not the wide strip (alerts.js)
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
  // not her place: Today. Her state lists only her places, so an owner's address (Watch, the Throne) is one this page does
  // not know (here falls back to 'home'): that is not hers either.
  const unknown = SEG[0] !== '' && SEG[0] !== 'home' && here === 'home';
  if (role() !== 'owner' && (!LEARNER.includes(placeOf()) || unknown)) { location.replace(url('')); return; }
  const me = S.personas.find(p => p.key === here), name = S.title || 'Elaia';
  const head = (h1, sub, title) => { $('.title h1').textContent = h1; $('#sub').textContent = sub; document.title = `${title} · ${name}`; };
  if (plugin) {
    const w = WORDS[plugin.id] || {}, word = w.word || plugin.name, god = w.icon && AGENT_KEYS.includes(w.icon) ? w.icon : null;
    head(word, w.realm ? [w.realm, plugin.name !== w.realm ? plugin.name : plugin.subtitle].filter(Boolean).join(' · ') : plugin.subtitle, word);
    $('#hero').hidden = !plugin.icon && !plugin.agent && !god;          // a plugin that took over an agent's section keeps the agent's icon
    if (!$('#hero').hidden) $('#hero').src = plugin.icon ? url(`plugins/${plugin.id}/${plugin.icon}`) : `static/icons/${god || plugin.id}.png`;
  } else if (here === 'home') {
    head(name, home.greet().join(' · '), 'Today'); $('#hero').hidden = true;
  } else if (here === 'phone') {
    head('Phone alerts', 'Argus · what makes your phone buzz', 'Phone alerts'); $('#hero').hidden = true;
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
  // the people file cannot be used (the server keeps its last good copy): one plain line for the owner, on Today and Watch only
  const pp = $('#peopleProblem'), ppShow = role() === 'owner' && !!S.people_problem && (here === 'home' || (!plugin && !side && !onOlympus));
  pp.textContent = ppShow ? S.people_problem : ''; pp.hidden = !ppShow;          // textContent: the sentence is never read as HTML
  phoneAlerts.hint();                                                            // Today's one quiet line about phone alerts (alerts.js)
  const by = {}; S.jobs.forEach(j => (by[j.persona] ||= []).push(j));
  const lone = {}; loneAlerts().forEach(a => (lone[a.job.split('-')[0]] ||= []).push(a));   // alerts with no task card of their own
  const rows = {}; (S.watch || []).filter(w => !hasCard(w)).forEach(w => (rows[agentOf(w)] ||= []).push(w));   // checks with no card: compact rows
  const shown = S.personas.filter(p => (by[p.key] || lone[p.key] || rows[p.key] || p.key === only) && !SIDE.includes(p.key));
  const chip = (k, label, href) => `<a href="${href}" class="${only === k ? 'on' : ''}" ${only === k ? 'aria-current="page"' : ''}>${esc(label)}</a>`;
  $('#nav').innerHTML = chip(null, 'All', WATCH) + shown.map(p => chip(p.key, p.name, p.key === 'argus' ? WATCH + '/argus' : url(p.key))).join('');
  if (plugin) { look.retarget(); return leafy.show(plugin); }
  if (onOlympus) { look.retarget(); return playground.show(); }
  if (here === 'home') { look.retarget(); return home.show(); }
  if (here === 'phone') { look.retarget(); return phoneAlerts.show(); }
  // trouble first: failed (or alerted), then running, then ok, then the rest; groups ordered by their worst card
  const rank = j => j.state === 'failed' || j.works === false || alertsFor(j).some(a => a.level === 'alert') ? 0 : j.state === 'running' ? 1 : j.state === 'ok' ? 2 : 3;
  const worst = p => Math.min(4, ...(by[p.key] || []).map(rank), ...(lone[p.key] || []).map(a => a.level === 'alert' ? 0 : 2), ...(rows[p.key] || []).map(w => w.works === false ? 0 : 2));
  const list = (only ? shown.filter(p => p.key === only) : shown).map((p, i) => [p, i]).sort((a, b) => worst(a[0]) - worst(b[0]) || a[1] - b[1]).map(x => x[0]);
  // Trouble first: one block per broken thing, above the groups (docs/home.md "Trouble first"); "What happened lately" at the end
  const items = only ? troubleItems().filter(it => it.agent === only) : troubleItems();
  const top = items.length ? `<section class="trouble" aria-labelledby="trouble-h"><h2 id="trouble-h">${items.length === 1 ? 'One thing needs a look' : `${items.length} things need a look`}</h2>${items.map(troubleBlock).join('')}</section>` : '';
  const end = only ? '' : `<section class="lately" aria-labelledby="lately-h"><h2 id="lately-h">What happened lately</h2><div id="lately">${lately.html || '<p class="quiet">Loading…</p>'}</div></section>`;
  $('#main').innerHTML = top + (list.map(p => {
    const js = (by[p.key] || []).map((j, i) => [j, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(x => x[0]), ls = lone[p.key] || [];
    const cr = (rows[p.key] || []).map((w, i) => [w, i]).sort((a, b) => (a[0].works === false ? 0 : 1) - (b[0].works === false ? 0 : 1) || a[1] - b[1]).map(x => x[0]);
    const c = s => js.filter(j => j.state === s).length, na = (S.alerts || []).filter(a => a.level === 'alert' && a.job.split('-')[0] === p.key).length;
    const counts = (na ? [`<span class="failed">${na} alert${na === 1 ? '' : 's'}</span>`] : []).concat(['failed', 'running', 'frozen'].filter(s => c(s)).map(s => `<span class="${s}">${c(s)} ${s}</span>`)).concat(`${js.length} task${js.length === 1 ? '' : 's'}`).join(' · ');
    return `<section class="persona" aria-labelledby="h-${p.key}"><a class="ph" href="${p.key === 'argus' ? WATCH + '/argus' : url(p.key)}"><img src="static/icons/${p.key}.png" alt=""><div><h2 id="h-${p.key}">${esc(p.name)}</h2><div class="dom">${esc(p.domain)}</div></div><div class="counts">${counts}</div></a>
      ${cr.length ? `<ul class="crows" aria-label="${esc(p.name)}: checks">${cr.map(checkRow).join('')}</ul>` : ''}
      ${js.length || ls.length ? `<div class="grid">${ls.map(alertCard).join('')}${js.map(card).join('')}</div>` : cr.length ? '' : `<div class="empty"><b>No ${esc(p.name)} tasks yet</b>Background jobs named <code>${esc(p.key)}-…</code> appear here on their own, so you can watch and run them. <a href="https://github.com/Celeiritas/argus-ui#which-jobs-show-up">Learn how to add a task</a></div>`}</section>`;
  }).join('') || `<div class="empty"><b>No tasks found</b>Argus shows systemd --user jobs whose names start with an agent's key. <a href="https://github.com/Celeiritas/argus-ui#which-jobs-show-up">Learn how to add a task</a></div>`) + end;
  if (!only) askLately();
  wireFixes();
  $$('.card.frozen').forEach(addStone);
  if (armed) arm(armed, true);
  look.retarget();
  satellite.place(items);
}
/* ---------- alert files (docs/alerts.md): an agent's message on its task's card, or a card of its own ---------- */
const alertsFor = j => (S.alerts || []).filter(a => a.job === j.job || (j.base && a.job === j.base));
// alerts with no task card; an alert the server made from a check is shown as that check's row instead (checkRow)
const loneAlerts = () => (S.alerts || []).filter(a => !S.jobs.some(j => alertsFor(j).includes(a)) && !(S.watch || []).some(w => a.file === 'watch-' + w.id));
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
const always = j => typeof j.restarts === 'boolean' ? j.restarts : j.next === 'always on';   // the server says (api/state `restarts`); an older one did not
// Every check is on Watch while it works too (docs/checks.md): on its task's card as one line, or as a compact row of its own
// under the agent that owns it (a check whose job has no card: a media program, a drive).
function worksLine(j) {
  const rs = checksFor(j); if (!rs.length || j.works !== true) return '';
  const w = rs[0];
  return `<p class="worksline"><b>${w.again ? 'Works again' : 'Works'}</b>${w.since ? ` · ${esc(sinceText(w.since))}` : ''}${rs.length > 1 ? ` · ${rs.length} checks` : ''}</p>`;
}
function checkRow(w) {
  const st = w.fixing ? ['busy', 'Restarting…'] : w.works === true ? ['ok', w.again ? 'Works again' : 'Works']
    : w.works === false ? ['bad', w.drive ? w.reason : w.code === 'unit-down' ? 'Not running' : `Running, but not working: ${w.reason}`]
    : ['unknown', `Not known yet${w.reason ? `: ${w.reason}` : ''}`];
  return `<li class="crow ${st[0]}" data-check="${esc(w.id)}"><span class="cdot" aria-hidden="true"></span><span class="cw"><b>${esc(w.title)}</b><span>${esc(st[1])}${w.since && !w.fixing ? ` · ${esc(sinceText(w.since))}` : ''}</span></span></li>`;
}
// "What happened lately": the newest 10 events (api/events) as plain sentences, each with a relative and an exact time.
const lately = {html: '', at: 0, since: ''};
function ago(t) {
  const d = new Date(t), s = (Date.now() - d) / 1000; if (isNaN(d)) return '';
  const n = (v, w) => `${v} ${w}${v === 1 ? '' : 's'} ago`;
  return s < 60 ? 'just now' : s < 3600 ? n(Math.floor(s / 60), 'minute') : s < 86400 ? n(Math.floor(s / 3600), 'hour') : n(Math.floor(s / 86400), 'day');
}
const exact = t => { const d = new Date(t); return isNaN(d) ? '' : d.toLocaleString([], {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}); };
function latelyHtml(evs, sinceAt) {
  if (!evs.length) return `<p class="quiet">Nothing has happened since ${esc(exact(sinceAt) || 'the server started')}.</p>`;
  return `<ol class="events">${evs.map(e => `<li class="ev ${e.level === 'alert' ? 'bad' : e.level === 'warn' ? 'warn' : 'good'}"><p class="et">${esc(e.title)}</p>${e.body ? `<p class="eb">${esc(e.body)}</p>` : ''}<p class="ew"><time datetime="${esc(e.at)}">${esc(ago(e.at))}</time> · ${esc(exact(e.at))}</p></li>`).join('')}</ol>`;
}
async function askLately() {
  if (Date.now() - lately.at < 10000) return; lately.at = Date.now();
  try { const r = await fetch(url('api/events?limit=10'), {cache: 'no-store'}); const j = await r.json(); lately.html = latelyHtml(j.events || [], j.since); }
  catch (e) { lately.html = '<p class="quiet">Could not load what happened. It tries again with the next refresh.</p>'; lately.at = 0; }
  const el = $('#lately'); if (el && el.innerHTML !== lately.html) el.innerHTML = lately.html;
}
function card(j) {
  const fz = j.state === 'frozen', al = alertsFor(j), lvl = al.some(a => a.level === 'alert') ? 'alerted' : al.length ? 'warned' : '';
  const go = always(j) ? 'Restart' : 'Run', why = (j.state === 'failed' || j.works === false) && (j.works_reason || j.reason);   // why, when the server says
  return `<article class="card ${fz ? 'frozen' : ''} ${lvl}${j.works === false ? ' notworking' : ''}" data-job="${esc(j.job)}" data-state="${j.state}" data-canfreeze="${j.canfreeze}" data-canrun="${j.canrun !== false}" aria-label="${esc(j.job)}, ${fz ? 'frozen (paused)' : j.state}">
   <div class="top"><div><div class="job">${esc(j.name)}</div><div class="unit">${esc(j.job)}${j.runs > 1 ? ` · latest of ${j.runs} runs` : ''}</div></div><span class="pill ${j.state}">${fz ? 'frozen' : j.state}</span></div>
   ${why ? `<p class="why"><b>${j.works === false && j.state !== 'failed' ? 'Running, but not working' : 'Why'}:</b> ${esc(why)}</p>` : worksLine(j)}
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
async function refresh() { if (busy || $('.hold.holding,.hold[aria-busy]')) return;   /* never redraw a button that is being held */ try { const r = await fetch(url('api/state'), {cache: 'no-store'}); S = await r.json(); const open = $$('details[open]').map(d => d.dataset.log); render(); open.forEach(k => { const d = $(`details[data-log="${CSS.escape(k)}"]`); if (d) { d.open = true; loadLog(d); } }); } catch (e) {} }
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
  let pointer = null, lastMove = 0, target = null, wander = {x: 0, y: 0, t: 0}, cur = eyes.map(() => [0, 0]), watched = null, fixed = null;   // watched: kept in view ahead of the pointer; fixed: what is wrong (satellite)
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
    // a failed or not-working task, or an agent's alert file at level "alert" (docs/alerts.md): he glares and counts them (trouble()).
    // A learner does not get him at all: no badge, no words about the owner's tasks, no chime, no way into Watch.
    const owner = role() === 'owner'; A.hidden = !owner; A.tabIndex = owner && side ? 0 : -1;
    if (!owner) { A.removeAttribute('aria-label'); alarmed = false; lastBad = null; return; }
    const {tasks: bad, alerts: up, checks: ck, n} = trouble();
    target = $(".tblock") || $('.card[data-state="failed"]') || $('.card.alerted') || $('.card.notworking');
    alarmed = n > 0; A.classList.toggle('glare', alarmed); A.classList.toggle('calm', !n);
    $('#alarm').hidden = !n; $('#alarmN').textContent = n > 1 ? n : '';
    const fl = bad.filter(j => j.state === 'failed'), nw = bad.filter(j => j.state !== 'failed');
    const say = n ? [fl.length && `${fl.length} task${fl.length === 1 ? '' : 's'} failed: ${fl.map(j => j.job).join(', ')}`, nw.length && `${nw.length} running but not working: ${nw.map(j => j.job).join(', ')}`,
      ck.length && `${ck.length} not working: ${ck.map(w => w.title).join(", ")}`, up.length && `${up.length} alert${up.length === 1 ? '' : 's'}: ${up.map(a => `${a.job}, ${a.message}`).join('; ')}`].filter(Boolean).join('. ') : 'all tasks well';
    A.setAttribute('aria-label', side ? `Argus: ${say}. Open the watch page` : `Argus, the watchman: ${say}`);
    if (lastBad !== null && n > lastBad) alarmChime();               // a short alarm only when something newly fails
    lastBad = n;
  }
  if (side) {
    A.setAttribute('role', 'link'); A.tabIndex = 0;
    A.onclick = () => { if (role() === 'owner') location.href = WATCH; };
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
    else if (fixed?.isConnected) { const r = fixed.getBoundingClientRect(); aim(r.left + r.width / 2, r.top + r.height / 2); }   // something is wrong: not the pointer
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
  return {retarget, react, watch: el => { watched = el || null; }, fix: el => { fixed = el || null; }, doze: ms => { dozeAfter = ms; }};   // doze: how long before he dozes (tests shorten it)
})();

/* ---------- the satellite eye: one of Argus's eyes leaves him and glares at what is wrong (docs/home.md "The satellite eye") ---------- */
// On Watch, when something is wrong, a copy of his red eye (his own markup, nothing new drawn) travels once (750 ms, fx.travel) from
// his face to the top-right corner of the first trouble block and stays there; his red eye shows shut meanwhile, and his other eyes
// look at that block, not at the pointer (look.fix). The glare pulses 4 times (4.8 s), then holds still. Several broken things: a
// small "2 more" under it. The block keeps a gutter on its right, so the eye never covers its words or its button. When the block is
// scrolled out of view, an edge marker (44 px, an arrow) brings it back. Reduced motion: no travel, no pulse, the eye is just there.
// The eye is aria-hidden; one polite sentence says the same, once per change. When the trouble ends the eye flies home and the
// sentence says so. Only the owner, only on Watch.
const satellite = (() => {
  const A = $('#argus'), red = $('svg .eye.red', A);
  const live = document.createElement('p'); live.className = 'sr'; live.id = 'satSay'; live.setAttribute('aria-live', 'polite'); document.body.append(live);
  const edge = document.createElement('button'); edge.type = 'button'; edge.id = 'satEdge'; edge.className = 'satedge'; edge.hidden = true;
  edge.setAttribute('aria-label', 'Scroll to what needs a look'); document.body.append(edge);
  let key = null, at = null, seen = null;                     // the block it glares at, where it last sat (page coordinates), the observer
  const say = t => { live.textContent = t; };
  function eye() {                                            // a copy of his red eye in a small frame, its iris turned down-left onto the block
    const g = red.cloneNode(true); g.classList.remove('red'); $('.iris', g).setAttribute('transform', 'translate(-2.2 1.4)');
    return `<svg viewBox="90.2 64.1 28 28" aria-hidden="true">${g.outerHTML}</svg>`;
  }
  const centre = el => { const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
  function edgeFor(block) {                                   // the edge marker: shown only while the block is out of view
    seen?.disconnect(); seen = null; edge.hidden = true;
    if (!block || !('IntersectionObserver' in window)) return;
    seen = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { edge.hidden = true; return; }
      const up = e.boundingClientRect.top < 0, bar = $('#tabbar'), barH = bar && bar.offsetHeight && getComputedStyle(bar).display !== 'none' ? bar.offsetHeight : 0;
      edge.className = `satedge ${up ? 'up' : 'down'}`; edge.style.top = up ? '12px' : ''; edge.style.bottom = up ? '' : `${barH + 12}px`;
      edge.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${up ? 'M12 5 5 13h4v6h6v-6h4z' : 'M12 19 5 11h4V5h6v6h4z'}" fill="currentColor"/></svg><span>Look</span>`;
      edge.hidden = false;
    }, {threshold: .25});
    seen.observe(block);
  }
  edge.onclick = () => { const b = $('#main .tblock.eyed'); if (!b) return; b.scrollIntoView({block: 'center', behavior: RM.matches ? 'auto' : 'smooth'}); ($('button,a', b) || b).focus?.({preventScroll: true}); };
  function home() {                                           // the trouble ended: the eye flies back from where it sat, and his own opens again
    const back = () => { A.classList.remove('sat-out'); };
    if (!at || RM.matches || A.hidden) return back();
    const tmp = document.createElement('span'); tmp.className = 'sat flying'; tmp.innerHTML = eye();
    const [x, y] = centre(red), w = 44; tmp.style.cssText = `position:fixed;left:${x - w / 2}px;top:${y - w / 2}px;width:${w}px;height:${w}px`;
    $('#fx').append(tmp);
    fx.travel(tmp, [at[0] - scrollX, at[1] - scrollY], {ms: 700, scale: 1}).then(() => { tmp.remove(); back(); });
  }
  // called by render() on Watch with the trouble items in the page's order (the blocks are already in #main)
  function place(items) {
    const blocks = !side && role() === 'owner' && !A.hidden ? $$('#main .tblock') : [], first = blocks[0] || null;
    look.fix(first);
    if (!first) {
      edgeFor(null);
      if (key !== null) { key = null; say('All is well again: nothing on Watch needs a look.'); home(); }
      return;
    }
    const k = first.dataset.trouble, it = items.find(i => i.key === k), more = blocks.length - 1;
    first.classList.add('eyed');
    const sat = document.createElement('span'); sat.className = 'sat'; sat.setAttribute('aria-hidden', 'true');
    sat.innerHTML = eye() + (more ? `<span class="satn">${more} more</span>` : '');
    first.append(sat); A.classList.add('sat-out');
    const r = sat.getBoundingClientRect(); at = [r.left + r.width / 2 + scrollX, r.top + 22 + scrollY];
    if (k !== key) {                                          // a change: travel once and pulse, and say it once
      const from = key === null ? centre(red) : null;
      key = k; sat.classList.add('glaring');
      if (from) fx.travel($('svg', sat), from);
      say(`${(it ? it.say : 'Something is wrong').replace(/[.\s]+$/, '')}${more ? `, and ${more} more thing${more === 1 ? ' needs' : 's need'} a look` : ''}.`);
    }
    edgeFor(first);
  }
  return {place, get key() { return key; }};
})();
