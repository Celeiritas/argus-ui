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
Each `switch_unit` is a oneshot that does the whole switch (ends one session, starts the other) and then **ends**. Do not give it `RemainAfterExit=yes`: a unit that stays active after it runs is not started again by `systemctl start`, so the next press would do nothing. Argus tells the two apart by `SubState`: a switch unit that is `activating`, `reloading`, or `active` while it still runs is a switch under way (the pill says *Switching to …*); one that is `active` with `SubState` `exited` has already run, so the pill does not count it as switching, and a press to that mode is refused with 409 (*… its switch unit stays active after it runs (RemainAfterExit=yes), so a start would do nothing.*). Before the first deploy, check on the host: `systemctl --user show <switch units> -p Type -p RemainAfterExit -p ActiveState`.

**The host rule.** Argus only ever starts a switch unit, with `systemctl --user start --no-block <switch_unit>`, and never starts, stops or restarts a session unit (an `active_unit`) itself. Starting a game session from a script while the desktop runs makes a hidden second session: a black screen until a reboot. Write the care into the switch units; the pill only pulls their trigger.

## What the pill shows
- **The mode the server is in** is filled with its colour and read out as "Desktop (current)". **The other mode** is a button: press and hold it for 3 seconds (`holdConfirm`), or hold Space or Enter on it, and the server starts that mode's switch unit. The toast says *Switching to Game mode. The TV goes dark for a few seconds.*
- **Switching**: both halves are off, and a note beside the pill says *Switching to Game…* with a small dot that pulses (it stays still with reduced motion). The mode it leaves keeps its full colour with a dashed white edge, so its words keep their contrast. The page asks the server every 2 seconds until it is in the new mode, for 2 minutes at most. After that, if the server still says it is switching, the note says *Still switching: check the TV*; if nothing is switching any more and the mode never showed up, it says *Didn't reach Game: check the TV*, until the mode shows up, a failure is reported, or the next press.
- **A failed switch**: when the target's switch unit failed (less than 2 minutes ago, into a mode the server is not in), the note says *Couldn't switch to Game* with a still red dot, and the other half is a button again. The page that started the switch says so at once: Argus winces and the toast says *<name> couldn't switch to Game mode. Try again, or check the TV.*
- **Mode unknown**: when both `active_unit`s run, or neither does, or `systemctl` does not answer, the pill says *Mode unknown* in muted words, with nothing to press.
- **A refusal**: the toast says what the server said, and Argus winces.
- The wrapper is a group named "*<server name>* mode" (from `SERVER` in `~/.config/leafy/realm.json`, else "The server"). Each half is at least 44 px; long labels wrap inside their half; nothing scrolls sideways at 375 px.
- **For a screen reader** the other half is named verb first, *Switch to Game (hold 3 seconds to confirm)*, and an armed button says *Click again to switch to Game* (`holdConfirm`'s `name`, docs/fx.md); the visible word stays *Game*.
- **The keyboard stays on the pill.** When the pill is drawn again while it had the focus (a hold just started a switch, or the switch ended), the focus goes to its button, or to the group itself (`tabindex="-1"`, with a visible focus ring) while nothing can be pressed.

## The server
`server/modes.py` (stdlib, like `quiet.py`).
- **`api/state`** for the owner carries, when the file sets the feature up:
  `"modes": {"current": "desktop" | "game" | "unknown", "switching": "<id>" | null, "failed": "<id>" | null, "modes": [{"id", "label"}], "name": "<server name>"}`.
  Ids and labels only: the unit names never leave the server. A learner's state never has `modes`.
- **One `systemctl` call** reads all four units: `systemctl --user show A B C D -p Id -p ActiveState -p SubState -p InactiveEnterTimestampMonotonic`, with the server's usual 20 s timeout. The answer is kept about 2 seconds, however many pages ask, and a switch clears it. It never holds the lock the powers use.
- `switching` is set while a switch unit is under way (`activating`, `reloading`, or `active` but not `exited`), or for up to 120 s after a switch this server started, until the target mode is current. That note is written before the start, and is cleared when the target mode is current, when 120 s pass, when `systemctl` refuses the start, or when the target's switch unit fails after the switch began. The clock for it is read under the same lock as the note, so a probe running beside a press can't wipe it.
- **After a restart** (a deploy in the middle of a switch) the note, which lives in memory, is rebuilt once from systemd: a switch unit that ended well less than 120 s ago (its `InactiveEnterTimestampMonotonic`, on the same clock as Python's `time.monotonic()`) into a mode the host is not in yet counts as a switch still under way. The same happens once after the file changes.
- `failed` is set, only while nothing is switching, to the mode whose switch unit failed less than 120 s ago, when the host is not in that mode.
- **`POST api/mode`** with `{"to": "<id>"}`: the owner's only (a learner gets 403), after the usual JSON, Origin and Sec-Fetch-Site checks. It answers JSON `{"ok", "msg"}`:

| Case | Code | `ok` | `msg` |
|---|---|---|---|
| No file, or a bad one | 404 | false | Desktop / Game mode is not set up on this server. |
| An id that is not in the file | 400 | false | There is no mode with that name. Reload the page. |
| A switch is under way | 409 | false | *<name>* is already switching to *<label>* mode. |
| The mode can't be told | 409 | false | Can't tell which mode *<name>* is in right now. Try again in a minute. |
| Already in that mode | 200 | true | Already in *<label>* mode. |
| Its switch unit stays active (`RemainAfterExit=yes`) | 409 | false | *<name>* can't switch to *<label>* mode: its switch unit stays active after it runs (RemainAfterExit=yes), so a start would do nothing. |
| The switch unit started | 200 | true | Switching to *<label>* mode. The TV goes dark for a few seconds. |
| `systemctl` refused | 200 | false | *<name>* could not start the switch to *<label>* mode: *<its first line>* |
| `systemctl` did not answer in 20 s | 200 | false | *<name>* may be switching to *<label>* mode: systemctl did not answer in time. Check the TV before you try again. (The start may still have been queued, so the switching note stays and a second press is refused until the mode shows up or 120 s pass.) |

One switch at a time: the server takes its own lock, looks at the units again inside it, and only then starts the switch unit, so two presses at once start one switch. A refusal from `systemctl` answers 200 with `ok: false`, as the powers do. No event is written: the events file is for the watch's changes, and the powers write none either.

## The colours
`web/css/argus.css`, one line under `:root`: Game purple (`--mode-game` #6B46C1, edge #A383F0), Desktop green (`--mode-desktop` #287043, edge #52B67A), white words on both. Contrast: white on purple 6.4:1, on green 6.0:1; the edges against the page 5.5:1 and 6.4:1. While switching, the mode it leaves is not faded (opacity .6 dropped its words to about 3.7:1); it keeps these colours and gets a dashed white edge. The failed note's dot is `--bad`; its words keep the note's colour. To swap the modes' colours, exchange the game pair with the desktop pair on that line.

## Tests
`tests/modes_test.py` (37 tests, no browser: the file's checks, the probe against a fake `systemctl`, the pending note against a racing probe, a start that times out, a failed switch, a switch unit that stays active, the note rebuilt after a restart, the route end to end with an owner and a learner) and `tests/modes.test.js` (the pill, its verb-first name and armed text, a hold, the switch and the dashed edge, the keyboard staying on the pill, a failed switch, *Mode unknown*, 375 px). The fixture `tests/fixtures/modes.json` uses the fake units `fake-desktop-shell`, `fake-game-session`, `fake-to-desktop` and `fake-to-game`; `tests/run.sh` sets `ARGUS_MODES` to it, so every browser test sees the pill.
