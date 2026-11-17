# Today (once called Home)

Today answers **"does anything need me, and where do I go?"** in a few seconds, on a phone, with one thumb. It is what LeafyGrove
opens on: the bare address `<base>/`, and `<base>/home`, its old address, which keeps working. It is about *you*. Watch
(Argus's section, `<base>/argus`) is about *the machines*: "is every task running?".

## What it shows, top to bottom
1. **The header**: the page's name, LeafyGrove, and under it a greeting by the viewer's clock, the date and the weather
   ("Good evening · Friday, October 23 · Light rain · 48°F"). On a narrow phone it wraps onto a second line rather than being
   cut off (4.44.0). This is Today's only weather: the strip's weather (on every other page) is hidden here (4.44.0).
   Above the list, for the owner, **the server's own line on what it is doing now** (4.44.0, below), a band across Today in
   the server's own colours (4.45.0).
   Under it, for the owner and only when the host lists devices, **one line with the devices' counts** (*Devices · 3 online
   · 1 offline · 2 can't tell*, 4.51.0), each count with a dot in its status's colour; the line opens Argus's Devices panel on
   Watch ([devices.md](devices.md)).
2. **One line that says the state in words**: *Nothing needs you*, *1 thing needs you*, *3 things need you*, or *Asking every
   section…* while the sections are still answering. It counts what the bar counts: every task in trouble, every alert, and
   each section that needs you (its `count`, else one), never a quiet section or a task marked known ("Quiet", below). A
   learner sees "The realm is quiet." under it when nothing needs her.
   It is the heading of the list:
3. **The rows that need you**, the failed thing first. Each row has the place's mark, who it is from (the god's name and only
   that, e.g. *Zeus*; for a task or an alert, whose it is and where: *Hermes · Argus*, 4.45.0), one sentence, and one
   verb-first button that goes there:
   - **one row per broken thing on Argus** (4.40.0, see "Trouble first" below): a program that runs but cannot do its job,
     a check with no task card of its own (a media program, a drive), a failed task, each with the same three plain lines as on
     Argus's page and, when checks.json declares a fix, the same press-and-hold button (**Restart Jellyfin**) beside **Open
     Argus**. A failed task's row also has **Mark as known** (the owner's; "Quiet", below)
   - every `alert`-level alert (docs/alerts.md) that is not about one of those: whose it is ("Hermes · Argus"), its message,
     and "Open <section>" when it links to one, else "Open Argus" (Argus's page showing that agent's tasks)
   - every server plugin whose status says it needs you: its line → its `action` ("Review argus-ui 4.15.0"); never a quiet one

   A row whose need is met **fades out** where it stood (200 ms, hidden from screen readers while it goes); a row that is new
   since the last draw slides in. Under reduced motion both just happen. Warnings stay on their cards on Argus's page.
