# LeafyPlugins

A LeafyPlugin adds a section to Argus without changing Argus's code: drop a folder in, and it gets a pill in the section bar and its own page at `<base>/<id>`. There are two kinds:
- **`static`**: plain files in a sandboxed frame, or in a tab of their own at their own address (*Its own address*, 4.42.0). Spartamelee (a browser game) is the first.
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
| `version` | no | Shown under the frame (or next to the Open button). |
| `order` | no | Pills sort by `order` (default 100), then name. |
| `agent` | no | `true`: this server plugin takes over the section of the theme's agent with the same id (see *Taking over an agent's section*). |
| `roles` | no | Server plugins only: which of its `api/<id>/<path>` a learner may call (see *Roles and who*). Everything else is the owner's. |

A folder with a missing or invalid manifest is skipped quietly. If a theme's `coming_soon` list has an entry with the same `name`, the "coming later" pill disappears once the plugin is installed.

## What a static plugin gets
- **Its section, `<base>/<id>`.** Argus's page as a side page (Argus in the corner, the section bar on top), with the plugin's `entry` in a frame that fills the content area, plus a "Show full screen" button. The 15-second refresh never reloads the frame, so a game keeps running.
- **Its files at `<base>/plugins/<id>/...`.** These are served from the plugin's folder only: the same path guard as `static/`, so `..` can't climb out, and `plugin.json` is never served. `plugins/<id>` redirects to `plugins/<id>/` so relative URLs work. Types are set for `.js`/`.mjs` (`text/javascript`), `.json`, `.glb`, `.wasm`, images and the like.
- **Caching.** Every plugin file carries `Last-Modified` and an `ETag`, and a reload that already has the file gets `304 Not Modified` (no body). A content-hashed name, `<name>.<8 lower-case hex>.<ext>` (e.g. `models/ares.1a2b3c4d.glb`), is sent `Cache-Control: public, max-age=31536000, immutable`: change the file, change its name. Every other text file, `*.html`, `*.js`, `*.mjs`, `*.css`, `*.json` and `*.map`, is `no-cache` (checked on every load; cheap with the 304), since these point to the hashed names or change with a deploy (an unhashed stylesheet or mask list would otherwise stay stale for an hour). Everything else (unhashed binaries: models, images, audio, `.wasm`) is `max-age=3600` with the same validators.
- **Relative URLs only.** Argus runs at `/` and at `/argus/` (behind `tailscale serve`), so a plugin must never use absolute paths. Spartamelee's `dist/` already works under any base path.

## The sandbox, and why
A plugin's frame and files run in a **sandbox with an opaque origin**. The iframe has `sandbox="allow-scripts allow-pointer-lock allow-popups"`, and every plugin file is also sent with `Content-Security-Policy: sandbox ...`, so the sandbox holds even when a plugin page is opened in its own tab.
- **What it can do:** run scripts, use WebGL, gamepads (`allow="gamepad"`), full screen and pointer lock, and fetch its own files. A static plugin's files carry `Access-Control-Allow-Origin: *` because ES modules and `fetch()` from an opaque origin are CORS requests. A **server** plugin's files do not (4.37.0): they run inside Elaia's own page and need no CORS. Who is asking rides on the network path, not on a cookie, so any web site open in the owner's browser can make it send a GET that carries his identity; what stops that site from *reading* the answer is the browser's same-origin rule, and a wildcard header would give that away.
- **Who may open it:** a static plugin is the owner's only (docs/people.md).
- **What it can't do:**
  - **Use Argus's powers.** POSTs from it send `Origin: null` and are refused, so a plugin can't freeze, thaw or run your tasks.
  - **Read `api/state` or task logs.** Those send no CORS header.
  - **Touch Argus's cookies or storage, or navigate the Argus page.**
- **Storage:** the sandbox has none: `localStorage` throws on its opaque origin. Keep state in the URL, or give the plugin its own address (below), where storage works and lasts.

