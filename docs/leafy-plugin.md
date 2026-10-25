# LeafyPlugins

A LeafyPlugin adds a section to Argus without changing Argus's code: drop a folder in, and it gets a pill in the section bar and its own page at `<base>/<id>`. There are two kinds:
- **`static`**: plain files in a sandboxed frame. Spartamelee (a browser game) is the first.
- **`server`**: trusted code with a Python side and a page script that runs inside Elaia's page. The agents' pages use it (Hermes · Delivery, Janus · Map, Zeus · Throne), and Mentor will move to it.

## The folder
```
~/.config/argus-ui/plugins/<id>/        (or $ARGUS_PLUGINS/<id>/)
  plugin.json                           the manifest (never served)
  index.html                            the plugin's page (or whatever "entry" says)
  ...                                   anything it loads, by relative URL
```
Plugins live outside the install, so upgrading Argus keeps them (like the sounds). Argus reads the folder on every request: a deploy shows up on the next page load, no restart needed. Plugins that ship with Elaia itself are *bundled* (see *Bundled plugins* below).

## plugin.json
```json
{
  "id": "spartamelee",
  "name": "Spartamelee",
  "subtitle": "Play",
  "kind": "static",
  "entry": "index.html",
  "icon": "icon.png",
  "version": "0.5.0",
  "order": 10
}
```
| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Must equal the folder name: `a-z`, digits, `-`, starts with a letter, up to 32 characters. Not `olympus`, `home`, `api`, `static`, `plugins`, `all`, `argus`, `play` or a built-in API route. An agent key only with `"agent": true` (below). |
| `name` | yes | Shown on the pill and as the page title (40 characters max). |
| `subtitle` | no | The pill's small line, e.g. "Play" (40 max). |
| `kind` | no | `static` (the default) or `server` (see *Server plugins* below). A folder with any other kind is skipped. |
| `entry` | no | The page to show, relative to the folder. Default `index.html`. |
| `icon` | no | A square PNG in the folder for the pill and the page header. Without one, the pill shows a plain laurel-and-blades mark. Icons follow the theme's art rules: drawn to match, approved by the owner. |
| `version` | no | Shown under the frame. |
| `order` | no | Pills sort by `order` (default 100), then name. |
| `agent` | no | `true`: this server plugin takes over the section of the theme's agent with the same id (see *Taking over an agent's section*). |

A folder with a missing or invalid manifest is skipped quietly. If a theme's `coming_soon` list has an entry with the same `name`, the "coming later" pill disappears once the plugin is installed.

## What a static plugin gets
- **Its section, `<base>/<id>`.** Argus's page as a side page (Argus in the corner, the section bar on top), with the plugin's `entry` in a frame that fills the content area, plus a "Show full screen" button. The 15-second refresh never reloads the frame, so a game keeps running.
- **Its files at `<base>/plugins/<id>/...`.** These are served from the plugin's folder only: the same path guard as `static/`, so `..` can't climb out, and `plugin.json` is never served. `plugins/<id>` redirects to `plugins/<id>/` so relative URLs work. Types are set for `.js`/`.mjs` (`text/javascript`), `.json`, `.glb`, `.wasm`, images and the like.
- **Relative URLs only.** Argus runs at `/` and at `/argus/` (behind `tailscale serve`), so a plugin must never use absolute paths. Spartamelee's `dist/` already works under any base path.

## The sandbox, and why
A plugin's frame and files run in a **sandbox with an opaque origin**. The iframe has `sandbox="allow-scripts allow-pointer-lock allow-popups"`, and every plugin file is also sent with `Content-Security-Policy: sandbox ...`, so the sandbox holds even when a plugin page is opened in its own tab.
- **What it can do:** run scripts, use WebGL, gamepads (`allow="gamepad"`), full screen and pointer lock, and fetch its own files. Plugin files carry `Access-Control-Allow-Origin: *` because ES modules and `fetch()` from an opaque origin are CORS requests.
- **What it can't do:**
  - **Use Argus's powers.** POSTs from it send `Origin: null` and are refused, so a plugin can't freeze, thaw or run your tasks.
  - **Read `api/state` or task logs.** Those send no CORS header.
  - **Touch Argus's cookies or storage, or navigate the Argus page.**
- **Storage:** a plugin's `localStorage` is not durable inside the sandbox. Treat it as per-visit, or keep state in the URL.

