# Elaia UI plan: every section, more to touch

A plan for making each section reachable from Home more interactive, with the same kind of assets and small animations as the Olympus playground. It covers what each page is *for*, what it shows, what you can do there, what moves and why, and the art it needs. It is a plan, not a spec: each section becomes its own pull request (in its agent's repo when it is a server plugin), and every new piece of art waits for the owner's approval.

Written 2026-10-23 from the code of argus-ui 4.15, Hermes 0.2.2, Janus 0.2.1, Zeus 0.3.3, the Mnemosyne backup job, and the rules in CLAUDE.md, `docs/ux-audit-4.1.md` and the agents' design docs.

## 1. The rules every section keeps
These come from the repos' rules; the plan never trades one away for a nicer animation.
- **Motion confirms something real.** An animation shows an event that happened (a delivery arrived, a deploy reached *install*, a door closed), never decoration that competes with status. Every animation has a still equivalent: with `prefers-reduced-motion` it becomes a fade or nothing, and the state is still shown.
- **State is an icon plus a word**, never colour alone (✓ delivered, ⚠ quarantined, ⏸ held, 💤 asleep).
- **The list comes first in the DOM.** A picture (a maze, a road, a shelf) is a `<figure>` drawn from the same data, `role="img"` with a summary label, out of the tab order. The list is the keyboard and screen-reader path, and the default under 600 px.
- **44 px hit areas, verb-first labels, visible focus, a keyboard path for every pointer action, no sideways scroll at 375 px**, type 16/14/12, weights 400/600.
- **Drag is never the only way.** As on Olympus, anything you can drag you can also pick up with a click or Enter and place with a click or Enter.
- **The page never decides.** Reads are file reads (no subprocess on a GET). Writes call the agent's own CLI with fixed arguments; Janus and Zeus decide. Anything that changes what runs uses **hold-to-confirm** (3 s; keyboard: hold Space or Enter; letting go early sends nothing).
- **Escape everything** (`esc()`), placeholders in public text, nothing personal committed.
- **Art:** the theme's existing icons are never redrawn. New art is drawn to match (flat shapes, the medallion frame, the palette below) and approved by the owner before it ships; until then a section uses a plain placeholder mark.

**Palette** (already in the theme): night `#1C2127`, card, powder `#A7B6C4`, snow `#E6ECF1`, gold `#E7C35A`/`#C9A36A`, bolt `#FFE27A`, each agent's hue (Zeus storm gold `#E0B341`, Janus slate `#4A5568`, Hermes sky `#8EC9E8`, Athena olive `#9BAA6A`, Dionysus wine `#B04A8A`).

## 2. Shared pieces to build first
Each section below reuses these, so they come first and keep every page consistent.

| Piece | What it is | Why first |
|---|---|---|
| **`fx.js` + `api.fx`** (built in 4.18: docs/fx.md; `medal(key)` stays in Olympus until another page needs it) | Move the Olympus helpers out of `olympus.js`/`powers.js` into one shared file: `particle`, `burst`, `crumble`, `boltFx`, `streak`, `motes` (a ribbon of glowing motes, after SoulSeed's heal swirl), `medal(key)`. Server plugins get them as `api.fx`. All honour reduced motion inside, so a plugin can't forget. | Every page wants the same feedback; copying it into four repos would drift. |
| **`holdConfirm(button, onDone)`** (built in 4.18) | The 3-second hold with a ring that fills and the words "Hold… 3 · 2 · 1"; Space/Enter held works the same; reduced motion shows the countdown words only. | Throne's Approve and Roll back, Delivery's Release. One implementation, one test. |
| **Status v2** | `GET api/<id>/status` may add `needs` (true when the owner should act), `action` (a verb-first label, 32 characters at most, e.g. "Approve argus-ui 4.15.0") and `count`. Old plugins keep working: `{line}` alone still shows. | Home's "Needs you" list is built from it. |
| **Events** | `GET api/<id>/events?since=<iso>` → `[{t, kind, text, link}]`, at most 50, newest last, read from the agent's own logs. | Home's "Today" strip and each page's history use it. |
| **`ctx.jobs()`** | A server plugin can read the task information Elaia already collects (last run, next run, state) without its own subprocess. | Mnemosyne has no status file; her page needs the timer's last and next run. |

## 3. Home: the agora (`<base>/home`)
**What it is for:** *"What needs me today, across the whole realm, and where do I go?"* Home is about **you**. Watch is about **the machines**: "is every task running?". Today they look alike (a grid of tiles next to a grid of cards), so Home changes shape.

**Shows, top to bottom:**
1. **Greeting band:** "Good evening" by the viewer's clock, the date, and the weather as a sentence ("Light rain, 48 °F"). There is no tile grid; Argus stays small in the corner.
2. **Needs you:** one list, ordered by urgency (alerts first, then decisions, then study), one row per thing to do. Each row has the section's medallion, a sentence, and one verb-first button that goes there: **Approve argus-ui 4.15.0** · **Review 1 quarantined delivery** · **Look at 1 failed task** · **Study 5 due cards**. Rows come from status v2 (`needs: true`) and from alert files. When it's empty, it says *"Nothing needs you. The realm is quiet."*, and an owl from Olympus settles on the nearest tree (art already approved, 4.15).
3. **Today:** a horizontal day line from midnight to now with small marks for the day's events (deliveries, deploys, backups, study sessions, door changes) from the events contract. Hover or focus a mark to read it; a new mark drops in like one of Demeter's seeds. Under 600 px it becomes a short list of the last five.
4. **Places:** one row of medallion buttons, one per section, each with a one-line status under it. It's quieter than today's tiles: no card boxes and no borders.

**Interactions:** Enter or click a row's button to go there. The day line is a list of buttons (←/→ move along it). There are no destructive actions on Home, ever.

**Motion:** a new "Needs you" row slides in from its medallion (reduced motion: it appears). A row leaves with a short fade when its need is met.

**Art:** none new beyond Home's own pill mark (the placeholder awaits approval).

## 4. Watch: Argus's watchtower (`<base>/`)
**What it is for:** the machines' health. It stays a grid of task cards with the powers (Medusa, Zeus's bolt). Changes:
- **Since you last looked:** a card that failed or changed state since your last visit gets a thin gold glint for one refresh, and the header says "2 changed since 9:20 AM" (kept in `localStorage`).
- **Filter chips:** All · Failed · Running · Stone · Transient, plus `f`, `r`, `s` shortcuts.
- **Run history dots** on each card: the last ten runs as ✓/✕ dots, for timer tasks only, read from the journal once per refresh. The cost needs measuring first.
- **Argus's hundred eyes:** with more than one failure, small eyes open along the section bar's Argus pill, one per failure. This needs approval (new art).

## 5. Mentor: the study (`<base>/mentor`, bundled plugin)
**What it is for:** learning the code you build. Changes:
- **The lesson garden.** Each lesson is a plant in a strip of ground at the top of the page, grown from FSRS *stability*, not from streaks: seed (new) → sprout → young tree → tree with fruit (well retained). Cards that are due make a few leaves droop; answering them perks the plant up with a short Demeter's-seed sparkle. It measures retention, not effort, so it can't be gamed by grinding, and it never shames (no dying plants, only drooping ones). Click a plant to study that lesson. *Art: four growth stages, needs approval; until then the scene's trees and flowers stand in.*
- **The hint ladder as a ladder:** the four rungs drawn as steps that light as you climb, so you can see what you've used (the words stay).
- **Athena's owl as the local AI's voice.** When the local model is on (docs/mentor-ai.md), its feedback appears in a speech bubble from the owl, clearly labelled "Local AI · <model>", under the rubric's grade, never instead of it. When the model is off or slow, no owl appears and nothing waits.
- **Answer feedback:** a correct key idea pops an olive-leaf burst at its line (reduced motion: the ✓ only).

## 6. Olympus: the playground (`<base>/olympus`)
Ten of the twelve-plus-two seats now have powers (4.15 added Hermes' sandal, Athena's owl and Dionysus' cup). These are the next proposals, each needing approval:

| Seat | Item | Does |
|---|---|---|
| Artemis | a silver crescent moon | makes it night for 30 s: the moon rises over the summit, stars come out, owls' eyes glow, skeletons yawn and sit down |
| Hera | a peacock feather | a peacock struts across and fans its tail; the tail's eyes are Argus's (Hera set his hundred eyes there) and all follow the pointer |
| Ares | a war horn | skeletons line up and march in step to the nearest edge; trees shake |
| Aphrodite | a dove | carries a flower from the ground to a skeleton or a stone tree; two skeletons with flowers dance together |

## 7. Hermes · Delivery (`<base>/delivery`, Hermes plugin, hermes#11, #25, #27)
**What it is for:** what came in and went out, and what's waiting on you (quarantine).

**Shows (DOM order):** the status line ("4 delivered today · 1 quarantined · 1 waiting for {{PC}}"), the send box, recent deliveries with All / Quarantined / Outbox filters, the fetchers, and the quarantine detail. Next to the list is **the road**, a `<figure>`:
- Senders on the left, Janus's gate in the middle, places on the right (library shelf, mail, outbox, quarantine cage, held box).
- Each recent delivery is a parcel at the end of its path.
- New arrivals since the last refresh travel the road: they slide in, stop at the gate for a beat (Janus checking), then go to the shelf (✓ delivered), into the cage (⚠ quarantined), into the box (⏸ held), or to the outbox with a 💤 when the device is asleep.

**Interactions:**
- **Send a note:** type, pick a route, **Send note**. Hermes' winged sandal carries it off along the road (reuses the 4.15 sandal art).
- **Fetch now** on each fetcher (allowlisted jobs only). While one runs, a small sandal runs back and forth on its row.
- **Quarantine:** click or press Enter on a parcel or its row to open the detail: the verdict reasons with ⚠ notes, a copyable `hermes discard` line, and **Release…**, which opens the Zeus hold-to-confirm (Hermes never releases by itself; #27). Executables stay refused.
- **Seen** clears the alert.

**Art (needs approval):** the parcel (three sizes by bytes), gate, shelf, cage, held box, outbox. The sandal is already approved.

## 8. Janus · Map (`<base>/map`, Janus plugin, janus#12)
**What it is for:** which doors in the realm are open, and the door check's verdicts.
- **Two faces.** The page header carries Janus's two-faced medallion with a toggle: **Map** (doors) and **Checks** (the verdict log). The medallion turns when you switch (reduced motion: no turn).
- **Map:** one `<section>` per room (device), each door a `<button>` with ✓ open · ✕ closed · 💤 asleep · ⚠ closed unexpectedly. The maze `<figure>` draws rooms as tiles and doors as gates that swing open or shut when their state changes. An asleep room dims with Artemis' crescent over it, and an unexpectedly closed door glares red like Argus.
- **Probe now:** a lantern travels the maze from door to door while the probe runs (`POST probe` → `janus map --once`), and each door flips as its answer comes back.
- **Checks:** the last verdicts as rows (pass / quarantine / duplicate) with their four checks shown as four small pips (route, kind, shape, integrity), plus a 7-day bar of verdicts per day.
- **Door detail:** expect (`always` / `when-online` / `sometimes`), the agents that use it, its clients, and a 7-day strip of open and closed from the doors log.

**Art (needs approval):** room tile, gate in four states, lantern, two-faced medallion (Janus's icon stays; the toggle uses it).

## 9. Zeus · Throne (`<base>/throne`, Zeus plugin, zeus#11)
**What it is for:** deciding what gets deployed, and seeing what's live.
- **Waiting:** each request is a stone tablet before the throne: repo, version, subject, files changed, checks, time to expiry, and the gold badge "changes the realm's own rules" when it does.
  - **Approve & deploy:** hold to confirm. The ring charges; on release at 3 s, Zeus's bolt strikes the tablet (the existing `boltFx`).
  - **Decline:** pick a reason word, and the tablet crumbles (the existing `crumble`).
- **Deploying:** the five stages, fetch → checkout → build → install → health, as a lightning path through five nodes, each lighting from the live deploy log (refreshed every 2 s while deploying). *install* is marked: a failure after it means the previous version goes back. There is no Cancel.
- **Deployed now:** each repo's live version as a column with "since" and the approver. **Roll back → 4.14.0** is hold-to-confirm, and the column steps down one stone.
- **History:** past versions as stone steps, with filters All / Waiting / Expired / Failed.

**Art (needs approval):** the tablet, the throne silhouette and the stage nodes. The bolt and the crumble exist already.

## 10. Mnemosyne · Memory (`<base>/memory`, new bundled plugin in this repo)
**What it is for:** are my backups fresh, and how many copies exist. Mnemosyne has no repo and no status file. Her job writes snapshots `<server>-brain_<date>_<time>.tar.gz` weekly (Sun 04:00), so the page reads the snapshot folder (names, sizes, times) and `ctx.jobs()`.
- **Shows:** the last snapshot's age and size, the next run, and the count and total size of snapshots. Then **the shelf**: one jar per snapshot, its height scaled by size, labelled by date, the newest glowing faintly.
- **3-2-1, honestly:** three vessels: *on the server* ✓, *on the PC* (✓ when a copy is there; the PC folder is not visible from the server, so this is a manual tick for now), *off-site* ✕ "drives planned". It shows what isn't done instead of hiding it.
- **Back up now:** a hold-to-confirm, because it pauses Jellyfin for about a minute. It calls `systemctl --user start --no-block mnemosyne-<server>-brain.service`, a fixed argument that is the same allowlisted run Argus's bolt already does. While it runs, a ribbon of motes (SoulSeed's heal-swirl look) flows from the server into a new, filling jar.
- **Never:** deleting snapshots, restoring from the page, or showing what's inside a snapshot (it holds keys and passwords).

**Art (needs approval):** the jar, the shelf and the three vessels.

## 11. Spartamelee (`<base>/spartamelee`, static plugin)
It stays a sandboxed frame. Home shows its version. If Spartamelee later writes a small `status.json` into its own folder (last played, current version), Home could show "Played yesterday". That would be read-only, and it still never runs code in Elaia's page.

## 12. Order of work
1. **Home v2 + status v2** (this repo). Home is the first page you see, and the change you asked for. Building it is half done (on a branch waiting for #17).
2. **`fx.js` / `api.fx` / `holdConfirm`** (this repo), with tests, before any agent page. Done in 4.18.
3. **Mentor's local-AI groundwork** (docs/mentor-ai.md), then the garden once its art is approved.
4. **Zeus · Throne** (zeus#11), because it replaces typing `yes` over ssh. Then **Hermes · Delivery** (hermes#11), **Janus · Map** (janus#12) and **Mnemosyne · Memory**.
5. **Olympus** proposals as art is approved; **Watch** additions alongside.

## 13. Art waiting for the owner
| Section | Pieces | Status |
|---|---|---|
| Olympus | sandal, owl, cup | **approved** (2026-10-23, shipped in 4.15) |
| Home | pill mark | placeholder, waiting |
| Mentor | lesson plant in four stages | proposed |
| Delivery | parcel, gate, shelf, cage, held box, outbox | proposed |
| Map | room tile, gate ×4 states, lantern | proposed |
| Throne | tablet, throne, stage nodes | proposed |
| Memory | jar, shelf, three vessels | proposed |
| Olympus | crescent moon, peacock feather, war horn, dove | proposed |
| Watch | Argus's small eyes | proposed |
