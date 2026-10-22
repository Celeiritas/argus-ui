// Test stand-in for a server plugin's page: runs inside Elaia's page and talks to its own API.
leafy.register('demo-server', {
  async show(el, api) {
    el.innerHTML = `<p id="demo-ping">asking…</p><button type="button" id="demo-echo">Send echo</button><p id="demo-out" aria-live="polite"></p>`;
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
