# LeafyPlugins

A LeafyPlugin adds a section to Argus without changing Argus's code: drop a folder in, and it gets a pill in the section bar and its own page at `<base>/<id>`. Spartamelee (a browser game) is the first. Mentor will become one later.

## The folder
```
~/.config/argus-ui/plugins/<id>/        (or $ARGUS_PLUGINS/<id>/)
  plugin.json                           the manifest (never served)
  index.html                            the plugin's page (or whatever "entry" says)
  ...                                   anything it loads, by relative URL
```
Plugins live outside the install, so upgrading Argus keeps them (like the sounds). Argus reads the folder on every request: a deploy shows up on the next page load, no restart needed.

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
| `id` | yes | Must equal the folder name: `a-z`, digits, `-`, starts with a letter, up to 32 characters. Not an agent key, `olympus`, `api`, `static`, `plugins`, `all`, `argus` or `play`. |
| `name` | yes | Shown on the pill and as the page title (40 characters max). |
| `subtitle` | no | The pill's small line, e.g. "Play" (40 max). |
| `kind` | no | `static` (the default; the only kind so far). See *Module plugins* below. |
| `entry` | no | The page to show, relative to the folder. Default `index.html`. |
| `icon` | no | A square PNG in the folder for the pill and the page header. Without one, the pill shows a plain laurel-and-blades mark. Icons follow the theme's art rules: drawn to match, approved by the owner. |
| `version` | no | Shown under the frame. |
| `order` | no | Pills sort by `order` (default 100), then name. |

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

## Module plugins (planned, for Mentor)
Mentor needs a server side: a SQLite database and `/api/mentor/*`. The planned `"kind": "module"` adds:
- `"server": "plugin.py"`, a Python module loaded at startup. It exposes `get(path, query)` and `post(path, body)` and gets its own data folder, `~/.local/share/argus-ui/plugins/<id>/`.
- Routes under `api/<id>/...`, passed through Argus's existing checks (host allowlist; JSON-only POST with same-origin `Origin`/`Sec-Fetch-Site`; a 4 KB body cap).
- A page that runs **inside** Argus's page, not in a frame, because it is trusted code installed by the owner. That page script shows the section the way `practice.show()` does today.

Until that exists, Mentor stays built in: `server/mentor.py`, `web/js/mentor.js`, `/api/mentor/*`. Work on Mentor's internals doesn't need to wait for module plugins. Moving it over is a separate change that adds the module loader, then moves Mentor's files.

## Checking a plugin
`bash tests/run.sh plugins` installs the demo plugin from `tests/plugin-fixtures/demo/` into a throwaway HOME and checks the whole flow:
- the pill appears and replaces a matching "coming later" pill
- the section shows the frame, and the frame loads its module script and JSON
- the 15-second refresh keeps the frame
- the sandbox blocks a POST to `api/freeze`
- `..` and `plugin.json` aren't served
- no sideways scrolling at 375 px
