// Mentor's local AI is retired from study (4.55, docs/mentor-ai.md): even with tests/fixtures/fake_model.py running and a
// config that turns it on, an answer is never sent to it, nothing is "pending", and the page shows no AI part.
// The config file is taken away again at the end.
const {BASE, check, page: page0, run} = require('./lib');
const page = async (b, ...a) => { const x = await page0(b, ...a); await x.addInitScript(() => { try { localStorage.setItem('mentor-view', 'practice'); } catch (e) {} }); return x; };
const fs = require('fs'), path = require('path');
const CFG = path.join(path.dirname(process.env.FIXTURES), 'home/.config/argus-ui/mentor-ai.json');
const api = (p, what, body) => body ? p.request.post(BASE + 'api/mentor/' + what, {data: body}).then(r => r.json()) : p.request.get(BASE + 'api/mentor/' + what).then(r => r.json());
const config = obj => { fs.mkdirSync(path.dirname(CFG), {recursive: true}); fs.writeFileSync(CFG, JSON.stringify(obj)); };
run(async b => {
  const p = await page(b);
  try {
    config({enabled: true, api: 'ollama', url: `http://127.0.0.1:${process.env.MODEL_PORT}`, embed_model: 'fake-embed', chat_model: 'fake-chat', feedback: true});
    const s = await api(p, 'ai');
    check(s.retired === true && s.enabled === false, 'the status says retired, whatever the config says');
    const {card} = await api(p, 'next?deck=ux-hci');
    const r = await api(p, 'answer', {card: card.id, text: 'users, their tasks, interfaces and how people think', confidence: 3, ms: 1000});
    check(r.ok && !r.ai_pending, 'an answer starts no AI part');
    const a = await api(p, 'ai?attempt=' + r.attempt);
    check(a.state === 'none', 'an attempt has no AI part');
    await api(p, 'rate', {attempt: r.attempt, rating: 3, grade_wrong: false});

    await p.goto(BASE + 'mentor'); await p.waitForTimeout(800);
    await p.selectOption('#mdeck', 'ux-hci'); await p.waitForTimeout(600);
    await p.locator('#ans').fill('people, their tasks and the tools they use'); await p.locator('#checkBtn').click(); await p.waitForTimeout(1500);
    check(await p.locator('#rpanel .aiowl').count() === 0 && !/Meaning match/.test(await p.locator('#rpanel').textContent()), 'the page shows no AI part');
    await p.locator('[data-view=modules]').click(); await p.waitForTimeout(800);
    check(/Local AI: retired from study/.test(await p.locator('#ailine').textContent()), 'the Lessons view says the local AI is retired');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  } finally { fs.rmSync(CFG, {force: true}); }
});
