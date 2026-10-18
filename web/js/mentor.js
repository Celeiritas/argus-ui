// Argus UI - Mentor: the Practice page (spaced repetition, typed answers, calibration). See docs/mentor.md.
/* ---------- Mentor: the Practice tab ---------- */
const practice = (() => {
  const M = {deck: null, card: null, t0: 0, result: null, shown: false};
  try { M.deck = localStorage.getItem('mentor-deck') || null; } catch (e) {}
  const get = async p => (await fetch(url('api/mentor/' + p), {cache: 'no-store'})).json();
  const send = async (p, body) => (await fetch(url('api/mentor/' + p), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json();
  // shown best to worst; value = FSRS rating (4 Easy ... 1 Again)
  const RATES = [[4, 'Very well', 'Quick, easy recall'], [3, 'Well enough', 'Took moderate thought'], [2, 'Not well', 'Hard to remember or explain'], [1, 'Needs work', 'Run this card again soon']];
  const back = d => d < 1 / 24 ? `${Math.max(1, Math.round(d * 1440))} min` : d < 1 ? `${Math.round(d * 24)} hour${Math.round(d * 24) === 1 ? '' : 's'}` : `${Math.round(d)} day${Math.round(d) === 1 ? '' : 's'}`;
  const verb = v => v === 1 ? 'Run again in 10 min' : 'Save and next card';
  const CONF = [[1, 'Guessing'], [2, 'Unsure'], [3, 'Fairly sure'], [4, 'Certain']];
  function calText(c) { if (c == null) return 'not enough answers yet'; if (c > .15) return 'running overconfident'; if (c < -.15) return 'running underconfident'; return 'well calibrated'; }
  function when(ts) { if (!ts) return ''; const d = new Date(ts * 1000), m = (ts * 1000 - Date.now()) / 60000; return m < 60 ? `in ${Math.max(1, Math.round(m))} min` : m < 1440 ? `at ${d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}` : d.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'}); }
  async function show() {
    if (M.shown) return; M.shown = true;      // refresh() re-renders agent pages; Practice keeps its own state
    const [{decks}] = await Promise.all([get('decks')]);
    M.decks = decks;
    $('#main').innerHTML = `<section class="persona practice" aria-label="Practice">
      <div class="decks" role="group" aria-label="Deck">${[[null, 'All decks']].concat(decks.map(d => [d.id, d.name])).map(([id, n]) => `<button type="button" data-deck="${id || ''}" aria-pressed="${(M.deck || null) === id}">${esc(n)}</button>`).join('')}</div>
      <p class="mstats" id="mstats" aria-live="polite"></p><div id="mpanel"></div></section>`;
    $$('.decks button').forEach(b => b.onclick = () => { M.deck = b.dataset.deck || null; try { M.deck ? localStorage.setItem('mentor-deck', M.deck) : localStorage.removeItem('mentor-deck'); } catch (e) {} $$('.decks button').forEach(x => x.setAttribute('aria-pressed', x === b)); next(); });
    next();
  }
  async function stats() {
    const s = await get('stats' + (M.deck ? '?deck=' + encodeURIComponent(M.deck) : ''));
    $('#mstats').innerHTML = `<b>${s.due}</b> due · <b>${s.new}</b> new · <b>${s.today}</b> answered today · calibration: <b>${calText(s.calibration)}</b>${s.labels ? ` · ${s.labels} graded answer${s.labels === 1 ? '' : 's'} saved for the learning grader` : ''}`;
  }
  async function next(extra) {
    stats();
    const r = await get('next?' + (M.deck ? 'deck=' + encodeURIComponent(M.deck) + '&' : '') + (extra ? 'extra=1' : ''));
    M.card = r.card; M.result = null;
    if (!M.card) {
      $('#mpanel').innerHTML = `<div class="panel"><h3>All caught up</h3><p class="coach">Nothing is due in this deck${r.next_due ? `; the next card comes back ${when(r.next_due)}` : ''}. Spacing reviews out is what makes them stick, so stopping here is a good choice.</p>
        <button type="button" id="ahead">Practice ahead</button></div>`;
      $('#ahead').onclick = () => next(true); return;
    }
    const deckName = (M.decks.find(d => d.id === M.card.deck) || {}).name || M.card.deck;
    $('#mpanel').innerHTML = `<form class="panel" id="qform" novalidate>
      <p class="deckname">${esc(deckName)}${M.card.reps ? '' : ' · new card'}</p>
      <h3 id="qprompt">${esc(M.card.prompt)}</h3>
      <div class="field"><label for="ans">Your answer, in your own words</label>
        <textarea id="ans" aria-describedby="anshelp" autocomplete="off" spellcheck="true"></textarea>
        <p class="help" id="anshelp">Write it before peeking. Leave it blank if you don't know. <kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p></div>
      <fieldset><legend>How sure are you?</legend><div class="seg">${CONF.map(([v, n]) => `<label><input type="radio" name="conf" value="${v}">${n}</label>`).join('')}</div></fieldset>
      <div class="row"><button type="submit" class="primary" id="checkBtn">Check answer</button></div></form>`;
    M.t0 = performance.now();
    const ta = $('#ans'), btn = $('#checkBtn');
    const label = () => btn.textContent = ta.value.trim() ? 'Check answer' : 'Show answer';
    ta.oninput = label; label(); ta.focus();
    ta.onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('#qform').requestSubmit(); } };
    $('#qform').onsubmit = e => { e.preventDefault(); check(); };
  }
  async function check() {
    const text = $('#ans').value.trim(), conf = +($('input[name=conf]:checked')?.value || 0) || null;
    const btn = $('#checkBtn'); btn.disabled = true;
    let r; try { r = await send('answer', {card: M.card.id, text, confidence: conf, ms: Math.round(performance.now() - M.t0)}); } catch (e) { r = {ok: false}; }
    if (!r.ok) { btn.disabled = false; return toast("Couldn't reach Mentor to check that answer. Check that the server is on, then try again."); }
    M.result = r; M.grade_wrong = false;
    const n = r.hits.length + r.missed.length, pct = Math.round(r.coverage * 100);
    $('#mpanel').innerHTML = `<div class="panel" id="rpanel">
      <p class="deckname">${esc(M.card.prompt)}</p>
      <h3 tabindex="-1" id="rhead">${r.hits.length} of ${n} key ideas</h3>
      <div class="meter" role="img" aria-label="${pct}% of key ideas covered"><span style="transform:scaleX(${r.coverage})"></span></div>
      ${text ? `<p class="deckname">You wrote</p><p class="model" style="border-color:var(--frost)">${esc(text)}</p>` : ''}
      <ul class="ideas">${r.hits.map(h => `<li class="hit">${esc(h)}</li>`).join('')}${r.missed.map(h => `<li class="miss">Missing: ${esc(h)}</li>`).join('')}</ul>
      <p class="deckname">Model answer</p><p class="model">${esc(r.reference)}</p>
      <p class="coach"><b>Mentor:</b> ${esc(r.coach)}</p>
      <fieldset><legend>How well did you know it?</legend>
        <div class="seg rates">${RATES.map(([v, n, d], i) => `<label><input type="radio" name="rate" value="${v}" ${v === r.suggested ? 'checked' : ''}><span><b>${i + 1}. ${n}</b><small>${d}</small><small class="when">Back in ${back(r.previews[v])}</small>${v === r.suggested ? '<em class="tag">Mentor suggests</em>' : ''}</span></label>`).join('')}</div>
        <p class="help">Mentor's suggestion comes from the key ideas you covered; pick what feels true. Keys <kbd>1</kbd>–<kbd>4</kbd> choose, <kbd>Enter</kbd> confirms.</p></fieldset>
      <div class="row" style="margin-bottom:var(--s3)"><button type="button" class="primary" id="rateBtn">${verb(r.suggested)}</button></div>
      <label class="check"><input type="checkbox" id="gw"> Mentor's grade was wrong (your answer was better or worse than it scored)</label></div>`;
    $('#rhead').focus();
    $('#gw').onchange = e => M.grade_wrong = e.target.checked;
    const pick = () => +($('input[name=rate]:checked')?.value || 0);
    $$('input[name=rate]').forEach(i => i.onchange = () => $('#rateBtn').textContent = verb(pick()));
    $('#rateBtn').onclick = () => pick() && rate(pick());
  }
  async function rate(v) {
    if (!M.result) return; const r = M.result; M.result = null;
    let s; try { s = await send('rate', {attempt: r.attempt, rating: v, grade_wrong: M.grade_wrong}); } catch (e) { s = {ok: false}; }
    if (!s.ok) { M.result = r; return toast("Couldn't save that rating. Try again in a moment."); }
    toast(v === 1 ? 'Coming back in 10 minutes for another try.' : `Saved. Next review in ${back(s.days)}.`);
    next();
  }
  addEventListener('keydown', e => {
    if (here !== 'mentor' || !M.result || document.activeElement.tagName === 'TEXTAREA') return;
    if (/^[1-4]$/.test(e.key)) { const i = $$('input[name=rate]')[+e.key - 1]; if (i) { i.checked = true; i.dispatchEvent(new Event('change')); i.focus(); } }
    else if (e.key === 'Enter' && document.activeElement.type === 'radio') { e.preventDefault(); $('#rateBtn').click(); }
  });
  return {show};
})();
