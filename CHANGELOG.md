# Changelog

## 4.19.0 – 2026-10-23
- **Fix:** on wide screens Home and server-plugin pages (the Throne) were squeezed into a column a word or two wide. They added the page margin a second time inside a page that already had it; at 3440 px that was about 1840 px of margin. They now use the full content width (16:9 too, where they had been pushed 160 px right)
- **Ultrawide** (2:1 or wider, 1800 px and up): the sections bar becomes a rail down the left edge, with the weather and Mute at its foot, so the short screen gets its top band back; content may run to 2400 px, so Watch fits 8–9 task cards in a row
- **Argus is sized by height as well as width:** at most about a fifth of the screen's height, so Watch's header takes a quarter of an ultrawide instead of a third
- **Home on wide screens** (1200 px and up): Needs you beside Places
- **Phones:** Argus is smaller (128 px), so the first task shows sooner; the sections bar scrolls to show the section you are on; a phone on its side shrinks Argus to 96 px so a task shows on the first screen
- Tests: `tests/layout.test.js` (3440×1440, 2560×1080, 1920×1080, 375×760, 844×390); docs/ui-plan.md §14

## 4.18.0 – 2026-10-23
- **Shared effects** (`web/js/fx.js`, docs/fx.md): `fx.burst`, `fx.motes` (a ribbon of glowing motes, after SoulSeed's heal swirl), `fx.glint`, `fx.pieces` and `fx.bolt`, plus the helpers Watch and Olympus already used (`particle`, `ROCK`, `boltFx`, moved out of `powers.js` unchanged). Each one handles reduced motion itself and cleans up after itself
- **Hold to confirm** (`web/js/hold.js`): hold a button 3 s (pointer, or Space/Enter) and a ring fills while the label counts down; letting go early sends nothing and says so. A click that can't be held (a screen reader's or a switch's) arms the button and a second click within 5 s confirms. Reduced motion: no ring, the countdown words only. For Throne, Delivery and Memory next
- Server plugins get both as `api.fx` and `api.holdConfirm` (docs/leafy-plugin.md)
- **Mentor:** each key idea you got pops a few olive leaves from its tick (the tick alone with reduced motion)
- **Fix:** Home's greeting now shows the weather. It used to read it once, before the weather had arrived
- Tests: `tests/fx.test.js` (each effect plays and cleans up, the old helpers still answer, hold by pointer, sliding off, keyboard, a screen reader's two clicks, reduced motion), through a hold button in `tests/plugin-fixtures/demo-server`; `tests/mentor.test.js` checks the leaves, `tests/home.test.js` the weather in the greeting

## 4.17.0 – 2026-10-23
- **Groundwork for a local AI in Mentor** (docs/mentor-ai.md). Off until `~/.config/argus-ui/mentor-ai.json` turns it on. With a model server on this machine (Ollama, or any OpenAI-compatible server such as llama.cpp's `llama-server`), a written answer also gets a **meaning match** (embeddings, cosine) and, optionally, two or three sentences of **feedback** from a small chat model. The rubric answers at once as always; Athena's owl brings the AI's part a moment later, labelled "Local AI · <model> · not used for the rating". Shadow mode: it is stored with the attempt (`attempts.ai`) but the rubric still suggests the rating
- Answers stay home: a model server on another machine is refused unless `"allow_remote": true`. A broken config, a slow or stopped server: the AI's part is skipped, one log line, the Lessons view says why
- `python plugins/mentor/mentor.py export [mentor.db]` writes every rated attempt as one JSON line, the training data for a grader that learns from you (stage Bv2)
- Tests: `tests/mentor-ai.test.js` against `tests/fixtures/fake_model.py` (a stand-in server for both APIs, started by `tests/run.sh` on `MODEL_PORT`): off by default, remote URL refused, status, pending then done, both APIs, a server that doesn't answer, the owl on the page, the Lessons line

## 4.16.0 – 2026-10-23
- **Home is about you now, and looks it** (docs/home.md, docs/ui-plan.md §3). The header greets you by the time of day with the date and weather; then **Needs you**, one list, most urgent first, each row with a verb-first button that goes there (an alert → "Open Throne", failed tasks → "Look at 1 failed task", Mentor → "Study 5 due cards"); then **Places**, a row of medallions with each section's one line. No more grid of tiles: Watch keeps the cards, so the two pages no longer look alike. "Nothing needs you. The realm is quiet." when it's all done
- **Status v2** for server plugins: `api/<id>/status` may add `needs` and `action` (32 characters, verb-first); old `{line}` answers keep working and never enter the list. Mentor says it needs you when cards are due
- Tests: `tests/home.test.js` rewritten for the new Home (greeting, the list and its order, buttons and their targets, places in the section bar's order, focus across redraws, phone); `tests/bundled.test.js` checks status v2 and a needs row from a plugin

## 4.15.0 – 2026-10-23
- **Three new powers on Olympus**, filling three empty seats on the Ω (new art drawn for them, with the owner's go-ahead):
  - **Hermes' winged sandal**: skims along the ground the way you throw it, its wings beating; the wind carries debris, spilled wine and arrows in the ground off the screen, bends the flowers, rocks the trees and makes skeletons stagger. It says how many pieces it carried away
  - **Athena's owl**: glides to the nearest free tree (or a skeleton's skull, or the ground) and perches; her eyes follow your pointer and she blinks. Click or tap her for a hoot and a Delphic maxim ("Know thyself."). She flies off when her tree is struck or her skeleton crumbles, and turns to stone with a stone perch. Four at most
  - **Dionysus' cup**: drips wine in flight; a skeleton it splashes dances for eight seconds to a little tune with music notes; a tree grows a grapevine with grapes for the season; the ground gets a puddle of wine that the sandal or the trident cleans up
- Poseidon's tsunami also washes away owls and vines. Reduced motion: no flapping, no dancing, no particles; every effect still happens
- docs/scene.md: the three items, the layer order and class names
- Tests: `tests/olympus.test.js` checks the sandal clears the mess and the arrow but leaves flowers and trees, the owl perches, speaks, follows the pointer and flees a struck tree, and the cup's dance, vine and puddle
## 4.14.0 – 2026-10-23
- **Mentor is now a bundled server plugin** (`plugins/mentor/`, `"agent": true`), the first real one: `mentor.py` (unchanged), `plugin.py` (`api/mentor/...`), `page.js` and `page.css` (were `web/js/mentor.js` and `web/css/mentor.css`). Same section (`<base>/mentor`), same pill in the same place, same API, same keyboard paths. Elaia's own server no longer imports Mentor
- **Nothing of yours moved**: the database stays `~/.local/share/argus-ui/mentor.db` (or `ARGUS_MENTOR_DB`), the inbox and your decks stay in `~/.local/share/argus-ui/`. An install sets the old built-in `mentor.py` aside with the previous version
- Home's Mentor tile now reads `api/mentor/status`, like every server plugin, instead of computing its line in the page
- Fix: Mentor handles one request at a time on its single SQLite connection. The page asks for decks and stats at once, and two requests could read each other's rows (seen as a `tuple index out of range` on `next`)
- Tests: `tests/bundled.test.js` checks Mentor loads as a bundled plugin, keeps its pill right after Argus, never serves its Python files and answers `status`; `tests/mentor.test.js` runs unchanged

## 4.13.0 – 2026-10-22
- **Bundled plugins**: plugins that ship with Elaia live in the repo's `plugins/<id>/`; the package carries them and every install puts them in `~/.local/share/argus-ui/bundled/` (the old copy is set aside with the previous version). Your own plugin with the same id wins and the bundled one is never imported. The log marks bundled ones
- **A server plugin can take over an agent's section** with `"agent": true` and the agent's key as its id: `<base>/<key>` and `api/<key>/...` are the plugin's (ahead of the built-in Mentor routes), with the agent's name, subtitle and icon unless the plugin has its own. Its pill keeps the agent's place, and Home shows its status line. A folder named after an agent without `"agent": true` is skipped. This is the groundwork for moving Mentor into a bundled plugin
- `ctx.theme_dir`: a server plugin can read the installed theme (`theme.json`, `decks/`)
- No `hide()` hook: leaving a section loads a new page, so a plugin's timers end with it (`docs/leafy-plugin.md`)
- Tests: `tests/bundled.test.js` with `tests/bundled-fixtures/` (`heracles`, a bundled `demo-server`), and the `chronos` fixture

## 4.12.0 – 2026-10-22
- **Home** (`<base>/home`, `docs/home.md`): one tile per section, each with the line that says whether it needs you, and every `alert`-level alert above the tiles with its link. The tiles: Watch ("1 task failed · 1 alert", or "All 6 tasks well", with a red edge while something is wrong), Mentor ("3 cards due · 2 to learn"), Olympus, each server plugin's `api/<id>/status` line, and each static plugin's version. The whole tile is the link (at least 44 px); a redraw keeps keyboard focus; one column on a phone
- The Home pill comes first in the section bar. **Watch stays the default page** until the name test; making Home the default is a later change. The pill's four-square mark is a placeholder until the owner approves art
- Tests: `tests/home.test.js`

## 4.11.0 – 2026-10-22
- **Alert files** (#8, `docs/alerts.md`): any agent can make Argus glare without a failed unit by writing `~/.local/state/argus-ui/alerts/<agent>.json` (`{"job", "level": "alert"|"warn", "message", "since", "link"}`; the folder can be changed with `ARGUS_ALERTS` or the theme's `alerts`). The folder is read on every refresh, with no new process. The task's card shows the message with "Open <section>". An alert for a job with no card (Zeus's `zeus-approve`) gets a card of its own in its agent's section. `alert` makes Argus glare, counts in his badge and the section's counts, and is read out in his label; `warn` shows on the card only. Removing the file calms him. Malformed files are ignored with one log line each, and a link to a section that isn't installed is dropped
- **Registry fallback** (#11): a task with no registry file of its own uses the longest prefix before a `-` that has one, stopping above the god's prefix (`zeus-deploy-<id>` → `zeus-deploy.json`). An entry with `"transient": true` makes per-run units one card, showing the latest run (a running one first) with "latest of N runs". That card has no Run or Freeze, and the bolt skips it. Exact-name lookups are unchanged
- Fix: the alarm badge stayed visible when nothing had failed (`display:flex` overrode `hidden`). The Watch test now checks that it goes away
- Tests: `tests/alerts.test.js` (alert → glare and badge, warn → card only, file removed → calm, a lone alert card, malformed files ignored with one log line, phone width; the deploy runs collapsing into one card that takes the latest run's state, the prefix fallback, exact lookups)

## 4.10.0 – 2026-10-22
- **Server plugins** (`"kind": "server"`): trusted plugins with a Python side and a page inside Elaia, for the agents' pages (Hermes · Delivery, Janus · Map, Zeus · Throne) and, later, Mentor. At startup Elaia imports each one's `plugin.py` by path and calls `init(ctx)` with its own data folder (`~/.local/share/argus-ui/plugins/<id>/`); `GET`/`POST api/<id>/<path>` go to its `get(path, query, ctx)` / `post(path, body, ctx)`, which answer `(status, obj)`. POSTs pass Elaia's usual checks first (host, JSON only, same-origin, 4 KB) and run one at a time per plugin; `ctx.headers` carries `Tailscale-User-Login`, `Tailscale-User-Name` and `X-Forwarded-For` for the agent's CLI to check with Janus. `GET api/<id>/status` is reserved for the Home page's one line. A plugin that fails to load is logged and skipped, and Elaia starts anyway; an exception in a request is a 500, not a crash
- The page script runs in Elaia's page (no frame) and calls `leafy.register(id, {show, refresh})`; it gets `api.get` / `api.post` for its own API, `esc`, `toast` and `url`. Its section is a side page like Mentor's, and the 15-second refresh calls `refresh()` instead of rebuilding it. Script and style URLs carry their file time, so a changed page is fetched fresh. `plugin.py` is never served
- Plugin ids can no longer be the names of built-in API routes (`state`, `sky`, `health`, `log`, `freeze`, `thaw`, `bolt`, `run`)
- `docs/leafy-plugin.md`: the *Server plugins* section with a minimal example, replacing the planned "module" kind. Test fixtures `demo-server` and `demo-broken`; `tests/run.sh plugins` checks the server kind end to end, and that a sandboxed static plugin can't read a server plugin's API

## 4.9.1 – 2026-10-21
- **`GET api/health`**: `{ "ok": true, "version": "4.9.1", "uptime_s": 120 }`, for a deploy tool to confirm the new version came up and for a door probe to see the page is alive. Nothing personal in it
- **`scripts/deploy.sh --no-pull`** builds and installs the commit that is checked out without touching git, and prints `ZEUS_STAGE=install` before the install starts, so a deploy tool (Zeus) knows whether a failure changed anything. Without the flag it pulls `main` as before
- Test: `api/health` is checked on the Watch run

## 4.9.0 – 2026-10-20
- **Placeholders in lessons.** A lesson says `{{SERVER}}`, `{{PC}}`, `{{PHONE}}`, `{{SSH}}`, `{{HOME_PC}}`, `{{HOME_SERVER}}` or `{{REPO_URL}}`, and Mentor fills them in from `~/.config/leafy/realm.json` in every field it shows (prompts, answers, hints, snippets, the Lessons view), falling back to public defaults (`homeserver`, `desktop` …). Grading compares against the filled-in text. The database keeps the placeholders, so lessons move between people unchanged and an edit to `realm.json` shows on the next card. `docs/realm.example.json`; docs/mentor.md explains the file
- **`scripts/check-private.sh`** stops personal data reaching the public repo: home paths, `*.ts.net` names, IPv4/IPv6 addresses, emails, and every line of your own `~/.config/leafy/denylist.txt` (never committed). It checks the staged changes, a commit range (`main..HEAD`, messages included), the whole tree (`--tree`) or history (`--history`), and prints file:line. `scripts/install-hooks.sh` runs it before every push; a GitHub Actions job runs the generic checks on every pull request
- The Leafy Realm theme's subtitle is now "Leafy Realm agents" (it named a device), with a new Watch screenshot; the service worker's comment no longer names a device. CLAUDE.md: the placeholder rule, the check before every push, personal lessons never in `themes/`
- Tests: a lesson with `{{SERVER}}` shows the public default without `realm.json` and the `realm.json` value with it, and is graded against it

## 4.8.0 – 2026-10-20
- **Mentor teaches before it tests.** A new lesson opens with an **orientation** screen (what the code does, the terms coming, why this lesson; you type one line before the cards). Each term gets a **teach card** (what it does, where it is in your code, its look-alike, what an expert looks for) that ends in *spot it*: pick the line of a snippet that uses it. Each drill gets a **worked example** (level 0): the full code, annotated line by line; you say why a line is there before the note appears, then explain the whole snippet, graded by its rubric. Each explain card gets a **pre-read**: the ideas it rests on and a near example to answer before the reveal. Learn cards are read once and never scheduled; *I know this, test me* skips one (it comes back if the practice card then goes wrong)
- **Hint ladder** on every practice card: a nudge, the expert's first move, a near example, the answer. Each rung needs a three-word reflection, caps the rating Mentor suggests (rung 3 also stops a drill moving up), and the answer counts as a blank. A blank *Show answer* offers a hint first; the Hint button pulses after 30–90 s without typing. <kbd>Alt</kbd>+<kbd>H</kbd> opens the next rung
- **Stuck detection** sends the lesson's card back before the next try: wrong twice in a row, a skipped Learn card whose practice card fails, the answer shown twice, or *Needs work* twice in a week (the last two also hold the card for a day). The stats line counts cards sent back today and cards still to learn
- **Coach line rewritten**: at most two sentences, the expert's first move and one place to look; a slip (right before, wrong now) is named as one; never about the person
- **"Code modules" are now lessons** (the old word clashed with Python modules, which Mentor teaches): *Lessons* view, *Study this lesson*, *Add a lesson*; the Study picker shows learning progress. Each lesson lists its Learn cards to read again. The section is **Mentor · Learn**
- **Lesson format**: optional `orientation`, `expert_move`, `spot_it`, `teach_order`, `level_0_worked`, `look_at`, `preread`, `hints` and `metadata.lint` (`docs/mentor-command.md`, with authoring limits). Older files get derived Learn cards from what they already have. The shipped lesson has the authored fields for its first term, drill and explain card
- API: `answer` with `hint: k` returns one rung; the final answer carries `hints` and `reflections`; `rate` with `rating: 0` marks a Learn card read; `next?card=<id>` returns a Learn card to read again. Database: `cards.learn_of`, `sched.refresh`, `attempts.hints/reflections/stuck/skipped` (older databases gain them on start)
- Lessons need no drills: a lesson with only terms and explain cards imports and runs (spot-it snippets can be terminal transcripts, not just code). Your own lessons go in the inbox or `~/.local/share/argus-ui/decks/`, never in the theme, if they mention your machines or paths
- Tests: the Learn flow end to end, the hint ladder, stuck detection, read-again, an old-shape lesson, the worked example on a phone

## 4.7.0 – 2026-10-20
- **Mentor teaches the code you build.** Code modules made by the `/mentor` command in Claude Code (a Cognitive Task Analysis of real code, saved as JSON) give three tiers of cards: **code drills** with blanks typed straight into the snippet, faded over three levels (endings → logic → whole body); **explain cards** (find the bug, why this design, human factors link); and **term cards** (fill in the term, then see what it does, where it is in your code and its look-alike)
- New modules unlock terms → drills → explain cards (pre-training); drills move up a level when you're right and fast, or right twice in a row, and down on "Needs work"; reviews interleave across modules and decks
- Whole bodies are checked with Python's parser (never run): same structure as the model, how alike they are, or Python's syntax error with its line
- **Inbox**: copy a module into `~/.local/share/argus-ui/inbox/` and it appears without a restart; broken files are listed with the reason. A **Code modules** view shows each module's breakdown and progress, and a **Study** picker replaces the deck buttons
- Ships one module made from Argus's own `sky.py` and `mentor.py`; `docs/mentor-command.md` is the `/mentor` command (adds a project name, accepted wordings for each rubric idea, and the one-line reply); `docs/mentor.md` rewritten
- Older Mentor databases gain the new columns on start; every attempt now also records the card kind, drill level and code-grading features for the learning grader

## 4.6.0 – 2026-10-20
- **LeafyPlugins:** drop a folder with a `plugin.json` into `~/.config/argus-ui/plugins/<id>/` and Argus shows a new section at `<base>/<id>` with its own pill, no code change or restart. Static plugins (games, tools) run in a sandboxed frame with an opaque origin, so they can't use the powers or read your tasks, even when a plugin page is opened in its own tab. A plugin replaces a theme's "coming later" pill of the same name. The contract is in `docs/leafy-plugin.md`, including the planned `module` kind for moving Mentor over
- **Spartamelee · Play** is the first plugin: its `scripts/deploy.sh` installs to `plugins/spartamelee/`
- The 15-second refresh never reloads a plugin's frame, so a game keeps running; "Show full screen" for plugins; the frame fits the window and a 375px phone
- Tests: `tests/plugins.test.js` with a demo plugin in `tests/plugin-fixtures/` (pill, side page, its module script and JSON load, a blocked POST to `api/freeze`, blocked `api/state`, refresh keeps the frame, no `..` or `plugin.json`, headers, redirect, phone)

## 4.5.3 – 2026-10-19
- README opens with a short preview GIF of Watch and the Olympus playground. `bash tests/run.sh demo` records it again from the fake tasks (needs ffmpeg)

## 4.5.2 – 2026-10-19
- **`scripts/new-theme.py`** makes a theme in one step: theme.json, a lettered medallion per agent, a plain Argus, a snowflake freeze medallion, app icons and a sample practice deck (needs Pillow)
- **`themes/starter`**, a free (MIT) placeholder theme made with it, so the project can be tried without the Leafy Realm art
- **docs/sounds.md**: file names, free sound sources, trimming with ffmpeg and where to put the files; docs/themes.md rewritten
- README install steps no longer scroll sideways; `THEME=<name> bash tests/run.sh` builds another theme for the tests

## 4.5.1 – 2026-10-19
- README rewritten for visitors: screenshots of Watch, Olympus and Mentor (taken by the test run with fake tasks), what each section does, and how Argus runs (a systemd user service, no containers)
- The weather example uses a sample location instead of a real one; comments no longer name the author's machine

## 4.5.0 – 2026-10-18
- **Olympus playground rebuilt around items**: the twelve Olympians on an Ω with Zeus at the top; Hades in a **Chthonic** spot and Medusa **Beyond Olympus**. Seats show each god's item; gods without a power yet are dashed placeholders
- Drag and fling any item (a still release drops it): Zeus's bolt, Medusa's snake (stone and back), Poseidon's trident (an opaque tsunami resets the playground), Hades' bident (skeletons rise from the ground and rattle; it crumbles them too), Demeter's seeds (seasonal flowers), Apollo's bow (arrows that stick), Hephaestus' hammer (digs ever-deeper holes, smashes skeletons). Click-then-place for keyboard and touch
- Zeus's bolt burns skeletons black until they crumble; the hammer smashes stone skeletons
- Scene controls collapse into a "Weather, season, time" bar, so the field stays reachable on phones; the section bar stays one row on phones
- Mount Olympus keeps its summit on wide and ultrawide screens; the storm flash covers the whole sky instead of being clipped
- Taller ground with turf, soil, clay and bedrock
- Sounds for the hammer, burning, digging, rattling and crumbling bones, sprouting seeds, the bow and arrow hits (supplied by the owner; not in the repository). Install copies your sounds from `~/.config/argus-ui/sfx/`, so packages built from git keep them
- **The page is split into files**: `web/css/` and `web/js/` (core, scene, powers, olympus, mentor, main), loaded with `?v=<version>` so browsers never mix old and new files
- **Tests in the repository**: `bash tests/run.sh` with fake systemd units and Playwright checks for Watch, Mentor and Olympus. `scripts/deploy.sh` (git pull + build + install on the host). `CLAUDE.md` for Claude Code sessions
- A pause before letting go now counts as a drop on the Watch page too

## 4.4.0 – 2026-10-18
- **Scene** behind every page: sky, Mount Olympus with a glowing temple, grass and trees. Trees follow the season: green summer, red/orange/yellow fall with falling leaves, bare and snow-covered winter, blossoming spring
- **Live weather** from Open-Meteo (no key; fetched only by the server, every 20 minutes, cached): rain, snow, fog, cloud, storms with lightning over the summit; night sky with stars; the current conditions appear beside Mute sounds. Location via `WEATHER=<lat>,<lon> ./install.sh`
- **Olympus · Playground** section: controls for weather, season and time of day (the address keeps the choice), and all three powers on the scene
- Zeus's medallion now hands you a bolt instead of flying itself: drop it on a task or tree, or fling it at the trees (it arcs and strikes a tree or the ground). Flung bolts never run tasks
- Struck trees burn, smoke and stand charred with debris; **Poseidon** (new tool on Olympus) washes debris, scorch marks and rubble away so trees grow back. Elsewhere, struck trees clean up after 30 s
- Medusa can turn a tree to stone and back
- Medusa's sleeping Zs sit outside her rim with a dark outline, so the pale rim no longer hides them
- docs/scene.md: weather sources compared, privacy, and the layer order for art and effects

## 4.3.1 – 2026-10-18
- **HTTPS only by default**: the installer makes Argus listen on 127.0.0.1, so other devices reach it through `tailscale serve` over HTTPS and the plain-http port is closed to the network. The setting lives in `~/.config/systemd/user/argus-ui.service.d/bind.conf` and is kept across upgrades; `BIND=0.0.0.0 ./install.sh` opts back into LAN http
- Installer checks and prints the Tailscale HTTPS address
- Mentor medallion: the staff is one piece with his hand gripping it; icon rendered at 512 px so he stays sharp in the centre of his page

## 4.3.0 – 2026-10-18
- **Section bar**: Argus · Watch (default), Mentor · Practice, and themed "coming later" sections (Spartamelee · Play in the Leafy Realm theme)
- Mentor gets his own page: his medallion takes the centre, and Argus keeps watch from the corner (select him to go back to watching)
- **Alerts**: when a task fails, all of Argus's eyes turn red and glow, a red aura pulses, an alarm badge counts the failures (also on the Argus section button), and a short chime plays when something newly fails (muted with Mute sounds)
- Eyes redrawn to match the medallion's almond eyes and cover them, so a blink no longer shows a second eye behind; blinks close to a lid line; the top grey eye has a pupil

## 4.2.2 – 2026-10-18
- Practice ratings in plain words: Very well (quick, easy recall), Well enough (took moderate thought), Not well (hard to remember or explain), Needs work (run this card again soon)
- Each choice shows when the card will come back; Mentor's suggestion is preselected
- Rating is now pick-then-confirm: a verb button follows your choice ("Run again in 10 min" or "Save and next card"); keys 1–4 choose in on-screen order, Enter confirms

## 4.2.1 – 2026-10-18
- Mentor medallion: hooded dark grey robe, broad-shouldered torso, scraggly beard, Athena's owl with wing lines, a tan scroll rolled top and bottom

## 4.2.0 – 2026-10-18
- **Mentor / Practice tab**: typed-answer flashcards with key-idea (rubric) grading, model answers, coaching notes, confidence and calibration tracking, FSRS-4.5 spaced repetition, keys 1–4 to rate, "Practice ahead" when caught up
- Every attempt is saved with grading features and your final rating, as training data for a future learning grader (docs/mentor.md)
- Decks: UX & HCI terms (25), Psych behind design (8), AI-assisted coding habits (9); add your own in `~/.local/share/argus-ui/decks/`
- Ultrawide: Argus scales with the window (up to 360px), content column widens to 1600px, header aligns with it
- Mentor agent in the Leafy Realm theme (icon draft)

## 4.1.0 – 2026-10-18
UX audit (VectorLab UX skills) and security review.
- **Type:** 16/14/12px scale (no text under 12px), task details at 14px, weights 400/600 only, body line-height 1.5
- **Targets:** every control has a 44px hit area; nav links and the log toggle are 44px tall
- **Keyboard:** Medusa and Zeus's bolt are real buttons. Press one, then Enter on a task (Esc cancels). Tooltips show on hover *and* focus. Argus's eyes follow keyboard focus too.
- **Confirm before interrupting:** freezing or restarting a task that is running right now asks first (named task, Cancel focused, Esc cancels). Freezing anything else offers **Undo**.
- **Copy:** verb-first buttons ("Show log", "Mute sounds"), plain-language results, errors say what happened and what to do next
- **Motion:** UI transitions use 150/200/300ms tokens and only transform/opacity; tools fly with transforms; reduced-motion skips particles and strikes (fade only); Argus stops wandering/blinking under reduced motion
- **Layout:** header is full width (only main content is capped); counts are plain text, not pills; sound toggle moved into the nav
- **Security:** CSRF and DNS-rebinding protection, `ARGUS_BIND`, `ARGUS_ALLOWED_HOSTS`, safe static paths, body size cap, `</script>` escaping, a lock around freeze/thaw, atomic frozen-list writes, and systemctl failures are reported instead of ignored

## 4.0.0 – 2026-10-18
First version in this repository. Same features as the author's "v4" home install, generalized:
- Agent list, titles and registry folder come from the theme (`theme.json`) instead of being hard-coded
- Build script (`scripts/build.sh <theme>`) and generic installer (`scripts/install.sh`, keeps the previous version)
- Large centered Argus with pointer-tracking, blinking, glaring eyes
- Compact task cards, persona pages at `<base>/<agent>`
- Medusa freeze/thaw with green stone effects (sounds optional, bring your own); Zeus's bolt run/restart with lightning effect and sound
- Works directly on a port or behind `tailscale serve --set-path /argus`; installable as a phone app

## Earlier (before this repo)
- v3 – persona groups with medallion icons, moving eyes, Medusa freeze/thaw (frost/fire), Tailscale path
- v2 – first web page (status cards, Run now)
