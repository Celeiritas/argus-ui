// Mealie: this week's meal plan from the owner's Mealie, read-only (docs/mealie.md). A bundled server plugin's page script.
// Today first (always shown, planned or not), then each later day that has a meal; each meal is its kind and its name,
// a link to the recipe in Mealie when LeafyGrove knows Mealie's address. Every state says what is wrong and what to do,
// in words. "Check again" sits outside the list, so keyboard focus stays on it across the 15 s redraws.
leafy.register('mealie', (() => {
  const HELP = {
    setup: ['Not set up yet', 'Make an API token in Mealie (your profile, then API Tokens) and save it on the server as mealie-token.txt in LeafyGrove\'s settings folder. The token stays on the server: this page never sees it.'],
    empty: ['Not set up yet', 'The token file is there but empty. Paste the token from Mealie into it, on one line.'],
    badtoken: ['The token file does not hold a token', 'Its first line should be the token from Mealie, alone on the line. Make a new one in Mealie if this one is lost.'],
    config: ['mealie.json could not be read', 'It should hold Mealie\'s address on the server, for example {"url": "http://127.0.0.1:9925"}. Fix it or set it aside to use that default.'],
    refused: ['Mealie refused the token', 'The token was deleted in Mealie or has run out. Make a new one in Mealie and put it in mealie-token.txt.'],
    down: ['Mealie is not answering', 'Mealie may be stopped or restarting. LeafyGrove asks again every 30 seconds; Watch shows whether its task runs.'],
    slow: ['Mealie took too long to answer', 'It may be busy or starting up. LeafyGrove asks again every 30 seconds.'],
    unexpected: ['Mealie answered something unexpected', 'A newer or older Mealie may answer in another shape. LeafyGrove asks again every 30 seconds.'],
  };

  function meal(m, esc) {
    const name = m.href ? `<a href="${esc(m.href)}" rel="noopener noreferrer">${esc(m.name)}<span class="sr"> (recipe in Mealie)</span></a>` : `<span>${esc(m.name)}</span>`;
    return `<li class="meal"><span class="kind">${esc(m.type)}</span>${name}</li>`;
  }
  function day(d, esc) {
    const body = d.meals.length ? `<ul class="meals">${d.meals.map(m => meal(m, esc)).join('')}</ul>` : '<p class="none">No meal planned</p>';
    return `<li class="day"><h4><time datetime="${esc(d.date)}">${esc(d.label)}</time></h4>${body}</li>`;
  }

  let asked = 0;                       // the newest read wins: a slow 15 s refresh never paints over a newer "Check again"
  async function draw(el, api, again) {
    const n = ++asked, {ok, data: d} = await api.get(again ? 'plan?again=1' : 'plan');
    if (n !== asked) return;
    const body = el.querySelector('.mealbody'), sum = el.querySelector('.mealsum'), open = el.querySelector('.mealopen');
    if (!ok || !d) { body.innerHTML = '<div class="empty"><b>No answer from the server</b>The plan comes back on its own when LeafyGrove answers again.</div>'; sum.textContent = ''; return; }
    sum.textContent = d.line || '';
    open.innerHTML = d.open ? `<a class="openmealie" href="${api.esc(d.open)}" rel="noopener noreferrer">Open Mealie</a>` : '';
    if (d.state !== 'ok') {
      const [t, w] = HELP[d.state] || HELP.unexpected;
      body.innerHTML = `<div class="empty${d.state === 'setup' || d.state === 'empty' ? '' : ' problem'}"><b>${api.esc(t)}</b>${api.esc(w)}</div>`;
      return;
    }
    body.innerHTML = `<ol class="days" aria-label="Meal plan, today and the next six days">${d.days.map(x => day(x, api.esc)).join('')}</ol>
      ${d.days.length === 1 ? '<p class="mealnote">Nothing else is planned this week.</p>' : ''}
      ${d.more ? '<p class="mealnote">More meals are planned than fit here: see them in Mealie.</p>' : ''}`;
  }

  return {
    async show(el, api) {
      el.innerHTML = `<div class="mealie panel">
        <div class="mealhead"><div><h3>Meals this week</h3><p class="mealsum" aria-live="polite"></p></div>
          <div class="mealacts"><span class="mealopen"></span><button type="button" class="mealcheck">Check again</button></div></div>
        <div class="mealbody"></div>
        <p class="mealfoot">From Mealie's meal plan, read on the server. LeafyGrove only reads it: plan meals in Mealie.</p></div>`;
      el.querySelector('.mealcheck').onclick = () => draw(el, api, true);
      await draw(el, api);
    },
    refresh(el, api) { return draw(el, api); },
  };
})());
