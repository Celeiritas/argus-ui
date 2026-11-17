// One way to each place (4.54.0, docs/home.md): the bars do the navigating, Today says what needs you. Checked at a phone
// (412), a laptop (1024), a computer (1440) and 16:9 (1920):
//   Today: no tiles, no Open list, no Edit Today; what needs you sorted by what it costs to leave it (a backup with no
//     off-site copy above a skipped workout); one line per section with news, each ending in the chevron, 44 px or more;
//   the phone's bottom bar: Today, Argus, Mentor, Zeus, More;
//   the computer's top bar: the sections, then the one that opens elsewhere (links.json "section": true, here a placeholder
//     "Studio Test") last, with the opens-elsewhere mark; never a media player or a plain link;
//   More, top to bottom: the sections the bar leaves out (each with its live line, and its count when it needs you), Media,
//     Other pages, then Settings: Phone alerts, Mute sounds (a phone; the strip has its own), Edit Today.
// The fixture: two players and two links (placeholders, written to the test HOME and removed after), Mnemosyne and Chiron
// asking for him through routes; a failed task from tests/fixtures (Hermes) stays, so a broken thing leads.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CFG = path.join(HOME, '.config/argus-ui');
const MD = path.join(CFG, 'media.json'), LK = path.join(CFG, 'links.json');
const LINKS = [{name: 'Notes', what: 'Pages', href: '/notes-test/'}, {name: 'Studio Test', what: 'Studio', href: '/studio-test/', section: true}];
const settle = fn => async r => { try { await fn(r); } catch (e) { if (!/closed|disposed/i.test(String(e && e.message))) throw e; } };
const settled = p => p.waitForFunction(() => { const h = document.querySelector('#main .home'); return h && !/Checking…|Asking every section/.test(h.textContent); });
// needs: Mnemosyne (no off-site copy) and Chiron (a workout) ask for him, Chiron first in the plugin list's order;
// calm: nothing failed, no alert, every section's own line kept but needing nothing
async function open(b, w, h, calm) {
  const p = await page(b, w, h);
  if (calm) {
    await p.route('**/api/*/status*', settle(async r => { const res = await r.fetch(); let j = {}; try { j = await res.json(); } catch (e) {} await r.fulfill({json: {...j, needs: false, action: ''}}); }));
    await p.route('**/api/state*', settle(async r => { const res = await r.fetch(), j = await res.json();
      (j.jobs || []).forEach(x => { if (x.state === 'failed') x.state = 'running'; delete x.works; }); (j.watch || []).forEach(x => { if (x.works === false) x.works = true; });
      j.alerts = []; await r.fulfill({response: res, json: j}); }));
  } else {
    await p.route('**/api/memory/status*', r => r.fulfill({json: {line: 'The server has no copy outside your home yet. Your PC backed up last night.', needs: true, action: 'Check backups'}}));
    await p.route('**/api/chiron/status*', r => r.fulfill({json: {line: '1 workout skipped', needs: true, action: 'Plan a workout'}}));
  }
  await p.goto(BASE); await p.evaluate(() => refresh()); await settled(p);
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
  return p;
}
run(async b => {
  fs.mkdirSync(CFG, {recursive: true});
  fs.writeFileSync(MD, JSON.stringify({jellyfin: 'https://films.example/web/', audiobookshelf: 'https://books.example/'}));
  fs.writeFileSync(LK, JSON.stringify(LINKS));
  try {
    for (const [w, h] of [[412, 915], [1024, 768], [1440, 900], [1920, 1080]]) {
      const p = await open(b, w, h, false), phone = w < 600;

      // ---- Today ----
      check(await p.locator('#main .places, #main .place, #main .open, #main #editToday, #main .openlink').count() === 0, `${w}: Today has no tiles, no Open list and no Edit Today`);
      const keys = await p.locator('#main .needlist .need').evaluateAll(es => es.map(e => e.dataset.key));
      const mi = keys.indexOf('needs-memory'), ci = keys.indexOf('needs-chiron');
      check(mi >= 0 && ci > mi, `${w}: the backup with no off-site copy is above the workout (${keys.join(', ')})`);
      check(keys.length && !keys[0].startsWith('needs-'), `${w}: what broke leads (${keys[0]})`);
      const lines = await p.locator('#main .news a.qline').evaluateAll(es => es.map(e => ({id: e.dataset.id, chev: !!e.querySelector('svg.chev'), h: Math.round(e.getBoundingClientRect().height)})));
      check(lines.length > 0 && lines.every(l => l.chev && l.h >= 44), `${w}: every section line ends in the chevron and is 44 px or more (${lines.map(l => `${l.id} ${l.h}${l.chev ? '>' : ''}`).join(', ')})`);
      check(lines.some(l => l.id === 'mentor' && l.chev), `${w}: Mentor's line has its chevron`);
      check(!lines.some(l => l.id === 'memory' || l.id === 'chiron'), `${w}: a section with a row above has no line under Sections`);
      check(await noOverflow(p), `${w}: Today does not scroll sideways`);
      if (phone) await shot(p, 'nav-phone-today-needs');
      if (w === 1440) await shot(p, 'nav-1440-today');

      // ---- the bars ----
      if (phone) {
        const tabs = await p.locator('#tabs .tab:not(.more) b').allTextContents();
        check(JSON.stringify(tabs) === '["Today","Argus","Mentor","Zeus"]' && await p.locator('#tabs .tab.more').count() === 1, `${w}: the bottom bar is Today, Argus, Mentor, Zeus, then More (${tabs.join(', ')})`);
        check(await p.locator('.realms').isHidden(), `${w}: no top bar on a phone`);
      } else {
        const pills = await p.locator('#realms a.realm').evaluateAll(es => es.map(e => ({id: e.dataset.id, word: e.querySelector('b')?.textContent, link: e.classList.contains('link'),
          sr: e.querySelector('.sr')?.textContent || '', over: e.classList.contains('over'), shown: !!e.offsetWidth})));
        const last = pills[pills.length - 1] || {};
        check(last.word === 'Studio Test' && last.link && /opens another page/.test(last.sr), `${w}: the section that opens elsewhere is the top bar's last pill, with the opens-elsewhere mark (${pills.map(x => x.word + (x.over ? ' (in More)' : '')).join(', ')})`);
        check(!pills.some(x => /Jellyfin|Audiobookshelf|Notes/.test(x.word)), `${w}: no media player and no plain link on the top bar`);
      }

      // ---- More ----
      await p.locator('[data-more]:visible').first().click(); await p.locator('#moreSheet[open]').waitFor(); await p.waitForTimeout(250);
      const parts = await p.evaluate(() => ['moreList', 'moreMediaH', 'moreMedia', 'moreAwayH', 'moreAway', 'moreSetH', 'moreSet'].map(id => { const e = document.getElementById(id);
        return {id, y: e && e.offsetHeight ? Math.round(e.getBoundingClientRect().top) : null}; }).filter(x => x.y !== null));
      check(parts.every((x, i) => !i || x.y > parts[i - 1].y) && parts.map(x => x.id).slice(-2).join() === 'moreSetH,moreSet', `${w}: More's parts in order, Settings last (${parts.map(x => x.id).join(' > ')})`);
      check(JSON.stringify(await p.locator('#moreMedia .srow b').allTextContents()) === '["Jellyfin","Audiobookshelf"]', `${w}: Media lists Jellyfin and Audiobookshelf`);
      check(JSON.stringify(await p.locator('#moreAway .srow b').allTextContents()) === '["Notes"]', `${w}: Other pages has the plain link, not the section`);
      check(await p.locator('#moreSetH').textContent() === 'Settings', `${w}: the heading says Settings`);
      const sets = await p.locator('#moreSet .srow').evaluateAll(es => es.filter(e => e.offsetWidth).map(e => (e.querySelector('b') || e).textContent.trim()));
      const wantSets = phone ? ['Phone alerts', /^(Mute|Unmute) sounds$/, 'Edit Today'] : ['Phone alerts', 'Edit Today'];
      check(sets.length === wantSets.length && wantSets.every((x, i) => typeof x === 'string' ? sets[i] === x : x.test(sets[i])), `${w}: Settings holds ${sets.join(', ')}`);
      const secs = await p.locator('#moreList .srow').evaluateAll(es => es.map(e => ({id: e.dataset.id, word: e.querySelector('b')?.textContent, line: e.querySelector('small')?.textContent || '', dot: !!e.querySelector('.tabcount')})));
      if (phone) {
        check(!secs.some(x => ['home', 'argus', 'mentor', 'throne'].includes(x.id)) && secs[secs.length - 1]?.word === 'Studio Test', `${w}: More's sections are the ones off the bar, Studio Test last (${secs.map(x => x.word).join(', ')})`);
        check(secs.length >= 3 && secs.every(x => x.line.trim()), `${w}: each section row says its live line (${secs.map(x => `${x.word}: ${x.line}`).join(' | ')})`);
        const mem = secs.find(x => x.id === 'memory');
        check(!!mem && mem.dot && /no copy outside/.test(mem.line), `${w}: Mnemosyne's row has its dot and her line ("${mem && mem.line}")`);
        await shot(p, 'nav-phone-more');
        // the sheet's bottom: Media, Other pages and Settings (a picture for the owner's review)
        await p.evaluate(() => { const m = document.getElementById('moreSheet'); m.scrollTop = m.scrollHeight; }); await p.waitForTimeout(200);
        await shot(p, 'nav-phone-more-settings');
      } else {
        const folded = await p.locator('#realms .realm.over').evaluateAll(es => es.map(e => e.dataset.id));
        check(JSON.stringify(secs.map(x => x.id).sort()) === JSON.stringify([...folded].sort()), `${w}: More's sections are exactly the pills folded off the strip (${folded.join(' ') || 'none'})`);
        if (w === 1440) await shot(p, 'nav-1440-more');
      }
      const small = await p.locator('#moreSheet a, #moreSheet button').evaluateAll(es => es.map(e => e.getBoundingClientRect()).filter(r => r.width && (r.width < 44 || r.height < 44)).length);
      check(small === 0, `${w}: every control in More is 44 px or more`);
      await p.keyboard.press('Escape');
      check(await p.waitForFunction(() => !document.getElementById('moreSheet').open && document.activeElement?.matches('[data-more]'), null, {timeout: 3000}).then(() => true, () => false), `${w}: Esc closes More, focus back on More`);
      check(p.errors.length === 0, `${w}: no page errors ${p.errors.join(' | ')}`);
      await p.close();
    }

    // ---- 1920 x 1080 with a real host's count: ten sections and the studio (the owner, 2026-11-16: the studio joins the top
    // bar and the weather may leave it). The fixture has more plugins than a host, so the last ones are left out of the page's
    // state until the strip holds 11 pills (as tests/layout.test.js does). Pill widths follow the names, so with the real
    // names the cut-off can move by a section either way; the check names what it saw.
    {
      const REAL = 10, wp = await page(b, 1920, 1080);
      let drop = 0;
      const trim = j => { if (drop && Array.isArray(j.plugins)) j.plugins = j.plugins.slice(0, Math.max(0, j.plugins.length - drop)); return j; };
      await wp.route(u => /\/home$/.test(new URL(u).pathname), settle(async r => { const res = await r.fetch();
        const body = (await res.text()).replace(/(const INIT = )(\{.*?\})(;<\/script>)/s, (m, a, j, z) => a + JSON.stringify(trim(JSON.parse(j))).replace(/<\//g, '<\\/') + z);
        const headers = {...res.headers()}; delete headers['content-length'];
        await r.fulfill({status: res.status(), headers, body}); }));
      await wp.route('**/api/state*', settle(async r => { const res = await r.fetch(); await r.fulfill({response: res, json: trim(await res.json())}); }));
      const pills = async () => { await wp.goto(BASE + 'home'); await settled(wp); await wp.evaluate(() => document.fonts.ready); await wp.waitForTimeout(300);
        return wp.locator('#realms .realm').count(); };
      for (drop = 0; await pills() > REAL + 1 && drop < 40; drop++);
      const bar = await wp.evaluate(() => { const ps = [...document.querySelectorAll('#realms .realm')], s = ps[ps.length - 1], r = document.querySelector('.realms');
        return {n: ps.length, word: s?.querySelector('b')?.textContent, over: s?.classList.contains('over'), shown: !!s?.offsetWidth, bare: r.classList.contains('bare'), compact: r.classList.contains('compact'),
          folded: ps.filter(e => e.classList.contains('over')).map(e => e.querySelector('b')?.textContent)}; });
      check(bar.n === REAL + 1 && bar.word === 'Studio Test' && bar.shown && !bar.over,
        `1920, ${bar.n} pills (${REAL} sections and the studio): Studio Test is on the top bar itself, not folded into More (weather ${bar.bare ? 'off the strip' : 'on the strip'}, second lines ${bar.compact ? 'hidden' : 'shown'}${bar.folded.length ? ', in More: ' + bar.folded.join(', ') : ''})`);
      await shot(wp, 'nav-1920-bar');
      check(wp.errors.length === 0, `1920 trimmed: no page errors ${wp.errors.join(' | ')}`);
      await wp.close();
    }

    // ---- calm: the phone's Today when nothing needs him, and a 375 px phone ----
    const c = await open(b, 412, 915, true);
    check(/Nothing needs you/.test(await c.locator('#needs-h').textContent()) && await c.locator('#main .places, #main .open').count() === 0, '412 calm: "Nothing needs you", no tiles, no Open list');
    await shot(c, 'nav-phone-today-calm');
    await c.setViewportSize({width: 375, height: 812}); await c.waitForTimeout(300);
    check(await noOverflow(c), '375 calm: no sideways scrolling');
    await c.locator('[data-more]:visible').first().click(); await c.locator('#moreSheet[open]').waitFor(); await c.waitForTimeout(250);
    check(await noOverflow(c) && await c.locator('#moreSheet').evaluate(d => d.scrollWidth <= d.clientWidth + 1), '375: More does not scroll sideways');
    check(c.errors.length === 0, `calm: no page errors ${c.errors.join(' | ')}`);
    await c.close();
  } finally {
    for (const f of [MD, LK]) fs.rmSync(f, {force: true});     // the test HOME's own copies; the next test starts with none
  }
});
