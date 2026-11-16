// Edit Today (4.50.0, docs/home.md "Edit Today"): the owner makes Today his own. A mode with a clear Done: Today's place on the
// page becomes three lists, and nothing is kept until he presses Done (Cancel leaves Today as it was; Reset to default fills
// the lists with the default, and Done keeps that).
//   Sections: each tile shown or hidden, moved up or down, renamed (a god's tile keeps its god's name: core.js godOwned),
//   Open: each link or player shown or hidden, renamed, put in a group (typing a new group name makes the group, an empty one
//         takes it out), moved up or down in its group; a group renamed or moved as a whole. As compact on Today as before.
//   Reminders: one switch per section that can need him (a server plugin's status). Off: its tile keeps its line, but it never
//         asks for him on Today or buzzes his phone (server/quiet.py). Mentor is always off and cannot be switched on.
// Saved on the server (POST api/today -> ~/.config/argus-ui/today.json, server/today.py), so every device shows the same Today
// and an update keeps it. Only the owner sees the button; the server refuses anyone else. Every name he types is drawn with
// esc(), never as HTML. Moving is by buttons (keyboard and touch alike); the keyboard stays on the button it pressed.
const todayEdit = (() => {
  let d = null;                            // the draft while editing: {tiles, open, quiet}; null when not editing
  let saving = false;
  // editing only while the lists are on the page: going to another section and back is the same as Cancel
  const on = () => { if (d && !$('#main .home.edit')) d = null; return !!d; };
  const plainWord = e => WORDS[e.id]?.name || e.own || e.id;          // a tile's name before the owner renamed it
  const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
  const QUIET_ALWAYS = ['mentor'];         // server/quiet.py DEFAULT_QUIET: never reminds him, whatever the file says
  // the draft from a layout: `lay` is today.json's (S.today) or {} for Reset to default
  function draft(lay) {
    const was = S.today; S.today = lay;    // tileList / openList read the layout through myToday()
    try {
      const names = lay.tiles?.names || {}, onames = lay.open?.names || {};
      const tiles = home.tileList().map(e => ({id: e.id, mark: e.mark, god: godOwned(e.id), word: e.word, def: plainWord(e), name: godOwned(e.id) ? '' : names[e.id] || plainWord(e), shown: e.shown}));
      const open = home.openList().filter(x => x.key.length <= 300).map(x => ({key: x.key, what: x.what || '', def: x.def, own: x.own, name: onames[x.key] || x.def, group: x.group, shown: x.shown}));
      return {tiles, open: tidy(open), quiet: new Set((lay.quiet || []).filter(id => !QUIET_ALWAYS.includes(id)))};
    } finally { S.today = was; }
  }
  // Open's order as Today shows it: the entries without a group first, then each group, in the order the groups first come
  function tidy(list) {
    const gs = []; list.forEach(x => { const g = x.group.trim(); if (g && !gs.includes(g)) gs.push(g); });
    return [...list.filter(x => !x.group.trim()), ...gs.flatMap(g => list.filter(x => x.group.trim() === g))];
  }
  const groupsOf = () => { const gs = []; d.open.forEach(x => { const g = x.group.trim(); if (g && !gs.includes(g)) gs.push(g); }); return gs; };
  // the sections that can remind him: the server plugins (each answers status with "needs"); Argus's own failures are not a reminder
  const reminders = () => PLUGINS.filter(p => p.kind === 'server' && p.id !== 'argus' && visible([{id: p.id}]).length).map(p => ({id: p.id, word: wordOf(p.id, p.name)}));

  // ---- drawing ----
  const mv = (what, i, n, name, extra = '') => `<div class="edmove"><button type="button" class="edbtn" data-mv="-1" data-what="${what}"${extra} aria-label="Move ${esc(name)} up"${i === 0 ? ' disabled' : ''}>↑</button>`
    + `<button type="button" class="edbtn" data-mv="1" data-what="${what}"${extra} aria-label="Move ${esc(name)} down"${i === n - 1 ? ' disabled' : ''}>↓</button></div>`;
  const show = (on, name) => `<label class="check edshow"><input type="checkbox" data-f="shown"${on ? ' checked' : ''} aria-label="Show ${esc(name)} on Today"><span aria-hidden="true">Show</span></label>`;
  function tileRow(t, i) {
    const name = t.god ? t.word : t.name.trim() || t.def;
    return `<li class="edrow${t.shown ? '' : ' off'}" data-list="tiles" data-i="${i}" data-id="${esc(t.id)}"><span class="edmark">${t.mark}</span>`
      + `<div class="edname">${t.god ? `<b>${esc(t.word)}</b><small>A god's name: it stays</small>`
        : `<input type="text" class="edin" data-f="name" maxlength="40" value="${esc(t.name)}" aria-label="Name of the ${esc(t.def)} tile" autocomplete="off" spellcheck="false">`}</div>`
      + show(t.shown, name) + mv('tiles', i, d.tiles.length, name) + '</li>';
  }
  function openRow(x, i, k, n) {
    const name = x.name.trim() || x.def;
    return `<li class="edrow edlink${x.shown ? '' : ' off'}" data-list="open" data-i="${i}" data-key="${esc(x.key)}"><span class="edmark">${LINK_MARK}</span>`
      + `<div class="edname"><input type="text" class="edin" data-f="name" maxlength="40" value="${esc(x.name)}" aria-label="Name of the link ${esc(x.def)}" autocomplete="off" spellcheck="false">${x.what ? `<small>${esc(x.what)}</small>` : ''}</div>`
      + `<label class="edgroupin"><span>Group</span><input type="text" class="edin" data-f="group" maxlength="40" list="edGroups" value="${esc(x.group)}" aria-label="Group of ${esc(name)} (empty: no group)" autocomplete="off" spellcheck="false"></label>`
      + show(x.shown, name) + mv('open', k, n, name) + '</li>';
  }
  function openPart() {
    if (!d.open.length) return '';
    const gs = groupsOf(), at = x => d.open.indexOf(x);
    const block = (items, g, gi) => `<div class="edg">${g === null ? (gs.length ? '<h3 class="edgh">Without a group</h3>' : '')
      : `<div class="edghead"><label class="edgnamein"><span>Group name</span><input type="text" class="edin edgname" data-g="${esc(g)}" maxlength="40" value="${esc(g)}" autocomplete="off" spellcheck="false"></label>${mv('group', gi, gs.length, `the group ${g}`, ` data-g="${esc(g)}"`)}</div>`}`
      + `<ol class="edlist">${items.map((x, k) => openRow(x, at(x), k, items.length)).join('')}</ol></div>`;
    const loose = d.open.filter(x => !x.group.trim());
    return `<section aria-labelledby="ed-open"><h2 id="ed-open">Open</h2><p class="edhint">Type a group name on a link to put it in that group, or a new name to make one. Empty takes it out of its group.</p>`
      + (loose.length ? block(loose, null) : '') + gs.map((g, gi) => block(d.open.filter(x => x.group.trim() === g), g, gi)).join('')
      + `<datalist id="edGroups">${gs.map(g => `<option value="${esc(g)}"></option>`).join('')}</datalist></section>`;
  }
  function quietPart() {
    const rs = reminders(); if (!rs.length) return '';
    const sw = r => { const always = QUIET_ALWAYS.includes(r.id), onn = !always && !d.quiet.has(r.id);
      return `<li><label class="edswitch${always ? ' locked' : ''}"><input type="checkbox" role="switch" data-q="${esc(r.id)}"${onn ? ' checked' : ''}${always ? ' disabled' : ''}>`
        + `<span class="edsw"><b>${esc(r.word)}</b><small>${always ? 'Never reminds you' : onn ? 'Reminds you' : 'Off: never asks for you'}</small></span></label></li>`; };
    return `<section aria-labelledby="ed-quiet"><h2 id="ed-quiet">Reminders</h2><p class="edhint">Off: its tile keeps its line, but it never asks for you on Today and never buzzes your phone.</p>`
      + `<ul class="edswitches">${rs.map(sw).join('')}</ul></section>`;
  }
  const acts = where => `<div class="edacts"><button type="button" class="primary" data-ed="done"${where === 'top' ? ' id="editDone"' : ''}${saving ? ' aria-busy="true" disabled' : ''}>Done</button><button type="button" data-ed="cancel">Cancel</button>`
    + (where === 'end' ? '<button type="button" data-ed="reset" class="edreset">Reset to default</button>' : '') + '</div>';
  function draw() {
    $('#main').innerHTML = `<section class="home edit" aria-labelledby="edit-h"><div class="edtop"><h2 class="state" id="edit-h" tabindex="-1">Edit Today</h2>`
      + `<p class="edhint">Show, hide, move and rename. Nothing changes until you press Done.</p>${acts('top')}</div>`
      + `<section aria-labelledby="ed-tiles"><h2 id="ed-tiles">Sections</h2><ol class="edlist">${d.tiles.map(tileRow).join('')}</ol></section>`
      + openPart() + quietPart() + `<div class="edend">${acts('end')}</div></section>`;
  }
  // after a redraw the keyboard goes back to the same control (a moved row's button, a renamed group's field)
  const refocus = sel => { const el = $(sel); if (el && !el.disabled) el.focus(); else if (el) el.closest('.edmove')?.querySelector('button:not([disabled])')?.focus(); };

  // ---- the owner's actions ----
  function start() {
    if (role() !== 'owner' || here !== 'home') return;
    d = draft(myToday()); draw();
    scrollTo({top: 0, behavior: 'auto'}); $('#edit-h').focus();
  }
  function stop() { d = null; home.reset(); home.draw(); $('#editToday')?.focus(); }
  function move(what, i, by, g) {
    if (what === 'tiles') { const j = i + by; if (j < 0 || j >= d.tiles.length) return; [d.tiles[i], d.tiles[j]] = [d.tiles[j], d.tiles[i]]; draw(); return refocus(`[data-list=tiles][data-i="${j}"] [data-mv="${by}"]`); }
    if (what === 'open') {                 // within its own group: swap with the one before or after in the same group
      const x = d.open[i], peers = d.open.filter(y => y.group.trim() === x.group.trim()), k = peers.indexOf(x), y = peers[k + by]; if (!y) return;
      const a = d.open.indexOf(x), b = d.open.indexOf(y); [d.open[a], d.open[b]] = [d.open[b], d.open[a]]; draw();
      return refocus(`[data-list=open][data-i="${b}"] [data-mv="${by}"]`);
    }
    const gs = groupsOf(), gi = gs.indexOf(g), j = gi + by; if (gi < 0 || j < 0 || j >= gs.length) return;   // a whole group
    [gs[gi], gs[j]] = [gs[j], gs[gi]];
    d.open = [...d.open.filter(x => !x.group.trim()), ...gs.flatMap(h => d.open.filter(x => x.group.trim() === h))]; draw();
    refocus(`.edghead [data-mv="${by}"][data-g="${CSS.escape(g)}"]`);
  }
  // what Done sends: only what differs from the default, so a section or link added later still finds its place
  function layout() {
    const base = draft({}), lay = {};
    const t = {}, tn = {};
    if (!same(d.tiles.map(x => x.id), base.tiles.map(x => x.id))) t.order = d.tiles.map(x => x.id);
    const th = d.tiles.filter(x => !x.shown).map(x => x.id); if (th.length) t.hidden = th;
    d.tiles.forEach(x => { const v = x.name.trim(); if (!x.god && v && v !== x.def) tn[x.id] = v; }); if (Object.keys(tn).length) t.names = tn;
    if (Object.keys(t).length) lay.tiles = t;
    const o = {}, on = {}, og = {};
    if (!same(d.open.map(x => x.key), base.open.map(x => x.key))) o.order = d.open.map(x => x.key);
    const oh = d.open.filter(x => !x.shown).map(x => x.key); if (oh.length) o.hidden = oh;
    d.open.forEach(x => { const v = x.name.trim(), g = x.group.trim(); if (v && v !== x.def) on[x.key] = v; if (g !== x.own) og[x.key] = g; });
    if (Object.keys(on).length) o.names = on; if (Object.keys(og).length) o.groups = og;
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
    S.today = j.today; S.today_problem = null; S.quiet = [...new Set([...QUIET_ALWAYS, ...(j.today.quiet || [])])];
    stop(); toast(j.msg || 'Today saved.'); refresh();
  }
  function resetDraft() { d = draft({}); draw(); refocus('#editDone'); toast('Back to the default layout. Press Done to keep it, or Cancel.'); }

  // A press of the mouse or a finger that takes the keyboard out of a group field fires 'change' (so regroup) before its click.
  // Redrawing then would replace the button under the finger and lose the tap (Done, Cancel, Reset or a Move pressed straight
  // after typing a group). So while a press is down the regroup waits in `later`: the click applies it first and then does what
  // was pressed, on the same row or group (found by the object, not its old place); a press that ends anywhere else applies it
  // just after (mouseup). Enter and Tab are not presses: they apply at once, as before.
  let pressed = false, later = null;
  const listOf = what => what === 'tiles' ? d.tiles : d.open;
  function settle() {
    const el = later; later = null; if (!el || !on() || !el.isConnected) return;
    const a = document.activeElement, r = a && a !== el && a.dataset?.f && a.closest('#main .edit [data-i]');   // the field he pressed into, if any
    const x = r && listOf(r.dataset.list)[+r.dataset.i];
    regroup(el, false);
    if (x) refocus(`[data-list=${r.dataset.list}][data-i="${listOf(r.dataset.list).indexOf(x)}"] [data-f=${a.dataset.f}]`);
  }
  document.addEventListener('mousedown', e => { pressed = e.button === 0 && on(); }, true);   // before the press moves the keyboard
  document.addEventListener('mouseup', () => { pressed = false; if (later) setTimeout(settle, 0); }, true);   // after its click
  document.addEventListener('keydown', () => { pressed = false; }, true);

  // ---- wiring: one listener each on the page for clicks, typing and switches ----
  document.addEventListener('click', e => {
    if (e.target.closest('#editToday')) return start();
    if (!on()) return;
    const b = e.target.closest('#main .edit button'); if (!b || b.disabled) return;
    const row = b.closest('[data-i]'), x = row && listOf(row.dataset.list)[+row.dataset.i];   // what was pressed, before a regroup
    const lr = later?.dataset.f === 'group' && later.closest('[data-i]'), moving = lr && d.open[+lr.dataset.i];   // a link about to change group
    const gx = b.dataset.g !== undefined && d.open.find(y => y.group.trim() === b.dataset.g && y !== moving);   // a member of the pressed group
    settle();
    if (b.dataset.ed === 'done') return done();
    if (b.dataset.ed === 'cancel') return stop();
    if (b.dataset.ed === 'reset') return resetDraft();
    if (!b.dataset.mv) return;
    if (b.dataset.what === 'group') { if (gx) move('group', -1, +b.dataset.mv, gx.group.trim()); return; }
    if (x) move(b.dataset.what, listOf(b.dataset.what).indexOf(x), +b.dataset.mv);
  });
  document.addEventListener('input', e => {             // typing: kept in the draft as it is typed, nothing redrawn
    if (!on()) return;
    const el = e.target, row = el.closest('[data-i]');
    if (row && el.dataset.f === 'name') (row.dataset.list === 'tiles' ? d.tiles : d.open)[+row.dataset.i].name = el.value;
  });
  document.addEventListener('change', e => {
    if (!on()) return;
    const el = e.target, row = el.closest('[data-i]');
    if (el.dataset.q) { if (el.checked) d.quiet.delete(el.dataset.q); else d.quiet.add(el.dataset.q);
      const s = el.closest('label').querySelector('small'); if (s) s.textContent = el.checked ? 'Reminds you' : 'Off: never asks for you'; return; }
    if (row && el.dataset.f === 'shown') { (row.dataset.list === 'tiles' ? d.tiles : d.open)[+row.dataset.i].shown = el.checked; row.classList.toggle('off', !el.checked); return; }
    if (pressed && (el.dataset.f === 'group' || el.classList.contains('edgname'))) { later = el; return; }   // waits for the click (above)
    regroup(el, false);
  });
  // Enter in a group field applies it at once and keeps the keyboard there (the row may have moved to its new group)
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !on() || !(e.target.dataset.f === 'group' || e.target.classList.contains('edgname'))) return;
    e.preventDefault(); regroup(e.target, true);
  });
  // A group field applied: a link put in another group (or out of one), or a group renamed (empty: its links leave the group).
  // Open's order follows, so the list is drawn again. `stay`: Enter, the keyboard stays on that field; else he left it (Tab,
  // a tap elsewhere), and the keyboard goes to what comes after it in that row (its Show, or the group's Move buttons).
  function regroup(el, stay) {
    const to = el.value.replace(/\s+/g, ' ').trim(), row = el.closest('[data-i]');
    if (row && el.dataset.f === 'group') {
      const x = d.open[+row.dataset.i]; if (x.group.trim() === to) return;
      x.group = to; d.open = tidy(d.open); draw();
      return refocus(`[data-list=open][data-i="${d.open.indexOf(x)}"] ${stay ? '[data-f=group]' : '[data-f=shown]'}`);
    }
    if (el.dataset.g === undefined || !el.classList.contains('edgname')) return;
    const from = el.dataset.g, first = d.open.find(x => x.group.trim() === from); if (from === to) return;
    d.open.forEach(x => { if (x.group.trim() === from) x.group = to; }); d.open = tidy(d.open); draw();
    const h = to && `.edghead:has(.edgname[data-g="${CSS.escape(to)}"])`;
    refocus(!to ? `[data-list=open][data-i="${d.open.indexOf(first)}"] [data-f=group]` : stay ? `${h} .edgname` : `${h} [data-mv]`);
  }
  return {on, start};
})();
