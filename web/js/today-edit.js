// Edit Today (4.50.0, docs/home.md "Edit Today"): the owner makes Today his own. Its button is in More's Settings (4.54.0); on
// another page it goes to Today first (<base>/#edit, home.js). A mode with a clear Done: Today's place on the page becomes
// three lists, and nothing is kept until he presses Done (Cancel leaves Today as it was; Reset to default fills the lists with
// the default, and Done keeps that).
//   Sections: each section renamed (a god's keeps its god's name: core.js godOwned) and moved up or down; one that can have
//         a line on Today (a server plugin: it has a status line) is shown there or hidden (4.54.0: no Show where it does nothing),
//   Links in More: each player or link renamed and moved up or down (4.54.0: no groups and no Show; More lists them all),
//   Reminders: one switch per section that can need him (a server plugin's status). Off: its line stays, but it never
//         asks for him on Today or buzzes his phone (server/quiet.py). Mentor is always off and cannot be switched on; Zeus
//         is always on and cannot be switched off (he asks for the owner's yes). Mnemosyne's says off also drops the backup
//         line from the 08:00 summary.
// Saved on the server (POST api/today -> ~/.config/argus-ui/today.json, server/today.py), so every device shows the same Today
// and an update keeps it. Only the owner sees the button; the server refuses anyone else. Every name he types is drawn with
// esc(), never as HTML. Moving is by buttons (keyboard and touch alike); the keyboard stays on the button it pressed.
const todayEdit = (() => {
  let d = null;                            // the draft while editing: {tiles, open, quiet}; null when not editing
  let saving = false;
  // editing only while the lists are on the page: going to another section and back is the same as Cancel
  const on = () => { if (d && !$('#main .home.edit')) d = null; return !!d; };
  const plainWord = e => WORDS[e.id]?.name || e.own || e.id;          // a tile's name before the owner renamed it
  const canLine = id => PLUGINS.some(p => p.id === id && p.kind === 'server');   // home.js newsLines: only these have a line
  const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
  const QUIET_ALWAYS = ['mentor'];         // server/quiet.py DEFAULT_QUIET: never reminds him, whatever the file says
  const QUIET_NEVER = ['throne'];          // server/quiet.py NEVER_QUIET: Zeus asks for his yes, so he always reminds (4.50.1)
  const quietable = id => !QUIET_ALWAYS.includes(id) && !QUIET_NEVER.includes(id);
  // a plain line under a switch whose "off" does more than Today and the phone (server/argus_ui.py backups_line())
  const SWITCH_NOTE = {memory: 'Off also leaves the backup line out of the daily summary.',
    throne: 'Zeus asks for your yes before deploys and merges, so he always reminds you.'};
  // the draft from a layout: `lay` is today.json's (S.today) or {} for Reset to default
  function draft(lay) {
    const was = S.today; S.today = lay;    // tileList / openList read the layout through myToday()
    try {
      const names = lay.tiles?.names || {}, onames = lay.open?.names || {};
      const tiles = home.tileList().map(e => ({id: e.id, mark: e.mark, god: godOwned(e.id), word: e.word, def: plainWord(e), name: godOwned(e.id) ? '' : names[e.id] || plainWord(e), shown: e.shown, line: canLine(e.id)}));
      const open = linkList().map(x => ({key: x.key, what: x.what || '', def: x.def, name: onames[x.key] || x.def}));
      return {tiles, open, quiet: new Set((lay.quiet || []).filter(quietable))};
    } finally { S.today = was; }
  }
  // More's players and links (a player that is also a section, Mealie, is not in More: it has its own row there)
  const linkList = () => home.openList().filter(x => x.key.length <= 300 && !(x.media && PLUGINS.some(p => p.id === x.id)));
  // the sections that can remind him: the server plugins (each answers status with "needs"); Argus's own failures are not a reminder
  const reminders = () => PLUGINS.filter(p => p.kind === 'server' && p.id !== 'argus' && visible([{id: p.id}]).length).map(p => ({id: p.id, word: wordOf(p.id, p.name)}));

  // ---- drawing ----
  const mv = (what, i, n, name, extra = '') => `<div class="edmove"><button type="button" class="edbtn" data-mv="-1" data-what="${what}"${extra} aria-label="Move ${esc(name)} up"${i === 0 ? ' disabled' : ''}>↑</button>`
    + `<button type="button" class="edbtn" data-mv="1" data-what="${what}"${extra} aria-label="Move ${esc(name)} down"${i === n - 1 ? ' disabled' : ''}>↓</button></div>`;
  const show = (on, name) => `<label class="check edshow"><input type="checkbox" data-f="shown"${on ? ' checked' : ''} aria-label="Show ${esc(name)} on Today"><span aria-hidden="true">Show</span></label>`;
  function tileRow(t, i) {
    const name = t.god ? t.word : t.name.trim() || t.def;
    return `<li class="edrow${t.line && !t.shown ? ' off' : ''}" data-list="tiles" data-i="${i}" data-id="${esc(t.id)}"><span class="edmark">${t.mark}</span>`
      + `<div class="edname">${t.god ? `<b>${esc(t.word)}</b><small>A god's name: it stays</small>`
        : `<input type="text" class="edin" data-f="name" maxlength="40" value="${esc(t.name)}" aria-label="Name of the ${esc(t.def)} tile" autocomplete="off" spellcheck="false">`}</div>`
      + (t.line ? show(t.shown, name) : '') + mv('tiles', i, d.tiles.length, name) + '</li>';
  }
  function openRow(x, i) {
    const name = x.name.trim() || x.def;
    return `<li class="edrow edlink" data-list="open" data-i="${i}" data-key="${esc(x.key)}"><span class="edmark">${LINK_MARK}</span>`
      + `<div class="edname"><input type="text" class="edin" data-f="name" maxlength="40" value="${esc(x.name)}" aria-label="Name of the link ${esc(x.def)}" autocomplete="off" spellcheck="false">${x.what ? `<small>${esc(x.what)}</small>` : ''}</div>`
      + mv('open', i, d.open.length, name) + '</li>';
  }
  const openPart = () => !d.open.length ? '' : `<section aria-labelledby="ed-open"><h2 id="ed-open">Links in More</h2><p class="edhint">Their names, and their order in More.</p>`
    + `<ol class="edlist">${d.open.map(openRow).join('')}</ol></section>`;
  function quietPart() {
    const rs = reminders(); if (!rs.length) return '';
    // a locked switch (Mentor always off, Zeus always on) is disabled but still read out: its label says its state in words
    const sw = r => { const off = QUIET_ALWAYS.includes(r.id), lock = !quietable(r.id), onn = !off && !d.quiet.has(r.id);
      const state = off ? 'Never reminds you' : lock ? 'Always reminds you' : onn ? 'Reminds you' : 'Off: never asks for you';
      const note = SWITCH_NOTE[r.id], nid = note && `edq-note-${esc(r.id)}`;
      return `<li><label class="edswitch${lock ? ' locked' : ''}"><input type="checkbox" role="switch" data-q="${esc(r.id)}"${onn ? ' checked' : ''}${lock ? ' disabled' : ''}${note ? ` aria-describedby="${nid}"` : ''}>`
        + `<span class="edsw"><b>${esc(r.word)}</b><small class="edstate">${state}</small></span></label>${note ? `<p class="ednote" id="${nid}">${esc(note)}</p>` : ''}</li>`; };
    return `<section aria-labelledby="ed-quiet"><h2 id="ed-quiet">Reminders</h2><p class="edhint">Off: its line stays on Today, but it never asks for you there and never buzzes your phone.</p>`
      + `<ul class="edswitches">${rs.map(sw).join('')}</ul></section>`;
  }
  const acts = where => `<div class="edacts"><button type="button" class="primary" data-ed="done"${where === 'top' ? ' id="editDone"' : ''}${saving ? ' aria-busy="true" disabled' : ''}>Done</button><button type="button" data-ed="cancel">Cancel</button>`
    + (where === 'end' ? '<button type="button" data-ed="reset" class="edreset">Reset to default</button>' : '') + '</div>';
  function draw() {
    $('#main').innerHTML = `<section class="home edit" aria-labelledby="edit-h"><div class="edtop"><h2 class="state" id="edit-h" tabindex="-1">Edit Today</h2>`
      + `<p class="edhint">Show, hide, move and rename. Nothing changes until you press Done.</p>${acts('top')}</div>`
      + `<section aria-labelledby="ed-tiles"><h2 id="ed-tiles">Sections</h2><p class="edhint">Their names everywhere. Shown: its line on Today when it has news.</p><ol class="edlist">${d.tiles.map(tileRow).join('')}</ol></section>`
      + openPart() + quietPart() + `<div class="edend">${acts('end')}</div></section>`;
  }
  // after a redraw the keyboard goes back to the same control (a moved row's button)
  const refocus = sel => { const el = $(sel); if (el && !el.disabled) el.focus(); else if (el) el.closest('.edmove')?.querySelector('button:not([disabled])')?.focus(); };

  // ---- the owner's actions ----
  function start() {
    if (role() !== 'owner' || here !== 'home') return;
    d = draft(myToday()); draw();
    scrollTo({top: 0, behavior: 'auto'}); $('#edit-h').focus();
  }
  // the keyboard goes back to the More button that is showing (the strip's or the bottom bar's), where Edit Today was found
  function stop() { d = null; home.reset(); home.draw(); $$('[data-more]').find(b => !b.hidden && b.getClientRects().length)?.focus(); }
  const listOf = what => what === 'tiles' ? d.tiles : d.open;
  function move(what, i, by) {
    const list = listOf(what), j = i + by; if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]]; draw(); refocus(`[data-list=${what}][data-i="${j}"] [data-mv="${by}"]`);
  }
  // what Done sends: only what differs from the default, so a section or link added later still finds its place
  function layout() {
    const base = draft({}), lay = {};
    const t = {}, tn = {};
    if (!same(d.tiles.map(x => x.id), base.tiles.map(x => x.id))) t.order = d.tiles.map(x => x.id);
    const th = d.tiles.filter(x => x.line && !x.shown).map(x => x.id); if (th.length) t.hidden = th;
    d.tiles.forEach(x => { const v = x.name.trim(); if (!x.god && v && v !== x.def) tn[x.id] = v; }); if (Object.keys(tn).length) t.names = tn;
    if (Object.keys(t).length) lay.tiles = t;
    const o = {}, on = {};                 // 4.54.0: an older file's Open "hidden" and "groups" are not kept
    if (!same(d.open.map(x => x.key), base.open.map(x => x.key))) o.order = d.open.map(x => x.key);
    d.open.forEach(x => { const v = x.name.trim(); if (v && v !== x.def) on[x.key] = v; });
    if (Object.keys(on).length) o.names = on;
    if (Object.keys(o).length) lay.open = o;
    if (d.quiet.size) lay.quiet = [...d.quiet];
    return lay;
  }
  async function done() {
    if (saving) return;
    const lay = layout(), reset = !Object.keys(lay).length;
    saving = true; $$('#main [data-ed=done]').forEach(b => { b.disabled = true; b.setAttribute('aria-busy', 'true'); });
    let j = null;
    try { const r = await fetch(url('api/today'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(reset ? {reset: true} : lay)}); j = await r.json(); }
    catch (e) { j = {ok: false, msg: "Couldn't reach the server to save Today. Check that it's on, then press Done again."}; }
    saving = false;
    if (!j || !j.ok) {                     // stay in Edit with everything he changed, and say why in plain words
      $$('#main [data-ed=done]').forEach(b => { b.disabled = false; b.removeAttribute('aria-busy'); });
      toast((j && j.msg) || "Couldn't save Today. Try again in a moment."); return;
    }
    S.today = j.today; S.today_problem = null; S.quiet = [...new Set([...QUIET_ALWAYS, ...(j.today.quiet || []).filter(quietable)])];
    stop(); toast(j.msg || 'Today saved.'); refresh();
  }
  function resetDraft() { d = draft({}); draw(); refocus('#editDone'); toast('Back to the default layout. Press Done to keep it, or Cancel.'); }

  // ---- wiring: one listener each on the page for clicks, typing and switches ----
  document.addEventListener('click', e => {
    if (e.target.closest('#editToday')) return fromMore();
    if (!on()) return;
    const b = e.target.closest('#main .edit button'); if (!b || b.disabled) return;
    if (b.dataset.ed === 'done') return done();
    if (b.dataset.ed === 'cancel') return stop();
    if (b.dataset.ed === 'reset') return resetDraft();
    const row = b.closest('[data-i]'); if (b.dataset.mv && row) move(row.dataset.list, +row.dataset.i, +b.dataset.mv);
  });
  document.addEventListener('input', e => {             // typing: kept in the draft as it is typed, nothing redrawn
    if (!on()) return;
    const el = e.target, row = el.closest('[data-i]');
    if (row && el.dataset.f === 'name') listOf(row.dataset.list)[+row.dataset.i].name = el.value;
  });
  document.addEventListener('change', e => {
    if (!on()) return;
    const el = e.target, row = el.closest('[data-i]');
    if (el.dataset.q) { if (el.checked) d.quiet.delete(el.dataset.q); else d.quiet.add(el.dataset.q);
      const s = el.closest('label').querySelector('.edstate'); if (s) s.textContent = el.checked ? 'Reminds you' : 'Off: never asks for you'; return; }
    if (row && el.dataset.f === 'shown') { d.tiles[+row.dataset.i].shown = el.checked; row.classList.toggle('off', !el.checked); }
  });
  // Edit Today in More's Settings: More closes; on Today the lists open at once, on another page Today opens with them
  // (<base>/#edit, home.js draw())
  function fromMore() {
    // the sheet's 'close' (core.js) would give the keyboard back to the More button after start() put it on the lists
    moreFrom?.setAttribute('aria-expanded', 'false'); moreFrom = null;
    const sheet = $('#moreSheet'); if (sheet?.open) sheet.close();
    if (here !== 'home') { location.href = url('') + '#edit'; return; }
    start();
  }
  return {on, start};
})();
