# Home

Home (`<base>/home`) answers one question: **does any part of the realm need me?** It shows one tile per section, each with the line that answers that question, and any alert at the top. The whole tile is the link to the section.

**For now, Watch stays the default page** (`<base>/`). Home is a pill at the front of the section bar. Making Home the default and renaming the page to Elaia are separate changes, to make after the name test (three people, about 10 minutes: "where would you go to…?").

## The tiles
| Section | Its line | Where it comes from |
|---|---|---|
| Argus · Watch | "1 task failed · 1 alert · 2 stone", or "All 6 tasks well". The tile has a red edge while something failed or an alert is up | the page state (`api/state`), no extra request |
| Mentor · Learn | "3 cards due · 2 to learn", "5 new cards waiting" or "Nothing due" | `api/mentor/stats` |
| Olympus | "Powers, weather, seasons" | fixed |
| A server plugin | its own sentence, e.g. "1 deploy waiting · argus-ui 4.9.1 live" (Zeus), or "No news" | `GET api/<id>/status` → `{"line": …}` (docs/leafy-plugin.md) |
| A static plugin | "Version 0.5.0" | `plugin.json` |

Above the tiles, every `alert`-level alert file (docs/alerts.md) is listed with its "Open <section>" link. Warnings stay on their cards on the Watch page.

## Behaviour
- The page refreshes every 15 seconds like the others. It draws at once from what it knows, then asks Mentor and the server plugins again. A tile still waiting for its answer says "Checking…".
- A redraw keeps keyboard focus on the tile you were on. Tiles are plain links, so Tab and Enter work, and each is at least 44 px tall. On a phone the tiles stack in one column without sideways scrolling.
- The Home pill's mark (four squares in the section frame) is a **placeholder**: new art is drawn to match the theme and approved by the owner first.

## Adding a line for a new section
A server plugin gets a tile automatically: answer `api/<id>/status` with one sentence that says whether it needs the owner, and put the count first ("2 waiting · …"). Keep it under 160 characters, and use placeholders, never real names.
