// The device list (4.51.0, docs/devices.md): Argus's Devices panel on Watch and its line on Today, against the shared server
// (tests/run.sh: ARGUS_DEVICES = FIXTURES/devices/active.json, which is not there until this test writes it; ARGUS_TAILSCALE
// = the stand-in tests/fixtures/fake_tailscale.py, answering devices/tailscale-status.json; the answer is cached 1 s).
// No file: a plain empty state on Watch and no line on Today. The fixture (devices/devices.json) has a device for every
// status: this machine (Desktop, then Game), online, offline with the time last seen, and three kinds of "can't tell".
// Each status is a word on a badge in its colour (--dev-*), never colour alone. Tailscale failing makes every device "can't
// tell", never "offline". A learner sees none of it. The server side is tests/devices_test.py.
const {BASE, check, page, noOverflow, shot, units, run} = require('./lib');
const fs = require('fs'), path = require('path');
const DIR = path.join(process.env.FIXTURES, 'devices'), ACTIVE = path.join(DIR, 'active.json'), MODE = path.join(DIR, 'tailscale-mode');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home'), CONF = path.join(HOME, '.config', 'argus-ui'), PEOPLE = path.join(CONF, 'people.json');
const WATCH = new URL('/argus/argus', BASE).href;
let n = 0;
const put = (f, text) => { fs.writeFileSync(f, text); const t = new Date(Date.now() + 1000 * ++n); fs.utimesSync(f, t, t); };
const aside = f => { if (fs.existsSync(f)) fs.renameSync(f, `${f}.set-aside-${Date.now()}-${++n}`); };
const answer = mode => { if (mode === 'ok') aside(MODE); else put(MODE, mode); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
// the rows as the page shows them
const rows = p => p.$$eval('#devices .dev', ls => ls.map(l => {
  const st = l.querySelector('.dstat'), cs = getComputedStyle(st), r = l.getBoundingClientRect();
  return {name: l.querySelector('b').textContent, meta: l.querySelector('.dw span').textContent, status: [...l.classList].find(c => c.startsWith('s-')).slice(2),
          label: st.textContent, bg: cs.backgroundColor, ink: cs.color, border: cs.borderStyle, h: r.height};
}));
const token = (p, name) => p.evaluate(n => { const d = document.createElement('i'); d.style.color = `var(${n})`; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }, name);
const lum = c => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, k) => k - m); return (x + 0.05) / (y + 0.05); };
async function watch(b, w, h = 900) {
  const p = await page(b, w, h); await p.goto(WATCH);
  await p.waitForFunction(() => { const d = document.querySelector('#devbody'); return d && !/Checking your devices/.test(d.textContent); }, null, {timeout: 10000}).catch(() => {});
  await p.evaluate(() => document.fonts.ready); return p;
}
async function today(b, w, h = 900) {
  const p = await page(b, w, h); await p.goto(BASE);
  await p.waitForSelector('.home .devline', {timeout: 8000}).catch(() => {});
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300); return p;
}
const chips = p => p.$$eval('.home .devline .dchip', cs => cs.map(c => c.textContent.replace(/ /g, ' ')));

