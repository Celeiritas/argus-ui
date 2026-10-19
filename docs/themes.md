# Themes

A theme is a folder in `themes/` that holds the agents, their art and the practice decks. The code is the same for every theme.

| Theme | Art | License |
|---|---|---|
| `leafy-realm` | The author's hand-drawn Greek gods | All rights reserved (see its `ASSETS.md`); look, but don't reuse |
| `starter` | Plain lettered medallions, made by `scripts/new-theme.py` | MIT, free to use and change |

## Make your own in one step

```bash
python3 scripts/new-theme.py mytheme --subtitle "Home server" \
  --agent "backup:Backup:Copies · snapshots" \
  --agent "media:Media:Library · streaming" \
  --agent "sync:Sync:Files between devices"
bash scripts/build.sh mytheme      # -> dist/argus-ui-<version>-mytheme.tar.gz
```

This needs Pillow (`pip install pillow`). Each `--agent` is `key:Name:What it does`. Tasks show up under an agent when their systemd unit is named `<key>-…` (for example `backup-nightly.service`). Argus and Mentor are added for you. The script makes:

| File | What it is | Replace with |
|---|---|---|
| `theme.json` | Title, subtitle, agents in page order, `never_freeze` (tasks the freeze tool may not touch; keep `argus-ui`), optional `registry` (folder of per-task notes) and `coming_soon` (sections shown as "coming later") | Edit by hand |
| `icons/<key>.png` | One round medallion per agent, plus `mentor.png` and `olympus.png` for the section bar | Any square PNG, 256×256, transparent corners |
| `icons/argus.png` | The header figure. The page draws Argus's moving eyes on top at fixed spots (a 234×234 grid, eyes around x 104–141, y 45–90; see `web/index.html`), so keep a face there | 234×234 PNG |
| `gods/medusa.svg` | The freeze/thaw medallion. The page adds the classes `awake`, `freezing` and `thawing` while it's in use, so the SVG can change colour | SVG with `viewBox="0 0 234 234"` and `class="medusa"` on the root |
| `argus-192.png`, `argus-512.png` | App icons for **Add to Home screen** | Same sizes |
| `decks/*.json` | Mentor practice decks (a sample is included) | See [mentor.md](mentor.md) |

Zeus's bolt medallion, the scene, Mount Olympus and the Olympus playground items are drawn by the page itself and are the same in every theme.

## Sounds

Sounds aren't part of a theme. See [sounds.md](sounds.md).

## Tips
- Try a theme without touching your real install: `THEME=mytheme bash tests/run.sh` runs it against fake tasks. The Watch checks expect the Leafy Realm agents, so some of them fail on other themes; the screenshots still show your art.
- Keep art you can't share out of git. Put a note in the theme's `ASSETS.md` saying what's covered by which license.
