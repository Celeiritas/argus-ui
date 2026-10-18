# Making a theme
Copy `themes/leafy-realm` to `themes/<your-theme>` and edit:

- `theme.json`
  - `title`, `subtitle`: shown at the top of the page
  - `agents`: list of `{key, name, domain}`, in page order. A task belongs to the agent whose `key` it starts with (`key-…`).
  - `never_freeze`: task names Medusa may not freeze (keep `argus-ui`)
  - `registry` (optional): folder of per-task JSON notes and the frozen list
- `icons/<key>.png`: one round icon per agent (128×128 works well), plus `argus.png` for the header (the page draws Argus's moving eyes over it; eye positions are in `web/index.html`)
- `gods/medusa.svg`: the draggable Medusa (classes `awake`, `freezing`, `thawing` switch her states)
- `sfx/freeze.mp3`, `sfx/thaw.mp3`, `sfx/bolt.mp3`
- `argus-192.png`, `argus-512.png`: app icons

Then `bash scripts/build.sh <your-theme>`.
