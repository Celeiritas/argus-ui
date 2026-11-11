# Checks: does it WORK, not just run?

A program can be "active" in systemd, and even answer its own health check, while it cannot do its job. The classic case: a USB drive drops out and comes back under a new device name. A container that was running keeps an **old, dead copy** of the drive, so every file it opens fails with *Input/output error*, while the unit still reads active and the app still says healthy.

Argus looks for exactly this. A background loop in the server (`server/watch.py`) reads **checks**, proves each program can do its job, and says so in plain words: a line on the card (*Running, but not working: cannot read its drive*) and **one event** each time something changes state.

Nothing runs without a checks file, and the server never restarts anything by itself unless you approve it by name (see Self-repair).

## The checks file
`~/.config/argus-ui/checks.json` (change with `ARGUS_CHECKS`). No file: no checks. It is re-read every round, so editing it needs no restart.

```json
{ "checks": [
  { "id": "media-drive", "title": "The media drive", "job": "{{AGENT}}-media-drive",
    "mount": "/mnt/media" },
  { "id": "player", "title": "Media player", "job": "{{AGENT}}-player", "url": "{{AGENT}}",
    "unit": "player", "mount": "/mnt/media",
    "container": { "name": "player", "file": "/media/some-known-file.mp4" },
    "http": "http://127.0.0.1:8096/health",
    "fix": { "restart": ["player", "reader"], "say": "the player and the reader" } }
] }
```

| Field | Meaning |
|---|---|
| `id` | Lowercase letters, digits, dashes. Names the check in events, `auto-fix.json` and `state()`. |
| `title` | The name in plain words ("Media player"). Used in event titles. |
| `job` | Optional. The card to put the verdict on: an agent task name (`<agent>-<name>`). If there is no unit with that name, a card of its own appears (as for alert files). |
| `url` | Optional. A section id that goes into the event, so the page can open it. |
| `unit` | Optional. A `systemd --user` unit that must be active. |
| `mount` | Optional. The drive's mount point. Checked in the **mount table** (`/proc/self/mountinfo`): it must be there, writable, and not marked dropped. |
| `container` | Optional. `name`, and optionally `file` (read 4 KB) or `dir` (list it) *inside* the container, and `runtime` (default `podman`; a list is allowed). |
| `http` | Optional. An address (or a list) that must answer 2xx. An object `{ "url": ..., "status": 200 }` sets another status, or `"any"` for anything below 500. |
| `fix` | Optional. `{ "restart": [units], "say": "words" }`: what would fix it. Without it, a failure only tells. |

A check with only `mount` is a **drive check**: it speaks for the drive, and programs that need that drive stay quiet while it is down (one event, not four).

### The order of the proof, and its safety rules
1. Frozen by Medusa: paused on purpose, `works` is unknown.
2. The unit is active.
3. **The mount table first.** The drive must be mounted, not read-only and not `shutdown`. **No file is read on a drive that fails this**; a check that names a `file` or `dir` without a `mount` is refused.
4. The container's own mount table: a line that carries `shutdown` (or `emergency_ro`), or a block device the host no longer has, is a **dead copy**. Only if there is none, the named file is read.
5. The http address answers.

Everything is read without sudo. Every subprocess and http call has a 6-second limit, the loop runs in its own thread, and `state()` only reads the last results, so one hung check cannot block the page. Results that stop refreshing show as unknown. A check that cannot be run (the list of mounts is unreadable, the container is not reachable) is **unknown**, which never raises an event.

## What state() shows
`watch`: one entry per check, `{id, title, job, unit, works, code, reason, since, fix, autofix, drive}`.
`works` is `true`, `false` or `null` (unknown). `reason` is the plain phrase: *cannot read its drive*, *its drive is not connected*, *does not answer at its web address*. Each task card the checks name also gets `works` and `works_reason`. A failed check with a `job` adds an alert (same as an alert file: the card note, Argus's glare and the badge), worded *Running, but not working: cannot read its drive*.

## Events
`server/notify.py` takes events: `{id, at, kind, subject, title, body, url, level}`.

| `kind` | When | `level` |
|---|---|---|
| `broke` | something stopped working and there is no fix to ask for (or a restart did not help) | alert |
| `needs-yes` | something stopped working and a `fix` is named but not approved for self-repair | alert |
| `fixed` | Argus restarted it (approved) and it works again | info |
| `recovered` | it works again | info |
| `summary` | reserved for the daily summary | info |

**One event per change of state**, never per failed attempt: the same failure on the next round raises nothing. Starting the server again does not repeat it (the last known state is kept in `~/.local/state/argus-ui/watch.json`). `title` and `body` are plain words, for example *Media player runs, but cannot read its drive*.

The first sink writes `~/.local/state/argus-ui/events.jsonl` (`ARGUS_EVENTS`): one JSON object per line, the newest 500 kept. More sinks (a phone push) are added with `notify.register(fn)`.

## Self-repair ships OFF
`~/.config/argus-ui/auto-fix.json` lists the check ids you allow the server to repair: `{ "ids": ["player"] }` (or a plain list). **Absent, empty or broken means none**: the server raises `needs-yes` and waits for you (the restart is a Zeus action). For an id in the list, Argus runs the same `systemctl --user restart --no-block` as the bolt for each unit in `fix.restart` (never a frozen one), checks again for up to 20 seconds, and raises `fixed` or `broke`. It tries **once** per breakage; the next attempt waits until the check has worked again.

## Settings
`ARGUS_WATCH_INTERVAL` (seconds between rounds, default 60; 0 turns the loop off), `ARGUS_WATCH=0` (off), `ARGUS_CHECKS`, `ARGUS_AUTOFIX`, `ARGUS_EVENTS`, `ARGUS_WATCH_STATE`, `ARGUS_MOUNTINFO` (tests).

## Tests
`tests/watch_works_test.py` (canned mount tables in `tests/fixtures/watch/`, a fake container runtime, a real server in its own process) and `tests/works.test.js` (the card in a browser, the event file, the card going away). `bash tests/run.sh works`.
