# Today (once called Home)

Today answers **"does anything need me, and where do I go?"** in a few seconds, on a phone, with one thumb. It is what Elaia
opens on: the bare address `<base>/`, and `<base>/home`, its old address, which keeps working. It is about *you*. Watch
(Argus's section, `<base>/argus`) is about *the machines*: "is every task running?".

## What it shows, top to bottom
1. **The header**: the page's name, Elaia, and under it a greeting by the viewer's clock, the date and the weather
   ("Good evening · Friday, October 23 · Light rain · 48°F").
2. **One line that says the state in words**: *Nothing needs you* (with "The realm is quiet." under it), *1 thing needs you*,
   *3 things need you*, or *Asking every section…* while the sections are still answering. It is the heading of the list:
3. **The rows that need you**, the failed thing first. Each row has the place's mark, who it is from (the plain word and the
   realm's name, e.g. *Approvals · Zeus*), one sentence, and one verb-first button that goes there:
   - failed tasks, as one row: "1 task failed: hermes-rename" → **Look at 1 failed task** (to Watch). When the server sends a
     `reason` for a single failed task, the sentence ends with it.
   - every `alert`-level alert file (docs/alerts.md): its message, and "Open <section>" when it links to one
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
(and on Today only Study's row and card). Until the server sends a role, everyone is the owner. Sign-in is not built here.

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
