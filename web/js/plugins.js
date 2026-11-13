// LeafyPlugins (docs/leafy-plugin.md).
// A static plugin's section shows its page in a sandboxed frame: its own opaque origin, so it can't read Argus's state or use its powers.
// One with its own address (own-origin.json, 4.42.0) gets an Open button instead: a different origin is the same wall, without the sandbox.
// A server plugin is trusted code the owner installed: its page script runs inside this page and calls leafy.register(id, {show, refresh}).
const leafy = (() => {
  const mods = {}, loads = {};
  function show(p) {
    if (p.kind === 'server') return showServer(p);
    const main = $('#main');
    if (main.querySelector(`.plugin[data-id="${p.id}"]`)) return;   // the 15 s refresh must never restart a running game
    if (p.own) return showOwn(p, main);
    main.innerHTML = `<section class="plugin" data-id="${esc(p.id)}" aria-labelledby="plugin-h">
      <h2 class="sr" id="plugin-h">${esc(p.name)}</h2>
      <iframe class="plugin-frame" src="${esc(url(`plugins/${p.id}/`))}" title="${esc(p.name)}"
        sandbox="allow-scripts allow-pointer-lock allow-popups" allow="gamepad; fullscreen; autoplay" allowfullscreen referrerpolicy="no-referrer"></iframe>
      <div class="plugin-bar"><p>Click the frame or <kbd>Tab</kbd> into it to give ${esc(p.name)} the keyboard.${p.version ? ` <span class="ver">v${esc(p.version)}</span>` : ''}</p>
        <button type="button" class="plugin-full">Show full screen</button></div></section>`;
    const fr = main.querySelector('.plugin-frame');
    main.querySelector('.plugin-full').onclick = () => (fr.requestFullscreen ? fr.requestFullscreen() : Promise.reject()).catch(() => toast('Full screen is not available here'));
  }
  // A static plugin with its own address (own-origin.json on the server, 4.42.0): no frame, a button that opens it in its own
  // tab, where its cache, storage and downloads work, plus its extra pages. The address is the host name this page was opened
  // at with the plugin's port: the HTTPS port tailscale serve publishes it on, or its local port when this page is plain http.
  function showOwn(p, main) {
    const base = `${location.protocol}//${location.hostname}:${location.protocol === 'https:' ? p.own.public : p.own.local}/`;
    const links = (p.own.links || []).map(l => `<a href="${esc(base + l.path)}" target="_blank" rel="noopener">${esc(l.name)}<span class="sr"> (opens in a new tab)</span></a>`).join('');
    main.innerHTML = `<section class="plugin plugin-own" data-id="${esc(p.id)}" aria-labelledby="plugin-h">
      <h2 class="sr" id="plugin-h">${esc(p.name)}</h2>
      <div class="plugin-own-card">
        <a class="plugin-open primary" href="${esc(base)}" target="_blank" rel="noopener">Open ${esc(p.name)}<span class="sr"> (opens in a new tab)</span></a>
        ${links ? `<nav class="plugin-links" aria-label="More of ${esc(p.name)}">${links}</nav>` : ''}
        <p>${esc(p.name)} opens in its own tab, at its own address, so it loads quickly after the first visit and keeps your notes.${p.version ? ` <span class="ver">v${esc(p.version)}</span>` : ''}</p>
      </div></section>`;
  }

  // What a server plugin's page gets: its own API (api/<id>/...), answers as {ok, status, data}, and Elaia's helpers:
  // the shared effects (fx.js) and hold-to-confirm (hold.js), so every page gives the same feedback.
  function api(p) {
    const call = async (path, init) => {
      try { const r = await fetch(url(`api/${p.id}/${path}`), init); return {ok: r.ok, status: r.status, data: await r.json().catch(() => null)}; }
      catch (e) { return {ok: false, status: 0, data: null}; }                     // no answer: the server is down or the network is
    };
    return {plugin: p, url, esc, toast, fx, holdConfirm, argus: {react: look.react, watch: look.watch},
      get: path => call(path, {cache: 'no-store'}),
      post: (path, body) => call(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})})};
  }
  // the page script (and style) load once, versioned by the server; the script registers itself
  function load(p) {
    return loads[p.id] ||= new Promise((ok, fail) => {
      if (p.style) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = url(p.style); document.head.append(l); }
      const s = document.createElement('script'); s.src = url(p.page);
      s.onload = () => mods[p.id] ? ok(mods[p.id]) : fail(new Error(`${p.page} did not call leafy.register('${p.id}', …)`));
      s.onerror = () => fail(new Error(`${p.page} did not load`));
      document.head.append(s);
    });
  }
  function showServer(p) {
    const main = $('#main'), open = main.querySelector(`.plugin-server[data-id="${p.id}"]`);
    if (open) { if (open.dataset.ready) mods[p.id].refresh?.(open.querySelector('.plugin-body'), api(p)); return; }   // the 15 s refresh: new data, same page
    main.innerHTML = `<section class="plugin plugin-server" data-id="${esc(p.id)}" aria-labelledby="plugin-h">
      <h2 class="sr" id="plugin-h">${esc(p.name)}</h2><div class="plugin-body" aria-busy="true"><p class="plugin-wait">Loading ${esc(p.name)}…</p></div></section>`;
    const sec = main.querySelector('.plugin-server'), body = $('.plugin-body', sec);
    load(p).then(m => { body.innerHTML = ''; body.removeAttribute('aria-busy'); sec.dataset.ready = '1'; return m.show(body, api(p)); })
      .catch(e => { console.error(e); delete sec.dataset.ready; body.removeAttribute('aria-busy');
        body.innerHTML = `<div class="empty"><b>${esc(p.name)} didn't load</b>Reload the page to try again. If it keeps happening, check the plugin's page script on the server.</div>`; });
  }
  function register(id, mod) { mods[id] = mod; }
  return {show, register};
})();
