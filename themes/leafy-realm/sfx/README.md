# Sounds (not included)
The page plays these if they exist and stays silent if they don't (a few Olympus sounds fall back to simple tones made in the browser):

| File | When |
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

Two ways to add them:
- **On the machine that runs Argus:** put the files in `~/.config/argus-ui/sfx/`. Every install copies them in, so packages built from git keep your sounds.
- **In a package you build:** put them in this folder before `scripts/build.sh`. This folder's mp3 files are ignored by git.

Use sounds you have the right to use. Keep each to a few seconds.
