// demo.js - records the README preview: Watch powers, then the Olympus playground. Run with: bash tests/run.sh demo
// Writes $SHOTS/demo.webm; tests/run.sh turns it into docs/screenshots/preview.gif (needs ffmpeg).
const {BASE, center, drag} = require('./lib');
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const b = await chromium.launch(), W = 1280, H = 720;
  const ctx = await b.newContext({viewport: {width: W, height: H}, recordVideo: {dir: process.env.SHOTS, size: {width: W, height: H}}});
  const p = await ctx.newPage(), wait = ms => p.waitForTimeout(ms);
  // Watch: Argus glares at a failed task, the bolt runs one, Medusa turns one to stone
  await p.goto(BASE + '?sky=clear&season=fall&night=0'); await wait(2200);
  let [x, y] = await center(p.locator('.card[data-state="ok"]')); await drag(p, '#boltHome', x, y); await wait(1800);
  [x, y] = await center(p.locator('.card[data-canfreeze="true"]:not([data-state="running"])')); await drag(p, '#medusaHome', x, y); await wait(2600);
  // Olympus playground
  await p.goto(BASE + 'olympus?season=spring&sky=clear&night=0'); await wait(1500);
  const S = await p.evaluate(() => scene.surface());
  await drag(p, '[data-item=bident]', 560, S - 120); await wait(1800);
  [x, y] = await center(p.locator('.skel')); await drag(p, '[data-item=bolt]', x, y); await wait(2400);
  const [dx, dy] = await center(p.locator('[data-item=seeds]'));
  await drag(p, '[data-item=seeds]', 0, 0, [[dx - 40, dy + 40], [dx - 120, dy + 110], [dx - 220, dy + 190], [dx - 320, dy + 260]]); await wait(1600);
  const [ax, ay] = await center(p.locator('[data-item=bow]')); await drag(p, '[data-item=bow]', ax - 220, ay + 140); await wait(1300);
  [x, y] = await center(p.locator('.tree').nth(2)); await drag(p, '[data-item=snake]', x, y); await wait(1200);
  [x, y] = await center(p.locator('.tree').nth(1)); await drag(p, '[data-item=bolt]', x, y); await wait(1400);
  await drag(p, '[data-item=hammer]', 860, S - 60); await wait(900); await drag(p, '[data-item=hammer]', 860, S - 60); await wait(900);
  await drag(p, '[data-item=trident]', 640, S - 200); await wait(3400);
  const v = p.video(); await ctx.close(); await b.close();
  fs.renameSync(await v.path(), path.join(process.env.SHOTS, 'demo.webm'));
  console.log('  recorded demo.webm');
})();
