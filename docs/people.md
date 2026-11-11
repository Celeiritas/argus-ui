# People: who may use the page

Elaia can be used by more than one person, each from their own phone or computer, each with their own Tailscale sign-in.
The server finds out who is asking and refuses what is not theirs. This page is for the owner: what the people file is,
how to check who the server thinks you are, what each role can do, and what to do when you are locked out.

## How the server knows who is asking

The page listens on this machine only (`127.0.0.1`). Other devices reach it through `tailscale serve`, which adds a line
to every request it passes on: `Tailscale-User-Login`, the Tailscale login of the person whose device sent it. Serve
removes any copy a device sends itself, so through Serve that line is true.

But any program on the server could connect to the page's port directly and write that line itself. So the server
believes it **only when the connection really comes from Serve**: it asks the kernel which user owns the other end of the
connection (the tables `/proc/net/tcp` and `/proc/net/tcp6`, readable without sudo) and accepts the login only when that
user is the one Serve runs as. That is user id `0` (root, where `tailscaled` runs) unless `ARGUS_SERVE_UID` says otherwise.
Anything else (another program, a machine without `/proc`, a closed connection) means the request has **no identity**.

There is no setting that hands out a role directly.

## Check who the server thinks you are

Open `<base>/api/whoami` (for example `https://<server>.<tailnet>.ts.net/argus/api/whoami`). Anyone may open it. It answers:

```json
{"login": "owner@example.com", "trusted": true, "through_serve": true,
 "person": "owner-one", "name": "Owner One", "role": "owner", "problem": null}
```

- `login`: the Tailscale login the request carried, or `null`.
- `trusted`: `true` only when it came through Serve (see above). An untrusted login counts for nothing.
- `through_serve`: the connection came from Serve (a tagged device comes through Serve without a login).
- `person`, `name`, `role`: who you are to the page.
- `problem`: a sentence when the people file cannot be used (shown to an owner only), else `null`.

**Do this before you write the people file.** If `trusted` is `false` for your own phone, writing the file would lock you
out; tell whoever set up the server (see *Locked out* below).

## The people file

One file on the server, never in git: `~/.config/argus-ui/people.json` (`ARGUS_PEOPLE` gives another path).

```json
{"people": [
  {"id": "owner-one",   "name": "Owner One",   "role": "owner",   "logins": ["owner@example.com"]},
  {"id": "learner-two", "name": "Learner Two", "role": "learner", "logins": ["learner@example.com"]}
]}
```

- `name`: shown on the page. `id` is optional: without it, the name in lower case with every run of other characters
  turned into one `-` ("Learner Two" becomes `learner-two`). Mentor keeps each person's progress under this id.
- `role`: `owner` or `learner`. Two owners are fine.
- `logins`: the Tailscale logins of that person (as `api/whoami` shows them). Upper and lower case do not matter.
- The server reads the file again whenever it changes: adding a person needs no restart.

**No file:** everyone the tailnet lets in is the owner, called "You", exactly as before people existed.

**A file the server cannot use** is one that is not JSON, has no `people` list, has an entry without a name, with a role
other than `owner` or `learner`, or with `logins` that are not a list of names, uses one `id` twice, lists **one login under
two people**, or **names no owner**. Strict on purpose: a typo must never quietly change what someone may do.
- If the file **was read correctly before** (since the server started), the server keeps that last good copy, writes one
  line in its log, and tells the owner on the page (`people_problem` in the page's state, `problem` in `api/whoami`).
- If it **never read correctly** (broken when the server started, or when the file first appeared), the page is shown as if
  there were no file, and **every change is refused** (every POST answers `503` with the sentence) until it is fixed.
- Deleting the file is the way back to "no file".

## What each role can do

Everything is the owner's unless it is listed as open below.

| | owner | learner | no role |
|---|---|---|---|
| The page itself, its files (`static/`, `sw.js`, the app manifest) | yes | yes (a place that is not hers sends her to Today) | the small private page |
| `api/health`, `api/whoami` | yes | yes | yes |
| `api/state` | everything | her role, name and the places she may open only: no tasks, alerts, links, watch rows | refused |
| `api/sky` (weather) | yes | yes | refused |
| Program logs (`api/log/...`), Freeze, Thaw, Restart, Run | yes | refused | refused |
| A plugin's `api/<id>/<path>` | yes | only paths its `plugin.json` opens to learners (`"roles"`, docs/leafy-plugin.md) | refused |
| A plugin's files (`plugins/<id>/...`) | yes | only a server plugin that opens at least one path to learners | the small private page |
| A static plugin (a game in a frame) | yes | refused | the small private page |

The table as the tests find it is in `tests/gate_test.py` (`ROLE_TABLE=<file> python3 tests/gate_test.py` writes it out).

**Who has no role:** with a people file, a trusted login that is not listed, and any request without a trusted login.

## When the page says no

- An address of the page opened by someone without a role gets one small page: that the page is private, which Tailscale
  login the server saw (or that the request did not come through Tailscale), that the owner can add that login, and a
  link to `api/whoami`.
- A refused `api/...` call answers `403` with `{"error": "<one plain sentence>"}` (also as `msg`, which the page shows).
- A learner who opens an owner's address gets the normal page; the page itself sends her to Today, and the data behind
  the owner's places is refused.

## Locked out

You open the page and get "This page is private".
1. Read the login it shows. If it is yours but spelt differently from the file, fix `logins` in the file. No restart needed.
2. If it says the request did not come through Tailscale although you use the tailnet address, the server does not
   recognise Serve's connections (`trusted` is `false` in `api/whoami`). Move the people file aside on the server
   (`mv ~/.config/argus-ui/people.json ~/.config/argus-ui/people.json.set-aside`): with no file you are the owner again.
   Then find which user Serve's connections come from (`ss -tnpe state established dport = :<port>` shows `uid:` per
   connection) and set `ARGUS_SERVE_UID` in the service's drop-in.
3. Always possible over ssh: moving the file aside brings back the page as it was before people existed.

## For plugins

A server plugin gets `who = {"person", "name", "role"}` as a fourth parameter on every call if its `get` / `post` takes
one, and declares which paths a learner may call in `plugin.json`. See *Roles and who* in `docs/leafy-plugin.md`.
