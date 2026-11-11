# Today (once called Home)

Today answers **"does anything need me, and where do I go?"** in a few seconds, on a phone, with one thumb. It is what Elaia
opens on: the bare address `<base>/`, and `<base>/home`, its old address, which keeps working. It is about *you*. Watch
(Argus's section, `<base>/argus`) is about *the machines*: "is every task running?".

## What it shows, top to bottom
1. **The header**: the page's name, Elaia, and under it a greeting by the viewer's clock, the date and the weather
   ("Good evening · Friday, October 23 · Light rain · 48°F").
2. **One line that says the state in words**: *Nothing needs you* (with "The realm is quiet." under it), *1 thing needs you*,
   *3 things need you*, or *Asking every section…* while the sections are still answering. It counts what the bar counts:
   every task in trouble, every alert, and each section that needs you (its `count`, else one). It is the heading of the list:
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
4. **Open**: the links to other pages on this machine (below), each a 44 px chip with its name and what it is. No links file,
   no row.
5. **Sections**: one one-line card per section, in the bar's order: its mark, plain word, realm name and status line. Watch
   says "All 6 tasks well" or "1 task failed" (red edge); a server plugin shows its status line (gold edge while it needs
   you); a static plugin shows its version. The playground has no news and no card. The whole card is the link.

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
- **Wider screens**: the same places as a strip across the top (a rail down the left on an ultrawide, docs/ui-plan.md §14).
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
Pages on the same machine that aren't Elaia sections (a studio, a media server) can sit in the bar and on Today. List them in
`~/.config/argus-ui/links.json` (or `ARGUS_LINKS`), read on every refresh:
```json
[{"name": "Sound Lab", "what": "Studio", "href": "/studio/"}]
```
`href` must be a path on this host (`/…`) or an `https://` address; anything else (`javascript:`, `//other-host`) is dropped,
as is a broken file. At most 8. In the strip and the More sheet a link has an "opens another page" mark; on Today it is a chip
in the Open row.

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
   *Restarts it in a moment, as you asked*; once the restart is really sent: *Restarting it now, as you asked. Looks again for up to
   90 seconds and tells you if it helped.* When Argus could not look again: one more line, *Argus has not been able to look again
   since 5:52 AM.*
3. **You:** what you can do: *Hold the button to restart Jellyfin once. Argus looks again for up to 90 seconds and tells you if it
   helped.* A drive that is gone says to plug it in again; a failed task says to read its log and press Run.

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
- **Out of view**: when the block is scrolled away, an edge marker appears (top right; above the bottom bar if the block is below): the pill *Look* with an arrow for 5 seconds after it appears or after the set of trouble changes, then an arrow-only round button of 44 px with the same name (*Scroll to what needs a look*), so it does not rest on a control. A tap scrolls back to the block. Reduced motion: it changes without a transition.
- **His other eyes look at that block, not at the pointer**, while anything is red (`look.fix`). Carrying a bolt and holding a
  button still come first.
- **Said once**: the eye is `aria-hidden`; one polite live sentence says the same, once per change (*Jellyfin is running but not
  working, and 1 more thing needs a look.*). When the trouble ends the eye flies home and the sentence says *All is well again:
  nothing on Watch needs a look.* **Only when Argus could look at everything**: while a broken check's round was unknown (podman
  could not look inside) or its result is stale, the server keeps it broken (docs/checks.md), and the page never says all is well,
  never turns the alarm off and never sends the eye home while any check is unknown, stale or seen once only.
- **Reduced motion**: no travel and no pulse; the eye is simply at the block.
- A learner never sees any of it (no Watch, no eye, no fix buttons, no rows about the owner's programs).
