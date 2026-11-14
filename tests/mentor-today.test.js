// Mentor 4.38 in the browser: Today first ("Who is studying?", one button "Study 10 minutes", pinned tracks, the week, the
// shelf), the timed session and its summary, think-it on a phone and typing on a wide screen, reduced motion, 375 px.
// It studies as "Learner Two" (a placeholder person in a people file inside the throwaway HOME), so the owner's database,
// which tests/mentor.test.js walks through next, is only read. The people file is taken away again at the end.
// Since #45 the server tells Mentor who is asking: tests/run.sh starts it as Tailscale Serve, so a browser that sends
// Tailscale-User-Login is that person (docs/people.md), and with a people file a request without a listed login has no
// person and is refused. Every page here comes in with the owner's or the learner's login, as tests/people.test.js does.
const {BASE, check, noOverflow, shot, run} = require('./lib');
const fs = require('fs'), path = require('path');
const HOME = path.join(path.dirname(process.env.FIXTURES), 'home');
const PEOPLE = path.join(HOME, '.config', 'argus-ui', 'people.json');
const LDECKS = path.join(HOME, '.local', 'share', 'argus-ui', 'decks-learner-two');
const api = (p, what, body) => body ? p.request.post(BASE + 'api/mentor/' + what, {data: body}).then(r => r.json()) : p.request.get(BASE + 'api/mentor/' + what).then(r => r.json());
const L = 'learner=learner-two';
const OWNER = 'owner@example.com', LEARNER = 'learner@example.com';
const page = async (b, w = 1440, h = 900, login = OWNER, extra = {}) => {
  const ctx = await b.newContext({viewport: {width: w, height: h}, extraHTTPHeaders: {'Tailscale-User-Login': login, 'X-Forwarded-For': '192.0.2.20'}, ...extra});
  const p = await ctx.newPage(); p.errors = []; p.on('pageerror', e => p.errors.push(String(e))); return p;
};
const small = async (p, sel) => (await p.locator(sel).evaluateAll(els => els.filter(e => e.offsetParent && e.getBoundingClientRect().height < 44).map(e => e.textContent.trim().slice(0, 30))));
run(async b => {
  fs.mkdirSync(path.dirname(PEOPLE), {recursive: true});
  fs.writeFileSync(PEOPLE, JSON.stringify({people: [{id: 'owner-one', name: 'Owner One', role: 'owner', logins: ['owner@example.com']},
    {name: 'Learner Two', role: 'learner', logins: ['learner@example.com']}]}));
  fs.mkdirSync(LDECKS, {recursive: true});
  fs.writeFileSync(path.join(LDECKS, 'placeholder.json'), JSON.stringify({id: 'study-skills', name: 'Study skills', cards: [
    {id: 'spacing', prompt: 'Define: spaced practice', answer: 'Spreading study of the same material over several sessions.', points: [{idea: 'spread over sessions', any: ['spread', 'sessions']}]},
    {id: 'retrieval', prompt: 'Define: retrieval practice', answer: 'Recalling an answer from memory instead of reading it again.', points: [{idea: 'recall', any: ['recall', 'memory']}]},
    {id: 'interleave', prompt: 'Define: interleaving', answer: 'Mixing different kinds of problems in one session.', points: [{idea: 'mixing', any: ['mix', 'different']}]}]}));
  try {
    const p = await page(b, 412, 915);
    // the server's answers, per person
    const people = await api(p, 'learners');
    check(people.role === 'owner' && people.people.map(x => x.id).join() === 'owner-one,learner-two', 'api/mentor/learners lists the people for the owner');
    const lt = await api(p, 'today?' + L);
    check(lt.learner.id === 'learner-two' && lt.tracks.map(t => t.id).join() === 'study-skills', "Learner Two's Today has only her own track, none of the owner's");
    const refused = await api(p, 'settings', {learner: 'learner-two', pinned: ['a', 'b', 'c', 'd']});
    check(!refused.ok && /Unpin/.test(refused.msg), 'a fourth pin is refused with a sentence that says how to free a slot');
    const st = await api(p, 'status?' + L);
    check(st.line === '3 new cards waiting' && st.action === '' && st.needs === false, `status asked by the owner: the line, no button and never needs him (Mentor is quiet for the owner, 4.45.0): "${st.line}" · ${st.action}`);

    // Today is the first view: who is studying, one primary button
    await p.goto(BASE + 'mentor'); await p.waitForTimeout(1000);
    check(await p.locator('#go10').textContent() === 'Study 10 minutes' && await p.locator('#mpanel .primary').count() === 1, 'Mentor opens on Today with ONE primary button: Study 10 minutes');
    check(/Who is studying\?\s*Owner One/.test(await p.locator('#mwho').textContent()), 'the header says who is studying');
    check(await p.locator('#mdeck').isHidden(), 'the topic picker is not on Today');
    await p.locator('#whoBtn').click();
    check(await p.locator('#whoList button').count() === 2 && await p.locator('#whoBtn').getAttribute('aria-expanded') === 'true', '"change" opens the people the server allows');
    await p.locator('[data-who="learner-two"]').click(); await p.waitForTimeout(1200);
    check(await p.locator('#mwho b').textContent() === 'Learner Two' && /Learner Two is studying now/.test(await p.locator('#toastText').textContent()), 'picking a name switches the person (remembered on this device)');
    check(/Nothing is pinned yet/.test(await p.locator('.go').textContent()), 'with nothing pinned, Today says what a session uses');
    check(await p.locator('.dots li').count() === 7 && !/streak/i.test(await p.locator('#mpanel').textContent()), 'the week as seven dots, and no streak to break');
    // pin from the shelf: the track becomes a card with "Study this"
    await p.locator('#shelf summary').click();
    check(/Shelf: 0 tracks/.test(await p.locator('#shelf summary').textContent()), 'the shelf row counts the tracks on it');
    await p.locator('[data-pin="study-skills"]').click(); await p.waitForTimeout(700);
    check(await p.locator('.tcard h3').textContent() === 'Study skills' && await p.locator('.tcard [data-study]').count() === 1, 'a pinned track is a card on Today with Study this');
    check(await p.evaluate(() => document.activeElement.dataset.unpin) === 'study-skills', 'focus stays on the track: on its Unpin button');
    await p.locator('[data-preview="study-skills"]').click(); await p.waitForTimeout(500);
    check(/Define: spaced practice/.test(await p.locator('#pv-study-skills').textContent()) && !/Spreading study/.test(await p.locator('#pv-study-skills').textContent()), 'Preview shows the first questions, never an answer');
    await p.locator('[data-shelve="study-skills"]').click(); await p.waitForTimeout(700);
    check(/Shelf: 1 track/.test(await p.locator('#shelf summary').textContent()) && await p.locator('.tcard').count() === 0, 'Shelve takes it off Today and onto the shelf');
    check((await api(p, 'stats?' + L)).new === 0 && (await api(p, 'next?' + L)).card === null, 'a shelved track is never served and never counted');
    await p.locator('[data-unshelve="study-skills"]').click(); await p.waitForTimeout(700);
    await p.locator('[data-pin="study-skills"]').click(); await p.waitForTimeout(700);
    check(await p.locator('.tcard').count() === 1, 'and back: off the shelf, pinned again');
    check((await small(p, '#mpanel button, #mwho button, .views button')).length === 0, 'every button on Today is at least 44 px high: ' + (await small(p, '#mpanel button, #mwho button, .views button')).join(' | '));
    check(await noOverflow(p), 'Today fits 412 px without sideways scrolling');
    await shot(p, 'mentor-today-412');

    // the session, shortened through the answer the page reads its minutes from
    await p.route('**/api/mentor/today*', async r => { const res = await r.fetch(); const j = await res.json(); j.minutes = 0.05; r.fulfill({json: j}); });
    await p.goto(BASE + 'mentor'); await p.waitForTimeout(900);
    await p.locator('#go10').click(); await p.waitForTimeout(700);
    check(await p.locator('#mtime').isVisible() && await p.locator('#mtime [role=progressbar]').count() === 1, 'a thin bar shows the time');
    check(await p.locator('[data-view=today]').getAttribute('aria-pressed') === 'true', 'during a session the Today tab stays marked');
    check(await p.locator('#ans').count() === 0 && await p.locator('#checkBtn').textContent() === 'Show the answer', 'on a phone a card is thought, then revealed: no box to type in');
    check(await p.locator('input[name=conf]').count() === 0, '"How sure are you?" is not asked on every card');
    await p.locator('#modeBtn').click(); await p.waitForTimeout(500);
    check(await p.locator('#ans').count() === 1 && await p.evaluate(() => localStorage.getItem('mentor-answer')) === 'type', 'typing is one tap away, and remembered');
    await p.locator('#modeBtn').click(); await p.waitForTimeout(500);
    check(await p.locator('#ans').count() === 0, 'and back to think it');
    await p.keyboard.press('Space'); await p.waitForTimeout(600);
    const hit = async sel => Math.round((await p.locator(sel).first().boundingBox() || {height: 0}).height);
    await p.locator('details.report summary').click();
    check(await hit('#rateBtn') >= 44 && await hit('details.report label.check') >= 44, `the save button and "grade was wrong" are 44 px targets (${await hit('#rateBtn')}, ${await hit('details.report label.check')})`);
    check(/Here is the answer/.test(await p.locator('#rhead').textContent()) && await p.locator('input[name=rate]:checked').count() === 0, 'Space reveals the answer; nothing is graded, so nothing is preselected');
    await p.locator('#rateBtn').click(); await p.waitForTimeout(300);
    check(/Pick how well you knew it/.test(await p.locator('#toastText').textContent()), 'saving without a rating says what to do');
    await p.waitForTimeout(3200);
    check(/Time's up/.test(await p.locator('#mtleft').textContent()), "when the time is up the bar says so; the card on screen is finished first");
    await p.keyboard.press('3'); await p.locator('#rateBtn').click(); await p.waitForTimeout(1200);
    check(/^1 card, 1 right\.$/.test((await p.locator('#shead').textContent()).trim()), 'then a summary: ' + (await p.locator('#shead').textContent()).trim());
    check(/later today|tomorrow|Next/.test(await p.locator('#spanel .coach').textContent()), 'it says what comes next: ' + (await p.locator('#spanel .coach').textContent()).trim());
    check(await p.locator('#more5').textContent() === 'Keep going 5 more' && await p.locator('#toToday').count() === 1, 'Keep going 5 more, Back to Today');
    await shot(p, 'mentor-summary-412');
    await p.locator('#more5').click(); await p.waitForTimeout(800);
    check(await p.locator('#qform').count() === 1 || /All done for now/.test(await p.locator('#mpanel').textContent()), 'Keep going serves more cards');
    await p.unroute('**/api/mentor/today*');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));

    // everything done today (4.38): no false promise and no big button; "Study a little more" brings cards forward
    for (let i = 0; i < 6; i++) { const {card} = await api(p, 'next?session=1&' + L); if (!card) break;
      const a = await api(p, 'answer', {learner: 'learner-two', card: card.id, text: '', think: true}); await api(p, 'rate', {learner: 'learner-two', attempt: a.attempt, rating: 3}); }
    await p.goto(BASE + 'mentor'); await p.waitForTimeout(900);
    check(/All done for now\./.test(await p.locator('.go').textContent()) && /later today/.test(await p.locator('#golist').textContent()) && /Next: /.test(await p.locator('#golist').textContent()),
      'all done while cards come back later today: "All done for now.", with when the next card comes: ' + (await p.locator('.go').textContent()).replace(/\s+/g, ' ').trim());
    await p.route('**/api/mentor/today*', async r => { const res = await r.fetch(); const j = await res.json(); j.later = 0; r.fulfill({json: j}); });   // nothing more due today
    await p.goto(BASE + 'mentor'); await p.waitForTimeout(900);
    check(/All done for today\./.test(await p.locator('.go h2').textContent()), 'nothing more due today: "All done for today."');
    await p.unroute('**/api/mentor/today*'); await p.goto(BASE + 'mentor'); await p.waitForTimeout(900);
    check(await p.locator('#mpanel .primary').count() === 0 && await p.locator('#go10').count() === 0, 'and the big primary button goes away');
    check(/started/.test(await p.locator('.tcard small').textContent()) && !/learned/.test(await p.locator('#mpanel').textContent()), 'a card answered once is "started", not "learned"');
    await shot(p, 'mentor-all-done-412');
    // a wide screen types by default (the next cards brought forward, a define card)
    const w = await page(b, 1440, 900);
    await w.addInitScript(() => { try { localStorage.setItem('mentor-learner', 'learner-two'); localStorage.removeItem('mentor-answer'); } catch (e) {} });
    await w.goto(BASE + 'mentor'); await w.waitForTimeout(900);
    await w.locator('#goMore').click(); await w.waitForTimeout(800);
    check(await w.locator('#qform').count() === 1 && await w.locator('#ans').count() === 1, 'Study a little more serves a card, and on a wide screen the answer is typed');

    // Lessons: an owner studying as Learner Two sees her real folder; an empty Lessons view points to Today
    await p.locator('[data-view=modules]').click(); await p.waitForTimeout(900);
    check(await p.locator('#toToday2').count() === 1 && /Your questions are on Today/.test(await p.locator('.empty').textContent()), 'no lessons: the view points to Today');
    check(/decks-learner-two/.test(await p.locator('details.about').textContent()) && !/<id>/.test(await p.locator('details.about').textContent()), "the owner sees the person's real lesson folder");
    // ... and Learner Two on her own phone (her own login) sees her name, no picker, and never the owner's steps
    const lp = await page(b, 412, 915, LEARNER);
    await lp.addInitScript(() => { try { localStorage.setItem('mentor-view', 'modules'); localStorage.setItem('mentor-learner', 'owner-one'); } catch (e) {} });
    await lp.goto(BASE + 'mentor'); await lp.waitForTimeout(1200);
    check(await lp.locator('#whoBtn').count() === 0 && /Learner Two/.test(await lp.locator('#mwho').textContent()), 'a learner sees her name and no picker');
    check((await api(lp, 'learners')).people.map(x => x.id).join() === 'learner-two' && (await api(lp, 'today?learner=owner-one')).learner.id === 'learner-two',
      "with her own login she is always herself: learner=owner-one is ignored");
    check(await lp.locator('#toToday2').count() === 1, 'her empty Lessons view points to Today');
    // while Mentor refuses her (the list of people cannot be read; tests/mentor_people_test.py makes the real case), the page
    // shows Mentor's own sentence, not the shell's "didn't load"
    const rf = await page(b, 412, 915, LEARNER);
    await rf.route('**/api/mentor/learners*', r => r.fulfill({status: 503, json: {ok: false, msg: 'The list of people cannot be read right now. Ask the owner.'}}));
    await rf.goto(BASE + 'mentor'); await rf.waitForTimeout(1000);
    check(/The list of people cannot be read right now\. Ask the owner\./.test(await rf.locator('#mrefused').textContent()) && rf.errors.length === 0, "a refusal shows Mentor's sentence");
    check(await lp.locator('ol.steps').count() === 0 && !/mentor_inbox|Claude Code|adding a lesson/.test(await lp.locator('details.about').textContent()), "a learner never sees the owner's steps for adding a lesson");
    await shot(lp, 'mentor-learner-lessons-412');

    // question first on a lesson (the theme's lesson, copied into her folder): a question, Teach me first, and it counts as help
    fs.copyFileSync(path.join(__dirname, '..', 'themes', 'leafy-realm', 'decks', 'argus-code.json'), path.join(LDECKS, 'argus-code.json'));
    const q = await page(b, 1440, 900);
    await q.addInitScript(() => { try { localStorage.setItem('mentor-learner', 'learner-two'); localStorage.setItem('mentor-view', 'practice'); localStorage.setItem('mentor-deck', 'argus-code'); localStorage.setItem('mentor-answer', 'type'); } catch (e) {} });
    await q.goto(BASE + 'mentor'); await q.waitForTimeout(1200);
    check(!/Orientation|Teach ·/.test(await q.locator('.deckname').first().textContent()) && await q.locator('#teachBtn').count() === 1, 'a new lesson starts with a question, with Teach me first');
    await q.locator('#teachBtn').click(); await q.waitForTimeout(600);
    check(await q.locator('#teachbox .taught').count() === 1, 'Teach me first shows the lesson card above the question');
    const box = q.locator('#qform input.blank, #qform textarea#ans').first(); await box.fill('context manager'); await q.keyboard.press('Control+Enter'); await q.waitForTimeout(800);
    check(+(await q.locator('input[name=rate]:checked').inputValue()) <= 2, 'after Teach me first Mentor suggests at most Hard');
    check(q.errors.length === 0 && w.errors.length === 0 && lp.errors.length === 0, 'no page errors ' + [...q.errors, ...w.errors, ...lp.errors].join(' | '));
    const rm = await page(b, 375, 760, OWNER, {reducedMotion: 'reduce'});
    await rm.addInitScript(() => { try { localStorage.setItem('mentor-learner', 'learner-two'); } catch (e) {} });
    await rm.goto(BASE + 'mentor'); await rm.waitForTimeout(900);
    check(await noOverflow(rm), 'Today fits 375 px without sideways scrolling');
    check(parseFloat(await rm.locator('.tfill span').evaluate(e => getComputedStyle(e).transitionDuration)) <= .01 &&await rm.locator('.today').evaluate(e => getComputedStyle(e).animationName) === 'none', 'reduced motion: no slide-in, no gliding bar');
    // a learner herself (the server says who, later): the page shows her name and no picker; here, a person picked by the owner
    check(await rm.locator('#mwho b').textContent() === 'Learner Two', 'the picked person is remembered on this device');
  } finally { fs.rmSync(PEOPLE, {force: true}); }
});
