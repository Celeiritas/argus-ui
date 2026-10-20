// Mentor page: plain decks and code modules (terms -> drills -> explain cards), the inbox, levels, Argus in the corner.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const INBOX = path.join(process.env.FIXTURES || '.', '..', 'home', '.local', 'share', 'argus-ui', 'inbox');
const api = (p, what, body) => body ? p.request.post(BASE + 'api/mentor/' + what, {data: body}).then(r => r.json()) : p.request.get(BASE + 'api/mentor/' + what).then(r => r.json());
// answer the next card of a module through the API (fast and right where we know the answer), so the page moves on
async function skip(p, deck, kind, n) {
  for (let i = 0; i < n; i++) {
    const {card} = await api(p, 'next?deck=' + deck);
    if (!card || card.kind !== kind) return card;
    const r = await api(p, 'answer', {card: card.id, text: '', confidence: 2, ms: 1000});
    await api(p, 'rate', {attempt: r.attempt, rating: 3, grade_wrong: false});
  }
  return (await api(p, 'next?deck=' + deck)).card;
}
run(async b => {
  const p = await page(b);
  await p.goto(BASE + 'mentor'); await p.waitForTimeout(1000);
  check(await p.locator('body.side').count() === 1, 'Mentor is a side page (Argus in the corner)');
  check(await p.locator('#mdeck option[value="argus-code"]').count() === 1, 'the built-in code module is in the Study picker');

  // a plain deck still works as before
  await p.selectOption('#mdeck', 'psych-design'); await p.waitForTimeout(500);
  await p.locator('#ans').fill('spread out over time, remembered better than cramming');
  await p.locator('#ans').focus(); await p.keyboard.press('Control+Enter'); await p.waitForTimeout(600);
  const labels = await p.locator('.seg.rates label b').allTextContents();
  check(labels.join('|') === '1. Very well|2. Well enough|3. Not well|4. Needs work', 'ratings read Very well … Needs work');
  check(await p.locator('input[name=rate]:checked').count() === 1, "Mentor's suggestion is preselected");
  await p.keyboard.press('4');
  check(await p.locator('#rateBtn').textContent() === 'Run again in 10 min', 'key 4 picks Needs work and the button says what happens');
  await p.keyboard.press('Enter'); await p.waitForTimeout(700);
  check(/10 minutes/.test(await p.locator('#toastText').textContent()), 'Needs work brings the card back in 10 minutes');

  // a code module starts with its terms (pre-training)
  await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(/^Term/.test(await p.locator('.kind').textContent()), 'a new module starts with a term card');
  await p.locator('#ans').fill('context manager'); await p.keyboard.press('Enter'); await p.waitForTimeout(600);
  check((await p.locator('#rhead').textContent()).trim() === 'context manager', 'a right term is confirmed');
  check(await p.locator('.defs dt', {hasText: 'In your code'}).count() === 1, 'the feedback shows where the term lives in the code');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(500);

  // then drills: blanks typed straight into the code
  const drill = await skip(p, 'argus-code', 'term', 8);
  check(drill && drill.kind === 'drill' && drill.level === 1, 'drills unlock once every term has been seen');
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(await p.locator('pre.code input.blank').count() === 2, 'a level 1 drill has two blanks in the code');
  await shot(p, 'mentor-drill-ask');
  await p.locator('input.blank').nth(0).fill('_mem'); await p.keyboard.press('Enter');
  check(await p.evaluate(() => document.activeElement.dataset.n) === '2', 'Enter moves to the next blank');
  await p.keyboard.type('data'); await p.keyboard.press('Enter'); await p.waitForTimeout(600);
  check(/2 of 2 blanks right/.test(await p.locator('#rhead').textContent()), 'both blanks graded right');
  check(/level 2/.test(await p.locator('.seg.rates label').first().textContent()), 'a fast, right answer offers level 2');
  await shot(p, 'mentor-drill');
  await p.keyboard.press('1'); await p.keyboard.press('Enter'); await p.waitForTimeout(700);
  check(/Level 2 next time/.test(await p.locator('#toastText').textContent()), 'the toast says the drill moves up a level');

  // a second fast, right answer (level 2: the logic) takes it to level 3
  const r2 = await api(p, 'answer', {card: 'argus-code:drill_01', text: JSON.stringify(['with _lock', "_mem.get('at', 0) > time.time() - TTL"]), confidence: 4, ms: 1000});
  check(r2.level === 2 && r2.coverage === 1, 'level 2 blanks the logic, and quotes or spacing may differ');
  check((await api(p, 'rate', {attempt: r2.attempt, rating: 4, grade_wrong: false})).level === 3, 'a fast, right answer takes the drill to level 3');

  // modules view: the breakdown, progress, and the inbox
  fs.mkdirSync(INBOX, {recursive: true});
  const mod = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'themes', 'leafy-realm', 'decks', 'argus-code.json')));
  mod.metadata.module_name = 'inbox_test_module'; mod.metadata.project = 'test-project';
  fs.writeFileSync(path.join(INBOX, '20261020_120000_inbox_test.json'), JSON.stringify(mod));
  fs.writeFileSync(path.join(INBOX, '20261020_120100_broken.json'), '{"tier_1_faded_code_drills": [');
  await p.locator('[data-view=modules]').click(); await p.waitForTimeout(700);
  check(await p.locator('.module').count() === 2, 'a module copied into the inbox shows up without a restart');
  check(await p.locator('.ideas li.miss', {hasText: 'broken.json'}).count() === 1, 'a broken inbox file is listed with what is wrong');
  await p.locator('.module details summary').first().click();
  check(await p.locator('.module .defs dt', {hasText: 'The big picture'}).first().isVisible(), 'the breakdown opens');
  await shot(p, 'mentor-modules');
  await p.locator('.module', {hasText: 'inbox test module'}).locator('[data-study]').click(); await p.waitForTimeout(600);
  check(await p.locator('#mdeck').inputValue() === '20261020_120000_inbox_test' && /^Term/.test(await p.locator('.kind').textContent()), 'Study this module opens its first term');

  // explain cards come after the drills; fenced code in the prompt is shown as code
  for (const k of ['term', 'drill']) await skip(p, 'argus-code', k, 8);
  await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(await p.locator('.kind').textContent() === 'Find the bug' && await p.locator('.prompt pre.code').count() === 1, 'a pre-mortem card shows its code');
  await p.locator('#ans').fill('A crash leaves a truncated file, so json load fails next start. Write a temp file then os.replace, which is atomic.');
  await p.keyboard.press('Control+Enter'); await p.waitForTimeout(600);
  check(/3 of 3 key ideas/.test(await p.locator('#rhead').textContent()), 'the explanation covers all three key ideas');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(500);

  // level 3: write the whole body (auto-indent); Python reads it, never runs it
  await skip(p, 'argus-code', 'explain', 8);
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  await p.locator('#ahead').click(); await p.waitForTimeout(600);
  check(/level 3 of 3/.test(await p.locator('.kind').textContent()) && await p.locator('textarea.codein').count() === 1, 'Practice ahead brings back the drill at level 3: a body to write');
  await p.locator('textarea.codein').focus(); await p.keyboard.type('with _lock:'); await p.keyboard.press('Enter');
  check(await p.locator('textarea.codein').inputValue() === 'with _lock:\n    ', 'Enter after a colon indents the next line');
  await p.locator('textarea.codein').fill(mod.tier_1_faded_code_drills[0].answers.level_3[0]);
  await p.keyboard.press('Control+Enter'); await p.waitForTimeout(600);
  check(/Same structure/.test(await p.locator('#rhead').textContent()) && await p.locator('.pair pre.code').count() === 2, 'a body typed from memory matches, shown next to the model');
  await shot(p, 'mentor-level3');
  const s2 = await api(p, 'answer', {card: 'argus-code:drill_01', text: 'with _lock\n    return', confidence: 3, ms: 9000});
  check(/line \d+/.test(s2.problem || ''), "Python's syntax error is reported with its line");
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

  const ph = await page(b, 375, 760); await ph.goto(BASE + 'mentor'); await ph.waitForTimeout(800);
  await ph.selectOption('#mdeck', 'argus-code'); await ph.waitForTimeout(600);
  check(await noOverflow(ph), 'phone: no sideways scrolling on a code card');
  await shot(ph, 'mentor-phone');
  await ph.locator('[data-view=modules]').click(); await ph.waitForTimeout(600);
  check(await noOverflow(ph), 'phone: no sideways scrolling on code modules');
});
