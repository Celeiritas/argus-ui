# Leafy Pads

The **Pads** section (`<base>/pads`) answers one question: *which game pads does the server see right now, and will they work?* One row per pad, always in the same order of facts:

| Fact | What it says | Where it comes from |
|---|---|---|
| Slot | `P1`, `P2`, `P3`, `Retro` … or *No slot* | your slot map, `~/.config/argus-ui/pads.json` (below) |
| Name | the slot map's `label`, else the name the kernel gives the pad; the kernel name, USB ids and nodes (`js0`, `event20`) under it | `/proc/bus/input/devices` |
| Mode | for the OpenPuck, from its USB ids: `28de:1304` **Steam**, `045e:028e` **Xbox 360**, `2e8a:10c6` **SInput**, `0f0d:0092` **Switch**; any other pad shows **Unknown (vid:pid)** (dashed) unless your map names it | the `I:` line's Vendor and Product |
| Real or virtual | **Real** (on a cable or dongle), **Steam virtual** (Steam Input's copy: named `Microsoft X-Box 360 pad N` and living under `/sys/devices/virtual/`), or **Virtual** (another program's) | the `S: Sysfs=` path |
| Rumble | **Rumble works** when the pad has an event node and its `capabilities/ff` is not zero, else **No rumble** | `/sys/<sysfs path>/capabilities/ff` (falls back to `/proc`'s `B: FF=` line) |

Every state is an icon and a word, never colour alone. Home gets a **Pads** place with the line *3 connected · 1 Steam virtual* (*No pads connected* when there are none); Pads never asks for you in *Needs you*.

When no pad is there the section says **No pads connected** and how to wake one (the `wake_hint`). On a machine without `/proc/bus/input/devices` (not Linux) it says it can't read pads there.

## Read-only, on every request
The plugin (`plugins/pads/`, a bundled server plugin: docs/leafy-plugin.md) only reads two kernel views, on every `GET api/pads/list` and `api/pads/status`: no shell, no subprocess, no writes, no timer, no job. The page re-reads every 15 seconds and on **Check again**. It is a port of the owner's read-only shell check of the pads (the "Pads the system sees" part: name, real or virtual, rumble).

What counts as a pad: a device with a joystick node (`jsN`), or one with a pad-like name (Steam, Xbox, Puck, SInput, 8BitDo …) that has analog axes. The Steam Controller's keyboard and mouse parts, touchpads and motion sensors are left out.

## The slot map: `~/.config/argus-ui/pads.json`
Optional (`ARGUS_PADS` points elsewhere). Without it every pad shows *No slot*; a broken file is named on the page and the pads still show. Example (also in `docs/pads.example.json`):
```json
{
  "slots": [
    {"slot": "P1", "label": "{{PAD_1}}", "match": ["28de:1304", "045e:028e", "2e8a:10c6", "0f0d:0092"]},
    {"slot": "P2", "label": "{{PAD_2}}", "match": ["phys:-1.2/"]},
    {"slot": "Retro", "label": "{{PAD_4}}", "match": ["<part of the pad's name>"]}
  ],
  "modes": {"1234:abcd": "<what this pad's ids mean>"},
  "wake_hint": "Press a pad's Home or Steam button to wake it."
}
```
- `slots` in the order the page lists them. The first entry with a matching `match` wins. A match is `vvvv:pppp` (USB ids, exact), `phys:<text>` (part of the pad's USB port path, the `P: Phys=` line: use it when the hub port is the player slot and two adapters share ids), or anything else (part of the name). Case is ignored. One string instead of a list (`"match": "puck"`) is one match.
- **Virtual pads never take a slot**, even when their ids match: they are copies of a real pad, which has it.
- `modes` names ids the built-in list doesn't know (a GameCube adapter, say). `wake_hint` replaces the default empty-state hint.
- The real map lives only on the server; the repo has placeholders only.

## Tests
- `python3 tests/pads_test.py -v` (no browser, any OS; `tests/run.sh` runs it as "pads model"): the probe over `tests/fixtures/pads-sysfs/four` (OpenPuck SInput, a puck in Steam mode with its keyboard and mouse parts, a Steam-virtual Xbox pad, a GameCube adapter without rumble) and `.../none` (a keyboard), the slot map, a broken map, the `B: FF=` fallback, a sysfs path that tries to leave the root. The fixtures' sysfs paths use dashes where real ones have colons, so a Windows checkout can hold them.
- `bash tests/run.sh pads` (browser): four rows with the right words and icons, the summary, **Check again** by keyboard, the empty state with the hint, Home's place, 375 px with no sideways scroll. `run.sh` points the server at the fixtures with `ARGUS_PADS_SYSROOT` and `ARGUS_PADS`.

## Later
When Daedalus (the planned hardware agent) has a `daedalus status --json`, the plugin should prefer its answer and fall back to reading sysfs itself. A real check after a deploy: the section's rows should match the owner's shell check on the server.
