# Phone alerts

Elaia can make your phone buzz, also when Elaia is closed. It buzzes for exactly three kinds of thing, and you choose which
of them each phone gets:

| On the page | When | How urgent |
|---|---|---|
| **Something stopped working** | a program on the server stops doing its job and there is nothing Argus may do about it (`broke` events, `docs/checks.md`) | high: it may wake the phone; it waits up to 6 hours if the phone is off |
| **Something needs my yes** | Argus waits for you before it restarts something (`needs-yes`) | high, 6 hours |
| **Daily summary** | once a day, at 08:00 unless you set another time | normal; it waits up to 12 hours |

It never buzzes when Argus fixed something by itself, or when something came back on its own (`fixed`, `recovered`): that
stays on the page and goes into the next daily summary.

So that the phone never becomes noise:
- the same thing (same check, same kind) does not buzz again within **30 minutes**. If it keeps going wrong, the quiet
  time grows to 1 hour, 2 hours, then 4 hours, and it is back to 30 minutes once that thing has been quiet for 12 hours;
  nothing is lost: every event stays in the events file and in the daily summary;
- at most **6 buzzes per person in any hour**. What comes after that is not lost: it is folded into **one** later message,
  *"3 more things happened. Open Elaia."*, sent as soon as the hour has room again;
- a newer message about the same thing replaces one the phone has not shown yet, and on the phone a newer notification
  about the same thing replaces the older one instead of stacking.

Only **owners** get alerts (`docs/people.md`); a learner never sees the page. A phone turned on before there was a
people file keeps getting its alerts after one is written: it counts for the owners (with several owners, for all of
them), every owner sees it in his list and can remove it, and it becomes his own when that phone turns alerts on again.
A learner never sees or gets it.

On the lock screen a message that waits for you starts with **Needs your yes:** and the name of the thing (*Needs your
yes: Media player*); its first line then says what is wrong. A message that something stopped working keeps Argus's own
words. On a computer the same alerts show as notifications, and the page says *show an alert* instead of *buzz*.

## Turning it on (the owner, on the phone)

These are the steps as you will read them; nothing here needs a terminal.

1. On the phone, open Elaia **at its usual secure address** (the one that starts with `https`, through your home network's
   sign-in). In Chrome: tap the three dots **⋮**, then **Add to home screen** (it may say **Install app**). Open Elaia from
   the new icon.
2. Tap **More**, then **Phone alerts**. (On Today there is also one quiet line, *Your phone can buzz when something needs
   you*, with **Set up phone alerts**; **Not now** hides it for good on that phone.)
3. Tap **Turn on alerts on this phone**. The phone asks whether Elaia may send notifications: tap **Allow**.
4. Tap **Send a test buzz**. It should arrive within a few seconds, also when Elaia is closed. Below the button the page
   says when the last message was handed to the phone's message service, or what went wrong.
5. Choose with the three switches what this phone gets. Each switch changes at once.

On the same page: **Turn off on this phone**, and **Your other devices** with **Remove** for each. At most 8 devices per
person. On a computer the page is not in the strip of sections at the top (it would crowd it); open Elaia's address with
`phone` at the end (`<base>/phone`).

If the page says *Notifications are blocked for this page*, the phone said no earlier; the page lists the three taps that
allow them again. If it says *This browser cannot do it yet*, add Elaia to the home screen first (the page shows how).
If it says *Alerts can be turned on and tested only when Elaia is opened through its secure address*, the page was
opened another way (for example by the server's plain address): open it through the secure one.

## What leaves the server, and to whom

Only one thing, and only when something buzzes: **an encrypted message to the phone maker's push service** (for Chrome on
Android, Google's; the address is the one the phone's browser gave when you tapped Allow). The message is locked for that
one phone (RFC 8291): the push service carries it but **cannot read it**. It holds the event's title, a short body (at most
2,000 bytes in all), the place on the page it opens, its time and kind. The request is signed with the server's own key
(RFC 8292), so the push service knows it comes from the same server each time; the signature carries a contact address,
`mailto:elaia@example.invalid` unless you set another (a made-up address under the reserved name `.invalid`). <!-- private-ok -->

The server only ever calls a known push service: the address must be `https` with no port written out (so port 443),
and its host must be
`fcm.googleapis.com` or end in `.push.services.mozilla.com`, `.notify.windows.com` or `.push.apple.com`. Anything else is
refused when a phone is added and again before every message; a redirect is never followed. Nothing else about you, your
programs or your network is sent anywhere. In the clear, outside the encrypted part, the push service sees how long it may
hold the message, how urgent it is, and a topic made from the subject with a secret from the server's key (so it cannot
guess what the message is about; a newer message with the same topic replaces one the phone has not fetched yet).

Sending runs on its own thread with a small queue, so neither Argus's checks nor the page ever wait on the network (10
seconds per try). When the push service says the phone is gone (404 or 410), that device is removed. When it is busy or
does not answer (429, 5xx, no answer), Elaia tries once more a minute later and then shows the reason in plain words next
to the device.

## The daily summary

