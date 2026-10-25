// Mentor: learn the code you build. Lessons (teach -> drills, explain cards, terms) + plain decks,
// spaced repetition, typed answers, a hint ladder, calibration. See docs/mentor.md.
// A bundled server plugin (docs/leafy-plugin.md): Elaia loads this script and page.css on the Mentor section only.
// It is first-party code, so besides the plugin api it uses Elaia's page helpers ($, $$, esc, url, toast).
(() => {
  let ROOT = null;                            // the section's content area, from show(el)
  let FX = null;                              // Elaia's shared effects (api.fx); null on an Elaia older than 4.18
  let ARGUS = null;                           // Argus's reactions (api.argus); null on an Elaia older than 4.20
  const M = {deck: null, view: 'practice', card: null, t0: 0, result: null, shown: false, decks: [], modules: [], stats: null,
             hints: 0, reflections: [], idle: null, step: 0, notes: []};
  try { M.deck = localStorage.getItem('mentor-deck') || null; M.view = localStorage.getItem('mentor-view') === 'modules' ? 'modules' : 'practice'; } catch (e) {}
  const save = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) {} };
  const stored = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const get = async p => (await fetch(url('api/mentor/' + p), {cache: 'no-store'})).json();
  const send = async (p, body) => (await fetch(url('api/mentor/' + p), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json();
  // shown best to worst; value = FSRS rating (4 Easy ... 1 Again)
  const RATES = [[4, 'Very well', 'Quick, easy recall'], [3, 'Well enough', 'Took moderate thought'], [2, 'Not well', 'Hard to remember or explain'], [1, 'Needs work', 'Run this card again soon']];
  const CONF = [[1, 'Guessing'], [2, 'Unsure'], [3, 'Fairly sure'], [4, 'Certain']];
  const TYPES = {'pre-mortem': 'Find the bug', 'trade-off': 'Why this design', 'hci-bridge': 'Human factors link'};
  const SUMMARY = [['schematic_mental_model', 'The big picture'], ['design_rules_heuristics', "Why it's built this way"], ['hard_rules_invariants', 'Rules that must always hold'], ['hci_human_factors_bridge', 'Human factors link']];
  const LEARN = ['orientation', 'teach', 'level0', 'preread'];
  const IDLE = {drill: 45, term: 30, explain: 90, define: 60};        // seconds without a keystroke before the Hint button pulses
  const BLANK = /\{\{\s*BLANK(?:_(\d+))?\s*\}\}/g;
  const back = d => d < 1 / 24 ? `${Math.max(1, Math.round(d * 1440))} min` : d < 1 ? `${Math.round(d * 24)} hour${Math.round(d * 24) === 1 ? '' : 's'}` : `${Math.round(d)} day${Math.round(d) === 1 ? '' : 's'}`;
  const verb = v => v === 1 ? 'Run again in 10 min' : 'Save and next card';
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  const words = s => (s.match(/[A-Za-z0-9_']+/g) || []).length;
  function calText(c) { if (c == null) return 'not enough answers yet'; if (c > .15) return 'running overconfident'; if (c < -.15) return 'running underconfident'; return 'well calibrated'; }
  function when(ts) { if (!ts) return ''; const d = new Date(ts * 1000), m = (ts * 1000 - Date.now()) / 60000; return m < 60 ? `in ${Math.max(1, Math.round(m))} min` : m < 1440 ? `at ${d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}` : d.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'}); }
  // text from a lesson: paragraphs, `inline code` and ```fenced``` blocks; escaped first, so nothing in it becomes markup
  const inline = s => s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  const rich = t => esc(t).split(/```[\w-]*\n?([\s\S]*?)```/).map((part, i) => i % 2 ? `<pre class="code"><code>${part.replace(/\n$/, '')}</code></pre>`
    : part.split(/\n{2,}/).filter(p => p.trim()).map(p => `<p>${inline(p.trim()).replace(/\n/g, '<br>')}</p>`).join('')).join('');
  // where the code is: only its last part (the function), never folders or file names; the Lessons view lists the files
  const crumb = s => { const x = (s || '').split(/\s*(?:->|→|›)\s*/).filter(Boolean).pop(); return x ? `<p class="crumb"><span class="sr">Where in the code: </span><span>${inline(esc(x))}</span></p>` : ''; };
  const kindLabel = c => c.kind === 'drill' ? `Code drill · level ${c.level} of 3: ${c.level_name.toLowerCase()}` : c.kind === 'explain' ? (TYPES[(c.type || '').toLowerCase()] || 'Explain it')
    : c.kind === 'term' ? `Term${c.category ? ' · ' + c.category : ''}` : c.kind === 'teach' ? `Teach${c.category ? ' · ' + c.category : ''}` : c.kind === 'level0' ? 'Worked example · read it line by line'
    : c.kind === 'preread' ? `Before ${(TYPES[(c.type || '').toLowerCase()] || 'the explain card').toLowerCase().replace('find the bug', 'the bug hunt')}` : c.kind === 'orientation' ? 'Orientation · one screen before the cards' : '';
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
    $('#mdeck').onchange = e => { M.deck = e.target.value || null; save('mentor-deck', M.deck); if (M.view !== 'practice') setView('practice'); else next(); };
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
    M.view = v; save('mentor-view', v === 'modules' ? v : null);
    $$('.views button').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === v));
    v === 'modules' ? modulesView() : next();
  }
  async function stats() {
    const s = await get('stats' + (M.deck ? '?deck=' + encodeURIComponent(M.deck) : ''));
    M.stats = s; M.modules = s.modules || M.modules; fillPicker();
    $('#mstats').innerHTML = `${s.learn ? `<b>${s.learn}</b> to learn · ` : ''}<b>${s.due}</b> due · <b>${s.new}</b> new · <b>${s.today}</b> answered today · calibration: <b>${calText(s.calibration)}</b>${s.labels ? ` · ${plural(s.labels, 'graded answer')} saved for the learning grader` : ''}${s.sent_back ? ` · ${plural(s.sent_back, 'card')} sent back to the lesson today` : ''}`;
  }
  const clearIdle = () => { if (M.idle) clearTimeout(M.idle); M.idle = null; };

  /* ----- one card: ask ----- */
  async function next(extra) {
    if (M.view !== 'practice') return;
    clearIdle(); stats();
    const seq = M.seq = (M.seq || 0) + 1;         // two quick picker changes: only the last request may draw
    const r = await get('next?' + (M.deck ? 'deck=' + encodeURIComponent(M.deck) + '&' : '') + (extra ? 'extra=1' : ''));
    if (seq !== M.seq || M.view !== 'practice') return;
    M.card = r.card; M.result = null; M.hints = 0; M.reflections = []; M.step = 0; M.notes = [];
    if (!M.card) {
      $('#mpanel').innerHTML = `<div class="panel"><h3>All caught up</h3><p class="coach">Nothing is due here${r.next_due ? `; the next card comes back ${when(r.next_due)}` : ''}. Spacing reviews out is what makes them stick, so stopping here is a good choice.</p>
        <div class="row"><button type="button" id="ahead">Practice ahead</button><button type="button" id="toMods">See lessons</button></div></div>`;
      $('#ahead').onclick = () => next(true); $('#toMods').onclick = () => setView('modules'); return;
    }
    const c = M.card;
    if (isLearn(c)) return learnCard(c);
    const mod = moduleOf(c.deck), big = mod && mod.summary && mod.summary.schematic_mental_model;
    const head = `<p class="deckname">${esc(sourceName(c))}${c.reps ? '' : ' · new card'}</p>
      <p class="kind">${esc(kindLabel(c))}</p>${crumb(c.breadcrumb)}
      ${big && c.kind !== 'term' ? `<details class="big"><summary>Show the big picture of this lesson</summary>${rich(big)}</details>` : ''}`;
    const conf = `<fieldset><legend>How sure are you?</legend><div class="seg">${CONF.map(([v, n]) => `<label><input type="radio" name="conf" value="${v}">${n}</label>`).join('')}</div></fieldset>`;
    const go = `<div class="row"><button type="submit" class="primary" id="checkBtn">Check answer</button><button type="button" id="hintBtn" aria-describedby="hinthelp">Show a hint</button></div>
      <p class="help" id="hinthelp">A hint lowers the rating Mentor suggests; the answer counts as a blank. <kbd>Alt</kbd>+<kbd>H</kbd> opens the next hint.</p><div id="hints" aria-live="polite"></div>`;
    let body;
    if (c.kind === 'drill' && c.level < 3) {
      const nums = [...new Set([...c.code.matchAll(BLANK)].map(m => +(m[1] || 1)))].sort((a, b) => a - b), done = new Set();
      const code = esc(c.code).replace(BLANK, (m, n) => { n = +(n || 1); if (done.has(n)) return `<span class="ghost">blank ${n}</span>`; done.add(n);
        const w = c.widths[nums.indexOf(n)] || 6; return `<input class="blank" data-n="${n}" aria-label="Blank ${n} of ${nums.length}" style="width:${Math.min(w, 60) + 2}ch" autocomplete="off" autocapitalize="off" spellcheck="false">`; });
      body = `<h3 id="qprompt">${inline(esc(c.context || c.prompt))}</h3>
        <pre class="code fill"><code>${code}</code></pre>
        <p class="help">Type the missing code in each box. <kbd>Enter</kbd> moves to the next box; <kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p>`;
    } else if (c.kind === 'drill') {
      const code = esc(c.code).replace(BLANK, '<span class="slot">your code goes here</span>');
      body = `<h3 id="qprompt">${inline(esc(c.context || c.prompt))}</h3>
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
    $('#hints').insertAdjacentHTML('beforeend', `<div class="hint" id="rung${r.rung}"><p class="deckname">Hint ${r.rung} of 4 · ${esc(r.name)}</p><div class="model">${rich(r.text)}</div>
      ${last ? '' : `<label for="refl${r.rung}">What did that tell you?</label><textarea id="refl${r.rung}" rows="2" maxlength="300" placeholder="Three words or more"></textarea>`}</div>`);
    const hb = $('#hintBtn'), cb = $('#checkBtn');
    if (last) { hb.disabled = true; cb.textContent = 'Rate it'; $$('#qform input.blank, #qform textarea#ans').forEach(i => i.disabled = true); cb.focus(); }
    else { hb.textContent = r.next === 4 ? 'Show the answer' : 'Next hint'; $(`#refl${r.rung}`).focus(); }
  }

  /* ----- one card: check and give feedback ----- */
  async function check() {
    const c = M.card, boxes = $$('#qform input.blank'), ta = $('#qform textarea#ans');
    const text = M.hints === 4 ? '' : c.kind === 'drill' && c.level < 3 ? JSON.stringify([...boxes].sort((a, b) => a.dataset.n - b.dataset.n).map(b => b.value))
      : c.kind === 'drill' ? ta.value.replace(/\s+$/, '') : (ta || boxes[0]).value.trim();
    const open = $('#hints .hint:not(.offer):last-child textarea'); if (open && !open.disabled) M.reflections.push(open.value.trim().slice(0, 300));
    const conf = +($('input[name=conf]:checked')?.value || 0) || null;
    const btn = $('#checkBtn'); btn.disabled = true; clearIdle();
    let r; try { r = await send('answer', {card: c.id, text, confidence: conf, ms: Math.round(performance.now() - M.t0), hints: M.hints, reflections: M.reflections}); } catch (e) { r = {ok: false}; }
    if (!r.ok) { btn.disabled = false; return toast("Couldn't reach Mentor to check that answer. Check that the server is on, then try again."); }
    M.result = r; M.grade_wrong = false;
    const n = r.hits.length + r.missed.length, pct = Math.round(r.coverage * 100);
    let head, detail;
    if (c.kind === 'drill' && c.level < 3) {
      head = M.hints === 4 ? 'The answer was shown' : `${r.hits.length} of ${plural(n, 'blank')} right`;
      detail = `<ul class="ideas">${r.blanks.map(b => b.ok ? `<li class="hit">Blank ${b.n}: <code>${esc(b.expected)}</code></li>`
          : `<li class="miss">Blank ${b.n}: ${b.typed && b.typed.trim() ? `you wrote <code>${esc(b.typed)}</code>, ` : ''}the code has <code>${esc(b.expected)}</code></li>`).join('')}</ul>
        <p class="deckname">The full code</p><pre class="code"><code>${esc(r.canonical)}</code></pre>`;
    } else if (c.kind === 'drill') {
      head = M.hints === 4 ? 'The answer was shown' : r.same_structure ? 'Same structure as the model answer' : r.problem ? "Python can't read your version yet" : `${pct}% like the model answer`;
      detail = `${r.problem ? `<p class="coach">Python says: <code>${esc(r.problem)}</code></p>` : ''}
        <div class="pair"><div><p class="deckname">Your version</p><pre class="code"><code>${esc(r.yours)}</code></pre></div>
        <div><p class="deckname">Model answer</p><pre class="code"><code>${esc(r.canonical)}</code></pre></div></div>`;
    } else if (c.kind === 'term') {
      const typed = text;
      head = M.hints === 4 ? `The answer was shown: “${esc(r.reference)}”` : r.coverage >= .99 ? esc(r.reference) : r.coverage > 0 ? `Close: it's “${esc(r.reference)}”` : `It's “${esc(r.reference)}”`;
      detail = `${typed && r.coverage < .99 ? `<p class="coach">You wrote “${esc(typed)}”.</p>` : ''}
        <dl class="defs">${r.definition ? `<dt>What it does</dt><dd>${inline(esc(r.definition))}</dd>` : ''}${r.anchor ? `<dt>In your code</dt><dd>${inline(esc(r.anchor))}</dd>` : ''}${r.contrast ? `<dt>Not to be confused with</dt><dd>${inline(esc(r.contrast))}</dd>` : ''}</dl>`;
    } else {
      head = M.hints === 4 ? 'The answer was shown' : `${r.hits.length} of ${plural(n, 'key idea')}`;
      detail = `${text ? `<p class="deckname">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}
        <ul class="ideas">${r.hits.map(h => `<li class="hit">${esc(h)}</li>`).join('')}${r.missed.map(h => `<li class="miss">Missing: ${esc(h)}</li>`).join('')}</ul>
        <p class="deckname">Model answer</p><div class="model">${rich(r.reference)}</div>`;
    }
    const note = r.note ? `<p class="deckname">Why it's written this way</p><div class="model">${rich(r.note)}</div>` : '';
    const stuck = r.stuck === 'repeat' ? `<p class="coach back"><b>Twice in a row.</b> ${esc(r.move)} The lesson's card for this comes back before the next try.</p>`
      : r.stuck === 'skipped' ? `<p class="coach back"><b>You skipped the lesson card for this one.</b> It comes back before the next try.</p>` : '';
    const lvl = v => r.level_after && r.level_after[v] !== r.level ? ` · level ${r.level_after[v]}` : '';
    $('#mpanel').innerHTML = `<div class="panel" id="rpanel">
      <p class="deckname">${esc(sourceName(c))} · ${esc(kindLabel(c))}${M.hints ? ` · ${plural(M.hints, 'hint')} used` : ''}</p>
      <h3 tabindex="-1" id="rhead">${head}</h3>
      <div class="meter" role="img" aria-label="${pct}% right"><span style="transform:scaleX(${r.coverage})"></span></div>
      ${detail}${note}
      <p class="coach"><b>Mentor:</b> ${esc(r.coach)}</p>${stuck}
      <fieldset><legend>How well did you know it?</legend>
        <div class="seg rates">${RATES.map(([v, nm, d], i) => `<label><input type="radio" name="rate" value="${v}" ${v === r.suggested ? 'checked' : ''}><span><b>${i + 1}. ${nm}</b><small>${d}</small><small class="when">Back in ${back(r.previews[v])}${lvl(v)}</small>${v === r.suggested ? '<em class="tag">Mentor suggests</em>' : ''}</span></label>`).join('')}</div>
        <p class="help">Mentor's suggestion comes from what you got right${M.hints ? ' and the hints you used' : ''}; pick what feels true. Keys <kbd>1</kbd>–<kbd>4</kbd> choose, <kbd>Enter</kbd> confirms.</p></fieldset>
      <div class="row" style="margin-bottom:var(--s3)"><button type="button" class="primary" id="rateBtn">${verb(r.suggested)}</button></div>
      <label class="check"><input type="checkbox" id="gw"> Mentor's grade was wrong (your answer was better or worse than it scored)</label></div>`;
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
    const lv = s.level_change > 0 ? ` Level ${s.level} next time: ${s.level === 3 ? "you'll write the whole body" : 'the logic is blanked'}.` : s.level_change < 0 ? ` Back to level ${s.level} for now.` : '';
    toast(s.held ? `Held for a day${s.back ? ', and the lesson card for it comes back first' : ''}.` : (v === 1 ? 'Coming back in 10 minutes for another try.' : `Saved. Next review in ${back(s.days)}.`) + lv);
    next();
  }

  /* ----- Learn cards: orientation, teach (+ spot it), level 0 worked example, pre-read ----- */
  function learnCard(c, readOnly) {
    const g = M.guess && M.guess.id === c.id ? M.guess : null; M.guess = null;
    const head = `<p class="deckname">${esc(sourceName(c))}${c.refresh ? ' · back to the lesson' : readOnly ? ' · reading again' : ' · learn'}</p><p class="kind">${esc(kindLabel(c))}</p>${crumb(c.breadcrumb)}`;
    const skip = !readOnly && (c.kind === 'teach' || c.kind === 'level0') ? `<button type="button" id="skipBtn">I know this, test me</button>` : '';
    const done = readOnly ? `<button type="button" class="primary" id="doneBtn">Back to lessons</button>` : '';
    if (c.try && !readOnly && !g) return tryFirst(c, head, skip);
    // the try-first question stays above the explanation: with the guess beside it, or as plain text when reading again
    const tried = c.try ? `<div class="callout tried"><b>Try first: ${inline(esc(c.try))}</b>${g ? `<p>Your guess: ${esc(g.text)}</p>` : ''}</div>` : '';
    let body, go;
    if (c.kind === 'orientation') {
      body = `<h3>${esc(c.module || 'This lesson')}</h3><div class="prompt">${rich(c.prompt)}</div>
        ${c.terms && c.terms.length ? `<p class="deckname">Terms you'll meet</p><ul class="tags" aria-label="Terms">${c.terms.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
        ${c.bridge ? `<p class="deckname">Why this lesson</p><div class="model">${rich(c.bridge)}</div>` : ''}
        ${readOnly ? '' : `<div class="field"><label for="ans">In my words, this code…</label><textarea id="ans" rows="2" aria-describedby="anshelp"></textarea><p class="help" id="anshelp">Five words or more, then <kbd>Ctrl</kbd>+<kbd>Enter</kbd>.</p></div>`}`;
      go = readOnly ? done : `<button type="submit" class="primary" id="goBtn" disabled>Start learning</button>`;
    } else if (c.kind === 'teach') {
      const lines = c.spot ? c.spot.snippet.split('\n') : [];
      body = `<h3>${esc(c.prompt)}</h3>${tried}
        <dl class="defs">${c.definition ? `<dt>What it does</dt><dd>${inline(esc(c.definition))}</dd>` : ''}${c.anchor ? `<dt>In your code</dt><dd>${inline(esc(c.anchor))}</dd>` : ''}${c.contrast ? `<dt>Not to be confused with</dt><dd>${inline(esc(c.contrast))}</dd>` : ''}${c.move ? `<dt>What an expert looks for</dt><dd>${inline(esc(c.move))}</dd>` : ''}</dl>
        ${c.spot ? `<p class="deckname" id="spotq">Spot it: ${readOnly ? `line ${c.spot.line}` : 'pick the line that uses it'}</p>
          <ol class="lines" aria-labelledby="spotq">${lines.map((l, i) => `<li><button type="button" class="line${readOnly && i + 1 === c.spot.line ? ' is' : ''}" data-line="${i + 1}" ${readOnly ? 'disabled' : ''}><span class="n">${i + 1}</span><code>${esc(l) || ' '}</code></button></li>`).join('')}</ol>
          ${readOnly ? `<p class="coach">${esc(c.spot.why)}</p>` : `<p class="help"><kbd>↑</kbd>/<kbd>↓</kbd> move, <kbd>Enter</kbd> picks; or type the line number: <input class="blank" id="lineNo" inputmode="numeric" aria-label="Line number" style="width:4ch"></p>`}` : ''}`;
      go = readOnly ? done : c.spot ? `<button type="submit" class="primary" id="goBtn" disabled>That's the line</button>${skip}` : `<button type="submit" class="primary" id="goBtn">Got it, next</button>${skip}`;
    } else if (c.kind === 'level0') {
      const lines = c.code.split('\n'), ann = c.annotations || [];
      body = `<h3 id="qprompt">${inline(esc(c.context || 'Read the code, one line at a time'))}</h3>
        <pre class="code worked" id="worked"><code>${lines.map((l, i) => `<span class="ln" data-line="${i + 1}">${esc(l) || ' '}</span>`).join('\n')}</code></pre>
        <div id="annot"></div>
        <p class="help" id="annhelp">${readOnly ? 'Every note is shown.' : `Annotation <span id="step">1</span> of ${ann.length}. Say why the line is there (three words or more), then <kbd>Enter</kbd> shows the note.`}</p>`;
      go = readOnly ? done : `<button type="button" class="primary" id="goBtn" disabled>Reveal</button>${skip}`;
    } else {          // preread
      body = `<h3>Before you hunt the bug: the ideas it rests on</h3>${tried}
        <ol class="ideas keys">${(c.ideas || []).map(i => `<li>${inline(esc(i))}</li>`).join('')}</ol>
        ${c.near ? `<p class="deckname">A near example</p><pre class="code"><code>${esc(c.near.code)}</code></pre>
          ${readOnly ? `<p class="coach"><b>${esc(c.near.ask)}</b> ${esc(c.near.answer || '')}</p>`
          : `<div class="field"><label for="ans">${esc(c.near.ask)}</label><input id="ans" class="blank wide" autocomplete="off"><p class="help"><kbd>Enter</kbd> reveals the answer.</p></div>`}` : ''}`;
      go = readOnly ? done : `<button type="submit" class="primary" id="goBtn">${c.near ? 'Reveal' : 'Got it, next'}</button>`;
    }
    $('#mpanel').innerHTML = `<form class="panel learn" id="qform" novalidate>${head}${body}<div class="row">${go}</div></form>`;
    M.t0 = performance.now();
    if (readOnly) { $('#doneBtn').onclick = () => setView('modules'); if (c.kind === 'level0') revealAll(c); return; }
    wireLearn(c);
  }
  // a question to answer before the explanation (pretesting): typed, never graded or sent, then the card itself
  function tryFirst(c, head, skip) {
    $('#mpanel').innerHTML = `<form class="panel learn" id="qform" novalidate>${head}<h3>${c.kind === 'teach' ? esc(c.prompt) : 'Before the ideas: try this first'}</h3>
      <div class="field"><label for="guess">Try first: ${inline(esc(c.try))}</label><textarea id="guess" rows="2" aria-describedby="guesshelp"></textarea>
      <p class="help" id="guesshelp">A guess is fine: it isn't graded. <kbd>Ctrl</kbd>+<kbd>Enter</kbd> shows the explanation.</p></div>
      <div class="row"><button type="submit" class="primary" id="tryBtn" disabled>Show the explanation</button>${skip}</div></form>`;
    M.t0 = performance.now();
    const form = $('#qform'), ta = $('#guess'), go = $('#tryBtn'), sk = $('#skipBtn');
    ta.oninput = () => go.disabled = words(ta.value) < 1; ta.focus();
    form.onsubmit = e => { e.preventDefault(); if (go.disabled) return; M.guess = {id: c.id, text: ta.value.trim()}; learnCard(c); };
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
      const ta = $('#ans'); ta.oninput = () => go.disabled = words(ta.value) < 5; ta.focus();
      form.onsubmit = e => { e.preventDefault(); if (!go.disabled) finish(ta.value.trim()); };
      form.onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); } };
    } else if (c.kind === 'teach') {
      if (!c.spot) { form.onsubmit = e => { e.preventDefault(); finish(''); }; go.focus(); return; }
      const lines = $$('.lines .line'), no = $('#lineNo');
      let picked = 0;
      const pick = n => { picked = n; lines.forEach(b => b.classList.toggle('is', +b.dataset.line === n)); no.value = n || ''; go.disabled = !n; };
      lines.forEach(b => { b.onclick = () => pick(+b.dataset.line); b.onkeydown = e => { const i = +b.dataset.line; if (e.key === 'ArrowDown' && lines[i]) { e.preventDefault(); lines[i].focus(); } if (e.key === 'ArrowUp' && lines[i - 2]) { e.preventDefault(); lines[i - 2].focus(); } }; });
      no.oninput = () => { const n = +no.value; pick(n >= 1 && n <= lines.length ? n : 0); };
      form.onsubmit = e => { e.preventDefault(); if (picked) finish(String(picked)); };
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
      const ta = $(`#why${k}`); if (ta && !ta.disabled) { M.notes.push(ta.value.trim().slice(0, 120)); ta.disabled = true; $(`#call${k}`).insertAdjacentHTML('beforeend', `<p>${inline(esc(ann[k].why))}</p>`); go.textContent = k + 1 < ann.length ? 'Next annotation' : 'Explain it'; go.disabled = false; return go.focus(); }
      if (k + 1 < ann.length) M.step++;
      else return selfExplain(c, go);
    }
    const a = ann[M.step];
    $$('#worked .ln').forEach(l => l.classList.toggle('hi', +l.dataset.line === a.line));
    const line = $(`#worked .ln[data-line="${a.line}"]`); if (line) line.scrollIntoView({block: 'nearest'});
    box.insertAdjacentHTML('beforeend', `<div class="callout" id="call${M.step}"><b>${M.step + 1}. Line ${a.line}${a.note ? ': ' + inline(esc(a.note)) : ''}</b>
      <label for="why${M.step}">Why is this line here?</label><input id="why${M.step}" class="blank wide" autocomplete="off" maxlength="120"></div>`);
    $('#step').textContent = M.step + 1;
    const ta = $(`#why${M.step}`); ta.focus(); go.textContent = 'Reveal'; go.disabled = true;
    ta.oninput = () => go.disabled = words(ta.value) < 3;
    ta.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); if (!go.disabled) go.click(); } };
  }
  function selfExplain(c, go) {
    $('#annot').insertAdjacentHTML('beforeend', `<div class="callout ask"><label for="ans">${inline(esc(c.prompt))}</label><textarea id="ans" rows="3"></textarea><p class="help"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.</p></div>`);
    $('#annhelp').textContent = 'Last step: explain it in your own words.';
    const ta = $('#ans'); ta.focus(); go.textContent = 'Check'; go.disabled = true;
    ta.oninput = () => go.disabled = words(ta.value) < 3;
    const finish = async () => {
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
    if (c.kind === 'teach') {
      head = r.spot_ok ? `Line ${r.line}: that's it` : `It's on line ${r.line}`;
      const lines = c.spot.snippet.split('\n');
      detail = `<ol class="lines">${lines.map((l, i) => `<li><span class="line${i + 1 === r.line ? ' is' : ''}"><span class="n">${i + 1}</span><code>${esc(l) || ' '}</code></span></li>`).join('')}</ol>`;
    } else if (c.kind === 'level0') {
      const n = r.hits.length + r.missed.length;
      head = n ? (r.coverage >= .99 ? `All ${plural(n, 'key idea')}` : `${r.hits.length} of ${plural(n, 'key idea')}`) : 'Explained';
      detail = `${text ? `<p class="deckname">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}
        ${n ? `<ul class="ideas">${r.hits.map(h => `<li class="hit">${esc(h)}</li>`).join('')}${r.missed.map(h => `<li class="miss">Missing: ${esc(h)}</li>`).join('')}</ul>` : ''}`;
    } else {
      head = c.near ? c.near.ask : 'Read';
      detail = `${text ? `<p class="deckname">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}${r.answer ? `<p class="deckname">Answer</p><div class="model">${rich(r.answer)}</div>` : ''}`;
    }
    $('#mpanel').innerHTML = `<div class="panel learn" id="rpanel"><p class="deckname">${esc(sourceName(c))} · ${esc(kindLabel(c))}</p>
      <h3 tabindex="-1" id="rhead">${esc(head)}</h3>${detail}<p class="coach"><b>Mentor:</b> ${esc(r.coach)}</p>
      <div class="row"><button type="button" class="primary" id="rateBtn">Next card</button></div></div>`;
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
  function modulesView() {
    stats().then(() => {
      const s = M.stats, mods = M.modules;
      const prog = m => [['term', 'Terms'], ['drill', 'Drills'], ['explain', 'Explain cards']].filter(([k]) => m.cards[k]).map(([k, n]) =>
        `${n} ${m.cards[k].seen}/${m.cards[k].n}${k === 'drill' && m.cards[k].seen ? ` (${m.cards[k].top} at level 3)` : ''}`).join(' · ');
      const imp = (s.imports || []).filter(i => !i.ok || i.msg.includes('skipped'));
      const lint = m => (m.summary.lint || []).length ? `<p class="meta">The <code>/mentor</code> command noted: ${m.summary.lint.map(esc).join('; ')}</p>` : '';
      $('#mpanel').innerHTML = `<div class="panel modules">
        <h3>Lessons</h3><p class="meta" id="ailine">Local AI: checking…</p>
        <p class="coach">Each lesson breaks down real code from your projects: the big picture, the rules behind it, and cards in three tiers. You learn first (orientation, terms, a worked example, the ideas behind each bug hunt), then practise: terms, code drills, explain cards.</p>
        ${mods.length ? mods.map(m => `<article class="module" aria-labelledby="mh-${esc(m.id)}">
            <h4 id="mh-${esc(m.id)}">${esc(m.name)}</h4>
            <p class="meta">${[m.project, m.built_in ? 'comes with Argus' : new Date(m.at * 1000).toLocaleDateString([], {month: 'short', day: 'numeric', year: 'numeric'}), m.files.join(', ')].filter(Boolean).map(esc).join(' · ')}</p>
            <p class="meta">${m.to_learn ? `${m.to_learn} to learn · ` : ''}${esc(prog(m))}</p>${lint(m)}
            ${SUMMARY.some(([k]) => m.summary[k]) ? `<details><summary>Read the breakdown</summary><dl class="defs">${SUMMARY.filter(([k]) => m.summary[k]).map(([k, n]) => `<dt>${n}</dt><dd>${rich(m.summary[k])}</dd>`).join('')}</dl></details>` : ''}
            ${m.learn.length ? `<details><summary>Read the lesson again</summary><ul class="learnlist">${m.learn.map(l => `<li><button type="button" data-read="${esc(l.id)}"><span>${esc(l.title)}</span><small>${l.seen ? 'read' : 'not yet'}</small></button></li>`).join('')}</ul></details>` : ''}
            ${m.concepts.length ? `<ul class="tags" aria-label="Concepts">${m.concepts.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
            <div class="row"><button type="button" data-study="${esc(m.id)}">Study this lesson</button></div></article>`).join('')
          : `<div class="empty"><b>No lessons yet</b>Add one with the steps below.</div>`}
        <h3 class="addh">Add a lesson</h3>
        <ol class="steps">
          <li>In Claude Code, right after building something, run <code>/mentor</code> (or <code>/mentor</code> plus a file or function name). It writes a JSON file to the project's <code>mentor_inbox</code> folder.</li>
          <li>Copy that file to <code>${esc(s.inbox || '~/.local/share/argus-ui/inbox')}</code> on the machine that runs Argus.</li>
          <li>Open this page again: the lesson shows up here and in Study.</li></ol>
        ${imp.length ? `<p class="deckname">Inbox files that need a look</p><ul class="ideas">${imp.map(i => `<li class="${i.ok ? 'hit' : 'miss'}"><code>${esc(i.path)}</code>: ${esc(i.msg)}</li>`).join('')}</ul>` : ''}
      </div>`;
      get('ai').then(a => { const p = $('#ailine'); if (p) p.textContent = aiLine(a); }).catch(() => {});   // after the panel is drawn
      $$('[data-study]').forEach(b => b.onclick = () => { M.deck = b.dataset.study; save('mentor-deck', M.deck); fillPicker(); setView('practice'); });
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
