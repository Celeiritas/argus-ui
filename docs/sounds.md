# Adding sounds

Argus ships with **no sound files**. The page plays a sound only if the file exists. Otherwise it stays quiet, and a few Olympus items fall back to simple tones made in the browser. **Mute sounds** at the top right turns everything off.

## 1. Get the files

Use sounds you have the right to use. Good free sources:

| Source | License | Notes |
|---|---|---|
| [Kenney](https://kenney.nl/assets?q=audio) | CC0 (no credit needed) | Game sound packs: impacts, UI, RPG |
| [Freesound](https://freesound.org) | Varies: filter by **Creative Commons 0** | Huge library; free account to download |
| [Pixabay sound effects](https://pixabay.com/sound-effects/) | Pixabay license (free, no credit needed) | Easy search |
| Record or make your own | Yours | Phone recorder, [jsfxr](https://sfxr.me) for retro blips |

Avoid sites where clips are uploaded by anyone with no license (meme soundboards). They're fine for your own server, but don't commit or share them.

## 2. Name them

| File | Plays when |
|---|---|
| `freeze.mp3` | Medusa turns a task, tree or skeleton to stone |
| `thaw.mp3` | the stone crumbles back to life |
| `bolt.mp3` | Zeus's lightning strike |
| `burn.mp3` | a skeleton burns |
| `hammer.mp3` | Hephaestus' hammer hits the ground |
| `dirt.mp3` | digging; a skeleton climbing out of the ground |
| `rattle.mp3` | a skeleton's bones rattle as it rises |
| `bonedeath.mp3` | a skeleton crumbles |
| `seed.mp3` | a flower sprouts |
| `bow.mp3` | Apollo's bow lets an arrow go |
| `arrowhit.mp3` | the arrow sticks |

Keep each one short (under about 3 seconds) and small (under 200 KB). The alarm chime for failed tasks is made in the browser and needs no file.

**Converting or trimming** (needs [ffmpeg](https://ffmpeg.org)): this keeps the first 2 seconds, fades out the end and saves a small mp3:

```bash
ffmpeg -i input.wav -t 2 -af "afade=t=out:st=1.6:d=0.4" -ac 1 -b:a 96k bolt.mp3
```

## 3. Put them on the machine that runs Argus

```bash
mkdir -p ~/.config/argus-ui/sfx && cp *.mp3 ~/.config/argus-ui/sfx/
bash ~/src/argus-ui/scripts/deploy.sh     # or re-run install.sh from a package
```

Every install copies the files from `~/.config/argus-ui/sfx/` into the page, so updates built from git keep your sounds. To copy files from another computer, use `scp *.mp3 <user>@<host>:.config/argus-ui/sfx/`.

**Other ways:**
- **Bake them into a package:** put the files in `themes/<theme>/sfx/` before `scripts/build.sh`. Git ignores mp3 files there, so they never get committed by accident.
- **Swap one sound quickly:** replace the file in `~/.local/share/argus-ui/static/sfx/` and reload the page. The next install restores whatever is in `~/.config/argus-ui/sfx/`.

## Checking

Open the page, unmute and use the power. If you hear nothing:
- Check that the browser tab isn't muted.
- Check that the file name matches the table exactly (lowercase, `.mp3`).
- Check `ls ~/.local/share/argus-ui/static/sfx/`.
