// Leafy Pads: the game pads this machine sees, one row each (docs/pads.md). A bundled server plugin's page script.
// Every row says the same five things in the same place: slot, name, mode, real or Steam virtual, rumble. Each state is
// an icon and a word, never colour alone. The list is redrawn on the 15 s refresh and by "Check again"; the button
// sits outside the list, so keyboard focus stays on it across redraws.
leafy.register('pads', (() => {
  const ICON = {   // 16 px line icons, aria-hidden: the word next to each one carries the meaning
    yes: '<path d="M3 8.5l3.2 3L13 4.5"/>',
    no: '<path d="M4 4l8 8M12 4l-8 8"/>',
    real: '<path d="M6 2v4M10 2v4M4.5 6h7v2.5a3.5 3.5 0 0 1-7 0zM8 12v2"/>',                      // a plug: on a cable or dongle
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-1h-8v8h1"/>',    // a copy of a real pad
  };
  const icon = k => `<svg class="ico" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">${ICON[k]}</svg>`;
  const KIND = {real: ['real', 'Real'], 'steam-virtual': ['copy', 'Steam virtual'], virtual: ['copy', 'Virtual']};
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

  function row(p, esc) {
    const [ki, kw] = KIND[p.kind] || KIND.real;
    const title = p.label || p.name;
    const meta = [p.label ? p.name : '', p.ids, p.nodes.join(' ')].filter(Boolean).map(esc).join(' · ');
    return `<li class="pad ${esc(p.kind)}">
      ${p.slot ? `<span class="slot" title="Player slot">${esc(p.slot)}</span>` : '<span class="slot none">No slot</span>'}
      <div class="who"><b>${esc(title)}</b><span class="meta">${meta}</span></div>
      <ul class="facts">
        <li class="mode${p.known_mode ? '' : ' unknown'}"><span class="sr">Mode: </span>${esc(p.mode)}</li>
        <li class="kind">${icon(ki)}${kw}</li>
        <li class="rumble ${p.rumble ? 'yes' : 'no'}">${icon(p.rumble ? 'yes' : 'no')}${p.rumble ? 'Rumble works' : 'No rumble'}</li>
      </ul></li>`;
  }

  function summary(d) {
    if (!d.ok || !d.pads.length) return '';
    const steam = d.pads.filter(p => p.kind === 'steam-virtual').length, other = d.virtual - steam;
    return [`${d.connected} connected`, steam && `${steam} Steam virtual`, other && `${other} virtual`].filter(Boolean).join(' · ');
  }

  async function draw(el, api) {
    const {ok, data: d} = await api.get('list');
    const list = el.querySelector('.padbody'), sum = el.querySelector('.padsum');
    if (!ok || !d) { list.innerHTML = `<div class="empty"><b>No answer from the server</b>The list comes back on its own when Elaia answers again.</div>`; sum.textContent = ''; return; }
    sum.textContent = summary(d);
    let html = '';
    if (d.problem && d.ok) html += `<p class="padnote" role="status">${api.esc(d.problem)} Slots are not shown until it is fixed.</p>`;
    if (!d.ok) html += `<div class="empty"><b>Can't read pads here</b>${api.esc(d.problem)}</div>`;
    else if (!d.pads.length) html += `<div class="empty"><b>No pads connected</b>${api.esc(d.wake_hint)}</div>`;
    else html += `<ul class="padlist" aria-label="${plural(d.pads.length, 'pad')}">${d.pads.map(p => row(p, api.esc)).join('')}</ul>
      ${d.pads.some(p => p.kind === 'steam-virtual') ? '<p class="padnote">Steam virtual: a copy Steam Input makes of a real pad while Steam Input is on for it. Games that read pads directly see the real one.</p>' : ''}`;
    list.innerHTML = html;
  }

  return {
    async show(el, api) {
      el.innerHTML = `<div class="pads panel">
        <div class="padhead"><div><h3>Pads on this machine</h3><p class="padsum" aria-live="polite"></p></div>
          <button type="button" class="padcheck">Check again</button></div>
        <div class="padbody"></div>
        <p class="padfoot">Read from the machine Elaia runs on, every 15 seconds.</p></div>`;
      el.querySelector('.padcheck').onclick = () => draw(el, api);
      await draw(el, api);
    },
    refresh(el, api) { return draw(el, api); },
  };
})());
