// Today (docs/home.md): what needs *you* across the realm, and where to go. It is what Elaia opens on (the bare address,
// and <base>/home, its old name). Watch is about the machines; Today is about you. In this order:
//   1. one line that says the state in words ("Nothing needs you", "2 things need you"), heading the list of
//   2. the rows that need you, the failed thing first, each with one verb-first button; between them, for the owner, the server's
//      own line on what it is doing now ("<name>: calm", "busy: …", "a game is running, …": now_line() in the server),
//   3. "Open": the media players (~/.config/argus-ui/media.json), then the links to other pages (~/.config/argus-ui/links.json),
//   4. one one-line card per section, from status v2 (api/<id>/status: line, needs, action). A new section (workouts,
//      meals, music) only has to answer that to get its card. A section with a row above has no card; no cards, no heading.
// A row whose need is met fades out (200 ms); a new row slides in. Under reduced motion they just go and come.
const home = (() => {
  let had = null;                          // how many things needed you at the last draw (null: not drawn yet)
  let seen = null;                         // the rows drawn last time, by key (null: not drawn yet)
  const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
  // the things to do: one row per broken thing on Watch first (troubleItems() in core.js: what is wrong and since when, what Argus
  // did, what you can do, and the declared fix as a hold button), then each section that says it needs you. `of`: the place it
  // belongs to; `n`: how many things the row stands for, so the line above counts what the bar counts (trouble() in core.js).
  function needs() {
    const out = troubleItems().map(it => ({key: it.key, of: it.of || 'argus', n: weight(it), mark: icon(AGENT_KEYS.includes(it.agent) ? it.agent : 'argus'), level: 'alert',
      who: it.who, text: it.what, item: it, label: it.label || 'Look at it on Watch', href: it.href}));
    PLUGINS.forEach(p => { const s = STATUS[p.id], c = needCount(p.id); if (s && s.needs) out.push({key: `needs-${p.id}`, of: p.id, n: c === true ? 1 : c,
      mark: pluginMark(p), who: placeName(p.id, p.name), level: 'needs', text: s.line, label: s.action || `Open ${p.name}`, href: url(p.id)}); });
    return visible(out.map(n => ({...n, id: n.of})));
  }
  const placeName = (id, name) => { const w = WORDS[id]; return w ? `${w.word}${w.realm && w.realm !== w.word ? ` · ${w.realm}` : ''}` : name; };
  const row = (n, fresh) => `<li class="need ${n.level}${fresh ? ' fresh' : ''}" data-key="${esc(n.key)}"><span class="nmark">${n.mark}</span><div class="nb"><p><small>${esc(n.who)}${n.item?.when ? ` · ${esc(n.item.when)}` : ''}</small>${esc(n.text)}</p>${n.item ? troubleLines(n.item) : ''}</div><div class="nacts">${n.item ? fixButton(n.item) : ''}<a class="go" href="${esc(n.href)}">${esc(n.label)}</a></div></li>`;
  // one card per section, in the bar's order: Watch, then each plugin with its status line (a static one with its version).
  // One place for each fact (4.44.0): a section with a row in the list above has no card until that row is gone.
  function cards(list) {
    const st = s => s === undefined ? 'Checking…' : s === null ? 'No news' : s.line;
    const tr = trouble(), fails = tr.n, allFailed = !tr.alerts.length && !tr.checks.length && tr.tasks.every(j => j.state === 'failed');
    const listed = new Set(list.map(n => n.of));
    return sections().filter(e => !e.kind && e.id !== 'home' && e.id !== 'phone' && !listed.has(e.id) && visible([e]).length).map(e => {
      const p = PLUGINS.find(x => x.id === e.id);
      const line = e.id === 'argus' ? (!fails ? `All ${plural(S.jobs.length, 'task')} well` : allFailed ? `${plural(fails, 'task')} failed` : `${plural(fails, 'thing')} need${fails === 1 ? 's' : ''} a look`)
        : e.id === 'olympus' ? 'Powers, weather, seasons'
        : !p ? '' : p.kind === 'server' ? st(STATUS[p.id]) : p.version ? `Version ${p.version}` : 'Open it';
      const mood = e.id === 'argus' ? (fails ? ' bad' : '') : STATUS[e.id]?.needs ? ' needs' : '';   // red: something failed; gold: waits for you
      return `<li><a class="place${mood}" href="${esc(e.href)}" data-id="${esc(e.id)}">${e.mark}<span class="pw">${words(e)}</span><span class="pl">${esc(line)}</span></a></li>`;
    }).join('');
  }
  // Open: the media players first (~/.config/argus-ui/media.json; another site, so a plain link that sends no referrer),
  // then the links to other pages on this machine (~/.config/argus-ui/links.json)
  function opens() {
    const li = (x, rel) => `<li><a class="openlink" href="${esc(x.href)}"${rel ? ' rel="noopener noreferrer"' : ''}>${LINK_MARK}<span><b>${esc(x.name)}</b>${x.what ? `<small>${esc(x.what)}</small>` : ''}</span></a></li>`;
    return (S.media || []).map(x => li(x, true)).join('') + (S.links || []).map(x => li(x, false)).join('');
  }
  let last = '';                           // the last page drawn: an unchanged page is not redrawn (focus and running fades stay)
  function draw() {
    if (here !== 'home') return;
    const list = needs(), asking = PLUGINS.some(p => p.kind === 'server' && STATUS[p.id] === undefined);
    const total = list.reduce((t, n) => t + n.n, 0);              // every failed task and every alert counts, as on the bar
    const state = total ? `${plural(total, 'thing')} need${total === 1 ? 's' : ''} you` : asking ? 'Asking every section…' : 'Nothing needs you';
    const keys = new Set(list.map(n => n.key)), links = role() === 'owner' ? opens() : '', places = cards(list);
    const now = role() === 'owner' && typeof S.now === 'string' ? S.now : '';   // what the server is doing (the server's own words)
    const html = `<section class="home" aria-label="Today">
      <section class="needs" aria-labelledby="needs-h"><h2 class="state${list.length ? ' bad' : ''}" id="needs-h">${state}</h2>
        ${now ? `<p class="now">${esc(now)}</p>` : list.length || asking ? '' : '<p class="quiet">The realm is quiet.</p>'}
        <ul class="needlist">${list.map(n => row(n, seen && !seen.has(n.key))).join('')}</ul></section>
      ${links ? `<section class="open" aria-labelledby="open-h"><h2 id="open-h">Open</h2><ul class="openlist">${links}</ul></section>` : ''}
      ${places ? `<section class="places" aria-labelledby="places-h"><h2 id="places-h">Sections</h2><ul class="placelist">${places}</ul></section>` : ''}</section>`;
    if (html.replace(/ fresh/g, '') === last) return;
    const focused = document.activeElement?.closest?.('#main a')?.getAttribute('href');   // a redraw must not drop keyboard focus
    const gone = seen && !RM.matches ? $$('#main .need[data-key]').filter(li => !keys.has(li.dataset.key)).map(li => [li, [...li.parentNode.children].indexOf(li)]) : [];
    $('#main').innerHTML = html; last = html.replace(/ fresh/g, '');
    const ul = $('#main .needlist');       // a met need leaves with a short fade where it stood, then is gone
    gone.forEach(([li, i]) => { li.classList.remove('fresh'); li.classList.add('leaving'); li.setAttribute('aria-hidden', 'true'); li.inert = true;
      ul.insertBefore(li, ul.children[i] || null);
      li.animate([{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'translateX(12px)'}], {duration: 200, easing: 'ease-in', fill: 'forwards'}).finished.then(() => li.remove(), () => li.remove()); });
    wireFixes();                           // the fix buttons are press-and-hold (holdConfirm), as on Watch
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
