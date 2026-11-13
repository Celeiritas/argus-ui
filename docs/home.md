# Today (once called Home)

Today answers **"does anything need me, and where do I go?"** in a few seconds, on a phone, with one thumb. It is what Elaia
opens on: the bare address `<base>/`, and `<base>/home`, its old address, which keeps working. It is about *you*. Watch
(Argus's section, `<base>/argus`) is about *the machines*: "is every task running?".

## What it shows, top to bottom
1. **The header**: the page's name, Elaia, and under it a greeting by the viewer's clock, the date and the weather
   ("Good evening · Friday, October 23 · Light rain · 48°F"). On a narrow phone it wraps onto a second line rather than being
   cut off (4.44.0). This is Today's only weather: the strip's weather (on every other page) is hidden here (4.44.0).
   Above the list, for the owner, **the server's own line on what it is doing now** (4.44.0, below), a small panel of its own.
2. **One line that says the state in words**: *Nothing needs you*, *1 thing needs you*, *3 things need you*, or *Asking every
   section…* while the sections are still answering. It counts what the bar counts: every task in trouble, every alert, and
   each section that needs you (its `count`, else one). A learner sees "The realm is quiet." under it when nothing needs her.
   It is the heading of the list:
3. **The rows that need you**, the failed thing first. Each row has the place's mark, who it is from (the plain word and the
   realm's name, e.g. *Approvals · Zeus*), one sentence, and one verb-first button that goes there:
   - **one row per broken thing on Watch** (4.40.0, see "Trouble first" below): a program that runs but cannot do its job,
     a check with no task card of its own (a media program, a drive), a failed task, each with the same three plain lines as on
     Watch and, when checks.json declares a fix, the same press-and-hold button (**Restart Jellyfin**) beside **Look at it on
     Watch**
   - every `alert`-level alert (docs/alerts.md) that is not about one of those: its agent in plain words ("Hermes · Watch"),
     its message, and "Open <section>" when it links to one, else "Look at Hermes on Watch" (Watch showing that agent's tasks)
   - every server plugin whose status says it needs you: its line → its `action` ("Study 5 due cards", "Review argus-ui 4.15.0")

   A row whose need is met **fades out** where it stood (200 ms, hidden from screen readers while it goes); a row that is new
   since the last draw slides in. Under reduced motion both just happen. Warnings stay on their cards on the Watch page.
4. **Open** (the owner's): the media players (Jellyfin, Audiobookshelf; below), then the links to other pages on this machine
   (below), each a 44 px chip with its name and what it is. Neither file, no row.
5. **Sections**: one one-line card per section, in the bar's order: its mark, plain word, realm name and status line. Watch
   says "All 6 tasks well" or "1 task failed" (red edge); a server plugin shows its status line (gold edge while it needs
   you); a static plugin shows its version; the Playground says "Powers, weather, seasons". The whole card is the link.
   **One place for each fact** (4.44.0): a section with a row above has no card until that row is gone (Watch with a failed
   task, Approvals with a deploy waiting), so the same news is never said twice on one screen. No card left, no heading.

## What the server is doing now (4.44.0)
One line above the list, in its own small panel (not a row of the list), for the owner only, written by the server
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

## Films, shows and audiobooks (4.44.0)
The media players' own pages (they are other sites, not Elaia sections) are the first chips in Today's Open row when the host
says where they are, in `~/.config/argus-ui/media.json` (or `ARGUS_MEDIA`), read on every refresh:
```json
{"jellyfin": "http://<host>:<port>/", "audiobookshelf": "http://<host>:<port>/"}
```
Only these two keys count (any case); each must be an `http://` or `https://` address, at most 300 characters, with no
spaces or quotes (a player on the tailnet or the home network is often plain http). Anything else, a broken file or no file:
no chip. They show as **Jellyfin · Films and shows** and **Audiobookshelf · Audiobooks and podcasts**, plain links with
`rel="noopener noreferrer"` (no referrer, no hold on Elaia's window), for the owner only. Keep the file on the host; never
commit it. They are on Today only, not in the strip or More.

## A section's card: status v2
`GET api/<id>/status` → `{"line": "…", "needs": true, "action": "Study 5 due cards"}`. `line` is required for anything to show;
`needs` (only `true` counts) puts the plugin in the rows and gives it a mark in the bar; `action` is the button's label,
verb-first, cut to 32 characters, and defaults to "Open <name>". Elaia passes on only these three fields and never errors
(`{"line": null}` when a plugin has nothing or fails). A plugin that answers only `{"line"}` keeps working and simply never
needs you. **A new section (workouts, meals, music) gets its card on Today by answering this, nothing else.** Mentor answers
`needs` when cards are due; Memory (docs/memory.md) when the newest snapshot is older than 8 days or the job failed.

## Finding your way (4.36.0)
One list of places, in this order, drawn three ways (`sections()` and `drawNav()` in `web/js/core.js`):
**Today, Watch (Argus), Study (Mentor), Approvals (the Throne, Zeus), Backups (Memory, Mnemosyne), Playground (Olympus),
Controllers, Spartamelee, Ariad-Node**, any other plugin, then the links to other pages and anything "coming later".
- **On a phone (under 600 px)**: a bar at the bottom edge, in thumb reach, with five slots: Today, Watch, Study, Approvals and
  **More**. More opens a sheet from the bottom with every other place, the links ("Other pages") and the sound switch;
  Escape, Close or a tap outside shuts it and gives focus back to More. While you are on a place inside More, the More slot
  is the current one and names it. The bar keeps clear of the phone's own gesture bar (`env(safe-area-inset-bottom)`), and
  the page and the scene end above it, so nothing hides behind it.
- **Wider screens**: the same places as a strip across the top (a rail down the left on an ultrawide, docs/ui-plan.md §14),
  ending in **More** and Mute sounds. The strip is always one row inside the screen (4.44.0): when the places do not fit (a
  laptop, a phone on its side), the pills first drop their second line (still read out), then the weather goes, then the last
  pills fold into More, never Today or the place you are on; widen the window and they come back. Nothing scrolls sideways and
  nothing passes under Mute. More here holds the folded places, **Phone alerts** and the links to other pages, so Phone
  alerts has a way in at every width; on a place inside it, More is the current one and a screen reader hears its name (no
  second line on screen: it made More, and so the strip, change shape from page to page). The strip has one shape on every
  page at a given width.
- **Each place**: the plain word large, the realm's name small under it where it differs, its medallion, and a count only
  when something needs you: a red number on Watch (failed tasks and alerts), a gold mark on a section whose status says it
  needs you (a number once the server passes a `count`), summed on More. A screen reader hears "Watch, Argus, 1 needs you".
- **Medallions**: Approvals uses Zeus's, Backups Mnemosyne's. Today (four squares), More (three dots), Controllers,
  Spartamelee, Ariad-Node and the links keep plain placeholder marks until the owner chooses.
- **Keyboard**: every slot and row is a link or button, in reading order after the page; the current one has
  `aria-current="page"`; focus rings show.
- **Motion with meaning**: a section arrives with a 200 ms fade; arriving from another section, the bar's gold marker slides
  over from the slot you left (200 ms); the More sheet slides up (200 ms). Under reduced motion none of it moves.

## Who sees what
`role()` in `core.js` reads `role` from the server's state: `owner` sees every place; `learner` sees Today and Study only
(and on Today only Study's row and card). Until the server sends a role, everyone is the owner. A learner who opens any other place (an old link, a typed address) lands
on Today, and the page shows her no Argus: no alarm badge, no words about the owner's tasks, no chime, no way into Watch.
**This only hides places in the page; it protects nothing.** Every address and every `api/...` still answers to anyone who can
reach the server. The server's own check comes with sign-in.

## Links to other pages (4.25.0)
Pages on the same machine that aren't Elaia sections (a studio, a dashboard) can sit in More and on Today. List them in
`~/.config/argus-ui/links.json` (or `ARGUS_LINKS`), read on every refresh:
```json
[{"name": "Sound Lab", "what": "Studio", "href": "/studio/"}]
```
`href` must be a path on this host (`/…`) or an `https://` address; anything else (`javascript:`, `//other-host`) is dropped,
as is a broken file. At most 8. In the More sheet (under "Other pages", at every width since 4.44.0; no longer a pill of its
own in the strip) a link has an "opens another page" mark; on Today it is a chip in the Open row.

## Behaviour
- The page refreshes every 15 seconds like the others: it draws at once from what it knows, then asks the server plugins
  again. A card still waiting for its answer says "Checking…". An unchanged page is not redrawn, so focus and a running
  fade stay put; when it is redrawn, keyboard focus stays on the link you were on.
- Every row button, chip and card is a plain link at least 44 px tall. On a phone the buttons go full width under their
  sentence and the cards make one column, with no sideways scrolling at 360 px.
- Each part sits on one quiet panel so it reads over the scene.

## Trouble first (4.40.0)
The owner reads this page mostly on a phone and is not a programmer. When something is wrong, the page says **what is wrong, what
Argus did, and what you can do**, before anything else, on Watch and on Today. `troubleItems()` in `web/js/core.js` makes one entry
per broken thing, in this order: programs that run but cannot do their job (they have a fix), checks with no task card, failed
tasks, then agents' alerts. Each entry is drawn as a **block** on Watch (`troubleBlock()`, in a "2 things need a look" panel above
the groups) and as a **row** on Today, with three plain lines:

1. **What is wrong and since when**, with whose it is: *Jellyfin runs, but cannot read its drive* · *Mnemosyne · Watch · since 4:50 AM*
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
button**, *Restart Jellyfin* (`"say"` of the fix, else its units), in the bolt's gold look, made with `holdConfirm`, for the owner
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
  the block is below): the pill *Look* with an arrow for 5 seconds after it appears or after the set of trouble changes, then an
  arrow-only round button of 44 px with the same name (*Scroll to what needs a look*). **It never rests on a control**: after every
  scroll and resize it takes the first spot down that edge where it touches no button, link or other control (4 px clear); where
  there is none, it waits out of sight until there is. Checked by a scroll sweep at 360 and 412 px (0 % of every control covered). A
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
