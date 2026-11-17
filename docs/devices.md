# Devices

Argus watches more than tasks: the **Devices** panel on Watch (after the task groups, before *What happened lately*) lists the owner's own devices (`{{SERVER}}`, `{{PC}}`, `{{PHONE}}` and the rest) and says whether each one is on. Today has one short line with the counts that opens the list. Both are the owner's only, and both show only what the host's `devices.json` lists.

## The file
`~/.config/argus-ui/devices.json` on the host (or the path in `ARGUS_DEVICES`). It names your devices, so it lives on the host and never in git.
```json
{"devices": [
  {"name": "{{SERVER}}", "kind": "server", "probe": "self"},
  {"name": "{{PC}}",     "kind": "pc",     "probe": "tailscale", "host": "<tailscale host name>", "wake": {"mac": "<aa:bb:cc:dd:ee:ff>"}},
  {"name": "{{PHONE}}",  "kind": "phone",  "probe": "tailscale", "host": "<tailscale host name>"}
]}
```
| Field | Meaning |
|---|---|
| `devices` | At most 24, in the order the list shows them. |
| `name` | What the list calls it, 1 to 40 characters. No two the same (case does not count). |
| `kind` | `pc`, `laptop`, `server`, `phone`, `tablet`, `console` or `other` (the default). Only the small word under the name, and left out when the name already says it (*{{PHONE}} Phone* is just *{{PHONE}}*). |
| `probe` | How Argus tells whether it is on: `self` (this machine, the server Argus runs on; at most one), `tailscale` (the peer called `host` in `tailscale status --json`) or `none` (Argus does not check it; it always shows *Can't tell*). |
| `host` | For `tailscale`: the device's host name as `tailscale status` shows it (the first part of its MagicDNS name, or its machine name), letters, digits and `-` only, at most 63. Case does not count. Not a full `*.ts.net` name. |
| `wake` | Optional. **The place for Wake on LAN later**: `{"mac": "<six pairs of hex digits, split by : or ->"}`. Nothing uses it yet and there is no Wake button. The page only learns that a device has it (`"wake": true`), never the address. |

- **No file**: the Devices panel on Watch says *No devices listed yet* with a link here, and Today has no line. Nothing is asked of Tailscale.
- **A bad file** (not JSON, a rule above broken, larger than 64 KB): the panel says *The device list could not be read*, what is wrong and where (*Fix device 2 in devices.json on the server*: the file's own name, as `ARGUS_DEVICES` may name another, and the device's number when one device is wrong), Today has no line, and the server log (`journalctl --user -u argus-ui`) gets one line, once each time the file changes. Argus keeps running.
- The file is read again when it changes (its modification time or size), so an edit needs no restart.

## The statuses
A small fixed set. Each status is a **word on a badge** in its own colour, never colour alone.

| Status | Word on the badge | When |
|---|---|---|
| online | Online | Tailscale says the peer is online; or `self` when Desktop / Game mode is off or does not know. |
| offline | Offline | Tailscale says the peer is offline. The row adds *last seen 3 hours ago (Sun, Nov 15, 9:04 PM)* when Tailscale knows it: the exact time is in the row's text, for a phone and the keyboard too. |
| unknown | Can't tell | Argus cannot tell, and the row says why: *Not on the Tailscale list*, *Two machines on the Tailscale list have this name*, *Another machine on Tailscale has this name and is online: remove the old entry* (see below), *Tailscale did not say*, *Argus does not check this one*. When Tailscale itself cannot be asked, the reason is said once, above the list (*Tailscale gave an error, so Argus can't tell which devices are on right now*), the rows say only *Can't tell*, and the time under the list says *Tried 8:28 AM*, not *Checked*. The reasons said above the list: *Tailscale is not installed on this machine*, *Tailscale gave an error*, *Tailscale did not answer in time*, *Tailscale gave an answer too large to read*, *Tailscale gave an answer Argus could not read*, *Tailscale is not running here*. |
| desktop | Desktop mode | `self`, while the server is in its Desktop mode ([modes.md](modes.md)). |
| game | Game mode | `self`, while the server is in its Game mode. The label is the mode's own label from `modes.json` plus "mode" (not added when the label already ends with it). The colour is the one the mode pill gives that mode (`modeHues()` in `core.js`): an id `desktop` or `game` keeps its own, one other id gets the colour left over, two other ids are green then purple. |

**Never "offline" by guess.** When Tailscale is missing, fails, hangs or is stopped, every `tailscale` device is *Can't tell*, not *Offline*: a device is offline only when Tailscale itself says so.

