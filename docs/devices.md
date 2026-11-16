# Devices

Argus watches more than tasks: the **Devices** panel on Watch lists the owner's own devices (`{{SERVER}}`, `{{PC}}`, `{{PHONE}}` and the rest) and says whether each one is on. Today has one short line with the counts that opens the list. Both are the owner's only, and both show only what the host's `devices.json` lists.

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
| `kind` | `pc`, `laptop`, `server`, `phone`, `tablet`, `console` or `other` (the default). Only the small word under the name. |
| `probe` | How Argus tells whether it is on: `self` (this machine, the server Argus runs on; at most one), `tailscale` (the peer called `host` in `tailscale status --json`) or `none` (Argus does not check it; it always shows *Can't tell*). |
| `host` | For `tailscale`: the device's host name as `tailscale status` shows it (the first part of its MagicDNS name, or its machine name), letters, digits and `-` only, at most 63. Case does not count. Not a full `*.ts.net` name. |
| `wake` | Optional. **The place for Wake on LAN later**: `{"mac": "<six pairs of hex digits, split by : or ->"}`. Nothing uses it yet and there is no Wake button. The page only learns that a device has it (`"wake": true`), never the address. |

- **No file**: the Devices panel on Watch says *No devices listed yet* with a link here, and Today has no line. Nothing is asked of Tailscale.
- **A bad file** (not JSON, a rule above broken, larger than 64 KB): the panel says *The device list could not be read* and what is wrong, Today has no line, and the server log (`journalctl --user -u argus-ui`) gets one line, once each time the file changes. Argus keeps running.
- The file is read again when it changes (its modification time or size), so an edit needs no restart.

## The statuses
A small fixed set. Each status is a **word on a badge** in its own colour, never colour alone.

| Status | Word on the badge | When |
|---|---|---|
| online | Online | Tailscale says the peer is online; or `self` when Desktop / Game mode is off or does not know. |
| offline | Offline | Tailscale says the peer is offline. The row adds *last seen 3 hours ago* (the exact time on hover) when Tailscale knows it. |
| unknown | Can't tell | Argus cannot tell, and the row says why: *Tailscale is not installed on this machine*, *Tailscale gave an error*, *Tailscale did not answer in time*, *Tailscale gave an answer Argus could not read*, *Tailscale is not running here*, *Not on the Tailscale list*, *Tailscale did not say*, *Argus does not check this one*. |
| desktop | Desktop mode | `self`, while the server is in its Desktop mode ([modes.md](modes.md)). |
| game | Game mode | `self`, while the server is in its Game mode. The label is the mode's own label from `modes.json` plus "mode". |

**Never "offline" by guess.** When Tailscale is missing, fails, hangs or is stopped, every `tailscale` device is *Can't tell*, not *Offline*: a device is offline only when Tailscale itself says so.

Today's line counts three of them: *online* (Desktop and Game count as online), *offline* and *can't tell*, each with a dot in its colour and the number and word kept together; a count of nought is left out. The whole line is one link to `Watch#devices`.

## The probe
- **One call for every device**: `tailscale status --json` (or the binary in `ARGUS_TAILSCALE`), run as a fixed argument list without a shell. Nothing from the file goes into the command; host names are only compared with Tailscale's answer.
- A 5-second timeout. The answer is cached for 30 seconds (`ARGUS_DEVICES_CACHE`, 0 to 300). **Check again** in the panel asks Tailscale again when its last answer is more than 5 seconds old, so holding the key cannot run it many times a second.
- A peer is found by the first part of its `DNSName`, then by its `HostName`, case folded. A device whose host is the server's own Tailscale name counts as this machine (*Online*).
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
| `--dev-unknown` | `var(--frost)` #8C99A6, as a dashed ring with no fill (the words are `--snow` on the panel) | – |

## Tests
`tests/devices_test.py` (no browser: every rule of the file, each status against a stand-in `tailscale` (`tests/fixtures/fake_tailscale.py` with the canned answer `tests/fixtures/devices/tailscale-status.json`), each way the probe can fail, one call cached, Check again's 5 seconds, this machine's mode, and `GET api/devices` for the owner, with no file and for a learner). `tests/devices.test.js` (the page: the empty state, every status with its word and colour, 44 px rows, the keyboard, 375 / 412 px with no sideways scroll, Today's counts and its link, Game mode, Tailscale failing, a broken file, a learner). `tests/run.sh` starts the shared server with `ARGUS_DEVICES` pointing at a file only `devices.test.js` writes, so the other checks see no device list.
