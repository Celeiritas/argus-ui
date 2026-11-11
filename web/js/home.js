// Today (docs/home.md): what needs *you* across the realm, and where to go. It is what Elaia opens on (the bare address,
// and <base>/home, its old name). Watch is about the machines; Today is about you. In this order:
//   1. one line that says the state in words ("Nothing needs you", "2 things need you"), heading the list of
//   2. the rows that need you, the failed thing first, each with one verb-first button,
//   3. "Open": the links to other pages on this machine (~/.config/argus-ui/links.json),
//   4. one one-line card per section, from status v2 (api/<id>/status: line, needs, action). A new section (workouts,
//      meals, music) only has to answer that to get its card.
// A row whose need is met fades out (200 ms); a new row slides in. Under reduced motion they just go and come.
const home = (() => {
  let had = null;                          // how many things needed you at the last draw (null: not drawn yet)
  let seen = null;                         // the rows drawn last time, by key (null: not drawn yet)
  const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
  // the things to do: failed tasks first, then alerts, then each section that says it needs you. `of`: the place it belongs to.
  function needs() {
    const out = [];
    const failed = S.jobs.filter(j => j.state === 'failed'), why = failed.length === 1 && failed[0].reason ? `: ${failed[0].reason}` : '';
    if (failed.length) out.push({key: 'failed', of: 'argus', mark: icon('argus'), who: 'Argus · Watch', level: 'alert',
      text: `${plural(failed.length, 'task')} failed: ${failed.map(j => j.job).join(', ')}${why}`, label: `Look at ${plural(failed.length, 'failed task')}`, href: WATCH});
    (S.alerts || []).filter(a => a.level === 'alert').forEach(a => out.push({key: `alert-${a.file || a.job}`, of: a.link || 'argus', mark: icon(a.job.split('-')[0]),
      who: a.job, level: 'alert', text: a.message, label: a.link ? `Open ${sectionName(a.link)}` : 'Look at the alert', href: a.link ? url(a.link) : WATCH}));
    PLUGINS.forEach(p => { const s = STATUS[p.id]; if (s && s.needs) out.push({key: `needs-${p.id}`, of: p.id, mark: pluginMark(p), who: placeName(p.id, p.name),
      level: 'needs', text: s.line, label: s.action || `Open ${p.name}`, href: url(p.id)}); });
    return visible(out.map(n => ({...n, id: n.of})));
  }
  const placeName = (id, name) => { const w = WORDS[id]; return w ? `${w.word}${w.realm && w.realm !== w.word ? ` · ${w.realm}` : ''}` : name; };
  const row = (n, fresh) => `<li class="need ${n.level}${fresh ? ' fresh' : ''}" data-key="${esc(n.key)}"><span class="nmark">${n.mark}</span><p><small>${esc(n.who)}</small>${esc(n.text)}</p><a class="go" href="${esc(n.href)}">${esc(n.label)}</a></li>`;
  // one card per section, in the bar's order: Watch, then each plugin with its status line (a static one with its version)
  function cards() {
    const st = s => s === undefined ? 'Checking…' : s === null ? 'No news' : s.line;
    const fails = S.jobs.filter(j => j.state === 'failed').length;
    return sections().filter(e => !e.kind && e.id !== 'home' && e.id !== 'olympus' && visible([e]).length).map(e => {
      const p = PLUGINS.find(x => x.id === e.id);
      const line = e.id === 'argus' ? (fails ? `${plural(fails, 'task')} failed` : `All ${plural(S.jobs.length, 'task')} well`)
        : !p ? '' : p.kind === 'server' ? st(STATUS[p.id]) : p.version ? `Version ${p.version}` : 'Open it';
      const mood = e.id === 'argus' ? (fails ? ' bad' : '') : STATUS[e.id]?.needs ? ' needs' : '';   // red: something failed; gold: waits for you
      return `<li><a class="place${mood}" href="${esc(e.href)}" data-id="${esc(e.id)}">${e.mark}<span class="pw">${words(e)}</span><span class="pl">${esc(line)}</span></a></li>`;
    }).join('');
  }
  function opens() {
    return (S.links || []).map(x => `<li><a class="openlink" href="${esc(x.href)}">${LINK_MARK}<span><b>${esc(x.name)}</b>${x.what ? `<small>${esc(x.what)}</small>` : ''}</span></a></li>`).join('');
  }
  let last = '';                           // the last page drawn: an unchanged page is not redrawn (focus and running fades stay)
  function draw() {
    if (here !== 'home') return;
    const list = needs(), asking = PLUGINS.some(p => p.kind === 'server' && STATUS[p.id] === undefined);
    const state = list.length ? `${plural(list.length, 'thing')} need${list.length === 1 ? 's' : ''} you` : asking ? 'Asking every section…' : 'Nothing needs you';
    const keys = new Set(list.map(n => n.key)), links = role() === 'owner' ? opens() : '';
    const html = `<section class="home" aria-label="Today">
      <section class="needs" aria-labelledby="needs-h"><h2 class="state${list.length ? ' bad' : ''}" id="needs-h">${state}</h2>
        ${list.length || asking ? '' : '<p class="quiet">The realm is quiet.</p>'}
        <ul class="needlist">${list.map(n => row(n, seen && !seen.has(n.key))).join('')}</ul></section>
      ${links ? `<section class="open" aria-labelledby="open-h"><h2 id="open-h">Open</h2><ul class="openlist">${links}</ul></section>` : ''}
      <section class="places" aria-labelledby="places-h"><h2 id="places-h">Sections</h2><ul class="placelist">${cards()}</ul></section></section>`;
    if (html.replace(/ fresh/g, '') === last) return;
    const focused = document.activeElement?.closest?.('#main a')?.getAttribute('href');   // a redraw must not drop keyboard focus
    const gone = seen && !RM.matches ? $$('#main .need[data-key]').filter(li => !keys.has(li.dataset.key)).map(li => [li, [...li.parentNode.children].indexOf(li)]) : [];
    $('#main').innerHTML = html; last = html.replace(/ fresh/g, '');
    const ul = $('#main .needlist');       // a met need leaves with a short fade where it stood, then is gone
    gone.forEach(([li, i]) => { li.classList.remove('fresh'); li.classList.add('leaving'); li.setAttribute('aria-hidden', 'true'); li.inert = true;
      ul.insertBefore(li, ul.children[i] || null);
      li.animate([{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'translateX(12px)'}], {duration: 200, easing: 'ease-in', fill: 'forwards'}).finished.then(() => li.remove(), () => li.remove()); });
    if (focused) $$('#main a').find(a => a.getAttribute('href') === focused)?.focus();
    if (had > 0 && !list.length) look.react('content');       // Needs you just emptied: Argus gives a slow, contented blink
    had = list.length; seen = keys;
  }
  function show() { draw(); askStatus().then(draw); }      // the 15 s refresh calls this too: draw from what we know, then ask again
  // the greeting by the viewer's clock, then the date and the weather (core.js render() puts it under the name)
  function greet() {
    const h = new Date().getHours(), wx = ($('#wxText')?.textContent || '').trim();
    return [h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening',
      new Date().toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'}) + (wx ? ` · ${wx}` : '')];
  }
  return {show, greet, draw};
})();
