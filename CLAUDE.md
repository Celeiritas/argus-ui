# Argus UI – notes for Claude Code

A small, dependency-free web page that watches `systemd --user` services ("tasks") grouped by Greek-god "agents", with powers (Medusa freeze/thaw, Zeus run), Mentor's Learn page (lessons: teach first, then spaced practice) and the Olympus playground. Python stdlib server + one static page. MIT code; the Leafy Realm theme's art is all rights reserved (`themes/leafy-realm/ASSETS.md`).

## Map
- `server/argus_ui.py` – HTTP server (routing under `/` or `/argus/`, host allowlist, JSON-only POSTs, powers via `systemctl --user`). `server/mentor.py` – lessons (Learn cards derived or authored), grading, the hint ladder, stuck detection, spaced repetition (SQLite, FSRS-4.5). `server/sky.py` – weather from Open-Meteo, fetched server-side and cached.
- `web/index.html` – markup only. `web/css/argus.css` (core), `scene.css`, `olympus.css`. `web/js/` loads in this order and shares one global scope: `core` (helpers, routing, render, Argus's eyes) → `scene` (sky, Olympus, trees, weather) → `powers` (Watch-page tools and strikes) → `olympus` (playground items) → `mentor` → `plugins` (LeafyPlugin sections) → `main`.
- `themes/<name>/` – `theme.json` (agents, title, `coming_soon`), `icons/*.png`, `gods/*.svg` (sources), `decks/*.json`. Sounds are never in git (see `themes/leafy-realm/sfx/README.md`).
- `scripts/build.sh [theme]` → `dist/argus-ui-<VERSION>-<theme>.tar.gz` (inlines Medusa's SVG, versions script/style URLs). `scripts/install.sh` installs it on the host. `scripts/deploy.sh` = `git pull` + build + install, run on the host. `scripts/new-theme.py <name>` makes a theme with placeholder art (`themes/starter` was made with it).
- LeafyPlugins – `docs/leafy-plugin.md` is the contract: folders in `~/.config/argus-ui/plugins/<id>/` (manifest `plugin.json`), served sandboxed at `<base>/plugins/<id>/` and shown as the section `<base>/<id>` (server `plugins()` / `plugin_file()`, client `web/js/plugins.js`). Never give plugin frames `allow-same-origin`. Test fixture: `tests/plugin-fixtures/`.
- `docs/` – `scene.md` (weather sources, items, **layer order**), `mentor.md`, `leafy-plugin.md`, `themes.md`, `sounds.md`, `ux-audit-4.1.md`, `screenshots/`.

## Test before you say it works
`bash tests/run.sh` (or `bash tests/run.sh olympus`) builds the package, runs it in a temp HOME against fake systemd units (`tests/fixtures/`), and drives Chromium with Playwright: Watch powers and alarm, Mentor rating flow, every Olympus item, ultrawide and 375px phone. Needs python3, node, `npm install` and `npx playwright install chromium` (Linux; on Windows use a cloud session or the host). Add a check to the matching `tests/*.test.js` when you add a feature.

## Rules
- Bump `VERSION` and add a `CHANGELOG.md` entry for every change that ships. Small commits, clear messages.
- Never commit sound files, credentials, tailnet names, home paths or anything personal. Personal setup goes in `CLAUDE.local.md` (gitignored) or `~/.claude/CLAUDE.md`.
- Never redraw the theme's existing icons; new art is drawn to match and approved by the owner first. SVG sources go in `themes/*/gods/`.
- UI rules (see `docs/ux-audit-4.1.md`): type 16/14/12px, weights 400/600; 44px hit areas; verb-first button labels; visible focus; keyboard path for every pointer action where it makes sense; honour `prefers-reduced-motion`; no horizontal scroll at 375px.
- Scene/effects: keep the layer order in `docs/scene.md`. Don't reuse `.stone` (frozen-card overlay) for scene states; trees use `.struck` / `.statue`.
- Security: POST stays JSON-only with Origin/Sec-Fetch-Site checks; escape anything put into HTML (`esc()`); the server binds to 127.0.0.1 by default and is published with `tailscale serve`.
- Classic scripts share globals: declare state that an earlier file reads every frame (e.g. `drag`, `gaze`) in `core.js`.
