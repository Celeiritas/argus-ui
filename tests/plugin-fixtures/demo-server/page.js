// Test stand-in for a server plugin's page: runs inside Elaia's page and talks to its own API.
leafy.register('demo-server', {
  async show(el, api) {
    el.innerHTML = `<p id="demo-ping">asking…</p><button type="button" id="demo-echo">Send echo</button><p id="demo-out" aria-live="polite"></p>
      <button type="button" id="demo-hold">Send held echo</button><p id="demo-held"></p>`;
    // hold to confirm (api.holdConfirm, tests/fx.test.js): each completed hold sends one echo and counts it
    let held = 0;
    api.holdConfirm(el.querySelector('#demo-hold'), async () => {
      const r = await api.post('echo', {text: 'held'}); held++;
      el.querySelector('#demo-held').textContent = r.ok ? `held echo ${held}: ${r.data.echo}` : `refused (${r.status})`;
    });
    el.dataset.argus = typeof (api.argus || {}).react;
    el.dataset.fx = ['burst', 'motes', 'glint', 'pieces', 'bolt'].filter(k => typeof (api.fx || {})[k] === 'function').join(' ');
    const {ok, data} = await api.get('ping');
    el.querySelector('#demo-ping').textContent = ok && data.pong ? `pong from ${data.id}` : 'no answer';
    el.querySelector('#demo-echo').onclick = async () => {
      const r = await api.post('echo', {text: 'hello'});
      el.querySelector('#demo-out').textContent = r.ok ? `echo: ${r.data.echo}` : `refused (${r.status})`;
    };
    el.dataset.shows = String(+(el.dataset.shows || 0) + 1);
  },
  refresh(el) { el.dataset.refreshes = String(+(el.dataset.refreshes || 0) + 1); },
});
