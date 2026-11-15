# Desktop / Game mode

A server that is also a games console has two faces: a desktop and a game session on the TV. The mode pill at the top of every section shows which one `{{SERVER}}` is in and switches it to the other with one press and hold. It shows only for the owner, and only when the host has a `modes.json`.

## The file
`~/.config/argus-ui/modes.json` on the host (or the path in `ARGUS_MODES`). It names the host's own units, so it lives on the host and never in git.
```json
{"modes": [
  {"id": "desktop", "label": "Desktop", "active_unit": "<desktop-shell-unit>", "switch_unit": "<switch-to-desktop-unit>"},
  {"id": "game",    "label": "Game",    "active_unit": "<game-session-unit>",  "switch_unit": "<switch-to-game-unit>"}
]}
```
| Field | Meaning |
|---|---|
| `modes` | Exactly two, in the order the pill shows them (left, then right). |
| `id` | `a-z`, `0-9` and `-`, starting with a letter, at most 16 characters. The two ids differ. `desktop` and `game` get their own colours (below); with one other id, it gets the colour left over; with two others, the first is green and the second purple. |
| `label` | The words on the pill, 1 to 16 characters. |
| `active_unit` | A `systemctl --user` unit that runs (active) while the host is in this mode, and only then. |
| `switch_unit` | The `systemctl --user` unit that switches the host **into** this mode. |

Unit names may leave out `.service`; Argus adds it. Only `.service` units can be used, a template must name one instance (`<name>@<instance>`), a name may not start with `-`, and the four names must all differ.

- **No file**: the feature is off. No pill, `api/state` has no `modes`, and `POST api/mode` answers 404.
- **A bad file** (not JSON, the wrong number of modes, a bad id, label or unit name, larger than 64 KB): off too, and the server log (`journalctl --user -u argus-ui`) gets one line saying what is wrong, once each time the file changes, never on every refresh. Argus keeps running.
- The file is read again when it changes (its modification time or size), so an edit needs no restart.

## The switch units
Each `switch_unit` is a oneshot that does the whole switch (ends one session, starts the other) and then **ends**. Do not give it `RemainAfterExit=yes`: while a switch unit is `activating` or `active` the pill says *Switching to …* and offers nothing to press, so a switch unit that stays active keeps the pill switching for good.

**The host rule.** Argus only ever starts a switch unit, with `systemctl --user start --no-block <switch_unit>`, and never starts, stops or restarts a session unit (an `active_unit`) itself. Starting a game session from a script while the desktop runs makes a hidden second session: a black screen until a reboot. Write the care into the switch units; the pill only pulls their trigger.

## What the pill shows
- **The mode the server is in** is filled with its colour and read out as "Desktop (current)". **The other mode** is a button: press and hold it for 3 seconds (`holdConfirm`), or hold Space or Enter on it, and the server starts that mode's switch unit. The toast says *Switching to Game mode. The TV goes dark for a few seconds.*
- **Switching**: both halves are off, and a note beside the pill says *Switching to Game…* with a small dot that pulses (it stays still with reduced motion). The page asks the server every 2 seconds until it is in the new mode, for 2 minutes at most; after that the note says *Still switching: check the TV*.
- **Mode unknown**: when both `active_unit`s run, or neither does, or `systemctl` does not answer, the pill says *Mode unknown* in muted words, with nothing to press.
- **A refusal or a failure**: the toast says what the server said, and Argus winces.
- The wrapper is a group named "*<server name>* mode" (from `SERVER` in `~/.config/leafy/realm.json`, else "The server"). Each half is at least 44 px; long labels wrap inside their half; nothing scrolls sideways at 375 px.

## The server
`server/modes.py` (stdlib, like `quiet.py`).
- **`api/state`** for the owner carries, when the file sets the feature up:
  `"modes": {"current": "desktop" | "game" | "unknown", "switching": "<id>" | null, "modes": [{"id", "label"}], "name": "<server name>"}`.
  Ids and labels only: the unit names never leave the server. A learner's state never has `modes`.
- **One `systemctl` call** reads all four units: `systemctl --user show A B C D -p Id -p ActiveState`, with the server's usual 20 s timeout. The answer is kept about 2 seconds, however many pages ask, and a switch clears it. It never holds the lock the powers use.
- `switching` is set while a switch unit is `activating` or `active`, or for up to 120 s after a switch this server started, until the target mode is current (that note is cleared then).
- **`POST api/mode`** with `{"to": "<id>"}`: the owner's only (a learner gets 403), after the usual JSON, Origin and Sec-Fetch-Site checks. It answers JSON `{"ok", "msg"}`:

| Case | Code | `ok` | `msg` |
|---|---|---|---|
| No file, or a bad one | 404 | false | Desktop / Game mode is not set up on this server. |
| An id that is not in the file | 400 | false | There is no mode with that name. Reload the page. |
| A switch is under way | 409 | false | *<name>* is already switching to *<label>* mode. |
| The mode can't be told | 409 | false | Can't tell which mode *<name>* is in right now. Try again in a minute. |
| Already in that mode | 200 | true | Already in *<label>* mode. |
| The switch unit started | 200 | true | Switching to *<label>* mode. The TV goes dark for a few seconds. |
| `systemctl` refused or timed out | 200 | false | *<name>* could not start the switch to *<label>* mode: *<its first line>* |

One switch at a time: the server takes its own lock, looks at the units again inside it, and only then starts the switch unit, so two presses at once start one switch. A refusal from `systemctl` answers 200 with `ok: false`, as the powers do. No event is written: the events file is for the watch's changes, and the powers write none either.

## The colours
`web/css/argus.css`, one line under `:root`: Game purple (`--mode-game` #6B46C1, edge #A383F0), Desktop green (`--mode-desktop` #287043, edge #52B67A), white words on both. Contrast: white on purple 6.4:1, on green 6.0:1; the edges against the page 5.5:1 and 6.4:1. To swap them, exchange the game pair with the desktop pair on that line.

## Tests
`tests/modes_test.py` (no browser: the file's checks, the probe against a fake `systemctl`, the route end to end with an owner and a learner) and `tests/modes.test.js` (the pill, a hold, the switch, the keyboard, *Mode unknown*, 375 px). The fixture `tests/fixtures/modes.json` uses the fake units `fake-desktop-shell`, `fake-game-session`, `fake-to-desktop` and `fake-to-game`; `tests/run.sh` sets `ARGUS_MODES` to it, so every browser test sees the pill.
