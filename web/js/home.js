// Today (docs/home.md): what needs *you* across the realm. It is what LeafyGrove opens on (the bare address, and <base>/home,
// its old name). Watch is about the machines; Today is about you. The top bar (a computer) and the bottom bar with More (a
// phone) do the navigating (4.54.0, docs/home.md "One way to each place"), so Today is the same at every width, in the
// owner's order of what matters:
//   1. a line when today.json cannot be used (the owner's),
//   2. what needs you: one line that says the state ("2 things need you"), then the rows, sorted by what it costs to leave
//      them (needRank: what broke, then backups, then approvals, then the rest), each with one verb-first button; the server's
//      own line on what it is doing under them. When nothing needs you, one band says both: "Nothing needs you" and the
//      server's line ("<name>: calm", now_line() in the server; its name, now_name, in the name colour),
//   3. the devices line (devices.js),
//   4. one line for each section with news (its status v2 line, api/<id>/status), called by its god's name (wordOf in core.js),
//      ending in the chevron that says it takes you there. A section with a row above has no line; Argus's news is its rows.
//   The owner makes Today his own (4.50.0, Edit Today in More's Settings, today-edit.js): which sections may have a line, in his
//   order, under his names, and the names and order of More's media and links. A learner's page has the default.
// A row whose need is met fades out (200 ms); a new row slides in. Under reduced motion they just go and come.
const home = (() => {
  let had = null;                          // how many things needed you at the last draw (null: not drawn yet)
  let seen = null;                         // the rows drawn last time, by key (null: not drawn yet)
  const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
  // a list in the owner's saved order (today.json "order"): the ones he placed first, in his order, then the rest in their own
  // order (a section or link that is new since he saved goes at the end); `key` gives each one's id
  const ordered = (list, order, key) => { const at = new Map((Array.isArray(order) ? order : []).map((k, i) => [k, i]));
    return list.map((x, i) => [x, at.has(key(x)) ? at.get(key(x)) : at.size + i]).sort((a, b) => a[1] - b[1]).map(x => x[0]); };
  // Today's sections and More's media and links as the owner set them (Edit Today, today-edit.js; the second also More,
  // core.js drawMore): all of them, in order. A section with `shown` (may it have a line on Today); a player or link with its
  // key and its name (his, else the file's)
  function tileList() {
    const t = myToday().tiles || {}, hid = new Set(t.hidden || []);
    return ordered(sections().filter(e => !e.kind && e.id !== 'home' && e.id !== 'phone' && visible([e]).length), t.order, e => e.id).map(e => ({...e, shown: !hid.has(e.id)}));
  }
  function openList() {
    const o = myToday().open || {};
    const all = [...(S.media || []).map(x => ({...x, media: true})), ...(S.links || [])].map(x => ({...x, key: openKey(x, x.media), def: x.name, name: openName(x, x.media)}));
    return ordered(all, o.order, x => x.key);
  }
  // what it costs to leave a row (the owner, 2026-11-16: a backup with no off-site copy above workouts): what broke on Watch first,
  // then Mnemosyne (your data), then Zeus (an approval waits), then everything else; the same rank keeps its own order
  const needRank = n => n.level === 'alert' ? 0 : n.of === 'memory' ? 1 : n.of === 'throne' ? 2 : 3;
  // the things to do: one row per broken thing on Watch (troubleItems() in core.js: what is wrong and since when, what Argus
  // did, what you can do, and the declared fix as a hold button), then each section that says it needs you. `of`: the place it
  // belongs to; `n`: how many things the row stands for, so the line above counts what the bar counts (trouble() in core.js).
  function needs() {
    const out = troubleItems().map(it => ({key: it.key, of: it.of || 'argus', n: weight(it), mark: icon(AGENT_KEYS.includes(it.agent) ? it.agent : 'argus'), level: 'alert',
      who: it.who, text: it.what, item: it, label: it.label || `Open ${wordOf('argus')}`, href: it.href}));
    PLUGINS.forEach(p => { const s = STATUS[p.id], c = needCount(p.id); if (s && s.needs && !isQuiet(p.id)) out.push({key: `needs-${p.id}`, of: p.id, n: c === true ? 1 : c,
      mark: pluginMark(p), who: wordOf(p.id, p.name), level: 'needs', text: s.line, label: s.action || `Open ${wordOf(p.id, p.name)}`, href: url(p.id)}); });
    return visible(out.map((n, i) => ({...n, id: n.of, at: i}))).sort((a, b) => needRank(a) - needRank(b) || a.at - b.at);
  }
  // a failed task's row: "Mark as known" (the owner's; core.js markKnown) beside the way to Argus, so a failure he already
  // knows about leaves Today without opening Argus
  const knownBtn = it => { const j = it?.known && (S.jobs || []).find(x => x.job === it.known);
    return j && role() === 'owner' ? `<button type="button" class="knownbtn" data-known="${esc(j.job)}" data-on="1" aria-label="Mark ${esc(j.name)} as known, low priority">Mark as known</button>` : ''; };
  // a row's words: the first sentence at reading size, the rest under it a size smaller (visual review 2026-11-17: a four-line
  // backup row pushed its button down a phone's screen); a row of one sentence stays as it is
  const lead = t => { const s = String(t || ''), m = s.match(/^(.+?[.!?])\s+(\S[\s\S]*)$/); return m ? [m[1], m[2]] : [s, '']; };
  const row = (n, fresh) => { const [first, rest] = n.item ? [n.text, ''] : lead(n.text);
    return `<li class="need ${n.level}${fresh ? ' fresh' : ''}" data-key="${esc(n.key)}"><span class="nmark">${n.mark}</span><div class="nb"><p><small>${esc(n.who)}${n.item?.when ? ` · ${esc(n.item.when)}` : ''}</small>${esc(first)}</p>${rest ? `<p class="ndetail">${esc(rest)}</p>` : ''}${n.item ? troubleLines(n.item) : ''}</div><div class="nacts">${n.item ? fixButton(n.item) : ''}<a class="go" href="${esc(n.href)}">${esc(n.label)}</a>${knownBtn(n.item)}</div></li>`; };
  // a line wraps only where a reader would expect it (no-break spaces): a " · " keeps its dot on the line before, so a wrapped
  // line never starts with "·", and a count keeps its word ("1 Steam virtual", never "1" at a line's end, 4.49.0)
  const keep = s => s.replace(/ · /g, '\u00a0· ').replace(/\b(\d+) (?=\p{L})/gu, '$1\u00a0');
  // one line for each section with news: a server plugin the owner lets onto Today (Edit Today) with a status line and no row
  // above (Mentor's "6 cards due", Mnemosyne's last backup when it is fine), a link to its section ending in the chevron
  function newsLines(list) {
    const listed = new Set(list.map(n => n.of));
    const lines = tileList().filter(e => e.shown && !listed.has(e.id) && STATUS[e.id]?.line && PLUGINS.some(p => p.id === e.id && p.kind === 'server'));
    return lines.length ? `<section class="news" aria-labelledby="news-h"><h2 id="news-h">Sections</h2><ul class="newslist">${lines.map(e =>
      `<li><a class="qline" href="${esc(e.href)}" data-id="${esc(e.id)}">${e.mark}<span class="qw"><b>${esc(e.word)}</b><span class="qt">${esc(keep(STATUS[e.id].line))}</span>${needSay(e.count)}</span>${CHEVRON}</a></li>`).join('')}</ul></section>` : '';
  }
  // the server's band: its name (now_name, from the server) in the name colour, the rest in the words colour; the same text
  // as before, so a line without that name (a learner, an older server) is drawn plain
  function nowBand(now) {
    const nm = typeof S.now_name === 'string' && S.now_name && now.startsWith(S.now_name + ': ') ? S.now_name : '';
    return `<p class="now">${nm ? `<b class="nowname">${esc(nm)}</b>${esc(now.slice(nm.length))}` : esc(now)}</p>`;
  }
  let last = '';                           // the last page drawn: an unchanged page is not redrawn (focus and running fades stay)
  function draw() {
    if (here !== 'home' || todayEdit.on()) return;           // Edit Today has the page: the 15 s refresh must not draw over it
    // Edit Today pressed in More on another page comes here as <base>/#edit: it opens once (the address loses the #edit)
    if (location.hash === '#edit') { history.replaceState(null, '', location.pathname + location.search); if (role() === 'owner') return todayEdit.start(); }
    const list = needs(), asking = PLUGINS.some(p => p.kind === 'server' && STATUS[p.id] === undefined);
    const total = list.reduce((t, n) => t + n.n, 0);              // every failed task and every alert counts, as on the bar
    const state = total ? `${plural(total, 'thing')} need${total === 1 ? 's' : ''} you` : asking ? 'Asking every section…' : 'Nothing needs you';
    const keys = new Set(list.map(n => n.key));
    const now = role() === 'owner' && typeof S.now === 'string' ? S.now : '';   // what the server is doing (the server's own words)
    const why = role() === 'owner' && typeof S.today_problem === 'string' ? S.today_problem : '';   // today.json cannot be used
    const problem = why ? `<p class="people-problem today-problem" role="status">${esc(why)}</p>` : '';
    const rows = `<ul class="needlist">${list.map(n => row(n, seen && !seen.has(n.key))).join('')}</ul>`;
    // what needs you first, in a solid card, the server's line under it; else one band for "Nothing needs you" and that line
    const needsPart = now && !list.length ? `<section class="needs calm" aria-labelledby="needs-h"><h2 class="state" id="needs-h">${state}</h2>${nowBand(now)}${rows}</section>`
      : `<section class="needs${list.length ? ' first' : ''}" aria-labelledby="needs-h"><h2 class="state${list.length ? ' bad' : ''}" id="needs-h">${state}</h2>
        ${now || list.length || asking ? '' : '<p class="quiet">The realm is quiet.</p>'}
        ${rows}</section>${now ? nowBand(now) : ''}`;
    const html = `<section class="home${PHONE.matches ? ' phone' : ''}" aria-label="Today">${problem}${needsPart}${devices.line()}${newsLines(list)}</section>`;
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
      new Date().toLocaleDateString([], PHONE.matches ? {weekday: 'short', month: 'short', day: 'numeric'} : {weekday: 'long', month: 'long', day: 'numeric'}) + (wx ? ` · ${wx}` : '')];   // a phone: "Mon, Nov 16", on one line
  }
  return {show, greet, draw, tileList, openList, needRank, reset: () => { last = ''; }};
})();
