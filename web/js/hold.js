// Hold to confirm (docs/fx.md), for anything that changes what runs: approve a deploy, roll back, release a delivery.
// Press and hold for 3 s: a ring fills and the label counts down ("Hold… 3"); letting go early sends nothing.
// Holding Space or Enter does the same. A click with no press behind it (a screen reader's or a switch's) can't be held,
// so it arms the button and a second click within 5 s confirms. Reduced motion: no ring (CSS), the countdown words only.
// Server plugins get it as api.holdConfirm. Returns {cancel}; the button keeps its own label and look between holds.
// Argus watches the button while it is held, then nods when onDone finishes, or winces if it returns false or throws.
function holdConfirm(btn, onDone, {ms = 3000} = {}) {
  const label = btn.textContent.trim(), secs = Math.ceil(ms / 1000);
  btn.classList.add('hold'); btn.type = 'button';
  btn.innerHTML = `<span class="hold-ring" aria-hidden="true"></span><span class="hold-label"></span>`;
  const text = $('.hold-label', btn), say = s => { text.textContent = s; };
  say(label); btn.setAttribute('aria-label', `${label} (hold ${secs} seconds to confirm)`);
  let t0 = 0, raf = 0, busy = false, armed = 0, pressed = false;
  const set = p => btn.style.setProperty('--p', p);
  function tick() {
    const p = Math.min(1, (performance.now() - t0) / ms); set(p);
    if (p >= 1) return finish();
    say(`Hold… ${Math.ceil((1 - p) * ms / 1000)}`); raf = requestAnimationFrame(tick);
  }
  function start() {
    if (busy || t0) return;
    clearTimeout(armed); armed = 0; t0 = performance.now(); btn.classList.add('holding');
    btn.style.minWidth = `${btn.offsetWidth}px`;   // the countdown is shorter than the label: the button must not shrink out from under the finger
    look.watch(btn); look.react('wide');   // Argus keeps his eyes on the button and opens them wide while you hold
    tick();
  }
  function stop(quiet) {                    // let go early: nothing is sent
    if (!t0) return;
    cancelAnimationFrame(raf); t0 = 0; set(0); btn.classList.remove('holding'); btn.style.minWidth = ''; say(label); look.watch(null); look.react('rest');
    if (!quiet) toast(`Let go early: nothing was sent. Hold ${label} for ${secs} seconds to confirm.`);
  }
  async function finish() {
    cancelAnimationFrame(raf); t0 = 0; clearTimeout(armed); armed = 0; busy = true;
    btn.classList.remove('holding'); btn.classList.add('done'); btn.setAttribute('aria-busy', 'true'); say('Working…');
    look.watch(null); look.react('rest');
    try { const r = await onDone(); look.react(r === false ? 'wince' : 'nod'); } catch (e) { look.react('wince'); throw e; } finally { busy = false; set(0); btn.classList.remove('done'); btn.removeAttribute('aria-busy'); btn.style.minWidth = ''; say(label); }
  }
  btn.addEventListener('pointerdown', e => { if (e.button) return; pressed = true; e.preventDefault(); btn.focus(); start(); });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) btn.addEventListener(ev, () => stop());
  btn.addEventListener('contextmenu', e => e.preventDefault());             // a long touch must not open the menu
  const key = e => e.key === ' ' || e.key === 'Enter';
  btn.addEventListener('keydown', e => { if (!key(e)) return; e.preventDefault(); if (!e.repeat) { pressed = true; start(); } });
  btn.addEventListener('keyup', e => { if (key(e)) { e.preventDefault(); pressed = false; stop(); } });     // no click follows a key
  btn.addEventListener('blur', () => stop(true));
  btn.addEventListener('click', e => {
    if (pressed || e.detail > 0) { pressed = false; return; }                // a real press was already handled as a hold
    if (busy) return;
    if (armed) return finish();
    say(`Click again to ${label.toLowerCase()}`); toast(`Click ${label} again within 5 seconds to confirm.`);
    armed = setTimeout(() => { armed = 0; say(label); }, 5000);
  });
  return {cancel: () => stop(true)};
}
