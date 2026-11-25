// Mnemosyne's book reader (4.69.0, docs/mnemosyne-library.md "Reading the book"): the original EPUB or PDF in pages,
// drawn by foliate-js (MIT, vendor/THIRD-PARTY.md). Turn with a tap on the left or right third, the page buttons, the keys
// (PageDown, Space, arrows) or a swipe; a tap in the middle hides or shows the bar. The place is kept on this browser at
// once and on the server 1.5 s after the last turn, as a reading place with the book's CFI and how far through it is.
// URL: plugins/memory/reader/?id=<64 hex>&revision=<64 hex>&format=epub|pdf[&title=<library title>][&eink=1]
import './vendor/foliate-js/view.js';

const HEX = /^[a-f0-9]{64}$/;
const $ = s => document.querySelector(s);
const query = new URLSearchParams(location.search);
const id = query.get('id') || '', revision = query.get('revision') || '', format = query.get('format') || '';
// the library's title (4.69.1): used when the file has none of its own (many PDFs); shown as text only
const libraryTitle = (query.get('title') || '').replace(/\s+/g, ' ').trim().slice(0, 200) || 'Book';
const base = new URL('../../../', location.href);                  // <base>/ : this page is <base>/plugins/memory/reader/
const api = path => new URL('api/memory/' + path, base);
const libraryLink = new URL('memory', base).href;
const SAY = {
  changed: 'This book changed since your saved place; starting at the beginning.',
  waiting: 'Place kept on this device; it will sync when the library answers.',
  missing: "This book's file is not on the server. Read its text in the library instead.",
  link: 'This link to a book is not complete. Open the book from the library.',
};
function say(msg, back = false) {
  const el = $('#say'); el.textContent = msg; el.hidden = !msg;
  if (back) { const a = document.createElement('a'); a.href = libraryLink; a.textContent = 'Back to library'; el.append(' ', a); }
  // a note that only informs can be put away at once (4.69.1); it also goes on the first turn
  if (msg === SAY.changed) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'close'; b.textContent = 'Close';
    b.setAttribute('aria-label', 'Close this note'); b.addEventListener('click', () => { say(''); $('#next').focus(); });
    el.append(' ', b);
  }
}
const noteText = () => $('#say').firstChild?.nodeValue || '';             // the message alone, without its link or button

// ---- e-ink: ?eink=1, or the library's Reading settings (4.67.0, same key and the same "Automatic" test as page.js)
const EINK_UA = ua => /\b(?:BOOX|Onyx)\b/i.test(ua) || /\b(?:NoteAir|NoteMax|Tab ?Ultra|Go ?10\.3|Palma|Poke ?\d|Nova ?(?:Air|Pro|\d)|Leaf ?\d)/.test(ua);
function einkWanted() {
  if (query.get('eink') === '1') return true;
  let mode = 'auto';
  try { mode = JSON.parse(localStorage.getItem('mnemosyne-reading-settings-v1') || '{}')?.eink || 'auto'; } catch (_) { /* default */ }
  return mode === 'on' || (mode === 'auto' && (matchMedia('(update: slow)').matches || matchMedia('(monochrome)').matches || EINK_UA(navigator.userAgent)));
}
const eink = einkWanted();
document.documentElement.classList.toggle('eink', eink);
const still = eink || matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---- places: this browser's rows {id, revision, cfi, fraction, at, pending?, seen?} by book, the newest 50
const placesKey = 'mnemosyne-book-places-v1';
const CFI = /^epubcfi\([!#-&(-;=?-[\]-_a-~]{1,1015}\)$/;            // what the server keeps (plugins/memory/places.py)
function localPlaces() {
  try { const all = JSON.parse(localStorage.getItem(placesKey) || '{}'); return all && typeof all === 'object' && !Array.isArray(all) ? all : {}; }
  catch (_) { return {}; }
}
function keepLocal(row) {
  const all = localPlaces(); all[row.id] = row;
  const rows = Object.values(all).filter(r => r && HEX.test(r.id)).sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, 50);
  try { localStorage.setItem(placesKey, JSON.stringify(Object.fromEntries(rows.map(r => [r.id, r])))); return true; } catch (_) { return false; }
}
function dropLocal() {
  const all = localPlaces(); delete all[id];
  try { localStorage.setItem(placesKey, JSON.stringify(all)); } catch (_) { /* nothing kept here */ }
}
const goodPlace =r => r && r.id === id && typeof r.revision === 'string' && (r.cfi === undefined || CFI.test(r.cfi));
// A waiting row wins while the server still has the copy it replaced (`seen`), as in the library's own places (4.67.0);
// otherwise the newer by the server's time.
function pick(local, server) {
  if (!local) return server; if (!server) return local;
  if (local.pending && typeof local.seen === 'string') return server.at === local.seen ? local : server;
  return (Date.parse(server.at) || 0) >= (Date.parse(local.at) || 0) ? server : local;
}
let serverRow;                                                        // this book's recent row on the server ('' = none, undefined = not known)
async function send(row, keepalive = false) {
  const body = JSON.stringify({kind: 'recent', id, revision, offset: 0, cfi: row.cfi, ...(row.fraction !== undefined ? {fraction: row.fraction} : {})});
  try {
    const r = await fetch(api('library/place'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body, keepalive, credentials: 'same-origin'});
    if (!r.ok) throw new Error(String(r.status));
    const lists = await r.json().catch(() => null);
    const mine = lists?.recent?.find?.(x => x.id === id) || null;
    serverRow = mine || '';
    const now = localPlaces()[id];
    if (now && now.cfi === row.cfi) keepLocal({...now, pending: false, seen: undefined, at: mine?.at || now.at});
    if (last && last.cfi === row.cfi) last.pending = false;          // sent: hiding the tab must not send it again
    if (noteText() === SAY.waiting) say('');
    return true;
  } catch (_) {
    say(SAY.waiting);
    return false;
  }
}

// ---- the book
let view, last = null, timer = 0;
function remember(loc) {
  if (!loc?.cfi || !CFI.test(loc.cfi)) return;
  const sections = view.book.sections.length || 1;
  let fraction = typeof loc.fraction === 'number' ? loc.fraction : (view.renderer.index + 1) / sections;   // a PDF reports pages, not a fraction
  fraction = Math.min(1, Math.max(0, Math.round(fraction * 10000) / 10000));
  // a PDF says its page; an EPUB how far (on a narrow phone only the number, the word goes)
  const [head, word] = format === 'pdf' ? [`Page ${view.renderer.index + 1}`, ` of ${sections}`] : [`${Math.round(fraction * 100)}%`, ' read'];
  const w = document.createElement('span'); w.className = 'word'; w.textContent = word;
  $('#progress').replaceChildren(head, w);
  if (last && last.cfi === loc.cfi) return;                           // the same place again (a resize, a snap): nothing new to keep
  const before = localPlaces()[id];
  let seen = before?.pending ? before.seen : (serverRow === undefined ? undefined : serverRow ? serverRow.at : '');
  last = {id, revision, cfi: loc.cfi, fraction, at: new Date().toISOString(), pending: true, ...(typeof seen === 'string' ? {seen} : {})};
  keepLocal(last);
  clearTimeout(timer); timer = setTimeout(() => { timer = 0; send(last); }, 1500);
}
function flush() { if (last?.pending && timer) { clearTimeout(timer); timer = 0; send(last, true); } }
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush(); });
addEventListener('pagehide', flush);

