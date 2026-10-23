// Mentor's local AI (docs/mentor-ai.md) against tests/fixtures/fake_model.py: off by default, a config turns it on,
// the rubric answers at once and the AI's part arrives later (labelled, not used for the rating); a remote URL is refused
// and a server that doesn't answer leaves the rubric's grade alone. The config file is taken away again at the end.
const {BASE, check, page, run} = require('./lib');
const fs = require('fs'), path = require('path');
const CFG = path.join(path.dirname(process.env.FIXTURES), 'home/.config/argus-ui/mentor-ai.json');
const api = (p, what, body) => body ? p.request.post(BASE + 'api/mentor/' + what, {data: body}).then(r => r.json()) : p.request.get(BASE + 'api/mentor/' + what).then(r => r.json());
const config = obj => { fs.mkdirSync(path.dirname(CFG), {recursive: true}); fs.writeFileSync(CFG, JSON.stringify(obj)); };
const wait = ms => new Promise(z => setTimeout(z, ms));
async function settle(p, attempt) { for (let i = 0; i < 30; i++) { const a = await api(p, 'ai?attempt=' + attempt); if (a.state !== 'pending') return a; await wait(200); } return {state: 'timeout'}; }
run(async b => {
  const p = await page(b);
  try {
    let s = await api(p, 'ai');
    check(s.enabled === false, 'off by default: no config file, no AI');
    const {card} = await api(p, 'next?deck=ux-hci');
    let r = await api(p, 'answer', {card: card.id, text: 'something about people and screens', confidence: 2, ms: 1000});
    check(r.ok && !r.ai_pending, 'off: an answer is graded by the rubric alone');

    config({enabled: true, url: 'http://example.com:11434'});
    s = await api(p, 'ai');
    check(s.enabled === false && /not this machine/.test(s.problem), 'a server that is not this machine is refused unless "allow_remote": true');

    config({enabled: true, api: 'ollama', url: `http://127.0.0.1:${process.env.MODEL_PORT}`, embed_model: 'fake-embed', chat_model: 'fake-chat', feedback: true});
    s = await api(p, 'ai');
    check(s.enabled && !s.problem && s.answering === true && s.feedback === true, 'on: the status says which models and that the server answers');
    r = await api(p, 'answer', {card: card.id, text: 'users, their tasks, interfaces and how people think and work with computers', confidence: 3, ms: 1000});
    check(r.ok && r.ai_pending === true && typeof r.suggested === 'number', 'the rubric answers at once; the AI part is pending');
    let a = await settle(p, r.attempt);
    check(a.state === 'done' && a.similarity >= 0 && a.similarity <= 1 && /Fake feedback/.test(a.feedback) && a.model === 'fake-embed', `the AI part arrives: a meaning match (${a.similarity}) and feedback`);
    const close = a.similarity;
    await api(p, 'rate', {attempt: r.attempt, rating: 3, grade_wrong: false});

    config({enabled: true, api: 'openai', url: `http://127.0.0.1:${process.env.MODEL_PORT}`, embed_model: 'fake-embed'});
    r = await api(p, 'answer', {card: card.id, text: 'unrelated words zzz', confidence: 1, ms: 1000});
    a = await settle(p, r.attempt);
    check(a.state === 'done' && a.similarity < close && !a.feedback, `OpenAI-compatible servers work too; unrelated words match less (${a.similarity}); no feedback unless asked for`);

    config({enabled: true, url: 'http://127.0.0.1:9', embed_model: 'fake-embed', timeout_s: 2});
    r = await api(p, 'answer', {card: card.id, text: 'an answer while the model is down', confidence: 2, ms: 1000});
    a = await settle(p, r.attempt);
    check(r.ok && typeof r.suggested === 'number' && a.state === 'error', 'a server that does not answer: the grade stands, the AI part is an error');

    // the page: the owl brings the AI's part under the rubric's result, labelled
    config({enabled: true, url: `http://127.0.0.1:${process.env.MODEL_PORT}`, embed_model: 'fake-embed', chat_model: 'fake-chat', feedback: true});
    await p.goto(BASE + 'mentor'); await p.waitForTimeout(800);
    await p.selectOption('#mdeck', 'ux-hci'); await p.waitForTimeout(600);
    await p.locator('#ans').fill('people, their tasks and the tools they use'); await p.locator('#checkBtn').click();
    const owl = p.locator('#rpanel .aiowl');
    await owl.locator('text=Meaning match').waitFor({timeout: 8000});
    check(/Local AI · fake-chat · not used for the rating/.test(await owl.textContent()) && /Fake feedback/.test(await owl.textContent()), 'the page shows the AI part, labelled and kept apart from the rating');
    check(await p.locator('#rpanel input[name=rate]:checked').count() === 1, 'the rubric still suggests the rating');
    await p.locator('[data-view=modules]').click(); await p.waitForTimeout(800);
    check(/Local AI: on \(fake-embed, feedback by fake-chat\)/.test(await p.locator('#ailine').textContent()), 'the Lessons view says the local AI is on');
    check(p.errors.length === 0, 'no page errors ' + p.errors.join(' | '));
  } finally { fs.rmSync(CFG, {force: true}); }
});