4. **One line per section with news** (4.54.0; the phone's quiet lines of 4.52.0, now at every width), under the heading
   *Sections*: a shown section (Edit Today's Sections list) whose server status has a line and that has no row above, e.g.
   *Mentor · 6 cards due*. Its mark, its name (16 px, 600), its line (14 px) and a chevron at the end, which says the line
   goes somewhere (visual review item 12); the whole line is one link, at least 44 px, and a screen reader hears its name and
   its whole line. **One place for each fact** (4.44.0): a section with a row above has no line until that row is gone.
   Argus (its news is the rows), Olympus and static plugins have no line. No line left, no heading.

**No Open list, no Sections tiles, no Edit Today on Today** (4.54.0, the owner's decisions of 2026-11-16, "One way to each
place" below): the bars reach every section, More holds the media players, the other pages and Edit Today. Today has one
reading column at every width (at most 880 px), so a computer reads the same as a phone.

**What needs you, in order of what it costs to leave it** (4.54.0, `needRank()` in `web/js/home.js`, a stable sort): what
broke and every alert first, then Mnemosyne (data: a backup with no copy outside the home), then Zeus (a deploy waiting for a
yes), then everything else (a skipped workout, a meal). Within a rank the bar's order. A row's text is its first sentence at
16 px and the rest under it at 14 px (`.ndetail`, visual review item 5), so a long backup line is quick to scan.

## On a phone (4.52.0)
Below 600 px wide (the width where the bottom bar shows, `PHONE` in `core.js`) Today and Watch are drawn in the owner's order
of what matters, so Today fits one screen and Watch stays short when all is well (the owner, 2026-11-16: less scrolling,
a visual hierarchy by his priorities). Wider screens keep the layout above.

**Today**, top to bottom:
1. **The header** on two short lines: the name with the Desktop/Game switch beside it; the short date and the weather under it.
   Argus sits at 56 px beside both.
2. **What needs you**, first, framed red when something broke, on a solid card (the scene does not show through it). A
   broken task's red bar sits in the card's own padding, so every row's picture and words start on the same line. When nothing
   needs you, one band carries both *Nothing needs you* and, on the line under it, the server's line (`.needs.calm`, no leading
   dot), so the calm state costs one band.
3. **The devices line.**
4. **One line per section with news**, as on every width (above).

Edit Today, the media players and the links are in More (the bottom bar's last slot), not on Today (4.54.0).

**Watch** (the All view; a single group's page is unchanged):
1. Anything broken, as before.
2. **Devices**, before the groups.
3. **Groups**: a group whose tasks all work is one line (*All well · 4 tasks · 1 running*, plus checks, frozen and known
   counts) that opens its own page. A group with a failure, a task with an alert, or a message of its own stays open. On the
   phone All view the folded groups' cards are not there to drop a power on; their own pages have them.
4. **What happened lately**: the three newest, then *Show more* / *Show fewer* (`aria-expanded`; it stays open across the 15 s
   redraw). Hidden when there are three or fewer.

Argus's marker for something broken that is out of view (*See what needs a look*, above) sits bottom centre on a phone, just
above the bottom bar, in thumb reach; it moves up only to clear a control, so it never covers a task's state pill or buttons.

Crossing the width (turning a tablet, narrowing a window) draws the page again.

## One way to each place (4.54.0)
The owner's decisions (2026-11-16) replace *Sections or Open* (4.45.0): **the bars go places, Today says what needs you.**
- **Sections** are on the bars: the phone's bottom bar has Today, Argus, Mentor, Zeus and More; the computer's top bar has
  every section that fits. A section's news is one line on Today (above); there are no tiles.
- **A section that opens elsewhere** (a studio on the same machine, served by its own program) is a section like the others,
  set in `links.json` with `"section": true` ("Links to other pages", below). On the computer it is a pill on the top bar,
  right after Zeus, with the opens-elsewhere mark (`LINK_MARK`) and read out as "…, opens another page"; on a narrow strip it
  stays on the bar while the later sections fold into More. On a phone it is the last row of More's sections. It never takes the bar's "you are here" (it leaves
  LeafyGrove). Its name is `links.json`'s `name` (or the owner's name for it in Edit Today); the repository never holds it.
- **More**, top to bottom (`#moreSheet`, `drawMore()` in `web/js/core.js`):
  1. the sections the bar leaves out (a phone: every one but Today, Argus, Mentor and Zeus; a computer: the pills folded off
     the strip), each with its mark, its name, its live line (12 px; `placeLine()`: "All 6 tasks well · 1 known", a status
     line, a version) and its count when it needs you (gold; red on Argus);
  2. **Media**: Jellyfin and Audiobookshelf (`media.json`; never on the top bar; a section of their own, like Mealie, is not
     repeated here);
  3. **Other pages**: the `links.json` entries that are not sections;
  4. **Settings**: Phone alerts, Mute sounds (a phone; the strip has its own on a computer) and Edit Today (the owner's).
  An empty part has no heading. Esc, Close or a tap outside gives focus back to More.
- **An integration** (a recipe app, a workout log) is a section when LeafyGrove reads from it, through status v2 (below);
  Mealie is the first (4.53.0, docs/mealie.md). Its own site is in Media when `media.json` names it, never twice.

## What the server is doing now (4.44.0)
One line above the list, in a band of its own across Today (not a row of the list), for the owner only, written by the server
(`now_line()` in `server/argus_ui.py`) from what it already knows, never a guess. One colon, after the name:
- **`<name>: calm`**: nothing below is true.
- **`<name>: busy with Hermes media and Zeus deploy`**: a task's run is in progress, a timer's run or one run of a transient
  job (a deploy). A service that is always on is not "busy". With the watch restarting a program: *restarting Jellyfin*. More
  than three: the first three *and 2 more*. A run is named as Watch names its task (agent and task name).
- **`<name>: a game is running, the local AI is paused`**: Medusa's game guard says a game runs (its record
  `~/.local/state/medusa-gameguard/frozen-by-me.json` lists what it paused, or its alert file is there; docs/memory.md). The
  tasks it paused are named in plain words: a task ending in `ollama` is *the local AI*, any other its agent and name.
- Together, in this order and parted by semicolons: *a game is running, the local AI is paused; busy with Hermes media;
  restarting Jellyfin*.

`<name>` is the server's own name, `SERVER` in `~/.config/leafy/realm.json` (`LEAFY_REALM`; the same file Mentor fills
`{{SERVER}}` from, docs/mentor.md), at most 40 characters; without the file or the key it says *The server*. The repository never
holds the name. The game guard's record path can be moved with `ARGUS_GAMEGUARD`.

**The band (4.45.0)** spans Today's column, lined up with the panels under it, 16 px under it to the first. The name is
drawn in the name colour at 600, the words after it in the words colour at 400, 16 px, on the band's background with a
1 px border. It is not a button and does not move. The server sends the name it used as `now_name` beside `now`; the page
colours the name only when `now` starts with exactly `<now_name>: `, otherwise (a learner, an older server) it draws the
line plain in the words colour. The colours are the theme's (`"colors"` in `theme.json`, docs/themes.md): the Leafy Realm
theme uses the server's own purple and green, background `#3a2a5e`, border `#5b4a85`, name `#7bd88f` (7.21:1 on the
background), words `#cbb8ff` (7.08:1). A theme without colours gets the page's neutral panel colours (name 12.19:1, words
7.00:1 on `--card`).

