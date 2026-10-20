// Argus UI - Mentor: learn the code you build. Code modules (drills, explain cards, terms) + plain decks,
// spaced repetition, typed answers, calibration. See docs/mentor.md.
/* Mentor's own styles (css/mentor.css), added from here so the page's markup stays as it is */
(() => { const s = document.currentScript; if (!s) return; const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = s.src.replace('/js/mentor.js', '/css/mentor.css'); document.head.appendChild(l); })();

/* ---------- Mentor: the Practice page ---------- */
const practice = (() => {
  const M = {deck: null, view: 'practice', card: null, t0: 0, result: null, shown: false, decks: [], modules: [], stats: null};
  try { M.deck = localStorage.getItem('mentor-deck') || null; M.view = localStorage.getItem('mentor-view') === 'modules' ? 'modules' : 'practice'; } catch (e) {}
  const save = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) {} };
  const get = async p => (await fetch(url('api/mentor/' + p), {cache: 'no-store'})).json();
  const send = async (p, body) => (await fetch(url('api/mentor/' + p), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json();
  // shown best to worst; value = FSRS rating (4 Easy ... 1 Again)
  const RATES = [[4, 'Very well', 'Quick, easy recall'], [3, 'Well enough', 'Took moderate thought'], [2, 'Not well', 'Hard to remember or explain'], [1, 'Needs work', 'Run this card again soon']];
  const CONF = [[1, 'Guessing'], [2, 'Unsure'], [3, 'Fairly sure'], [4, 'Certain']];
  const TYPES = {'pre-mortem': 'Find the bug', 'trade-off': 'Why this design', 'hci-bridge': 'Human factors link'};
  const SUMMARY = [['schematic_mental_model', 'The big picture'], ['design_rules_heuristics', "Why it's built this way"], ['hard_rules_invariants', 'Rules that must always hold'], ['hci_human_factors_bridge', 'Human factors link']];
  const BLANK = /\{\{\s*BLANK(?:_(\d+))?\s*\}\}/g;
  const back = d => d < 1 / 24 ? `${Math.max(1, Math.round(d * 1440))} min` : d < 1 ? `${Math.round(d * 24)} hour${Math.round(d * 24) === 1 ? '' : 's'}` : `${Math.round(d)} day${Math.round(d) === 1 ? '' : 's'}`;
  const verb = v => v === 1 ? 'Run again in 10 min' : 'Save and next card';
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  function calText(c) { if (c == null) return 'not enough answers yet'; if (c > .15) return 'running overconfident'; if (c < -.15) return 'running underconfident'; return 'well calibrated'; }
  function when(ts) { if (!ts) return ''; const d = new Date(ts * 1000), m = (ts * 1000 - Date.now()) / 60000; return m < 60 ? `in ${Math.max(1, Math.round(m))} min` : m < 1440 ? `at ${d.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}` : d.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'}); }
  // text from a module: paragraphs, `inline code` and ```fenced``` blocks; escaped first, so nothing in it becomes markup
  const inline = s => s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  const rich = t => esc(t).split(/```[\w-]*\n?([\s\S]*?)```/).map((part, i) => i % 2 ? `<pre class="code"><code>${part.replace(/\n$/, '')}</code></pre>`
    : part.split(/\n{2,}/).filter(p => p.trim()).map(p => `<p>${inline(p.trim()).replace(/\n/g, '<br>')}</p>`).join('')).join('');
  const crumb = s => s ? `<p class="crumb"><span class="sr">Where in the code: </span>${s.split(/\s*(?:->|→|›)\s*/).map(x => `<span>${inline(esc(x))}</span>`).join('<span aria-hidden="true"> › </span>')}</p>` : '';
  const kindLabel = c => c.kind === 'drill' ? `Code drill · level ${c.level} of 3: ${c.level_name.toLowerCase()}` : c.kind === 'explain' ? (TYPES[(c.type || '').toLowerCase()] || 'Explain it') : c.kind === 'term' ? `Term${c.category ? ' · ' + c.category : ''}` : '';
  const sourceName = c => c.module || (M.decks.find(d => d.id === c.deck) || {}).name || c.deck;
  const moduleOf = id => M.modules.find(m => m.id === id);

  async function show() {
    if (M.shown) return; M.shown = true;      // refresh() re-renders agent pages; Practice keeps its own state
    const [{decks}, s] = await Promise.all([get('decks'), get('stats')]);
    M.decks = decks; M.stats = s; M.modules = s.modules || [];
    if (M.deck && !decks.some(d => d.id === M.deck) && !moduleOf(M.deck)) M.deck = null;
    $('#main').innerHTML = `<section class="persona practice mentor" aria-label="Mentor">
      <div class="mbar"><div class="views" role="group" aria-label="View">
          <button type="button" data-view="practice" aria-pressed="${M.view === 'practice'}">Practice</button>
          <button type="button" data-view="modules" aria-pressed="${M.view === 'modules'}">Code modules</button></div>
        <div class="pick"><label for="mdeck">Study</label><select id="mdeck"></select></div></div>
      <p class="mstats" id="mstats" aria-live="polite"></p><div id="mpanel"></div></section>`;
    fillPicker();
    $('#mdeck').onchange = e => { M.deck = e.target.value || null; save('mentor-deck', M.deck); if (M.view !== 'practice') setView('practice'); else next(); };
    $$('.views button').forEach(b => b.onclick = () => setView(b.dataset.view));
    setView(M.view);
  }
  function fillPicker() {
    const opt = (id, n) => `<option value="${esc(id)}" ${(M.deck || '') === id ? 'selected' : ''}>${esc(n)}</option>`;
    $('#mdeck').innerHTML = opt('', 'Everything, mixed') +
      (M.modules.length ? `<optgroup label="Code modules">${M.modules.map(m => opt(m.id, (m.project ? m.project + ': ' : '') + m.name)).join('')}</optgroup>` : '') +
      (M.decks.length ? `<optgroup label="Decks">${M.decks.map(d => opt(d.id, d.name)).join('')}</optgroup>` : '');
  }
  function setView(v) {
    M.view = v; save('mentor-view', v === 'modules' ? v : null);
    $$('.views button').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === v));
    v === 'modules' ? modulesView() : next();
  }
  async function stats() {
    const s = await get('stats' + (M.deck ? '?deck=' + encodeURIComponent(M.deck) : ''));
    M.stats = s; if (s.modules && s.modules.length !== M.modules.length) { M.modules = s.modules; fillPicker(); } else M.modules = s.modules || M.modules;
    $('#mstats').innerHTML = `<b>${s.due}</b> due · <b>${s.new}</b> new · <b>${s.today}</b> answered today · calibration: <b>${calText(s.calibration)}</b>${s.labels ? ` · ${plural(s.labels, 'graded answer')} saved for the learning grader` : ''}`;
  }

  /* ----- one card: ask ----- */
  async function next(extra) {
    if (M.view !== 'practice') return;
    stats();
    const r = await get('next?' + (M.deck ? 'deck=' + encodeURIComponent(M.deck) + '&' : '') + (extra ? 'extra=1' : ''));
    M.card = r.card; M.result = null;
    if (!M.card) {
      $('#mpanel').innerHTML = `<div class="panel"><h3>All caught up</h3><p class="coach">Nothing is due here${r.next_due ? `; the next card comes back ${when(r.next_due)}` : ''}. Spacing reviews out is what makes them stick, so stopping here is a good choice.</p>
        <div class="row"><button type="button" id="ahead">Practice ahead</button><button type="button" id="toMods">See code modules</button></div></div>`;
      $('#ahead').onclick = () => next(true); $('#toMods').onclick = () => setView('modules'); return;
    }
    const c = M.card, mod = moduleOf(c.deck), big = mod && mod.summary && mod.summary.schematic_mental_model;
    const head = `<p class="deckname">${esc(sourceName(c))}${c.reps ? '' : ' · new card'}</p>
      <p class="kind">${esc(kindLabel(c))}</p>${crumb(c.breadcrumb)}
      ${big && c.kind !== 'term' ? `<details class="big"><summary>Show the big picture of this module</summary>${rich(big)}</details>` : ''}`;
    const conf = `<fieldset><legend>How sure are you?</legend><div class="seg">${CONF.map(([v, n]) => `<label><input type="radio" name="conf" value="${v}">${n}</label>`).join('')}</div></fieldset>`;
    const go = `<div class="row"><button type="submit" class="primary" id="checkBtn">Check answer</button></div>`;
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
    const btn = $('#checkBtn'), form = $('#qform'), boxes = $$('#qform input.blank'), ta = $('#qform textarea');
    const typed = () => boxes.some(b => b.value.trim()) || (ta && ta.value.trim());
    const label = () => btn.textContent = typed() ? 'Check answer' : 'Show answer';
    form.oninput = label; label();
    (boxes[0] || ta).focus();
    form.onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); } };
    boxes.forEach((b, i) => b.onkeydown = e => { if (e.key !== 'Enter' || e.ctrlKey || e.metaKey) return; e.preventDefault(); boxes[i + 1] ? boxes[i + 1].focus() : form.requestSubmit(); });
    if (ta && ta.classList.contains('codein')) ta.onkeydown = e => {   // keep the indent; one level deeper after a colon
      if (e.key !== 'Enter' || e.ctrlKey || e.metaKey || e.shiftKey) return;
      e.preventDefault();
      const line = ta.value.slice(0, ta.selectionStart).split('\n').pop(), ind = line.match(/^ */)[0] + (/:\s*$/.test(line) ? '    ' : '');
      ta.setRangeText('\n' + ind, ta.selectionStart, ta.selectionEnd, 'end'); label();
    };
    form.onsubmit = e => { e.preventDefault(); check(); };
  }

  /* ----- one card: check and give feedback ----- */
  async function check() {
    const c = M.card, boxes = $$('#qform input.blank'), ta = $('#qform textarea');
    const text = c.kind === 'drill' && c.level < 3 ? JSON.stringify([...boxes].sort((a, b) => a.dataset.n - b.dataset.n).map(b => b.value))
      : c.kind === 'drill' ? ta.value.replace(/\s+$/, '') : (ta || boxes[0]).value.trim();
    const conf = +($('input[name=conf]:checked')?.value || 0) || null;
    const btn = $('#checkBtn'); btn.disabled = true;
    let r; try { r = await send('answer', {card: c.id, text, confidence: conf, ms: Math.round(performance.now() - M.t0)}); } catch (e) { r = {ok: false}; }
    if (!r.ok) { btn.disabled = false; return toast("Couldn't reach Mentor to check that answer. Check that the server is on, then try again."); }
    M.result = r; M.grade_wrong = false;
    const n = r.hits.length + r.missed.length, pct = Math.round(r.coverage * 100);
    let head, detail;
    if (c.kind === 'drill' && c.level < 3) {
      head = `${r.hits.length} of ${plural(n, 'blank')} right`;
      detail = `<ul class="ideas">${r.blanks.map(b => b.ok ? `<li class="hit">Blank ${b.n}: <code>${esc(b.expected)}</code></li>`
          : `<li class="miss">Blank ${b.n}: ${b.typed && b.typed.trim() ? `you wrote <code>${esc(b.typed)}</code>, ` : ''}the code has <code>${esc(b.expected)}</code></li>`).join('')}</ul>
        <p class="deckname">The full code</p><pre class="code"><code>${esc(r.canonical)}</code></pre>`;
    } else if (c.kind === 'drill') {
      head = r.same_structure ? 'Same structure as the model answer' : r.problem ? "Python can't read your version yet" : `${pct}% like the model answer`;
      detail = `${r.problem ? `<p class="coach">Python says: <code>${esc(r.problem)}</code></p>` : ''}
        <div class="pair"><div><p class="deckname">Your version</p><pre class="code"><code>${esc(r.yours)}</code></pre></div>
        <div><p class="deckname">Model answer</p><pre class="code"><code>${esc(r.canonical)}</code></pre></div></div>`;
    } else if (c.kind === 'term') {
      const typed = $('#ans').value.trim();
      head = r.coverage >= .99 ? esc(r.reference) : r.coverage > 0 ? `Close: it's “${esc(r.reference)}”` : `It's “${esc(r.reference)}”`;
      detail = `${typed && r.coverage < .99 ? `<p class="coach">You wrote “${esc(typed)}”.</p>` : ''}
        <dl class="defs">${r.definition ? `<dt>What it does</dt><dd>${inline(esc(r.definition))}</dd>` : ''}${r.anchor ? `<dt>In your code</dt><dd>${inline(esc(r.anchor))}</dd>` : ''}${r.contrast ? `<dt>Not to be confused with</dt><dd>${inline(esc(r.contrast))}</dd>` : ''}</dl>`;
    } else {
      head = `${r.hits.length} of ${plural(n, 'key idea')}`;
      detail = `${text ? `<p class="deckname">You wrote</p><p class="model mine">${esc(text)}</p>` : ''}
        <ul class="ideas">${r.hits.map(h => `<li class="hit">${esc(h)}</li>`).join('')}${r.missed.map(h => `<li class="miss">Missing: ${esc(h)}</li>`).join('')}</ul>
        <p class="deckname">Model answer</p><div class="model">${rich(r.reference)}</div>`;
    }
    const note = r.note ? `<p class="deckname">Why it's written this way</p><div class="model">${rich(r.note)}</div>` : '';
    const lvl = v => r.level_after && r.level_after[v] !== r.level ? ` · level ${r.level_after[v]}` : '';
    $('#mpanel').innerHTML = `<div class="panel" id="rpanel">
      <p class="deckname">${esc(sourceName(c))} · ${esc(kindLabel(c))}</p>
      <h3 tabindex="-1" id="rhead">${head}</h3>
      <div class="meter" role="img" aria-label="${pct}% right"><span style="transform:scaleX(${r.coverage})"></span></div>
      ${detail}${note}
      <p class="coach"><b>Mentor:</b> ${esc(r.coach)}</p>
      <fieldset><legend>How well did you know it?</legend>
        <div class="seg rates">${RATES.map(([v, nm, d], i) => `<label><input type="radio" name="rate" value="${v}" ${v === r.suggested ? 'checked' : ''}><span><b>${i + 1}. ${nm}</b><small>${d}</small><small class="when">Back in ${back(r.previews[v])}${lvl(v)}</small>${v === r.suggested ? '<em class="tag">Mentor suggests</em>' : ''}</span></label>`).join('')}</div>
        <p class="help">Mentor's suggestion comes from what you got right; pick what feels true. Keys <kbd>1</kbd>–<kbd>4</kbd> choose, <kbd>Enter</kbd> confirms.</p></fieldset>
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
    const lv = s.level_change > 0 ? ` Level ${s.level} next time: ${s.level === 3 ? "you'll write the whole body" : 'the logic is blanked'}.` : s.level_change < 0 ? ` Back to level ${s.level} for now.` : '';
    toast((v === 1 ? 'Coming back in 10 minutes for another try.' : `Saved. Next review in ${back(s.days)}.`) + lv);
    next();
  }

  /* ----- code modules: the CTA summaries, progress and how to add one ----- */
  function modulesView() {
    stats().then(() => {
      const s = M.stats, mods = M.modules;
      const prog = m => [['term', 'Terms'], ['drill', 'Drills'], ['explain', 'Explain cards']].filter(([k]) => m.cards[k]).map(([k, n]) =>
        `${n} ${m.cards[k].seen}/${m.cards[k].n}${k === 'drill' && m.cards[k].seen ? ` (${m.cards[k].top} at level 3)` : ''}`).join(' · ');
      const imp = (s.imports || []).filter(i => !i.ok || i.msg.includes('skipped'));
      $('#mpanel').innerHTML = `<div class="panel modules">
        <h3>Code modules</h3>
        <p class="coach">Each module breaks down real code from your projects: the big picture, the rules behind it, and cards in three tiers. Terms come first, then code drills, then explain cards.</p>
        ${mods.length ? mods.map(m => `<article class="module" aria-labelledby="mh-${esc(m.id)}">
            <h4 id="mh-${esc(m.id)}">${esc(m.name)}</h4>
            <p class="meta">${[m.project, m.built_in ? 'comes with Argus' : new Date(m.at * 1000).toLocaleDateString([], {month: 'short', day: 'numeric', year: 'numeric'}), m.files.join(', ')].filter(Boolean).map(esc).join(' · ')}</p>
            <p class="meta">${esc(prog(m))}</p>
            ${SUMMARY.some(([k]) => m.summary[k]) ? `<details><summary>Read the breakdown</summary><dl class="defs">${SUMMARY.filter(([k]) => m.summary[k]).map(([k, n]) => `<dt>${n}</dt><dd>${rich(m.summary[k])}</dd>`).join('')}</dl></details>` : ''}
            ${m.concepts.length ? `<ul class="tags" aria-label="Concepts">${m.concepts.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
            <div class="row"><button type="button" data-study="${esc(m.id)}">Study this module</button></div></article>`).join('')
          : `<div class="empty"><b>No code modules yet</b>Add one with the steps below.</div>`}
        <h3 class="addh">Add a module</h3>
        <ol class="steps">
          <li>In Claude Code, right after building something, run <code>/mentor</code> (or <code>/mentor</code> plus a file or function name). It writes a JSON file to the project's <code>mentor_inbox</code> folder.</li>
          <li>Copy that file to <code>${esc(s.inbox || '~/.local/share/argus-ui/inbox')}</code> on the machine that runs Argus.</li>
          <li>Open this page again: the module shows up here and in Practice.</li></ol>
        ${imp.length ? `<p class="deckname">Inbox files that need a look</p><ul class="ideas">${imp.map(i => `<li class="${i.ok ? 'hit' : 'miss'}"><code>${esc(i.path)}</code>: ${esc(i.msg)}</li>`).join('')}</ul>` : ''}
      </div>`;
      $$('[data-study]').forEach(b => b.onclick = () => { M.deck = b.dataset.study; save('mentor-deck', M.deck); fillPicker(); setView('practice'); });
    });
  }

  addEventListener('keydown', e => {
    const a = document.activeElement;
    if (here !== 'mentor' || !M.result || a.tagName === 'TEXTAREA' || a.tagName === 'SELECT' || (a.tagName === 'INPUT' && a.type === 'text')) return;
    if (/^[1-4]$/.test(e.key)) { const i = $$('input[name=rate]')[+e.key - 1]; if (i) { i.checked = true; i.dispatchEvent(new Event('change')); i.focus(); } }
    else if (e.key === 'Enter' && a.type === 'radio') { e.preventDefault(); $('#rateBtn').click(); }
  });
  return {show};
})();