**A machine added to Tailscale again** (reinstalled, or signed in afresh) leaves its old entry behind: the old one keeps the DNS name `<host>` and goes offline, the new one is `<host>-1` with the same machine name. Argus matches `<host>` to the old entry, so when that entry is offline while another machine with the same machine name is online, the row says *Can't tell* and *Another machine on Tailscale has this name and is online: remove the old entry*, never an *Offline* that may be wrong. Remove the old machine in the Tailscale admin console (or set `host` to `<host>-1`). When both are offline the row stays *Offline*.

Today's line (14 px, like Today's other lines) counts three of them: *online* (Desktop and Game count as online), *offline* and *can't tell*, each with a dot in its colour (for *can't tell* a small solid *?*) and the number and word kept together; a count of nought is left out. The whole line is one link to `Watch#devices`, named for a screen reader as *Devices: 3 online, 1 offline, 3 can't tell. Open the list*. When the page could not reach the server, the line says *Could not reach the server* instead of counts that may be old. Edit Today leaves the line alone, and it still shows when every tile is hidden.

## The probe
- **One call for every device**: `tailscale status --json` (or the binary in `ARGUS_TAILSCALE`), run as a fixed argument list without a shell. Nothing from the file goes into the command; host names are only compared with Tailscale's answer.
- A 5-second timeout. The answer is cached for 30 seconds (`ARGUS_DEVICES_CACHE`, 0 to 300). **Check again** in the panel asks Tailscale again when its last answer is more than 5 seconds old, so holding the key cannot run it many times a second. Pressed while the page's own background ask is still running, it waits for that ask and then checks again. Its result is said by a screen reader (a polite live region), and the keyboard stays on it through the page's 15-second refresh. The page asks the server at most every 10 seconds after its last answer, and gives up a request after 12 seconds.
- A device's `host` is matched in passes, so the answer never depends on the order Tailscale lists its peers: first the first part of the `DNSName` of every machine in your own tailnet (the server's own included; Tailscale keeps these unique, adding `-1` to a machine added again), then that of every machine shared in from another tailnet (so someone's shared `desk` never hides your own `desk`; your tailnet is Tailscale's `MagicDNSSuffix`, else the server's own DNS name without its first part), then the `HostName` of each machine that no DNS name took, case folded. A machine shared in from another tailnet never counts as your machine added again. A name two machines claim in the same pass (two phones both called `localhost`) is *Can't tell* (*Two machines on the Tailscale list have this name*), never either one's status: give that device its DNS name instead. A device whose host is the server's own Tailscale name counts as this machine (*Online*).
- At most 4 MB of Tailscale's answer is read, held to while reading: a larger answer stops the command at once and is *Can't tell*.
- When the list itself cannot be made (a bug, not the file), the panel says *Argus could not read the device list* and the server log gets the real error with its traceback, once for each different error.
- The page asks `GET api/devices` at most every 10 seconds while Watch or Today is open.

## Who sees it
The owner only. `api/devices` is not on the learner list in the server's role check, so a learner gets 403; her page never asks for it, Today shows her no line and Watch is not one of her places. The answer carries names, kinds and statuses, never a host name or a MAC address.

## The colours
`web/css/argus.css`, one line under `:root`, one custom property per status. Each fills its badge under white words (`--mode-ink`) and its dot on Today; a lightened edge of the same colour goes round both. Change one value to recolour one status.

| Token | Default | White words on it |
|---|---|---|
| `--dev-online` | `var(--mode-desktop)` #287043 (the pill's green) | 6.0:1 |
| `--dev-desktop` | `var(--mode-desktop)` #287043 | 6.0:1 |
| `--dev-game` | `var(--mode-game)` #6B46C1 (the pill's purple) | 6.4:1 |
| `--dev-offline` | #4F5A65 (slate) | 7.0:1 |
| `--dev-unknown` | `var(--frost)` #8C99A6: no fill, a ring and a small solid *?* before the words (the words are `--snow` on the panel; the *?* is `--night` on frost) | – |

## Tests
`tests/devices_test.py` (no browser: every rule of the file, each status against a stand-in `tailscale` (`tests/fixtures/fake_tailscale.py` with the canned answer `tests/fixtures/devices/tailscale-status.json`), each way the probe can fail, one call cached, Check again's 5 seconds, this machine's mode, and `GET api/devices` for the owner, with no file and for a learner). `tests/devices.test.js` (the page: the empty state, every status with its word and colour, 44 px rows, the keyboard, 375 / 412 px with no sideways scroll, Today's counts and its link, Game mode, Tailscale failing, a broken file, a learner). `tests/run.sh` starts the shared server with `ARGUS_DEVICES` pointing at a file only `devices.test.js` writes, so the other checks see no device list.
