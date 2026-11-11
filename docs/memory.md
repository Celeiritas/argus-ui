# Memory (Mnemosyne's backups)

Memory (`<base>/memory`) answers **"are my backups fresh, and how many copies exist?"** It is a bundled server plugin (`plugins/memory/`, docs/leafy-plugin.md), built in 4.30.0 from docs/ui-plan.md §10. Mnemosyne has no repo and no status file, so the page reads what her jobs leave behind: the snapshot files and the task information Elaia already collects (`ctx.jobs('mnemosyne-')`).

## What it shows
- **Latest snapshot:** its age ("2 days ago", with the date and time), its size, the next run (the brain job's timer) and how many snapshots the server keeps, with their total size. A warning line appears when the newest snapshot is older than 8 days (the job runs weekly: *The newest snapshot is older than a week: look at its weekly job under Mnemosyne on the Watch page.*) or the brain job's last run failed (*The last try failed (Sun 4:03 AM): its card under Mnemosyne on the Watch page has the log.*).
- **Where your backups are** (3-2-1): three rows, each a mark and the copy's name, then **one plain sentence** (plugin 1.1.0, Elaia 4.39.0). The sentence says what the copy is, when it was last made and, only when something is not fine, what to do. The mark is a shape as well as a colour (✓ fine, ! older than a week, ✕ missing or failed, ? no word or unreadable, ↻ running), and the row's accessible name is the sentence (the mark is hidden from screen readers). No status words (*Done, Old, None, Unknown, Not yet, Failed, Not run*) and never the word *secrets*: tests check both.
- **The shelf:** one bar per snapshot (the newest 12), oldest on the left, height by size, labelled by date; the newest is marked. While a backup runs, a dashed bar fills at the right. Under it, **All N snapshots** lists each one with its time, age and exact size in bytes (the same number as `ls -l`). These are plain bars and words: **the jar, shelf and vessel art waits for the owner's approval** (ui-plan §13).

### The rows, every state, word for word
Times read as the rest of the page writes them: an age, then the clock time in brackets: *3 hours ago (9:00 AM)* today, *2 days ago (Sunday, 4:00 AM)* within the week, *12 days ago (Nov 8, 4:00 AM)* before that (with the year when it is another year's). Ages count hours within a day, then calendar days, so the age and the weekday never disagree. A time ahead of the server's clock reads *just now*, never *in 3 hours*. "Older than a week" is the same 8-day rule as before, counted in the calendar days the age shows: more than 8 calendar days, so a check mark never sits beside *9 days ago*, at midnight or when the clocks change.

**Snapshots the server keeps of itself** (the snapshot files, and what the brain job is doing):

| State | Mark | Sentence |
|---|---|---|
| fresh | ✓ | The server took its newest snapshot of itself 2 days ago (Sunday, 4:00 AM) and keeps 3 of them, 2.6 KB in all. *(one snapshot: "and keeps only that one, 900 bytes.")* |
| older than 8 days | ! | The server's newest snapshot of itself is from 12 days ago (Nov 8, 4:00 AM), older than a week, so look at its weekly job under Mnemosyne on the Watch page. |
| none, a brain job exists | ✕ | The server has no snapshot of itself yet: hold Back up now to take the first one. *(the job is paused: "…yet: its weekly job is paused; press Resume on its card on the Watch page first.")* |
| none, no brain job | ✕ | The server has no snapshot of itself yet, and no weekly job to take one was found. |
| last run failed | ✕ | The server's newest snapshot of itself is from 2 days ago (Sunday, 4:00 AM), and its last try failed, so look at its weekly job under Mnemosyne on the Watch page. *(older than 8 days: "…(Nov 8, 4:00 AM), older than a week, and its last try failed, so …"; no snapshot: "The server's first try to take a snapshot of itself failed, so look at its weekly job under Mnemosyne on the Watch page.")* |
| running | ↻ | The server is taking a new snapshot of itself now; its newest finished one is from 2 days ago (Sunday, 4:00 AM). *(no snapshot yet: "The server is taking its first snapshot of itself now.")* |

**Your PC's own weekly backup** (the marker file, below). Every sentence ends with what the weekly run leaves out: *your passwords and keys are left out on purpose: you back those up by hand, typing the passphrase* (shortened to "; …" below):

| State | Mark | Sentence |
|---|---|---|
| no marker | ? | No word has come from your PC's weekly backup yet (the PC sends word each time one finishes); … |
| fresh, with `sets` and `bytes` | ✓ | Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 6 sets of files, 117.7 MB; … |
| fresh, only `bytes` | ✓ | Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 117.7 MB of files; … |
| fresh, only `sets` | ✓ | Your PC's weekly backup finished yesterday (Monday, 3:00 AM) with 6 sets of files; … *(one: "1 set of files")* |
| fresh, only `at` | ✓ | Your PC's weekly backup finished yesterday (Monday, 3:00 AM); … |
| `at` up to a day ahead (another clock) | ✓ | Your PC's weekly backup finished just now with 6 sets of files, 117.7 MB; … |
| older than 8 days | ! | Your PC's weekly backup last finished 40 days ago (Oct 1, 3:00 AM), older than a week, so check its scheduled task on your PC; … |
| marker is not JSON, not an object, too big (over 64 KB), or its `at` is not a time | ? | Word came from your PC's weekly backup but could not be read, so this page cannot tell when it last ran (the next backup sends it again); … |
| `at` more than a day ahead (a wrong clock, not a fresh backup) | ? | Word came from your PC's weekly backup with a time still ahead of this server's clock (Nov 20, 3:00 AM), so check the date and time on your PC; … |

**The server's copy outside your home** (the `mnemosyne-<server>-offsite` job, once it exists; its time is the task's last start):

| State | Mark | Sentence |
|---|---|---|
| no job yet | ✕ | The server's backups are not copied outside your home yet: the job that will do that is planned but not built. |
| never run | ? | The job that copies the server's backups outside your home is set up but has not run yet: see when it runs under Mnemosyne on the Watch page. |
| failed | ✕ | The last try to copy the server's backups outside your home failed 2 days ago (Sunday, 4:30 AM), so look at its job under Mnemosyne on the Watch page. |
| running | ↻ | The server's backups are being copied outside your home now. |
| done | ✓ | The server's backups were last copied outside your home 2 days ago (Sunday, 4:30 AM). *(no start time known: "The server's backups have been copied outside your home.")* |

## Back up now
A hold-to-confirm button (`api.holdConfirm`: 3 seconds, or Space/Enter held; docs/fx.md). The note beside it says Jellyfin pauses for about a minute. It POSTs `api/memory/backup`, which runs exactly one command, as an argument list with no shell:
```
systemctl --user start --no-block mnemosyne-<server>-brain.service
```
The unit is never read from the request. It is the one task whose name matches `mnemosyne-<name>-brain` (or `"unit"` in the config, if that names such a task). It is refused, with the reason under the button, when:
- **a game is running**: `medusa-gameguard` says so through either of the two files it writes, `~/.local/state/medusa-gameguard/frozen-by-me.json` (a non-empty list of what it froze) or its alert file `~/.local/state/argus-ui/alerts/medusa-gameguard.json`. Both clear about a minute after the game closes.
- a backup is already running, the brain job is frozen (thaw it on Watch first), or there is no brain job.

While it runs, a ribbon of motes (`api.fx.motes`) flows from the server's copy into the filling bar (none with reduced motion).

**Never:** deleting snapshots, restoring, or showing what is inside a snapshot (they hold passwords and keys). The plugin lists names and sizes only, directly inside the one folder: no subfolders, no symlinks, nothing outside it, and nothing in a request can change which folder it reads.

## Home
Its line on Today is one plain sentence about the server and the PC, then one about the copy outside the home (since 4.39.0; it was `Last snapshot 2 days ago · 3 on the server, 4.1 GB · off-site not yet`). On a phone the card shows the start of it; the whole line is in **Needs you** when it needs you.

| Server, PC | First sentence |
|---|---|
| both fresh | Backups are fresh: the server 2 days ago, your PC yesterday. |
| a backup is running | Backing up the server now; *(the PC's part)*. |
| last run failed | The server's last backup failed; *(the PC's part)*. |
| no snapshot | The server has no backup yet; *(the PC's part)*. |
| older than 8 days | The server's backup is older than a week (12 days ago); *(the PC's part)*. |
| fresh, the PC not | The server backed up 2 days ago; *(the PC's part)*. |

The PC's part: *your PC backed up 21 hours ago* (fresh), *your PC's backup is older than a week (40 days ago)*, *your PC's backup sent word this page cannot read* (a marker that cannot be read), *your PC's clock looks wrong* (a marker more than a day ahead), or *no word from your PC's backup yet* (no marker). While a backup runs over a snapshot older than a week, the first part says so: *Backing up the server now (last one: 12 days ago)*.

**The PC is the problem** (the server is fresh, the PC's backup is older than a week): the line starts with the verdict, because the card on Today shows only the start of it: *Check your PC's backup: it last finished 12 days ago; the server backed up 2 days ago.*

The second sentence is about the server's copy outside the home only (the PC's weekly archives go to a cloud folder, which this page cannot see): *The server has no copy outside your home yet.* (no job, or never run), *The copy of the server's backups outside your home failed.*, *Copying the server's backups outside your home now.*, or *The server's backups were copied outside your home 2 days ago.*

For example: *Backups are fresh: the server 2 days ago, your PC 3 days ago. The server has no copy outside your home yet.*

It goes to **Needs you** when the newest snapshot is older than 8 days (**Check backups**), the last run failed (**Look at the failed backup**) or, since 4.41.0, the PC's backup is older than a week (**Check the PC's backup**).

## Settings
Nothing is needed when the snapshots are in the only `~/.mnemosyne/<Server>-brain/` folder and there is one brain job. Otherwise, `~/.config/argus-ui/memory.json` (read on every refresh, all fields optional):
```json
{ "folder": "~/.mnemosyne/<Server>-brain", "unit": "mnemosyne-<server>-brain",
  "pc_marker": "~/.mnemosyne/last-backup.json", "note": "Jellyfin pauses for about a minute while the snapshot is made." }
```
Environment overrides for tests: `ARGUS_MEMORY_DIR` (the folder), `ARGUS_MEMORY_CONFIG`, `ARGUS_MNEMOSYNE` (where `<Server>-brain/` is looked for), `ARGUS_GAMEGUARD`, `ARGUS_ALERTS`, `ARGUS_SYSTEMCTL`.

### The PC's marker file
The PC's backup writes a small `last-backup.json` when it finishes, and it is brought to the server at `pc_marker` (default `~/.mnemosyne/last-backup.json`):
```json
{ "at": "2026-11-08T03:12:00-07:00", "sets": 6, "bytes": 123456789 }
```
- `at` (required): an ISO time; with a zone it is read in the server's zone. A time up to a day ahead of the server's clock reads *just now*; further ahead, the row says to check the PC's clock.
- `sets` (optional): how many sets of files the run backed up, a whole number from 1 to 999. Anything else is left out.
- `bytes` (optional): their size, shown in MB or GB with at most one decimal (*117.7 MB*, *4.1 GB*, *12 GB*, *under 0.1 MB*). Zero, negative, not a number (a string, `true`, `NaN`, `Infinity`) or over 16 TB is left out, never shown as it is.
- A byte-order mark at the start is fine (Windows PowerShell 5 writes one with `-Encoding UTF8`; before 4.39.0 such a file read as no word). A file over 64 KB is not read.

Until that file arrives, the PC's row says no word has come yet.

## Tests
- `tests/memory_test.py` (no browser, runs on Windows too): the three fixture snapshots and never the decoys (a text file, a name without a date, a folder named like a snapshot, a symlink to a file outside), the same sizes as the files, reading changes nothing; **every sentence above, word for word** (server: fresh, the 8-day edge, older, none with and without a job, failed, running; PC: no marker, only `at`, `sets` and `bytes`, `sets` missing or not a count, `bytes` zero, negative, a string, NaN, huge, older than 8 days, not JSON, a BOM, `at` not a time, `at` a little and far ahead; off-site: no job, never run, failed, done, running); ages and clock times; sizes; Home's line for each combination that matters and *needs*; no status word and never *secrets* across 250 combinations; and Back up now: the exact command, the body ignored, refused while a game runs (either file), while running, frozen or missing.
- `tests/memory.test.js` (Playwright, through `tests/run.sh`): the page lists three snapshots, bar heights follow size, each row's sentence is its accessible name, no status word and never *secrets*, the hold works by keyboard (let go early sends nothing, refused while a game runs, then starts the job, a bar fills and the server's row says it runs), Home's place, and 375 px with no sideways scroll. Then three scenarios with their own folder and marker, dated from today (all fine; the PC never heard from; the server's snapshot older than a week): each row's exact sentence and mark, Today's line and Needs you, and no sideways scroll at 360, 375 and 412 px.
- The fixture folder is `tests/fixtures/memory/Server-brain/`; `tests/run.sh` copies it into the throwaway HOME's `~/.mnemosyne/`.
