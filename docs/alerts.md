# Alert files

Any agent can make Argus glare without a failed systemd unit. For example, Hermes can say "1 delivery quarantined", or Zeus can say "the deploy could not be started". The agent writes one small JSON file. Argus reads the folder on every refresh (the page refreshes every 15 seconds), so no extra process runs. The alert ends when the file is gone.

## The file
`~/.local/state/argus-ui/alerts/<agent>.json`. The folder can be changed with `ARGUS_ALERTS` or the theme's `alerts`. Use one file per agent (or per cause) and write it atomically: write a `.tmp` file, then rename it.
```json
{ "job": "hermes-door", "level": "alert", "since": "2026-10-21T09:05:00-06:00",
  "message": "1 delivery quarantined: .exe files are never allowed", "link": "delivery" }
```
| Field | Required | Meaning |
|---|---|---|
| `job` | yes | The task it belongs to, named like a task: an agent key, a dash, then the rest (`hermes-door`, `zeus-approve`). |
| `level` | yes | `alert`: Argus glares and the alert counts in his badge like a failed task. `warn`: the message shows on the card only. |
| `message` | yes | One plain sentence: what happened, and what to do if that isn't obvious. Up to 300 characters are shown. Use `{{SERVER}}`-style placeholders, never real names. |
| `since` | no | ISO time. The card says "since 9:05 AM" (or the date). |
| `link` | no | A section id (an agent, `olympus` or a plugin id such as `throne`). The card gets "Open <section>". A link to a section that isn't installed is dropped, but the alert still shows. |

## What Argus shows
- **The task's card** shows the message: "Alert:" in red or "Warning:" in gold, with a red or gold edge. A per-run unit's alert can name the base card (`zeus-deploy`).
- **An alert for a job with no card** (such as `zeus-approve`, which is not a unit) gets a card of its own at the top of its agent's section. That card can't be frozen or run.
- `alert` level: Argus glares, the badge and the Watch pill's dot count it, his label reads it out ("1 alert: hermes-door, 1 delivery quarantined …"), and the agent's section header counts "1 alert". The short chime plays when the count goes up.
- **Removing the file** calms him on the next refresh.

## Malformed files
A file that isn't a JSON object, or has no message, an unknown `level` or a `job` that isn't an agent's task name, is ignored. The server log (`journalctl --user -u argus-ui`) gets one line per file version, `argus-ui: ignored alert file <name>: <why>`, and not one on every refresh. Argus never glares at a broken file.

## Who writes them
| Agent | File | When |
|---|---|---|
| Hermes | `hermes.json` (`hermes-door`) | a delivery is quarantined; Seen on the Delivery page clears it |
| Janus | `janus.json` (`janus-map`) | a door that should be open closed unexpectedly |
| Zeus | `zeus.json` (`zeus-approve`, `zeus-deploy`) | Janus couldn't verify an approval, or a deploy failed or couldn't start; `zeus seen` or the next good deploy clears it |
