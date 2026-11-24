// Mnemosyne's book reader (4.69.0, docs/mnemosyne-library.md "Reading the book"): the original EPUB or PDF in pages,
// edge taps, keys and swipes, e-ink, the place kept on this browser and the server, and a book's own scripts never running.
// The reader's real files and foliate-js, synthetic API answers, books made by tests/fixtures/books/make-books.py.
const {chromium} = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path'), assert = require('assert/strict'), {execFileSync} = require('child_process');
const root = path.resolve(__dirname, '..');
const books = fs.mkdtempSync(path.join(os.tmpdir(), 'reader-books-'));
execFileSync(process.env.PYTHON || 'python3', [path.join(root, 'tests/fixtures/books/make-books.py'), books]);
// what the server sends with the reader's folder ("open_folder_policy": "strict", STRICT_FOLDER_HEADERS; tests/gate_test.py)
const STRICT = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline' blob:; img-src 'self' data: blob:; " +
  "font-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' blob: data:; worker-src 'self' blob:; frame-src 'self' blob:; " +
  "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'";
const ID = 'a'.repeat(64), REV = 'b'.repeat(64), OLD = 'c'.repeat(64);
const server = {places: {recent: [], saved: []}, down: false, missing: false, posts: []};
const MIME = {'.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.bcmap': 'application/octet-stream'};

