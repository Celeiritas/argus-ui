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
    if (v.job && v.job.state === 'failed') warn = `<p class="mem-warn"><span aria-hidden="true">!</span> The last try failed (${e(v.job.last)}): its card under Mnemosyne on the Watch page has the log.</p>`;
    else if (v.stale) warn = `<p class="mem-warn"><span aria-hidden="true">!</span> The newest snapshot is older than a week: look at its weekly job under Mnemosyne on the Watch page.</p>`;
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

  function fill(el, api, v) {
    const e = api.esc, $ = s => el.querySelector(s);
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
    if (!ok || !data) { el.querySelector('#mem-where').textContent = 'No answer from the server: the numbers below may be old.'; return null; }
    fill(el, api, data); return data;
  }

  leafy.register('memory', {
    async show(el, api) {
      el.innerHTML = `<div class="memory">
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
          <p class="mem-meta">The 3-2-1 rule: three copies, on two kinds of storage, one of them outside your home. Each line says when that copy was last made.</p>
        </section>
        <section class="panel mem-shelfp" aria-labelledby="mem-shelf-h">
          <h3 id="mem-shelf-h">The shelf</h3>
          <p class="mem-meta" id="mem-shelf-say"></p>
          <ol class="mem-shelf" id="mem-shelf" aria-label="Snapshots on the server, oldest first"></ol>
          <details class="mem-all" id="mem-all"><summary id="mem-all-s">All snapshots</summary><ul class="mem-list" id="mem-list"></ul></details>
        </section>
      </div>`;
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
