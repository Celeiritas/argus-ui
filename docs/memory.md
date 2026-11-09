# Memory (Mnemosyne's backups)

Memory (`<base>/memory`) answers **"are my backups fresh, and how many copies exist?"** It is a bundled server plugin (`plugins/memory/`, docs/leafy-plugin.md), built in 4.30.0 from docs/ui-plan.md §10. Mnemosyne has no repo and no status file, so the page reads what her jobs leave behind: the snapshot files and the task information Elaia already collects (`ctx.jobs('mnemosyne-')`).

## What it shows
- **Latest snapshot:** its age ("2 days ago", with the date and time), its size, the next run (the brain job's timer) and how many snapshots the server keeps, with their total size. A warning line appears when the newest snapshot is older than 8 days (the job runs weekly) or the brain job's last run failed.
- **Copies (3-2-1):** three rows, each with a mark *and* a word, never colour alone:
  | Copy | Shows |
  |---|---|
  | On the server | ✓ Done when there is a snapshot (! Old after 8 days, ✕ None without one) |
  | On the PC | read from a marker file (below): ✓ Done, ! Old after 8 days, or ? **Unknown** when there is no marker. The PC's folder can't be seen from the server, so it never guesses. |
  | Off-site | ✕ **Not yet** until a `mnemosyne-<server>-offsite` job exists; then that job's last run (✓ Done, ✕ Failed, ? Not run) |
- **The shelf:** one bar per snapshot (the newest 12), oldest on the left, height by size, labelled by date; the newest is marked. While a backup runs, a dashed bar fills at the right. Under it, **All N snapshots** lists each one with its time, age and exact size in bytes (the same number as `ls -l`). These are plain bars and words: **the jar, shelf and vessel art waits for the owner's approval** (ui-plan §13).

## Back up now
A hold-to-confirm button (`api.holdConfirm`: 3 seconds, or Space/Enter held; docs/fx.md). The note beside it says Jellyfin pauses for about a minute. It POSTs `api/memory/backup`, which runs exactly one command, as an argument list with no shell:
```
systemctl --user start --no-block mnemosyne-<server>-brain.service
```
The unit is never read from the request. It is the one task whose name matches `mnemosyne-<name>-brain` (or `"unit"` in the config, if that names such a task). It is refused, with the reason under the button, when:
- **a game is running**: `medusa-gameguard` says so through either of the two files it writes, `~/.local/state/medusa-gameguard/frozen-by-me.json` (a non-empty list of what it froze) or its alert file `~/.local/state/argus-ui/alerts/medusa-gameguard.json`. Both clear about a minute after the game closes.
- a backup is already running, the brain job is frozen (thaw it on Watch first), or there is no brain job.

While it runs, a ribbon of motes (`api.fx.motes`) flows from the server's copy into the filling bar (none with reduced motion).

**Never:** deleting snapshots, restoring, or showing what is inside a snapshot (they hold keys and passwords). The plugin lists names and sizes only, directly inside the one folder: no subfolders, no symlinks, nothing outside it, and nothing in a request can change which folder it reads.

## Home
Its line on Home: `Last snapshot 2 days ago · 3 on the server, 4.1 GB · off-site not yet` ("Backing up now · " in front while it runs). It goes to **Needs you** when the newest snapshot is older than 8 days (**Check backups**) or the last run failed (**Look at the failed backup**).

## Settings
Nothing is needed when the snapshots are in the only `~/.mnemosyne/<Server>-brain/` folder and there is one brain job. Otherwise, `~/.config/argus-ui/memory.json` (read on every refresh, all fields optional):
```json
{ "folder": "~/.mnemosyne/<Server>-brain", "unit": "mnemosyne-<server>-brain",
  "pc_marker": "~/.mnemosyne/last-backup.json", "note": "Jellyfin pauses for about a minute while the snapshot is made." }
```
Environment overrides for tests: `ARGUS_MEMORY_DIR` (the folder), `ARGUS_MEMORY_CONFIG`, `ARGUS_MNEMOSYNE` (where `<Server>-brain/` is looked for), `ARGUS_GAMEGUARD`, `ARGUS_ALERTS`, `ARGUS_SYSTEMCTL`.

### The PC's marker file
The PC's backup writes a small `last-backup.json` next to its archives, and a pull job on the server brings it to `pc_marker` (default `~/.mnemosyne/last-backup.json`):
```json
{ "at": "2026-11-08T03:12:00-07:00", "sets": 6, "bytes": 123456789 }
```
Only `at` (an ISO time) is read. Until that file arrives, *On the PC* says **Unknown**.

## Tests
- `tests/memory_test.py` (no browser, runs on Windows too): the three fixture snapshots and never the decoys (a text file, a name without a date, a folder named like a snapshot, a symlink to a file outside), the same sizes as the files, reading changes nothing, 3-2-1 with and without the marker and the off-site job, Home's line and *needs*, and Back up now: the exact command, the body ignored, refused while a game runs (either file), while running, frozen or missing.
- `tests/memory.test.js` (Playwright, through `tests/run.sh`): the page lists three snapshots, bar heights follow size, the hold works by keyboard (let go early sends nothing, refused while a game runs, then starts the job and a bar fills), Home's place, and 375 px with no sideways scroll.
- The fixture folder is `tests/fixtures/memory/Server-brain/`; `tests/run.sh` copies it into the throwaway HOME's `~/.mnemosyne/`.