## Its own address (4.42.0)
A static plugin can run in a tab of its own instead, at **its own address**: the host name Elaia is opened at, on another HTTPS port. A different port is a different origin, so the browser keeps the plugin out of Elaia's answers and its POSTs fail Elaia's checks (*Why Elaia stays shut*, below). It is not the whole wall the sandbox gives: cookies belong to the host name, not the port, so those it shares with Elaia (see there what keeps Elaia safe anyway). In return the plugin has a real origin of its own: storage that lasts, normal downloads, its own frames, and a cache that a long-running game can rely on. Its section in Elaia becomes a large **Open <name>** button (a new tab) and up to four links to its other pages; there is no frame.

**The host file**, `~/.config/argus-ui/own-origin.json` (or `$ARGUS_OWN_ORIGIN`). It lives on the host only and never goes in git; without it nothing changes and every static plugin keeps the sandboxed frame.
```
{
  "spartamelee": {
    "port":   <local port>,
    "public": <HTTPS port that tailscale serve publishes>,
    "links":  [{"name": "Frame data", "path": "frames/"}]
  }
}
```
- `port`: the plugin's own listener, on `127.0.0.1` only, inside Elaia's process. 1024 to 65535, not Elaia's own port and not another plugin's.
- `public`: the HTTPS port `tailscale serve` publishes it on. Never 443 (Elaia's address) or 80, never another plugin's.
- `links` (optional): each a `name` (1 to 40 characters) and a `path` inside the plugin's folder, like `frames/` (no `..`, no leading `/`, no scheme). The first 4 good ones are kept. A link whose page is not there, or leads out of the folder, is not shown.
- An entry with a bad id, `port` or `public` is skipped with a line in the log (`own-origin.json: skipped …`). A bad link is dropped on its own (`<id>: skipped a link …`) and the entry stays. A file that cannot be read as JSON (also one nested too deep) or is not a JSON object is ignored with one line, and Elaia starts as if there were none.
- **A port that is taken at start**: that plugin keeps its frame, the log says so, and Argus glares with an alert (`argus-own-origin`, docs/alerts.md; the theme needs an agent `argus`, as both shipped themes have). Meanwhile `tailscale serve` still forwards the plugin's public port to whatever holds the local one, so turn that off first (`sudo tailscale serve --https=<public> off`), free the port, restart Elaia, and publish it again (below). The alert goes away at the next start where every own listener starts.
- Elaia reads the file at start: a change needs a restart (a deploy restarts it). Only static plugins are served there; a server plugin's id gets nothing.
- The browser keeps a site's storage per origin, so changing `public` starts the plugin with empty storage.

**Publishing it** (once, on the host; Serve keeps it across restarts): `sudo tailscale serve --bg --https=<public> http://127.0.0.1:<port>`. Serve passes on the Tailscale login the same way it does for Elaia, so people and roles work unchanged. To stop publishing it: `sudo tailscale serve --https=<public> off`.

**What the page shows.** Elaia offers the own address only where the browser can reach it. Opened through `tailscale serve`, the Open button and the links point at `https://<the host name this page was opened at>:<public>/`. Opened on the host itself over plain http at a loopback name (`127.0.0.1`, `localhost`), they point at `http://127.0.0.1:<port>/`. Opened any other way, such as from another device over plain http with `ARGUS_BIND=0.0.0.0`, there is no own address (the local port answers on `127.0.0.1` only) and the section keeps the sandboxed frame. The button and links open a new tab with `rel="noopener"`.

**The plugin's listener:**
- Answers **GET and HEAD only**. Any other method is `405` with `Allow: GET, HEAD`, before anything else is looked at.
- Serves **only that plugin's files, at the root** of its address: `/` is its `entry` page, `/frames/` its `frames/index.html`, a folder without its slash is redirected to it. No API, no `static/`, no other plugin, no `plugin.json`. `..` (plain or percent-encoded), backslashes, `NUL`, a drive name and symbolic links that point out of the folder (at any step, a folder's `index.html` included) are all `404`.
- Applies **the same host check** (`421` for an unknown host) and **the same people and roles** as opening `plugins/<id>/` inside Elaia: the Tailscale login counts only when the connection comes from Serve and not from the server itself (docs/people.md); a learner gets `403`; someone not on the list, or no login, gets the private page; a broken people file closes it like Elaia.
- Sends **the same caching headers**: `ETag`, `Last-Modified`, `304`, a year for content-hashed names, `no-cache` for pages and scripts (see *Caching* above).
- Sends **no sandbox**, and this policy for a game on its own origin (inline scripts and styles for import maps, WebAssembly, `data:` and `blob:` URLs for loaded models and exports):
  `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' data: blob:; worker-src 'self' blob:; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'`.
  Plus `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Resource-Policy: same-origin`. No `Access-Control-Allow-Origin`, and no `Set-Cookie`.