async function page(browser, opts = {}) {
  const ctx = await browser.newContext({viewport: opts.viewport || {width: 375, height: 812}, reducedMotion: opts.motion ? 'no-preference' : 'reduce', hasTouch: !!opts.touch});
  const p = await ctx.newPage(); p.errors = []; p.csp = [];
  p.on('pageerror', e => p.errors.push(e.message));
  p.on('console', m => { if (/Content Security Policy/i.test(m.text())) p.csp.push(m.text()); });
  await p.route('**/*', async route => {
    const u = new URL(route.request().url()), at = u.pathname.replace(/^\/(?:argus\/)?/, '');
    const json = (data, status = 200) => route.fulfill({json: data, status});
    if (at === 'api/memory/library/places') return server.down ? json({msg: 'Library unavailable.'}, 503) : json(server.places);
    if (at === 'api/memory/library/place') {
      if (server.down) return json({msg: 'Library unavailable.'}, 503);
      const body = JSON.parse(route.request().postData()); server.posts.push(body);
      const row = {id: body.id, revision: body.revision, offset: body.offset, cfi: body.cfi, fraction: body.fraction, at: new Date(Date.now() + server.posts.length).toISOString()};
      server.places.recent = [row, ...server.places.recent.filter(r => r.id !== row.id)];
      return json(server.places);
    }
    const original = at.match(/^api\/memory\/library\/original\.(epub|pdf)$/);
    if (original) {
      if (server.missing || u.searchParams.get('id') !== ID || u.searchParams.get('revision') !== REV) return json({msg: 'Original is unavailable or too large'}, 404);
      return route.fulfill({body: fs.readFileSync(path.join(books, `tiny.${original[1]}`)), contentType: original[1] === 'epub' ? 'application/epub+zip' : 'application/pdf'});
    }
    if (at === 'memory') return route.fulfill({contentType: 'text/html', body: '<p>library</p>'});
    if (!at.startsWith('plugins/memory/reader/')) return route.fulfill({status: 404, body: ''});
    let file = path.join(root, at); if (at.endsWith('/')) file = path.join(file, 'index.html');
    if (!fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
    return route.fulfill({body: fs.readFileSync(file), contentType: MIME[path.extname(file)] || 'application/octet-stream',
      headers: {'content-security-policy': STRICT, 'x-content-type-options': 'nosniff'}});
  });
  return p;
}
const origin = 'http://fixture.test/argus/';
const reader = (q = '') => `${origin}plugins/memory/reader/?id=${ID}&revision=${REV}&format=epub${q}`;
// the first word on screen: foliate-view's lastLocation.range is what is visible now
const firstWord = p => p.evaluate(() => (document.querySelector('foliate-view')?.lastLocation?.range?.toString() || '').trim().split(/\s+/)[0]);
const ready = async p => { await p.waitForFunction(() => document.querySelector('foliate-view')?.lastLocation?.cfi); await p.waitForTimeout(150); };
const turned = async (p, before) => { await p.waitForFunction(w => (document.querySelector('foliate-view')?.lastLocation?.range?.toString() || '').trim().split(/\s+/)[0] !== w, before); return firstWord(p); };
const say = p => p.locator('#say').textContent();
const tap = async (p, fx) => { const v = p.viewportSize(); await p.mouse.click(Math.round(v.width * fx), Math.round(v.height * 0.6)); };
const shot = (p, name) => process.env.SHOTS && p.screenshot({path: path.join(process.env.SHOTS, name)});

(async () => {
  const browser = await chromium.launch();
  try {
    // ---- an EPUB on a phone: title, how far, taps on the edges and in the middle
    let p = await page(browser);
    await p.goto(reader()); await ready(p);
    assert.equal(await p.locator('#title').textContent(), 'Tiny Fixture Book');
    assert.match(await p.locator('#progress').textContent(), /^\d+% read$/);
    const start = await firstWord(p);
    assert.equal(start, 'Chapter', 'opens at the start of the text');
    await tap(p, 0.9); const second = await turned(p, start);
    assert.match(second, /^c1w\d+$/, 'the right edge turns to the next page');
    await tap(p, 0.1); assert.equal(await turned(p, second), start, 'the left edge turns back');
    const bookBox = await p.locator('#book').boundingBox();
    await tap(p, 0.5); assert.equal(await p.locator('#bar').isHidden(), true, 'a tap in the middle hides the bar');
    assert.deepEqual(await p.locator('#book').boundingBox(), bookBox, 'and the pages keep their size (no new layout, no jump)');
    await p.waitForTimeout(300); assert.equal(await firstWord(p), start, 'and turns nothing');
    await tap(p, 0.5); assert.equal(await p.locator('#bar').isVisible(), true, 'and shows it again');
    await p.keyboard.press('Escape'); assert.equal(await p.locator('#bar').isHidden(), true, 'Escape hides the bar');
    await p.keyboard.press('Escape'); assert.equal(await p.locator('#bar').isVisible(), true, 'and shows it again');
    assert.match(await p.locator('#progress').innerText(), /^\d+%$/, 'a phone shows how far, as a number');
    await shot(p, 'library-reader-phone.png');

    // keys (focus is in the page after the taps)
    for (const [key, back] of [['PageDown', 'PageUp'], ['ArrowRight', 'ArrowLeft'], ['Space', 'Shift+Space']]) {
      const before = await firstWord(p);
      await p.keyboard.press(key); const after = await turned(p, before);
      await p.keyboard.press(back); assert.equal(await turned(p, after), before, `${key} / ${back}`);
    }
    // the page buttons (44 px) and no sideways scroll at 375 px
    for (const b of ['#back', '#prev', '#next']) { const r = await p.locator(b).boundingBox(); assert.ok(r.width >= 44 && r.height >= 44, b); }
    assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no sideways scroll');
    assert.equal(await p.locator('#back').getAttribute('href'), `${origin}memory`);

    // ---- the place: kept on the server after a turn, with the CFI and how far; reopening lands on the same page
    server.posts.length = 0;
    await p.keyboard.press('PageDown'); const here = await turned(p, start);
    await p.waitForFunction(() => true); const t0 = Date.now();
    while (!server.posts.length && Date.now() - t0 < 2500) await p.waitForTimeout(100);
    const post = server.posts.at(-1);
    assert.ok(post, 'a place POST within 2.5 s of the turn');
    assert.equal(post.kind, 'recent'); assert.equal(post.id, ID); assert.equal(post.revision, REV); assert.equal(post.offset, 0);
    assert.match(post.cfi, /^epubcfi\(/); assert.ok(post.fraction > 0 && post.fraction < 1, String(post.fraction));
    await p.goto(reader()); await ready(p);
    assert.equal(await firstWord(p), here, 'reopening the book lands on the same page');
    assert.equal(await say(p), '');

    // ---- a book's own scripts never run (inline, onerror, a script file in the book), and the policy says so
    await p.evaluate(() => document.querySelector('foliate-view').goTo(1)); await p.waitForTimeout(400);
    for (let i = 0; i < 3; i++) { await p.keyboard.press('PageDown'); await p.waitForTimeout(150); }
    assert.equal(await p.evaluate(() => window.BAD), undefined, 'no script from inside the book ran');
    // the reader strips them before the browser sees them (the strict policy stays the first guard)
    assert.deepEqual(await p.evaluate(() => { const d = document.querySelector('foliate-view').renderer.getContents()[0].doc;
      return [d.querySelectorAll('script').length, d.querySelectorAll('[onerror]').length]; }), [0, 0],
      'the chapter shows without its scripts or handlers');
    assert.deepEqual(p.errors, []);

    // ---- the server does not answer: the place waits on this device, and goes once it answers
    server.down = true;
    const w1 = await firstWord(p); await p.keyboard.press('PageDown'); await turned(p, w1);
    await p.waitForFunction(t => document.querySelector('#say').textContent === t, 'Place kept on this device; it will sync when the library answers.', {timeout: 4000});
    assert.equal(await p.evaluate(id => JSON.parse(localStorage.getItem('mnemosyne-book-places-v1'))[id].pending, ID), true);
    server.down = false;
    const w2 = await firstWord(p); await p.keyboard.press('PageDown'); await turned(p, w2);
    await p.waitForFunction(() => document.querySelector('#say').hidden, null, {timeout: 4000});
    assert.equal(await p.evaluate(id => JSON.parse(localStorage.getItem('mnemosyne-book-places-v1'))[id].pending, ID), false);

    // ---- turning the phone keeps the page: the word at the top before is still on screen after (foliate keeps it in view,
    // the page may now start a few words earlier)
    const onScreen = (p, w) => p.evaluate(w => (document.querySelector('foliate-view')?.lastLocation?.range?.toString() || '').split(/\s+/).includes(w), w);
    const upright = await firstWord(p);
    await p.setViewportSize({width: 812, height: 375}); await p.waitForTimeout(800);
    assert.ok(await onScreen(p, upright), 'the same words on screen after turning the phone sideways');
    await p.setViewportSize({width: 375, height: 812}); await p.waitForTimeout(800);
    assert.ok(await onScreen(p, upright), 'and after turning it back');
    assert.deepEqual(p.errors, []);
    await p.context().close();

    // ---- a place in an older copy of the book: start at the beginning and say why
    server.places.recent = [{id: ID, revision: OLD, offset: 0, cfi: post.cfi, fraction: 0.5, at: new Date().toISOString()}];
    p = await page(browser);
    await p.goto(reader()); await ready(p);
    assert.equal(await firstWord(p), 'Chapter');
    assert.equal(await say(p), 'This book changed since your saved place; starting at the beginning.');
    await tap(p, 0.9); await turned(p, 'Chapter'); assert.equal(await p.locator('#say').isHidden(), true, 'the note goes with the first turn');
    await p.context().close();

    // ---- swipe (foliate's own touch handling)
    p = await page(browser, {touch: true});
    await p.goto(reader()); await ready(p);
    const sw = await firstWord(p);
    // real TouchEvents in the book's frame: foliate reads screenX, which Chromium's simulated touches leave at 0
    await p.evaluate(async () => {
      const doc = document.querySelector('foliate-view').renderer.getContents()[0].doc, win = doc.defaultView;
      const send = (type, x) => {
        const t = new win.Touch({identifier: 1, target: doc.body, clientX: x, clientY: 500, screenX: x, screenY: 500});
        doc.body.dispatchEvent(new win.TouchEvent(type, {bubbles: true, cancelable: true, touches: type === 'touchend' ? [] : [t], changedTouches: [t]}));
      };
      send('touchstart', 300);
      for (const x of [270, 230, 190, 150]) { await new Promise(r => setTimeout(r, 16)); send('touchmove', x); }
      send('touchend', 150);
    });
    assert.notEqual(await turned(p, sw), sw, 'a swipe to the left turns the page');
    await p.context().close();

    // ---- e-ink (1404 x 1872, motion allowed): no animation, white paper, black ink, no shadow, wide margins
    p = await page(browser, {viewport: {width: 1404, height: 1872}, motion: true});
    await p.goto(reader('&eink=1')); await ready(p);
    assert.equal(await p.evaluate(() => document.querySelector('foliate-view').renderer.hasAttribute('animated')), false);
    const look = await p.evaluate(() => { const b = getComputedStyle(document.body);
      return {bg: b.backgroundColor, ink: b.color, shadow: getComputedStyle(document.querySelector('#bar')).boxShadow, side: parseFloat(getComputedStyle(document.querySelector('#book')).paddingLeft)}; });
    assert.equal(look.bg, 'rgb(255, 255, 255)'); assert.equal(look.ink, 'rgb(0, 0, 0)'); assert.equal(look.shadow, 'none'); assert.ok(look.side >= 32, String(look.side));
    assert.equal(await p.evaluate(() => getComputedStyle(document.querySelector('#next')).textDecorationLine), 'none', 'page buttons: a border, no underline');
    assert.equal(await p.evaluate(() => document.querySelector('foliate-view').renderer.getAttribute('max-block-size')), '4000px', 'the page fills the tall screen');
    await shot(p, 'library-reader-eink.png');
    await p.context().close();
    p = await page(browser, {viewport: {width: 1280, height: 800}, motion: true});
    await p.goto(reader()); await ready(p);
    assert.equal(await p.evaluate(() => document.querySelector('foliate-view').renderer.hasAttribute('animated')), true, 'pages slide when motion is allowed');
    await p.context().close();

    // ---- a PDF: drawn by pdf.js, turns, place kept with a CFI
    server.posts.length = 0;
    p = await page(browser);
    await p.goto(`${origin}plugins/memory/reader/?id=${ID}&revision=${REV}&format=pdf`); await ready(p);
    assert.equal(await p.evaluate(() => document.querySelector('foliate-view').renderer.index), 0);
    assert.match(await p.locator('#progress').textContent(), /^Page 1 of \d+$/, 'a PDF says its page');
    await tap(p, 0.9);
    await p.waitForFunction(() => document.querySelector('foliate-view').renderer.index === 1);
    const t1 = Date.now(); while (!server.posts.length && Date.now() - t1 < 2500) await p.waitForTimeout(100);
    assert.match(server.posts.at(-1)?.cfi || '', /^epubcfi\(/);
    assert.deepEqual(p.errors, []);
    await p.context().close();

    // ---- no file on the server, or a broken link: say so, with the way back
    server.missing = true;
    p = await page(browser);
    await p.goto(reader());
    await p.getByText("This book's file is not on the server. Read its text in the library instead.").waitFor();
    assert.equal(await p.locator('#say a').getAttribute('href'), `${origin}memory`);
    await p.goto(`${origin}plugins/memory/reader/?id=nope&format=epub`);
    await p.getByText('This link to a book is not complete. Open the book from the library.').waitFor();
    assert.deepEqual(p.errors, []);
    await p.context().close();
    server.missing = false;
    console.log('library-reader: all checks passed');
  } finally {
    await browser.close();
    fs.rmSync(books, {recursive: true, force: true});
  }
})().catch(e => { console.error(e); process.exit(1); });
