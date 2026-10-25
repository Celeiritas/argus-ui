# Home

Home (`<base>/home`) answers **"what needs me today, across the realm, and where do I go?"** It is about *you*. Watch (`<base>/`) is about *the machines*: "is every task running?". So Home is shaped differently: no grid of cards, but a greeting, one to-do list and a row of places (docs/ui-plan.md §3).

**For now, Watch stays the default page.** Home is a pill at the front of the section bar. Making Home the default and renaming the page to Elaia are separate changes, made after the name test (three people, about 10 minutes: "where would you go to…?").

## What it shows
1. **The greeting** in the page header: "Good morning / afternoon / evening / night" by the viewer's clock, then the date and the weather ("Friday, October 23 · Light rain · 48°F").
2. **Needs you**: one list with a count, most urgent first. Each row has the section's mark, who it's from, one sentence, and one verb-first button that goes there:
   - every `alert`-level alert file (docs/alerts.md): its message, and "Open <section>" when it links to one
   - failed tasks, as one row: "1 task failed: hermes-rename" → **Look at 1 failed task** (to Watch)
   - every server plugin whose status says it needs you: its line → its `action` ("Study 5 due cards", "Approve argus-ui 4.15.0")

   When nothing does: *"Nothing needs you. The realm is quiet."* (While sections are still answering: "Asking every section…".) Warnings stay on their cards on the Watch page.
3. **Places**: one medallion per section in the section bar's order (Watch, Mentor, Olympus, then plugins), each with its one line: Watch's task count, a server plugin's status line, a static plugin's version.

## Links to other pages (4.25.0)
Pages on the same machine that aren't Elaia sections (a studio, a dashboard) can sit in the section bar and on Home. List them in `~/.config/argus-ui/links.json` (or `ARGUS_LINKS`), read on every refresh:
```json
[{"name": "Sound Lab", "what": "Studio", "href": "/studio/"}]
```
`href` must be a path on this host (`/…`) or an `https://` address; anything else (`javascript:`, `//other-host`) is dropped, as is a broken file. At most 8. In the bar a link has an "opens another page" mark; on Home it is a place whose button says "Open <what>".

## Status v2 (what a server plugin answers)
`GET api/<id>/status` → `{"line": "…", "needs": true, "action": "Study 5 due cards"}`. `line` is required for anything to show; `needs` (only `true` counts) puts the plugin in **Needs you**; `action` is the button's label, verb-first, cut to 32 characters, and defaults to "Open <name>". Elaia passes on only these three fields and never errors (`{"line": null}` when a plugin has nothing or fails). A plugin that answers only `{"line"}` keeps working and simply never appears in the list. Mentor answers `needs` when cards are due.

## Behaviour
- The page refreshes every 15 seconds like the others: it draws at once from what it knows, then asks the server plugins again. A place still waiting for its answer says "Checking…".
- A redraw keeps keyboard focus on the link you were on. Every row button and place is a plain link at least 44 px tall, so Tab and Enter work. On a phone the buttons go full width under their sentence and the places make a three-column grid, with no sideways scrolling.
- New rows slide in (reduced motion: they just appear). Each part sits on one quiet panel so it reads over the scene.
- The Home pill's mark (four squares in the section frame) is a **placeholder** until the owner approves art.
