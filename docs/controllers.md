# Leafy Controllers

The **Controllers** section (`<base>/controllers`) answers one question: *which game controllers does the server see right now, and will they work?* One row per controller, always in the same order of facts:

| Fact | What it says | Where it comes from |
|---|---|---|
| Slot | `P1`, `P2`, `P3`, `Retro` … or *No slot* | your slot map, `~/.config/argus-ui/controllers.json` (below) |
| Name | the slot map's `label`, else the name the kernel gives the controller; the kernel name, USB ids and nodes (`js0`, `event20`) under it | `/proc/bus/input/devices` |
| Mode | for the OpenPuck, from its USB ids: `28de:1304` **Steam**, `045e:028e` **Xbox 360**, `2e8a:10c6` **SInput**, `0f0d:0092` **Switch**; any other controller shows **Unknown (vid:pid)** (dashed) unless your map names it | the `I:` line's Vendor and Product |
| Real or virtual | **Real** (on a cable or dongle), **Steam virtual** (Steam Input's copy: the kernel names it `Microsoft X-Box 360 pad N` and it lives under `/sys/devices/virtual/`), or **Virtual** (another program's) | the `S: Sysfs=` path |
| Rumble | **Rumble works** when the controller has an event node and its `capabilities/ff` is not zero, else **No rumble** | `/sys/<sysfs path>/capabilities/ff` (falls back to `/proc`'s `B: FF=` line) |

Every state is an icon and a word, never colour alone. Home gets a **Controllers** place with the line *3 connected · 1 Steam virtual* (*No controllers connected* when there are none); Controllers never asks for you in *Needs you*.

When no controller is there the section says **No controllers connected** and how to wake one (the `wake_hint`). On a machine without `/proc/bus/input/devices` (not Linux) it says it can't read controllers there.

**One word.** Here a *controller* is always a game controller. The word *pad* is left only inside names the kernel gives (`Microsoft X-Box 360 pad 0`), which are shown as they are.

## Read-only, on every request
The plugin (`plugins/controllers/`, a bundled server plugin: docs/leafy-plugin.md) only reads two kernel views, on every `GET api/controllers/list` and `api/controllers/status`: no shell, no subprocess, no writes, no timer, no job. The page re-reads every 15 seconds and on **Check again**. It is a port of the owner's read-only shell check of the controllers (the "controllers the system sees" part: name, real or virtual, rumble).

What counts as a controller: a device with a joystick node (`jsN`), or one with a controller-like name (Steam, Xbox, Puck, SInput, 8BitDo …) that has analog axes. The Steam Controller's keyboard and mouse parts, touchpads and motion sensors are left out.

## The slot map: `~/.config/argus-ui/controllers.json`
Optional (`ARGUS_CONTROLLERS` points elsewhere). Without it every controller shows *No slot*; a broken file is named on the page and the controllers still show. The file is looked for on every request, so a new or changed map counts at once, without a restart. Example (also in `docs/controllers.example.json`):
```json
{
  "slots": [
    {"slot": "P1", "label": "{{CONTROLLER_1}}", "match": ["28de:1304", "045e:028e", "2e8a:10c6", "0f0d:0092"]},
    {"slot": "P2", "label": "{{CONTROLLER_2}}", "match": ["phys:-1.2/"]},
    {"slot": "Retro", "label": "{{CONTROLLER_4}}", "match": ["<part of the controller's name>"]}
  ],
  "modes": {"1234:abcd": "<what this controller's ids mean>"},
  "wake_hint": "Press a controller's Home or Steam button to wake it."
}
```
- `slots` in the order the page lists them. The first entry with a matching `match` wins. A match is `vvvv:pppp` (USB ids, exact), `phys:<text>` (part of the controller's USB port path, the `P: Phys=` line: use it when the hub port is the player slot and two adapters share ids), or anything else (part of the name). Case is ignored. One string instead of a list (`"match": "puck"`) is one match.
- **Virtual controllers never take a slot**, even when their ids match: they are copies of a real controller, which has it.
- `modes` names ids the built-in list doesn't know (a GameCube adapter, say). `wake_hint` replaces the default empty-state hint.
- The real map lives only on the server; the repo has placeholders only.

## Renamed from Pads in 4.33.0
Until 4.33.0 this section was called **Pads**. Words and ids changed together:

| Was | Now |
|---|---|
| the section `<base>/pads`, called Pads | `<base>/controllers`, called Controllers |
| plugin id `pads` (`plugins/pads/`, `api/pads/...`) | `controllers` (`plugins/controllers/`, `api/controllers/...`) |
| the key `pads` in the answer of `api/.../list` | `controllers` |
| slot map `~/.config/argus-ui/pads.json` | `~/.config/argus-ui/controllers.json` |
| `ARGUS_PADS` | `ARGUS_CONTROLLERS` |
| `ARGUS_PADS_SYSROOT` | `ARGUS_CONTROLLERS_SYSROOT` |
| `docs/pads.md`, `docs/pads.example.json` | `docs/controllers.md`, `docs/controllers.example.json` |

**4.33 still reads the old names, and it is the last release that does**, so an install keeps working across the update:
- `pads.json` is read while there is no `controllers.json` in the same folder. Once `controllers.json` exists it wins and `pads.json` is ignored.
- `ARGUS_PADS` and `ARGUS_PADS_SYSROOT` are read while `ARGUS_CONTROLLERS` and `ARGUS_CONTROLLERS_SYSROOT` are unset or empty.
- An old bookmark to `<base>/pads` is answered with a redirect to `<base>/controllers` (a 302, which says "for now", sent with `Cache-Control: no-store` so no browser remembers it). The redirect is off when you have installed a plugin of your own with the id `pads`.
- While an old name is in use, a notice above the list (an icon, a rule on its left, the thing to do in bold) says for each one what to do and what happens otherwise: *Copy pads.json to controllers.json in ~/.config/argus-ui/ on the server. The next release ignores pads.json, so every controller would show No slot.* For a setting: *Rename the setting ARGUS_PADS to ARGUS_CONTROLLERS where the service is set up. The next release ignores ARGUS_PADS, so every controller would show No slot.* Home's line stays as it is.
- `api/pads/...` has no data any more. A page that was left open across the update still asks it and cannot know about the move, so for this release the answer is one that page can show: `{"ok": false, "moved": "controllers", "problem": ..., "line": ...}`. The open section then says *This section is now called Controllers. Reload this page to open it.* under its *Can't read pads here*, and its Home place says *Now called Controllers: reload this page*. One reload lands on `<base>/controllers`. Off, like the redirect, when a plugin of your own has the id `pads`.

To switch, copy the map to its new name on the server (the old file stays where it is; nothing needs a restart):
```
test -e ~/.config/argus-ui/controllers.json || cp ~/.config/argus-ui/pads.json ~/.config/argus-ui/controllers.json
```
The notice on the page goes away with the next look. The release after 4.33 reads only the new names: `pads.json`, `ARGUS_PADS`, `ARGUS_PADS_SYSROOT` and `<base>/pads` stop working then.

## Tests
- `python3 tests/controllers_test.py -v` (no browser, any OS; `tests/run.sh` runs it as "controllers model"): the probe over `tests/fixtures/controllers-sysfs/four` (OpenPuck SInput, a puck in Steam mode with its keyboard and mouse parts, a Steam-virtual Xbox controller, a GameCube adapter without rumble) and `.../none` (a keyboard), the slot map, a broken map, the `B: FF=` fallback, a sysfs path that tries to leave the root. The fixtures' sysfs paths use dashes where real ones have colons, so a Windows checkout can hold them.
- The old names, in the same file: which name wins (`OldNames`), and a real server in its own process, started with only `pads.json` and `ARGUS_PADS_SYSROOT` (`OldNamesOnTheServer`): the slots still show, the notice says what to do about both, copying the file to `controllers.json` counts without a restart, `<base>/pads` redirects (also under `/argus/`, with a trailing path, with a query), a plugin of your own with the id `pads` keeps its address (the redirect comes back when it is gone), `api/pads/...` tells a page left open to reload.
- `bash tests/run.sh controllers` (browser): four rows with the right words and icons, the summary, **Check again** by keyboard, the empty state with the hint, the word *pad* nowhere but in the kernel's name, the old address landing on the section, the old-name notice (its words per name, shown as text, its own look, desktop and 375 px), the full stop in the line for a map that cannot be read, Home's place, 375 px with no sideways scroll. `run.sh` points the server at the fixtures with `ARGUS_CONTROLLERS_SYSROOT` and `ARGUS_CONTROLLERS`.

## Later
When Daedalus (the planned hardware agent) has a `daedalus status --json`, the plugin should prefer its answer and fall back to reading sysfs itself. A real check after a deploy: the section's rows should match the owner's shell check on the server.