**Why Elaia stays shut.** The plugin's origin is the same *site* as Elaia (same host name) but not the same *origin* (another port), and Elaia's walls are written for origins:
- **Its POSTs are refused.** A JSON POST from another origin makes the browser ask first (`OPTIONS`), and Elaia answers no such question (`501`), so the POST is never sent. A form or text POST, which goes out without asking, is refused as not JSON (`415`). Behind those, Elaia checks the two headers a browser adds, each when it is there: `Sec-Fetch-Site` must be `same-origin` or `none` (typed or bookmarked; the plugin's pages send `same-site`), and `Origin` must equal Elaia's `Host` (`403` either way). A request with neither header is not from a browser page; it passes this step and meets the role check (docs/people.md).
- **It cannot read Elaia.** No API answer of Elaia carries `Access-Control-Allow-Origin`, so the browser hands the plugin nothing; its own `connect-src 'self'` stops it asking in the first place.
- **Cookies are shared, and Elaia reads none.** Cookies belong to a host name, not a port, so the plugin's pages *can* set cookies that the browser then sends to Elaia and to every other service on that host name, and can read the ones those services set there without `HttpOnly`. Elaia sets none and reads none: who is asking comes only from Serve's login header on Serve's own connection (docs/people.md), so no cookie makes anyone the owner. Both of Elaia's listeners skip every `Cookie` line while reading a request, whatever its size (up to 4 MB, more than a browser sends; the standard library alone answers `431` past 64 KB), so a page that piles up cookies cannot shut Elaia either. Another service on the same host name that does use cookies gets the plugin's too: give an own address only to plugins you trust that far.
- **No frames, no opener.** Neither page can frame the other (`frame-ancestors 'self'` both ways); the new tab has no handle on Elaia's.
- The sandboxed copy at `plugins/<id>/` stays as it was, and plugin frames still never get `allow-same-origin`.

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
- `ctx.jobs(prefix='')` (4.30.0): the tasks the Watch page shows whose unit name starts with `prefix`, as a list of dicts: `job` (the unit), `state` (`ok`, `running`, `failed`, `frozen`, `never`), `last` and `next` (as the cards word them: "Sun 4:00 AM", "paused by Medusa", "manual"), `notes` and the rest of a card's fields. It runs `systemctl` the way Elaia's own refresh does, so a plugin reads its agent's timers without a subprocess of its own (Memory reads `mnemosyne-*`). Check it exists (`getattr(ctx, 'jobs', None)`) if your plugin must run on an older Elaia.
- `GET api/<id>/<path>` calls `get(path, query, ctx)`; `POST api/<id>/<path>` calls `post(path, body, ctx)`. Both return `(status, obj)`: an HTTP status and anything `json.dumps` takes. `query` is `parse_qs` output (`{'q': ['hi']}`); `body` is the JSON object. A function that takes a fourth parameter also gets `who` (see *Roles and who*).
- Each call gets its own `ctx` with `ctx.headers`: `Tailscale-User-Login`, `Tailscale-User-Name` and `X-Forwarded-For` when the request has them **and came through `tailscale serve` from another device** (4.37.0: the server checks that the connection belongs to the Serve user, and that Serve's `X-Forwarded-For` is not the server itself; docs/people.md). From anywhere else, a program on the server included, all three are dropped, so a plugin is never handed a faked or borrowed name. **A plugin never decides on them itself**: it passes them to the agent's CLI, and Janus checks them (`janus verify-approval`).
- POSTs pass Elaia's checks before `post()` is called: host allowlist, JSON only, same-origin `Origin`/`Sec-Fetch-Site`, the role, 4 KB at most. They run one at a time per plugin. GETs run side by side and **must not change anything** (a GET has no cross-site check).
- An exception, or an answer that isn't `(status, obj)`, is a `500 {"ok": false, "msg": "plugin error"}` and a traceback in the journal.
- **`GET api/<id>/status` is reserved** for Elaia's Home page: answer `200, {"line": "1 deploy waiting · argus-ui 4.9.1 live", "needs": true, "action": "Approve argus-ui 4.9.2"}`. `needs: true` puts the plugin in Home's **Needs you** list with `action` as the button (verb-first, 32 characters at most; default "Open <name>"). Elaia passes on only `line` (160 characters at most), `needs` and `action`, or `{"line": null, "needs": false}` when the plugin has none or fails; it never errors (docs/home.md).
- **Reads are file reads; writes call the agent's CLI; the plugin itself never decides.** A plugin reads the agent's status files directly (no subprocess on a GET). A POST runs the agent's own command (`zeus approve …`, `hermes message …`) with fixed arguments, never a shell, and returns what the agent said. Decisions (who may approve, what is allowed through) stay in the agent and Janus.

**Roles and who** (4.37.0, docs/people.md). Elaia knows who is asking (owner, learner, or nobody it knows) and checks the role **before** it calls a plugin. Every `api/<id>/<path>` is the owner's unless `plugin.json` opens it to learners, path by path, exactly as `<path>` is written after `api/<id>/` (no query, no wildcards):
```json
"roles": {"get":  {"today": "learner", "next": "learner", "status": "learner"},
          "post": {"answer": "learner", "rate": "learner"}}
```
- Only the value `"learner"` opens a path; anything else (missing, `"owner"`, a typo) leaves it to the owner. A refused call answers `403 {"error": "<sentence>"}` without calling the plugin.
- Open `status` too if Home's line should show for a learner.
- The plugin's files (`plugins/<id>/...`, its page script and style) are open to a learner only if it opens at least one path; its section and pill only show for her then.
- A `get` or `post` that takes a fourth parameter, `get(path, query, ctx, who=None)` (or a keyword-only `who`: `get(path, query, ctx, *, who=None)`), gets `who = {"person": "<id>", "name": "<name>", "role": "owner" | "learner"}` on **every** call, never `None` (without a people file: `{"person": "owner", "name": "You", "role": "owner"}`). A parameter named `who` is passed by name; otherwise a fourth positional parameter gets it. Old three-parameter plugins are called as before. A plugin that keeps data per person (Mentor) uses `who["person"]` to keep each person's apart and still checks `who` itself for what a role may see.

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

**Controllers** is a small bundled plugin that is not an agent (`plugins/controllers/`, docs/controllers.md): its own section and a Home place, read-only, with a Python test that runs without a browser (`tests/controllers_test.py`). It was called Pads until 4.33.0; a section that changes its id keeps its old address for one release through `MOVED` in `server/argus_ui.py` (a redirect, and an answer on the old `api/<id>/...` that tells a page left open to reload; both off when a plugin of yours has the old id).

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
- its own address (4.42.0; also `bash tests/run.sh own-origin`): `tests/own_origin_test.py` runs without a browser and checks the host file (bad entries and links left out, a busy port skipped), the listener (root serving, caching, `HEAD`, the host check, every method but GET and HEAD refused, no API), paths that try to leave the folder (dots plain and encoded, backslashes, `NUL`, symbolic links), each role answering as it does inside Elaia, and Elaia refusing every POST from the plugin's origin with no API answer it could read. `tests/own-origin.test.js` starts a second Elaia with a host file on free ports and checks the Open button (new tab, 44 px, reached with <kbd>Tab</kbd>), the links, no frame, the game's storage, its tries at Elaia from its own tab, and 375 px
