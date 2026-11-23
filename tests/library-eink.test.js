// Mnemosyne reading settings (4.67.0, docs/mnemosyne-library.md "Reading settings, e-ink and synced places"): the e-ink
// switch (Automatic / On / Off), e-ink paged reading with edge taps, places synced through the server and the side-index
// vibration switch. Production assets, synthetic API answers, no services (like tests/library-ui.test.js).
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const built = path.join(root, 'dist', `argus-ui-${fs.readFileSync(path.join(root,'VERSION'),'utf8').trim()}-leafy-realm`, 'static');
const theme = JSON.parse(fs.readFileSync(path.join(root,'themes/leafy-realm/theme.json')));
const state = {title:'LeafyGrove',personas:theme.agents,jobs:[],watch:[],alerts:[],links:[],media:[],soon:[],quiet:[],role:'owner',updated:'Now',now:'Server: calm',now_name:'Server',
  plugins:[{id:'memory',name:'Memory',kind:'server',agent:true,subtitle:'Library and backups',page:'plugins/memory/page.js',style:'plugins/memory/page.css'}]};
const source = {id:'a'.repeat(64),revision:'b'.repeat(64),title:'Synthetic long book',kind:'book',collection:'Research',health:'ready',authorship:'Fixture author',source_version:'1',extraction_version:'1',indexed_at:'2026-11-23',original:'',diagnostic:''};
const backup = {summary:'Backups are fresh.',attention:false,folder:'fixtures',found:true,last:null,job:null,count:0,total_h:'0 B',copies:[],snapshots:[],shelf:7,note:'',why_not:''};
// section 1 is long (several screens), section 2 is one short line, section 3 is long again
const words = n => Array.from({length:n}, (_, i) => `word${i}`).join(' ');
const sections = [`Start of section one. ${words(1500)} End of section one.`, 'Short section two.', `Start of section three. ${words(1500)} End of section three.`];
const BOOX = 'Mozilla/5.0 (Linux; Android 12; NoteAir3C Build/2023) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const server = {places:{recent:[], saved:[]}, down:false, posts:[]};

async function page(browser, opts = {}) {
  const ctx = await browser.newContext({viewport:opts.viewport || {width:375,height:812}, userAgent:opts.userAgent, reducedMotion:'reduce'});
  const p = await ctx.newPage(); p.errors = [];
  p.on('pageerror', e => p.errors.push(e.message));
  await p.route('**/*', async route => {
    const u = new URL(route.request().url()), at = u.pathname.replace(/^\/(?:argus\/)?/, '');
    const json = (data, status = 200) => route.fulfill({json:data, status});
    if (at === 'api/state') return json(state);
    if (at === 'api/memory/state') return json(backup);
    if (at === 'api/memory/status') return json({needs:false, line:'Backups are fresh.'});
    if (at === 'api/memory/library/catalog') return json({configured:true, sources:[source], total:1, totals:{ready:1}, collections:['Research']});
    if (at === 'api/memory/library/source') return json(source);
    if (at === 'api/memory/library/read') {
      const offset = Number(u.searchParams.get('offset'));
      return json({available:true, offset, total:sections.length, blocks:[{pdf_page:null, chapter:null, text:sections[offset]}]});
    }
    if (at === 'api/memory/library/places') return server.down ? json({msg:'Library unavailable.'}, 503) : json(server.places);
    if (at === 'api/memory/library/place') {
      if (server.down) return json({msg:'Library unavailable.'}, 503);
      const body = JSON.parse(route.request().postData()); server.posts.push(body);
      const row = {id:body.id, revision:body.revision, offset:body.offset, at:new Date(Date.now() + server.posts.length).toISOString()};
      const list = body.kind === 'saved' ? 'saved' : 'recent';
      server.places[list] = list === 'recent' ? [row, ...server.places.recent.filter(r => r.id !== row.id)].slice(0, 10)
        : [...server.places.saved.filter(r => r.id !== row.id), row].slice(-100);
      return json(server.places);
    }
    if (at.startsWith('api/')) return json({});
    let file;
    if (at.startsWith('static/')) file = path.join(built, at.slice(7));
    else if (at.startsWith('plugins/memory/')) file = path.join(root, at);
    else return route.fulfill({contentType:'text/html', body:fs.readFileSync(path.join(built,'index.html'),'utf8').replace('/*STATE*/null', JSON.stringify(state))});
    if (!fs.existsSync(file)) return route.fulfill({status:404, body:''});
    const mime = {'.html':'text/html','.js':'application/javascript','.css':'text/css','.png':'image/png','.woff2':'font/woff2','.json':'application/json'};
    return route.fulfill({body:fs.readFileSync(file), contentType:mime[path.extname(file)] || 'application/octet-stream'});
  });
  return p;
}
const origin = 'http://fixture.test/argus/';
const eink = p => p.evaluate(() => document.documentElement.classList.contains('eink'));
const shot = (p, name, fullPage = true) => process.env.SHOTS && p.screenshot({path:path.join(process.env.SHOTS, name), fullPage});

