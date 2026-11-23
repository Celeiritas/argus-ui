// Memory (docs/memory.md, docs/ui-plan.md §10): are Mnemosyne's backups fresh, and how many copies exist?
// The latest snapshot and the next run, the three copies of 3-2-1 told honestly, the shelf (one bar per snapshot, height by
// size: plain bars until the owner approves the jar art), and Back up now behind hold-to-confirm. Nothing here deletes,
// restores or opens a snapshot. The 15-second refresh fills the parts again but never replaces the button, so a hold in
// progress is not cut off.
// Since 1.1.0 each copy is one plain sentence from the server (what it is, when it was last made, what to do only when
// something is not fine), with a mark beside it so the state never rests on colour; no status words (docs/memory.md).
(() => {
  const MARK = {yes: '✓', no: '✕', unknown: '?', stale: '!', running: '↻'};
  const plural = (n, one) => `${n} ${one}${n === 1 ? '' : 's'}`;

  function facts(v, e) {
    const rows = [['Last snapshot', v.last ? `${e(v.last.age)} <small>${e(v.last.when)}</small>` : 'No snapshot yet'],
      ['Its size', v.last ? e(v.last.size_h) : '—'],
      ['Next run', v.job ? e(v.job.next || '—') : 'No weekly job found'],
      ['On the server', `${plural(v.count, 'snapshot')}, ${e(v.total_h)} in all`]];
    let warn = '';
    if (v.job && v.job.state === 'failed') warn = `<p class="mem-warn"><span aria-hidden="true">!</span> The last try failed (${e(v.job.last)}): its card under Mnemosyne on the Argus page has the log.</p>`;
    else if (v.stale) warn = `<p class="mem-warn"><span aria-hidden="true">!</span> The newest snapshot is older than a week: look at its weekly job under Mnemosyne on the Argus page.</p>`;
    if (v.running) warn = `<p class="mem-run"><span aria-hidden="true">●</span> Backing up now: the new snapshot fills its jar on the shelf.</p>`;
    return `<dl class="mem-facts">${rows.map(([k, d]) => `<div><dt>${k}</dt><dd>${d}</dd></div>`).join('')}</dl>${warn}`;
  }

  // one row per copy: the mark (hidden from screen readers), the copy's name, and its sentence, which is also the row's name
  function copies(v, e) {
    return v.copies.map(c => `<li class="${e(c.state)}" data-key="${e(c.key)}" data-kind="${e(c.kind || '')}" aria-label="${e(c.say)}">
      <span class="mark" aria-hidden="true">${MARK[c.state] || '?'}</span><b class="name">${e(c.label)}</b><span class="say">${e(c.say)}</span></li>`).join('');
  }

  function shelf(v, e) {
    const on = v.snapshots.slice(0, v.shelf).reverse();              // oldest on the left, the newest on the right
    let html = on.map((s, i) => { const newest = i === on.length - 1;
      return `<li class="mem-jar${newest ? ' newest' : ''}" style="--h:${Number(s.height) || 0}" title="${e(s.when)} · ${e(s.size_h)}">
        <span class="mem-bar" aria-hidden="true"></span><span class="mem-lab" aria-hidden="true"><b>${e(String(s.day))}</b>${e(s.month)}</span>
        <span class="sr">${e(s.when)}, ${e(s.size_h)}${newest ? ', the newest' : ''}</span></li>`; }).join('');
    if (v.running) html += `<li class="mem-jar filling" style="--h:.5"><span class="mem-bar" aria-hidden="true"></span><span class="mem-lab" aria-hidden="true"><b>Now</b></span><span class="sr">A new snapshot, being made now</span></li>`;
    return html;
  }

  // Browsing history is kept on this browser first, then on the server for the signed-in person (4.67.0, "Synced places"
  // below); no text or titles are persisted. `at` is when the row was made (the server's time once it took the row) and
  // `pending` marks a row the server has not taken yet.
  const recentKey = 'mnemosyne-recent-v1';
  const stamp = at => typeof at === 'string' && at.length <= 40 ? at : '';
  const keep = row => ({id:row.id, revision:row.revision, offset:row.offset, ...(stamp(row.at) ? {at:row.at} : {}), ...(row.pending === true ? {pending:true} : {})});
  let sessionRecent = [], sessionRecentOnly = false;
  function recentReads() {
    if (sessionRecentOnly) return sessionRecent;
    try {
      const raw = localStorage.getItem(recentKey);
      if (!raw) return sessionRecent;
      if (raw.length > 10000) return [];
      const rows = JSON.parse(raw), ids = new Set();
      if (!Array.isArray(rows)) return [];
      return rows.filter(row => {
        if (!row || typeof row.id !== 'string' || typeof row.revision !== 'string' || !/^[a-f0-9]{64}$/.test(row.id) || !/^[a-f0-9]{64}$/.test(row.revision) ||
            !Number.isSafeInteger(row.offset) || row.offset < 0 || row.offset > 100000 || ids.has(row.id)) return false;
        ids.add(row.id); return true;
      }).slice(0, 10).map(keep);
    } catch (_) { return sessionRecent; }
  }
  function writeRecent(rows) {
    sessionRecent = rows.slice(0, 10);
    try { localStorage.setItem(recentKey, JSON.stringify(sessionRecent)); sessionRecentOnly = false; return true; }
    catch (_) { sessionRecentOnly = true; return false; }
  }
  function rememberRead(source, offset) {
    return writeRecent([{id:source.id, revision:source.revision, offset, at:new Date().toISOString(), pending:true}, ...recentReads().filter(row => row.id !== source.id)]);
  }
  // The server took this row: the local copy gets the server's time and stops waiting (only if it is still the same place).
  function settleRecent(row) {
    const rows = recentReads();
    if (rows.some(r => r.id === row.id && r.revision === row.revision && r.offset === row.offset && r.pending))
      writeRecent(rows.map(r => r.id === row.id ? keep({...row, pending:false}) : r));
  }

  // Saved places on this browser: rows {key: JSON [id, revision], offset, at?, pending?}, the last 100.
  const placeKey = 'mnemosyne-reading-places-v1';
  function localPlaces() {
    const raw = localStorage.getItem(placeKey);
    if (!raw || raw.length > 100000) return [];
    const rows = JSON.parse(raw);
    return Array.isArray(rows) ? rows.filter(row => row && typeof row.key === 'string' && row.key.length < 300 && Number.isSafeInteger(row.offset) && row.offset >= 0 && row.offset <= 100000).slice(-100) : [];
  }
  function storePlace(key, row) {      // throws when this browser cannot store
    let rows;
    try { rows = localPlaces(); } catch (_) { rows = []; }
    rows = rows.filter(r => r.key !== key);
    rows.push({key, offset:row.offset, ...(stamp(row.at) ? {at:row.at} : {}), ...(row.pending ? {pending:true} : {})});
    localStorage.setItem(placeKey, JSON.stringify(rows.slice(-100)));
  }
  // The newer of two rows by `at`; a row without a time (made before 4.67.0) loses to one with a time.
  const time = at => Date.parse(stamp(at)) || 0;
  const newer = (a, b) => !a ? b : !b ? a : (time(b.at) > time(a.at) ? b : a);

  // Reading settings (4.67.0, docs/mnemosyne-library.md): kept on this browser, never on the server. E-ink mode is Automatic,
  // On or Off; Automatic looks for a slow-refresh or monochrome screen, or an e-ink tablet's name in the browser's user agent.
  // The side index's vibration is off until the reader turns it on.
  const prefsKey = 'mnemosyne-reading-settings-v1', EINK_MODES = ['auto', 'on', 'off'];
  const EINK_UA = /\b(?:BOOX|Onyx)\b|NoteAir|NoteMax|Tab ?Ultra|Go ?10\.3|Palma|Poke ?\d|Nova ?\d|\bLeaf ?\d/i;
  let sessionPrefs = null;
  function readingPrefs() {
    if (sessionPrefs) return {...sessionPrefs};
    try {
      const raw = JSON.parse(localStorage.getItem(prefsKey) || '{}') || {};
      return {eink: EINK_MODES.includes(raw.eink) ? raw.eink : 'auto', vibrate: raw.vibrate === true};
    } catch (_) { return {eink: 'auto', vibrate: false}; }
  }
  function savePrefs(prefs) {
    try { localStorage.setItem(prefsKey, JSON.stringify(prefs)); sessionPrefs = null; return true; }
    catch (_) { sessionPrefs = {...prefs}; return false; }
  }
  const einkScreen = () => matchMedia('(update: slow)').matches || matchMedia('(monochrome)').matches || EINK_UA.test(navigator.userAgent);
  const einkActive = () => { const m = readingPrefs().eink; return m === 'on' || (m === 'auto' && einkScreen()); };
  const applyEink = () => { document.documentElement.classList.toggle('eink', einkActive()); document.dispatchEvent(new Event('mnemosyne-eink')); };
  const EINK_SAY = {on: 'On: black and white, page by page, no motion.', off: 'Off: the usual colours and scrolling.'};
  const einkSay = m => EINK_SAY[m] || (einkScreen() ? 'Automatic: e-ink screen found.' : 'Automatic: not an e-ink screen.');

  const originalURLs = new Set();
  function clearOriginals() { originalURLs.forEach(u => URL.revokeObjectURL(u)); originalURLs.clear(); }
  function libraryUI(el, api) {
    const $ = s => el.querySelector(s), e = api.esc;
    const removed = new MutationObserver(() => { if (!el.isConnected) { clearOriginals(); document.documentElement.classList.remove('eink'); removed.disconnect(); } });
    removed.observe(document.getElementById('main'), {childList: true, subtree: true});
    let request = 0, offset = 0, browsing = true;
    // Synced places (4.67.0, docs/mnemosyne-library.md): the server keeps the signed-in person's recent list and saved places
    // (ids and a section number only), so their other devices open the same place. Fetched once per visit to the Library and
    // again by Library home; rows still waiting on this browser are sent then, unless the server already has a newer one.
    const HEX = /^[a-f0-9]{64}$/;
    const goodRow = r => r && HEX.test(r.id) && HEX.test(r.revision) && Number.isSafeInteger(r.offset) && r.offset >= 0 && r.offset <= 100000 && time(r.at) > 0;
    const goodLists = d => d && Array.isArray(d.recent) && Array.isArray(d.saved) ? {recent:d.recent.filter(goodRow), saved:d.saved.filter(goodRow)} : null;
    let synced;                                     // undefined: not asked this visit; null: the server did not answer
    async function sendPlace(kind, row) {           // the server's row, or null when it did not take it
      const r = await api.post('library/place', {kind, id:row.id, revision:row.revision, offset:row.offset});
      const lists = r.ok ? goodLists(r.data) : null;
      if (lists) synced = lists;
      return lists?.[kind].find(x => x.id === row.id && x.revision === row.revision && x.offset === row.offset) || null;
    }
    const onServer = (kind, id) => synced?.[kind].find(x => x.id === id) || null;
    async function fetchPlaces(fresh = false) {
      if (synced !== undefined && !fresh) return synced;
      const r = await api.get('library/places');
      synced = (r.ok && goodLists(r.data)) || null;
      if (!synced) return null;
      for (const row of recentReads().filter(r => r.pending && newer(onServer('recent', r.id), r) === r)) {
        const s = await sendPlace('recent', row); if (s) settleRecent(s);
      }
      let waiting = [];
      try { waiting = localPlaces().filter(r => r.pending); } catch (_) { /* nothing stored here */ }
      for (const row of waiting) {
        let id, revision;
        try { [id, revision] = JSON.parse(row.key); } catch (_) { continue; }
        if (!HEX.test(id) || !HEX.test(revision) || newer(onServer('saved', id), row) !== row) continue;
        const s = await sendPlace('saved', {id, revision, offset:row.offset});
        if (s) try { storePlace(row.key, s); } catch (_) { /* the server has it */ }
      }
      return synced;
    }
    // This browser's history first, then the server; the reading is never held up by the server.
    function remember(source, offsetRead) {
      const kept = rememberRead(source, offsetRead);
      sendPlace('recent', {id:source.id, revision:source.revision, offset:offsetRead}).then(s => { if (s) settleRecent(s); });
      return kept;
    }
    const params = () => new URLSearchParams({kind: $('#lib-kind').value, collection: $('#lib-collection').value});
    const status = msg => { $('#lib-status').textContent = msg; };
    const chapterLabel = c => (c.label === `Chapter ${Number(c.number)}` ? c.label : `Chapter ${Number(c.number)}: ${c.label}`) + (c.linear === false ? ' (additional material)' : '');
    const label = r => `${r.kind === 'paper' ? 'Original paper' : r.kind} · ${r.collection}`;
    function item(r, passage, recent = null) {
      const id = passage ? r.source_id : r.id;
      return `<article class="lib-result${recent ? ' lib-recent' : ''}"><h4>${e(r.title)}</h4><p class="lib-meta">${e(label(r))}${recent && !recent.changed ? ` · Section ${recent.offset + 1}` : ''}${passage && r.pdf_page ? ` · PDF page ${Number(r.pdf_page)}` : ''}${r.chapter ? ` · ${e(chapterLabel(r.chapter))}` : ''}</p>
        ${passage ? `<p class="lib-excerpt">${e(r.text.slice(0, 160))}${r.text.length > 160 ? '…' : ''}</p><details><summary>Read full passage</summary><p class="lib-full">${e(r.text)}</p><p class="lib-meta">${r.chapter ? e(chapterLabel(r.chapter)) + '.' : r.pdf_page ? `PDF page ${Number(r.pdf_page)}; printed page not recorded.` : 'Text source; no page number recorded.'} Keyword match, not a verified answer.</p></details>` : recent ? '' : `<p class="lib-meta">${e(r.health === 'ready' ? 'Searchable' : r.health)}${r.diagnostic ? ' · ' + e(r.diagnostic) : ''}</p>`}
        ${recent ? `<button type="button" class="lib-continue">${recent.changed ? 'Open updated document' : 'Continue reading'}</button>${recent.changed ? '<p class="lib-meta lib-recent-note">This document has changed. Open its current version from the beginning.</p>' : ''}` : ''}
        <details class="lib-source" data-source="${e(id)}" data-revision="${e(r.revision)}" data-page="${passage && r.pdf_page ? Number(r.pdf_page) : ''}" data-reader="${recent ? recent.offset : r.chapter ? Number(r.chapter.reader_offset) : ''}"><summary>Read source and details</summary><div class="lib-source-body"></div></details></article>`;
    }
    async function sourceDetail(details) {
      if (!details.open || details.dataset.loaded || details.dataset.loading) return;
      details.dataset.loading = '1';
      const body = details.querySelector('.lib-source-body'); body.textContent = 'Loading source…';
      const [r] = await Promise.all([api.get('library/source?id=' + encodeURIComponent(details.dataset.source) + '&revision=' + encodeURIComponent(details.dataset.revision)), fetchPlaces()]);
      delete details.dataset.loading;
      if (!details.isConnected || !details.open) return;
      if (!r.ok) { body.textContent = r.data?.msg || 'Could not load the source. Close and reopen to retry.'; return; }
      details.dataset.loaded = '1'; const d = r.data;
      body.innerHTML = `
        <details class="lib-reader"><summary>Read source text</summary><div class="lib-reader-body"><div class="lib-reader-tools"><button type="button" class="lib-save" disabled>Save place</button><button type="button" class="lib-resume" hidden>Resume reading</button></div><p class="lib-place-status lib-meta" role="status"></p><details class="lib-navigation"><summary>Jump to section</summary><form class="lib-jump"><label>Section number <input type="number" min="1" step="1" required inputmode="numeric" disabled></label><button type="submit" disabled>Read section</button></form></details><p class="lib-reader-status" role="status" tabindex="-1"></p><div class="lib-page"><p class="lib-reader-text lib-full"></p></div><p class="lib-page-status lib-meta" hidden></p><div class="lib-reader-nav"><button type="button" class="lib-prev">Read previous section</button><button type="button" class="lib-next">Read next section</button></div></div></details>
        <details class="lib-file-details"><summary>View file details</summary><dl><dt>File format</dt><dd>${e(d.file_format || 'unknown')}</dd><dt>Authorship</dt><dd>${e(d.authorship)}</dd><dt>Source version</dt><dd>${e(d.source_version)}</dd><dt>Extraction</dt><dd>${e(d.health)} · ${e(d.extraction_version)}</dd><dt>Indexed</dt><dd>${e(d.indexed_at)}</dd><dt>Revision</dt><dd>${e(d.revision)}</dd></dl></details>
        ${d.url ? `<a href="${e(d.url)}" target="_blank" rel="noopener noreferrer">Open source website</a>` : ''}
        ${d.original ? `<p class="lib-meta">Original: ${e(d.original.split('/').pop())}</p><button type="button" class="lib-original">Prepare original PDF</button><p class="lib-original-status" role="status"></p>` : '<p class="lib-meta">No original file is connected to the viewer yet.</p>'}`;
      const reader = body.querySelector('.lib-reader'), readStatus = body.querySelector('.lib-reader-status');
      const text = body.querySelector('.lib-reader-text'), prev = body.querySelector('.lib-prev'), next = body.querySelector('.lib-next');
      const save = body.querySelector('.lib-save'), resume = body.querySelector('.lib-resume');
      const placeStatus = body.querySelector('.lib-place-status'), jump = body.querySelector('.lib-jump');
      const section = jump.querySelector('input'), jumpButton = jump.querySelector('button');
      const identity = JSON.stringify([d.id, d.revision]);
      // The saved place is the newer of this browser's and the server's; the server's counts only for this revision.
      let local = null;
      try { local = localPlaces().find(row => row.key === identity) || null; } catch (_) { /* Reading works without storage. */ }
      const remote = onServer('saved', d.id)?.revision === d.revision ? onServer('saved', d.id) : null;
      const best = newer(local, remote);
      let saved = best ? best.offset : null;
      // where: 'synced' (the server has it), 'waiting' (this browser only, sent when the server answers), 'local' (older place)
      let where = !best ? '' : best === remote || remote?.offset === best.offset ? 'synced' : best.pending ? 'waiting' : 'local';
      const PLACE_SAY = {synced: n => `Saved section ${n}. Your other devices will open it here.`,
        waiting: n => `Saved section ${n} on this browser. Other devices get it when the server answers.`, local: n => `Saved section ${n} on this browser.`};
      function showPlace(message) {
        resume.hidden = saved === null;
        placeStatus.textContent = message || (saved === null ? 'Save a place to return later.' : PLACE_SAY[where](saved + 1));
      }
      showPlace();
      let readOffset = 0, readTotal = 0, reading = false, loaded = false;
      // E-ink paging (4.67.0): the section's text in screen-high CSS columns, one column shown; a tap on the left or right
      // quarter, PageUp/PageDown or the arrow keys turn the page, and past either end they open the neighbouring section.
      // `anchor` is the text offset at the top of the shown page, so a rotation or a resize keeps the same text in view.
      const leaf = body.querySelector('.lib-page'), pageStatus = body.querySelector('.lib-page-status');
      const GAP = 32;
      let page = 0, pages = 1, anchor = 0;
      const paged = () => document.documentElement.classList.contains('eink');
      const step = () => text.clientWidth + GAP;
      function goPage(n) {
        page = Math.max(0, Math.min(pages - 1, n)); text.scrollLeft = page * step();
        pageStatus.textContent = `Page ${page + 1} of ${pages}`;
        const b = text.getBoundingClientRect(), at = document.caretRangeFromPoint?.(b.left + 2, b.top + 8);
        anchor = at && text.contains(at.startContainer) ? at.startOffset : 0;
      }
      function pageOf(offset) {
        const node = text.firstChild;
        if (!node || !offset) return 0;
        const r = document.createRange(); r.setStart(node, Math.min(offset, node.length)); r.collapse(true);
        return Math.floor((r.getBoundingClientRect().left - text.getBoundingClientRect().left + text.scrollLeft + 1) / step());
      }
      function layout(at = null) {
        const on = paged() && loaded;
        text.classList.toggle('paged', on); pageStatus.hidden = !on;
        if (on) leaf.tabIndex = 0; else leaf.removeAttribute('tabindex');
        if (!on) { text.scrollLeft = 0; return; }
        text.style.setProperty('--colw', text.clientWidth + 'px');
        pages = Math.max(1, Math.round((text.scrollWidth + GAP) / step()));
        goPage(at === 'last' ? pages - 1 : at === 'first' ? 0 : pageOf(anchor));
      }
      function turn(dir) {
        if (reading || !text.classList.contains('paged')) return;
        if (dir > 0) { if (page < pages - 1) goPage(page + 1); else if (!next.disabled) readSection(readOffset + 1, false, 'first'); }
        else if (page > 0) goPage(page - 1); else if (!prev.disabled) readSection(readOffset - 1, false, 'last');
      }
      leaf.addEventListener('click', event => {
        if (!text.classList.contains('paged') || String(getSelection())) return;
        const b = leaf.getBoundingClientRect(), x = (event.clientX - b.left) / b.width;
        if (x < 0.25) turn(-1); else if (x > 0.75) turn(1);
      });
      leaf.addEventListener('keydown', event => {
        const dir = {PageDown: 1, ArrowRight: 1, PageUp: -1, ArrowLeft: -1}[event.key];
        if (!dir || !text.classList.contains('paged')) return;
        event.preventDefault(); turn(dir);
      });
      new ResizeObserver(() => { if (leaf.isConnected) layout(); }).observe(leaf);
      const relayout = () => { if (!leaf.isConnected) document.removeEventListener('mnemosyne-eink', relayout); else layout(); };
      document.addEventListener('mnemosyne-eink', relayout);
      prev.disabled = true; next.disabled = true;
      async function readSection(offset, initial = false, at = 'first') {
        if (reading) return;
        reading = true; prev.disabled = true; next.disabled = true; save.disabled = true; resume.disabled = true; section.disabled = true; jumpButton.disabled = true; readStatus.textContent = 'Loading text…';
        const params = new URLSearchParams({id:d.id, revision:d.revision, offset});
        if (initial && details.dataset.page) params.set('pdf_page', details.dataset.page);
        if (initial && details.dataset.reader) params.set('offset', details.dataset.reader);
        const result = await api.get('library/read?' + params);
        if (!body.isConnected) return;
        reading = false; resume.disabled = false;
        if (!result.ok) {
          readStatus.textContent = result.data?.msg || 'Could not load text. Close and reopen to retry. Your current text is kept.';
          save.disabled = readTotal === 0; section.disabled = readTotal === 0; jumpButton.disabled = readTotal === 0;
          loaded = false; prev.disabled = readOffset <= 0; next.disabled = readOffset + 1 >= readTotal; return;
        }
        const data = result.data;
        if (!data.available) { loaded = false; readStatus.textContent = data.reason || 'No reviewed text is available.'; save.disabled = readTotal === 0; section.disabled = readTotal === 0; jumpButton.disabled = readTotal === 0; prev.disabled = readOffset <= 0; next.disabled = readOffset + 1 >= readTotal; return; }
        loaded = true; readOffset = data.offset; readTotal = data.total;
        save.disabled = false; section.disabled = false; jumpButton.disabled = false;
        if (saved !== null && saved >= readTotal) { saved = null; showPlace('The saved section is unavailable. Save a new place in this document.'); }
        if (reader.open && details.open && !remember(d, readOffset)) showPlace('Reading history is kept for this visit only; this browser could not save it.');
        section.max = String(readTotal); section.value = String(readOffset + 1);
        const block = data.blocks[0];
        text.textContent = block.text || '(No extracted text on this page.)';
        readStatus.textContent = `Section ${readOffset + 1} of ${readTotal}${block.pdf_page ? ` · PDF page ${block.pdf_page}; printed page not recorded` : ''}${block.chapter ? ` · ${chapterLabel(block.chapter)}` : ''}. Extracted text; check the original for layout.`;
        prev.disabled = readOffset <= 0; next.disabled = readOffset + 1 >= readTotal;
        layout(at);
        if (initial && text.classList.contains('paged')) readStatus.scrollIntoView({block:'start'});   // the whole page on the screen
        if (!initial) {
          if (text.classList.contains('paged') && leaf.contains(document.activeElement)) leaf.focus({preventScroll:true});
          else readStatus.focus({preventScroll:true});
          readStatus.scrollIntoView({block:'start'});
        }
      }
      reader.addEventListener('toggle', () => {
        if (!reader.open) return;
        if (!loaded) readSection(readOffset, readTotal === 0);
        else if (details.open && !remember(d, readOffset)) showPlace('Reading history is kept for this visit only; this browser could not save it.');
      });
      details.addEventListener('toggle', () => {
        if (details.open && reader.open && loaded && !remember(d, readOffset)) showPlace('Reading history is kept for this visit only; this browser could not save it.');
      });
      if (details.dataset.continue) reader.open = true;
      // Save place: this browser first, then the server. Either one is enough to keep the place.
      save.addEventListener('click', async () => {
        if (reading || readTotal === 0) return;
        const placeAt = readOffset, row = {id:d.id, revision:d.revision, offset:placeAt};
        let here = true;
        try { storePlace(identity, {...row, at:new Date().toISOString(), pending:true}); } catch (_) { here = false; }
        if (here) { saved = placeAt; where = 'waiting'; showPlace(); }
        save.disabled = true;
        const s = await sendPlace('saved', row);
        if (!body.isConnected) return;
        save.disabled = reading || readTotal === 0;
        if (s) { try { storePlace(identity, s); } catch (_) { /* the server has it */ } saved = placeAt; where = 'synced'; showPlace(); }
        else if (!here) showPlace('This browser could not save your place. You can keep reading.');
      });
      resume.addEventListener('click', () => { if (saved !== null) readSection(saved); });
      jump.addEventListener('submit', event => {
        event.preventDefault();
        const target = Number(section.value);
        if (Number.isSafeInteger(target) && target >= 1 && target <= readTotal) readSection(target - 1);
      });
      prev.addEventListener('click', () => readSection(readOffset - 1));
      next.addEventListener('click', () => readSection(readOffset + 1));
      body.querySelector('.lib-original')?.addEventListener('click', async event => {
        const button = event.currentTarget, msg = body.querySelector('.lib-original-status'); button.disabled = true; msg.textContent = 'Preparing PDF…';
        const result = await api.get('library/original?id=' + encodeURIComponent(d.id) + '&revision=' + encodeURIComponent(d.revision));
        if (!body.isConnected) return;
        button.disabled = false;
        if (!result.ok) { msg.textContent = result.data?.msg || 'The original is unavailable. Your search results are kept.'; return; }
        try {
          const bytes = Uint8Array.from(atob(result.data.base64), c => c.charCodeAt(0));
          const url = URL.createObjectURL(new Blob([bytes], {type: 'application/pdf'})); originalURLs.add(url);
          const link = document.createElement('a'); link.href = url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Open original PDF';
          msg.replaceChildren(link); button.hidden = true;
        } catch (_) { msg.textContent = 'The PDF could not be prepared. Try again.'; }
      });
    }
    function wire() { el.querySelectorAll('.lib-source:not([data-wired])').forEach(d => {
      d.dataset.wired = '1'; d.addEventListener('toggle', () => sourceDetail(d));
      d.closest('article').querySelector('.lib-continue')?.addEventListener('click', event => {
        d.dataset.continue = '1'; d.open = true;
        if (d.dataset.loaded) d.querySelector('.lib-reader').open = true;
        event.currentTarget.hidden = true;
      });
    }); }
    // Library home: this browser's recent list merged with the server's by document, the newer row winning, newest first.
    async function home() {
      const seq = ++request;
      $('#lib-heading').textContent = 'Recently checked out';
      $('#lib-more').hidden = true; $('#lib-totals').textContent = '';
      status('Loading your recently checked out documents…');
      const server = await fetchPlaces(true);
      if (seq !== request || !el.isConnected) return;
      const byId = new Map();
      [...recentReads(), ...(server?.recent || [])].forEach(row => byId.set(row.id, newer(byId.get(row.id), row)));
      const rows = [...byId.values()].sort((a, b) => time(b.at) - time(a.at)).slice(0, 10);
      if (!rows.length) { await load(true, false, true); return; }
      const results = await Promise.all(rows.map(row => api.get('library/source?id=' + encodeURIComponent(row.id))));
      if (seq !== request || !el.isConnected) return;
      clearOriginals();
      $('#lib-results').innerHTML = results.map((result, i) => {
        if (!result.ok) return `<article class="lib-result"><h4>Unavailable document</h4><p class="lib-meta">${result.status === 404 ? 'This document is no longer in the current catalog.' : 'Could not load this document. Choose Library home to retry.'}</p></article>`;
        const d = result.data, changed = d.revision !== rows[i].revision;
        return item(d, false, {changed, offset:changed ? 0 : rows[i].offset});
      }).join('');
      status(`Your last ${rows.length} checked out documents${server ? '' : ' on this browser'}. Nothing is moved or locked.`);
      wire();
    }
    async function load(browse, more = false, emptyHome = false) {
      const seq = ++request, query = $('#lib-query').value.trim(); browsing = browse;
      const nextOffset = more ? offset + 30 : 0;
      $('#lib-heading').textContent = emptyHome ? 'Your library' : browse ? 'Browse shelves' : 'Search library';
      const p = params();
      $('#lib-scope').textContent = $('#lib-kind').selectedOptions[0].textContent;
      if (!browse && !query) { status('Enter a topic or phrase, or browse your sources.'); return; }
      if (browse) { p.set('health', $('#lib-health').value); p.set('offset', nextOffset); }
      else p.set('q', query);
      $('#lib-more').hidden = true; status(browse ? 'Loading sources…' : 'Searching your sources…');
      const r = await api.get('library/' + (browse ? 'catalog' : 'search') + '?' + p);
      if (seq !== request || !el.isConnected) return;
      if (!r.ok) { $('#lib-more').hidden = !more; status(r.data?.msg || 'The library did not answer. Your previous results are kept.'); return; }
      const d = r.data, rows = browse ? d.sources : d.passages;
      if (d.configured === false) { status('Your library has not been connected yet. Backups are available below.'); $('#lib-results').replaceChildren(); return; }
      if (browse) {
        offset = nextOffset;
        const total = Object.values(d.totals).reduce((a, b) => a + b, 0);
        $('#lib-totals').textContent = `${total} catalogued · ${d.totals.ready || 0} searchable`;
        if (!$('#lib-collection').dataset.loaded) {
          d.collections.forEach(c => { const o = document.createElement('option');o.value = c;o.textContent = c;$('#lib-collection').append(o); });
          $('#lib-collection').dataset.loaded = '1';
        }
        status(d.total ? `${Math.min(offset + rows.length, d.total)} of ${d.total} sources in this view.` : 'No sources in this view. Try another filter.');
        $('#lib-more').hidden = offset + rows.length >= d.total;
      } else status(rows.length ? `${rows.length} matching passages. Open a passage to check its context.` : 'No matching passages in this scope. Try different words or source filters.');
      if (emptyHome) status('No recently checked out documents yet. Browse your sources below or search to start reading.');
      const content = rows.map(r => item(r, !browse)).join('');
      if (more) $('#lib-results').insertAdjacentHTML('beforeend', content); else { clearOriginals(); $('#lib-results').innerHTML = content; }
      wire();
    }
    $('#lib-search').addEventListener('submit', event => { event.preventDefault(); load(false); });
    $('#lib-browse').addEventListener('click', () => load(true));
    $('#lib-more').addEventListener('click', () => load(true, true));
    $('#lib-home').addEventListener('click', home);
    const prefs = readingPrefs(), modeSelect = $('#lib-eink'), vibrateBox = $('#lib-vibrate');
    const sayPrefs = kept => { $('#lib-settings-say').textContent = einkSay(readingPrefs().eink) + (kept ? '' : ' This browser could not keep the setting; it applies until you leave.'); };
    modeSelect.value = prefs.eink; vibrateBox.checked = prefs.vibrate; applyEink(); sayPrefs(true);
    modeSelect.addEventListener('change', () => { const kept = savePrefs({...readingPrefs(), eink: modeSelect.value}); applyEink(); sayPrefs(kept); });
    vibrateBox.addEventListener('change', () => { sayPrefs(savePrefs({...readingPrefs(), vibrate: vibrateBox.checked})); });
    for (const id of ['#lib-kind', '#lib-collection', '#lib-health']) $(id).addEventListener('change', () => load(id === '#lib-health' ? true : browsing));
    home();
  }

  function fill(el, api, v) {
    const e = api.esc, $ = s => el.querySelector(s);
    $('#mem-summary').textContent = v.summary || 'Backup status';
    $('#mem-summary').classList.toggle('mem-warn', !!v.attention);
    const backup = $('#mem-backups');
    if (v.attention && !el.dataset.backupTouched) backup.open = true;
    $('#mem-where').innerHTML = !v.folder ? 'No snapshot folder found. Name it as <code>"folder"</code> in <code>~/.config/argus-ui/memory.json</code>.'
      : v.found ? `Reading the snapshot list in <code>${e(v.folder)}/</code>: names and sizes only, never what is inside.`
      : `Can't read <code>${e(v.folder)}/</code>: check that it exists.`;
    $('#mem-facts').innerHTML = facts(v, e);
    $('#mem-copies').innerHTML = copies(v, e);
    $('#mem-shelf').innerHTML = shelf(v, e);
    $('#mem-shelf').hidden = !v.count && !v.running;
    $('#mem-shelf-say').textContent = !v.count ? 'No snapshots on the shelf yet.'
      : v.count > v.shelf ? `The newest ${v.shelf} of ${v.count}, oldest on the left. Height shows size.` : 'Oldest on the left, newest on the right. Height shows size.';
    $('#mem-all-s').textContent = `All ${plural(v.count, 'snapshot')}`;
    $('#mem-all').hidden = !v.count;
    $('#mem-list').innerHTML = v.snapshots.map(s => `<li><b>${e(s.when)}</b> <span>${e(s.age)}</span>
      <span class="size">${e(s.size_h)} <small>(${Number(s.size).toLocaleString('en-US')} bytes)</small></span></li>`).join('');
    $('#mem-note').textContent = v.note;
    if (!el.dataset.said) $('#mem-why').textContent = v.why_not;   // a fresh answer to a hold stays until the next hold
    el.dataset.said = '';
  }

  async function load(el, api) {
    const {ok, data} = await api.get('state');
    if (!ok || !data) { el.querySelector('#mem-summary').textContent = 'No answer from the server: backup information may be old.'; el.querySelector('#mem-summary').classList.add('mem-warn'); return null; }
    fill(el, api, data); return data;
  }

  leafy.register('memory', {
    async show(el, api) {
      clearOriginals(); delete el.dataset.backupTouched;
      el.innerHTML = `<div class="memory">
        <section class="panel mem-library" aria-labelledby="lib-heading">
          <h3 id="lib-heading">Recently checked out</h3>
          <form id="lib-search" role="search"><label for="lib-query" class="sr">Search your sources</label><input id="lib-query" type="search" maxlength="300" placeholder="Search a topic or phrase"><button type="submit" class="primary">Search</button></form>
          <details class="lib-filters"><summary>Filter sources <span id="lib-scope">All source types</span></summary>
            <label>Source type<select id="lib-kind"><option value="paper">Original papers</option><option value="" selected>All source types</option><option value="book">Books</option><option value="learning">Our learnings</option><option value="note">Notes</option><option value="summary">Summaries</option><option value="guide">Guides</option><option value="unknown">Unclassified</option></select></label>
            <label>Collection<select id="lib-collection"><option value="">All collections</option></select></label>
            <label>Availability (browse only)<select id="lib-health"><option value="">Any status</option><option value="ready">Searchable</option><option value="pending">Pending extraction</option><option value="failed">Failed extraction</option><option value="suspect">Needs text review</option><option value="catalog-only">Catalog only</option><option value="unknown">Unknown</option></select></label>
          </details>
          <div class="lib-tools"><button id="lib-home" type="button">Library home</button><button id="lib-browse" type="button">Browse shelves</button><span id="lib-totals"></span></div>
          <details class="lib-settings"><summary>Reading settings</summary>
            <label>E-ink mode<select id="lib-eink"><option value="auto">Automatic</option><option value="on">On</option><option value="off">Off</option></select></label>
            <p id="lib-settings-say" class="lib-meta" role="status"></p>
            <label class="lib-check"><input type="checkbox" id="lib-vibrate"> Vibrate when the side index moves</label>
          </details>
          <p class="lib-preview"><a id="lib-preview" href="${api.esc(api.url('plugins/memory/reading-room-preview.html'))}">Try the reading room preview</a><small>Sample books · Colorful shelves and a sliding index</small></p>
          <p id="lib-status" role="status" aria-live="polite"></p><div id="lib-results"></div><button id="lib-more" type="button" hidden>Show more sources</button>
        </section>
        <div class="mem-backup-summary"><h3>Backups</h3><p id="mem-summary" role="status">Checking backups…</p></div>
        <details class="mem-backups" id="mem-backups"><summary>Backup controls and history</summary><div class="mem-backup-panels">
        <p class="mem-where" id="mem-where">Reading the snapshot folder…</p>
        <section class="panel mem-now" aria-labelledby="mem-now-h">
          <h3 id="mem-now-h">Latest snapshot</h3>
          <div id="mem-facts"></div>
          <div class="mem-act">
            <button type="button" class="primary" id="mem-backup" aria-describedby="mem-note mem-why">Back up now</button>
            <p class="mem-note" id="mem-note"></p>
          </div>
          <p class="mem-why" id="mem-why" role="status" aria-live="polite"></p>
        </section>
        <section class="panel mem-321" aria-labelledby="mem-copies-h">
          <h3 id="mem-copies-h">Where your backups are</h3>
          <ul class="mem-copies" id="mem-copies"></ul>
          <p class="mem-meta">The 3-2-1 rule: three copies, on two kinds of storage, one of them outside your home. Each line is one place your backups live, and when it was last brought up to date.</p>
        </section>
        <section class="panel mem-shelfp" aria-labelledby="mem-shelf-h">
          <h3 id="mem-shelf-h">The shelf</h3>
          <p class="mem-meta" id="mem-shelf-say"></p>
          <ol class="mem-shelf" id="mem-shelf" aria-label="Snapshots on the server, oldest first"></ol>
          <details class="mem-all" id="mem-all"><summary id="mem-all-s">All snapshots</summary><ul class="mem-list" id="mem-list"></ul></details>
        </section>
        </div></details>
      </div>`;
      el.querySelector('#mem-backups').addEventListener('click', e => { if (e.target.closest('summary')) el.dataset.backupTouched = '1'; });
      libraryUI(el, api);
      const btn = el.querySelector('#mem-backup'), why = el.querySelector('#mem-why');
      api.holdConfirm(btn, async () => {
        const r = await api.post('backup', {});
        const msg = (r.data && r.data.msg) || (r.ok ? 'Backup started.' : 'No answer from the server: nothing was started.');
        el.dataset.said = '1'; why.textContent = msg; api.toast(msg);
        if (!r.ok) return false;
        await load(el, api); why.textContent = msg;
        const from = el.querySelector('.mem-copies li[data-key="server"] .mark'), to = el.querySelector('.mem-shelf .filling .mem-bar');
        if (from && to) api.fx.motes(from, to, {color: '#8FC4A4'});   // a ribbon of motes into the new jar (reduced motion: none)
      });
      await load(el, api);
    },
    refresh(el, api) { return load(el, api); },
  });
})();