## Films, shows, audiobooks and recipes (4.44.0; Mealie 4.48.0)
The media players' own pages, and Mealie's recipes, (they are other sites, not LeafyGrove sections) are listed when the host
says where they are, in `~/.config/argus-ui/media.json` (or `ARGUS_MEDIA`), read on every refresh (since 4.54.0 they are
in More under **Media**, not on Today, "One way to each place" above):
```json
{"jellyfin": "http://<host>:<port>/", "audiobookshelf": "http://<host>:<port>/", "mealie": "http://<host>:<port>/"}
```
Only these three keys count (any case); each must be an `http://` or `https://` address, at most 300 characters, with no
spaces or quotes (a player on the tailnet or the home network is often plain http). Anything else, a broken file or no file:
no chip. They show as **Jellyfin · Films and shows**, **Audiobookshelf · Audiobooks and podcasts** and **Mealie · Recipes**
(a plain service: no agent's name on it), plain links with
`rel="noopener noreferrer"` (no referrer, no hold on LeafyGrove's window), for the owner only. Keep the file on the host; never
commit it. They are in More, never on the strip. Mealie's address is not listed under Media: Mealie is a section.
The `mealie` address also links each recipe in the Mealie section to its page in Mealie (docs/mealie.md).

## A section's card: status v2
`GET api/<id>/status` → `{"line": "…", "needs": true, "action": "Study 5 due cards"}`. `line` is required for anything to show;
`needs` (only `true` counts) puts the plugin in the rows and gives it a mark in the bar; `action` is the button's label,
verb-first, at most 32 characters, and defaults to "Open <name>"; the server cuts a longer `action` (32) or `line` (160)
after the last whole word, with "…" (`clip()`, 4.45.0; before, it cut inside a word). LeafyGrove passes on only these three fields and never errors
(`{"line": null}` when a plugin has nothing or fails). A plugin that answers only `{"line"}` keeps working and simply never
needs you. **A new section (workouts, meals, music) gets its line on Today by answering this, nothing else.** Mentor answers
`needs` when cards are due; Memory (docs/memory.md) when the newest snapshot is older than 8 days or the job failed. To the
owner, the server answers for a quiet section (Mentor, "Quiet" below) with its line, `needs: false`, no `action` and no
`count`, whatever the plugin said.

## Finding your way (4.36.0)
One list of places, in this order, drawn three ways (`sections()` and `drawNav()` in `web/js/core.js`):
**Today, Argus, Mentor, Zeus (the Throne plugin), Mnemosyne (the Memory plugin), Olympus, Controllers, Spartamelee,
Ariad-Node**, any other plugin, then the links to other pages and anything "coming later".
**A section that belongs to a god is called by the god's name, and only that, everywhere** (4.45.0; the owner: "I need it as
the ONLY title"): the bar, the strip, the More sheet, its line on Today, its page heading and the "who" line of a row. The
name comes from the theme's agent (`WORDS` and `wordOf()` in `core.js`), so another theme's god names it there. Sections with
no god keep their own name (Spartamelee, Ariad-Node, the links). Buttons stay verb-first ("Open
Argus"). Addresses and ids do not change (`/watch`, `throne`, `memory`); the plain words of before (Watch, Study, Approvals,
Backups, Playground) are kept in `WORDS` as `was`, for the search the next build adds.
- **On a phone (under 600 px)**: a bar at the bottom edge, in thumb reach, with five slots: Today, Argus, Mentor, Zeus and
  **More**. More opens a sheet from the bottom with every other place, the media, the links ("Other pages") and Settings
  (4.54.0, "One way to each place" above);
  Escape, Close or a tap outside shuts it and gives focus back to More. While you are on a place inside More, the More slot
  is the current one and names it. The bar keeps clear of the phone's own gesture bar (`env(safe-area-inset-bottom)`), and
  the page and the scene end above it, so nothing hides behind it.
- **Wider screens**: the same places as a strip across the top (a rail down the left on an ultrawide, docs/ui-plan.md §14),
  ending in **More** and Mute sounds. The strip is always one row inside the screen (4.44.0): when the places do not fit (a
  laptop, a phone on its side), the pills first drop their second line (a link's or a coming one's; still read out), then the weather goes, then the last
  pills fold into More, never Today or the place you are on; widen the window and they come back. Nothing scrolls sideways and
  nothing passes under Mute. More here holds the folded places, the media, the links to other pages and Settings (**Phone
  alerts**, Edit Today), so Phone
  alerts has a way in at every width; on a place inside it, More is the current one and a screen reader hears its name (no
  second line on screen: it made More, and so the strip, change shape from page to page). The strip has one shape on every
  page at a given width.
- **Each place**: its one name, its medallion, and a count only when something needs you: a red number on Argus (failed
  tasks and alerts, not those marked known), a gold mark on a section whose status says it needs you (a number once the
  server passes a `count`; never on a quiet section), summed on More. A screen reader hears "Argus, 1 needs you". Only a
  link or a coming-later place has a second, smaller line (what it is).
  A number sits where it always did on the medallion; while one shows, the label is moved 4 px right so the number keeps 6 px
  clear of it, two digits too (4.45.0). It is moved, not given a margin: the pill keeps its width, so a count that comes or
  goes never reshapes the strip.
- **Medallions**: Zeus and Mnemosyne wear their own (the Throne and Memory plugins have none of their own). Today (four squares), More (three dots), Controllers,
  Spartamelee, Ariad-Node and the links keep plain placeholder marks until the owner chooses.
- **Keyboard**: every slot and row is a link or button, in reading order after the page; the current one has
  `aria-current="page"`; focus rings show.
- **Motion with meaning**: a section arrives with a 200 ms fade; arriving from another section, the bar's gold marker slides
  over from the slot you left (200 ms); the More sheet slides up (200 ms). Under reduced motion none of it moves.

## Who sees what
`role()` in `core.js` reads `role` from the server's state: `owner` sees every place; `learner` sees Today and Mentor only
(and on Today only Mentor's row and card; Mentor is not quiet for her, it is what she studies). Until the server sends a role, everyone is the owner. A learner who opens any other place (an old link, a typed address) lands
on Today, and the page shows her no Argus: no alarm badge, no words about the owner's tasks, no chime, no way into his page,
no "Mark as known".
**This only hides places in the page; it protects nothing.** Every address and every `api/...` still answers to anyone who can
reach the server. The server's own check comes with sign-in.

## Quiet (4.45.0)
What Today, the phone and the 08:00 summary keep still about, in **one place**: `server/quiet.py` (the owner, 2026-11-13: "the
cognitive annoyance of the alert is taking up space, same with Mentor. I don't need Mentor notifications like EVER").
- **Quiet sections**: `quiet_sections()`: the default set `DEFAULT_QUIET = {'mentor'}` plus the sections the owner switched
  off in Edit Today (4.50.0, `quiet` in `today.json`), never `NEVER_QUIET = {'throne'}` (Zeus, 4.50.1). For the owner a quiet section never needs him: its line on Today keeps
  its line ("6 cards due"), but the server answers its status with `needs: false`, no `action` and no `count` (so no row, no
  number under "N things need you", no "Study 10 minutes" button, no dot or count on the bar, the strip or More), an event about
  it never buzzes the phone, and it is never in the daily summary. The page gets the set as `quiet` in the owner's state and
  checks it again (`isQuiet()` in `core.js`). A learner's page has no quiet set.
- **Known, low priority**: a failed task the owner already knows about (a login that ran out, to renew some day). **Mark as
  known**, a plain button on its card on Argus's page and on its row on Today (the owner's; no hold: it changes what reminds
  him, not what runs), sends `POST api/known` `{"job": "<task>", "on": true}`; a toast says *<task> is marked as known, low
  priority. It comes back if it fails another way.* with **Undo** (focused). Marked, the task leaves "N things need you" and
  every count, never buzzes, is not a need in the summary, and Argus's line (in More) says so quietly: *All 12 tasks well · 1 known*. On
  Argus's page it stays (sorted below the others; the view follows it when he marks it there), all in grey (`.card.known`: its pill in `--frost`, its name and values in `--powder`), with *Known, low priority · marked today, 5:40 PM*
  and **Unmark** (`"on": false`).
- **It comes back by itself.** The mark keeps the failure's **fingerprint**: systemd's `Result` and `ExecMainStatus` and the
  codes of the task's failing checks (`exit-code/1/`, `fingerprint()`). The server checks every mark on each state and every
  `KNOWN_EVERY` seconds (`reconcile()`): the mark goes when the task works again (a run ended well, or an always-on task runs
  with its checks passing) and when it fails another way (a new fingerprint, e.g. exit status 2 instead of 1). It stays while
  the task is frozen, in the middle of a timer run, or missing from systemd's list for a moment.
- **Stored server-side**, so it survives restarts and deploys: `~/.local/state/argus-ui/known.json` (or `ARGUS_KNOWN`),
  `{"<task>": {"fp": "<fingerprint>", "at": "<ISO time>"}}`, written atomically. `api/known` answers 400 for a bad request or
  an unknown task, 409 for a task that is not failing, 403 to a learner (the usual POST checks first).

## Edit Today (4.50.0)
The owner makes Today his own (`web/js/today-edit.js`, `server/today.py`). **Edit Today** is the last row of More, under
Settings (4.54.0; the owner's only): on Today it closes More and starts; elsewhere it goes to Today (`<base>/#edit`) and starts
there, once (the address loses `#edit`, so a reload does not start it again). It is a mode: Today's place becomes three
lists, with **Done** and **Cancel** at the top and the bottom, and nothing is kept until Done. Going to another section is the
same as Cancel.
- **Sections**: every section Today can give a line, each with **Show** (its line on Today when it has news), a name field
  and **Move up** / **Move down**. A god's section
  (`godOwned()` in `core.js`: a `WORDS` god or one of the theme's agents) has no field: a god's name is the only title (4.45.0).
  A new name shows wherever the section is named (`wordOf()`): its line, the bar, the strip and More. A hidden one keeps its
  bar slot, its place in More and its row under "N things need you" when it needs him.
- **Links in More** (4.54.0; was *Open*): every player and link, each with a name and Move up / down; the order and the names
  are More's. There is no Show and no group any more (a saved `hidden` or `groups` is ignored and dropped on the next save).
- **Reminders**: one switch per server section (the ones whose status can say "needs"). Off, it is quiet (see *Quiet* below):
  its line stays, but it never asks for him on Today and never buzzes his phone. Mentor is always off and locked
  (*Never reminds you*). **Zeus is always on and locked** (*Always reminds you*; 4.50.1, the owner: "Lock Zeus on"): he asks
  for the owner's yes (deploys, merges, root changes), and off, those requests would leave Today and never buzz the phone, so
  work would wait without him knowing. The server keeps it so (`NEVER_QUIET = {'throne'}` in `server/quiet.py`): `throne` in
  `today.json`'s `quiet` (by hand, or from an older page) is ignored, and a save that sends it is kept without it, not refused.
  A locked switch is disabled but keeps its name and state in words, so a screen reader still says what it is; Zeus's has a
  line under it, tied with `aria-describedby`: *Zeus asks for your yes before deploys and merges, so he always reminds you.*
  **Mnemosyne's** switch has one line under it, tied to it with `aria-describedby`: *Off also leaves the backup line out of
  the daily summary.* (`backups_line()` in `server/argus_ui.py` is empty while `memory` is quiet.)
  Argus has no switch: a failed task always counts (*Mark as known* is the way to set one aside).
- **Reset to default** fills the lists with the default; Done keeps it (the file then holds only `{"v": 1}`).
- **Keyboard**: every move is a button; after a move the keyboard stays on the same button of the same row (or on the other one
  when it reached the end). Edit opens with the keyboard on its heading; Done and Cancel give it back to More.
- **Stored server-side**, so every device shows the same Today and an update keeps it: `~/.config/argus-ui/today.json` (or
  `ARGUS_TODAY`), next to `links.json`; an install never touches that folder. Only what differs from the default is kept:
  ```json
  {"v": 1, "tiles": {"order": ["memory", "argus"], "hidden": ["olympus"], "names": {"spartamelee": "Games"}},
   "open": {"order": ["link:/notes/"], "hidden": ["media:audiobookshelf"], "names": {"link:/notes/": "Notes"},
            "groups": {"link:/notes/": "Daily"}}, "quiet": ["memory"]}
  ```
  The links' keys are `link:<href>` and `media:<id>`. A section or link not in a saved order comes after the ones that are, in its
  own order, so a new one shows up at the end. **No file**: the default layout. **A broken file** (not JSON, a wrong shape, over
  64 KB): Today shows the default and a line above it says *Your Today settings (today.json) could not be used (…), so Today shows
  the default layout. Save from Edit to replace them; the old file is kept beside it.* The next save moves it to
  `today.set-aside-<date>-<time>.json` first; nothing is overwritten. Entries it no longer knows (a link removed from
  `links.json`) are harmless and dropped on the next save.
- **`POST api/today`** with the layout or `{"reset": true}`: the owner's (a learner gets 403 and has no button), after the usual
  POST checks; a body up to 16 KB; checked strictly (names 1 to 40 characters, at most 64 entries in a list, keys up to 300
  characters, no rename of Today; a name saved for a god's section is never shown), 400 with the reason and nothing saved; written atomically (a `.tmp`
  file, then a rename). Answers `{ok, today, msg}`. Every name is drawn with `esc()`. `api/state` carries `today` (and
  `today_problem` for a broken file) in the owner's state only.

## Links to other pages (4.25.0)
Pages on the same machine that aren't LeafyGrove's own (a studio, a dashboard) are listed in `~/.config/argus-ui/links.json`
(or `ARGUS_LINKS`), read on every refresh:
```json
[{"name": "Notes", "what": "Pages", "href": "/notes/"},
 {"name": "<Studio name>", "what": "Studio", "href": "/<studio path>/", "section": true}]
```
`href` must be a path on this host (`/…`) or an `https://` address; anything else (`javascript:`, `//other-host`) is dropped,
as is a broken file. At most 8. **`"section": true`** (4.54.0; only the JSON value `true` counts, not `"true"` or `1`) makes
the link a section that opens elsewhere: a pill at the end of the computer's top bar and a row in More's sections on a phone
("One way to each place", above). Any other link is a row under **Other pages** in More, with the opens-elsewhere mark. Keep
the file on the host; never commit it (a real path or name there is the host's, not the repository's). `group` (4.45.0) is
no longer used.

## Behaviour
- The page refreshes every 15 seconds like the others: it draws at once from what it knows, then asks the server plugins
  again. A card still waiting for its answer says "Checking…". An unchanged page is not redrawn, so focus and a running
  fade stay put; when it is redrawn, keyboard focus stays on the link you were on.
- **One strong button**: only the top row's main button (its fix when it has one, else its way there) is filled in the
  bolt's gold; every other row's buttons are outlined, the same size: snow words and a 1 px frost border on the card, the
  plain focus ring. The eye goes to one thing first.
- Every row button and line is a plain link at least 44 px tall. On a phone the buttons go full width under their
  sentence, with no sideways scrolling at 360 px.
- The last thing on every page scrolls clear of the phone's bottom bar (checked at 360 x 800 on every section and Phone
  alerts, `tests/today-layout.test.js`).
- Each part sits on one quiet panel so it reads over the scene.

## Trouble first (4.40.0)
The owner reads this page mostly on a phone and is not a programmer. When something is wrong, the page says **what is wrong, what
Argus did, and what you can do**, before anything else, on Watch and on Today. `troubleItems()` in `web/js/core.js` makes one entry
per broken thing, in this order: programs that run but cannot do their job (they have a fix), checks with no task card, failed
tasks, then agents' alerts. Each entry is drawn as a **block** on Watch (`troubleBlock()`, in a "2 things need a look" panel above
the groups) and as a **row** on Today, with three plain lines:

1. **What is wrong and since when**, with whose it is: *Jellyfin runs, but cannot read its drive* · *Mnemosyne · Argus · since 4:50 AM*
2. **Argus:** what he did, or would have done (the check's `note`, docs/checks.md), without repeating his name: *Did not restart it
   and waits for your yes.* A program whose drive is gone: *Waits for the drive: a restart would not help until it is back.* Queued:
   *Your restart is being sent.* (his own: *His restart is being sent, as you allowed.*); once it is really sent: *Restarting it now,
   as you asked* (his own repair: *Restarting it now by himself, as you allowed*)*. Looks again for up to
   90 seconds and tells you if it helped.* When Argus could not look again: one more line, *Argus has not been able to look again
   since 5:52 AM.*
3. **You:** what you can do: *Hold the button to restart Jellyfin once. Argus looks again for up to 90 seconds and tells you if it
   helped.* A drive that is gone says to plug it in again; a failed task says to read its log and press Run.

The trial day's note reads *Today he only notes what he would do: he would have restarted Jellyfin.*

**A drive that is gone comes first**: its block is the first (the eye goes to the cause), and the programs whose only problem is
that drive (and a second check of the same drive) are one line under it, *Also waiting for this drive: Jellyfin, Audiobookshelf*, in place of a block each, on Watch and
on Today (they still count, one each, on the bar and in the panel's heading).

When checks.json declares a `fix` for the check (and the problem is not the drive itself), the block has **one press-and-hold
button**, *Restart Jellyfin* (`"say"` of the fix, else its units), in the bolt's gold look on the top row (outlined on a lower one, "One strong button" above), made with `holdConfirm`, for the owner
only. Holding it 3 seconds sends `POST api/watch/fix` once (docs/checks.md "Your yes from the page"); the toast says what the
server answered, and the block says *Restarting it now, as you asked* until Argus knows. It then ends on *Works again* (the row)
or *You restarted Jellyfin at 4:52 AM, and it did not help.* (the block). A refresh never redraws a button that is being held, or one that is armed (the click-twice path of a screen reader).

**Every check is on Watch while it works too.** A check whose `job` is a task card adds one line to that card, *Works · since
4:50 AM* (*Works again* after a failure). A check with no card gets a **compact row** under the agent that owns it (the agent of
its `job`, else Argus): a dot, its title and *Works · since …*, *Running, but not working: cannot read its drive · since …*,
*Not known yet: …* or *Restarting…*. Such a check is counted once: the alert the server makes from it is that row, not a second
card.

**What happened lately**, at the end of Watch: the newest 10 events (`api/events`) as plain sentences (the event's title, then
its body) with a relative and an exact time (*12 minutes ago · Wed, Nov 11, 4:50 AM*, an HTML `<time>`). With none:
*Nothing has happened since <the time the server started>.*

## The satellite eye (4.40.0)
The owner's words: the pointer still draws Argus's eyes while something is red; he should grow a satellite red eye that travels to
the broken card and glares at it. On Watch (owner only), `satellite` in `web/js/core.js`:
- **One eye leaves him.** A copy of his own red eye (his markup, cloned: no new drawing) travels once, 750 ms along a lifted
  curve (`fx.travel`), from his face to the **top-right corner of the first trouble block**, and stays there. His red eye shows
  its lid shut while it is out. It travels only when the trouble starts (the change itself draws the eye); a refresh with the
  same trouble does not move it again, and a new first block simply gets it.
- **It glares**: squinted, red, with a glow that pulses 4 times (4.8 s, under the 5 s of WCAG 2.2.2), then holds still.
- **It never covers anything**: the block keeps a 60 px gutter on its right for it (44 px eye). Checked at 360x800, 412x915 and
  1440x900.
- **Several broken things**: it goes to the first in the page's order, and a small *1 more* / *2 more* under it says how many
  others there are (they are all listed in the panel). **Every new one is noticed** (4.40.0 review): the page keeps the set of
  broken things, not only the first; when the set grows, the eye pulses once more where it stands (no travel) and the sentence
  says the new one with the count (*Extra is running but not working. Now 3 things need a look.*); when one leaves and others
  remain, the sentence says the new count, without a pulse. Reduced motion: the words only.
- **Out of view**: when the block is scrolled away, an edge marker appears on the right edge (from the top; from the bottom bar up if
  the block is below): the pill *See what needs a look* with an arrow for 5 seconds after it appears or after the set of trouble
  changes, then an arrow-only round button of 44 px with the same name. On a phone it sits bottom centre instead, just above the
  bottom bar (4.52.0). **It never rests on a control**: after every scroll and resize it takes the first spot along its edge (on a
  phone, up its centre column from the bar) where it touches no button, link, other control, task state pill or toast (4 px
  clear); where there is none, it waits out of sight until there is. Checked by a scroll sweep at 360 and 412 px (0 % of every control covered). A
  tap scrolls back to the block. Reduced motion: it changes without a transition.
- **His other eyes look at that block, not at the pointer**, while anything is red (`look.fix`). Carrying a bolt and holding a
  button still come first.
- **Said once**: the eye is `aria-hidden`; one polite live sentence says the same, once per change (*Jellyfin is running but not
  working, and 1 more thing needs a look.*). When the trouble ends the eye flies home and the sentence says *All is well again:
  nothing on Watch needs a look.* **Not across a restart of the server**: until the server's first round after a start has finished
  (`watch_ready: false`), it serves the saved verdicts (a known breakage stays broken) and the page does not say all is well or send
  the eye home. A check that cannot be looked into while nothing is broken does not keep Argus red: the server itself keeps a known
  breakage broken through unknown and stale rounds (docs/checks.md), so a real recovery calms him, his badge goes and his name says
  all is well.
- **Reduced motion**: no travel and no pulse; the eye is simply at the block.
- A learner never sees any of it (no Watch, no eye, no fix buttons, no rows about the owner's programs).
