# Argus UI

A small, self-hosted web page that watches the background jobs on a Linux machine (systemd `--user` services and timers) and lets you act on them, from any device on your Tailscale network.

Jobs are shown as **tasks**, grouped under **agents** (personas you define). Each task card shows whether it is OK, running, failed or frozen, when it last ran and runs next, its memory use and its latest log.

**Powers** you can throw at a task card:
- **Medusa's gaze**: drag Medusa onto a task to *freeze* it (stop it and pause its timer; the card turns to stone). Drag her onto a stone card to *thaw* it, which restores exactly what was enabled or running. Nothing is ever deleted.
- **Zeus's bolt**: hurl it at a task to *run* it now, or *restart* it if it's an always-on service.

**Sections:** a bar across the top switches between **Argus · Watch** (the default) and other sections such as **Mentor · Practice**, a spaced-repetition coach with typed answers, key-idea grading and confidence calibration ([docs/mentor.md](docs/mentor.md)). A theme can list sections that are still coming (`coming_soon` in `theme.json`).

**Scene:** every page sits on Mount Olympus with grass and trees that follow the season and the live weather (rain, snow, fog, storms), fetched by the server from Open-Meteo with no API key. The **Olympus · Playground** section lets you try the powers on the scene: strike or fling bolts at trees, turn them to stone with Medusa, wash the debris away with Poseidon. See [docs/scene.md](docs/scene.md). To show live weather, install with `WEATHER=<lat>,<lon>`.

**Develop and test:** `bash tests/run.sh` runs the package against fake systemd units and checks every page in a real browser (needs Playwright; see `CLAUDE.md`). On the machine that runs Argus, `bash scripts/deploy.sh` pulls the latest code from git, builds it and installs it, keeping your sounds (`~/.config/argus-ui/sfx/`), weather location and settings.

The watchman, Argus, sits at the top: his eyes follow your pointer and glare at anything that has failed. When a task fails, all his eyes turn red and glow, a red aura pulses, an alarm badge counts the failures and a short chime plays (unless muted). On other sections he keeps watch from the corner; select him to go back.

> Status: early and personal. It runs the author's home server and is being generalized. Expect changes.

## What you need
- Linux with systemd and Python 3 (no extra packages).
- Optional: [Tailscale](https://tailscale.com) to reach the page from your other devices over HTTPS.

## Install
```bash
bash scripts/build.sh leafy-realm            # -> dist/argus-ui-<version>-leafy-realm.tar.gz
# copy the package to the machine to watch, then on that machine:
mkdir -p ~/argus-ui && tar -xzf argus-ui-*.tar.gz -C ~/argus-ui && bash ~/argus-ui/install.sh
```
Argus listens on this machine only (`127.0.0.1:8095`) by default. Publish it to your devices over HTTPS on your tailnet at `https://<host>.<tailnet>.ts.net/argus` (Tailscale provides the certificate):
```bash
sudo tailscale serve --bg --set-path /argus http://127.0.0.1:8095
```
On a phone, open that address and use **Add to Home screen** to install it as an app.

## Which jobs show up
Any `systemd --user` service whose name starts with an agent key from the theme, followed by a dash. With the Leafy Realm theme, `hermes-sort` appears under Hermes and `mnemosyne-backup` under Mnemosyne. A JSON file per task in the registry folder (`~/.config/argus-ui/agents/<task>.json`, or the theme's `registry`) can add `notes` shown on the card.

## Themes
A theme is a folder in `themes/` with `theme.json` (title, subtitle, agents, which tasks may never be frozen), an icon per agent and the Medusa SVG. Sound effects are optional and not included: drop your own `freeze.mp3`, `thaw.mp3` and `bolt.mp3` into the theme's `sfx/` folder. See [docs/themes.md](docs/themes.md).

## Repository layout
```
server/argus_ui.py      the whole server (Python standard library only)
web/                    the page (index.html), app manifest, service worker
themes/leafy-realm/     the author's theme: agents, icons, Medusa, sounds, source artwork
scripts/build.sh        builds an installable package for a theme
scripts/install.sh      installs/updates on the target machine (keeps the old version)
```

## Safety
There is no login, so the server protects itself in other ways:
- **Your network only.** Serve it on your LAN or tailnet (`tailscale serve`, never `funnel`). By default it accepts only this machine, so other devices reach it through `tailscale serve` over HTTPS. To use plain http on a LAN instead, install with `BIND=0.0.0.0`.
- **No cross-site actions.** Actions must be JSON from the page itself (checked with `Sec-Fetch-Site` / `Origin`), so another website you visit can't freeze or run your tasks.
- **No DNS rebinding.** It only answers to this machine's hostname, IP addresses, `*.ts.net` and `*.local` names, plus any in `ARGUS_ALLOWED_HOSTS` (comma separated).
- **Can't delete anything.** Freeze only stops and disables; thaw re-enables exactly what was on. `argus-ui` itself can't be frozen. A task that's running asks for confirmation before it's interrupted.
- Static files can't escape the `static/` folder, request bodies are capped, and text from unit descriptions can't break out of the page's script.

## License
Code: MIT (see LICENSE). The Leafy Realm theme's artwork is **not** covered by the MIT license. See `themes/leafy-realm/ASSETS.md`.
