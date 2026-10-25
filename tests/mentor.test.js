// Mentor page: plain decks and lessons (learn first: orientation -> teach -> terms -> worked examples -> drills -> pre-reads
// -> explain cards), the hint ladder, stuck detection, the inbox, levels, Argus in the corner.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const INBOX = path.join(process.env.FIXTURES || '.', '..', 'home', '.local', 'share', 'argus-ui', 'inbox');
const api = (p, what, body) => body ? p.request.post(BASE + 'api/mentor/' + what, {data: body}).then(r => r.json()) : p.request.get(BASE + 'api/mentor/' + what).then(r => r.json());
const LEARN = ['orientation', 'teach', 'level0', 'preread'];
// answer the next card of a lesson through the API (a Learn card is marked read; a practice card gets a blank answer), so the page moves on
async function skip(p, deck, kind, n) {
  for (let i = 0; i < n; i++) {
    const {card} = await api(p, 'next?deck=' + deck);
    if (!card || card.kind !== kind) return card;
    const r = await api(p, 'answer', {card: card.id, text: LEARN.includes(kind) ? 'read it, five words long' : '', confidence: 2, ms: 1000});
    await api(p, 'rate', {attempt: r.attempt, rating: LEARN.includes(kind) ? 0 : 3, grade_wrong: false});
  }
  return (await api(p, 'next?deck=' + deck)).card;
}
// read the Learn cards of one kind through the page's own buttons
const words = async (p, sel, text) => { await p.locator(sel).fill(text); };
run(async b => {
  const p = await page(b);
  await p.goto(BASE + 'mentor'); await p.waitForTimeout(1000);
  check(await p.locator('body.side').count() === 1, 'Mentor is a side page (Argus in the corner)');
  check(await p.locator('#mdeck option[value="argus-code"]').count() === 1, 'the built-in lesson is in the Study picker');
  check(/to learn/.test(await p.locator('#mstats').textContent()), 'the stats line counts the Learn cards still to read');

  // a plain deck still works as before
  await p.selectOption('#mdeck', 'psych-design'); await p.waitForTimeout(500);
  await p.locator('#ans').fill('spread out over time, remembered better than cramming');
  await p.locator('#ans').focus(); await p.keyboard.press('Control+Enter'); await p.waitForTimeout(600);
  const labels = await p.locator('.seg.rates label b').allTextContents();
  check(labels.join('|') === '1. Again|2. Hard|3. Good|4. Easy', "ratings read Again, Hard, Good, Easy (Anki's order)");
  check(await p.locator('input[name=rate]:checked').count() === 1, "Mentor's suggestion is preselected");
  check(await p.locator('#rpanel .verdict[role=status] svg').count() === 1 && /Correct|Partly right|Not quite/.test(await p.locator('#rhead').textContent()), 'the verdict has an icon and a word, not colour alone');
  await p.keyboard.press('1');
  check(await p.locator('#rateBtn').textContent() === 'Run again in 10 min', 'key 1 picks Again and the button says what happens');
  await p.keyboard.press('Enter'); await p.waitForTimeout(700);
  check(/10 minutes/.test(await p.locator('#toastText').textContent()), 'Again brings the card back in 10 minutes');

  // a lesson starts with its orientation: one screen, and five typed words before the cards
  await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(/^Orientation/.test(await p.locator('.kind').textContent()) && (await p.locator('.termline').textContent()).split(', ').length === 8, 'a new lesson starts with its orientation and names the terms coming, as one plain line');
  check(!/Files:|\.py\b/.test(await p.locator('#qform').textContent()), 'the orientation names no files (the Lessons view keeps them)');
  check(await p.locator('#qform textarea').count() === 0 && await p.locator('#goBtn').textContent() === 'Start the lesson', 'no summary box to fill in before starting');
  await p.locator('#goBtn').click(); await p.waitForTimeout(700);

  // then teach cards: a question to try first (typed, not graded), then the term and a spot-it check; a wrong line still moves on, with the why
  check(/^Teach/.test(await p.locator('.kind').textContent()) && await p.locator('#guess').count() === 1 && await p.locator('.defs').count() === 0, 'a teach card asks its try-first question before explaining');
  await p.locator('#tryBtn').click(); await p.waitForTimeout(200);
  check(await p.locator('.needmsg[role=alert]').count() === 1 && await p.locator('#guess').count() === 1, 'an empty guess gets a message under the box, not a greyed-out button');
  await shot(p, 'mentor-try-first');
  await p.locator('#guess').fill('it unlocks the lock for you'); await p.keyboard.press('Control+Enter'); await p.waitForTimeout(400);
  check(/Your guess: it unlocks the lock for you/.test(await p.locator('.callout.tried').textContent()), 'the explanation shows under the question, next to the guess');
  check(/^Teach/.test(await p.locator('.kind').textContent()) && await p.locator('.lines .line').count() === 4, 'a teach card shows the term, its anchor and a snippet to spot it in');
  await shot(p, 'mentor-teach');
  await p.locator('.lines .line').nth(2).click(); await p.locator('#goBtn').click(); await p.waitForTimeout(600);
  check(/line 2/.test(await p.locator('#rhead').textContent()) && /released on exit/.test(await p.locator('.coach').textContent()), 'the wrong line shows the right one and why');
  check(await p.locator('.verdict.bad').count() === 1 && await p.locator('.line.wrong').count() === 1 && await p.locator('.line.right').count() === 1, 'the picked line is marked wrong, the right one right');
  check(await p.locator('input[name=rate]').count() === 0, 'a Learn card has no rating');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(600);
  check(/^Teach/.test(await p.locator('.kind').textContent()), 'the next teach card follows');
  await p.locator('#skipBtn').click(); await p.waitForTimeout(600);
  check(/Skipped/.test(await p.locator('#toastText').textContent()), '"I know this, test me" skips a teach card');
  const t2 = await skip(p, 'argus-code', 'teach', 8);
  check(t2 && t2.kind === 'term', 'the terms come once every teach card is read');
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);

  // the hint ladder on a term card: nudge -> expert's move -> near example -> answer; a reflection before each next rung
  check(await p.locator('#hintBtn').count() === 1, 'a practice card has a Hint button');
  await p.locator('#hintBtn').click(); await p.waitForTimeout(500);
  check(/Hint 1 of 4/.test(await p.locator('#hints').textContent()), 'the first rung is a nudge');
  await p.locator('#hintBtn').click(); await p.waitForTimeout(300);
  check(await p.locator('#hints .hint').count() === 1 && /three words/.test(await p.locator('#toastText').textContent()), 'the next rung waits for a three-word reflection');
  await p.locator('#hints textarea').last().fill('it is the with block'); await p.locator('#hintBtn').click(); await p.waitForTimeout(500);
  check(/expert's first move/.test(await p.locator('#hints').textContent()), 'rung 2 is the expert\'s first move');
  await p.locator('#ans').fill('context manager'); await p.keyboard.press('Enter'); await p.waitForTimeout(600);
  check(await p.locator('.verdict.ok').count() === 1 && /Correct · context manager/.test(await p.locator('#rhead').textContent()) && /2 hints used/.test(await p.locator('#rpanel .deckname').first().textContent()), 'a right term is confirmed (Correct, in green, with a tick) and the hints used are shown');
  check(await p.locator('input[name=rate]:checked').first().inputValue() === '3', 'rung 2 caps the suggested rating at Good');
  check(await p.locator('.defs dt', {hasText: "Where it's used"}).count() === 1, 'the feedback shows where the term is used');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(500);
  // "Show answer" on a blank card offers a hint first; the answer rung counts as a blank
  await p.locator('#checkBtn').click(); await p.waitForTimeout(300);
  check(await p.locator('#offer').count() === 1, 'a blank Show answer offers a hint first');
  await p.locator('#offerAns').click(); await p.waitForTimeout(500);
  check(/Hint 4 of 4/.test(await p.locator('#hints').textContent()) && await p.locator('#checkBtn').textContent() === 'Rate it', 'the answer rung shows the answer and leaves only rating');
  await p.locator('#checkBtn').click(); await p.waitForTimeout(600);
  check(/The answer was shown/.test(await p.locator('#rhead').textContent()) && await p.locator('input[name=rate]:checked').first().inputValue() === '1', 'an answer shown counts as a blank: Again suggested');
  check(/skipped the lesson card/.test(await p.locator('.coach.back').textContent()), 'failing a term whose teach card was skipped says so');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(600);
  check(/^Teach/.test(await p.locator('.kind').textContent()) && /back to the lesson/.test(await p.locator('.deckname').first().textContent()), 'the skipped teach card comes back before anything else');
  check(await p.locator('#guess').count() === 0 && await p.locator('.defs').count() === 1, 'back to the lesson: no second guess, the explanation straight away');
  await skip(p, 'argus-code', 'teach', 1);

  // worked example (level 0) before the first drill: one annotation at a time, the why after three typed words, then a self-explanation
  const l0 = await skip(p, 'argus-code', 'term', 8);
  check(l0 && l0.kind === 'level0', 'worked examples come once every term has been seen');
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(await p.locator('#annot .callout').count() === 1 && await p.locator('#worked .ln.hi').count() === 1, 'level 0 shows annotation 1 and highlights its line');
  await p.locator('#goBtn').click(); await p.waitForTimeout(200);
  check(await p.locator('.needmsg').count() === 1 && await p.locator('#call0 p:not(.needmsg)').count() === 0, 'the note waits for three typed words, and says so');
  await p.locator('#why0').fill('so only one request fetches'); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
  check(/Two requests can arrive at once/.test(await p.locator('#call0').textContent()), 'typing reveals the annotation\'s why');
  await shot(p, 'mentor-level0');
  for (let k = 1; k < 6; k++) { await p.locator('#goBtn').click(); await p.waitForTimeout(150); await p.locator(`#why${k}`).fill('because of this reason'); await p.keyboard.press('Enter'); await p.waitForTimeout(150); }
  await p.locator('#goBtn').click(); await p.waitForTimeout(300);
  check(await p.locator('#annot .ask textarea').count() === 1, 'after the last annotation comes the self-explanation');
  await p.locator('#ans').fill('every path returns the same dict and a failed fetch keeps the old reading'); await p.keyboard.press('Control+Enter'); await p.waitForTimeout(700);
  check(/All 2 key ideas/.test(await p.locator('#rhead').textContent()) && await p.locator('input[name=rate]').count() === 0, 'the self-explanation is graded by its rubric, with no rating');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(500);

  // then drills: blanks typed straight into the code
  const drill = await skip(p, 'argus-code', 'level0', 8);
  check(drill && drill.kind === 'drill' && drill.level === 1, 'drills unlock once every worked example has been read');
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(await p.locator('pre.code input.blank').count() === 2, 'a level 1 drill has two blanks in the code');
  check((await p.locator('.crumb').textContent()).replace('Where in the code: ', '') === 'current()', 'the card says which function, not which folder or file');
  await shot(p, 'mentor-drill-ask');
  await p.locator('input.blank').nth(0).fill('_mem'); await p.keyboard.press('Enter');
  check(await p.evaluate(() => document.activeElement.dataset.n) === '2', 'Enter moves to the next blank');
  await p.keyboard.type('data'); await p.keyboard.press('Enter'); await p.waitForTimeout(600);
  check(/2 of 2 blanks right/.test(await p.locator('#rhead').textContent()), 'both blanks graded right');
  check(/level 2/.test(await p.locator('.seg.rates label').last().textContent()), 'a fast, right answer offers level 2');
  await shot(p, 'mentor-drill');
  await p.keyboard.press('4'); await p.keyboard.press('Enter'); await p.waitForTimeout(700);
  check(/Level 2 next time/.test(await p.locator('#toastText').textContent()), 'the toast says the drill moves up a level');

  // a second fast, right answer (level 2: the logic) takes it to level 3
  const r2 = await api(p, 'answer', {card: 'argus-code:drill_01', text: JSON.stringify(['with _lock', "_mem.get('at', 0) > time.time() - TTL"]), confidence: 4, ms: 1000});
  check(r2.level === 2 && r2.coverage === 1, 'level 2 blanks the logic, and quotes or spacing may differ');
  check((await api(p, 'rate', {attempt: r2.attempt, rating: 4, grade_wrong: false})).level === 3, 'a fast, right answer takes the drill to level 3');

  // stuck: wrong twice in a row sends the drill's worked example back before the next try
  const w1 = await api(p, 'answer', {card: 'argus-code:drill_02', text: JSON.stringify(['x', 'y']), confidence: 3, ms: 3000});
  await api(p, 'rate', {attempt: w1.attempt, rating: 1, grade_wrong: false});
  const w2 = await api(p, 'answer', {card: 'argus-code:drill_02', text: JSON.stringify(['x', 'y']), confidence: 3, ms: 3000});
  check(w2.stuck === 'repeat' && /Look at|returns|hands back/.test(w2.coach), "two wrong in a row: the coach line gives the expert's first move");
  await api(p, 'rate', {attempt: w2.attempt, rating: 1, grade_wrong: false});
  const back = (await api(p, 'next?deck=argus-code')).card;
  check(back && back.kind === 'level0' && back.id === 'argus-code:level0-drill_02' && back.refresh, 'the worked example comes back first');
  const rp = (await api(p, 'next?replay=' + encodeURIComponent('argus-code:drill_02'))).card;
  check(rp && rp.id === 'argus-code:drill_02' && rp.code && !('answer' in rp), "replaying a mistake asks the practice card again, without its answer");
  check((await api(p, 'next?replay=' + encodeURIComponent('argus-code:level0-drill_02'))).card === null, 'replay never serves a Learn card');
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(/back to the lesson/.test(await p.locator('.deckname').first().textContent()), 'the page says it is back to the lesson');
  await skip(p, 'argus-code', 'level0', 1);

  // lessons view: the breakdown, progress, the Learn cards to read again, and the inbox
  fs.mkdirSync(INBOX, {recursive: true});
  const mod = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'themes', 'leafy-realm', 'decks', 'argus-code.json')));
  mod.metadata.module_name = 'inbox_test_module'; mod.metadata.project = 'test-project';
  fs.writeFileSync(path.join(INBOX, '20261020_120000_inbox_test.json'), JSON.stringify(mod));
  fs.writeFileSync(path.join(INBOX, '20261020_120100_broken.json'), '{"tier_1_faded_code_drills": [');
  await p.locator('[data-view=modules]').click(); await p.waitForTimeout(700);
  check(await p.locator('.module').count() === 2, 'a lesson copied into the inbox shows up without a restart');
  check(await p.locator('.course-list .module .mrow button[data-study]').count() === 2 && await p.locator('.modules .cont button[data-study]').count() === 1, 'each lesson is one row with one action, under one Continue');
  await p.locator('.module').first().locator('details', {hasText: 'Read the lesson again'}).locator('summary').click();
  check(await p.locator('.module').first().locator('[data-read]').count() === 18, 'every Learn card of a lesson can be read again');
  await p.locator('.module').first().locator('[data-read]').nth(1).click(); await p.waitForTimeout(600);
  check(/reading again/.test(await p.locator('.deckname').first().textContent()) && /line 2/.test(await p.locator('#spotq').textContent()), 'a teach card opens read-only with its answer');
  check(await p.locator('.callout.tried').count() === 1 && await p.locator('#guess').count() === 0, 'read-only, the try-first question is text with no guess step');
  await p.locator('#doneBtn').click(); await p.waitForTimeout(600);
  check(await p.locator('.ideas li.miss', {hasText: 'broken.json'}).count() === 1, 'a broken inbox file is listed with what is wrong');
  await p.locator('.module details summary').first().click();
  check(await p.locator('.module .defs dt', {hasText: 'The big picture'}).first().isVisible(), 'the breakdown opens');
  await shot(p, 'mentor-modules');
  await p.locator('.module', {hasText: 'inbox test module'}).locator('[data-study]').click(); await p.waitForTimeout(600);
  check(await p.locator('#mdeck').inputValue() === '20261020_120000_inbox_test' && /^Orientation/.test(await p.locator('.kind').textContent()), 'Start on a lesson row opens its orientation');

  // a pre-read before each explain card: the key ideas, then a near example to answer before the reveal
  for (const k of ['term', 'level0', 'drill']) await skip(p, 'argus-code', k, 8);
  await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(/^Before the bug hunt/.test(await p.locator('.kind').textContent()) && await p.locator('#guess').count() === 1 && await p.locator('.ideas.keys').count() === 0, 'a pre-read asks its try-first question first');
  check(await p.locator('#tryBtn').textContent() === 'Show the ideas', "a pre-read's button says the ideas come next");
  await p.locator('#guess').fill('the file is half there'); await p.locator('#tryBtn').click(); await p.waitForTimeout(400);
  check(await p.locator('.ideas.keys li').count() === 2, 'then lists the ideas the bug hunt rests on');
  await p.locator('#ans').fill('a half written file'); await p.keyboard.press('Enter'); await p.waitForTimeout(600);
  check(/truncated LOG/.test(await p.locator('.model').last().textContent()), 'the near example reveals its answer after a typed guess');
  await p.locator('#rateBtn').click(); await p.waitForTimeout(500);
  await skip(p, 'argus-code', 'preread', 8);
  // explain cards come after the pre-reads; fenced code in the prompt is shown as code
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  check(await p.locator('.kind').textContent() === 'Find the bug' && await p.locator('.prompt pre.code').count() === 1, 'a pre-mortem card shows its code');
  await p.evaluate(() => { localStorage.setItem('mentor-streak', '2'); window.moteCalls = 0; const m = fx.motes; fx.motes = (...a) => { moteCalls++; return m(...a); }; });   // two right in a row already
  await p.locator('#ans').fill('A crash leaves a truncated file, so json load fails next start. Write a temp file then os.replace, which is atomic.');
  await p.keyboard.press('Control+Enter');
  const leaves = await p.waitForFunction(() => document.querySelectorAll('#fx > .p').length > 0, null, {timeout: 1500}).then(() => true, () => false);
  await p.waitForTimeout(600);
  check(/3 of 3 key ideas/.test(await p.locator('#rhead').textContent()), 'the explanation covers all three key ideas');
  check(leaves, 'each key idea you got pops a few olive leaves (api.fx.burst)');
  check(await p.locator('.mentor').getAttribute('data-streak') === '3' && /· 3 in a row$/.test(await p.locator('#rpanel .deckname').first().textContent()) && await p.evaluate(() => moteCalls) === 1,
    "three cards in a row with every key idea: the panel says so and motes rise to Mentor's medallion (api.fx.motes)");
  await p.locator('#rateBtn').click(); await p.waitForTimeout(500);

  // level 3: write the whole body (auto-indent); Python reads it, never runs it
  await skip(p, 'argus-code', 'explain', 8);
  // an older lesson file without Learn fields still imports and gets derived Learn cards
  const old = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'themes', 'leafy-realm', 'decks', 'argus-code.json')));
  old.metadata.module_name = 'old_shape'; delete old.cta_summary.orientation; delete old.cta_summary.expert_move;
  for (const t of old.tier_3_terminology_cards) { delete t.spot_it; delete t.hints; delete t.expert_move; delete t.try_first; }
  for (const d of old.tier_1_faded_code_drills) { delete d.level_0_worked; delete d.hints; delete d.look_at; delete d.expert_move; }
  for (const c of old.tier_2_self_explanation_cards) { delete c.preread; delete c.hints; delete c.expert_move; }
  fs.writeFileSync(path.join(INBOX, '20261020_120200_old_shape.json'), JSON.stringify(old));
  const o1 = (await api(p, 'next?deck=20261020_120200_old_shape')).card;
  check(o1 && o1.kind === 'orientation' && /browser asks the Python server/.test(o1.prompt), 'an old lesson gets an orientation from its big picture');
  const h = await api(p, 'answer', {card: '20261020_120200_old_shape:drill_01', hint: 1});
  check(h.rung === 2 && /returns/.test(h.text) && h.next === 4, 'a card without authored hints skips to the expert\'s move, then the answer');
  await p.selectOption('#mdeck', ''); await p.selectOption('#mdeck', 'argus-code'); await p.waitForTimeout(600);
  const ta2 = await api(p, 'answer', {card: 'argus-code:term_02', text: 'generator expression', confidence: 4, ms: 2000});   // else it is the soonest-due card
  await api(p, 'rate', {attempt: ta2.attempt, rating: 4, grade_wrong: false});
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
  check(await noOverflow(ph), 'phone: no sideways scrolling on lessons');
  await ph.locator('.module').first().locator('details', {hasText: 'Read the lesson again'}).locator('summary').click();
  await ph.locator('.module').first().locator('[data-read*="level0"]').first().click(); await ph.waitForTimeout(600);
  check(await ph.locator('#annot .callout').count() >= 1 && await noOverflow(ph), 'phone: a worked example with its callouts fits without sideways scrolling');
  await shot(ph, 'mentor-phone-level0');

  // placeholders: a lesson says {{SERVER}}; Mentor fills it from ~/.config/leafy/realm.json, else the public default
  const REALM = path.join(process.env.FIXTURES || '.', '..', 'home', '.config', 'leafy', 'realm.json');
  fs.writeFileSync(path.join(INBOX, '20261020_120300_realm.json'), JSON.stringify({metadata: {module_name: 'realm_test'},
    tier_3_terminology_cards: [{term: '{{SERVER}}', concise_definition: 'The always-on machine; its files are under {{HOME_SERVER}}.',
      cloze_prompt: 'You reach it with `ssh {{SSH}}`; its name is {{BLANK}}.', project_anchor: '{{REPO_URL}} is cloned on it.'}]}));
  const DECK = '20261020_120300_realm';
  const d1 = (await api(p, 'next?deck=' + DECK)).card;
  check(d1 && d1.kind === 'teach' && d1.prompt === 'homeserver' && /under ~\./.test(d1.definition), 'without realm.json a placeholder shows its public default');
  check(d1.try === '', 'a teach card without try_first has no question to try first (the page shows it straight away)');
  fs.mkdirSync(path.dirname(REALM), {recursive: true});
  fs.writeFileSync(REALM, JSON.stringify({SERVER: 'TestHost', ssh: 'thost', REPO_URL: 'https://example.com/elaia'}));
  const d2 = (await api(p, 'next?deck=' + DECK)).card;
  check(d2.prompt === 'TestHost' && d2.anchor === 'https://example.com/elaia is cloned on it.', 'with realm.json the same card shows its values, with no restart');
  await skip(p, DECK, 'teach', 1);
  const rt = (await api(p, 'next?deck=' + DECK)).card;
  check(rt.kind === 'term' && /ssh thost/.test(rt.prompt) && !/\{\{(SSH|SERVER)\}\}/.test(rt.prompt), 'every field is filled, a lowercase key too');
  const ra = await api(p, 'answer', {card: rt.id, text: 'testhost', confidence: 3, ms: 2000});
  check(ra.coverage === 1 && ra.reference === 'TestHost', 'grading compares against the filled-in text');
  await p.selectOption('#mdeck', ''); await p.waitForTimeout(300);
  await p.locator('[data-view=modules]').click(); await p.waitForTimeout(600);
  check(await p.locator('.module', {hasText: 'realm test'}).locator('[data-read]', {hasText: 'TestHost'}).count() === 1, 'the Lessons view shows the filled-in name too');
  fs.unlinkSync(REALM);

  // submenus (4.22.0): a lesson whose project reads "MENU › Sub" sits in its own group, with Study all choices for
  // the submenu and for the whole menu; a group choice studies every lesson in it, and its stats count them together
  const sub = JSON.parse(JSON.stringify(mod));
  sub.metadata.module_name = 'submenu lesson'; sub.metadata.project = 'GAME_RESEARCH › Topics';
  fs.writeFileSync(path.join(INBOX, '20261020_120400_submenu.json'), JSON.stringify(sub));
  await p.locator('[data-view=modules]').click(); await p.waitForTimeout(700);
  check(await p.locator('#mdeck optgroup[label="GAME_RESEARCH › Topics"] option[value="20261020_120400_submenu"]').count() === 1, 'a "MENU › Sub" lesson sits in its submenu');
  check(await p.locator('#mdeck option[value="group:GAME_RESEARCH"]').count() === 1 && await p.locator('#mdeck option[value="group:GAME_RESEARCH › Topics"]').count() === 1, 'the menu and the submenu each offer Study all');
  check(await p.locator('#mdeck optgroup[label="Lessons"] option[value="20261020_120400_submenu"]').count() === 0, 'a submenu lesson is not repeated under Lessons');
  const g = (await api(p, 'next?deck=' + encodeURIComponent('group:GAME_RESEARCH'))).card;
  check(g && g.id.startsWith('20261020_120400_submenu:'), 'Study all of a menu serves a card from a lesson under it');
  const gs = await api(p, 'stats?deck=' + encodeURIComponent('group:GAME_RESEARCH › Topics'));
  const one = await api(p, 'stats?deck=20261020_120400_submenu');
  check(gs.cards === one.cards && gs.cards > 0, 'a group\'s stats count the cards of its lessons');
  const none = await api(p, 'stats?deck=' + encodeURIComponent('group:NO_SUCH_MENU'));
  check(none.cards === 0, 'an unknown group has no cards (and no error)');

  // courses (4.26.0): a course file in the inbox shows as one group in Lessons, its lessons in order; check items never served
  fs.copyFileSync(path.join(__dirname, 'deck-fixtures', 'good-course.json'), path.join(INBOX, 'demo-server.json'));
  await p.locator('[data-view=modules]').click(); await p.waitForTimeout(700);
  const cg = p.locator('section.group', {has: p.locator('h2', {hasText: 'Rebuild a small web server'})});
  check(await cg.locator('.module h4').allTextContents().then(t => t.join('|')) === 'The words for a request|Why a cross-site POST is refused|When to fetch again', 'a course shows as one group in Lessons, its lessons in course order');
  const cs = await api(p, 'stats');
  check(cs.courses && cs.courses[0].id === 'demo-server' && cs.courses.at(-1).id === 'loose', 'stats lists the course first and Loose lessons last');
  await cg.locator('button[data-study^="group:"]').click(); await p.waitForTimeout(600);
  const cc = (await api(p, 'next?deck=' + encodeURIComponent('group:Rebuild a small web server'))).card;
  check(cc && cc.id.startsWith('demo-server--'), 'Study all on a course serves a card from its lessons');
  check(p.errors.length === 0, 'courses: no page errors ' + p.errors.join(' | '));
});
