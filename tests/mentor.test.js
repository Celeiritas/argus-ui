// Mentor page: answer a card, see the plain-word ratings, confirm with the verb button, Argus in the corner.
const {BASE, check, page, noOverflow, shot, run} = require('./lib');
run(async b => {
  const p = await page(b);
  await p.goto(BASE + 'mentor'); await p.waitForTimeout(1000);
  check(await p.locator('body.side').count() === 1, 'Mentor is a side page (Argus in the corner)');
  await p.locator('button[data-deck="psych-design"]').click(); await p.waitForTimeout(400);
  await p.locator('#ans').fill('spread out over time, remembered better than cramming');
  await p.locator('#ans').focus(); await p.keyboard.press('Control+Enter'); await p.waitForTimeout(600);
  const labels = await p.locator('.seg.rates label b').allTextContents();
  check(labels.join('|') === '1. Very well|2. Well enough|3. Not well|4. Needs work', 'ratings read Very well … Needs work');
  check(await p.locator('input[name=rate]:checked').count() === 1, "Mentor's suggestion is preselected");
  await p.keyboard.press('4');
  check(await p.locator('#rateBtn').textContent() === 'Run again in 10 min', 'key 4 picks Needs work and the button says what happens');
  await p.keyboard.press('Enter'); await p.waitForTimeout(700);
  check(/10 minutes/.test(await p.locator('#toastText').textContent()), 'Needs work brings the card back in 10 minutes');
  await shot(p, 'mentor');
  check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  const ph = await page(b, 375, 760); await ph.goto(BASE + 'mentor'); await ph.waitForTimeout(800);
  check(await noOverflow(ph), 'phone: no sideways scrolling');
});
