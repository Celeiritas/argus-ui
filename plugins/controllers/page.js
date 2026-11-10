// Leafy Controllers: the game controllers this machine sees, one row each (docs/controllers.md). A bundled server plugin's page script.
// Every row says the same five things in the same place: slot, name, mode, real or Steam virtual, rumble. Each state is
// an icon and a word, never colour alone. The list is redrawn on the 15 s refresh and by "Check again"; the button
// sits outside the list, so keyboard focus stays on it across redraws.
leafy.register('controllers', (() => {
  const ICON = {   // 16 px line icons, aria-hidden: the word next to each one carries the meaning
    yes: '<path d="M3 8.5l3.2 3L13 4.5"/>',
    no: '<path d="M4 4l8 8M12 4l-8 8"/>',
    real: '<path d="M6 2v4M10 2v4M4.5 6h7v2.5a3.5 3.5 0 0 1-7 0zM8 12v2"/>',                      // a plug: on a cable or dongle
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-1h-8v8h1"/>',    // a copy of a real controller
    info: '<circle cx="8" cy="8" r="6"/><path d="M8 7.5V11M8 5v.01"/>',                               // a notice: something to do, nothing is broken
  };
  const icon = k => `<svg class="ico" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">${ICON[k]}</svg>`;
  const KIND = {real: ['real', 'Real'], 'steam-virtual': ['copy', 'Steam virtual'], virtual: ['copy', 'Virtual']};
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

  function row(c, esc) {
    const [ki, kw] = KIND[c.kind] || KIND.real;
    const title = c.label || c.name;
    const meta = [c.label ? c.name : '', c.ids, c.nodes.join(' ')].filter(Boolean).map(esc).join(' · ');
    return `<li class="controller ${esc(c.kind)}">
      ${c.slot ? `<span class="slot" title="Player slot">${esc(c.slot)}</span>` : '<span class="slot none">No slot</span>'}
      <div class="who"><b>${esc(title)}</b><span class="meta">${meta}</span></div>
      <ul class="facts">
        <li class="mode${c.known_mode ? '' : ' unknown'}"><span class="sr">Mode: </span>${esc(c.mode)}</li>
        <li class="kind">${icon(ki)}${kw}</li>
        <li class="rumble ${c.rumble ? 'yes' : 'no'}">${icon(c.rumble ? 'yes' : 'no')}${c.rumble ? 'Rumble works' : 'No rumble'}</li>
      </ul></li>`;
  }

  function summary(d) {
    if (!d.ok || !d.controllers.length) return '';
    const steam = d.controllers.filter(c => c.kind === 'steam-virtual').length, other = d.virtual - steam;
    return [`${d.connected} connected`, steam && `${steam} Steam virtual`, other && `${other} virtual`].filter(Boolean).join(' · ');
  }

  let asked = 0;                       // the newest read wins: a slow 15 s refresh never paints over a newer "Check again"
  async function draw(el, api) {
    const n = ++asked, {ok, data: d} = await api.get('list');
    if (n !== asked) return;
    const list = el.querySelector('.ctrlbody'), sum = el.querySelector('.ctrlsum');
    if (!ok || !d) { list.innerHTML = `<div class="empty"><b>No answer from the server</b>The list comes back on its own when Elaia answers again.</div>`; sum.textContent = ''; return; }
    sum.textContent = summary(d);
    let html = '';
    if (d.problem && d.ok) html += `<p class="ctrlnote" role="status">${api.esc(d.problem)}. Slots are not shown until it is fixed.</p>`;
    /* a name from before the section was renamed (pads.json, ARGUS_PADS) is still in use: per name, what to do and what happens otherwise */
    if (d.notice && d.notice.length) html += `<div class="ctrlnote oldname" role="status">${icon('info')}<ul>${d.notice.map(o => `<li><b>${api.esc(o.do)}</b> ${api.esc(o.why)}</li>`).join('')}</ul></div>`;
    if (!d.ok) html += `<div class="empty"><b>Can't read controllers here</b>${api.esc(d.problem)}</div>`;
    else if (!d.controllers.length) html += `<div class="empty"><b>No controllers connected</b>${api.esc(d.wake_hint)}</div>`;
    else html += `<ul class="ctrllist" aria-label="${plural(d.controllers.length, 'controller')}">${d.controllers.map(c => row(c, api.esc)).join('')}</ul>
      ${d.controllers.some(c => c.kind === 'steam-virtual') ? '<p class="ctrlnote">Steam virtual: a copy Steam Input makes of a real controller while Steam Input is on for it. Games that read controllers directly see the real one.</p>' : ''}`;
    list.innerHTML = html;
  }

  return {
    async show(el, api) {
      el.innerHTML = `<div class="controllers panel">
        <div class="ctrlhead"><div><h3>Controllers on this machine</h3><p class="ctrlsum" aria-live="polite"></p></div>
          <button type="button" class="ctrlcheck">Check again</button></div>
        <div class="ctrlbody"></div>
        <p class="ctrlfoot">Read from the machine Elaia runs on, every 15 seconds.</p></div>`;
      el.querySelector('.ctrlcheck').onclick = () => draw(el, api);
      await draw(el, api);
    },
    refresh(el, api) { return draw(el, api); },
  };
})());
