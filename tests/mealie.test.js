// Mealie (docs/mealie.md): the bundled mealie plugin asks tests/fixtures/fake_mealie.py, never a real Mealie. tests/run.sh
// starts the fake on MEALIE_PORT with FIXTURES/mealie/scenario.json and points the server at it (ARGUS_MEALIE =
// FIXTURES/mealie/mealie.json); the token file (ARGUS_MEALIE_TOKEN = FIXTURES/mealie/token.txt) is not there until this test
// writes it, and is set aside after it, so every other check sees "Not set up yet". Today's tile and its line, the section
// with the week and recipe links, each state in words, Check again by keyboard, phone width, and the token on no page.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const DIR = path.join(process.env.FIXTURES, 'mealie'), TOKEN = path.join(DIR, 'token.txt'), SCEN = path.join(DIR, 'scenario.json');
const SECRET = 'eyJhbGciOiJIUzI1NiJ9.browser-test-token.c2ln';
let n = 0;
const aside = f => { if (fs.existsSync(f)) fs.renameSync(f, `${f}.set-aside-${Date.now()}-${++n}`); };
const scenario = s => fs.writeFileSync(SCEN, JSON.stringify({token: SECRET, group: 'kitchen', ...s}));
const dinner = {in_days: 0, entryType: 'dinner', recipe: {name: 'Lentil soup', slug: 'lentil-soup'}};
const week = [dinner, {in_days: 0, entryType: 'breakfast', title: 'Porridge'}, {in_days: 2, entryType: 'dinner', recipe: {name: 'Shepherd\'s pie', slug: 'shepherds-pie'}}];
const sleep = ms => new Promise(r => setTimeout(r, ms));