// foliate drops a turn asked for while the last one settles (its paginator locks for 100 ms, longer when animated), so a quick
// second tap was lost: turns wait in line, at most three ahead.
let turning = Promise.resolve(), queued = 0;
function turn(how) {
  if (!view || queued >= 3) return;
  if (noteText() === SAY.changed) say('');                 // read, and the reader has moved on
  queued++;
  turning = turning.then(() => how === 'left' ? view.goLeft() : how === 'right' ? view.goRight() : how === 'next' ? view.next() : view.prev())
    .catch(() => {}).finally(() => { queued--; });
}
function toggleBar() { const bar = $('#bar'); bar.hidden = !bar.hidden; }
// A tap: left third back, right third on, middle the bar. Not on a link, a selection, or after a swipe (the paginator's own).
function onTap(e) {
  if (e.defaultPrevented || e.button !== 0 || e.target.closest?.('a, button, input, select, textarea, [role="button"]')) return;
  const sel = e.view?.getSelection?.(); if (sel && !sel.isCollapsed) return;
  const frame = e.view !== window ? e.view.frameElement : null;
  const x = e.clientX + (frame ? frame.getBoundingClientRect().left : 0), w = innerWidth;
  if (x < w / 3) turn('left'); else if (x > (2 * w) / 3) turn('right'); else toggleBar();
}
function onKey(e) {
  if (e.altKey || e.ctrlKey || e.metaKey || e.target.closest?.('input, select, textarea')) return;
  const k = e.key;
  if (k === 'Escape') { e.preventDefault(); toggleBar(); return; }   // the keyboard's way to the middle tap
  const how = k === 'ArrowRight' ? 'right' : k === 'ArrowLeft' ? 'left' : k === 'PageDown' || (k === ' ' && !e.shiftKey) ? 'next'
    : k === 'PageUp' || (k === ' ' && e.shiftKey) ? 'prev' : '';
  if (!how) return;
  if (k === ' ' && e.target.closest?.('a, button')) return;          // Space on a focused control presses it
  e.preventDefault(); turn(how);
}

const CONTENT_CSS = `
  html { color-scheme: ${eink ? 'light' : 'light dark'}; }
  p, li, blockquote, dd { line-height: 1.5; widows: 2; orphans: 2; }
  pre { white-space: pre-wrap !important; }
  img, svg, video { max-width: 100%; height: auto; }`;
