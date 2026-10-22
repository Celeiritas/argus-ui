// Argus UI - the god tools on the Watch page: drag Zeus's bolt or Medusa onto a task; strikes and effects shared with Olympus.
/* ---------- god tools: drag onto a task, or press the tool then choose a task (keyboard / tap) ---------- */
const TOOLS = {medusa: {home: $('#medusaHome'), el: $('#medusa'), size: 110, label: "Medusa"}, bolt: {home: $('#boltHome'), el: $('#bolt'), size: 90, label: "Zeus's bolt"}};
// Zeus's medallion stays home and hands you a bolt: drop it on a task or tree, or fling it at the trees
const BOLT_SVG = '<svg viewBox="26 8 48 84" aria-hidden="true"><path d="M56 12 L30 54 L47 54 L38 88 L70 42 L52 42 L62 12 Z" fill="#FFE27A" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/></svg>';
let shot = null;
function newShot(x, y) { const e = document.createElement('div'); e.className = 'shot'; e.innerHTML = BOLT_SVG; document.body.append(e); place(e, x, y, 56); return e; }
function homeOf(name) { const r = TOOLS[name].home.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }
function fizzle(e) { if (!e) return; const [hx, hy] = homeOf('bolt'); flyTo(e, hx, hy, 30, 250, 'ease-in').then(() => e.remove()); }   // back into the medallion
// what a tool can act on in the scene: bolt -> a living tree, Medusa -> a tree (stone or not), Poseidon -> debris or a charred tree
const sceneTarget = (name, x, y) => name === 'bolt' ? scene.treeAt(x, y) : name === 'medusa' ? scene.treeAt(x, y, true) : scene.messAt(x, y);
const usable = (tool, c) => c && tool !== 'poseidon' && (tool === 'medusa' ? c.dataset.canfreeze === 'true' : c.dataset.state !== 'frozen' && c.dataset.canrun !== 'false');
function place(el, x, y, w) { el.style.width = el.style.height = w + 'px'; el.style.left = (x - w / 2) + 'px'; el.style.top = (y - w / 2) + 'px'; }
// move a floating tool with transform/opacity only (FLIP): jump to the end box, then animate from the old box
function flyTo(el, x, y, w, ms = 200, easing = 'ease-out') {
  const a = el.getBoundingClientRect(); place(el, x, y, w); const b = el.getBoundingClientRect();
  if (RM.matches || !a.width) return Promise.resolve();
  const anim = el.animate([{transform: `translate(${a.left - b.left}px,${a.top - b.top}px) scale(${a.width / b.width})`, transformOrigin: 'top left'}, {transform: 'none', transformOrigin: 'top left'}], {duration: ms, easing});
  return anim.finished.catch(() => {});
}
function cardAt(x, y, tool) { const el = document.elementFromPoint(x, y), c = el && el.closest('.card'); return usable(tool, c) ? c : null; }
Object.entries(TOOLS).forEach(([name, T]) => {
  T.home.addEventListener('pointerdown', e => {
    if (busy || e.button > 0) return; T.home.setPointerCapture(e.pointerId);
    drag = {name, id: e.pointerId, over: null, x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, moved: false, trail: []};
  });
  T.home.addEventListener('pointermove', e => {
    if (!drag || e.pointerId !== drag.id) return;
    drag.x = e.clientX; drag.y = e.clientY;
    if (!drag.moved && Math.hypot(drag.x - drag.x0, drag.y - drag.y0) < 6) return;     // a small wobble is still a click
    if (!drag.moved) { drag.moved = true; disarm(); if (name === 'bolt') shot = newShot(e.clientX, e.clientY); else T.el.classList.add('floating'); }
    if (name === 'bolt') { place(shot, e.clientX, e.clientY, 56); drag.trail.push([performance.now(), e.clientX, e.clientY]); if (drag.trail.length > 8) drag.trail.shift(); }
    else place(T.el, e.clientX, e.clientY, T.size);
    const c = cardAt(e.clientX, e.clientY, name) || sceneTarget(name, e.clientX, e.clientY);
    if (c !== drag.over) { drag.over?.classList.remove('target'); c?.classList.add('target'); drag.over = c; if (name === 'medusa') T.el.classList.toggle('awake', !!c); }
  });
  const end = () => {
    if (!drag || drag.name !== name) return; const drag0 = drag, {over: c, moved} = drag; c?.classList.remove('target'); drag = null;
    if (!moved) return;                                                      // it was a click: the click handler arms it
    justDragged = true; setTimeout(() => justDragged = false, 50);
    if (!c && name === 'bolt') {                                           // no target: a fast release flings the bolt, a slow one puts it back
      const tr = drag0.trail, now = performance.now(), still = !tr.length || now - tr[tr.length - 1][0] > 80, old = tr.find(q => now - q[0] < 120) || tr[0], dt = old && !still ? (now - old[0]) / 1000 : 0;
      const vx = dt > .005 ? (drag0.x - old[1]) / dt : 0, vy = dt > .005 ? (drag0.y - old[2]) / dt : 0;
      const b = shot; shot = null;
      return Math.hypot(vx, vy) > 500 ? fling(b, drag0.x, drag0.y, vx, vy) : fizzle(b);
    }
    if (!c) return sendHome(name);
    if (c.classList.contains('tree') || c.classList.contains('mess')) return sceneCast(name, c, true);
    if (name === 'medusa') medusaCast(c, c.dataset.state === 'frozen' ? 'thaw' : 'freeze', true); else zeusStrike(c, true);
  };
  T.home.addEventListener('pointerup', end); T.home.addEventListener('pointercancel', end);
  T.home.addEventListener('click', () => { if (justDragged || busy) return; armed === name ? disarm(true) : arm(name); });
});
function arm(name, quiet) {
  disarm(); armed = name; TOOLS[name].home.setAttribute('aria-pressed', 'true');
  const cards = $$('.card').filter(c => usable(name, c));
  cards.forEach(c => { c.tabIndex = 0; c.classList.add('armable', 'armed-target'); });
  if (!quiet) { toast(onOlympus ? `Choose ${name === 'poseidon' ? 'a mess' : 'a tree'} for ${TOOLS[name].label}: click it. Esc cancels.` : `Choose a task for ${TOOLS[name].label}: click it, or Tab to it and press Enter. Esc cancels.`); cards[0]?.focus(); }
}
function disarm(refocus) {
  if (!armed) return; const T = TOOLS[armed]; T.home.setAttribute('aria-pressed', 'false'); armed = null;
  $$('.card.armable').forEach(c => { c.removeAttribute('tabindex'); c.classList.remove('armable', 'armed-target'); });
  if (refocus) T.home.focus();
}
function castArmed(c) { const name = armed; if (!usable(name, c)) return; disarm(); if (name === 'medusa') medusaCast(c, c.dataset.state === 'frozen' ? 'thaw' : 'freeze'); else zeusStrike(c); }
addEventListener('keydown', e => {
  if (e.key === 'Escape' && armed) { e.preventDefault(); disarm(true); toast('Cancelled.'); }
  if ((e.key === 'Enter' || e.key === ' ') && armed && e.target.classList?.contains('armable')) { e.preventDefault(); castArmed(e.target); }
});
function sendHome(name) {
  const T = TOOLS[name], r = T.home.getBoundingClientRect();
  T.el.classList.add('floating');
  flyTo(T.el, r.left + r.width / 2, r.top + r.height / 2, r.width, 300, 'ease-in').then(() => {
    T.el.classList.remove('floating', 'awake', 'freezing', 'thawing'); T.el.removeAttribute('style');
  });
}
function liftOff(name) { const T = TOOLS[name], h = T.home.getBoundingClientRect(); T.el.classList.add('floating'); place(T.el, h.left + h.width / 2, h.top + h.height / 2, h.width); }