`server/summary.py`, its own small thread. Once a day at `ARGUS_SUMMARY_AT` (local time, default `08:00`) it makes ONE
`summary` event (it goes to the events file like every event, and buzzes the phones that want it). Its title is for a
tired person, its body at most three short sentences, from the events of the last 24 hours and Argus's checks as they are
now:

| A day like this | Title | Body |
|---|---|---|
| nothing happened | Yesterday: everything worked | Argus checked 3 things all day, and nothing stopped working. Nothing waits for you. |
| a repair you allowed | Yesterday: 1 thing stopped working, Argus fixed it | Argus restarted Media player as you allowed, and it works now. Nothing waits for you. |
| something waits | 1 thing is waiting for your yes | Media player needs a restart, and Argus waits for your yes. |

The date of the last summary is saved before the message is made, so a restart never sends a second one. If the server
was off at the set time, the summary goes out when it is back only within 4 hours after that time; later, that day has
none. `ARGUS_SUMMARY=0` turns it off.

## Files and settings

| What | Where (setting) | |
|---|---|---|
| The server's key pair | `~/.config/argus-ui/push-key.pem` (`ARGUS_PUSH_KEY`) | made on first need; mode 600; never logged, never in an answer |
| The devices | `~/.local/state/argus-ui/push-devices.json` (`ARGUS_PUSH_DEVICES`) | mode 600; `{id, person, label, endpoint, keys, kinds, made, last_ok, last_error}` |
| The last summary's date | `~/.local/state/argus-ui/summary.json` (`ARGUS_SUMMARY_STATE`) | |
| The contact in the signature | `ARGUS_PUSH_CONTACT` | `mailto:` or `https:`; default `mailto:elaia@example.invalid` <!-- private-ok --> |
| Summary time / off | `ARGUS_SUMMARY_AT` (`08:00`), `ARGUS_SUMMARY=0` | |

Both secret files are written through a temporary file in the same folder and renamed, readable by the server's user only.
A device's address (`endpoint`) works like a secret: it is never written to a log and never sent back to the page. The page
tells which device is itself by a checksum of its own address (`id`).

Phone alerts need the Python package `cryptography` on the server (many Linux systems have it already; otherwise install
the system's `python3-cryptography` package). Check with `python3 -c "import cryptography"`. Without it, the Phone alerts page says *Phone alerts are not available on this server*
with the reason, and everything else works as before.

Routes (all the owner's, `docs/people.md`): `GET api/push/status` (available or why not; your devices without their
addresses; the public key the browser needs), `POST api/push/subscribe`, `api/push/kinds`, `api/push/forget`,
`api/push/test` (one test message to one device, at most one per 10 seconds). Turning on and testing also need a trusted
request: one that came through the secure front door with a sign-in, and not from the server itself.

## Turning it off

- One phone: **Turn off on this phone** on the page, or **Remove** it from another device.
- Everything: remove every device on the page. With no devices nothing is ever sent.
- The daily summary only: `ARGUS_SUMMARY=0` in the service's settings, then restart Elaia.

## Starting over (throw the key away)

If you think the key or the devices file got out, or a phone stopped getting alerts and turning them off and on did not
help:

1. On the server, move both files aside to dated names (never delete them right away):
   `mv ~/.config/argus-ui/push-key.pem ~/.config/argus-ui/push-key.pem.set-aside-$(date +%Y%m%d-%H%M)` and the same for
   `~/.local/state/argus-ui/push-devices.json`.
2. Restart Elaia. A new key is made the next time the page asks.
3. On each phone: open **Phone alerts**, tap **Turn off on this phone** if it still says on, then **Turn on alerts on this
   phone** again. Phones signed up with the old key get nothing more.

## For developers

`server/push.py` (encryption RFC 8291 `aes128gcm`, VAPID RFC 8292 ES256, the host rule, the devices file, the sender
thread, the sink registered with `notify.register()`, the routes' logic), `server/summary.py`, `web/sw.js` (`push`: always
shows a notification, `tag` = what it is about, the existing `static/argus-192.png` as its icon, no badge;
`notificationclick`: focuses an open Elaia window and sends it to the place, or opens one), `web/js/alerts.js` and
`web/css/alerts.css` (the page and Today's line).

Tests: `tests/push_test.py` (RFC 8291 Appendix A to the byte, a round trip decrypted as a browser does, the VAPID token
verified, the host rule, a fake push service on `127.0.0.1`: 201, 410, 500 then 201, 429 twice, a timeout, a redirect not
followed; the sink's rules; the summary's words, once a day across a restart, the 4-hour rule; the routes for owner,
learner and untrusted requests, no address or key in any answer, mode 600 on Linux). `tests/phone-alerts.test.js` (the
page's states, one call per switch, 44 px, 360 px, computed contrast, a learner has no way in, the test buzz decrypted as
a phone would; the service worker in Chromium: a push message delivered with Chromium's own hook shows a notification and
a tap opens the right place). `ARGUS_PUSH_TEST_ORIGIN` lets the tests use their fake push service; it is honoured only
together with `ARGUS_DEV=1` and only for an `http` address on the same machine. `bash tests/run.sh phone-alerts`.
