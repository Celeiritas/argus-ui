// Mentor: learn the code you build. Lessons (teach -> drills, explain cards, terms) + plain decks,
// spaced repetition, typed answers, a hint ladder, calibration. See docs/mentor.md.
// A bundled server plugin (docs/leafy-plugin.md): Elaia loads this script and page.css on the Mentor section only.
// It is first-party code, so besides the plugin api it uses Elaia's page helpers ($, $$, esc, url, toast).
(() => {
  let ROOT = null;                            // the section's content area, from show(el)
  let FX = null;                              // Elaia's shared effects (api.fx); null on an Elaia older than 4.18
  let ARGUS = null;                           // Argus's reactions (api.argus); null on an Elaia older than 4.20
  const M = {deck: null, view: 'practice', card: null, t0: 0, result: null, shown: false, decks: [], modules: [], stats: null,
             hints: 0, reflections: [], idle: null, step: 0, notes: [], session: {answered: 0, right: 0, missed: []}, replay: []};
  try { M.deck = localStorage.getItem('mentor-deck') || null; M.view = localStorage.getItem('mentor-view') === 'modules' ? 'modules' : 'practice'; } catch (e) {}
  const save = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) {} };
  const stored = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const get = async p => (await fetch(url('api/mentor/' + p), {cache: 'no-store'})).json();
  const send = async (p, body) => (await fetch(url('api/mentor/' + p), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json();
  // shown in Anki's order, keys 1-4 left to right; value = FSRS rating (1 Again ... 4 Easy)
  const RATES = [[1, 'Again', "Didn't know it"], [2, 'Hard', 'Got there with effort'], [3, 'Good', 'Took some thought'], [4, 'Easy', 'Quick and sure']];
  const CONF = [[1, 'Guessing'], [2, 'Unsure'], [3, 'Fairly sure'], [4, 'Certain']];
  const TYPES = {'pre-mortem': 'Find the bug', 'trade-off': 'Why this design', 'hci-bridge': 'Human factors link'};
  const SUMMARY = [['schematic_mental_model', 'The big picture'], ['design_rules_heuristics', "Why it's built this way"], ['hard_rules_invariants', 'Rules that must always hold'], ['hci_human_factors_bridge', 'Human factors link']];
  const LEARN = ['orientation', 'teach', 'level0', 'preread'];
  const IDLE = {drill: 45, term: 30, explain: 90, define: 60};        // seconds without a keystroke before the Hint button pulses
  const BLANK = /\{\{\s*BLANK(?:_(\d+))?\s*\}\}/g;
  const back = d => d < 1 / 24 ? `${Math.max(1, Math.round(d * 1440))} min` : d < 1 ? `${Math.round(d * 24)} hour${Math.round(d * 24) === 1 ? '' : 's'}` : `${Math.round(d)} day${Math.round(d) === 1 ? '' : 's'}`;
  const verb = v => v === 1 ? 'Run again in 10 min' : 'Save and continue';
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  const words = s => (s.match(/[A-Za-z0-9_']+/g) || []).length;
  function calText(c) { if (c == null) return 'not enough answers yet'; if (c > .15) return 'running overconfident'; if (c < -.15) return 'running underconfident'; return 'well calibrated'; }
  function when(ts) { if (!ts) return ''; const d = new Date(ts * 1000), m = (ts * 1000 - Date.now()) / 60000; return m < 60 ? `in ${Math.max(1, Math.round(m))} min` : m < 1440 ? `at ${d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}` : d.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'}); }
  // text from a lesson: paragraphs, `inline code` and ```fenced``` blocks; escaped first, so nothing in it becomes markup
  const inline = s => s.replace(/`([^`\n]+)`/g, '<code>$1</code>').replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
  const rich = t => esc(t).split(/```[\w-]*\n?([\s\S]*?)```/).map((part, i) => i % 2 ? `<pre class="code"><code>${part.replace(/\n$/, '')}</code></pre>`
    : part.split(/\n{2,}/).filter(p => p.trim()).map(p => `<p>${inline(p.trim()).replace(/\n/g, '<br>')}</p>`).join('')).join('');
  // where the code is: only its last part (the function), never folders or file names; the Lessons view lists the files
  const crumb = s => { const x = (s || '').split(/\s*(?:->|→|›)\s*/).filter(Boolean).pop(); return x && !/\.(?:py|js|mjs|ts|css|json|sh|md|html|ya?ml|toml|txt)$/i.test(x) ? `<p class="crumb"><span class="sr">Where in the code: </span><span>${inline(esc(x))}</span></p>` : ''; };
  // a card's title: short text is the heading; a sentence goes under a short heading as text, so no heading runs two lines
  const title = (t, short) => t.length <= 60 ? `<h3 id="qprompt">${inline(esc(t))}</h3>` : `<h3>${esc(short)}</h3><div class="prompt" id="qprompt">${rich(t)}</div>`;
  const kindLabel = c => c.kind === 'drill' ? `Code drill · level ${c.level} of 3: ${c.level_name.toLowerCase()}` : c.kind === 'explain' ? (TYPES[(c.type || '').toLowerCase()] || 'Explain it')
    : c.kind === 'term' ? `Term${c.category ? ' · ' + c.category : ''}` : c.kind === 'teach' ? `Teach${c.category ? ' · ' + c.category : ''}` : c.kind === 'level0' ? 'Worked example · read it line by line'
    : c.kind === 'preread' ? `Before ${(TYPES[(c.type || '').toLowerCase()] || 'the explain card').toLowerCase().replace('find the bug', 'the bug hunt')}` : c.kind === 'orientation' ? 'Orientation · one screen before the cards' : '';
  // the verdict after an answer: one band in one place, an icon and a word as well as the colour (never colour alone)
  const ICON = {ok: '<circle cx="12" cy="12" r="10"/><path d="M7 12.5l3.2 3.2L17 9"/>', part: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    bad: '<circle cx="12" cy="12" r="10"/><path d="M8.5 8.5l7 7M15.5 8.5l-7 7"/>', shown: '<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.6"/>'};
  const WORD = {ok: 'Correct', part: 'Partly right', bad: 'Not quite', shown: ''};
  const tone = (cov, shown) => shown ? 'shown' : cov >= .99 ? 'ok' : cov > 0 ? 'part' : 'bad';
  const verdict = (kind, title, body) => `<div class="verdict ${kind}" role="status"><p class="vt" id="rhead" tabindex="-1"><svg viewBox="0 0 24 24" aria-hidden="true">${ICON[kind]}</svg>`
    + `<span>${WORD[kind] ? `<b>${WORD[kind]}</b>${title ? ' · ' : ''}` : ''}${title}</span></p>${body || ''}</div>`;
  // a long model answer: its first paragraph; the rest (evidence, notes, sources) one click away
  const answerBlock = t => {
    const parts = String(t || '').includes('```') ? [String(t || '')] : String(t || '').split(/\n{2,}/).filter(x => x.trim());
    return `<div class="model">${rich(parts[0] || '')}</div>` + (parts.length > 1 ? `<details class="more"><summary>Show the full answer and sources</summary><div class="model">${rich(parts.slice(1).join('\n\n'))}</div></details>` : '');
  };
  const need = (el, msg) => { const at = el.closest('p') || el; let m = at.parentElement.querySelector('.needmsg'); if (!m) { m = document.createElement('p'); m.className = 'needmsg'; m.setAttribute('role', 'alert'); at.after(m); }
    m.textContent = msg; el.focus(); el.oninput = (f => e => { m.remove(); el.oninput = f; if (f) f(e); })(el.oninput); };
  const sourceName = c => c.module || (M.decks.find(d => d.id === c.deck) || {}).name || c.deck;
  const moduleOf = id => M.modules.find(m => m.id === id);
  const isLearn = c => LEARN.includes(c.kind);
  const LEAVES = {colors: ['#9BAA6A', '#B7C47E', '#7E8C52'], shape: 'leaf', n: 9, spread: 34, size: [4, 7], fall: 12, ms: 650};   // Athena's olive

  async function show(el, api) {
    ROOT = el; FX = api && api.fx || null; ARGUS = api && api.argus || null;                                // called once; there is no refresh(), so Mentor keeps its own state
    const [{decks}, s] = await Promise.all([get('decks'), get('stats')]);
    M.decks = decks; M.stats = s; M.modules = s.modules || [];
    if (M.deck && !decks.some(d => d.id === M.deck) && !moduleOf(M.deck)) M.deck = null;
    ROOT.innerHTML = `<section class="persona practice mentor" aria-label="Mentor">
      <div class="mbar"><div class="views" role="group" aria-label="View">
          <button type="button" data-view="practice" aria-pressed="${M.view === 'practice'}">Study</button>
          <button type="button" data-view="modules" aria-pressed="${M.view === 'modules'}">Lessons</button></div>
        <div class="pick"><label for="mdeck">Study</label><select id="mdeck"></select></div></div>
      <p class="mstats" id="mstats" aria-live="polite"></p><div id="mpanel"></div></section>`;
    fillPicker();
    $('#mdeck').onchange = e => { M.replay = []; M.deck = e.target.value || null; save('mentor-deck', M.deck); if (M.view !== 'practice') setView('practice'); else next(); };
    $$('.views button').forEach(b => b.onclick = () => setView(b.dataset.view));
    setView(M.view);
  }
  function fillPicker() {
    const opt = (id, n) => `<option value="${esc(id)}" ${(M.deck || '') === id ? 'selected' : ''}>${esc(n)}</option>`;
    const learning = m => m.to_learn ? ` (learning ${m.learn.length - m.to_learn}/${m.learn.length})` : '';
    // Submenus (4.22.0): a lesson whose project reads "MENU › Sub" goes in its own group, which starts with "Study all of
    // it" (and the menu gets one "Study all" for every submenu under it); other lessons stay in Lessons, as before.
    const SEP = ' \u203a ';
    const plain = M.modules.filter(m => !(m.project || '').includes(SEP));
    const subs = [...new Set(M.modules.map(m => m.project || '').filter(p => p.includes(SEP)))].sort();
    const roots = [...new Set(subs.map(p => p.split(SEP)[0]))];
    $('#mdeck').innerHTML = opt('', 'Everything, mixed') +
      roots.map(r => `<optgroup label="${esc(r)}">${opt('group:' + r, 'Study all of ' + r)}</optgroup>` +
        subs.filter(p => p.split(SEP)[0] === r).map(p => `<optgroup label="${esc(p)}">${opt('group:' + p, 'Study all: ' + p.split(SEP).slice(1).join(SEP))}` +
          M.modules.filter(m => m.project === p).map(m => opt(m.id, m.name + learning(m))).join('') + '</optgroup>').join('')).join('') +
      (plain.length ? `<optgroup label="Lessons">${plain.map(m => opt(m.id, (m.project ? m.project + ': ' : '') + m.name + learning(m))).join('')}</optgroup>` : '') +
      (M.decks.length ? `<optgroup label="Decks">${M.decks.map(d => opt(d.id, d.name)).join('')}</optgroup>` : '');
  }
  function setView(v) {
    M.view = v; M.replay = []; save('mentor-view', v === 'modules' ? v : null);
    $$('.views button').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === v));
    v === 'modules' ? modulesView() : next();
  }
  async function stats() {
    const s = await get('stats' + (M.deck ? '?deck=' + encodeURIComponent(M.deck) : ''));
    M.stats = s; M.modules = s.modules || M.modules; fillPicker();
    const m = M.deck && moduleOf(M.deck), read = m ? m.learn.filter(l => l.seen).length : 0, all = m ? m.learn.length : 0;
    $('#mstats').innerHTML = (m && all ? `<span class="lp"><span class="lpbar" role="progressbar" aria-label="Lesson cards read" aria-valuemin="0" aria-valuemax="${all}" aria-valuenow="${read}"><span style="width:${Math.round(100 * read / all)}%"></span></span><span>${read} of ${all} lesson cards read</span></span>` : '')
      + `<span>${s.learn ? `<b>${s.learn}</b> to learn · ` : ''}<b>${s.due}</b> due · <b>${s.new}</b> new</span>`;
  }
  const clearIdle = () => { if (M.idle) clearTimeout(M.idle); M.idle = null; };

  /* ----- one card: ask ----- */
  async function next(extra) {
    if (M.view !== 'practice') return;
    clearIdle(); stats();
    const seq = M.seq = (M.seq || 0) + 1;         // two quick picker changes: only the last request may draw
    const replaying = M.replay.length > 0;
    const r = replaying ? await get('next?replay=' + encodeURIComponent(M.replay.shift()))
      : await get('next?' + (M.deck ? 'deck=' + encodeURIComponent(M.deck) + '&' : '') + (extra ? 'extra=1' : ''));
    if (seq !== M.seq || M.view !== 'practice') return;
    M.card = r.card; if (M.card) M.card.replaying = replaying; M.result = null; M.hints = 0; M.reflections = []; M.step = 0; M.notes = [];
    if (!M.card) {
      const t = M.session, miss = [...new Set(t.missed)];
      $('#mpanel').innerHTML = `<div class="panel done"><p class="kicker">All caught up</p>
        <h2 class="lesson-title">${t.answered ? `This session: ${plural(t.answered, 'card')} answered, ${t.right} right.` : 'Nothing is due here.'}</h2>
        <p class="coach">${r.next_due ? `The next card comes back ${when(r.next_due)}. ` : ''}Spacing reviews out is what makes them stick, so stopping here is a good choice.</p>
        <div class="row">${miss.length ? `<button type="button" class="primary" id="replay">Replay your ${plural(miss.length, 'mistake')}</button>` : ''}<button type="button" id="ahead">Practise ahead</button><button type="button" id="toMods">Go to lessons</button></div></div>`;
      if (miss.length) $('#replay').onclick = () => { M.replay = miss; t.missed = []; next(); };
      $('#ahead').onclick = () => next(true); $('#toMods').onclick = () => setView('modules'); return;
    }
    const c = M.card;
    if (isLearn(c)) return learnCard(c);
    const mod = moduleOf(c.deck), big = mod && mod.summary && mod.summary.schematic_mental_model;
    const head = `<p class="deckname">${esc(sourceName(c))} · <span class="kind">${esc(kindLabel(c))}</span>${c.reps ? '' : ' · new card'}</p>${crumb(c.breadcrumb)}
      ${big && c.kind !== 'term' ? `<details class="big"><summary>Show the big picture of this lesson</summary>${rich(big)}</details>` : ''}`;
    const conf = `<fieldset><legend>How sure are you?</legend><div class="seg">${CONF.map(([v, n]) => `<label><input type="radio" name="conf" value="${v}">${n}</label>`).join('')}</div></fieldset>`;
    const go = `<div class="row"><button type="submit" class="primary" id="checkBtn">Check answer</button><button type="button" id="hintBtn" aria-describedby="hinthelp">Show a hint</button></div>
      <p class="help" id="hinthelp">A hint lowers the rating Mentor suggests; the answer counts as a blank. <kbd>Alt</kbd>+<kbd>H</kbd> opens the next hint.</p><div id="hints" aria-live="polite"></div>`;
    let body;
    if (c.kind === 'drill' && c.level < 3) {
      const nums = [...new Set([...c.code.matchAll(BLANK)].map(m => +(m[1] || 1)))].sort((a, b) => a - b), done = new Set();
      const code = esc(c.code).replace(BLANK, (m, n) => { n = +(n || 1); if (done.has(n)) return `<span class="ghost">blank ${n}</span>`; done.add(n);
        const w = c.widths[nums.indexOf(n)] || 6; return `<input class="blank" data-n="${n}" aria-label="Blank ${n} of ${nums.length}" style="width:${Math.min(w, 60) + 2}ch" autocomplete="off" autocapitalize="off" spellcheck="false">`; });
      body = `${title(c.context || c.prompt, 'Fill in the missing code')}
        <pre class="code fill"><code>${code}</code></pre>
        <p class="help">Type the missing code in each box. <kbd>Enter</kbd> moves to the next box; <kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p>`;
    } else if (c.kind === 'drill') {
      const code = esc(c.code).replace(BLANK, '<span class="slot">your code goes here</span>');
      body = `${title(c.context || c.prompt, 'Write the body')}
        <pre class="code"><code>${code}</code></pre>
        <div class="field"><label for="ans">Function body</label>
          <textarea id="ans" class="codein" aria-describedby="anshelp" autocomplete="off" autocapitalize="off" spellcheck="false" wrap="off"></textarea>
          <p class="help" id="anshelp">Write the body from memory; indentation is matched for you. <kbd>Enter</kbd> keeps the indent (one more after a colon); <kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p></div>`;
    } else if (c.kind === 'term') {
      const sentence = esc(c.prompt).replace(BLANK, () => '<input class="blank term" id="ans" aria-label="Missing term" autocomplete="off" autocapitalize="off" spellcheck="false">');
      body = `<p class="cloze" id="qprompt">${inline(sentence)}</p><p class="help">Type the missing term. <kbd>Enter</kbd> checks.</p>`;
    } else {
      body = `<div class="prompt" id="qprompt">${rich(c.prompt)}</div>
        <div class="field"><label for="ans">${c.kind === 'explain' ? 'Your explanation, in your own words' : 'Your answer, in your own words'}</label>
          <textarea id="ans" aria-describedby="anshelp" autocomplete="off" spellcheck="true"></textarea>
          <p class="help" id="anshelp">Write it before peeking. Leave it blank if you don't know. <kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p></div>`;
    }
    $('#mpanel').innerHTML = `<form class="panel" id="qform" novalidate>${head}${body}${conf}${go}</form>`;
    M.t0 = performance.now();
    wireAsk(c);
  }
  function wireAsk(c) {
    const btn = $('#checkBtn'), form = $('#qform'), boxes = $$('#qform input.blank'), ta = $('#qform textarea'), hb = $('#hintBtn');
    const typed = () => boxes.some(b => b.value.trim()) || (ta && ta.value.trim());
    const label = () => btn.textContent = M.hints === 4 ? 'Rate it' : typed() ? 'Check answer' : 'Show answer';
    const idle = () => { clearIdle(); if (M.hints < 4) M.idle = setTimeout(() => hb.classList.add('pulse'), (IDLE[c.kind] || 60) * 1000); };
    form.oninput = () => { label(); hb.classList.remove('pulse'); idle(); }; label(); idle();
    (boxes[0] || ta).focus();
    form.onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); } };
    boxes.forEach((b, i) => b.onkeydown = e => { if (e.key !== 'Enter' || e.ctrlKey || e.metaKey) return; e.preventDefault(); boxes[i + 1] ? boxes[i + 1].focus() : form.requestSubmit(); });
    if (ta && ta.classList.contains('codein')) ta.onkeydown = e => {   // keep the indent; one level deeper after a colon
      if (e.key !== 'Enter' || e.ctrlKey || e.metaKey || e.shiftKey) return;
      e.preventDefault();
      const line = ta.value.slice(0, ta.selectionStart).split('\n').pop(), ind = line.match(/^ */)[0] + (/:\s*$/.test(line) ? '    ' : '');
      ta.setRangeText('\n' + ind, ta.selectionStart, ta.selectionEnd, 'end'); label();
    };
    hb.onclick = () => hint();
    form.onsubmit = e => {
      e.preventDefault();
      // a blank "Show answer" first offers a hint (one click either way)
      if (!typed() && M.hints === 0 && !$('#offer')) {
        $('#hints').insertAdjacentHTML('beforeend', `<div class="hint offer" id="offer"><p>Try a hint first?</p><div class="row"><button type="button" class="primary" id="offerHint">Show a hint</button><button type="button" id="offerAns">Show the answer</button></div></div>`);
        $('#offerHint').onclick = () => { $('#offer').remove(); hint(); }; $('#offerAns').onclick = () => { $('#offer').remove(); hint(4); };
        $('#offerHint').focus(); return;
      }
      check();
    };
  }
  /* ----- the hint ladder: nudge -> the expert's first move -> a near example -> the answer ----- */
  async function hint(rung) {
    const c = M.card; if (!c || M.result || M.hints >= 4) return;
    const open = $('#hints .hint:not(.offer):last-child textarea');
    if (open && words(open.value) < 3 && !rung) { open.focus(); return toast('Say what that hint told you (three words or more) before the next one.'); }
    if (open) M.reflections.push(open.value.trim().slice(0, 300));
    const want = rung || (M.hints + 1);
    let r; try { r = await send('answer', {card: c.id, hint: want}); } catch (e) { r = {ok: false}; }
    if (!r.ok) return toast("Couldn't reach Mentor for a hint. Check that the server is on, then try again.");
    M.hints = r.rung; $('#hintBtn').classList.remove('pulse'); clearIdle();
    $$('#hints .hint textarea').forEach(t => t.disabled = true);
    const last = r.rung === 4;
    $('#hints').insertAdjacentHTML('beforeend', `<div class="hint" id="rung${r.rung}"><p class="label">Hint ${r.rung} of 4 · ${esc(r.name)}</p><div class="model">${rich(r.text)}</div>
      ${last ? '' : `<label for="refl${r.rung}">What did that tell you?</label><textarea id="refl${r.rung}" rows="2" maxlength="300" placeholder="Three words or more"></textarea>`}</div>`);
    const hb = $('#hintBtn'), cb = $('#checkBtn');
    if (last) { hb.hidden = true; cb.textContent = 'Rate it'; $$('#qform input.blank, #qform textarea#ans').forEach(i => i.disabled = true); cb.focus(); }
    else { hb.textContent = r.next === 4 ? 'Show the answer' : 'Next hint'; $(`#refl${r.rung}`).focus(); }
  }

  /* ----- one card: check and give feedback ----- */
  const keyIdeas = r => (r.hits.length + r.missed.length) ? `<ul class="ideas marked">${r.hits.map(h => `<li class="hit"><b>✓ Got it</b><span>${esc(h)}</span></li>`).join('')}${r.missed.map(h => `<li class="miss"><b>✕ Missing</b><span>${esc(h)}</span></li>`).join('')}</ul>` : '';
  async function check() {
    const c = M.card, boxes = $$('#qform input.blank'), ta = $('#qform textarea#ans');
    const text = M.hints === 4 ? '' : c.kind === 'drill' && c.level < 3 ? JSON.stringify([...boxes].sort((a, b) => a.dataset.n - b.dataset.n).map(b => b.value))
      : c.kind === 'drill' ? ta.value.replace(/\s+$/, '') : (ta || boxes[0]).value.trim();
    const open = $('#hints .hint:not(.offer):last-child textarea'); if (open && !open.disabled) M.reflections.push(open.value.trim().slice(0, 300));
    const conf = +($('input[name=conf]:checked')?.value || 0) || null;
    const btn = $('#checkBtn'); btn.disabled = true; clearIdle();
    let r; try { r = await send('answer', {card: c.id, text, confidence: conf, ms: Math.round(performance.now() - M.t0), hints: M.hints, reflections: M.reflections}); } catch (e) { r = {ok: false}; }
    if (!r.ok) { btn.disabled = false; return toast("Couldn't reach Mentor to check that answer. Check that the server is on, then try again."); }
    M.result = r; M.grade_wrong = false; r.shown = M.hints === 4;
    const n = r.hits.length + r.missed.length, pct = Math.round(r.coverage * 100);
    const shown = M.hints === 4;
    let kind = tone(r.coverage, shown), head, detail;
    if (c.kind === 'drill' && c.level < 3) {
      head = shown ? 'The answer was shown' : `${r.hits.length} of ${plural(n, 'blank')} right`;
      detail = `<ul class="ideas marked">${r.blanks.map(b => b.ok ? `<li class="hit"><b>✓ Right</b><span>Blank ${b.n}: <code>${esc(b.expected)}</code></span></li>`
          : `<li class="miss"><b>✕ Wrong</b><span>Blank ${b.n}: ${b.typed && b.typed.trim() ? `you wrote <code>${esc(b.typed)}</code>, ` : ''}the code has <code>${esc(b.expected)}</code></span></li>`).join('')}</ul>
        <p class="label">The full code</p><pre class="code"><code>${esc(r.canonical)}</code></pre>`;
    } else if (c.kind === 'drill') {
      head = shown ? 'The answer was shown' : r.same_structure ? 'Same structure as the model answer' : r.problem ? "Python can't read your version yet" : `${pct}% like the model answer`;
      if (!shown) kind = r.same_structure ? 'ok' : r.problem ? 'bad' : 'part';
      detail = `${r.problem ? `<p class="coach">Python says: <code>${esc(r.problem)}</code></p>` : ''}
        <div class="pair"><div><p class="label">Your version</p><pre class="code"><code>${esc(r.yours)}</code></pre></div>
        <div><p class="label">Model answer</p><pre class="code"><code>${esc(r.canonical)}</code></pre></div></div>`;
    } else if (c.kind === 'term') {
      const typed = text;
      head = shown ? `The answer was shown: “${esc(r.reference)}”` : r.coverage >= .99 ? esc(r.reference) : `the answer is “${esc(r.reference)}”`;
      detail = `${typed && r.coverage < .99 ? `<p class="mine">You wrote “${esc(typed)}”.</p>` : ''}
        <dl class="defs">${r.definition ? `<dt>What it means</dt><dd>${inline(esc(r.definition))}</dd>` : ''}${r.anchor ? `<dt>Where it's used</dt><dd>${inline(esc(r.anchor))}</dd>` : ''}${r.contrast ? `<dt>Not to be confused with</dt><dd>${inline(esc(r.contrast))}</dd>` : ''}</dl>`;
    } else {
      head = shown ? 'The answer was shown' : `${r.hits.length} of ${plural(n, 'key idea')}`;
      detail = `${text ? `<p class="label">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}
        ${keyIdeas(r)}
        <p class="label">Model answer</p>${answerBlock(r.reference)}`;
    }
    const note = r.note ? `<p class="label">Why it's written this way</p>${answerBlock(r.note)}` : '';
    const stuck = r.stuck === 'repeat' ? `<p class="coach back"><b>Twice in a row.</b> ${esc(r.move)} The lesson's card for this comes back before the next try.</p>`
      : r.stuck === 'skipped' ? `<p class="coach back"><b>You skipped the lesson card for this one.</b> It comes back before the next try.</p>` : '';
    const lvl = v => r.level_after && r.level_after[v] !== r.level ? ` · level ${r.level_after[v]}` : '';
    $('#mpanel').innerHTML = `<div class="panel" id="rpanel">
      <p class="deckname">${esc(sourceName(c))} · ${esc(kindLabel(c))}${M.hints ? ` · ${plural(M.hints, 'hint')} used` : ''}</p>
      ${verdict(kind, head, `<p class="coach">${inline(esc(r.coach))}</p>`)}${stuck}
      ${detail}${note}
      ${c.replaying ? `<p class="coach">A replay: practice only. The card keeps the schedule from your first try.</p><div class="row"><button type="button" class="primary" id="replayNext">${M.replay.length ? 'Go to the next mistake' : 'Finish the replay'}</button></div></div>` : `<fieldset class="rategroup"><legend>How well did you know it? Mentor suggests <b>${esc(RATES.find(x => x[0] === r.suggested)[1])}</b>.</legend>
        <div class="seg rates">${RATES.map(([v, nm, d], i) => `<label><input type="radio" name="rate" value="${v}" ${v === r.suggested ? 'checked' : ''}><span><b>${i + 1}. ${nm}</b><small>${d}</small><small class="when">In ${back(r.previews[v])}${lvl(v)}</small>${v === r.suggested ? '<em class="tag">Mentor suggests</em>' : ''}</span></label>`).join('')}</div>
        <p class="help">The suggestion comes from what you got right${M.hints ? ' and the hints you used' : ''}; pick what feels true. Keys <kbd>1</kbd>–<kbd>4</kbd> choose, <kbd>Enter</kbd> saves.</p></fieldset>
      <div class="row"><button type="button" class="primary" id="rateBtn">${verb(r.suggested)}</button></div>
      <details class="report"><summary>Report a grading problem</summary><label class="check"><input type="checkbox" id="gw"> Mentor's grade was wrong: my answer was better or worse than it scored</label></details></div>`}`;
    if (c.replaying) { $('#rhead').focus(); $('#replayNext').onclick = () => { M.result = null; next(); }; return; }
    $('#rhead').focus();
    if (r.ai_pending) aiLater(r.attempt);
    // each key idea you got: a few olive leaves from its tick (reduced motion: the tick alone)
    if (FX) $$('#rpanel .ideas .hit').forEach((li, i) => setTimeout(() => { const b = li.getBoundingClientRect(); if (li.isConnected) FX.burst([b.left + 8, b.top + b.height / 2], LEAVES); }, 120 * i));
    // every key idea there: Mentor nods. Nothing for a miss: a wrong answer is part of learning, not something to flinch at
    const ideas = $$('#rpanel .ideas li'), all = ideas.length > 0 && ideas.every(li => li.classList.contains('hit'));
    if (ARGUS && all) ARGUS.react('nod');
    // a streak: cards in a row with every key idea (kept in this browser; a miss ends it). Every third one sends a ribbon of
    // motes from the result up to Mentor's medallion, and the panel says how many in a row
    if (ideas.length) {
      const streak = all ? (+stored('mentor-streak') || 0) + 1 : 0; save('mentor-streak', streak ? String(streak) : null); ROOT.firstElementChild.dataset.streak = streak;
      if (streak >= 3) $('#rpanel .deckname').append(` · ${streak} in a row`);
      const hero = $('#hero'); if (FX && streak && streak % 3 === 0 && hero && !hero.hidden && hero.offsetWidth) FX.motes($('#rhead'), hero, {color: '#B7C47E', n: 26, ms: 1100, lift: 90});
    }
    $('#gw').onchange = e => M.grade_wrong = e.target.checked;
    const pick = () => +($('input[name=rate]:checked')?.value || 0);
    $$('input[name=rate]').forEach(i => i.onchange = () => $('#rateBtn').textContent = verb(pick()));
    $('#rateBtn').onclick = () => pick() && rate(pick());
  }
  async function rate(v) {
    if (!M.result) return; const r = M.result; M.result = null;
    let s; try { s = await send('rate', {attempt: r.attempt, rating: v, grade_wrong: M.grade_wrong}); } catch (e) { s = {ok: false}; }
    if (!s.ok) { M.result = r; return toast("Couldn't save that rating. Try again in a moment."); }
    if (s.learn) { toast(r.skipped ? 'Skipped. It comes back if the practice card goes wrong.' : 'Read. On to the next card.'); return next(); }
    M.session.answered++; if (r.coverage >= .99 && !r.shown && v > 1) M.session.right++; else M.session.missed.push(M.card && M.card.id);
    const lv = s.level_change > 0 ? ` Level ${s.level} next time: ${s.level === 3 ? "you'll write the whole body" : 'the logic is blanked'}.` : s.level_change < 0 ? ` Back to level ${s.level} for now.` : '';
    toast(s.held ? `Held for a day${s.back ? ', and the lesson card for it comes back first' : ''}.` : (v === 1 ? 'Coming back in 10 minutes for another try.' : `Saved. Next review in ${back(s.days)}.`) + lv);
    next();
  }

  /* ----- Learn cards: orientation, teach (+ spot it), level 0 worked example, pre-read ----- */
  function learnCard(c, readOnly) {
    const g = M.guess && M.guess.id === c.id ? M.guess : null; M.guess = null;
    const head = `<p class="deckname">${esc(sourceName(c))} · <span class="kind">${esc(kindLabel(c))}</span>${c.refresh ? ' · back to the lesson' : readOnly ? ' · reading again' : ''}</p>${crumb(c.breadcrumb)}`;
    const skip = !readOnly && (c.kind === 'teach' || c.kind === 'level0') ? `<button type="button" id="skipBtn">I know this, test me</button>` : '';
    const done = readOnly ? `<button type="button" class="primary" id="doneBtn">Back to lessons</button>` : '';
    if (c.try && !readOnly && !g && !c.refresh) return tryFirst(c, head, skip);
    // the try-first question stays above the explanation: with the guess beside it, or as plain text when reading again
    const tried = c.try ? `<div class="callout tried"><p class="label">Try first</p><p class="task">${inline(esc(c.try))}</p>${g ? `<p class="mine">Your guess: ${esc(g.text)}</p>` : ''}</div>` : '';
    let body, go;
    if (c.kind === 'orientation') {
      body = `<h2 class="lesson-title">${esc(c.module || 'This lesson')}</h2>
        <p class="kicker">What this lesson covers</p><div class="prompt">${rich(c.prompt)}</div>
        ${c.terms && c.terms.length ? `<p class="kicker">Terms you'll meet</p><p class="termline">${c.terms.map(esc).join(', ')}</p>` : ''}
        ${c.bridge ? `<p class="kicker">Why it matters</p><div class="prompt">${rich(c.bridge)}</div>` : ''}`;
      go = readOnly ? done : `<button type="submit" class="primary" id="goBtn">Start the lesson</button>`;
    } else if (c.kind === 'teach') {
      const lines = c.spot ? c.spot.snippet.split('\n') : [];
      body = `<h3>${esc(c.prompt)}</h3>${tried}
        <dl class="defs">${c.definition ? `<dt>What it means</dt><dd>${inline(esc(c.definition))}</dd>` : ''}${c.anchor ? `<dt>Where it's used</dt><dd>${inline(esc(c.anchor))}</dd>` : ''}${c.contrast ? `<dt>Not to be confused with</dt><dd>${inline(esc(c.contrast))}</dd>` : ''}${c.move ? `<dt>What an expert looks for</dt><dd>${inline(esc(c.move))}</dd>` : ''}</dl>
        ${c.spot ? `<p class="task" id="spotq">Spot it: ${readOnly ? `line ${c.spot.line}` : 'pick the line that uses it'}</p>
          <ol class="lines" aria-labelledby="spotq">${lines.map((l, i) => `<li><button type="button" class="line${readOnly && i + 1 === c.spot.line ? ' is' : ''}" data-line="${i + 1}" ${readOnly ? 'disabled' : ''}><span class="n">${i + 1}</span><code>${esc(l) || ' '}</code></button></li>`).join('')}</ol>
          ${readOnly ? `<p class="coach">${inline(esc(c.spot.why))}</p>` : `<p class="help"><kbd>↑</kbd>/<kbd>↓</kbd> move, <kbd>Enter</kbd> picks; or type the line number: <input class="blank" id="lineNo" inputmode="numeric" aria-label="Line number" style="width:4ch"></p>`}` : ''}`;
      go = readOnly ? done : c.spot ? `<button type="submit" class="primary" id="goBtn">Check this line</button>${skip}` : `<button type="submit" class="primary" id="goBtn">Go to the next card</button>${skip}`;
    } else if (c.kind === 'level0') {
      const lines = c.code.split('\n'), ann = c.annotations || [];
      body = `${title(c.context || 'Read the code, one line at a time', 'Read the code, one line at a time')}
        <pre class="code worked" id="worked"><code>${lines.map((l, i) => `<span class="ln" data-line="${i + 1}">${esc(l) || ' '}</span>`).join('\n')}</code></pre>
        <div id="annot"></div>
        <p class="help" id="annhelp">${readOnly ? 'Every note is shown.' : `Annotation <span id="step">1</span> of ${ann.length}. Say why the line is there (three words or more), then <kbd>Enter</kbd> shows the note.`}</p>`;
      go = readOnly ? done : `<button type="button" class="primary" id="goBtn">Show the note</button>${skip}`;
    } else {          // preread
      body = `<h3>Before you hunt the bug: the ideas it rests on</h3>${tried}
        <ol class="ideas keys">${(c.ideas || []).map(i => `<li>${inline(esc(i))}</li>`).join('')}</ol>
        ${c.near ? `<p class="label">A near example</p><pre class="code"><code>${esc(c.near.code)}</code></pre>
          ${readOnly ? `<p class="coach"><b>${inline(esc(c.near.ask))}</b> ${inline(esc(c.near.answer || ''))}</p>`
          : `<div class="field"><label for="ans">${esc(c.near.ask)}</label><input id="ans" class="blank wide" autocomplete="off"><p class="help"><kbd>Enter</kbd> reveals the answer.</p></div>`}` : ''}`;
      go = readOnly ? done : `<button type="submit" class="primary" id="goBtn">${c.near ? 'Show the answer' : 'Go to the next card'}</button>`;
    }
    $('#mpanel').innerHTML = `<form class="panel learn" id="qform" novalidate>${head}${body}<div class="row">${go}</div></form>`;
    M.t0 = performance.now();
    if (readOnly) { $('#doneBtn').onclick = () => setView('modules'); if (c.kind === 'level0') revealAll(c); return; }
    wireLearn(c);
  }
  // a question to answer before the explanation (pretesting): typed, never graded or sent, then the card itself
  function tryFirst(c, head, skip) {
    $('#mpanel').innerHTML = `<form class="panel learn" id="qform" novalidate>${head}${c.kind === 'teach' ? `<h3>${esc(c.prompt)}</h3>` : ''}
      <div class="field"><label for="guess">Try first: ${inline(esc(c.try))}</label><textarea id="guess" rows="2" aria-describedby="guesshelp"></textarea>
      <p class="help" id="guesshelp">A guess is fine: it isn't graded. <kbd>Ctrl</kbd>+<kbd>Enter</kbd> shows the ${c.kind === 'teach' ? 'explanation' : 'ideas'}.</p></div>
      <div class="row"><button type="submit" class="primary" id="tryBtn">${c.kind === 'teach' ? 'Show the explanation' : 'Show the ideas'}</button>${skip}</div></form>`;
    M.t0 = performance.now();
    const form = $('#qform'), ta = $('#guess'), go = $('#tryBtn'), sk = $('#skipBtn');
    ta.focus();
    form.onsubmit = e => { e.preventDefault(); if (!words(ta.value)) return need(ta, 'Type a guess first: a word or two is enough. It isn\'t graded.'); M.guess = {id: c.id, text: ta.value.trim()}; learnCard(c); };
    form.onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); } };
    if (sk) sk.onclick = async () => { if (await learnSend(c, '', true, go)) rate(0); };
  }
  // tell Mentor a Learn card was read (or skipped); null if the server couldn't be reached
  async function learnSend(c, text, skipped, go) {
    go.disabled = true;
    let r; try { r = await send('answer', {card: c.id, text, ms: Math.round(performance.now() - M.t0), skipped: !!skipped}); } catch (e) { r = {ok: false}; }
    if (!r.ok) { go.disabled = false; toast("Couldn't reach Mentor. Check that the server is on, then try again."); return null; }
    M.result = {...r, skipped: !!skipped};
    return r;
  }
  function revealAll(c) {
    $('#annot').innerHTML = (c.annotations || []).map((a, i) => `<div class="callout"><b>${i + 1}. Line ${a.line}${a.note ? ': ' + inline(esc(a.note)) : ''}</b><p>${inline(esc(a.why))}</p></div>`).join('');
    $$('#worked .ln').forEach(l => l.classList.toggle('hi', (c.annotations || []).some(a => a.line === +l.dataset.line)));
  }
  function wireLearn(c) {
    const form = $('#qform'), go = $('#goBtn'), skip = $('#skipBtn');
    const finish = async (text, skipped) => {
      const r = await learnSend(c, text, skipped, go);
      if (!r) return;
      if (skipped || c.kind === 'orientation' || (c.kind === 'teach' && !c.spot) || (c.kind === 'preread' && !c.near)) return rate(0);
      learnFeedback(c, r, text);
    };
    if (skip) skip.onclick = () => finish('', true);
    if (c.kind === 'orientation') {
      form.onsubmit = e => { e.preventDefault(); finish(''); };
      go.focus();
    } else if (c.kind === 'teach') {
      if (!c.spot) { form.onsubmit = e => { e.preventDefault(); finish(''); }; go.focus(); return; }
      const lines = $$('.lines .line'), no = $('#lineNo');
      let picked = 0;
      const pick = n => { picked = n; $$('#qform .needmsg').forEach(x => x.remove()); lines.forEach(b => { b.classList.toggle('is', +b.dataset.line === n); b.setAttribute('aria-pressed', +b.dataset.line === n); }); no.value = n || ''; };
      lines.forEach(b => { b.onclick = () => pick(+b.dataset.line); b.onkeydown = e => { const i = +b.dataset.line; if (e.key === 'ArrowDown' && lines[i]) { e.preventDefault(); lines[i].focus(); } if (e.key === 'ArrowUp' && lines[i - 2]) { e.preventDefault(); lines[i - 2].focus(); } }; });
      no.oninput = () => { const n = +no.value; pick(n >= 1 && n <= lines.length ? n : 0); };
      form.onsubmit = e => { e.preventDefault(); if (!picked) return need(no, 'Pick a line first: click it, or type its number.'); finish(String(picked)); };
      lines[0].focus();
    } else if (c.kind === 'level0') {
      stepAnnotation(c, go);
      go.onclick = () => stepAnnotation(c, go, true);
      form.onsubmit = e => e.preventDefault();
    } else {
      const inp = $('#ans');
      form.onsubmit = e => { e.preventDefault(); finish(inp ? inp.value.trim() : ''); };
      (inp || go).focus();
    }
  }
  // level 0: one annotation at a time; the "why" waits until three words are typed
  function stepAnnotation(c, go, advance) {
    const ann = c.annotations || [], k = M.step, box = $('#annot');
    if (advance) {
      const ta = $(`#why${k}`); if (ta && !ta.disabled && words(ta.value) < 3) return need(ta, 'Say why the line is there, in three words or more.');
      if (ta && !ta.disabled) { M.notes.push(ta.value.trim().slice(0, 120)); ta.disabled = true; $(`#call${k}`).insertAdjacentHTML('beforeend', `<p>${inline(esc(ann[k].why))}</p>`); go.textContent = k + 1 < ann.length ? 'Go to the next line' : 'Explain it'; return go.focus(); }
      if (k + 1 < ann.length) M.step++;
      else return selfExplain(c, go);
    }
    const a = ann[M.step];
    $$('#worked .ln').forEach(l => l.classList.toggle('hi', +l.dataset.line === a.line));
    const line = $(`#worked .ln[data-line="${a.line}"]`); if (line) line.scrollIntoView({block: 'nearest'});
    box.insertAdjacentHTML('beforeend', `<div class="callout" id="call${M.step}"><b>${M.step + 1}. Line ${a.line}${a.note ? ': ' + inline(esc(a.note)) : ''}</b>
      <label for="why${M.step}">Why is this line here?</label><input id="why${M.step}" class="blank wide" autocomplete="off" maxlength="120"></div>`);
    $('#step').textContent = M.step + 1;
    const ta = $(`#why${M.step}`); ta.focus(); go.textContent = 'Show the note';
    ta.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); go.click(); } };
  }
  function selfExplain(c, go) {
    $('#annot').insertAdjacentHTML('beforeend', `<div class="callout ask"><label for="ans">${inline(esc(c.prompt))}</label><textarea id="ans" rows="3"></textarea><p class="help"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p></div>`);
    $('#annhelp').textContent = 'Last step: explain it in your own words.';
    const ta = $('#ans'); ta.focus(); go.textContent = 'Check my explanation';
    const finish = async () => {
      if (words(ta.value) < 3) return need(ta, 'Explain it in three words or more first.');
      go.disabled = true;
      let r; try { r = await send('answer', {card: c.id, text: JSON.stringify({reflections: M.notes, explain: ta.value.trim().slice(0, 1500)}), ms: Math.round(performance.now() - M.t0)}); } catch (e) { r = {ok: false}; }
      if (!r.ok) { go.disabled = false; return toast("Couldn't reach Mentor. Check that the server is on, then try again."); }
      M.result = r; learnFeedback(c, r, ta.value.trim());
    };
    go.onclick = finish;
    $('#qform').onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); finish(); } };
  }
  function learnFeedback(c, r, text) {
    let head, detail = '';
    let band;
    if (c.kind === 'teach') {
      const picked = +text, lines = c.spot.snippet.split('\n');
      band = verdict(r.spot_ok ? 'ok' : 'bad', r.spot_ok ? `line ${r.line}` : `it's on line ${r.line}`, `<p class="coach">${inline(esc(String(r.coach || '').replace(/^(It's on line|Line) \d+[:.]\s*(that's it\.?\s*)?/i, '')))}</p>`);
      band += `<ol class="lines">${lines.map((l, i) => { const n = i + 1, right = n === r.line, wrong = n === picked && !r.spot_ok;
        return `<li><span class="line${right ? ' right' : wrong ? ' wrong' : ''}"><span class="n">${n}</span><code>${esc(l) || ' '}</code>${right ? '<b class="mark">✓ The line</b>' : wrong ? '<b class="mark">✕ Your pick</b>' : ''}</span></li>`; }).join('')}</ol>`;
    } else if (c.kind === 'level0') {
      const n = r.hits.length + r.missed.length;
      band = verdict(n ? tone(r.coverage) : 'ok', n ? (r.coverage >= .99 ? `All ${plural(n, 'key idea')}` : `${r.hits.length} of ${plural(n, 'key idea')}`) : 'Explained', `<p class="coach">${inline(esc(r.coach))}</p>`)
        + `${text ? `<p class="label">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}${keyIdeas(r)}`;
    } else {
      band = `<h3 tabindex="-1" id="rhead">${inline(esc(c.near ? c.near.ask : 'Read'))}</h3>${text ? `<p class="label">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}${r.answer ? `<p class="deckname">Answer</p>${answerBlock(r.answer)}` : ''}<p class="coach">${inline(esc(r.coach))}</p>`;
    }
    $('#mpanel').innerHTML = `<div class="panel learn" id="rpanel"><p class="deckname">${esc(sourceName(c))} · ${esc(kindLabel(c))}</p>
      ${band}<div class="row"><button type="button" class="primary" id="rateBtn">Next card</button></div></div>`;
    $('#rhead').focus(); $('#rateBtn').onclick = () => rate(0);
  }

  /* ----- lessons: the CTA summaries, progress, the Learn cards to read again, how to add one ----- */
  /* ----- the local AI's part (docs/mentor-ai.md): Athena's owl brings it when it arrives; the rubric's grade never waits ----- */
  const OWL = '<svg viewBox="22 20 56 66" aria-hidden="true"><path d="M34 40 L35 24 L44 34 Z M66 40 L65 24 L56 34 Z" fill="#8a7a5a"/><ellipse cx="50" cy="56" rx="19" ry="23" fill="#8a7a5a"/><ellipse cx="50" cy="63" rx="11" ry="14" fill="#d9c9a3"/><circle cx="42" cy="44" r="8.5" fill="#efe3c4"/><circle cx="58" cy="44" r="8.5" fill="#efe3c4"/><circle cx="42" cy="44" r="5" fill="#E7C35A"/><circle cx="58" cy="44" r="5" fill="#E7C35A"/><circle cx="42" cy="44" r="2.4" fill="#1C2127"/><circle cx="58" cy="44" r="2.4" fill="#1C2127"/><path d="M50 48 L47 52 L50 56 L53 52 Z" fill="#C9A36A"/></svg>';
  async function aiLater(attempt) {
    const panel = $('#rpanel'); if (!panel) return;
    const box = document.createElement('div'); box.className = 'aiowl'; box.setAttribute('aria-live', 'polite');
    box.innerHTML = `${OWL}<p><small>Local AI</small>Reading your answer…</p>`; $('.coach', panel).after(box);
    for (let i = 0; i < 40; i++) {                 // up to about a minute; give up quietly after that
      await wait(1500); if (!box.isConnected) return;
      let a; try { a = await get('ai?attempt=' + attempt); } catch (e) { continue; }
      if (a.state === 'pending') continue;
      if (a.state !== 'done') { box.remove(); return; }       // off or not answering: the rubric's grade stands alone
      box.innerHTML = `${OWL}<p><small>Local AI · ${esc(a.chat_model || a.model)} · not used for the rating</small>
        Meaning match: <b>${Math.round(a.similarity * 100)}%</b>${a.feedback ? `<span class="fb">${esc(a.feedback)}</span>` : ''}</p>`;
      return;
    }
    box.remove();
  }
  const aiLine = a => !a || !a.enabled ? 'Local AI: off (docs/mentor-ai.md says how to turn it on)' : a.problem ? `Local AI: off, the config has a problem: ${a.problem}`
    : a.answering === false ? `Local AI: on (${a.embed_model}), but its server is not answering` : `Local AI: on (${a.embed_model}${a.feedback ? `, feedback by ${a.chat_model}` : ''}), not used for ratings yet`;
  // Lessons as a course map: one Continue, the reviews due, then each project's lessons as one framed list (a row each:
  // name, one line, progress, one action); everything else (breakdown, Learn cards to read again, sources) one click away
  function modulesView() {
    stats().then(() => {
      const s = M.stats, mods = M.modules;
      const tally = m => Object.values(m.cards || {}).reduce((t, c) => ({n: t.n + c.n, seen: t.seen + c.seen}), {n: 0, seen: 0});
      const action = m => { const t = tally(m); return m.to_learn === m.learn.length && !t.seen ? 'Start' : m.to_learn || t.seen < t.n ? 'Continue' : 'Review'; };
      const cont = moduleOf(M.deck) && (moduleOf(M.deck).to_learn || tally(moduleOf(M.deck)).seen < tally(moduleOf(M.deck)).n) ? moduleOf(M.deck)
        : mods.filter(m => m.to_learn && m.to_learn < m.learn.length).sort((x, y) => y.at - x.at)[0] || null;
      const imp = (s.imports || []).filter(i => !i.ok || i.msg.includes('skipped'));
      const groups = [...new Set(mods.map(m => m.project || 'Lessons'))];
      const row = m => { const t = tally(m), pct = t.n ? Math.round(100 * t.seen / t.n) : 0;
        return `<li class="module"><div class="mrow">
          <div class="mname"><h4 id="mh-${esc(m.id)}">${esc(m.name)}</h4><p class="meta">${plural(t.n, 'card')}${m.to_learn ? ` · ${m.to_learn} lesson cards to read` : ''}${m.built_in ? ' · comes with Argus' : ''}</p></div>
          <div class="mprog"><span class="lpbar" role="progressbar" aria-label="${esc(m.name)}: cards practised" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"><span style="width:${pct}%"></span></span><small>${t.seen ? `${pct}% practised` : 'Not started'}</small></div>
          <button type="button" data-study="${esc(m.id)}" aria-describedby="mh-${esc(m.id)}">${action(m)}</button></div>
          <div class="mmore">${SUMMARY.some(([k]) => m.summary[k]) || (m.summary.lint || []).length ? `<details><summary>About this lesson</summary><dl class="defs">${SUMMARY.filter(([k]) => m.summary[k]).map(([k, n]) => `<dt>${n}</dt><dd>${rich(m.summary[k])}</dd>`).join('')}</dl>${(m.summary.lint || []).length ? `<p class="meta">Notes from the lesson's author: ${m.summary.lint.map(esc).join('; ')}</p>` : ''}</details>` : ''}
          ${m.learn.length ? `<details><summary>Read the lesson again</summary><ul class="learnlist">${m.learn.map(l => `<li><button type="button" data-read="${esc(l.id)}"><span>${esc(l.title)}</span><small>${l.seen ? 'read' : 'not yet'}</small></button></li>`).join('')}</ul></details>` : ''}</div></li>`; };
      $('#mpanel').innerHTML = `<div class="modules">
        ${cont ? `<section class="cont" aria-labelledby="cont-h"><div><p class="kicker">Continue where you left off</p><h2 id="cont-h">${esc(cont.name)}</h2><p class="meta">${cont.to_learn ? `${cont.to_learn} lesson cards still to read` : `${Math.round(100 * tally(cont).seen / (tally(cont).n || 1))}% practised`}</p></div>
          <button type="button" class="primary" data-study="${esc(cont.id)}">Continue the lesson</button></section>` : ''}
        ${s.due ? `<section class="duebar" aria-labelledby="due-h"><div><h2 id="due-h">${plural(s.due, 'card')} due for review</h2><p class="meta">From all your lessons, mixed</p></div><button type="button" id="reviewAll">Review ${plural(s.due, 'card')}</button></section>` : ''}
        ${mods.length ? groups.map((g, gi) => { const ms = mods.filter(m => (m.project || 'Lessons') === g), files = [...new Set(ms.flatMap(m => m.files))];
          return `<section class="group" aria-labelledby="g-${gi}"><div class="ghead"><h2 id="g-${gi}">${esc(g)}</h2>${ms.length > 1 && g !== 'Lessons' ? `<button type="button" class="link" data-study="group:${esc(g)}">Study all ${ms.length}</button>` : ''}</div>
            <ul class="course-list">${ms.map(row).join('')}</ul>
            ${files.length ? `<details class="srcs"><summary>Where these lessons come from (${files.length})</summary><ul>${files.map(f => `<li>${esc(f)}</li>`).join('')}</ul></details>` : ''}</section>`; }).join('')
          : `<div class="empty"><b>No lessons yet</b>Add one with the steps under "Add a lesson".</div>`}
        ${imp.length ? `<p class="label">Inbox files that need a look</p><ul class="ideas">${imp.map(i => `<li class="${i.ok ? 'hit' : 'miss'}"><code>${esc(i.path)}</code>: ${esc(i.msg)}</li>`).join('')}</ul>` : ''}
        <details class="about"><summary>About Mentor and adding a lesson</summary>
          <p class="coach">Each lesson breaks down real work from your projects. You learn first (an overview, the terms, worked examples, the ideas behind each bug hunt), then practise, and reviews come back when you're about to forget.</p>
          <p class="meta">Calibration: ${calText(s.calibration)}${s.labels ? ` · ${plural(s.labels, 'graded answer')} saved for the learning grader` : ''}</p><p class="meta" id="ailine">Local AI: checking…</p>
          <ol class="steps">
            <li>In Claude Code, right after building something, run <code>/mentor</code> (or <code>/mentor</code> plus a file or function name). It writes a JSON file to the project's <code>mentor_inbox</code> folder.</li>
            <li>Copy that file to <code>${esc(s.inbox || '~/.local/share/argus-ui/inbox')}</code> on the machine that runs Argus.</li>
            <li>Open this page again: the lesson shows up here and in Study.</li></ol></details>
      </div>`;
      get('ai').then(a => { const p = $('#ailine'); if (p) p.textContent = aiLine(a); }).catch(() => {});   // after the panel is drawn
      $$('[data-study]').forEach(b => b.onclick = () => { M.deck = b.dataset.study; save('mentor-deck', M.deck); fillPicker(); setView('practice'); });
      const ra = $('#reviewAll'); if (ra) ra.onclick = () => { M.deck = null; save('mentor-deck', null); fillPicker(); setView('practice'); };
      $$('[data-read]').forEach(b => b.onclick = async () => { const {card} = await get('next?card=' + encodeURIComponent(b.dataset.read)); if (card) { M.card = card; M.result = null; learnCard(card, true); } });
    });
  }

  addEventListener('keydown', e => {
    const a = document.activeElement;
    if (!ROOT) return;
    if (e.altKey && (e.key === 'h' || e.key === 'H') && M.card && !M.result && !isLearn(M.card)) { e.preventDefault(); return hint(); }
    if (!M.result || a.tagName === 'TEXTAREA' || a.tagName === 'SELECT' || (a.tagName === 'INPUT' && a.type === 'text')) return;
    if (/^[1-4]$/.test(e.key)) { const i = $$('input[name=rate]')[+e.key - 1]; if (i) { i.checked = true; i.dispatchEvent(new Event('change')); i.focus(); } }
    else if (e.key === 'Enter' && a.type === 'radio') { e.preventDefault(); $('#rateBtn').click(); }
  });
  leafy.register('mentor', {show});
})();
