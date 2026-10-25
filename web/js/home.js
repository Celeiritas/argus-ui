// Home (docs/home.md): what needs *you* across the realm, and where to go. Watch is about the machines; Home is about you.
// The header greets you (core.js render), then one "Needs you" list built from alert files, failed tasks and each server
// plugin's status (Mentor's too), then a row of places with their one line. Status v2: {line, needs, action} from api/<id>/status.
const home = (() => {
  const lines = {};                        // section id -> its last status (undefined: still asking, null: none)
  let had = null;                          // how many things needed you at the last draw (null: not drawn yet)
  const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
  async function ask() {
    await Promise.all(PLUGINS.filter(p => p.kind === 'server').map(p =>
      fetch(url(`api/${p.id}/status`), {cache: 'no-store'}).then(r => r.json()).then(j => { lines[p.id] = j && j.line ? j : null; }).catch(() => { lines[p.id] = null; })));
  }
  // the things to do, most urgent first: alerts, then failed tasks, then each section that says it needs you
  function needs() {
    const out = [], icon = k => `<img src="static/icons/${esc(k)}.png" alt="">`;
    (S.alerts || []).filter(a => a.level === 'alert').forEach(a => out.push({mark: icon(a.job.split('-')[0]), text: a.message, who: a.job,
      label: a.link ? `Open ${sectionName(a.link)}` : 'Look at the alert', href: url(a.link || ''), level: 'alert'}));
    const failed = S.jobs.filter(j => j.state === 'failed');
    if (failed.length) out.push({mark: icon('argus'), text: `${plural(failed.length, 'task')} failed: ${failed.map(j => j.job).join(', ')}`, who: 'Argus · Watch',
      label: `Look at ${plural(failed.length, 'failed task')}`, href: url(''), level: 'alert'});
    PLUGINS.forEach(p => { const s = lines[p.id]; if (s && s.needs) out.push({mark: pluginMark(p), text: s.line, who: p.name, label: s.action || `Open ${p.name}`, href: url(p.id), level: 'needs'}); });
    return out;
  }
  const row = n => `<li class="need ${n.level}"><span class="nmark">${n.mark}</span><p><small>${esc(n.who)}</small>${esc(n.text)}</p><a class="go" href="${n.href}">${esc(n.label)}</a></li>`;
  // the places: Watch, then every section in the section bar's order, each with its one line
  function places() {
    const st = s => s === undefined ? 'Checking…' : s === null ? 'No news' : s.line;
    const fails = S.jobs.filter(j => j.state === 'failed').length, mp = PLUGINS.find(p => p.id === 'mentor');
    const place = (href, mark, name, line, bad) => `<li><a class="place ${bad ? 'bad' : ''}" href="${href}">${mark}<b>${esc(name)}</b><small>${esc(line)}</small></a></li>`;
    return [place(url(''), '<img src="static/icons/argus.png" alt="">', 'Watch', fails ? `${plural(fails, 'task')} failed` : `All ${plural(S.jobs.length, 'task')} well`, fails > 0)]
      .concat(mp ? [place(url('mentor'), pluginMark(mp), mp.name, st(lines.mentor))] : [])
      .concat([place(url('olympus'), '<img src="static/icons/olympus.png" alt="">', 'Olympus', 'Powers, weather, seasons')])
      .concat(PLUGINS.filter(p => p !== mp).map(p => place(url(p.id), pluginMark(p), p.name, p.kind === 'server' ? st(lines[p.id]) : p.version ? `Version ${p.version}` : 'Open it')))
      .concat((S.links || []).map(x => place(esc(x.href), '<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16" fill="#1C2127" stroke="#2A9D8F" stroke-width="1.5"/><path d="M20 11h5v5M25 11l-8 8M23 20v4a1 1 0 0 1-1 1H12a1 1 0 0 1-1-1V14a1 1 0 0 1 1-1h4" fill="none" stroke="#A7B6C4" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>', x.name, `Open ${x.what || x.name}`)))
      .join('');
  }
  function draw() {
    if (here !== 'home') return;
    const list = needs(), focused = document.activeElement?.closest?.('#main a')?.getAttribute('href');   // a redraw must not drop keyboard focus
    const asking = PLUGINS.some(p => p.kind === 'server' && lines[p.id] === undefined);
    $('#main').innerHTML = `<section class="home" aria-label="Home">
      <section class="needs" aria-labelledby="needs-h"><h2 id="needs-h">Needs you${list.length ? ` <span class="count">${list.length}</span>` : ''}</h2>
        ${list.length ? `<ul class="needlist">${list.map(row).join('')}</ul>`
          : `<p class="quiet">${asking ? 'Asking every section…' : 'Nothing needs you. The realm is quiet.'}</p>`}</section>
      <section class="places" aria-labelledby="places-h"><h2 id="places-h">Places</h2><ul class="placelist">${places()}</ul></section></section>`;
    if (focused) $$('#main a').find(a => a.getAttribute('href') === focused)?.focus();
    if (had > 0 && !list.length) look.react('content');       // Needs you just emptied: Argus gives a slow, contented blink
    had = list.length;
  }
  function show() { draw(); ask().then(draw); }      // the 15 s refresh calls this too: draw from what we know, then ask again
  // the header: a greeting by the viewer's clock, then the date and the weather (core.js render() calls this)
  function greet() {
    const h = new Date().getHours(), wx = ($('#wxText')?.textContent || '').trim();
    return [h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening',
      new Date().toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'}) + (wx ? ` · ${wx}` : '')];
  }
  return {show, greet};
})();
