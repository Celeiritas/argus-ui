// Argus UI - the scene behind every page: sky, Olympus, ground, seasonal trees, live weather (see docs/scene.md).
/* ---------- scene: season from the date, weather from the server (api/sky), trees Zeus can strike ----------
   Preview any look with URL options, e.g.  ?sky=storm&season=fall&night=1   (sky: clear cloudy rain storm snow fog) */
const scene = (() => {
  const SC = $('#scene'), Q = new URLSearchParams(location.search);
  let W = {sky: 'clear', night: false, south: false, wind: 5, precip: 0}, season = 'summer', live = null, liveSky = null;
  const O = {sky: Q.get('sky') || undefined, season: Q.get('season') || undefined, night: Q.has('night') ? Q.get('night') !== '0' : undefined};   // overrides (Olympus controls / URL)
  const seasonOf = (d, south) => { const m = (d.getMonth() + (south ? 6 : 0)) % 12; return m === 11 || m < 2 ? 'winter' : m < 5 ? 'spring' : m < 8 ? 'summer' : 'fall'; };
  // grass tufts (one tile, repeated along the ground)
  const tuft = c => `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 16'><path d='M2 16 L5 6 L7 16 M12 16 L16 3 L18 16 M22 16 L24 8 L27 16 M34 16 L38 4 L40 16 M47 16 L49 9 L52 16 M58 16 L62 2 L64 16 M70 16 L72 7 L75 16 M82 16 L86 5 L88 16 M91 16 L93 9 L95 16' fill='${c}'/></svg>`)}")`;
  // ---- trees: brown trunk; crown by season (summer green, fall red/orange/yellow, winter bare + snow, spring green + blossom)
  const rnd = (seed => () => (seed = (seed * 16807) % 2147483647) / 2147483647)(7);
  const PAL = {summer: ['#2f6b3a', '#3d8049', '#27592f', '#4a8f53'], fall: ['#b8452f', '#d9822b', '#d9b13b', '#a8382a', '#e09a34'], spring: ['#5d9a4c', '#74ad5a', '#4f8a42', '#86bb68']};
  function treeSVG(kind) {
    const wood = `<g class="wood" stroke="#6b4a2f" stroke-linecap="round" fill="none"><path d="M60 160 L59 104" stroke-width="9"/><path d="M59 118 Q46 98 34 84" stroke-width="5"/><path d="M59 108 Q72 88 86 76" stroke-width="5"/><path d="M59 104 L60 62" stroke-width="5"/><path d="M60 80 Q50 66 44 54" stroke-width="3"/><path d="M60 74 Q70 62 78 52" stroke-width="3"/><path d="M34 84 Q26 78 22 70 M86 76 Q94 70 98 62" stroke-width="2.5"/></g>`;
    if (kind === 'winter') return `<svg viewBox="0 0 120 162">${wood}<g class="snowcap" stroke="#E6ECF1" stroke-linecap="round" fill="none" opacity=".9"><path d="M36 82 Q46 92 56 112" stroke-width="2.2"/><path d="M84 74 Q74 84 62 104" stroke-width="2.2"/><path d="M46 54 Q52 64 58 76 M76 52 Q70 62 62 72" stroke-width="1.8"/><path d="M24 68 Q28 76 34 82 M96 60 Q92 68 86 74" stroke-width="1.6"/></g><ellipse cx="60" cy="160" rx="30" ry="4" fill="#E6ECF1" opacity=".75"/></svg>`;
    const pal = PAL[kind], blobs = [[60, 56, 30], [38, 72, 22], [82, 68, 24], [50, 40, 20], [72, 38, 20], [60, 80, 22]];
    let crown = blobs.map(([x, y, r], i) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${pal[i % pal.length]}"/>`).join('');
    crown += blobs.slice(0, 4).map(([x, y, r]) => `<circle cx="${x - r * .3}" cy="${y - r * .35}" r="${r * .45}" fill="#ffffff" opacity=".06"/>`).join('');
    if (kind === 'spring') crown += Array.from({length: 14}, () => `<circle cx="${30 + rnd() * 60}" cy="${30 + rnd() * 55}" r="2.2" fill="#f2b6c6"/>`).join('');
    const leaves = kind === 'fall' ? Array.from({length: 4}, (_, i) => `<ellipse class="leaf" cx="${40 + rnd() * 40}" cy="${60 + rnd() * 20}" rx="3" ry="1.8" fill="${pal[i % pal.length]}" style="--fd:${7 + rnd() * 6}s;--fdl:${rnd() * 8}s;--fx:${-50 + rnd() * 40}px"/>`).join('') : '';
    return `<svg viewBox="0 0 120 162">${wood}<g class="crown">${crown}</g>${leaves}</svg>`;
  }
  function plant(fresh) {
    const w = innerWidth, keep = fresh ? {} : Object.fromEntries($$('.tree').map(t => [t.dataset.tree, ['struck', 'statue'].filter(k => t.classList.contains(k))]));
    const spots = onOlympus ? (w < 768 ? [.07, .3, .7, .93] : [.03, .09, .16, .24, .32, .68, .76, .84, .91, .97]) : w < 768 ? [.08, .92] : w < 1600 ? [.05, .15, .85, .95] : [.04, .12, .21, .79, .88, .96];
    $('#trees').innerHTML = spots.map((x, i) => { const h = 130 + ((i * 37) % 4) * 18 + (w < 768 ? -30 : 0);
      return `<div class="tree" data-tree="${i}" style="left:${x * 100}%;width:${h * .74}px"><div class="sway" style="--sway:${6 + i % 3}s;--lean:${(.6 + W.wind / 25).toFixed(2)}deg">${treeSVG(season)}</div></div>`; }).join('');
    $$('.tree').forEach(t => (keep[t.dataset.tree] || []).forEach(k => t.classList.add(k)));
  }
  // ---- stars for clear nights
  $('#stars').innerHTML = Array.from({length: 70}, () => `<circle cx="${rnd() * 1000}" cy="${rnd() * 560}" r="${(.6 + rnd() * 1.2).toFixed(1)}" fill="#E6ECF1" opacity="${(.3 + rnd() * .6).toFixed(2)}"/>`).join('');
  // ---- weather canvas: rain streaks / snowflakes; storms flash behind Olympus
  const cv = $('#wx'), cx = cv.getContext('2d'); let parts = [], raf = 0, last = 0, flashT = 0;
  function size() { const d = Math.min(2, devicePixelRatio || 1); cv.width = innerWidth * d; cv.height = innerHeight * d; cx.setTransform(d, 0, 0, d, 0, 0); }
  function seed() {
    const area = innerWidth * innerHeight, wet = W.sky === 'rain' || W.sky === 'storm', heavy = W.sky === 'storm' || W.precip > 2;
    const n = W.sky === 'snow' ? area / 9000 : wet ? area / (heavy ? 2600 : 5200) : 0;
    parts = Array.from({length: Math.min(900, n | 0)}, () => ({x: Math.random() * innerWidth, y: Math.random() * innerHeight, z: .4 + Math.random() * .6, p: Math.random() * 6.28}));
  }
  function draw(dt) {
    cx.clearRect(0, 0, innerWidth, innerHeight);
    const snow = W.sky === 'snow', slant = Math.min(.5, W.wind / 60);
    cx.strokeStyle = 'rgba(167,182,196,.32)'; cx.fillStyle = 'rgba(230,236,241,.75)'; cx.lineWidth = 1;
    if (!snow) cx.beginPath();
    for (const q of parts) {
      if (snow) { q.y += (18 + 30 * q.z) * dt; q.p += dt; q.x += Math.sin(q.p) * 12 * dt + slant * 20 * dt; cx.globalAlpha = q.z; cx.beginPath(); cx.arc(q.x, q.y, 1 + q.z * 1.6, 0, 6.28); cx.fill(); }
      else { const v = (520 + 380 * q.z) * dt; q.y += v; q.x += v * slant; const l = 10 + 10 * q.z; cx.moveTo(q.x, q.y); cx.lineTo(q.x - l * slant, q.y - l); }
      if (q.y > innerHeight) { q.y = -10; q.x = Math.random() * innerWidth; } if (q.x > innerWidth + 20) q.x = -20;
    }
    if (!snow) cx.stroke(); cx.globalAlpha = 1;
  }
  function loop(t) {
    const dt = Math.min(.05, (t - last) / 1000 || 0); last = t;
    if (!document.hidden) draw(dt);
    if (W.sky === 'storm' && t > flashT) { flashT = t + 5000 + Math.random() * 9000; stormFlash(); }
    raf = requestAnimationFrame(loop);
  }
  // the massif keeps its full height: 'meet' when the screen is wide (the ranges run on past the sides), 'slice' when narrow
  function fit() {
    const o = $('.olympus', SC), r = o.getBoundingClientRect();
    o.setAttribute('preserveAspectRatio', r.width / r.height > 1600 / 440 ? 'xMidYMax meet' : 'xMidYMax slice');
    const m = o.getScreenCTM(); if (m) { SC.style.setProperty('--sx', (m.a * 800 + m.e) + 'px'); SC.style.setProperty('--sy', (m.d * 110 + m.f) + 'px'); }
  }
  function stormFlash() {
    const g = $('.skyflash', SC), b = $('.sbolt', SC);
    g.animate([{opacity: 0}, {opacity: 1, offset: .1}, {opacity: .2, offset: .3}, {opacity: .8, offset: .4}, {opacity: 0}], {duration: 900});
    b.animate([{opacity: 0}, {opacity: 1, offset: .1}, {opacity: 0, offset: .3}, {opacity: .9, offset: .4}, {opacity: 0}], {duration: 600});
  }
  function apply() {
    W = Object.assign({}, live || {sky: 'clear', night: (h => h < 6 || h >= 20)(new Date().getHours()), south: false, wind: 5, precip: 0});
    if (O.sky) W.sky = O.sky; if (O.night !== undefined) W.night = O.night;
    season = O.season || seasonOf(new Date(), W.south);
    SC.dataset.sky = W.sky; SC.dataset.season = season; SC.toggleAttribute('data-night', W.night);
    const snowy = season === 'winter' || W.sky === 'snow';
    SC.style.setProperty('--tufts', tuft(snowy ? '#9aa7b3' : '#24442f'));
    const glow = {clear: '#FFE27A', cloudy: '#E6D9A8', rain: '#9fc3ff', storm: '#cfe0ff', snow: '#ffffff', fog: '#d8dde2'}[W.sky];
    $$('.glow', SC).forEach(g => g.setAttribute('stop-color', glow));
    plant(); fit(); size(); seed(); cancelAnimationFrame(raf); raf = 0;
    if (RM.matches) draw(0);                 // reduced motion: a still picture of the weather
    else if (parts.length || W.sky === 'storm') raf = requestAnimationFrame(loop); else draw(0);
  }
  async function load() {
    try { const r = await (await fetch(url('api/sky'), {cache: 'no-store'})).json();
      liveSky = r;
      if (r.sky) { live = {sky: r.sky, night: !r.is_day, south: r.south, wind: r.wind || 5, precip: r.precip || 0};
        $('#wxText').textContent = `${r.desc} · ${r.temp}°${r.unit}`;
        if (here === 'home') $('#sub').textContent = home.greet()[1];       // the greeting was drawn before the weather came
        $('#wxText').title = `Weather from ${r.source}, updated ${new Date(r.at * 1000).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}${r.stale ? ' (last reading; the weather service is not answering)' : ''}`; }
    } catch (e) {}
    apply(); if ($('#liveNote')) labNote();
  }
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { plant(); fit(); size(); seed(); if (!raf) draw(0); }, 200); });
  load(); setInterval(load, 20 * 60 * 1000);
  // ---- trees under the pointer (they sit behind the page, so hit-test them where nothing else covers them)
  const covered = (x, y) => { const el = document.elementFromPoint(x, y); return !!(el && el.closest('.card,.panel,.lab,.dock,button,a,input,textarea,label,.argus,.tools,.realms')); };
  const inside = (el, x, y, pad = 0) => { const r = el.getBoundingClientRect(); return x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad; };
  // a tree the pointer is over; stone trees only for Medusa (she turns them back)
  function treeAt(x, y, stone) {
    if (covered(x, y)) return null;
    return $$(stone ? '.tree:not(.struck)' : '.tree:not(.struck):not(.statue)').find(t => { const r = t.getBoundingClientRect(); return x >= r.left + r.width * .1 && x <= r.right - r.width * .1 && y >= r.top && y <= r.bottom; }) || null;
  }
  // something Poseidon can wash away: a charred tree, or debris (sticks, ash, scorch marks, rubble)
  function messAt(x, y) { if (covered(x, y)) return null; return $$('.tree.struck').find(t => inside(t, x, y)) || $$('.mess').find(m => inside(m, x, y, 30)) || null; }
  const MESS = {
    sticks: () => `<svg width="60" height="14" viewBox="0 0 60 14"><path d="M4 12 L26 8 M30 12 L52 6 M18 13 L36 11" stroke="#2a2018" stroke-width="3" stroke-linecap="round"/><path d="M10 11 L14 7" stroke="#2a2018" stroke-width="2" stroke-linecap="round"/></svg>`,
    ash: () => `<svg width="70" height="12" viewBox="0 0 70 12"><ellipse cx="35" cy="9" rx="33" ry="4" fill="#3b3f44"/><ellipse cx="30" cy="7" rx="16" ry="3" fill="#585d63"/></svg>`,
    scorch: () => `<svg width="90" height="16" viewBox="0 0 90 16"><defs><radialGradient id="sc"><stop offset="0" stop-color="#0d0d0d" stop-opacity=".9"/><stop offset="1" stop-color="#0d0d0d" stop-opacity="0"/></radialGradient></defs><ellipse cx="45" cy="10" rx="44" ry="7" fill="url(#sc)"/></svg>`,
    bones: () => `<svg width="50" height="12" viewBox="0 0 50 12"><path d="M6 10 L20 8 M24 11 L38 8" stroke="#E8E4D8" stroke-width="2.6" stroke-linecap="round"/><circle cx="44" cy="7.5" r="4" fill="#E8E4D8"/><circle cx="42.6" cy="7" r="1" fill="#1C2127"/><circle cx="45.4" cy="7" r="1" fill="#1C2127"/></svg>`,
    wine: () => `<svg width="64" height="10" viewBox="0 0 64 10"><ellipse cx="32" cy="6" rx="30" ry="3.6" fill="#5a1838" opacity=".85"/><ellipse cx="25" cy="5" rx="12" ry="1.6" fill="#9b2f62" opacity=".6"/></svg>`,
    rocks: () => `<svg width="56" height="16" viewBox="0 0 56 16"><path d="M4 16 L8 9 L15 8 L18 16 Z" fill="#6d7680"/><path d="M22 16 L25 6 L34 5 L37 16 Z" fill="#59626b"/><path d="M41 16 L44 11 L51 10 L53 16 Z" fill="#7d8690"/></svg>`,
  };
  function addMess(kind, x, of) { const m = document.createElement('div'); m.className = 'mess'; m.dataset.kind = kind; if (of != null) m.dataset.of = of; m.style.left = x + 'px'; m.innerHTML = MESS[kind](); $('#debris').append(m); m.animate([{opacity: 0}, {opacity: 1}], {duration: 300}); return m; }
  // ----- Olympus controls: preview any weather, season or time of day ("Live" follows the real ones)
  function labNote() {
    const r = liveSky, n = $('#liveNote'); if (!n) return;
    n.textContent = r && r.sky ? `Live right now: ${r.desc}, ${r.temp}°${r.unit}, ${seasonOf(new Date(), r.south)}. Weather from ${r.source}.` : `Live weather isn't set up on this server, so "Live" shows the season and time of day only.`;
  }
  const LBL = {sky: {clear: 'Clear', cloudy: 'Cloudy', rain: 'Rain', storm: 'Storm', snow: 'Snow', fog: 'Fog'}, season: {spring: 'Spring', summer: 'Summer', fall: 'Fall', winter: 'Winter'}};
  function labSum() { const n = $('#labNow'); if (n) n.textContent = `${O.sky ? LBL.sky[O.sky] : 'Live weather'} · ${O.season ? LBL.season[O.season] : 'live season'} · ${O.night === undefined ? 'live time' : O.night ? 'night' : 'day'}`; }
  function lab(host) {               // collapsed by default so the field stays reachable; remembers open/closed per browser
    const seg = (key, legend, opts) => { const cur = key === 'time' ? (O.night === undefined ? 'live' : O.night ? 'night' : 'day') : (O[key] || 'live');
      return `<fieldset><legend>${legend}</legend><div class="seg">${opts.map(([v, n]) => `<label><input type="radio" name="${key}" value="${v}" ${v === cur ? 'checked' : ''}><span>${n}</span></label>`).join('')}</div></fieldset>`; };
    let open = false; try { open = localStorage.getItem('olympus-lab') === 'open'; } catch (e) {}
    host.innerHTML = `<details class="lab" ${open ? 'open' : ''}><summary>Weather, season, time <span class="now" id="labNow"></span></summary>
      ${seg('sky', 'Weather', [['live', 'Live'], ['clear', 'Clear'], ['cloudy', 'Cloudy'], ['rain', 'Rain'], ['storm', 'Storm'], ['snow', 'Snow'], ['fog', 'Fog']])}
      ${seg('season', 'Season', [['live', 'Live'], ['spring', 'Spring'], ['summer', 'Summer'], ['fall', 'Fall'], ['winter', 'Winter']])}
      ${seg('time', 'Time of day', [['live', 'Live'], ['day', 'Day'], ['night', 'Night']])}
      <p class="live" id="liveNote"></p></details>`;
    $('details.lab', host).addEventListener('toggle', e => { try { localStorage.setItem('olympus-lab', e.target.open ? 'open' : 'closed'); } catch (er) {} });
    $$('.lab input', host).forEach(i => i.onchange = () => {
      if (i.name === 'time') O.night = i.value === 'live' ? undefined : i.value === 'night'; else O[i.name] = i.value === 'live' ? undefined : i.value;
      const q = new URLSearchParams(); if (O.sky) q.set('sky', O.sky); if (O.season) q.set('season', O.season); if (O.night !== undefined) q.set('night', O.night ? 1 : 0);
      history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));      // the address shares this look
      apply(); labSum();
    });
    labNote(); labSum();
  }
  const gh = () => $('.ground', SC).offsetHeight, surface = () => innerHeight - gh() + 4;     // y where things land
  // everything Poseidon's tsunami sweeps away: debris, flowers, skeletons, arrows, holes, owls; trees grow back fresh (vines go with them)
  function reset() { $$('.mess,.flower,.skel,.arrowstuck,.hole,.owl', SC).forEach(e => e.remove()); plant(true); }
  return {treeAt, messAt, addMess, lab, reset, covered, inside, gh, surface, get season() { return season; }};
})();