run(async b => {
  let saved; units(u => { saved = JSON.stringify(u); });
  const desk = () => units(u => { u['fake-desktop-shell'].ActiveState = 'active'; u['fake-game-session'].ActiveState = 'inactive'; });
  const game = () => units(u => { u['fake-desktop-shell'].ActiveState = 'inactive'; u['fake-game-session'].ActiveState = 'active'; });
  try {
    aside(ACTIVE); answer('ok'); desk();

    // ---- no file: a plain empty state on Watch, nothing on Today ----
    let p = await watch(b, 412, 915);
    check(await p.locator('#devices h2').textContent() === 'Devices', 'Watch has a Devices panel');
    const empty = await p.locator('#devbody').textContent();
    check(/No devices listed yet/.test(empty) && await p.locator('#devbody a', {hasText: 'Learn how to list your devices'}).count() === 1,
      `no file: the empty state says so and links to how ("${empty.slice(0, 60)}…")`);
    check((await p.locator('#devbody a').boundingBox()).height >= 44, 'no file: the help link is a 44 px target');
    check(await noOverflow(p), 'no file, 412 px: no sideways scroll');
    await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-empty-412'); await p.close();
    p = await watch(b, 1920, 1080); await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-empty-1920'); await p.close();
    p = await page(b, 412, 915); await p.goto(BASE); await p.waitForTimeout(1500);
    check(await p.locator('.home .devline').count() === 0, 'no file: Today has no device line');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | ')); await p.close();

    // ---- the fixture: every status ----
    put(ACTIVE, fs.readFileSync(path.join(DIR, 'devices.json'))); await sleep(1100);
    p = await watch(b, 412, 915);
    let r = await rows(p);
    const by = Object.fromEntries(r.map(x => [x.name, x]));
    check(r.map(x => x.name).join() === 'Shelf,Desk PC,Spare PC,Phone,Tablet,Laptop,Old console', `the devices in the file's order (${r.map(x => x.name).join(', ')})`);
    check(by.Shelf.status === 'desktop' && by.Shelf.label === 'Desktop mode' && /this machine/.test(by.Shelf.meta), `this machine shows its mode: ${by.Shelf.label} (${by.Shelf.meta})`);
    check(by['Desk PC'].status === 'online' && by['Desk PC'].label === 'Online' && by.Phone.label === 'Online', 'online peers say Online');
    check(by['Spare PC'].status === 'offline' && by['Spare PC'].label === 'Offline' && /last seen/.test(by['Spare PC'].meta), `offline, with when it was last seen (${by['Spare PC'].meta})`);
    check(['Tablet', 'Laptop', 'Old console'].every(k => by[k].status === 'unknown' && by[k].label === "Can't tell"), "the rest: Can't tell, in words");
    check(/Tailscale did not say/.test(by.Tablet.meta) && /Not on the Tailscale list/.test(by.Laptop.meta) && /does not check/.test(by['Old console'].meta), 'each "can\'t tell" says why');
    const tok = {};
    for (const s of ['online', 'offline', 'unknown', 'desktop', 'game']) tok[s] = await token(p, `--dev-${s}`);
    check(tok.desktop === await token(p, '--mode-desktop') && tok.game === await token(p, '--mode-game') && tok.online === await token(p, '--mode-desktop'),
      `the colours come from the mode pill's tokens (desktop ${tok.desktop}, game ${tok.game})`);
    check(by.Shelf.bg === tok.desktop && by['Desk PC'].bg === tok.online && by['Spare PC'].bg === tok.offline, `each badge is filled with its status's token (${by['Spare PC'].bg})`);
    check(by.Tablet.bg === 'rgba(0, 0, 0, 0)' && by.Tablet.border === 'dashed', "can't tell: no fill, a dashed ring");
    check(r.filter(x => x.status !== 'unknown').every(x => ratio(x.bg, x.ink) >= 4.5), `the words on every filled badge are readable (${r.filter(x => x.status !== 'unknown').map(x => ratio(x.bg, x.ink).toFixed(1)).join(', ')} : 1)`);
    check(r.every(x => x.h >= 44), `44 px rows (${Math.min(...r.map(x => Math.round(x.h)))} px the least)`);
    const again = p.locator('#devices .devagain'), bb = await again.boundingBox();
    check(await again.textContent() === 'Check again' && bb.height >= 44 && bb.width >= 44, `a verb-first Check again button, ${Math.round(bb.width)}x${Math.round(bb.height)}`);
    check(/Checked \d/.test(await p.locator('#devices .devmeta').textContent()), 'it says when it last checked');
    check(await noOverflow(p), 'every status, 412 px: no sideways scroll');
    const json = await (await p.request.get(BASE + 'api/devices')).text();
    check(!/aa:bb|aa-bb|pc-one|"host"/.test(json), 'the page never gets a MAC address or a host name');
    await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-list-412');
    // the keyboard: Check again by Enter, focus kept
    let asked = 0; p.on('request', q => { if (/api\/devices\?fresh=1/.test(q.url())) asked++; });
    await again.focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(1500);
    check(asked === 1 && await p.evaluate(() => document.activeElement?.classList.contains('devagain')), `Enter on Check again asks again (${asked}) and keeps the focus there`);
    await p.close();
    p = await page(b, 375, 812); await p.goto(WATCH); await p.waitForSelector('#devices .dev', {timeout: 8000}).catch(() => {});
    check(await noOverflow(p), '375 px: no sideways scroll'); await p.close();
    p = await watch(b, 1920, 1080); await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-list-1920'); await p.close();

    // ---- Today's line: the counts in words, one link to the list ----
    p = await today(b, 412, 915);
    const line = p.locator('.home .devline');
    check(await line.count() === 1, 'Today has the device line');
    const c = await chips(p);
    check(c.join() === "3 online,1 offline,3 can't tell", `the counts, Desktop counted as online (${c.join(' / ')})`);
    const lb = await line.boundingBox();
    check(lb.height >= 44 && lb.height <= 100, `one compact line, 44 px or more to the thumb (${Math.round(lb.height)} px)`);
    check(await noOverflow(p), 'Today with the line, 412 px: no sideways scroll');
    await shot(p, 'devices-today-412');
    await line.focus(); check(await line.evaluate(e => getComputedStyle(e).outlineStyle !== 'none'), 'the line shows its focus');
    await p.keyboard.press('Enter'); await p.waitForURL(/\/argus\/argus#devices$/, {timeout: 8000}).catch(() => {});
    await p.waitForSelector('#devices .dev', {timeout: 8000}).catch(() => {}); await p.waitForTimeout(600);
    const top = await p.locator('#devices').evaluate(e => e.getBoundingClientRect().top);
    check(/#devices$/.test(p.url()) && top < 400, `Enter opens Watch at the list (${new URL(p.url()).hash}, list at ${Math.round(top)} px)`);
    await p.close();
    p = await page(b, 375, 812); await p.goto(BASE); await p.waitForSelector('.home .devline', {timeout: 8000}).catch(() => {});
    check(await noOverflow(p), 'Today, 375 px: no sideways scroll'); await p.close();
    p = await today(b, 1920, 1080); await shot(p, 'devices-today-1920'); await p.close();

    // ---- Game mode: this machine in the pill's purple ----
    game(); await sleep(2500);
    p = await watch(b, 412, 915); await p.waitForFunction(() => /Game mode/.test(document.querySelector('#devices')?.textContent || ''), null, {timeout: 8000}).catch(() => {});
    r = await rows(p);
    check(r[0].status === 'game' && r[0].label === 'Game mode' && r[0].bg === tok.game, `Game: ${r[0].label} on ${r[0].bg}`);
    await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-game-412'); await p.close();
    p = await watch(b, 1920, 1080); await p.waitForFunction(() => /Game mode/.test(document.querySelector('#devices')?.textContent || ''), null, {timeout: 8000}).catch(() => {});
    await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-game-1920'); await p.close();
    desk();

    // ---- Tailscale fails: every peer "can't tell", never "offline" ----
    answer('fail'); await sleep(1100);
    p = await watch(b, 412, 915); r = await rows(p);
    check(r.filter(x => !['Shelf'].includes(x.name)).every(x => x.status === 'unknown' && /Tailscale gave an error|does not check/.test(x.meta)),
      `Tailscale failing: ${r.map(x => x.label).join(', ')}`);
    check(!r.some(x => x.status === 'offline'), 'never "offline" when Argus cannot tell');
    await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-cant-tell-412'); await p.close();
    p = await today(b, 412, 915);
    check((await chips(p)).join() === "1 online,6 can't tell", `Today: ${(await chips(p)).join(' / ')}`); await p.close();
    answer('ok');

    // ---- a broken file: the panel says what is wrong ----
    put(ACTIVE, '{"devices": [{"name": "Desk PC", "probe": "tailscale", "host": "pc one"}]}'); await sleep(300);
    p = await watch(b, 412, 915);
    const bad = await p.locator('#devbody').textContent();
    check(/Fix that line/.test(bad) && (await p.locator('#devbody .devbad a').boundingBox()).height >= 44, 'a broken file says what to do, with a 44 px help link');
    check(/could not be read/.test(bad) && /Tailscale host name/.test(bad), `a broken file says why ("${bad.slice(0, 90)}…")`);
    await p.locator('#devices').scrollIntoViewIfNeeded(); await shot(p, 'devices-broken-412'); await p.close();
    p = await page(b, 412, 915); await p.goto(BASE); await p.waitForTimeout(1500);
    check(await p.locator('.home .devline').count() === 0, 'a broken file: no line on Today (Watch says why)'); await p.close();
    put(ACTIVE, fs.readFileSync(path.join(DIR, 'devices.json')));

    // ---- a learner: no line on Today, the list refused ----
    fs.mkdirSync(CONF, {recursive: true});
    put(PEOPLE, JSON.stringify({people: [{id: 'owner-one', name: 'Owner One', role: 'owner', logins: ['owner@example.com']},
                                         {id: 'learner-two', name: 'Learner Two', role: 'learner', logins: ['learner@example.com']}]}));
    const ctx = await b.newContext({viewport: {width: 412, height: 915}, extraHTTPHeaders: {'Tailscale-User-Login': 'learner@example.com', 'X-Forwarded-For': '192.0.2.20'}});
    const lp = await ctx.newPage(); let tried = 0; lp.on('request', q => { if (/api\/devices/.test(q.url())) tried++; });
    await lp.goto(BASE); await lp.waitForTimeout(1500);
    check(await lp.evaluate(() => role()) === 'learner' && await lp.locator('.devline').count() === 0 && tried === 0, `learner: no device line, the list is never asked for (${tried})`);
    check((await lp.request.get(BASE + 'api/devices')).status() === 403, 'learner: api/devices is refused (403)');
    await ctx.close();
  } finally {
    aside(ACTIVE); aside(PEOPLE); answer('ok'); units(u => Object.assign(u, JSON.parse(saved)));   // later checks see the page without devices
  }
});