/* ---------- Medusa: green stone gaze (freeze) / green fire (thaw) ---------- */
async function medusaCast(c, act, fromDrag) {
  if (busy) return;
  const job = c.dataset.job;
  if (act === 'freeze' && isRunning(c) && !(await confirmInterrupt('freeze', job))) { if (fromDrag) sendHome('medusa'); return; }
  busy = true;
  const M = TOOLS.medusa.el, r = c.getBoundingClientRect(), x = r.left + r.width / 2, y = Math.max(70, r.top - 14);
  if (!fromDrag) liftOff('medusa');
  M.classList.add('awake'); await flyTo(M, x, y, 150, 200);
  M.classList.add(act === 'freeze' ? 'freezing' : 'thawing'); play(act);
  const req = post(act, job).catch(() => ({ok: false, msg: 'no answer'}));
  if (act === 'freeze') await petrify(c, x, y); else await crumble(c, x, y);
  const res = await req;
  if (!res.ok) toast(failText(act, job, res.msg));
  else if (act === 'freeze') toast(SAY.freeze.ok(job), {label: 'Undo', fn: () => { const cc = $(`.card[data-job="${CSS.escape(job)}"]`); if (cc) medusaCast(cc, 'thaw'); }});
  else toast(SAY.thaw.ok(job));
  busy = false; sendHome('medusa'); refresh();
}
function particle(x, y, w, h, style) { const p = document.createElement('div'); p.className = 'p'; p.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${h}px;${style}`; $('#fx').appendChild(p); return p; }
const ROCK = ['polygon(10% 30%,45% 0,90% 15%,100% 60%,60% 100%,10% 85%)', 'polygon(0 40%,35% 5%,80% 0,100% 45%,75% 95%,20% 100%)', 'polygon(20% 0,85% 20%,100% 75%,50% 100%,0 70%)'];
async function petrify(c, x, y) {
  const r = c.getBoundingClientRect();
  if (RM.matches) { addStone(c); c.classList.add('frozen'); $('.stone', c).animate([{opacity: 0}, {opacity: .93}], {duration: 150}); await wait(150); markStone(c); return; }
  // jade gaze: rock shards stream from her eyes onto the card
  for (let i = 0; i < 70; i++) {
    const sx = x + (Math.random() - .5) * 26, sy = y + 6, tx = r.left + Math.random() * r.width, ty = r.top + Math.random() * r.height;
    const s = 3 + Math.random() * 7, green = ['#8FD9A8', '#5E9C78', '#B9FFCF', '#7E9486', '#4E6A5A'][i % 5];
    const p = particle(sx, sy, s, s, `background:${green};clip-path:${ROCK[i % 3]}`);
    p.animate([{transform: 'translate(0,0) rotate(0)', opacity: 1}, {transform: `translate(${tx - sx}px,${ty - sy}px) rotate(${Math.random() * 360}deg)`, opacity: .9, offset: .8}, {transform: `translate(${tx - sx}px,${ty - sy + 6}px) rotate(${Math.random() * 360}deg)`, opacity: 0}],
      {duration: 700 + Math.random() * 700, delay: Math.random() * 600, easing: 'cubic-bezier(.3,.6,.4,1)', fill: 'forwards'}).onfinish = () => p.remove();
  }
  await wait(450);
  // stone grows down over the card (transform only) while it shakes
  addStone(c); const st = $('.stone', c);
  st.animate([{transform: 'scaleY(0)', opacity: .5}, {transform: 'scaleY(1)', opacity: .93}], {duration: 1300, easing: 'cubic-bezier(.5,0,.3,1)', fill: 'forwards'});
  c.classList.add('frozen', 'shake');
  for (let i = 0; i < 26; i++) {      // grit falling off the edges
    const sx = r.left + Math.random() * r.width, sy = r.top + Math.random() * r.height * .8, s = 2 + Math.random() * 5;
    const p = particle(sx, sy, s, s, `background:${['#6e8a7a', '#4d6358', '#8fa39a'][i % 3]};clip-path:${ROCK[i % 3]}`);
    p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${(Math.random() - .5) * 30}px,${60 + Math.random() * 80}px) rotate(${Math.random() * 300}deg)`, opacity: 0}],
      {duration: 900 + Math.random() * 500, delay: 300 + Math.random() * 900, easing: 'cubic-bezier(.5,0,1,1)', fill: 'forwards'}).onfinish = () => p.remove();
  }
  await wait(1700); c.classList.remove('shake'); markStone(c);
}
async function crumble(c, x, y) {
  const r = c.getBoundingClientRect(); addStone(c); const st = $('.stone', c);
  if (RM.matches) { await st.animate([{opacity: .93}, {opacity: 0}], {duration: 150}).finished.catch(() => {}); st.remove(); c.classList.remove('frozen'); return; }
  // cracks race across the stone
  const svg = $('svg', st), path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M50 30 L38 22 L30 8 L22 0 M50 30 L64 20 L72 6 L80 0 M50 30 L40 42 L34 60 M50 30 L62 40 L70 52 L76 60 M50 30 L20 34 L0 30 M50 30 L80 32 L100 26');
  path.setAttribute('stroke', '#a8ffc4'); path.setAttribute('stroke-width', '1.6'); path.setAttribute('fill', 'none'); path.setAttribute('vector-effect', 'non-scaling-stroke');
  svg.appendChild(path);
  path.animate([{strokeDasharray: '0 400'}, {strokeDasharray: '400 0'}], {duration: 700, easing: 'ease-out', fill: 'forwards'});
  for (let i = 0; i < 60; i++) {      // green fire washes up the card
    const sx = r.left + Math.random() * r.width, sy = r.bottom - Math.random() * 10, s = 3 + Math.random() * 7, col = ['#CFFFDA', '#7CFFA8', '#3FD27A', '#2FBF62'][i % 4];
    const p = particle(sx, sy, s, s * 1.6, `background:${col};border-radius:50% 50% 45% 45%`);
    p.animate([{transform: 'translate(0,0) scale(1)', opacity: 0}, {opacity: 1, offset: .15}, {transform: `translate(${(Math.random() - .5) * 30}px,${-r.height - 40 - Math.random() * 60}px) scale(.2)`, opacity: 0}],
      {duration: 800 + Math.random() * 700, delay: Math.random() * 900, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove();
  }
  c.classList.add('shake');
  await wait(800);
  const cols = 6, rows = 3, cw = r.width / cols, ch = r.height / rows;      // the stone breaks into falling chunks
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
    const p = particle(r.left + i * cw, r.top + j * ch, cw + 1, ch + 1, `background:radial-gradient(ellipse at 30% 30%,#6e8a7a,#4d6358 60%,#3e5148);clip-path:${ROCK[(i + j) % 3]}`);
    p.animate([{transform: 'translate(0,0) rotate(0)', opacity: 1}, {transform: `translate(${(Math.random() - .5) * 120}px,${200 + Math.random() * 260}px) rotate(${(Math.random() - .5) * 220}deg)`, opacity: 0}],
      {duration: 900 + Math.random() * 500, delay: Math.random() * 250, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards'}).onfinish = () => p.remove();
  }
  st.remove(); c.classList.remove('frozen');
  await wait(1100); c.classList.remove('shake');
}

/* ---------- Zeus: hurl the bolt at a task - Run (or Restart for always-on tasks) ---------- */
// a jagged bolt from the top of the screen down to (x, y), a flash, and sparks
function boltFx(x, y) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');     // a jagged bolt from the top of the screen
  svg.setAttribute('width', innerWidth); svg.setAttribute('height', innerHeight); svg.style.cssText = 'position:absolute;inset:0';
  const zig = (x0, y0, x1, y1, n, jit) => { let d = `M${x0} ${y0}`; for (let i = 1; i < n; i++) { const t = i / n; d += ` L${x0 + (x1 - x0) * t + (Math.random() - .5) * jit} ${y0 + (y1 - y0) * t}`; } return d + ` L${x1} ${y1}`; };
  const startX = x + (Math.random() - .5) * 200, main = zig(startX, -10, x, y, 12, 60);
  const branches = [0, 1, 2].map(() => { const t = .3 + Math.random() * .4, bx = startX + (x - startX) * t, by = (y + 10) * t; return zig(bx, by, bx + (Math.random() - .5) * 160, by + 60 + Math.random() * 80, 5, 30); });
  svg.innerHTML = `<g fill="none" stroke-linejoin="round" stroke-linecap="round"><path d="${main}" stroke="#FFF6C2" stroke-width="8" opacity=".35"/><path d="${main}" stroke="#FFF6C2" stroke-width="4"/><path d="${main}" stroke="#ffffff" stroke-width="2"/>${branches.map(b => `<path d="${b}" stroke="#FFE27A" stroke-width="2"/>`).join('')}</g>`;
  $('#fx').appendChild(svg);
  $('#flash').animate([{opacity: 0}, {opacity: .3, offset: .08}, {opacity: 0, offset: .3}, {opacity: .15, offset: .38}, {opacity: 0}], {duration: 700});
  svg.animate([{opacity: 1}, {opacity: .2, offset: .25}, {opacity: 1, offset: .35}, {opacity: 0}], {duration: 650, fill: 'forwards'}).onfinish = () => svg.remove();
  for (let i = 0; i < 40; i++) {    // sparks
    const a = Math.random() * Math.PI * 2, d = 30 + Math.random() * 90, s = 2 + Math.random() * 3;
    const p = particle(x, y, s, s, `background:${['#ffffff', '#FFE27A', '#FFF6C2', '#9fd3ff'][i % 4]};border-radius:50%`);
    p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d + 20}px)`, opacity: 0}], {duration: 500 + Math.random() * 500, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove();
  }
}
// Zeus strikes a tree: it flashes, burns, smokes, stands charred, then grows back
function sceneCast(name, t, fromDrag) {
  if (name === 'bolt') return strikeTree(t, fromDrag ? shot : null);
  if (name === 'medusa') return stoneTree(t, fromDrag);
  return null;
}
async function strikeTree(t, held, flung) {
  if (t.classList.contains('struck')) return;
  t.classList.add('struck');                                     // claim it at once so a second bolt can't hit it mid-strike
  const r = t.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height * .35;
  const B = held || newShot(...homeOf('bolt')); if (held === shot) shot = null;
  if (!flung) await flyTo(B, x, Math.max(50, r.top - 30), 56, 150);
  play('bolt');
  t.classList.remove('target');
  if (!RM.matches) {
    B.style.opacity = '0'; boltFx(x, y);
    t.animate([{transform: 'translateX(-50%) rotate(0)'}, {transform: 'translateX(-50%) rotate(-3deg)'}, {transform: 'translateX(-50%) rotate(2deg)'}, {transform: 'translateX(-50%) rotate(0)'}], {duration: 500});
    const end = performance.now() + 2600;
    (function burn() {                       // flames and embers rise from the crown, then smoke
      const now = performance.now(), smoke = now > end - 900;
      for (let i = 0; i < (smoke ? 1 : 3); i++) {
        const px = r.left + r.width * (.25 + Math.random() * .5), py = r.top + r.height * (.15 + Math.random() * .35), s = smoke ? 14 + Math.random() * 12 : 5 + Math.random() * 6;
        const p = particle(px, py, s, s, smoke ? 'background:#5a5f66;border-radius:50%;opacity:.5' : `background:${['#FFB347', '#FF7A2F', '#FFE27A'][i % 3]};border-radius:50% 50% 50% 0;transform:rotate(-45deg)`);
        p.animate([{transform: 'translate(0,0) scale(1)', opacity: smoke ? .45 : 1}, {transform: `translate(${(Math.random() - .5) * 30}px,${-40 - Math.random() * 50}px) scale(${smoke ? 2.2 : .3})`, opacity: 0}], {duration: smoke ? 1600 : 700 + Math.random() * 400, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove();
      }
      if (now < end) requestAnimationFrame(burn);
    })();
  }
  B.remove();
  const base = r.left + r.width / 2;
  ['ash', 'sticks'].forEach((k, i) => scene.addMess(k, base + (i ? 26 : -18), t.dataset.tree));
  await wait(RM.matches ? 0 : 700);
  if (onOlympus) { if (!strikeTree.told) { strikeTree.told = 1; toast("Zeus struck a tree. Hurl Poseidon's trident to wash the playground clean."); } }
  else setTimeout(() => wash(t), 30000);                          // on other pages it cleans itself up after 30 s
}
// a flung bolt flies on (with a little gravity) until it hits a tree or the ground
function fling(b, x, y, vx, vy) {
  const s = Math.min(1, 2400 / Math.hypot(vx, vy)); vx *= s; vy *= s;        // cap the speed
  let last = performance.now();
  (function step(t) {
    const dt = Math.min(.033, (t - last) / 1000); last = t;
    vy += 1500 * dt; x += vx * dt; y += vy * dt;
    place(b, x, y, 56); b.style.rotate = (Math.atan2(vy, vx) * 180 / Math.PI - 90) + 'deg';
    const tr = scene.treeAt(x, y);
    if (tr) return strikeTree(tr, b, true);
    if (y >= scene.surface() - 4) return groundStrike(b, x);
    if (x < -100 || x > innerWidth + 100 || y < -400) return b.remove();
    requestAnimationFrame(step);
  })(last);
}
function groundStrike(b, x) {
  const y = scene.surface(); b.remove(); play('bolt');
  if (!RM.matches) { boltFx(x, y);
    for (let i = 0; i < 16; i++) { const a = -Math.PI * (.15 + Math.random() * .7), d = 30 + Math.random() * 70, sz = 3 + Math.random() * 4;
      const p = particle(x, y, sz, sz, `background:${['#4b3a2a', '#6d7680', '#2f4a33'][i % 3]};clip-path:${ROCK[i % 3]}`);
      p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d + 40}px)`, opacity: 0}], {duration: 700, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove(); } }
  scene.addMess('scorch', x); scene.addMess('rocks', x + 30);
}
// Medusa turns a tree to stone, or a stone tree back to wood and leaves
async function stoneTree(t, fromDrag) {
  if (busy) return; busy = true;
  const M = TOOLS.medusa.el, r = t.getBoundingClientRect(), x = r.left + r.width / 2, y = Math.max(70, r.top - 20), back = t.classList.contains('statue');
  if (!fromDrag) liftOff('medusa');
  M.classList.add('awake'); await flyTo(M, x, y, 130, 200);
  M.classList.add(back ? 'thawing' : 'freezing'); play(back ? 'thaw' : 'freeze');
  if (!RM.matches) for (let i = 0; i < 18; i++) {
    const px = r.left + Math.random() * r.width, py = r.top + Math.random() * r.height * .7, sz = 4 + Math.random() * 6;
    const p = particle(px, py, sz, sz, back ? `background:${['#FF7A2F', '#FFE27A', '#7BD88F'][i % 3]};border-radius:50%` : `background:${['#8FA39A', '#5E9C78', '#7E9486'][i % 3]};clip-path:${ROCK[i % 3]}`);
    p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${(Math.random() - .5) * 40}px,${back ? -50 : 40}px)`, opacity: 0}], {duration: 900, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove();
  }
  await wait(RM.matches ? 0 : 500); t.classList.toggle('statue', !back); await wait(RM.matches ? 0 : 600);
  toast(back ? 'The tree is wood and leaves again.' : 'Medusa turned the tree to stone. Drag her onto it again to bring it back.');
  busy = false; sendHome('medusa');
}
// Poseidon washes debris away with a wave; charred trees in its path grow back
let actxW = null;
function whoosh() { if (!soundOn) return; try { actxW ||= new (window.AudioContext || window.webkitAudioContext)(); const a = actxW, n = a.sampleRate * .9, buf = a.createBuffer(1, n, a.sampleRate), d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.sin(Math.PI * i / n);
  const src = a.createBufferSource(), f = a.createBiquadFilter(), g = a.createGain(); src.buffer = buf; f.type = 'lowpass'; f.frequency.setValueAtTime(400, a.currentTime); f.frequency.linearRampToValueAtTime(1800, a.currentTime + .5); g.gain.value = .25;
  src.connect(f); f.connect(g); g.connect(a.destination); src.start(); } catch (e) {} }
// a struck tree on a page other than Olympus tidies itself up: its debris fades and it grows back
function wash(t) {
  $$(`.mess[data-of="${t.dataset.tree}"]`).forEach(m => m.animate([{opacity: 1}, {opacity: 0}], {duration: 500, fill: 'forwards'}).onfinish = () => m.remove());
  t.classList.remove('struck');
}
async function zeusStrike(c, fromDrag) {
  if (busy) return;
  const job = c.dataset.job;
  const held = fromDrag ? shot : null; if (held) shot = null;
  if (isRunning(c) && !(await confirmInterrupt('bolt', job))) { fizzle(held); return; }
  busy = true;
  const B = held || newShot(...homeOf('bolt')), r = c.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  await flyTo(B, x, Math.max(50, r.top - 30), 56, 150);
  play('bolt');
  const req = post('bolt', job).catch(() => ({ok: false, msg: 'no answer'}));
  if (!RM.matches) {
    B.style.opacity = '0';
    boltFx(x, y);
    const zap = document.createElement('div'); zap.style.cssText = 'position:absolute;inset:0;border-radius:12px;background:#FFE27A;pointer-events:none'; c.append(zap);
    zap.animate([{opacity: 0}, {opacity: .45, offset: .15}, {opacity: 0}], {duration: 900, easing: 'ease-out'}).onfinish = () => zap.remove();
  }
  const res = await req; await wait(RM.matches ? 0 : 900);
  toast(res.ok ? SAY.bolt.ok(job, res.msg) : failText('bolt', job, res.msg));
  B.remove(); busy = false; setTimeout(refresh, 1200);
}
