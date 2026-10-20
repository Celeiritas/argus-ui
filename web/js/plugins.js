// LeafyPlugins (docs/leafy-plugin.md): a plugin's section shows its page in a sandboxed frame.
// The frame gets its own opaque origin, so a plugin can't read Argus's state or use its powers.
const leafy = (() => {
  function show(p) {
    const main = $('#main');
    if (main.querySelector(`.plugin[data-id="${p.id}"]`)) return;   // the 15 s refresh must never restart a running game
    main.innerHTML = `<section class="plugin" data-id="${esc(p.id)}" aria-labelledby="plugin-h">
      <h2 class="sr" id="plugin-h">${esc(p.name)}</h2>
      <iframe class="plugin-frame" src="${esc(url(`plugins/${p.id}/`))}" title="${esc(p.name)}"
        sandbox="allow-scripts allow-pointer-lock allow-popups" allow="gamepad; fullscreen; autoplay" allowfullscreen referrerpolicy="no-referrer"></iframe>
      <div class="plugin-bar"><p>Click the frame or <kbd>Tab</kbd> into it to give ${esc(p.name)} the keyboard.${p.version ? ` <span class="ver">v${esc(p.version)}</span>` : ''}</p>
        <button type="button" class="plugin-full">Show full screen</button></div></section>`;
    const fr = main.querySelector('.plugin-frame');
    main.querySelector('.plugin-full').onclick = () => (fr.requestFullscreen ? fr.requestFullscreen() : Promise.reject()).catch(() => toast('Full screen is not available here'));
  }
  return {show};
})();