run(async b => {
  aside(TOKEN); scenario({mode: 'ok', plan: week});
  try {
    const p = await page(b);
    const st = await (await p.request.get(BASE + 'api/state')).json();
    const pl = st.plugins.find(x => x.id === 'mealie');
    check(pl && pl.kind === 'server' && pl.name === 'Mealie' && !pl.agent, 'Mealie is a bundled server plugin with its own section, no god\'s name');

    // 1. no token file: Today's line says so, and the section says how
    const line = async () => (await (await p.request.get(BASE + 'api/mealie/status')).json());
    check(JSON.stringify(await line()) === JSON.stringify({line: 'Not set up yet: make an API token in Mealie', needs: false, action: ''}), 'no token: "Not set up yet", never "needs you"');
    await p.goto(BASE + 'home');
    const tile = p.locator('.news a.qline[data-id="mealie"]');           // its line on Today (4.54.0: no tiles)
    await tile.filter({hasText: 'Not set up'}).waitFor({timeout: 5000}).catch(() => {});
    check(await tile.count() === 1 && /Not set up yet/.test(await tile.locator('.qt').textContent()) && await tile.locator('.qw b').textContent() === 'Mealie', 'Today: a Mealie line under Sections');
    check(await p.locator('.need', {hasText: 'Mealie'}).count() === 0, 'and no row in "Needs you"');
    await p.goto(BASE + 'mealie'); await p.locator('.mealie .empty').waitFor({timeout: 5000});
    check(/Not set up yet/.test(await p.locator('.mealie .empty b').textContent()) && /API Tokens/.test(await p.locator('.mealie .empty').textContent()), 'the section: Not set up yet, and where to make the token');

    // 2. a token: tonight's meal on Today, the week in the section
    fs.writeFileSync(TOKEN, SECRET + '\n');
    check((await line()).line === 'Tonight: Lentil soup', `with a token: "${(await line()).line}"`);
    await p.goto(BASE + 'home'); await tile.filter({hasText: 'Tonight'}).waitFor({timeout: 5000}).catch(() => {});
    check(/Tonight: Lentil soup/.test((await tile.locator('.qt').textContent()).replace(/ /g, ' ')), 'Today: the line says tonight\'s meal');
    await p.goto(BASE + 'mealie'); await p.locator('.mealie .day').first().waitFor({timeout: 5000});
    const days = await p.locator('.mealie .day').evaluateAll(ds => ds.map(d => [d.querySelector('h4').textContent, [...d.querySelectorAll('.meal')].map(m => m.querySelector('.kind').textContent + ': ' + m.lastElementChild.textContent.trim())]));
    check(days.length === 2 && days[0][0] === 'Today' && JSON.stringify(days[0][1]) === '["Breakfast: Porridge","Dinner: Lentil soup"]',
      `the week: today, then the day with a meal (${JSON.stringify(days)})`);
    check(/Tonight: Lentil soup/.test(await p.locator('.mealie .mealsum').textContent()), 'the summary is Today\'s line');
    // links only when media.json gives the browser's address for Mealie (run.sh does not): none here, and no Open Mealie
    check(await p.locator('.mealie .meal a').count() === 0 && await p.locator('.mealie .openmealie').count() === 0, 'no media.json address: names without links');

    // 3. Check again by keyboard: Mealie refuses the token now; the answer is said, and focus stays on the button
    scenario({mode: 'refuse'}); await sleep(5200);                        // Check again asks Mealie again after 5 s at most
    await p.locator('.mealie .mealcheck').focus(); await p.keyboard.press('Enter');
    await p.locator('.mealie .empty.problem').waitFor({timeout: 5000}).catch(() => {});
    check(/Mealie refused the token/.test(await p.locator('.mealie .empty.problem').textContent().catch(() => '')), 'Check again: "Mealie refused the token" and what to do');
    check(await p.evaluate(() => document.activeElement.classList.contains('mealcheck')), 'focus stays on Check again');

    // 4. the token is on no page and in no answer
    for (const u of ['home', 'mealie', 'api/state', 'api/mealie/plan', 'api/mealie/status']) {
      const t = await (await p.request.get(BASE + u)).text();
      check(!t.includes('browser-test-token'), `no token in ${u}`);
    }
    check(!(await p.content()).includes('browser-test-token'), 'nor in the page as drawn');

    // 5. phone width, with a recipe whose name looks like markup: it is drawn as text, in the section and on Today (review M5)
    const odd = '<b>x</b> & "q"';
    scenario({mode: 'ok', plan: [...week, {in_days: 0, entryType: 'side', recipe: {name: odd, slug: 'b-x'}}]});
    const ph = await page(b, 375, 760);
    await ph.goto(BASE + 'mealie'); await sleep(5200);
    await ph.locator('.mealie .mealcheck').click(); await ph.locator('.mealie .day').first().waitFor({timeout: 5000});
    await ph.locator('.mealie .meal', {hasText: '<b>x</b>'}).waitFor({timeout: 5000}).catch(() => {});
    const shown = await ph.locator('.mealie .meal').evaluateAll(ms => ms.map(m => m.lastElementChild.textContent.trim()));
    check(shown.includes(odd) && await ph.locator('.mealie .days b').count() === 0, `a name like "${odd}" is text, not markup (${JSON.stringify(shown)})`);
    const hits = await ph.locator('.mealie .mealcheck').evaluate(e => [e.offsetWidth, e.offsetHeight]);
    check(await noOverflow(ph) && hits[0] >= 44 && hits[1] >= 44, `375 px: no sideways scrolling, Check again ${hits.join(' x ')} px`);
    await shot(ph, 'mealie-phone');
    scenario({mode: 'ok', plan: [{...dinner, recipe: {name: odd, slug: 'b-x'}}]}); await sleep(5200);
    await ph.locator('.mealie .mealcheck').click(); await ph.locator('.mealie .mealsum', {hasText: 'Tonight: <b>'}).waitFor({timeout: 5000}).catch(() => {});
    await p.goto(BASE + 'home'); await tile.filter({hasText: 'Tonight: <b>'}).waitFor({timeout: 5000}).catch(() => {});
    check((await tile.locator('.qt').textContent()).replace(/\u00a0/g, ' ').includes('Tonight: ' + odd) && await tile.locator('.qt b').count() === 0, 'and on Today\'s line');
    check(p.errors.length === 0 && ph.errors.length === 0, 'no page errors ' + p.errors.concat(ph.errors).join(' | '));
  } finally {
    aside(TOKEN); scenario({mode: 'ok', plan: []});                      // later checks see "Not set up yet"
  }
});