const EINK_CSS = `
  html, body { background: #fff !important; color: #000 !important; }
  * { color: #000 !important; background-color: transparent !important; text-shadow: none !important; box-shadow: none !important;
      transition: none !important; animation: none !important; }
  a { text-decoration: underline !important; }`;

// A second guard behind the strict folder policy (an older browser might not apply it to the book's frames): book code is
// dropped and every chapter loses its scripts, on* handlers and javascript: links before foliate shows it.
const PARSE = {'application/xhtml+xml': 1, 'text/html': 1, 'image/svg+xml': 1, 'application/xml': 1, 'text/xml': 1};
function scrubDoc(text, type) {
  const doc = new DOMParser().parseFromString(text, type);
  if (doc.querySelector('parsererror')) return type === 'text/html' ? '' : scrubDoc(text, 'text/html');
  doc.querySelectorAll('script, iframe, object, embed').forEach(el => el.remove());
  for (const el of doc.querySelectorAll('*')) for (const a of [...el.attributes]) {
    if (/^on/i.test(a.name) || (/(^|:)href$|^src$|^action$/i.test(a.name) && /^\s*javascript:/i.test(a.value))) el.removeAttribute(a.name);
  }
  return type === 'text/html' ? '<!doctype html>' + doc.documentElement.outerHTML : new XMLSerializer().serializeToString(doc);
}
function scrub(e) {
  const d = e.detail, type = String(d.type || '').split(';')[0].trim().toLowerCase();
  if (/(java|ecma)script/.test(type)) { d.data = ''; return; }
  if (PARSE[type]) d.data = Promise.resolve(d.data).then(t => typeof t === 'string' ? scrubDoc(t, type) : t);
}

async function open() {
  $('#back').href = libraryLink;
  if (!HEX.test(id) || !HEX.test(revision) || !['epub', 'pdf'].includes(format)) { $('#title').textContent = libraryTitle; say(SAY.link, true); return; }
  const places = fetch(api('library/places'), {credentials: 'same-origin'}).then(r => r.ok ? r.json() : null).catch(() => null);
  let file;
  try {
    const r = await fetch(api(`library/original.${format}?id=${id}&revision=${revision}`), {credentials: 'same-origin'});
    if (!r.ok) throw new Error(String(r.status));
    file = new File([await r.blob()], `book.${format}`, {type: format === 'epub' ? 'application/epub+zip' : 'application/pdf'});
  } catch (_) { $('#title').textContent = libraryTitle; say(SAY.missing, true); return; }

  view = document.createElement('foliate-view');
  $('#book').append(view);
  view.addEventListener('relocate', e => remember(e.detail));
  view.addEventListener('load', e => { const doc = e.detail.doc; doc.addEventListener('click', onTap); doc.addEventListener('keydown', onKey); });
  try { await view.open(file); view.book.transformTarget?.addEventListener('data', scrub); }
  catch (e) { console.warn('reader: could not open the book', e); view.remove(); view = null; $('#title').textContent = libraryTitle; say(SAY.missing, true); return; }
  const t = view.book.metadata?.title;
  const title = typeof t === 'string' ? t : t && typeof t === 'object' ? Object.values(t)[0] : '';
  $('#title').textContent = title || libraryTitle; document.title = `${title || libraryTitle} · Mnemosyne`;
  const r = view.renderer;
  r.setAttribute('flow', 'paginated'); r.setAttribute('max-column-count', '1'); r.setAttribute('margin', '24px'); r.setAttribute('gap', '6%');
  if (eink) r.setAttribute('max-block-size', '4000px');              // a tall e-ink screen: the page fills it, no empty bands
  if (!still) r.setAttribute('animated', '');
  r.setStyles?.(CONTENT_CSS + (eink ? EINK_CSS : ''));

  // where to start: this book at this revision, the newer of this browser's row and the server's
  const lists = await places;
  const server = Array.isArray(lists?.recent) ? lists.recent.find(x => x?.id === id) || null : null;
  serverRow = lists ? (server || '') : undefined;
  const local = localPlaces()[id] || null;
  const mine = [local, server].filter(goodPlace);
  const same = mine.filter(x => x.revision === revision);
  const best = pick(same.find(x => x === local) || null, same.find(x => x === server) || null);
  if (mine.length && !same.length) say(SAY.changed);
  if (local && local.revision !== revision) dropLocal();               // a place in an older copy of the book means nothing now
  const cfi = best?.cfi || same.find(x => x.cfi)?.cfi || null;      // a text-reader save carries no cfi; keep the book's own
  await view.init({lastLocation: cfi, showTextStart: !cfi});
  if (best === local && local?.pending) send(local);                  // a place left waiting last time
}

document.addEventListener('keydown', onKey);
$('#book').addEventListener('click', onTap);
$('#prev').addEventListener('click', () => turn('left'));
$('#next').addEventListener('click', () => turn('right'));
open();