(async () => {
  const browser = await chromium.launch();
  try {
    // ---- Task 1: the Reading settings fold and the e-ink look
    let p = await page(browser);
    await p.goto(origin + 'memory'); await p.locator('#lib-results article').waitFor();
    await p.getByText('Reading settings', {exact:true}).click();
    const mode = p.getByLabel('E-ink mode'), vibrate = p.getByLabel('Vibrate when the side index moves');
    assert.equal(await mode.inputValue(), 'auto');
    assert.equal(await vibrate.isChecked(), false, 'vibration is off by default');
    assert.equal(await eink(p), false, 'a phone is not an e-ink screen');
    await p.getByText('Automatic: not an e-ink screen.', {exact:true}).waitFor();
    await mode.selectOption('on'); assert.equal(await eink(p), true);
    assert.equal(await p.locator('.lib-reader-text, .memory').first().evaluate(e => getComputedStyle(e).animationName), 'none');
    await p.reload(); await p.locator('#lib-results article').waitFor(); assert.equal(await eink(p), true, 'the choice survives a reload');
    assert.equal(await p.locator('#scene').evaluate(e => getComputedStyle(e).display), 'none', 'the scene is hidden on e-ink');
    await shot(p, 'library-eink-phone.png');
    await p.goto(origin + 'argus'); await p.waitForTimeout(200);
    assert.equal(await eink(p), false, 'leaving the Library ends e-ink mode');
    await p.goto(origin + 'memory'); await p.locator('#lib-results article').waitFor();
    await p.getByText('Reading settings', {exact:true}).click(); await p.getByLabel('E-ink mode').selectOption('off');
    assert.equal(await eink(p), false);
    // denied storage: the choice still applies for this visit
    await p.evaluate(() => { Storage.prototype.setItem = function () { throw new Error('denied'); }; });
    await p.getByLabel('E-ink mode').selectOption('on'); assert.equal(await eink(p), true);
    await p.getByText('This browser could not keep the setting; it applies until you leave.', {exact:false}).waitFor();
    assert.deepEqual(p.errors, []); await p.context().close();
    // Automatic on an e-ink tablet
    p = await page(browser, {userAgent:BOOX, viewport:{width:702,height:936}});
    await p.goto(origin + 'memory'); await p.locator('#lib-results article').waitFor();
    assert.equal(await eink(p), true, 'Automatic finds the e-ink tablet');
    await p.getByText('Reading settings', {exact:true}).click();
    await p.getByText('Automatic: e-ink screen found.', {exact:true}).waitFor();
    assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(p.errors, []); await p.context().close();
    console.log('PASS reading settings: e-ink Automatic/On/Off, reload, leaving, denied storage, e-ink tablet found');

    // ---- Task 2: paged reading with edge taps (e-ink only)
    p = await page(browser, {userAgent:BOOX, viewport:{width:702,height:936}});
    const openReader = async () => {
      await p.goto(origin + 'memory'); await p.locator('#lib-browse').click(); await p.locator('#lib-status').filter({hasText:'sources in this view'}).waitFor();
      await p.getByText('Read source and details', {exact:true}).click(); await p.getByText('Read source text', {exact:true}).click();
      await p.locator('.lib-reader-text').filter({hasText:'Start of section one'}).waitFor();
    };
    const pageNo = async () => { const m = (await p.locator('.lib-page-status').innerText()).match(/^Page (\d+) of (\d+)$/); assert(m, 'page status'); return [Number(m[1]), Number(m[2])]; };
    const tap = async where => { const b = await p.locator('.lib-page').boundingBox(); await p.mouse.click(b.x + b.width * where, b.y + b.height / 2); await p.waitForTimeout(80); };
    const visible = needle => p.evaluate(n => { const t = document.querySelector('.lib-reader-text'), i = t.textContent.indexOf(n), r = document.createRange();
      r.setStart(t.firstChild, i); r.setEnd(t.firstChild, i + n.length); const a = r.getBoundingClientRect(), b = t.getBoundingClientRect();
      return a.left >= b.left - 1 && a.right <= b.right + 1; }, needle);
    await openReader();
    assert(await p.locator('.lib-reader-text').evaluate(e => e.classList.contains('paged')));
    let [at, of] = await pageNo(); assert.equal(at, 1); assert(of > 2, `a long section has several pages (${of})`);
    assert(await visible('Start of section one'));
    await shot(p, 'library-eink-reader-tablet.png', false);
    await tap(0.9); assert.deepEqual(await pageNo(), [2, of]); assert(!(await visible('Start of section one')));
    await tap(0.5); assert.deepEqual(await pageNo(), [2, of], 'the middle does not turn');
    await tap(0.1); assert.deepEqual(await pageNo(), [1, of]);
    await p.locator('.lib-page').focus(); await p.keyboard.press('PageDown'); assert.deepEqual(await pageNo(), [2, of]);
    await p.keyboard.press('ArrowLeft'); assert.deepEqual(await pageNo(), [1, of]);
    await p.keyboard.press('ArrowRight'); await p.keyboard.press('PageUp'); assert.deepEqual(await pageNo(), [1, of]);
    // rotating keeps the text that was at the top of the page in view
    await tap(0.9); await tap(0.9);
    const anchor = await p.evaluate(() => { const t = document.querySelector('.lib-reader-text'), b = t.getBoundingClientRect();
      const r = document.caretRangeFromPoint(b.left + 2, b.top + 8); return t.textContent.slice(r.startOffset).split(' ')[1]; });
    await p.setViewportSize({width:936, height:702}); await p.waitForTimeout(300);
    assert(await visible(anchor), `after rotating, ${anchor} is still on the page`);
    [at, of] = await pageNo(); assert(at > 1);
    await p.setViewportSize({width:702, height:936}); await p.waitForTimeout(300);
    for (let i = 0; i < 400 && (await pageNo())[0] < (await pageNo())[1]; i++) await tap(0.9);
    assert(await visible('End of section one'));
    await tap(0.9); await p.getByText(/^Section 2 of 3/).waitFor(); await p.waitForTimeout(80);
    assert.deepEqual(await pageNo(), [1, 1], 'a short section is one page');
    await tap(0.9); await p.getByText(/^Section 3 of 3/).waitFor(); await p.waitForTimeout(80);
    assert.deepEqual((await pageNo())[0], 1); assert(await visible('Start of section three'));
    await tap(0.1); await p.getByText(/^Section 2 of 3/).waitFor(); await p.waitForTimeout(80);
    await tap(0.1); await p.getByText(/^Section 1 of 3/).waitFor(); await p.waitForTimeout(80);
    [at, of] = await pageNo(); assert.equal(at, of, 'going back opens the previous section at its last page'); assert(await visible('End of section one'));
    assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    // with e-ink off the reader scrolls as before
    await p.getByText('Reading settings', {exact:true}).click(); await p.getByLabel('E-ink mode').selectOption('off'); await p.waitForTimeout(100);
    assert(!(await p.locator('.lib-reader-text').evaluate(e => e.classList.contains('paged'))));
    assert(await p.locator('.lib-page-status').isHidden());
    assert.equal(await p.locator('.lib-reader-text').evaluate(e => e.scrollWidth <= e.clientWidth + 1), true);
    assert.deepEqual(p.errors, []); await p.context().close();
    console.log('PASS e-ink paging: edge taps, middle ignored, keys, rotation keeps the place, short section, across sections, off = scrolling');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
