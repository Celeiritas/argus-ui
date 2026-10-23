// Home (docs/home.md): one tile per section with the line that says whether it needs you, and the alerts first.
// Watch's line comes from the page state; Learn's from Mentor's stats; a server plugin's from its api/<id>/status.
const home = (() => {
  const lines = {};                        // section id -> its last line (undefined: still asking, null: none)
  const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
  function watchLine() {
    const c = s => S.jobs.filter(j => j.state === s).length, up = (S.alerts || []).filter(a => a.level === 'alert').length;
    const bad = [c('failed') && `${plural(c('failed'), 'task')} failed`, up && plural(up, 'alert'), c('frozen') && `${c('frozen')} stone`].filter(Boolean);
    return {text: bad.length ? bad.join(' · ') : `All ${plural(S.jobs.length, 'task')} well`, needs: !!(c('failed') || up)};
  }
  function learnLine(s) {
    if (s.due) return `${plural(s.due, 'card')} due${s.learn ? ` · ${s.learn} to learn` : ''}`;
    if (s.learn) return `${s.learn} to learn`;
    return s.new ? `${plural(s.new, 'new card')} waiting` : 'Nothing due';
  }
  async function ask() {
    const jobs = PLUGINS.filter(p => p.kind === 'server').map(p =>
      fetch(url(`api/${p.id}/status`), {cache: 'no-store'}).then(r => r.json()).then(j => { lines[p.id] = j.line || null; }).catch(() => { lines[p.id] = null; }));
    if (AGENT_KEYS.includes('mentor')) jobs.push(fetch(url('api/mentor/stats'), {cache: 'no-store'}).then(r => r.json())
      .then(s => { lines.mentor = learnLine(s); }).catch(() => { lines.mentor = null; }));
    await Promise.all(jobs);
  }
  const tile = (href, mark, name, what, line, needs) => `<li><a class="tile ${needs ? 'needs' : ''}" href="${href}">${mark}
    <span class="tname"><b>${esc(name)}</b><small>${esc(what)}</small></span>${line === '' ? '' : `<span class="tline">${line === undefined ? 'Checking…' : line === null ? 'No news' : esc(line)}</span>`}</a></li>`;
  const icon = k => `<img src="static/icons/${k}.png" alt="">`;
  function draw() {
    if (here !== 'home') return;
    const w = watchLine(), up = (S.alerts || []).filter(a => a.level === 'alert'), mentor = S.personas.find(p => p.key === 'mentor');
    const tiles = [tile(url(''), icon('argus'), 'Argus', 'Watch', w.text, w.needs)]
      .concat(mentor ? [tile(url('mentor'), icon('mentor'), mentor.name, mentor.domain.split('·')[0].trim(), lines.mentor, false)] : [])
      .concat([tile(url('olympus'), icon('olympus'), 'Olympus', 'Playground', 'Powers, weather, seasons', false)])
      .concat(PLUGINS.map(p => tile(url(p.id), pluginMark(p), p.name, p.subtitle || 'Plugin', p.kind === 'server' ? lines[p.id] : (p.version ? `Version ${p.version}` : ''), false)));
    const focused = document.activeElement?.closest?.('.tile')?.getAttribute('href');   // a redraw must not drop keyboard focus
    $('#main').innerHTML = `<section class="home" aria-labelledby="home-h"><h2 class="sr" id="home-h">Sections</h2>
      ${up.length ? `<div class="home-alerts" role="group" aria-label="Alerts">${up.map(alertNote).join('')}</div>` : ''}
      <ul class="tiles">${tiles.join('')}</ul></section>`;
    if (focused) $(`.tile[href="${CSS.escape(focused)}"]`)?.focus();
  }
  function show() { draw(); ask().then(draw); }      // the 15 s refresh calls this too: draw from what we know, then ask again
  return {show};
})();
