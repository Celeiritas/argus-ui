// Shared helpers for the browser checks (run through tests/run.sh, which sets BASE, FIXTURES and SHOTS).
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const BASE = process.env.BASE || 'http://127.0.0.1:8097/argus/';
let failed = 0;
function check(ok, what) { console.log(`${ok ? '  ok  ' : '  FAIL'} ${what}`); if (!ok) failed++; }
async function page(b, w = 1440, h = 900) {
  const p = await b.newPage({viewport: {width: w, height: h}});
  p.errors = []; p.on('pageerror', e => p.errors.push(String(e)));
  return p;
}
const center = async loc => { const bb = await loc.first().boundingBox(); return [bb.x + bb.width / 2, bb.y + bb.height / 2]; };
// press on `from`, move to (x, y) slowly, pause, let go: a drop.  fast = list of points: a fling.
async function drag(p, from, x, y, fast) {
  const [sx, sy] = await center(p.locator(from)); await p.mouse.move(sx, sy); await p.mouse.down(); await p.mouse.move(sx + 8, sy + 8, {steps: 2});
  if (fast) for (const [fx, fy] of fast) await p.mouse.move(fx, fy); else { await p.mouse.move(x, y, {steps: 16}); await p.waitForTimeout(150); }
  await p.mouse.up();
}
const noOverflow = p => p.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
const shot = (p, name) => process.env.SHOTS && p.screenshot({path: path.join(process.env.SHOTS, name + '.png')});
// the fake units live in FIXTURES/units.json; edit them to make a task fail etc.
function units(edit) { const f = path.join(process.env.FIXTURES, 'units.json'), u = JSON.parse(fs.readFileSync(f)); edit(u); fs.writeFileSync(f, JSON.stringify(u, null, 1)); }
async function run(fn) {
  const b = await chromium.launch();
  try { await fn(b); } catch (e) { check(false, 'threw: ' + e.message); }
  await b.close(); process.exit(failed ? 1 : 0);
}
module.exports = {BASE, check, page, center, drag, noOverflow, shot, units, run};
