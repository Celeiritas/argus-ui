// Argus UI - the Olympus playground: the Ω dock of items and everything they do to the scene.
/* ---------- Olympus playground: items from the gods, dragged or flung onto the field ----------
   The twelve Olympians sit in an Ω with Zeus in the middle; Medusa and Hades (not Olympians) have their own spot below.
   Release an item and it keeps its speed and falls (so a still release drops it straight down); over the dock it goes back. */
const playground = (() => {
  // all twelve on the Ω, left foot to right foot, Zeus at the top: six to his left (Hera beside him), five to his right (Poseidon beside him)
  const OMEGA = [['dionysus', 'Dionysus', 'cup'], ['hermes', 'Hermes', 'sandal'], ['artemis', 'Artemis'], ['apollo', 'Apollo', 'bow'], ['demeter', 'Demeter', 'seeds'], ['hera', 'Hera'],
    ['zeus', 'Zeus', 'bolt'], ['poseidon', 'Poseidon', 'trident'], ['hephaestus', 'Hephaestus', 'hammer'], ['athena', 'Athena', 'owl'], ['ares', 'Ares'], ['aphrodite', 'Aphrodite']];
  const ZI = 6, LEFT = 6, RIGHT = 5;
  const angleOf = i => i < ZI ? 215 - i * (125 / LEFT) : 90 - (i - ZI) * (125 / RIGHT);
  const GROUPS = [['Chthonic', [['hades', 'Hades', 'bident']]], ['Beyond Olympus', [['medusa', 'Medusa', 'snake']]]];   // the underworld, and everyone else who isn't an Olympian
  // ---- item medallions (the dock shows the item, not the god)
  const ART = {
    bolt: '<path d="M56 12 L30 54 L47 54 L38 88 L70 42 L52 42 L62 12 Z" fill="#FFE27A" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>',
    snake: '<path d="M30 80 C22 64 40 58 52 60 C68 62 74 48 64 38 C58 31 49 33 47 25" stroke="#3f7a57" stroke-width="10" fill="none" stroke-linecap="round"/><path d="M30 80 C22 64 40 58 52 60 C68 62 74 48 64 38 C58 31 49 33 47 25" stroke="#8FC4A4" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-dasharray="1 5"/><ellipse cx="46" cy="22" rx="8" ry="6" fill="#4E8A66" transform="rotate(-20 46 22)"/><circle cx="43.5" cy="20" r="1.8" fill="#E7C35A"/><path d="M38 18 l-6 -3 m6 3 l-6 2" stroke="#D64545" stroke-width="1.4" stroke-linecap="round"/>',
    trident: '<g stroke="#C9D6E3" stroke-width="4" fill="none" stroke-linecap="round"><path d="M50 90 L50 30"/><path d="M34 22 L34 32 Q34 40 50 40 Q66 40 66 32 L66 22"/><path d="M50 40 L50 16"/></g><path d="M50 7 L45 18 L55 18 Z M34 13 L30 23 L38 23 Z M66 13 L62 23 L70 23 Z" fill="#E6ECF1"/><rect x="45" y="45" width="10" height="5" rx="2" fill="#E7C35A"/>',
    bident: '<g stroke="#a99dbf" stroke-width="4" fill="none" stroke-linecap="round"><path d="M50 92 L50 42"/><path d="M50 42 Q38 38 39 25 Q40 16 36 10"/><path d="M50 42 Q62 38 61 25 Q60 16 64 10"/></g><path d="M36 5 L32 15 L40 13 Z M64 5 L68 15 L60 13 Z" fill="#d8cfe6"/><path d="M39 23 l5 -2 M61 23 l-5 -2" stroke="#d8cfe6" stroke-width="2.4" stroke-linecap="round"/><ellipse cx="50" cy="46" rx="5.5" ry="3.8" fill="#8B6BB8"/><rect x="46.5" y="54" width="7" height="4" rx="1.5" fill="#6b5a86"/>',
    seeds: '<path d="M33 52 Q28 80 50 82 Q72 80 67 52 Q60 46 50 48 Q40 46 33 52 Z" fill="#C9A36A" stroke="#8a6a3e" stroke-width="2"/><path d="M39 50 Q50 56 61 50" stroke="#6b4a2f" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M50 48 Q47 34 38 30 Q47 31 50 40 Q53 31 62 30 Q53 34 50 48" fill="#7FBF5A"/><g fill="#E8D3A8"><ellipse cx="44" cy="66" rx="2.4" ry="1.6"/><ellipse cx="55" cy="70" rx="2.4" ry="1.6"/><ellipse cx="50" cy="61" rx="2.4" ry="1.6"/></g>',
    bow: '<path d="M40 12 Q76 50 40 88" stroke="#D9A441" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M40 12 L30 50 L40 88" stroke="#E6ECF1" stroke-width="1.3" fill="none"/><path d="M30 50 L76 50" stroke="#a0703f" stroke-width="2.6"/><path d="M76 45 L88 50 L76 55 Z" fill="#C9D6E3"/><path d="M30 50 l-6 -5 M30 50 l-6 5 M34 50 l-6 -5 M34 50 l-6 5" stroke="#F1A93B" stroke-width="2" stroke-linecap="round"/>',
    hammer: '<path d="M50 40 L66 84" stroke="#8a5a3a" stroke-width="7" stroke-linecap="round"/><path d="M28 32 L60 22 L66 38 L34 48 Z" fill="#8F99A3" stroke="#5d656d" stroke-width="2" stroke-linejoin="round"/><path d="M31 34 L60 25" stroke="#c3cad1" stroke-width="2" stroke-linecap="round"/><g fill="#FFB347"><circle cx="72" cy="30" r="2"/><circle cx="78" cy="40" r="1.5"/><circle cx="70" cy="19" r="1.2"/></g>',
    // 4.15: Hermes' winged sandal, Athena's owl on an olive sprig, Dionysus' cup of wine with grapes
    sandal: '<path d="M33 60 Q16 50 17 32 Q25 41 33 45 Q23 33 27 21 Q35 35 41 43 Q37 31 43 23 Q47 38 47 51 Z" fill="#E6ECF1" stroke="#A7B6C4" stroke-width="1.5" stroke-linejoin="round"/><path d="M27 37 L33 45 M33 31 L40 42" stroke="#A7B6C4" stroke-width="1.2"/><path d="M22 66 Q20 74 30 74 L74 74 Q81 74 79 68 Q76 63 66 63 L30 63 Z" fill="#8a5a3a" stroke="#5e3c26" stroke-width="1.5"/><path d="M38 63 Q42 50 54 51 Q60 52 62 63 M30 63 Q32 56 40 56" stroke="#C9A36A" stroke-width="3.5" fill="none" stroke-linecap="round"/><circle cx="54" cy="51" r="2.4" fill="#E7C35A"/>',
    owl: '<path d="M26 82 Q50 74 74 82" stroke="#6b8a3a" stroke-width="2.6" fill="none" stroke-linecap="round"/><g fill="#7FA650"><ellipse cx="32" cy="78" rx="5" ry="2" transform="rotate(-25 32 78)"/><ellipse cx="68" cy="78" rx="5" ry="2" transform="rotate(25 68 78)"/></g><path d="M34 40 L35 24 L44 34 Z M66 40 L65 24 L56 34 Z" fill="#8a7a5a"/><ellipse cx="50" cy="56" rx="19" ry="23" fill="#8a7a5a"/><ellipse cx="50" cy="63" rx="11" ry="14" fill="#d9c9a3"/><path d="M44 60 l3 3 3-3 3 3 3-3 M44 67 l3 3 3-3 3 3 3-3" stroke="#a8946a" stroke-width="1.2" fill="none"/><circle cx="42" cy="44" r="8.5" fill="#efe3c4"/><circle cx="58" cy="44" r="8.5" fill="#efe3c4"/><circle cx="42" cy="44" r="5" fill="#E7C35A"/><circle cx="58" cy="44" r="5" fill="#E7C35A"/><circle cx="42" cy="44" r="2.4" fill="#1C2127"/><circle cx="58" cy="44" r="2.4" fill="#1C2127"/><path d="M50 48 L47 52 L50 56 L53 52 Z" fill="#C9A36A"/><path d="M43 78 l-2 4 M47 78 v4 M53 78 v4 M57 78 l2 4" stroke="#C9A36A" stroke-width="1.6" stroke-linecap="round"/>',
    cup: '<path d="M31 38 Q16 33 21 22 Q25 16 31 25" stroke="#C9A36A" stroke-width="3.5" fill="none" stroke-linecap="round"/><path d="M69 38 Q84 33 79 22 Q75 16 69 25" stroke="#C9A36A" stroke-width="3.5" fill="none" stroke-linecap="round"/><path d="M29 36 Q29 62 50 64 Q71 62 71 36 Z" fill="#C9A36A" stroke="#8a6a3e" stroke-width="2"/><ellipse cx="50" cy="36" rx="21" ry="5" fill="#7a2048"/><ellipse cx="50" cy="36" rx="21" ry="5" fill="none" stroke="#E7C35A" stroke-width="2"/><path d="M47 64 L46 74 L54 74 L53 64 Z" fill="#a8844f"/><ellipse cx="50" cy="77" rx="13" ry="3.5" fill="#C9A36A" stroke="#8a6a3e" stroke-width="1.5"/><g fill="#6b3a8a"><circle cx="41" cy="48" r="2.8"/><circle cx="46.5" cy="49" r="2.8"/><circle cx="43.5" cy="53.5" r="2.8"/><circle cx="49" cy="54" r="2.4"/><circle cx="46" cy="58" r="2.4"/></g><path d="M52 47 Q61 41 63 48 Q59 53 52 47 Z" fill="#7FBF5A"/><path d="M45 45 Q47 42 51 43" stroke="#4f7a32" stroke-width="1.4" fill="none"/>',
  };
  const RING = {bolt: ['#E7C35A', '#33331c'], snake: ['#5E9C78', '#1d3329'], trident: ['#3B82C4', '#152c44'], bident: ['#8B6BB8', '#271d36'], seeds: ['#9BBF6A', '#24331c'], bow: ['#F1A93B', '#382a14'], hammer: ['#D9822B', '#382313'],
    sandal: ['#8EC9E8', '#16303d'], owl: ['#9BAA6A', '#262b18'], cup: ['#B04A8A', '#2e1424']};
  const medal = k => `<svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="46" fill="${RING[k][1]}" stroke="#A7B6C4" stroke-width="3.5"/><circle cx="50" cy="50" r="42" fill="url(#mhl)"/><circle cx="50" cy="50" r="42" fill="none" stroke="${RING[k][0]}" stroke-width="1.4"/>${ART[k]}</svg>`;
  // ---- what each item is, what it does, and how it flies (w×h px, aim = degrees added to its heading, lead = centre to tip)
  const ITEM = {
    bolt: {name: "Zeus's bolt", does: 'strikes trees, burns skeletons, scorches the ground', w: 34, h: 60, aim: -90, lead: 28, g: 1500,
      svg: '<svg viewBox="26 8 48 84"><path d="M56 12 L30 54 L47 54 L38 88 L70 42 L52 42 L62 12 Z" fill="#FFE27A" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/></svg>'},
    snake: {name: "Medusa's snake", does: 'turns a tree or skeleton to stone, or back again', w: 24, h: 64, aim: 90, lead: 30, g: 1400,
      svg: '<svg viewBox="0 0 24 64"><path d="M12 62 C2 52 22 44 12 34 C2 24 20 18 12 10" stroke="#3f7a57" stroke-width="6" fill="none" stroke-linecap="round"/><ellipse cx="12" cy="8" rx="5" ry="6.5" fill="#4E8A66"/><circle cx="10" cy="6" r="1.2" fill="#E7C35A"/><circle cx="14" cy="6" r="1.2" fill="#E7C35A"/><path d="M12 1.5 l-2 -3 m2 3 l2 -3" stroke="#D64545" stroke-width="1" stroke-linecap="round"/></svg>'},
    trident: {name: "Poseidon's trident", does: 'a tsunami washes the whole playground clean', w: 30, h: 110, aim: 90, lead: 54, g: 1300,
      svg: '<svg viewBox="0 0 30 110"><g stroke="#C9D6E3" stroke-width="3.2" fill="none" stroke-linecap="round"><path d="M15 108 L15 28"/><path d="M5 12 L5 22 Q5 30 15 30 Q25 30 25 22 L25 12"/><path d="M15 30 L15 8"/></g><path d="M15 0 L11 9 L19 9 Z M5 4 L2 12 L8 12 Z M25 4 L22 12 L28 12 Z" fill="#E6ECF1"/><rect x="11" y="34" width="8" height="4" rx="2" fill="#E7C35A"/></svg>'},
    bident: {name: "Hades' bident", does: 'raises a skeleton out of the ground, or crumbles one', w: 30, h: 110, aim: 90, lead: 54, g: 1400,
      svg: '<svg viewBox="0 0 30 110"><g stroke="#a99dbf" stroke-width="3.2" fill="none" stroke-linecap="round"><path d="M15 108 L15 32"/><path d="M15 32 Q6 29 7 17 Q8 9 5 3"/><path d="M15 32 Q24 29 23 17 Q22 9 25 3"/></g><path d="M5 0 L2 8 L8 6.5 Z M25 0 L28 8 L22 6.5 Z" fill="#d8cfe6"/><ellipse cx="15" cy="36" rx="4.5" ry="3" fill="#8B6BB8"/><rect x="12.5" y="42" width="5" height="3" rx="1" fill="#6b5a86"/></svg>'},
    seeds: {name: "Demeter's seeds", does: 'scatter and sprout flowers for the season', w: 30, h: 20, aim: null, lead: 6, g: 1300,
      svg: '<svg viewBox="0 0 30 20"><g fill="#E8D3A8" stroke="#8a6a3e" stroke-width=".8"><ellipse cx="6" cy="12" rx="3" ry="2"/><ellipse cx="13" cy="7" rx="3" ry="2"/><ellipse cx="20" cy="13" rx="3" ry="2"/><ellipse cx="25" cy="7" rx="3" ry="2"/><ellipse cx="14" cy="16" rx="3" ry="2"/></g></svg>'},
    bow: {name: "Apollo's bow", does: 'draw an arrow and let it fly; it sticks where it lands', w: 64, h: 12, aim: 0, lead: 32, g: 700,
      svg: '<svg viewBox="0 0 64 12"><path d="M5 6 L54 6" stroke="#a0703f" stroke-width="2.2"/><path d="M53 2 L63 6 L53 10 Z" fill="#C9D6E3"/><path d="M5 6 L0 1.5 M5 6 L0 10.5 M9 6 L4 1.5 M9 6 L4 10.5" stroke="#F1A93B" stroke-width="1.6" stroke-linecap="round"/></svg>'},
    hammer: {name: "Hephaestus' hammer", does: 'digs into the ground and smashes skeletons', w: 40, h: 64, aim: 'spin', lead: 30, g: 1600,
      svg: '<svg viewBox="0 0 40 64"><path d="M20 18 L20 60" stroke="#8a5a3a" stroke-width="6" stroke-linecap="round"/><path d="M3 4 H37 V20 H3 Z" fill="#8F99A3" stroke="#5d656d" stroke-width="2" stroke-linejoin="round"/><path d="M5 7 H35" stroke="#c3cad1" stroke-width="2" stroke-linecap="round"/></svg>'},
    sandal: {name: "Hermes' winged sandal", does: 'skims the ground and its wind carries the mess away', w: 60, h: 40, aim: null, lead: 14, g: 300,
      svg: '<svg viewBox="0 0 60 40"><g class="wing"><path d="M14 26 Q2 18 3 4 Q9 12 15 15 Q8 6 12 0 Q18 10 22 16 Q20 8 25 3 Q27 14 26 24 Z" fill="#E6ECF1" stroke="#A7B6C4" stroke-width="1.2" stroke-linejoin="round"/></g><path d="M6 31 Q4 38 12 38 L52 38 Q59 38 57 33 Q54 29 46 29 L12 29 Z" fill="#8a5a3a" stroke="#5e3c26" stroke-width="1.2"/><path d="M20 29 Q24 19 34 20 Q40 21 41 29 M12 29 Q14 23 21 23" stroke="#C9A36A" stroke-width="3" fill="none" stroke-linecap="round"/></svg>'},
    owl: {name: "Athena's owl", does: 'glides to a tree, a skull or the ground and keeps watch; click her for a word of wisdom', w: 40, h: 46, aim: null, lead: 20, g: 0, svg: ''},
    cup: {name: "Dionysus' cup", does: 'skeletons it splashes dance, trees grow grapevines, the ground gets a puddle of wine', w: 34, h: 36, aim: null, lead: 16, g: 1300,
      svg: '<svg viewBox="0 0 34 36"><path d="M7 10 Q0 7 2 2 Q4 0 7 4 M27 10 Q34 7 32 2 Q30 0 27 4" stroke="#C9A36A" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M5 9 Q5 24 17 25 Q29 24 29 9 Z" fill="#C9A36A" stroke="#8a6a3e" stroke-width="1.4"/><ellipse cx="17" cy="9" rx="12" ry="3" fill="#7a2048"/><path d="M15 25 L14.5 31 L19.5 31 L19 25 Z" fill="#a8844f"/><ellipse cx="17" cy="33" rx="8" ry="2.4" fill="#C9A36A"/><g fill="#6b3a8a"><circle cx="12" cy="15" r="1.8"/><circle cx="15.5" cy="16" r="1.8"/><circle cx="13.5" cy="19" r="1.8"/></g></svg>'},
  };
  // ---- small sounds made in the browser (the sound files are reserved for the big moments)
  let ac = null;
  const ctx = () => { try { return ac ||= new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return null; } };
  function tone(f0, f1, dur, type = 'triangle', gain = .12) { if (!soundOn) return; const a = ctx(); if (!a) return; const o = a.createOscillator(), g = a.createGain(), t = a.currentTime;
    o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur); g.gain.setValueAtTime(gain, t); g.gain.exponentialRampToValueAtTime(.001, t + dur); o.connect(g); g.connect(a.destination); o.start(t); o.stop(t + dur); }
  function noise(dur, f0, f1, gain = .2, type = 'lowpass', at = 0) { if (!soundOn) return; const a = ctx(); if (!a) return; const n = Math.max(1, a.sampleRate * dur | 0), b = a.createBuffer(1, n, a.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.sin(Math.PI * i / n); const s = a.createBufferSource(), f = a.createBiquadFilter(), g = a.createGain(), t = a.currentTime + at;
    s.buffer = b; f.type = type; f.frequency.setValueAtTime(f0, t); f.frequency.linearRampToValueAtTime(f1, t + dur); g.gain.value = gain; s.connect(f); f.connect(g); g.connect(a.destination); s.start(t); }
  const clatterS = () => { for (let i = 0; i < 9; i++) noise(.025, 2600, 1800, .25, 'bandpass', i * (.04 + Math.random() * .04)); };
  const clatter = () => playOr('rattle', clatterS), bonesFall = () => playOr('bonedeath', clatterS), dirt = () => playOr('dirt', () => noise(.4, 600, 200, .3));
  const pop = () => playOr('seed', () => tone(520 + Math.random() * 200, 900, .09, 'sine', .07));
  const twang = () => playOr('bow', () => { tone(240, 120, .28, 'triangle', .12); noise(.06, 3000, 1500, .08, 'bandpass'); });
  const thunk = () => playOr('arrowhit', () => noise(.09, 500, 200, .35));
  const surge = () => { noise(1.9, 300, 2400, .4); noise(1.2, 1800, 400, .25, 'lowpass', .7); };
  const whoosh = () => { noise(.7, 500, 2600, .16, 'bandpass'); noise(.6, 2400, 600, .1, 'bandpass', .5); };
  const hoot = () => { tone(440, 400, .22, 'sine', .09); setTimeout(() => tone(430, 380, .32, 'sine', .09), 330); };
  const clink = () => { tone(1900, 1800, .18, 'sine', .06); tone(2600, 2500, .12, 'sine', .04); };
  const splash = () => noise(.35, 1800, 500, .22, 'lowpass');
  const tune = () => [587, 740, 880, 740, 587, 659, 740, 587].forEach((f, i) => setTimeout(() => tone(f, f, .16, 'triangle', .07), i * 190));
  // ---- placing items: a thrown thing is a fixed box we move and rotate
  const SCN = $('#scene');
  function make(key, x, y) { const I = ITEM[key], e = document.createElement('div'); e.className = 'thrown ' + key; e.innerHTML = key === 'owl' ? OWL : I.svg; e.style.width = I.w + 'px'; e.style.height = I.h + 'px'; document.body.append(e); put(e, x, y, 90); return e; }
  function put(e, x, y, ang) { const k = e.className.split(' ')[1], I = ITEM[k]; e.style.left = (x - I.w / 2) + 'px'; e.style.top = (y - I.h / 2) + 'px'; e._x = x; e._y = y; e._a = ang;
    e.style.rotate = I.aim === 'spin' ? ang + 'deg' : I.aim === null ? '0deg' : (ang + I.aim) + 'deg'; }
  const tipOf = (k, x, y, a) => { const I = ITEM[k]; if (I.aim === 'spin' || I.aim === null) return [x, y + I.lead]; const r = a * Math.PI / 180; return [x + Math.cos(r) * I.lead, y + Math.sin(r) * I.lead]; };
  const fade = (e, ms = 300) => e && e.animate([{opacity: 1}, {opacity: 0}], {duration: RM.matches ? 1 : ms, fill: 'forwards'}).finished.then(() => e.remove());
  const onUI = (x, y) => { const el = document.elementFromPoint(x, y); return !!(el && el.closest('.dock,.lab,.realms,header,.toast')); };
  const skelAt = (x, y) => scene.covered(x, y) ? null : $$('.skel:not(.dying)').find(s => scene.inside(s, x, y, 4)) || null;
  // what each item reacts to on its way down (the ground is always last)
  function targetAt(k, x, y) {
    if (k === 'bolt') return skelAt(x, y) || scene.treeAt(x, y);
    if (k === 'snake') return skelAt(x, y) || scene.treeAt(x, y, true);
    if (k === 'trident' || k === 'bow') return skelAt(x, y) || (k === 'bow' ? scene.treeAt(x, y, true) || $$('.tree.struck').find(t => !scene.covered(x, y) && scene.inside(t, x, y)) : scene.treeAt(x, y, true));
    if (k === 'bident' || k === 'hammer') return skelAt(x, y);
    if (k === 'cup') return skelAt(x, y) || scene.treeAt(x, y);
    return null;                                  // the sandal skims and the owl glides: they pick their own way
  }
  let tipsShown = {};
  const tipOnce = (k, text) => { if (tipsShown[k]) return; tipsShown[k] = 1; toast(text); };
  // ---- flight: gravity, a capped speed, and a hit test at the tip every frame
  function fly(k, e, x, y, vx, vy) {
    const I = ITEM[k], cap = 2600, sp = Math.hypot(vx, vy); if (sp > cap) { vx *= cap / sp; vy *= cap / sp; }
    let last = performance.now(), ang = e._a ?? 90;
    (function step(t) {
      if (!e.isConnected) return;
      const dt = Math.min(.033, (t - last) / 1000); last = t;
      vy += I.g * dt; x += vx * dt; y += vy * dt;
      ang = I.aim === 'spin' ? ang + 900 * dt * Math.sign(vx || 1) : Math.atan2(vy, vx) * 180 / Math.PI;
      put(e, x, y, ang); gaze = {x, y};
      if (k === 'cup' && !RM.matches && Math.random() < .25) drip(x, y - 8);
      const [tx, ty] = tipOf(k, x, y, ang), hit = targetAt(k, tx, ty);
      if (hit) { gaze = null; return impact(k, e, hit, tx, ty, ang); }
      if (ty >= scene.surface()) { gaze = null; return impact(k, e, 'ground', tx, scene.surface(), ang); }
      if (x < -150 || x > innerWidth + 150 || y > innerHeight + 200 || y < -1500) { gaze = null; return e.remove(); }
      requestAnimationFrame(step);
    })(last);
  }
  function scatter(e, x, y, vx, vy) {             // Demeter's handful splits into seeds
    e.remove();
    for (let i = 0; i < 5; i++) {
      const s = document.createElement('div'); s.className = 'seed'; document.body.append(s);
      let sx = x + (Math.random() - .5) * 20, sy = y, svx = vx * .8 + (Math.random() - .5) * 320, svy = vy * .8 - 80 - Math.random() * 160, last = performance.now();
      (function step(t) { const dt = Math.min(.033, (t - last) / 1000); last = t; svy += 1300 * dt; sx += svx * dt; sy += svy * dt; s.style.left = sx + 'px'; s.style.top = sy + 'px';
        if (sy >= scene.surface() - 2) { s.remove(); if (sx > -10 && sx < innerWidth + 10) sprout(sx); return; } if (sy > innerHeight + 50) return s.remove(); requestAnimationFrame(step); })(last);
    }
  }
  function launch(k, e, x, y, vx, vy) {
    if (k === 'seeds') return scatter(e, x, y, vx, vy);
    if (k === 'sandal') return skim(e, x, y, vx);
    if (k === 'owl') return glide(e, x, y, x + vx * .35);
    fly(k, e, x, y, vx, vy);
  }
  // ---- what happens on contact
  function impact(k, e, t, x, y, ang) {
    const ground = t === 'ground', isSkel = !ground && t.classList.contains('skel');
    if (k === 'bolt') { if (ground) return groundStrike(e, x); if (isSkel) return burnSkel(t, e); return strikeTree(t, e, true); }
    if (k === 'snake') { if (ground) return slither(e, x); fade(e, 200); return petrify(t); }
    if (k === 'trident') { stick(e, t, x, y, ang, true); return tsunami(x, e); }
    if (k === 'bident') { if (isSkel) { fade(e, 250); return crumble(t, t.classList.contains('statue') ? 'stone' : 'bone'); } stick(e, 'ground', x, y, ang, true); summon(x); return setTimeout(() => fade(e, 400), 700); }
    if (k === 'bow') return stick(e, t, x, y, ang);
    if (k === 'hammer') { if (isSkel) { fade(e, 200); return crumble(t, t.classList.contains('statue') ? 'stone' : 'bone'); } return mine(e, x); }
    if (k === 'cup') { clink(); if (isSkel) return dance(t, e); if (!ground) return grow(t, e); return spill(e, x); }
  }
  // stick an item by its tip: arrows stay (they sway with a tree, fall with a skeleton); spears stay a moment
  function stick(e, t, x, y, ang, brief) {
    const I = ITEM[e.className.split(' ')[1]], r = ang * Math.PI / 180, emb = brief ? .25 : .18;
    const cx = x - Math.cos(r) * I.lead * (1 - emb * 2), cy = y - Math.sin(r) * I.lead * (1 - emb * 2);
    const host = t === 'ground' ? $('#stuck') : t.classList.contains('tree') ? $('.sway', t) : t, hr = host.getBoundingClientRect();
    e.className = e.className.replace('thrown', 'arrowstuck'); e.style.rotate = (I.aim === 'spin' || I.aim === null ? 0 : ang + I.aim) + 'deg';
    e.style.left = (cx - hr.left - I.w / 2) + 'px'; e.style.top = (cy - hr.top - I.h / 2) + 'px'; host.append(e);
    if (!brief) { thunk(); if (!RM.matches) e.animate([{rotate: (ang + I.aim - 4) + 'deg'}, {rotate: (ang + I.aim + 3) + 'deg'}, {rotate: (ang + I.aim - 1) + 'deg'}, {rotate: (ang + I.aim) + 'deg'}], {duration: 320}); }
    if (!brief) { const all = $$('.arrowstuck', SCN).filter(a => a.querySelector('svg[viewBox="0 0 64 12"]')); if (all.length > 40) all[0].remove(); }
    return e;
  }
  function slither(e, x) {                         // a snake that lands on bare ground slips away
    const dir = Math.random() < .5 ? -1 : 1; e.style.rotate = (dir > 0 ? 0 : 180) + 'deg'; e.style.top = (scene.surface() - ITEM.snake.h / 2 - 4) + 'px';
    e.animate([{translate: '0 0', opacity: 1}, {translate: `${dir * 90}px 0`, opacity: 0}], {duration: RM.matches ? 1 : 1100, easing: 'ease-in', fill: 'forwards'}).finished.then(() => e.remove());
  }
  // ---- Medusa: stone and back (trees and skeletons)
  function petrify(t) {
    const back = t.classList.contains('statue'), r = t.getBoundingClientRect();
    play(back ? 'thaw' : 'freeze');
    if (!RM.matches) for (let i = 0; i < 16; i++) { const px = r.left + Math.random() * r.width, py = r.top + Math.random() * r.height * .8, sz = 4 + Math.random() * 5;
      const p = particle(px, py, sz, sz, back ? `background:${['#FF7A2F', '#FFE27A', '#7BD88F'][i % 3]};border-radius:50%` : `background:${['#8FA39A', '#5E9C78', '#7E9486'][i % 3]};clip-path:${ROCK[i % 3]}`);
      p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${(Math.random() - .5) * 40}px,${back ? -50 : 40}px)`, opacity: 0}], {duration: 900, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove(); }
    setTimeout(() => t.classList.toggle('statue', !back), RM.matches ? 0 : 350);
    tipOnce('snake', back ? 'Back to life.' : 'Turned to stone. Throw another snake at it to bring it back.');
  }
  // ---- Hades: skeletons climb out of the ground and rattle their bones
  const SKEL = `<svg viewBox="0 0 46 82" aria-hidden="true"><g class="body">
    <path class="b" d="M23 22 L23 50" stroke-width="3.2"/><path class="b" d="M15 28 Q23 24 31 28 M14 34 Q23 30 32 34 M15 40 Q23 36 31 40" stroke-width="2.2"/>
    <g class="arm l"><path class="b" d="M17 24 L10 36 L8 47" stroke-width="2.6"/><circle class="bf" cx="8" cy="48.5" r="2"/></g>
    <g class="arm r"><path class="b" d="M29 24 L36 36 L38 47" stroke-width="2.6"/><circle class="bf" cx="38" cy="48.5" r="2"/></g>
    <path class="b" d="M15 50 Q23 56 31 50" stroke-width="3.2"/><path class="b" d="M18 53 L16 66 L15 80 M28 53 L30 66 L31 80" stroke-width="2.6"/></g>
    <g class="head"><circle class="bf" cx="23" cy="11" r="9"/><circle cx="19.5" cy="10" r="2.6" fill="#1C2127"/><circle cx="26.5" cy="10" r="2.6" fill="#1C2127"/><path d="M22.4 14 l.6 1.8 .6-1.8" stroke="#1C2127" stroke-width=".9" fill="none"/></g>
    <g class="jaw"><path class="bf" d="M16.5 17 Q23 22.5 29.5 17 L28 19.5 Q23 22 18 19.5 Z"/><path d="M20 18.6 v1.6 M23 19.2 v1.6 M26 18.6 v1.6" stroke="#1C2127" stroke-width=".7"/></g></svg>`;
  function summon(x) {
    const old = $$('.skel:not(.dying)'); if (old.length >= 12) crumble(old[0], 'bone');
    const s = document.createElement('div'); s.className = 'skel'; s.style.left = x + 'px'; s.style.setProperty('--d', (Math.random() * 2.6).toFixed(2) + 's');
    s.innerHTML = `<div class="rise">${SKEL}</div>`; $('#skels').append(s);
    const gy = scene.surface();
    if (!RM.matches) for (let i = 0; i < 14; i++) { const a = -Math.PI * (.1 + Math.random() * .8), d = 20 + Math.random() * 50, sz = 3 + Math.random() * 4;
      const p = particle(x + (Math.random() - .5) * 30, gy, sz, sz, `background:${['#4a3526', '#3d2c20', '#2f5a3c'][i % 3]};clip-path:${ROCK[i % 3]}`);
      p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d + 30}px)`, opacity: 0}], {duration: 800, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove(); }
    const sv = $('svg', s);
    (RM.matches ? Promise.resolve() : sv.animate([{transform: 'translateY(100%)'}, {transform: 'translateY(-4%)', offset: .8}, {transform: 'translateY(0)'}], {duration: 1000, easing: 'ease-out'}).finished).then(() => s.classList.add('up'));
    clatter(); dirt(); tipOnce('bident', 'A skeleton rose. Hit it with the bident or the hammer to crumble it, or the bolt to burn it.');
  }
  // crumble: bone (white pieces), char (black pieces) or stone (rock pieces); leaves a little pile behind
  function crumble(s, kind) {
    s.classList.add('dying');
    const r = s.getBoundingClientRect(), gy = scene.surface(), x = r.left + r.width / 2;
    const col = kind === 'char' ? ['#141414', '#2a2a2a', '#3b3f44'] : kind === 'stone' ? ['#8FA39A', '#5E9C78', '#7E9486'] : ['#E8E4D8', '#d6d0c0', '#f2efe6'];
    if (!RM.matches) for (let i = 0; i < 18; i++) { const px = r.left + Math.random() * r.width, py = r.top + Math.random() * r.height, w = 3 + Math.random() * 7, h = 2 + Math.random() * 3;
      const p = particle(px, py, w, h, `background:${col[i % 3]};border-radius:${kind === 'stone' ? 0 : 2}px;${kind === 'stone' ? 'clip-path:' + ROCK[i % 3] : ''}`);
      p.animate([{transform: 'translate(0,0) rotate(0)', opacity: 1}, {transform: `translate(${(Math.random() - .5) * 50}px,${gy - py - 2}px) rotate(${(Math.random() - .5) * 400}deg)`, opacity: 1, offset: .75}, {transform: `translate(${(Math.random() - .5) * 60}px,${gy - py - 2}px) rotate(${(Math.random() - .5) * 400}deg)`, opacity: 0}], {duration: 1100 + Math.random() * 300, easing: 'ease-in', fill: 'forwards'}).onfinish = () => p.remove(); }
    bonesFall(); if (kind === 'stone') play('freeze');
    s.animate([{opacity: 1}, {opacity: 0}], {duration: RM.matches ? 1 : 260, fill: 'forwards'}).finished.then(() => s.remove());
    scene.addMess(kind === 'char' ? 'ash' : kind === 'stone' ? 'rocks' : 'bones', x);
  }
  async function burnSkel(s, e) {
    s.classList.add('dying', 'burning'); const r = s.getBoundingClientRect(), x = r.left + r.width / 2;
    e.remove(); play('bolt'); setTimeout(() => play('burn'), 250);
    if (!RM.matches) { boltFx(x, r.top + r.height * .3);
      const end = performance.now() + 1300;
      (function flames() { for (let i = 0; i < 3; i++) { const px = r.left + Math.random() * r.width, py = r.top + Math.random() * r.height * .8, sz = 5 + Math.random() * 6;
        const p = particle(px, py, sz, sz, `background:${['#FFB347', '#FF7A2F', '#FFE27A'][i]};border-radius:50% 50% 50% 0;transform:rotate(-45deg)`);
        p.animate([{transform: 'translate(0,0) scale(1)', opacity: 1}, {transform: `translate(${(Math.random() - .5) * 24}px,${-30 - Math.random() * 40}px) scale(.3)`, opacity: 0}], {duration: 700, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove(); }
        if (performance.now() < end) requestAnimationFrame(flames); })(); }
    await wait(RM.matches ? 0 : 500); s.classList.add('charred');
    await wait(RM.matches ? 0 : 1100); crumble(s, 'char');
  }
  // ---- Demeter: flowers for the season
  const pick = a => a[Math.random() * a.length | 0];
  const FLOWER = {
    spring: () => { const c = pick(['#A9C8F5', '#F4B6C9', '#BFD7FA', '#F7C6D6']); return `<svg viewBox="0 0 24 40"><path d="M12 40 Q11 30 12 18" stroke="#4f8a42" stroke-width="2" fill="none"/><path d="M12 32 Q5 29 4 24 Q10 25 12 30" fill="#5d9a4c"/>${[0, 72, 144, 216, 288].map(a => `<ellipse cx="12" cy="9" rx="3.4" ry="5" fill="${c}" transform="rotate(${a} 12 14)"/>`).join('')}<circle cx="12" cy="14" r="2.8" fill="#FFE27A"/></svg>`; },
    summer: () => `<svg viewBox="0 0 24 40"><path d="M12 40 Q13 30 12 18" stroke="#4f8a42" stroke-width="1.8" fill="none"/><path d="M12 40 L5 35 L8 34 L3 30 L10 33 Z M12 40 L19 36 L16 35 L21 31 L14 34 Z" fill="#5d9a4c"/>${Array.from({length: 16}, (_, i) => `<path d="M12 13 L12 6" stroke="#F2C94C" stroke-width="1.6" stroke-linecap="round" transform="rotate(${i * 22.5} 12 13)"/>`).join('')}<circle cx="12" cy="13" r="3" fill="#E0A92A"/></svg>`,
    fall: () => { const cap = pick(['#B8452F', '#8B5A3C', '#A8382A']); return `<svg viewBox="0 0 24 40"><path d="M9 40 L9.6 28 Q12 26 14.4 28 L15 40 Z" fill="#EDE3CF"/><path d="M1 29 Q12 12 23 29 Q12 31 1 29 Z" fill="${cap}"/>${cap !== '#8B5A3C' ? '<circle cx="8" cy="23" r="1.6" fill="#F4EFE6"/><circle cx="14" cy="20" r="1.8" fill="#F4EFE6"/><circle cx="18" cy="25" r="1.3" fill="#F4EFE6"/>' : ''}</svg>`; },
    winter: () => `<svg viewBox="0 0 24 40"><path d="M12 40 L12 26" stroke="#3f6b36" stroke-width="2"/><ellipse cx="6" cy="30" rx="5" ry="2.4" fill="#3f6b36" transform="rotate(-20 6 30)"/><ellipse cx="18" cy="30" rx="5" ry="2.4" fill="#3f6b36" transform="rotate(20 18 30)"/>${[0, 60, 120, 180, 240, 300].map(a => `<path d="M12 18 Q9 12 12 5 Q15 12 12 18 Z" fill="#C0392B" transform="rotate(${a} 12 18)"/>`).join('')}<circle cx="11" cy="17.5" r="1.1" fill="#F2C94C"/><circle cx="13" cy="18.5" r="1.1" fill="#F2C94C"/><circle cx="12.5" cy="16.5" r="1" fill="#7BD88F"/></svg>`,
  };
  function sprout(x) {
    const all = $$('.flower', SCN); if (all.length > 90) all[0].remove();
    const f = document.createElement('div'); f.className = 'flower'; f.style.left = x + 'px'; f.style.setProperty('--s', (.85 + Math.random() * .45).toFixed(2));
    f.innerHTML = FLOWER[scene.season](); $('#flora').append(f); pop();
    if (!RM.matches) f.animate([{transform: 'translateX(-50%) scaleY(0)'}, {transform: 'translateX(-50%) scaleY(1.12)', offset: .7}, {transform: 'translateX(-50%) scaleY(1)'}], {duration: 520, easing: 'ease-out'});
    tipOnce('seeds', {spring: 'Spring flowers.', summer: 'Dandelions for summer.', fall: 'Mushrooms for the fall.', winter: 'Poinsettias for winter.'}[scene.season]);
  }
  // ---- Hephaestus: the hammer swings down and digs; each blow on the same spot digs deeper
  async function mine(e, x) {
    const gy = scene.surface(); e.style.top = (gy - ITEM.hammer.h + 6) + 'px'; e.style.left = (x - ITEM.hammer.w / 2 - 10) + 'px';
    if (!RM.matches) await e.animate([{rotate: '-80deg'}, {rotate: '20deg'}], {duration: 160, easing: 'ease-in', fill: 'forwards'}).finished;
    play('hammer'); setTimeout(dirt, 120);
    const G = $('#scene .ground'), g = scene.gh(); let h = $$('.hole', G).find(o => Math.abs(parseFloat(o.style.left) - x) < 32);
    if (!h) { h = document.createElement('div'); h.className = 'hole'; h.style.left = x + 'px'; h.style.width = '36px'; h.style.height = '0px'; h.dataset.d = 0; G.append(h); }
    const d = Math.min(g - 10, +h.dataset.d + 16); h.dataset.d = d; requestAnimationFrame(() => { h.style.height = d + 'px'; h.style.width = (38 + d * .7) + 'px'; });
    const deep = d > g * .55;
    if (!RM.matches) for (let i = 0; i < 18; i++) { const a = -Math.PI * (.1 + Math.random() * .8), dd = 30 + Math.random() * 70, sz = 3 + Math.random() * 5, spark = i % 6 === 0;
      const p = particle(x + (Math.random() - .5) * 20, gy + 4, sz, sz, spark ? 'background:#FFB347;border-radius:50%' : `background:${(deep ? ['#363c43', '#4a3526', '#6d7680'] : ['#4a3526', '#3d2c20', '#2f5a3c'])[i % 3]};clip-path:${ROCK[i % 3]}`);
      p.animate([{transform: 'translate(0,0)', opacity: 1}, {transform: `translate(${Math.cos(a) * dd}px,${Math.sin(a) * dd + 40}px)`, opacity: 0}], {duration: 700 + Math.random() * 300, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove(); }
    if (d >= g - 10 || Math.random() < .35) scene.addMess('rocks', x + (Math.random() < .5 ? -1 : 1) * (30 + d * .4));
    setTimeout(() => fade(e, 300), 250);
    tipOnce('hammer', d >= g - 10 ? 'You reached bedrock.' : 'Hit the same spot again to dig deeper.');
  }
  // ---- Poseidon: an opaque wave sweeps the whole screen and the playground comes back fresh
  async function tsunami(x, e) {
    surge(); const dir = x < innerWidth / 2 ? 1 : -1, W = Math.round(innerWidth * 1.35);
    const wv = document.createElement('div'); wv.className = 'tsunami'; wv.style.width = W + 'px'; wv.style.left = (dir > 0 ? -W : innerWidth) + 'px';
    const crest = `<svg viewBox="0 0 70 800" preserveAspectRatio="none" style="${dir > 0 ? 'right:-60px' : 'left:-60px;transform:scaleX(-1)'}"><path d="M0 0 L20 0 Q60 30 34 70 Q66 110 38 160 Q70 210 36 260 Q68 310 40 360 Q70 410 36 460 Q66 510 40 560 Q70 610 36 660 Q64 710 40 760 L44 800 L0 800 Z" fill="#a9dcff"/><path d="M20 0 Q60 30 34 70 Q66 110 38 160 Q70 210 36 260 Q68 310 40 360 Q70 410 36 460 Q66 510 40 560 Q70 610 36 660 Q64 710 40 760 L44 800" stroke="#ffffff" stroke-width="10" fill="none" stroke-linecap="round" opacity=".9"/></svg>`;
    wv.innerHTML = crest; document.body.append(wv);
    if (RM.matches) { wv.style.left = '0'; wv.style.width = '100vw'; wv.animate([{opacity: 0}, {opacity: 1}], {duration: 200, fill: 'forwards'}); await wait(220); scene.reset(); e?.remove(); await wait(200); await wv.animate([{opacity: 1}, {opacity: 0}], {duration: 250, fill: 'forwards'}).finished; wv.remove(); return; }
    await wv.animate([{transform: 'translateX(0)'}, {transform: `translateX(${dir * W}px)`}], {duration: 800, easing: 'cubic-bezier(.3,.05,.4,1)', fill: 'forwards'}).finished;
    e?.remove(); scene.reset(); await wait(250);
    await wv.animate([{transform: `translateX(${dir * W}px)`}, {transform: `translateX(${dir * (W + innerWidth + 80)}px)`}], {duration: 750, easing: 'ease-in', fill: 'forwards'}).finished;
    wv.remove(); tipOnce('trident', "Poseidon's tsunami washed the playground clean.");
  }

  // ---- Hermes: the winged sandal skims along the ground; its wind carries debris and arrows off, bends flowers, rocks trees and skeletons
  function skim(e, x, y, vx) {
    const dir = Math.sign(vx) || (x < innerWidth / 2 ? 1 : -1), sp = Math.min(1500, Math.max(650, Math.abs(vx) || 900)), done = new Set();
    e.style.scale = dir < 0 ? '-1 1' : ''; whoosh();
    let last = performance.now(), carried = 0;
    (function step(t) {
      if (!e.isConnected) return;
      const dt = Math.min(.033, (t - last) / 1000); last = t;
      y += (scene.surface() - 26 - y) * Math.min(1, dt * 5); x += dir * sp * dt;    // glides down to just above the grass
      put(e, x, y, 90); gaze = {x, y};
      carried += gust(x, dir, done);
      if (!RM.matches && Math.random() < .45) streak(x - dir * 24, y - 12 + Math.random() * 30, dir);
      if (x < -90 || x > innerWidth + 90) { gaze = null; e.remove(); return tipOnce('sandal', carried ? `Hermes carried ${carried} piece${carried === 1 ? '' : 's'} of mess away.` : "Hermes' wind: throw the sandal along the ground to carry the mess away."); }
      requestAnimationFrame(step);
    })(last);
  }
  function gust(x, dir, done) {
    const near = el => { if (done.has(el)) return false; const r = el.getBoundingClientRect(); return Math.abs(r.left + r.width / 2 - x) < 34; };
    const swing = (el, deg, ms) => { if (!RM.matches) el.animate([{rotate: '0deg'}, {rotate: dir * deg + 'deg'}, {rotate: -dir * deg * .35 + 'deg'}, {rotate: '0deg'}], {duration: ms, easing: 'ease-out'}); };
    let n = 0;
    $$('.mess', SCN).filter(near).forEach(m => { done.add(m); blowAway(m, dir); n++; });
    $$('#stuck .arrowstuck').filter(near).forEach(a => { done.add(a); blowAway(a, dir); n++; });
    $$('.flower', SCN).filter(near).forEach(f => { done.add(f); swing(f, 30, 900); });
    $$('.tree', SCN).filter(near).forEach(tr => { done.add(tr); if (!tr.classList.contains('statue')) swing(tr, 6, 1400); });
    $$('.skel.up:not(.dying):not(.statue)').filter(near).forEach(s => { done.add(s); s.style.transformOrigin = '50% 100%'; swing(s, 16, 900); });
    return n;
  }
  function blowAway(el, dir) {
    const r = Math.random();
    el.animate([{translate: '0 0', rotate: '0deg', opacity: 1}, {translate: `${dir * (200 + r * 180)}px ${-40 - r * 60}px`, rotate: `${dir * (180 + r * 360)}deg`, opacity: 0}],
      {duration: RM.matches ? 1 : 900, easing: 'ease-out', fill: 'forwards'}).finished.then(() => el.remove());
  }
  function streak(x, y, dir) {
    const p = particle(x, y, 22 + Math.random() * 20, 2, 'background:#E6ECF1;border-radius:2px;opacity:.6');
    p.animate([{translate: '0 0', opacity: .6}, {translate: `${-dir * 70}px 0`, opacity: 0}], {duration: 420, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove();
  }
  // ---- Athena: an owl glides to a perch (a tree's crown, a skeleton's skull, or the ground) and keeps watch; her eyes follow you
  const OWL = `<svg viewBox="0 0 40 46" aria-hidden="true"><g class="wing l"><path d="M9 22 Q-5 25 2 40 Q8 35 12 31 Z" fill="#6f6247"/></g><g class="wing r"><path d="M31 22 Q45 25 38 40 Q32 35 28 31 Z" fill="#6f6247"/></g>
    <path d="M8 17 L9 3 L16 11 Z M32 17 L31 3 L24 11 Z" fill="#8a7a5a"/><ellipse cx="20" cy="28" rx="13" ry="16" fill="#8a7a5a"/><ellipse cx="20" cy="33" rx="8" ry="10" fill="#d9c9a3"/>
    <path d="M15 30 l2.5 2.5 2.5-2.5 2.5 2.5 2.5-2.5 M15 36 l2.5 2.5 2.5-2.5 2.5 2.5 2.5-2.5" stroke="#a8946a" stroke-width="1" fill="none"/>
    <circle cx="13.5" cy="18" r="6" fill="#efe3c4"/><circle cx="26.5" cy="18" r="6" fill="#efe3c4"/>
    <circle cx="13.5" cy="18" r="3.7" fill="#E7C35A"/><circle cx="26.5" cy="18" r="3.7" fill="#E7C35A"/>
    <circle class="pupil" cx="13.5" cy="18" r="1.9" fill="#1C2127"/><circle class="pupil" cx="26.5" cy="18" r="1.9" fill="#1C2127"/>
    <g class="lids"><ellipse cx="13.5" cy="18" rx="4.4" ry="4.4" fill="#8a7a5a"/><ellipse cx="26.5" cy="18" rx="4.4" ry="4.4" fill="#8a7a5a"/></g>
    <path d="M20 21 L18 24 L20 27 L22 24 Z" fill="#C9A36A"/><path d="M14 43 l-1 3 M18 43 v3 M22 43 v3 M26 43 l1 3" stroke="#C9A36A" stroke-width="1.5" stroke-linecap="round"/></svg>`;
  // Delphic maxims, carved at Apollo's temple: what a wise owl would say
  const WISDOM = ['Know thyself.', 'Nothing in excess.', 'Measure is best.', 'Know the right moment.', 'Practice makes perfect.', 'Think before you act.', 'Be a seeker of wisdom.', 'Finish the race without flinching.'];
  const owls = [];
  function perchFor(x) {
    const free = el => !owls.some(o => o.host === el);
    const trees = $$('.tree:not(.struck):not(.statue)', SCN).filter(free).map(t => [t, Math.abs(t.getBoundingClientRect().left + t.getBoundingClientRect().width / 2 - x)]).filter(([, d]) => d < 170).sort((a, b) => a[1] - b[1]);
    if (trees.length) return trees[0][0];
    const sk = $$('.skel.up:not(.dying):not(.statue)').filter(free).find(s => Math.abs(s.getBoundingClientRect().left + 23 - x) < 70);
    return sk || null;
  }
  // where an owl sits in its host's own box (trees are 120×162 in their SVG; the crown's top is near y 20, a bare winter tree's top branch near y 52)
  function seatIn(host, x) {
    const r = host.getBoundingClientRect();
    if (!host) return null;
    if (host.classList.contains('tree')) return [r.width / 2 - 20, r.height * (scene.season === 'winter' ? 52 : 22) / 162 - 42];
    return [3, -40];                               // a skeleton: on top of the skull
  }
  function glide(e, x, y, aimX) {
    aimX = Math.max(30, Math.min(innerWidth - 30, aimX));
    if (owls.length >= 4) flee(owls[0]);
    const host = perchFor(aimX), wing = !RM.matches;
    let tx, ty, local;
    if (host) { const hr = host.getBoundingClientRect(); local = seatIn(host); tx = hr.left + local[0] + 20; ty = hr.top + local[1] + 23; }
    else { tx = aimX; ty = scene.surface() - 23 - 6; }
    e.classList.add('flying');
    const dur = RM.matches ? 1 : Math.min(1300, 500 + Math.hypot(tx - x, ty - y) * .9), x0 = x, y0 = y, t0 = performance.now(), lift = Math.min(120, Math.abs(tx - x0) * .25);
    (function step(t) {
      if (!e.isConnected) return;
      const k = Math.min(1, (t - t0) / dur), ease = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const cx = x0 + (tx - x0) * ease, cy = y0 + (ty - y0) * ease - Math.sin(Math.PI * k) * lift;
      put(e, cx, cy, 90); e.style.scale = tx < x0 ? '-1 1' : ''; gaze = {x: cx, y: cy};
      if (k < 1) return requestAnimationFrame(step);
      gaze = null; e.classList.remove('flying'); e.style.scale = '';
      const into = host || $('#stuck'), hr = into.getBoundingClientRect();
      e.className = 'owl'; e.style.rotate = ''; e.style.position = 'absolute';
      if (host) { e.style.left = local[0] + 'px'; e.style.top = local[1] + 'px'; (host.classList.contains('tree') ? $('.sway', host) : host).append(e); }
      else { e.style.left = (tx - hr.left - 20) + 'px'; e.style.top = (-46 + 4) + 'px'; into.append(e); }
      if (!RM.matches) e.animate([{translate: '0 -4px'}, {translate: '0 1px'}, {translate: '0 0'}], {duration: 260, easing: 'ease-out'});
      owls.push({e, host}); watch(); hoot();
      tipOnce('owl', host ? (host.classList.contains('tree') ? "Athena's owl keeps watch from the tree. Click her for a word of wisdom." : 'An owl on a skull. Click her for a word of wisdom.') : "Athena's owl landed on the ground. Click her for a word of wisdom.");
    })(t0);
    if (wing) e.classList.add('flap');
  }
  // an owl leaves when her perch burns, crumbles or the playground is washed: up and away, off the screen
  function flee(o) {
    const i = owls.indexOf(o); if (i >= 0) owls.splice(i, 1);
    const e = o.e; if (!e.isConnected) return;
    const r = e.getBoundingClientRect(); e.remove(); const f = make('owl', r.left + 20, r.top + 23); f.classList.add('flying', 'flap');
    const dir = r.left < innerWidth / 2 ? -1 : 1;
    f.animate([{translate: '0 0', opacity: 1}, {translate: `${dir * 420}px -520px`, opacity: .9}], {duration: RM.matches ? 1 : 1500, easing: 'ease-in', fill: 'forwards'}).finished.then(() => f.remove());
  }
  // one loop for every owl: pupils follow the pointer (or whatever is in flight), blink now and then, flee a ruined perch
  let ptr = null, watching = false;
  addEventListener('pointermove', ev => { ptr = [ev.clientX, ev.clientY]; }, {passive: true});
  function watch() {
    if (watching) return; watching = true;
    (function tick(t) {
      for (const o of [...owls]) {
        if (!o.e.isConnected) { owls.splice(owls.indexOf(o), 1); continue; }
        const h = o.host;
        if (h && (h.classList.contains('struck') || h.classList.contains('dying') || !h.isConnected)) { flee(o); continue; }
        if (h && h.classList.contains('statue')) continue;            // a stone owl on a stone perch: her eyes stop too
        const to = gaze ? [gaze.x, gaze.y] : ptr; if (!to) continue;
        const r = o.e.getBoundingClientRect(), dx = to[0] - (r.left + 20), dy = to[1] - (r.top + 18), d = Math.hypot(dx, dy) || 1, m = Math.min(1.7, d / 60);
        $$('.pupil', o.e).forEach((p, i) => { p.setAttribute('cx', (i ? 26.5 : 13.5) + dx / d * m); p.setAttribute('cy', 18 + dy / d * m); });
        if (!RM.matches && Math.random() < .004) { o.e.classList.add('blink'); setTimeout(() => o.e.classList.remove('blink'), 140); }
      }
      if (owls.length) requestAnimationFrame(tick); else watching = false;
    })(performance.now());
  }
  // click (or tap) an owl: she hoots and says one maxim. The scene is behind the page, so this finds her by her box.
  document.addEventListener('pointerdown', ev => {
    if (!onOlympus || armedK || held || ev.target.closest('.dock,.lab,.realms,header,.toast,dialog,button,a')) return;
    const o = owls.find(o => scene.inside(o.e, ev.clientX, ev.clientY, 6)); if (!o) return;
    hoot(); if (!RM.matches) o.e.animate([{rotate: '0deg'}, {rotate: '-14deg'}, {rotate: '8deg'}, {rotate: '0deg'}], {duration: 600, easing: 'ease-out'});
    $$('.owlsay').forEach(b => b.remove());
    const r = o.e.getBoundingClientRect(), b = document.createElement('div'); b.className = 'owlsay'; b.setAttribute('role', 'status'); b.textContent = pick(WISDOM);
    b.style.left = Math.max(8, Math.min(innerWidth - 200, r.left + 20 - 90)) + 'px'; b.style.top = Math.max(8, r.top - 54) + 'px'; document.body.append(b);
    setTimeout(() => fade(b, 400), 2800);
  });
  // ---- Dionysus: the cup's wine makes skeletons dance, grows a grapevine up a tree, or leaves a puddle on the ground
  function drip(x, y) {
    const p = particle(x + (Math.random() - .5) * 10, y, 4, 5, 'background:#7a2048;border-radius:50% 50% 50% 50%/60% 60% 40% 40%');
    p.animate([{translate: '0 0', opacity: .9}, {translate: `0 ${30 + Math.random() * 30}px`, opacity: 0}], {duration: 500, easing: 'ease-in', fill: 'forwards'}).onfinish = () => p.remove();
  }
  function droplets(x, y, n = 14) {
    if (RM.matches) return;
    for (let i = 0; i < n; i++) { const a = -Math.PI * (.1 + Math.random() * .8), d = 20 + Math.random() * 45, sz = 3 + Math.random() * 3;
      const p = particle(x, y, sz, sz, `background:${['#7a2048', '#9b2f62', '#5a1838'][i % 3]};border-radius:50%`);
      p.animate([{translate: '0 0', opacity: 1}, {translate: `${Math.cos(a) * d}px ${Math.sin(a) * d + 24}px`, opacity: 0}], {duration: 600, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove(); }
  }
  function dance(s, e) {
    const r = s.getBoundingClientRect(); fade(e, 200); splash(); droplets(r.left + r.width / 2, r.top + 14, 10);
    if (s.classList.contains('statue') || s.classList.contains('charred')) return tipOnce('cupstone', 'Stone can\'t dance. Bring it back with the snake first.');
    s.classList.add('dancing'); tune(); clearTimeout(s._dance); s._dance = setTimeout(() => s.classList.remove('dancing'), 8000);
    if (!RM.matches) { let n = 0; const iv = setInterval(() => { if (!s.isConnected || !s.classList.contains('dancing') || ++n > 14) return clearInterval(iv); note(s); }, 520); }
    tipOnce('cup', 'The skeleton dances. Splash another and they dance together.');
  }
  function note(s) {
    const r = s.getBoundingClientRect(), p = document.createElement('div'); p.className = 'note'; p.setAttribute('aria-hidden', 'true');
    p.textContent = pick(['♪', '♫', '♩']); p.style.left = (r.left + 10 + Math.random() * 26) + 'px'; p.style.top = (r.top - 4) + 'px'; $('#fx').append(p);
    p.animate([{translate: '0 0', opacity: 0}, {translate: `${(Math.random() - .5) * 20}px -16px`, opacity: 1, offset: .3}, {translate: `${(Math.random() - .5) * 40}px -60px`, opacity: 0}], {duration: 1600, easing: 'ease-out', fill: 'forwards'}).onfinish = () => p.remove();
  }
  // a grapevine curls up the trunk and grape clusters hang from the branches (green in spring, purple in summer and fall, a few dry ones in winter)
  function grow(t, e) {
    fade(e, 200); splash(); const tr = t.getBoundingClientRect(); droplets(tr.left + tr.width / 2, tr.bottom - tr.height * .4, 8);
    const svg = $('.sway svg', t); if (!svg || $('.vine', svg)) return tipOnce('vine2', 'This tree already has a vine.');
    const col = {spring: ['#a7c46a', '#bcd67f'], summer: ['#5b2a6e', '#7a3a8a'], fall: ['#4a1f5c', '#6b2f7d'], winter: ['#3d2440', '#523356']}[scene.season];
    const bunch = (x, y, n) => Array.from({length: n}, (_, i) => { const row = i < 3 ? 0 : i < 5 ? 1 : 2, k = i < 3 ? i : i < 5 ? i - 3 : 0;
      return `<circle cx="${x - (row === 0 ? 4 : row === 1 ? 2 : 0) + k * 4}" cy="${y + row * 3.6}" r="2.2" fill="${col[i % 2]}"/>`; }).join('');
    const leaf = (x, y, a) => scene.season === 'winter' ? '' : `<path d="M${x} ${y} q4 -5 8 0 q-4 4 -8 0 Z" fill="#5d9a4c" transform="rotate(${a} ${x} ${y})"/>`;
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.setAttribute('class', 'vine');
    g.innerHTML = `<path class="tendril" pathLength="1" d="M55 160 Q67 150 56 140 Q45 130 62 120 Q71 111 57 101 Q47 92 61 84 Q68 77 58 68" stroke="#4f7a32" stroke-width="2.2" fill="none" stroke-linecap="round"/>
      ${leaf(62, 150, -20)}${leaf(48, 132, 160)}${leaf(65, 116, -30)}${leaf(52, 96, 150)}${leaf(63, 80, -10)}
      <g class="grapes">${bunch(36, 88, scene.season === 'winter' ? 3 : 6)}${bunch(84, 80, scene.season === 'winter' ? 2 : 6)}${scene.season === 'winter' ? '' : bunch(48, 62, 6)}</g>`;
    svg.append(g);
    if (!RM.matches) { $('.tendril', g).animate([{strokeDashoffset: 1}, {strokeDashoffset: 0}], {duration: 1200, easing: 'ease-out', fill: 'backwards'}).ready.then(() => {});
      $('.grapes', g).animate([{opacity: 0, scale: .4}, {opacity: 1, scale: 1}], {duration: 500, delay: 1000, easing: 'ease-out', fill: 'backwards'}); }
    tipOnce('vine', {spring: 'A grapevine, green grapes still ripening.', summer: 'A grapevine heavy with grapes.', fall: 'Ripe grapes for the harvest.', winter: 'A winter vine, a few dry grapes left.'}[scene.season]);
  }
  function spill(e, x) {
    const gy = scene.surface(); e.style.top = (gy - ITEM.cup.h / 2 - 2) + 'px'; splash(); droplets(x, gy - 4);
    if (!RM.matches) e.animate([{rotate: '0deg'}, {rotate: (Math.random() < .5 ? -1 : 1) * 95 + 'deg'}], {duration: 300, easing: 'ease-in', fill: 'forwards'});
    scene.addMess('wine', x); setTimeout(() => fade(e, 500), 900);
    tipOnce('cupground', 'Spilled wine. Hermes\' sandal or Poseidon\'s trident will clean it up.');
  }
  // ---- dragging an item out of the dock
  let held = null, armedK = null;
  function velocity(tr) { const now = performance.now(), last = tr[tr.length - 1]; if (!last || now - last[0] > 80) return [0, 0];     // paused before letting go = a drop, not a throw
    const old = tr.find(q => now - q[0] < 120) || tr[0], dt = (now - old[0]) / 1000;
    return dt > .005 ? [(last[1] - old[1]) / dt, (last[2] - old[2]) / dt] : [0, 0]; }
  function seatCenter(seat) { const r = seat.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }
  function back(e, seat) { const [hx, hy] = seatCenter(seat); e.animate([{left: e.style.left, top: e.style.top, opacity: 1}, {left: (hx - e.offsetWidth / 2) + 'px', top: (hy - e.offsetHeight / 2) + 'px', opacity: 0}], {duration: RM.matches ? 1 : 220, easing: 'ease-in'}).finished.then(() => e.remove()); }
  function wire(seat) {
    const k = seat.dataset.item;
    seat.addEventListener('pointerdown', ev => { if (ev.button > 0) return; seat.setPointerCapture(ev.pointerId); held = {k, seat, id: ev.pointerId, x0: ev.clientX, y0: ev.clientY, moved: false, trail: [], ang: 90}; });
    seat.addEventListener('pointermove', ev => {
      if (!held || held.id !== ev.pointerId) return; const x = ev.clientX, y = ev.clientY;
      if (!held.moved && Math.hypot(x - held.x0, y - held.y0) < 6) return;
      if (!held.moved) { held.moved = true; disarm(); held.e = make(k, x, y); }
      held.trail.push([performance.now(), x, y]); if (held.trail.length > 8) held.trail.shift();
      const [vx, vy] = velocity(held.trail), sp = Math.hypot(vx, vy);
      if (k === 'bow') { const [sx, sy] = seatCenter(seat); held.ang = Math.atan2(y - sy, x - sx) * 180 / Math.PI; }            // the arrow points away from the bow
      else if (sp > 250) held.ang = Math.atan2(vy, vx) * 180 / Math.PI; else held.ang += (90 - held.ang) * .15;                 // otherwise it leans the way you move it
      put(held.e, x, y, ITEM[k].aim === 'spin' ? (held.ang - 90) * .4 : held.ang); gaze = {x, y};
    });
    const end = ev => {
      if (!held || held.id !== ev.pointerId) return; const h = held; held = null; gaze = null;
      if (!h.moved) return; justMoved = true; setTimeout(() => justMoved = false, 60);
      const x = ev.clientX, y = ev.clientY, [vx, vy] = velocity(h.trail), sp = Math.hypot(vx, vy);
      if (sp < 500 && onUI(x, y)) return back(h.e, seat);
      const [tx, ty] = tipOf(k, x, y, h.ang), t = sp < 500 ? targetAt(k, x, y) || targetAt(k, tx, ty) : null;     // a slow drop acts on what is under the pointer
      if (t) return impact(k, h.e, t, tx, ty, h.ang);
      launch(k, h.e, x, y, k === 'bow' && sp < 500 ? Math.cos(h.ang * Math.PI / 180) * 900 : vx, k === 'bow' && sp < 500 ? Math.sin(h.ang * Math.PI / 180) * 900 : vy);   // a slow release of an arrow still shoots it
      if (k === 'bow') twang();
    };
    seat.addEventListener('pointerup', end); seat.addEventListener('pointercancel', end);
    // click / Enter: pick the item up, then click the field where it should go (Enter again: the middle of the field)
    seat.addEventListener('click', () => { if (justMoved) return; if (armedK === k) { disarm(); return useAt(k, innerWidth / 2 + (Math.random() - .5) * 240, scene.surface() - 140); } arm(k, seat); });
    seat.addEventListener('focus', () => help(k)); seat.addEventListener('mouseenter', () => help(k)); seat.addEventListener('mouseleave', () => help(armedK, !!armedK));
  }
  let justMoved = false;
  function arm(k, seat) { disarm(); armedK = k; seat.setAttribute('aria-pressed', 'true'); help(k, true); if (innerWidth < 768) toast(`${ITEM[k].name}: tap the field where it should go. Tap it again for the middle.`); }
  function disarm() { if (!armedK) return; $$('.seat[aria-pressed=true]').forEach(s => s.setAttribute('aria-pressed', 'false')); armedK = null; help(null); }
  function useAt(k, x, y) {                       // drop it from just above the spot (bolts come down from the sky; arrows fly from the bow)
    const t = targetAt(k, x, y);
    if (k === 'bolt') { const e = make(k, x, -40); return t ? impact(k, e, t, x, y, 90) : fly(k, e, x, -40, 0, 2200); }
    if (k === 'bow') { const seat = $('.seat[data-item=bow]'), [sx, sy] = seatCenter(seat), dx = x - sx, dy = y - sy, d = Math.hypot(dx, dy) || 1, sp = 1700, T = d / sp, e = make(k, sx, sy); twang();
      return fly(k, e, sx, sy, dx / d * sp, dy / d * sp - ITEM.bow.g * T / 2); }
    if (k === 'sandal') { const from = x < innerWidth / 2 ? -40 : innerWidth + 40, e = make(k, from, scene.surface() - 60); return skim(e, from, scene.surface() - 60, x < innerWidth / 2 ? 1 : -1); }
    if (k === 'owl') { const e = make(k, x, Math.max(80, y - 160)); return glide(e, x, Math.max(80, y - 160), x); }
    const sy = Math.min(y, scene.surface() - 120), e = make(k, x, sy);
    if (t) return impact(k, e, t, x, y, 90);
    launch(k, e, x, sy, 0, 150);
  }
  document.addEventListener('click', ev => {
    if (!armedK || ev.target.closest('.dock,.lab,.realms,header,.toast,dialog')) return;
    ev.preventDefault(); const k = armedK; disarm(); useAt(k, ev.clientX, ev.clientY);
  }, true);
  addEventListener('keydown', ev => { if (ev.key === 'Escape' && armedK) { disarm(); toast('Cancelled.'); } });
  function help(k, armedNow) {
    const p = $('#dockHelp'); if (!p) return;
    if (!k) { p.innerHTML = 'Drag an item onto the field and let go, or fling it. Click one, then the field, to place it.'; return; }
    p.innerHTML = `<b>${esc(ITEM[k].name)}</b>: ${esc(ITEM[k].does)}.${armedNow ? ' Click the field where it should go, or press Enter again for the middle. Esc cancels.' : ''}`;
  }
  // ---- the dock: Ω of the twelve Olympians (Zeus in the middle), and Medusa and Hades beyond Olympus
  let shown = false;
  function show(force) {
    if (shown && !force) return; shown = true;            // refresh() re-renders other pages every 15 s; the playground keeps its state
    const phone = innerWidth < 768, R = phone ? 118 : 172, S = phone ? 40 : 54, Z = Math.round(S * (phone ? 1.15 : 1.2)), F = phone ? 14 : 24;
    const ow = 2 * R + S + 8, cx = ow / 2, cy = R + Z / 2 + 4, s35 = Math.sin(35 * Math.PI / 180);
    const oh = Math.round(cy + R * s35 + F * .5 + S / 2 + 6);
    const pos = i => { const th = angleOf(i) * Math.PI / 180; let x = cx + R * Math.cos(th), y = cy - R * Math.sin(th);
      if (i === 0) { x -= F; y += F * .5; } if (i === 11) { x += F; y += F * .5; } return [x, y]; };
    const [ax, ay] = pos(0), [bx, by] = pos(11), [a1x, a1y] = [cx + R * Math.cos(215 * Math.PI / 180), cy - R * Math.sin(215 * Math.PI / 180)], [b1x, b1y] = [cx + R * Math.cos(-35 * Math.PI / 180), cy - R * Math.sin(-35 * Math.PI / 180)];
    const seat = (key, label, item, [x, y], cls = '') => item
      ? `<button type="button" class="seat ${cls}" data-item="${item}" style="left:${x.toFixed(1)}px;top:${y.toFixed(1)}px;--glow:${RING[item][0]}" aria-pressed="false" aria-label="${esc(ITEM[item].name)}: ${esc(ITEM[item].does)}. Drag it out, or press Enter and then click the field.">${medal(item)}</button>`
      : `<span class="seat off" role="img" style="left:${x.toFixed(1)}px;top:${y.toFixed(1)}px" aria-label="${label}: power coming later" title="${label}: power coming later">${label[0]}</span>`;
    const host = $('#main');
    host.innerHTML = `<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs><radialGradient id="mhl" cx="50%" cy="38%" r="62%"><stop offset="0" stop-color="#fff" stop-opacity=".13"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs></svg>
      <div class="playwrap"><div class="labhost" id="labhost"></div>
      <div class="dock" role="group" aria-label="Powers of the gods">
        <div class="omega" style="--ow:${ow}px;--oh:${oh}px;--ss:${S}px;--zs:${Z}px">
          <svg class="oline" aria-hidden="true"><path d="M${ax} ${ay} L${a1x} ${a1y} A${R} ${R} 0 1 1 ${b1x} ${b1y} L${bx} ${by}" fill="none" stroke="#E7C35A" stroke-opacity=".28" stroke-width="2.5" stroke-linecap="round"/></svg>
          ${OMEGA.map(([k, n, it], i) => seat(k, n, it, pos(i), i === ZI ? 'zeus' : '')).join('')}
        </div>
        <div class="groups">${GROUPS.map(([g, list]) => `<div class="beyond" role="group" aria-label="${g}"><span class="dock-label">${g}</span>${list.map(([k, n, it]) => seat(k, n, it, [0, 0])).join('')}</div>`).join('')}</div>
        <p class="dock-help" id="dockHelp" aria-live="polite"></p>
      </div></div>`;
    $$('.beyond .seat').forEach(s => { s.style.left = ''; s.style.top = ''; s.style.width = S + 'px'; s.style.height = S + 'px'; });
    $$('.dock .seat[data-item]').forEach(wire);
    scene.lab($('#labhost')); help(null);
  }
  let wasPhone = innerWidth < 768;
  addEventListener('resize', () => { if (onOlympus && (innerWidth < 768) !== wasPhone) { wasPhone = innerWidth < 768; show(true); } });
  return {show};
})();
