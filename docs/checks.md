# Checks: does it WORK, not just run?

A program can be "active" in systemd, and even answer its own health check, while it cannot do its job. The classic case: a USB drive drops out and comes back under a new device name. A container that was running keeps an **old, dead copy** of the drive, so every file it opens fails with *Input/output error*, while the unit still reads active and the app still says healthy.

Argus looks for exactly this. A background loop in the server (`server/watch.py`) reads **checks**, proves each program can do its job, and says so in plain words: a line on the card (*Running, but not working: cannot read its drive*) and **one event** each time something changes state.

Nothing runs without a checks file, and the server never restarts anything by itself unless you approve it by name and end the trial (see Self-repair).

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
    "fix": { "restart": ["player"], "say": "the media player" } },
  { "id": "downloader", "title": "Downloader", "job": "{{AGENT}}-downloader",
    "unit": "downloader", "mount": "/mnt/media",
    "container": { "name": "downloader", "mount": "/downloads" } }
] }
```

| Field | Meaning |
|---|---|
| `id` | Lowercase letters, digits, dashes. Names the check in events, `auto-fix.json` and `state()`. |
| `title` | The name in plain words ("Media player"). Used in event titles. |
| `job` | Optional. The card to put the verdict on: an agent task name (`<agent>-<name>`). If there is no unit with that name, a card of its own appears (as for alert files). |
| `url` | Optional. A section id that goes into the event, so the page can open it. |
| `unit` | Optional. A `systemd --user` unit that must be active. Unit and container names are letters, digits, `_ . @ -` and never start with `-`. |
| `mount` | Optional. The drive's mount point. Checked in the **mount table** (`/proc/self/mountinfo`): it must be there, writable, and not marked dropped. |
| `container` | Optional. `name`, and optionally `file` (read 4 KB) or `dir` (list it) *inside* the container, `mount` (see below), and `runtime` (default `podman`; a list is allowed). |
| `container.mount` | Optional. The path **inside** the container where the drive (or a folder of it) is bound, for example `"/downloads"`. The container's own mount table must have a line for that path, on the same device the host has for the check's `mount`; if not, it is a **dead copy** (same words on the card). Only mount tables are read for this, never a file. Needs `mount`. |
| `container.dir` | List a folder. **Name a folder that always has something in it**: an empty folder reads as *cannot read its drive*, because an empty folder is exactly what a container sees when it missed its drive. |
| `http` | Optional. An address (or a list) that must answer 2xx. An object `{ "url": ..., "status": 200 }` sets another status, or `"any"` for anything below 500. |
| `fix` | Optional. `{ "restart": [units], "say": "words" }`: what would fix it. Without it, a failure only tells. |

**`container.runtime` names a program the server will run** (with `exec <name> ...` after it), and `unit` and `fix.restart` name units it will ask `systemctl` about or restart. So only the owner may be able to write `checks.json` and `auto-fix.json`: keep `~/.config/argus-ui/` writable by the server's own user alone.

A check with only `mount` is a **drive check**: it speaks for the drive, and programs that need that drive stay quiet while it is down (one event, not four). Since 4.40 that one event names the programs that went with it, so the phone buzzes once: *The media drive is not connected; Jellyfin, Audiobookshelf and 1 more cannot read it* (*cannot save to it* for a read-only drive). This holds for every program on that drive whose only problem is the drive, with or without a `unit`, and for a second drive check of the same mount (the first in the file speaks), the same folding Watch's drive block does. Without a drive check, each program on a gone drive raises its own `broke`; add one to fold them.

### The order of the proof, and its safety rules
1. Frozen by Medusa: paused on purpose, `works` is unknown.
2. The unit is active.
3. **The mount table first.** The drive must be mounted, not read-only and not `shutdown`. **No file is read on a drive that fails this**; a check that names a `file` or `dir` without a `mount` is refused.
4. The container's own mount table: a line that carries `shutdown` (or `emergency_ro`), or a block device the host no longer has, is a **dead copy**; so is a `container.mount` line that is missing or sits on another device than the host's drive (a container started before the drive was mounted binds the empty folder underneath; its card gets the same words, its explanation says that story instead of "unplugged and came back"). Only if there is none, the named file is read.
   **Which answers of the test read count as "cannot read its drive":** only exit code 1 or 2 (what `head` and `ls`, GNU and busybox, return when the read itself fails, for example *Input/output error*), or exit 0 with nothing read (an empty file or folder). Any other exit code is the container runtime's own trouble, not the drive's: 125, 126, 127 (podman could not run the command: the container is stopping, a lock timed out, the command is missing), a signal such as 137, or anything unexpected. Those make the check **unknown** (`cannot-look`), so they never raise an event and never restart anything.
5. The http address answers.

Everything is read without sudo. **Time limits, per kind of call:** a look or a read inside a container and an http call get 6 seconds each; `systemctl --user is-active` and `systemctl --user restart --no-block` go through the server's own 20-second limit (the same as the page's power buttons). The loop runs in its own thread, and `state()` only reads the last results, so one hung check cannot block the page. Results that stop refreshing show as unknown. A check that cannot be run (the list of mounts is unreadable, the container is not reachable) is **unknown**, which never raises an event.

### When something counts
- **A failure counts once it is seen in 2 rounds in a row.** One slow answer is not a breakage: after one bad round the check shows `works: null` with code `pending`, and nothing is raised or restarted. *In a row* means it: an unknown round in between (the container could not be looked into, the unit was starting) starts the count again, so fail, unknown, fail is not two. Getting better counts at once. The count is saved with the rest of the state, so a restart of the server does not reset it.
- **Self-repair waits for its own 2 rounds.** A program that already counts as broken for one reason (its web address is silent) and then shows *cannot read its drive* is not restarted on that one round: the code that self-repair acts on must itself be seen in 2 rounds in a row, with no unknown round in between. For a check that self-repair may act on, the event waits with it, so the owner gets one event that says what was done; for every other check, a change of reason raises its event at once.
- **A unit that is starting is not down.** `systemctl is-active` saying `activating`, `reloading` or `deactivating` means "cannot tell yet": no verdict, no event, no restart. A unit that stays in one of those for more than 3 rounds in a row counts as not running (a program that crashes and starts again in a loop looks like that). This is the watch's own reading; the task cards keep theirs.
- **A test read that hangs** (no answer in 6 seconds) is not repeated for 15 minutes, or until the host's mount line for its drive changes (unplugged and back, re-mounted), so reads cannot pile up. Rounds without a read count as still hanging, so after 2 rounds the check shows a `warn` note on its card, *Media player does not answer when it reads its drive*, and raises one `broke` event with level `warn`. It has its own code (`read-hung`), so it never leads to a restart.

## What state() shows
`watch`: one entry per check, `{id, title, job, unit, works, code, reason, note, since, fix, fix_say, autofix, drive, title_line, detail, again, fixing}`
(4.40.0: `fix_say` the words for what its fix restarts, `title_line` the event-style sentence, `again` true while it works again after
a failure, `queued` true while a fix is asked for and its restart not yet sent, `by` (`owner` or `argus`: who asked for it),
`fixing` true once the restart has really been sent and
Argus looks again, `mount`, `looked` the time of the last round with a real verdict, `unsure` a sentence when that is not this round).
`since` is when its state last changed (the first round it was seen, until then).

**After a start of the server**, until its first round has finished, `watch` holds the saved verdicts from
`~/.local/state/argus-ui/watch.json` (a check known not to work stays so, with the "not been able to look" sentence; the rest is
unknown, code `starting`), never an empty list, and `state()` says `watch_ready: false`. **While Argus's own repair runs**, its row
is the confirmed failure (`works: false`) with `fixing` and `by: "argus"`.

**A known breakage stays known.** A check whose last known verdict is "not working" keeps being published as not working, with its
last code and reason, through a round where Argus cannot look (unknown: podman could not look inside, the unit is starting) and when
its result goes stale (the loop has not refreshed it for `3 x interval + 30` seconds). Its row then carries `unsure`: *Argus has not
been able to look again since 5:52 AM.* An unknown round never counts as a change, for events or for what the page says. A check that
was working and goes unknown is not turned into trouble (`works: null`).
`works` is `true`, `false` or `null` (unknown). `reason` is the plain phrase: *cannot read its drive*, *its drive is not connected*, *does not answer at its web address*. Each task card the checks name also gets `works` and `works_reason`. A failed check with a `job` adds an alert (same as an alert file: the card note, Argus's glare and the badge), worded *Running, but not working: cannot read its drive*.

### What the card says about a restart
A failed check that has a `fix` also says what Argus did about it (`note` in `watch`): Watch's trouble block shows it as *Argus: …* (docs/home.md "Trouble first"). It never claims a restart that did not happen:

| Situation | Added to the card |
|---|---|
| Trial day, where a restart would have happened | *Argus would have restarted the media player by itself and did not, because for now it only notes what it would do.* |
| Not on the self-repair list, a reason self-repair does not act on, or the try of the day already used | *Argus did not restart it and waits for your yes.* (the page shows it after "Argus:" as *Did not restart it …*) |
| Argus restarted it and it did not help | *Argus restarted the media player once by itself, and it did not help. It waits for your yes.* |
| The restart command itself failed | *Argus tried to restart the media player by itself, but the restart did not work. It waits for your yes.* |
| Self-repair may still act next round (the first round of *cannot read its drive*) | nothing yet |
| You pressed the fix on the page and it did not help (4.40.0) | *You restarted the media player at 4:52 AM, and it did not help.* |
| You pressed it and the restart command failed | *You asked for a restart of the media player at 4:52 AM, but the restart did not work.* |
| The server restarted during your restart's 90-second look (a deploy), so its outcome never came (4.40.0) | *You restarted the media player at 4:52 AM, but Argus himself was restarted before he could see whether it helped.* |
| The same during Argus's own repair | *Argus restarted the media player by himself at 4:52 AM, but was restarted himself before he could see whether it helped. It waits for your yes.* |

While a restart runs, the note is empty: the page says *Restarting it now …* from the row's `fixing` / `queued`. The try is saved
(`outcome` in watch.json) before its restart is sent, which is how a restart of the server in between is told apart from no restart
at all; no event is written for such a lost try, and the next real change raises its usual event (`recovered` when it works again).

A whole card then reads, for example, *Running, but not working: cannot read its drive. Argus did not restart it and waits for your yes.* A check without a `fix`, a drive that is missing (the drive's own card says it) and a test read that hangs keep their text as it is.

**A drive that is gone or read-only** (`drive-*` on a program): no note, no button, and its event is a `broke`, true as one
sentence on a lock screen: *Jellyfin runs, but its drive is not connected* / *The drive it needs is not mounted, so there is nothing for
it to read. Argus waits for the drive: a restart would not help until it is back.* It never says a restart should fix it or that a
yes is awaited.

**Times** in every sentence read like the rest of the page, *5:52 AM* (`clock()`, the same on Linux and Windows).

## Events
`server/notify.py` takes events: `{id, at, kind, subject, title, body, url, level}`. The events of a repair (4.40) also carry `by`:
`owner` (his press on the page, with `pressed`, when he pressed) or `argus` (self-repair, as allowed). The daily summary words a
repair by who did it, and the phone does not buzz for what his own press caused in the last 2 minutes (docs/phone-alerts.md);
`api/events` sends only the fields above.

| `kind` | When | `level` |
|---|---|---|
| `broke` | something stopped working and there is no fix to ask for (or a restart did not help, or did not work) | alert; `warn` for a test read that hangs |
| `needs-yes` | something stopped working and a `fix` is named; Argus may not (or, on the trial day, did not) restart it by itself | alert |
| `fixed` | Argus restarted it (approved) and it works again | info |
| `recovered` | it works again | info |
| `summary` | the daily summary, once a day (`server/summary.py`, docs/phone-alerts.md) | info |

**One event per change of state**, never per failed attempt: the same failure on the next round raises nothing. A program that stayed quiet because its drive had its own event (see above) raises no `recovered` either when the drive comes back. Starting the server again does not repeat anything (the last known state is kept in `~/.local/state/argus-ui/watch.json`). `title` and `body` are plain words, for example *Media player runs, but cannot read its drive*.

The first sink writes `~/.local/state/argus-ui/events.jsonl` (`ARGUS_EVENTS`): one JSON object per line, the newest 500 kept. More sinks are added with `notify.register(fn)`; the phone alerts' sink (`server/push.py`) buzzes owners' phones for `broke`, `needs-yes` and `summary` only (docs/phone-alerts.md).

## Self-repair ships OFF, and starts as a trial
Self-repair is for one situation only: **the program runs, but cannot read its drive** (codes `dead-copy` and `cannot-read`). A slow or missing web answer, a unit that is down or starting, a test read that hangs, or anything else never restarts anything; those raise `needs-yes` or `broke` and wait for you (the restart is a Zeus action).

`~/.config/argus-ui/auto-fix.json` (`ARGUS_AUTOFIX`) names the checks you allow it for:

```json
{ "ids": ["player"], "trial": true }
```

| Field | Meaning |
|---|---|
| `ids` | The check ids self-repair may act on. Each needs a `fix`. |
| `trial` | **Note only, the default.** Unless the file says `"trial": false` in so many words, nothing is restarted: where a restart would have happened, Argus records the try exactly as a real one and raises one `needs-yes`: *Argus would have restarted the media player by itself, but it did not: for now it only notes what it would do. Waiting for your yes.* After a quiet trial day, change it to `false` by hand. |

- **No file: off.** A file that cannot be read as JSON, or has another shape (a plain list, other keys, `"trial": "false"` as text), switches self-repair **off completely** and writes one line to the server log.
- **One try per check in 24 hours.** The time of the last try (real or trial) is saved in `~/.local/state/argus-ui/watch.json` **before** the restart command runs, and it is kept when the program works again and when the server restarts. A second breakage inside that day raises `needs-yes` and says when Argus last tried.
- **The try:** the same `systemctl --user restart --no-block` as the bolt, for each unit in `fix.restart`, never a frozen one, and each unit at most once per round even when two checks name it. Then Argus checks again every 3 seconds for up to **90 seconds** (it stops as soon as the program works) and raises `fixed` or `broke`. That wait does not hold the lock the page's power buttons use. A restart command that hangs or fails counts as *the restart did not work* (a `broke` event); the round still finishes and saves its state.

## Your yes from the page (4.40.0)
`POST api/watch/fix` with `{"id": "<check id>"}` (JSON only, the usual POST checks) is the owner's yes, from the hold button on Watch
or Today. **It runs exactly the fix that checks.json declares for that check and nothing else**: the id is looked up in the checks
file; no unit name is taken from the request. It is refused, with one plain sentence in `msg`, when:

| Refused when | Status | Says |
|---|---|---|
| the id is not a check (or not a valid id) | 404 (400) | *There is no check with that name. Reload the page.* |
| the check has no `fix` | 409 | *Media player has no fix that Argus may run. Look at it on the server.* |
| it works right now | 409 | *Media player works right now, so there is nothing to fix.* |
| its `job`, its `unit` or a unit of its fix is paused (frozen) | 409 | *Media player is paused (frozen). Resume it first, then try again.* |
| a fix of it started less than 2 minutes ago (yours, or Argus's real one; a trial note does not count) | 409 | *A restart of the media player started at 4:52 AM. Give it 2 minutes, then try again if it still does not work.* |
| the watch loop is off | 409 | *The watch is switched off, so Argus cannot run a fix from here.* |

Accepted, it answers `{"ok": true, "msg": "Restarting the media player. Argus looks again for up to 90 seconds and tells you how it went."}`
at once. The check and the queueing happen under the same lock as the page's other powers. The loop is woken and, on that round,
starts the fix **through the same `repair()` as self-repair**, in a short-lived thread of its own (one per check), so its 90-second
look never holds the loop: every other check keeps its round, and a second fix asked meanwhile starts at once. Restarts of the same unit
never overlap (a unit being restarted by another fix counts as restarted). The page says *queued* until the restart is really sent,
then *Restarting it now*; the 90 seconds start there. It uses the same `systemctl --user restart --no-block` for each unit of
`fix.restart` (never a frozen one, each once per round), the same look every 3 seconds for up to 90 seconds. It writes **one event**
(existing kinds): `fixed` (*You restarted the media player from the page at 4:52 AM, and it works now.*) or `broke` (*… You
restarted the media player at 4:52 AM, and it did not help.*). The card then ends on *Works again* or on the note above. When it
works again before the round, nothing is restarted (the usual `recovered` event). Self-repair does not restart it again right
after you did. Only the owner sees the button (the server's role table comes with sign-in, docs/home.md "Who sees what").

## What happened lately: api/events (4.40.0)
`GET api/events?limit=N` → `{"events": [...], "since": "<when the server started>"}`: the newest events from the events file, newest
first, 10 by default, at most 100 (a limit that is not 1 to 4 ASCII digits, an empty one included: 400; `0` gives 1). Each event carries only its own fields
(`id, at, kind, subject, title, body, url, level`, as text); a damaged line is skipped. Watch shows the newest 10.

## podman and the journal
Every `podman exec` the watch makes carries `--events-backend=none` (before `exec`): without it podman writes 2 lines to the journal
per call, about 14,000 a day from this loop; the exit code is the same. It is added only when the runtime is podman (the default,
or a path or list ending in a podman program); another runtime (`docker`) gets no flag it does not know.

## Settings
`ARGUS_WATCH_INTERVAL` (seconds between rounds, default 60; 0 turns the loop off), `ARGUS_WATCH=0` (off), `ARGUS_CHECKS`, `ARGUS_AUTOFIX`, `ARGUS_EVENTS`, `ARGUS_WATCH_STATE`, `ARGUS_MOUNTINFO` (tests). `tests/run.sh` sets `HOME` and `USERPROFILE` to its temp folder and `ARGUS_EVENTS` and `ARGUS_WATCH_STATE` to explicit paths, so a test run never writes into a real profile.

## Tests
`tests/watch_works_test.py` (canned mount tables in `tests/fixtures/watch/`, a fake container runtime, a real server in its own process), `tests/watch_routes_test.py` (the owner's yes: every refusal, one real fix that works and one that does not help; `api/events`, `count`, `restarts`, podman's flag in the fake runtime's call log) and `tests/works.test.js` (the row in a browser, the event file, the row going back to *Works*). `tests/salience.test.js` checks the page side (docs/home.md). `bash tests/run.sh works`.
