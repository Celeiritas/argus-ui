// Today (docs/home.md): what needs *you* across the realm, and where to go. It is what Elaia opens on (the bare address,
// and <base>/home, its old name). Watch is about the machines; Today is about you. In this order:
//   0. for the owner, the server's own line on what it is doing now, a band across the top in the server's colours ("<name>: calm",
//      "<name>: busy with …", "<name>: a game is running, …": now_line() in the server; its name, now_name, drawn in the name colour),
//   1. one line that says the state in words ("Nothing needs you", "2 things need you"), heading the list of
//   2. the rows that need you, the failed thing first, each with one verb-first button,
//   3. "Open": jumps to another app or site, as compact as 4.44.0: the media players (~/.config/argus-ui/media.json), then the
//      links to other pages (~/.config/argus-ui/links.json), one row of chips that wraps, no labels. A link with a "group" gets
//      that group's small label in front of its chips (opens()),
//   4. "Sections": the parts of Elaia, one compact tile each, called by its god's name (wordOf in core.js), with its live line
//      from status v2 (api/<id>/status: line, needs, action), cut at a word to two lines (fitLines). A new section (workouts,
//      meals, music) only has to answer that to get its tile. A section with a row above has no tile; no tiles, no heading.
//      A quiet section (server/quiet.py: Mentor) keeps its tile and its line, and never has a row.
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
      who: it.who, text: it.what, item: it, label: it.label || `Open ${wordOf('argus')}`, href: it.href}));
    PLUGINS.forEach(p => { const s = STATUS[p.id], c = needCount(p.id); if (s && s.needs && !isQuiet(p.id)) out.push({key: `needs-${p.id}`, of: p.id, n: c === true ? 1 : c,
      mark: pluginMark(p), who: wordOf(p.id, p.name), level: 'needs', text: s.line, label: s.action || `Open ${wordOf(p.id, p.name)}`, href: url(p.id)}); });
    return visible(out.map(n => ({...n, id: n.of})));
  }
  // a failed task's row: "Mark as known" (the owner's; core.js markKnown) beside the way to Argus, so a failure he already
  // knows about leaves Today without opening Argus
  const knownBtn = it => { const j = it?.known && (S.jobs || []).find(x => x.job === it.known);
    return j && role() === 'owner' ? `<button type="button" class="knownbtn" data-known="${esc(j.job)}" data-on="1" aria-label="Mark ${esc(j.name)} as known, low priority">Mark as known</button>` : ''; };
  const row = (n, fresh) => `<li class="need ${n.level}${fresh ? ' fresh' : ''}" data-key="${esc(n.key)}"><span class="nmark">${n.mark}</span><div class="nb"><p><small>${esc(n.who)}${n.item?.when ? ` · ${esc(n.item.when)}` : ''}</small>${esc(n.text)}</p>${n.item ? troubleLines(n.item) : ''}</div><div class="nacts">${n.item ? fixButton(n.item) : ''}<a class="go" href="${esc(n.href)}">${esc(n.label)}</a>${knownBtn(n.item)}</div></li>`;
  // one card per section, in the bar's order: Watch, then each plugin with its status line (a static one with its version).
  // One place for each fact (4.44.0): a section with a row in the list above has no card until that row is gone.
  function cards(list) {
    const st = s => s === undefined ? 'Checking…' : s === null ? 'No news' : s.line;
    const tr = trouble(), fails = tr.n, allFailed = !tr.alerts.length && !tr.checks.length && tr.tasks.every(j => j.state === 'failed'), kn = tr.known.length;
    const listed = new Set(list.map(n => n.of));
    return sections().filter(e => !e.kind && e.id !== 'home' && e.id !== 'phone' && !listed.has(e.id) && visible([e]).length).map(e => {
      const p = PLUGINS.find(x => x.id === e.id);
      // a task marked known is told apart, never in red: "All 12 tasks well · 1 known"
      const line = e.id === 'argus' ? (!fails ? `All ${plural(S.jobs.length, 'task')} well${kn ? ` · ${kn} known` : ''}` : allFailed ? `${plural(fails, 'task')} failed` : `${plural(fails, 'thing')} need${fails === 1 ? 's' : ''} a look`)
        : e.id === 'olympus' ? 'Powers, weather, seasons'
        : !p ? '' : p.kind === 'server' ? st(STATUS[p.id]) : p.version ? `Version ${p.version}` : 'Open it';
      const mood = e.id === 'argus' ? (fails ? ' bad' : '') : STATUS[e.id]?.needs && !isQuiet(e.id) ? ' needs' : '';   // red: something failed; gold: waits for you
      // a " · " keeps its dot on the line before (a no-break space), so a wrapped line never starts with "·"
      return `<li><a class="place${mood}" href="${esc(e.href)}" data-id="${esc(e.id)}">${e.mark}<span class="pw">${words(e)}</span><span class="pl">${esc(line).replace(/ · /g, '\u00a0· ')}</span></a></li>`;
    }).join('');
  }
  // Open: the media players first (~/.config/argus-ui/media.json; another site, so a plain link that sends no referrer),
  // then the links to other pages on this machine (~/.config/argus-ui/links.json). As compact as 4.44.0 (the owner,
  // 2026-11-13): one list of chips that wraps, no labels. Only a link with a "group" gets a small label, in front of that
  // group's chips: on a phone the label and its chips flow in the same wrap as the others (argus.css), on a wide screen the
  // groups sit side by side. The chips without a group come first, unlabelled.
  function opens() {
    const li = (x, rel) => `<li><a class="openlink" href="${esc(x.href)}"${rel ? ' rel="noopener noreferrer"' : ''}>${LINK_MARK}<span><b>${esc(x.name)}</b>${x.what ? `<small>${esc(x.what)}</small>` : ''}</span></a></li>`;
    const groups = new Map();              // label -> chips, in the order they first come
    let loose = (S.media || []).map(x => li(x, true)).join('');
    (S.links || []).forEach(x => { const g = typeof x.group === 'string' ? x.group.trim() : '';
      if (g) groups.set(g, (groups.get(g) || '') + li(x, false)); else loose += li(x, false); });
    if (!groups.size) return loose ? `<ul class="openlist">${loose}</ul>` : '';
    return `<div class="opengroups">${loose ? `<ul class="openlist">${loose}</ul>` : ''}${[...groups].map(([g, chips], i) => `<div class="og"><h3 class="opengroup" id="open-g${i}">${esc(g)}</h3><ul class="openlist" aria-labelledby="open-g${i}">${chips}</ul></div>`).join('')}</div>`;
  }
  // a tile's line in two lines at most, cut after the last word that fits, with "…" (never inside a word, unless one word is
  // wider than the tile). The cut words stay in the link's name as a .sr span, so a screen reader hears the whole line.
  const over = el => el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
  function fitLines() {
    $$('#main .place .pl').forEach(pl => {
      const full = pl.textContent; pl.textContent = full; pl.classList.remove('cut');
      if (!full || !over(pl)) return;
      pl.classList.add('cut');
      const fits = h => { pl.textContent = h; return !over(pl); };
      const tok = full.split(/(\s+)/), headOf = k => tok.slice(0, 2 * k - 1).join('').replace(/[\s,;:·.\-–—]+$/, '');
      let lo = 0, hi = Math.ceil(tok.length / 2) - 1;           // the most words that fit before "…"
      while (lo < hi) { const m = (lo + hi + 1) >> 1; if (fits(headOf(m))) lo = m; else hi = m - 1; }
      let head = lo ? headOf(lo) : '';
      if (!head) { let a = 0, b = full.length - 1; while (a < b) { const m = (a + b + 1) >> 1; if (fits(full.slice(0, m))) a = m; else b = m - 1; } head = full.slice(0, a); }
      pl.innerHTML = `${esc(head)}<span class="sr">${esc(full.slice(head.length))}</span>`;
    });
  }
  let fitting = 0;
  addEventListener('resize', () => { cancelAnimationFrame(fitting); fitting = requestAnimationFrame(() => here === 'home' && fitLines()); });
  document.fonts?.ready.then(() => here === 'home' && fitLines());   // the first draw may measure before Nunito is in
  // the server's band: its name (now_name, from the server) in the name colour, the rest in the words colour; the same text
  // as before, so a line without that name (a learner, an older server) is drawn plain
  function nowBand(now) {
    const nm = typeof S.now_name === 'string' && S.now_name && now.startsWith(S.now_name + ': ') ? S.now_name : '';
    return `<p class="now">${nm ? `<b class="nowname">${esc(nm)}</b>${esc(now.slice(nm.length))}` : esc(now)}</p>`;
  }
  let last = '';                           // the last page drawn: an unchanged page is not redrawn (focus and running fades stay)
  function draw() {
    if (here !== 'home') return;
    const list = needs(), asking = PLUGINS.some(p => p.kind === 'server' && STATUS[p.id] === undefined);
    const total = list.reduce((t, n) => t + n.n, 0);              // every failed task and every alert counts, as on the bar
    const state = total ? `${plural(total, 'thing')} need${total === 1 ? 's' : ''} you` : asking ? 'Asking every section…' : 'Nothing needs you';
    const keys = new Set(list.map(n => n.key)), links = role() === 'owner' ? opens() : '', places = cards(list);
    const now = role() === 'owner' && typeof S.now === 'string' ? S.now : '';   // what the server is doing (the server's own words)
    // the server's line stands above the list, on its own: inside the list's panel it read as one more thing to do
    const html = `<section class="home" aria-label="Today">${now ? nowBand(now) : ''}
      <section class="needs" aria-labelledby="needs-h"><h2 class="state${list.length ? ' bad' : ''}" id="needs-h">${state}</h2>
        ${now || list.length || asking ? '' : '<p class="quiet">The realm is quiet.</p>'}
        <ul class="needlist">${list.map(n => row(n, seen && !seen.has(n.key))).join('')}</ul></section>
      ${links ? `<section class="open" aria-labelledby="open-h"><h2 id="open-h">Open</h2>${links}</section>` : ''}
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
    fitLines();                            // the tiles' lines, cut at a word to their two lines
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
