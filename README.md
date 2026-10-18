# Argus UI

A small, self-hosted web page that watches the background jobs on a Linux machine (systemd `--user` services and timers) and lets you act on them, from any device on your Tailscale network.

Jobs are shown as **tasks**, grouped under **agents** (personas you define). Each task card shows whether it is OK, running, failed or frozen, when it last ran and runs next, its memory use and its latest log.

**Powers** you can throw at a task card:
- **Medusa's gaze**: drag Medusa onto a task to *freeze* it (stop it and pause its timer; the card turns to stone). Drag her onto a stone card to *thaw* it, which restores exactly what was enabled or running. Nothing is ever deleted.
- **Zeus's bolt**: hurl it at a task to *run* it now, or *restart* it if it's an always-on service.

The watchman, Argus, sits at the top: his eyes follow your pointer and glare at anything that has failed.

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
Open `http://<host>:8095`. To also publish it on your tailnet at `https://<host>.<tailnet>.ts.net/argus`:
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
- The page has no login. Serve it only on your own network or tailnet (`tailscale serve`, not `funnel`).
- Freeze only stops and disables; thaw re-enables. The UI cannot delete units or files. `argus-ui` itself can't be frozen.

## License
Code: MIT (see LICENSE). The Leafy Realm theme's artwork is **not** covered by the MIT license. See `themes/leafy-realm/ASSETS.md`.