## Server plugins
A server plugin is **trusted code**: only the owner installs plugins, so its page runs inside Elaia's page (no frame, no sandbox) and its Python side runs inside Elaia's server. Install only code you would put in Elaia itself.
```
~/.config/argus-ui/plugins/<id>/
  plugin.json        "kind": "server" (never served)
  plugin.py          the Python side (never served)
  page.js            the page script
  page.css           optional style sheet
```
Extra manifest fields: `"server"` (default `plugin.py`), `"page"` (default `page.js`), `"style"` (optional), `"max_body"` (optional, 4.23.0: the largest POST in bytes its `api/<id>/...` accepts; default and minimum 4096, at most 64 MB, for a page that saves long records or uploads images; Elaia's own routes keep 4 KB). `entry` is not used.

**Python side.** At startup Elaia imports `plugin.py` by its path and calls `init(ctx)` once, if it has one. A plugin that fails to import or whose `init` raises is logged (`skipped server plugin <id>` and the traceback, in Elaia's journal) and gets no pill, no section and no API; the rest of Elaia starts. **A new or changed `plugin.py` needs a restart**: a deploy restarts Elaia, or run `systemctl --user restart argus-ui`; `page.js` and `page.css` are fetched fresh after a change, like static plugins.
- `ctx.id`, `ctx.version` (Elaia's version), `ctx.config_dir` (the plugin's folder, bundled or yours), `ctx.theme_dir` (the installed theme: `theme.json`, `decks/`, `icons/`), `ctx.data_dir` (`~/.local/share/argus-ui/plugins/<id>/`, made for it: keep files here), `ctx.base_url` (`/argus/`, or `ARGUS_BASE_URL`).
- `GET api/<id>/<path>` calls `get(path, query, ctx)`; `POST api/<id>/<path>` calls `post(path, body, ctx)`. Both return `(status, obj)`: an HTTP status and anything `json.dumps` takes. `query` is `parse_qs` output (`{'q': ['hi']}`); `body` is the JSON object.
- Each call gets its own `ctx` with `ctx.headers`: `Tailscale-User-Login`, `Tailscale-User-Name` and `X-Forwarded-For` when the request has them. They say who is asking only behind `tailscale serve` with Elaia bound to `127.0.0.1`. **A plugin never decides on them itself**: it passes them to the agent's CLI, and Janus checks them (`janus verify-approval`).
- POSTs pass Elaia's checks before `post()` is called: host allowlist, JSON only, same-origin `Origin`/`Sec-Fetch-Site`, 4 KB at most. They run one at a time per plugin. GETs run side by side and **must not change anything** (a GET has no cross-site check).
- An exception, or an answer that isn't `(status, obj)`, is a `500 {"ok": false, "msg": "plugin error"}` and a traceback in the journal.
- **`GET api/<id>/status` is reserved** for Elaia's Home page: answer `200, {"line": "1 deploy waiting · argus-ui 4.9.1 live", "needs": true, "action": "Approve argus-ui 4.9.2"}`. `needs: true` puts the plugin in Home's **Needs you** list with `action` as the button (verb-first, 32 characters at most; default "Open <name>"). Elaia passes on only `line` (160 characters at most), `needs` and `action`, or `{"line": null, "needs": false}` when the plugin has none or fails; it never errors (docs/home.md).
- **Reads are file reads; writes call the agent's CLI; the plugin itself never decides.** A plugin reads the agent's status files directly (no subprocess on a GET). A POST runs the agent's own command (`zeus approve …`, `hermes message …`) with fixed arguments, never a shell, and returns what the agent said. Decisions (who may approve, what is allowed through) stay in the agent and Janus.

**Page script.** It runs as a classic script in Elaia's page and registers itself:
```js
leafy.register('<id>', {
  async show(el, api) { … },   // once, when the section opens: fill el
  refresh(el, api) { … },      // optional: every 15 s while the section is open
});
```
- `el` is the section's content area. Nested paths work (4.23.0): `<base>/<id>/<anything>` opens the same section, so a plugin can read `location.pathname` and show a sub-page (Ariad-Node: `/ariad-node/bestiary`); the page sets a `<base href>` so Elaia's own files still load.
- (continued) `el` The side-page layout is Elaia's: the plugin's icon and name in the title, Argus in the corner, the pill on top.
- `api.get(path)` and `api.post(path, body)` call the plugin's own `api/<id>/…` and resolve to `{ok, status, data}`. They never throw: no answer is `{ok: false, status: 0}`.
- `api.esc` (escape text for HTML), `api.toast(text)`, `api.url(path)` and `api.plugin` (the manifest as the page sees it).
- `api.fx` (the shared effects: `burst`, `motes`, `glint`, `pieces`, `bolt`) and `api.holdConfirm(button, onDone)` for anything that changes what runs (docs/fx.md, Elaia 4.18 and later). Both handle reduced motion themselves. From Elaia 4.20, `api.argus.react('nod' | 'wince')` and `api.argus.watch(el)` let the characters answer the user (docs/fx.md); check `api.argus` exists before using it.
- Escape anything you put into HTML with `api.esc`. Keep to Elaia's UI rules (CLAUDE.md): 44 px hit areas, verb-first button labels, a keyboard path, `prefers-reduced-motion`, no sideways scroll at 375 px.
- If the script fails to load or doesn't register, the section says so and asks for a reload.

**A minimal example** (the test fixture `tests/plugin-fixtures/demo-server/` is this, plus a style sheet):
```python
# plugin.py
def get(path, query, ctx):
    if path == 'ping': return 200, {'pong': True}
    if path == 'status': return 200, {'line': 'all well'}
    return 404, {'ok': False, 'msg': 'not found'}

def post(path, body, ctx):
    if path == 'echo': return 200, {'ok': True, 'echo': str(body.get('text', ''))[:100]}
    return 404, {'ok': False, 'msg': 'not found'}
```
```js
// page.js
leafy.register('demo-server', {
  async show(el, api) {
    const {ok, data} = await api.get('ping');
    el.innerHTML = `<p>${ok && data.pong ? 'pong' : 'no answer'}</p>`;
  },
});
```
A sandboxed static plugin can't read a server plugin's API: those answers carry no CORS header, and its POSTs fail the same-origin check.

## Bundled plugins
A plugin that ships with Elaia lives in the repo's `plugins/<id>/` folder, with the same files as above. `scripts/build.sh` puts it in the package and every install copies it to `~/.local/share/argus-ui/bundled/<id>/` (or `$ARGUS_BUNDLED`), setting the old copy aside with the rest of the previous version. So a bundled plugin is updated by a deploy, like Elaia's own code, while yours in `~/.config/argus-ui/plugins/` are left alone.
- **Yours win.** A plugin of yours with the same id replaces the bundled one completely (its `plugin.py` is never imported), so you can try a changed copy without touching the install.
- The log says `loaded server plugin <id> <version> (bundled)` for a bundled one.

## Taking over an agent's section
A server plugin whose id is one of the theme's agent keys and whose manifest says `"agent": true` *is* that agent's section: `<base>/<key>` shows the plugin's page, and `api/<key>/...` goes to its `plugin.py`, ahead of any built-in route of that name. Without `"agent": true`, a folder named after an agent is skipped, so a plugin can never take a section by accident.
- `name` and `subtitle` default to the agent's name and the first part of its domain from the theme; the pill and page header use the agent's icon (`static/icons/<key>.png`) unless the plugin has its own.
- The pill stays where the agent's pill was. Home gets the plugin's tile with its `api/<key>/status` line.
- The agent's tasks, if it has any, still show on the Watch page.

**Mentor** is the first bundled plugin (`plugins/mentor/`, `"agent": true`): the worked example of a big one. Its database stays where it always was, outside `ctx.data_dir`, so the move kept everyone's history.

Leaving a section loads a new page, so a plugin's timers and listeners end with it; there is no `hide()`.

## Checking a plugin
`bash tests/run.sh bundled` installs `tests/bundled-fixtures/` as bundled plugins: `heracles` (`"agent": true`, checks the section, pill, icon, `ctx.theme_dir` and its Home tile) and a `demo-server` that the owner's copy must replace without importing it. A fixture `chronos` without `"agent": true` must be skipped.

`bash tests/run.sh plugins` installs the fixtures from `tests/plugin-fixtures/` (static `spartamelee`, server `demo-server`, and `demo-broken`, whose `plugin.py` fails on purpose) into a throwaway HOME and checks the whole flow:
- the pill appears and replaces a matching "coming later" pill
- the section shows the frame, and the frame loads its module script and JSON
- the 15-second refresh keeps the frame
- the sandbox blocks a POST to `api/freeze`
- `..` and `plugin.json` aren't served
- no sideways scrolling at 375 px
- server plugins: the pill and section, the page script inside the page, its style sheet, `GET api/demo-server/ping` with `ctx.headers` and the data folder, a POST from the page, refused POSTs (cross-site, not JSON, over 4 KB), the `status` line, an exception as a 500, `plugin.py` never served, `refresh()` on the 15-second refresh, and `demo-broken` skipped while Elaia keeps answering
