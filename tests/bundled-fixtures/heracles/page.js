// Test stand-in: a bundled plugin's page in the agent's own section.
leafy.register('heracles', {
  async show(el, api) {
    const {ok, data} = await api.get('where');
    el.innerHTML = `<p id="her-where">${ok ? `from ${api.esc(data.config_dir)}, theme ${data.theme_ok ? 'found' : 'missing'}` : 'no answer'}</p>`;
  },
});
