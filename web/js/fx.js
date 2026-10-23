// Effects shared by every section (docs/fx.md): Watch's powers, Olympus, and server plugins through api.fx.
// They draw in the #fx layer (docs/scene.md) and check reduced motion (RM, core.js) themselves: with it on they are skipped or
// become a short fade, so the state they confirm must always be shown some other way too (a word, an icon).

// one piece of an effect: a positioned div in the #fx layer; the caller animates it and removes it
function particle(x, y, w, h, style) { const p = document.createElement('div'); p.className = 'p'; p.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${h}px;${style}`; $('#fx').appendChild(p); return p; }
const ROCK = ['polygon(10% 30%,45% 0,90% 15%,100% 60%,60% 100%,10% 85%)', 'polygon(0 40%,35% 5%,80% 0,100% 45%,75% 95%,20% 100%)', 'polygon(20% 0,85% 20%,100% 75%,50% 100%,0 70%)'];

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

// The shared effects, also given to server plugins as api.fx. A target is an element or a point [x, y] on the screen.
// Each one returns a promise that settles when it has played (at once with reduced motion), so a caller can await it.
const fx = (() => {
  const rnd = (a, b) => a + Math.random() * (b - a);
  const where = t => { if (Array.isArray(t)) return t; const r = t.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
  const SHAPE = {dot: () => 'border-radius:50%', leaf: () => 'border-radius:0 70% 0 70%', rock: i => `clip-path:${ROCK[i % 3]}`, spark: () => 'border-radius:1px'};
  const played = anims => Promise.all(anims.map(a => a.finished.catch(() => {}))).then(() => {});
  const still = Promise.resolve();
  // pieces fly out from a point and fade: a small "yes, that worked" (a correct idea, a delivery arrived)
  function burst(target, {colors = ['#FFE27A', '#E7C35A', '#FFF6C2'], n = 18, spread = 70, size = [3, 6], shape = 'dot', fall = 20, ms = 700} = {}) {
    if (RM.matches) return still;
    const [x, y] = where(target), form = SHAPE[shape] || SHAPE.dot, out = [];
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, d = rnd(spread * .4, spread), s = rnd(size[0], size[1]);
      const p = particle(x - s / 2, y - s / 2, s, shape === 'leaf' ? s * 1.6 : s, `background:${colors[i % colors.length]};${form(i)}`);
      const an = p.animate([{transform: 'translate(0,0) rotate(0)', opacity: 1}, {transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d + fall}px) rotate(${rnd(-180, 180)}deg)`, opacity: 0}],
        {duration: rnd(ms * .7, ms * 1.3), easing: 'cubic-bezier(.2,.7,.4,1)', fill: 'forwards'});
      an.onfinish = () => p.remove(); out.push(an);
    }
    return played(out);
  }
  // a ribbon of glowing motes swirls from one place to another along a lifted curve (after SoulSeed's heal swirl):
  // something moved there (a card to its lesson, a parcel to its shelf)
  function motes(from, to, {color = '#FFE27A', n = 22, ms = 900, lift = 60} = {}) {
    if (RM.matches) return still;
    const [x0, y0] = where(from), [x1, y1] = where(to), cx = (x0 + x1) / 2, cy = Math.min(y0, y1) - lift, out = [];
    const len = Math.hypot(x1 - x0, y1 - y0) || 1, nx = -(y1 - y0) / len, ny = (x1 - x0) / len;     // the normal: motes sway across the path
    for (let i = 0; i < n; i++) {
      const s = rnd(2, 5), phase = rnd(0, Math.PI * 2), amp = rnd(3, 9), steps = [];
      for (let k = 0; k <= 8; k++) {
        const t = k / 8, u = 1 - t, sway = Math.sin(t * Math.PI * 2 + phase) * amp * Math.sin(t * Math.PI);
        const px = u * u * x0 + 2 * u * t * cx + t * t * x1 + nx * sway, py = u * u * y0 + 2 * u * t * cy + t * t * y1 + ny * sway;
        steps.push({transform: `translate(${px - x0}px,${py - y0}px) scale(${1 - .5 * t})`, opacity: k === 0 ? 0 : k === 8 ? 0 : 1});
      }
      const p = particle(x0 - s / 2, y0 - s / 2, s, s, `border-radius:50%;background:radial-gradient(circle,#fff 0,${color} 55%,transparent 72%);box-shadow:0 0 ${s * 2}px ${color}`);
      const an = p.animate(steps, {duration: ms, delay: (i / n) * ms * .6, easing: 'ease-in-out', fill: 'both'});
      an.onfinish = () => p.remove(); out.push(an);
    }
    return played(out);
  }
  // one sheen sweeps across an element: "this changed since you last looked". Reduced motion: a soft glow that fades.
  function glint(el, {color = 'rgba(255,226,122,.35)'} = {}) {
    const r = el.getBoundingClientRect(), round = getComputedStyle(el).borderRadius;
    const box = particle(r.left, r.top, r.width, r.height, `overflow:hidden;border-radius:${round}`);
    if (RM.matches) { const an = box.animate([{boxShadow: `inset 0 0 0 2px ${color}`}, {boxShadow: 'inset 0 0 0 2px transparent'}], {duration: 900}); an.onfinish = () => box.remove(); return played([an]); }
    const sheen = document.createElement('i'), w = Math.max(40, r.width * .35);
    sheen.style.cssText = `position:absolute;top:0;bottom:0;left:0;width:${w}px;background:linear-gradient(105deg,transparent,${color},transparent)`;
    box.append(sheen);
    const an = sheen.animate([{transform: `translateX(${-w}px)`}, {transform: `translateX(${r.width}px)`}], {duration: 750, easing: 'ease-in-out'});
    an.onfinish = () => box.remove();
    return played([an]);
  }
  // an element's area breaks into chunks that fall away (the element itself stays: the caller decides what happens to it)
  function pieces(el, {colors = ['#8FA39A', '#5E9C78', '#7E9486'], cols = 6, rows = 3, ms = 1000} = {}) {
    if (RM.matches) return still;
    const r = el.getBoundingClientRect(), cw = r.width / cols, ch = r.height / rows, out = [];
    for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
      const p = particle(r.left + i * cw, r.top + j * ch, cw + 1, ch + 1, `background:${colors[(i + j) % colors.length]};clip-path:${ROCK[(i + j) % 3]}`);
      const an = p.animate([{transform: 'translate(0,0) rotate(0)', opacity: 1}, {transform: `translate(${rnd(-60, 60)}px,${rnd(200, 460)}px) rotate(${rnd(-110, 110)}deg)`, opacity: 0}],
        {duration: rnd(ms * .9, ms * 1.4), delay: rnd(0, 250), easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards'});
      an.onfinish = () => p.remove(); out.push(an);
    }
    return played(out);
  }
  // Zeus's bolt from the top of the screen to the target
  function bolt(target) { if (RM.matches) return still; const [x, y] = where(target); boltFx(x, y); return new Promise(ok => setTimeout(ok, 700)); }
  return {burst, motes, glint, pieces, bolt};
})();
