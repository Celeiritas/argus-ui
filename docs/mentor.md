# Mentor – learn the code you build
Mentor turns code you wrote with an AI into practice, so you can read, explain and write it yourself (aiming at Python fluency). Open `<base>/mentor` (**Mentor · Practice** in the section bar). It also still runs plain flashcard decks.

## Why it works this way
Code an AI writes for you skips the part where you build the mental model (the *illusion of competence*: the output works, but you couldn't rebuild or debug it). Mentor puts that effort back where it counts:

| Knowledge | Card | Built on |
|---|---|---|
| **Tier 1 – recurrent skills** (syntax, idioms, patterns) | **Code drill**: a 5–15 line snippet from your project with blanks, faded backwards over three levels | Faded worked examples (Renkl & Atkinson, 2003); 4C/ID (Van Merriënboer & Kirschner, 2018) |
| **Tier 2 – schemas** (why it's built so, what breaks it) | **Explain card**: *Find the bug* (pre-mortem), *Why this design* (trade-off), *Human factors link* | Self-explanation (Chi et al., 1989); testing effect (Roediger & Karpicke, 2006) |
| **Tier 3 – vocabulary** | **Term card**: a sentence with the term blanked; the feedback gives what it does, where it is in your code and the term it's easily confused with | Pre-training (Mayer & Pilegard, 2014); elaborative encoding |
| **Learn first** (4.8.0) | **Learn cards** in front of each practice card: an *orientation* for the lesson, a *teach card* per term (ending in "spot it in this snippet"), a *worked example* per drill (the full code, annotated line by line; you say why a line is there before the note appears, then explain the whole), a *pre-read* per explain card (the ideas it rests on, and a near example). A teach card or pre-read with a `try_first` question (4.24.0) asks it first: you type a guess, never graded or stored, then the explanation appears under it. Read once, never scheduled; they come back only when you are stuck | Worked examples before problems (Sweller & Cooper, 1985; Renkl, 2014); self-explanation (Chi et al., 1989); erroneous examples only after the correct one (Große & Renkl, 2007); pretesting (Richland, Kornell & Kao, 2009) |

- **Teach before test** (since 4.37 a setting, *Show a lesson's reading cards before its questions*, off by default: see *Question first* below). In a new lesson, cards unlock in order: orientation → teach cards → terms → worked examples → drills → pre-reads → explain cards. Each practice card also waits for its own Learn card. Terms take up working memory, so they're learned before the code that uses them. A teach card or worked example can be skipped with *I know this, test me*; if the practice card then goes wrong, the skipped card comes back (Kalyuga et al., 2003).
- **Hints before answers.** Every practice card has a four-rung hint ladder: a *nudge*, *the expert's first move* (what an expert scans for), a *near example* in different code, and the answer. From the second rung on, each needs a three-word reflection before the next (Aleven & Koedinger, 2002; the first hint is free since 4.37) and caps the rating Mentor suggests (rung 2: at most *Well enough*; rung 3: at most *Not well*, and a drill can't move up); the answer counts as a blank. A blank *Show answer* offers a hint first. The rung reached is stored with the attempt.
- **Stuck detection.** Wrong twice in a row on a card, a skipped Learn card whose practice card then fails, the answer shown twice, or *Needs work* twice in a week: the card's Learn card comes back before the next try (and in the last two cases the card is held for a day). The stats line counts cards sent back today. The Hint button pulses after 30–90 s without typing (never a modal, never a sound).
- **Feedback that says where to look.** After a wrong answer the coach line is at most two sentences: the result, then the expert's first move and one place to look in the code. A slip (right before, wrong now) is named as one. Never about the person (Hattie & Timperley, 2007).
- **Backward fading and expertise reversal.** Level 1 blanks the endings (return values, a call), level 2 the logic (a condition, a comprehension), level 3 leaves only the signature and docstring. A drill moves up a level when every blank is right and fast (under 15 s at level 1, 30 s at level 2, plus 5 s per extra blank), or right twice in a row at that level; it comes back within a day to try the new level. *Needs work* moves it down. Hints that help a beginner just slow down someone who knows the pattern (Kalyuga et al., 2003).
- **Generate before feedback.** You always type an answer (or choose to show it) before you see the model answer.
- **Interleaving.** When studying everything, each card comes from the lesson or deck that has waited longest, so you keep working out *which* rule applies (Bjork & Bjork, 2011).
- **Context.** Every code card shows where it lives (`server › sky.py › current()`), and the lesson's big picture is one click away.

## People, Today and tracks (4.37)
Mentor is for more than one person, and it opens on **Today**: what to study now, in one button.

**Who is studying.** The people come from one file on the server, outside git: `~/.config/argus-ui/people.json` (`ARGUS_PEOPLE` gives another path).
```json
{"people": [
  {"id": "owner-one", "name": "Owner One", "role": "owner", "logins": ["owner@example.com"]},
  {"id": "learner-two", "name": "Learner Two", "role": "learner", "logins": ["learner@example.com"]}
]}
```
`id` is optional (the name in lower case, every run of other characters one `-`). Elaia's server says who is asking (`who`, from the Tailscale login) and enforces the roles in `plugin.json` before Mentor is called; Mentor checks again. Mentor takes the role from the people file it reads itself, never from `who` alone: a person the file does not know is refused (403, with a sentence), and a `who` that claims `owner` for someone the file lists as a learner counts as a learner. **A request the server says nothing about (`who` is None) is the owner**: that is the contract while the server passes no `who`, so the people file and a learner's lessons belong on the server only once it does. A **learner** always studies as herself; a `learner=` she sends is ignored, and she sees only her own name. An **owner** may study as anyone in the file: the page's *Who is studying? Owner One · change* sends `learner=<id>` (a query on GET, a field on POST) and remembers the choice on that device. An unknown id is a 404 with a sentence. **No file:** one person, the owner, exactly as before. **A file that is not JSON:** read as no file, one log line, and every POST is refused with a sentence that names the file.

**One database per person.** The owner keeps today's database (`~/.local/share/argus-ui/mentor.db`, or `ARGUS_MENTOR_DB`): it is opened as before, and its rows are never moved or rewritten (`tests/mentor_people_test.py` compares it row for row before and after a learner studies). Whose it is, is written into `mentor.db` itself the first time it opens under a people file (the first owner then); after that the order of lines in the file never decides it, so a second owner gets a database of her own and nobody's history moves. If that person's id leaves the file (an owner renames her id), the first owner takes `mentor.db` over and one line is logged. Anyone else gets `mentor-<id>.db` in the same folder, made on first use, with only their own lessons from `~/.local/share/argus-ui/decks-<id>/` (read again when a file there is added or changed; no restart). Nothing of the owner's (the theme's decks, `decks/`, the inbox) is ever loaded into it. Each database has its own lock, so two people never wait on each other; reading a changed lesson folder happens under that lock too. A duplicate `id` in the people file keeps its first entry and logs one line. The local AI runs only when the person studying is an owner ([mentor-ai.md](mentor-ai.md)).

**Tracks.** A track is what a person picks to study: a plain deck, every lesson of one project or course (`group:<name>`; submenus count with their menu, so a menu with twelve lessons is one track), or a lesson without a project. Per database (study settings):

| Setting | Meaning |
|---|---|
| `pinned` | up to 3 tracks on Today and in *Study 10 minutes*. A fourth is refused: *You can pin 3 tracks. Unpin one first...* |
| `shelved` | tracks hidden from study and from every count (due, new, Home's line). History and schedule are kept; taking a track off the shelf brings it back exactly as it was. Shelving never edits a lesson file. A track is pinned or shelved, never both. |
| `new_per_day` | `{track: n}` new questions a day (default 10; `"*"` sets every track). A question counts on the local day of its first rating, so the limit holds across reloads and restarts and starts again after midnight. `null` takes a value out. **With nothing pinned**, a session's new questions share one limit for the whole day (the `"*"` value, else 10), so a database with many tracks does not open on hundreds of new cards. |
| `goal` | `{track: "one line"}` shown on the track's card. Only an owner sets it (a learner's goal: the owner studying as her). |
| `ask_confidence` | tracks that ask *How sure are you?* on every card; others ask it on every fifth card. |
| `teach_first` | the 4.32 order: every question after its reading card. Off by default. |

**Today.** When everything is done, Today says so (*All done for today. Next: Sat, Nov 14.*) and has no primary button; **Study a little more** brings the next cards forward (`next?extra=1`) and is offered only when a card is scheduled. Otherwise one primary button, **Study 10 minutes**: due reviews of the pinned tracks first, then other reviews off the shelf, then new questions from the pinned tracks up to each one's daily limit (nothing pinned: every track off the shelf). A thin bar fills over the ten minutes; when it is full the card on screen is finished, then a summary (*12 cards, 9 right. Next: tomorrow, 8 due.*) with **Keep going 5 more** and **Replay my 3 mistakes**. The timer lives in the page only. Under the button: up to three pinned track cards (name, goal, due today, new, a bar of questions *started*, that is answered at least once, **Study this**); the week as seven dots, one per day, filled by minutes studied (a card counts at most 2 minutes; no streak that breaks); and **Shelf: N tracks · Browse**, which lists every track with *Pin* / *Unpin*, *Shelve* / *Take off the shelf* and *Preview* (size, history, the first three questions, never an answer).

**Question first.** A new lesson starts with a question, not a wall of reading. **Teach me first** on a card opens its lesson card (or the lesson's orientation) above it, and counts as help: the answer goes in with `taught: true`, Mentor suggests at most *Hard* and a drill does not move up a level from it; otherwise the lesson card comes with the result the first time, and counts as read. A lesson with nothing to answer is still read card by card, and stuck detection still sends a lesson card back before the next try. Fewer steps per card: *How sure are you?* on every fifth card, the three-word reflection from the second hint on. **Think it, reveal it, rate it** is the default on a phone (600 px or narrower) for cards answered in words (define, explain, predict, write): show the answer, compare, rate it yourself (the attempt is stored with grader `self` and coverage 0.0, and left out of every graded count; no rating is suggested). After a rollback to a Mentor before 4.37, such rows read as answers with no key ideas: its average coverage and calibration count them as 0, and nothing fails. Typing is one tap away (*Type my answer instead*), remembered on the device, and stays the default on a wide screen. A long question shows about 80 words, the rest behind *More*.

**API (4.37).** Every route also takes `learner=` (an owner's choice; ignored for a learner).

| Route | Answer |
|---|---|
| `GET learners` | `{me, role, people: [{id, name, role}], problem}`; a learner gets only her own entry |
| `GET today` | `{learner, tracks: [{id, name, lessons, goal, cards, learned, progress, due, new, new_per_day, new_today, new_left, later, tomorrow, last, pinned, shelved, ask_confidence}], pinned, pin_max, shelf, due, new_left, scope, later, tomorrow, next_due, week: [{day, minutes}] (7), minutes, confidence_every, teach_first}` |
| `GET track?id=` | Preview: `{id, name, lessons, goal, cards, reading, learned, answers, last, questions, pinned, shelved}` |
| `GET next?session=1` | the next card of a *Study 10 minutes* session; every card now has `track`, `ask_confidence`, `teach_id` |
| `POST answer {..., think: true, taught: true}` | `think`: a self-rated answer (`coverage: null` in the answer, 0.0 stored; `suggested: 0`); `taught`: Teach me first was open (at most Hard, no level-up). Every result can carry `teach` (the lesson card) and `teach_new` |
| `POST settings` | also `pinned`, `shelved`, `new_per_day`, `goal`, `ask_confidence`, `teach_first` |
| `GET status` | Elaia's Today card and Home's line, per person: `{line: "6 due", needs, action: "Study 10 minutes"}` |

## The loop
1. **Build something** in Claude Code as usual.
2. **Run `/mentor`** (or `/mentor` plus a file or function name). The command reads the latest change, writes one JSON file to the project's `mentor_inbox/` folder, and replies with a single line, so your coding chat stays clean. The command's text is in [`docs/mentor-command.md`](mentor-command.md): copy it to `~/.claude/commands/mentor.md`. Add `mentor_inbox/` to the project's `.gitignore`.
3. **Copy the file to the inbox** on the machine that runs Argus: `~/.local/share/argus-ui/inbox/` (or set `ARGUS_MENTOR_INBOX`). For example: `scp mentor_inbox/*.json <host>:.local/share/argus-ui/inbox/`.
4. **Study.** The lesson appears the next time Mentor shows a card (no restart). **Lessons** lists every lesson with its breakdown (big picture, design rules, rules that must hold, human factors link), your progress per tier, every Learn card to read again, any notes the `/mentor` command left about its own output, and **Study this lesson**. Files with problems are listed there with the reason; inbox files are read, never moved or deleted. Changing a file re-imports it and keeps your history.

Argus ships one lesson, **Argus: caching, locks and the Mentor scheduler** (`themes/leafy-realm/decks/argus-code.json`), made from this project's own `sky.py` and `mentor.py`. It doubles as an example of the format, Learn fields included. A lesson needs no drills: terms and explain cards alone import and run, and a spot-it snippet can be a terminal transcript rather than code. Anything that names your machines, paths or hosts belongs in your private inbox or decks folder, not in a theme: themes ship with the repository.

**How a card should read** (4.24.0): every lesson and deck follows the [deck rubric](mentor-rubric.md): no file paths or repo words in what you read, one idea per card, a question before each explanation, a worked example before the fades, plain words with every term defined once. `python3 scripts/check-deck.py <file or folder>` checks a lesson before it goes in the inbox; the tests run it on the decks that ship.

## The study screen and the Lessons page (4.25.0)
- **No greyed-out buttons.** Every button works; if something is missing (a guess, a picked line, three words of *why*), a line under the field says what, and focus goes there.
- **Lines wrap.** Code and spot-it snippets wrap long lines and keep their indentation; nothing scrolls sideways. The box you write a whole function body in still doesn't wrap.
- **One lesson chosen:** the header shows how many of its lesson cards you've read.
- **End of a session:** "This session: 12 cards answered, 9 right", and **Replay your 3 mistakes** asks those cards again (`next?replay=<card id>` serves a practice card without its answer).
- **Lessons** is a course map: one *Continue where you left off*, the reviews due, then each project's lessons as one framed list. A row has the name, one line, how much is practised and one action (Start, Continue, Review); *About this lesson* and *Read the lesson again* open under it; each project's sources are one list behind *Where these lessons come from*. Calibration, the local AI line and how to add a lesson are under *About Mentor and adding a lesson*.

## Courses (4.26.0)
A **course** turns one project into something you can rebuild alone (the plan: [`docs/plans/2026-10-25-mentor-courses-spec.md`](plans/2026-10-25-mentor-courses-spec.md)). It has levels: **course** → **modules** (one slice of the project, `requires` other modules) → **lessons** (one sitting) → **notes** (one source item: a term, a concept, a snippet, a claim, each with a `source_ref`) → **cards**. Each level has **learning objectives** (LOs): `{id, text, verb, bloom, mode, knowledge, condition, standard, parent}`, one observable verb each, every lesson LO serving a module LO and every module LO a course LO.

A course is one JSON file in the inbox (or a decks folder), `"format": "mentor-course/1"`. A course lesson is a lesson in the format above with `id`, `los` and `notes` added, and four fields on each card: `lo` (one of the lesson's LOs), `note`, `role` and `check`:
```json
{"format": "mentor-course/1", "id": "demo-server", "name": "Rebuild a small web server", "summary": "…", "requires": [], "retention": 0.9,
 "sources": [{"cite": "Rosenshine, B. (2012). Principles of instruction. American Educator.", "url": "https://…"}],
 "los": [{"id": "T1", "text": "Build request checks that refuse unsafe POSTs", "verb": "build", "bloom": "create", "mode": "write",
          "knowledge": "procedural", "condition": "docs allowed", "standard": "all tests pass", "parent": null}],
 "modules": [{"id": "requests", "name": "Requests", "requires": [], "los": [{"id": "M1", "parent": "T1", "…": "…"}],
   "lessons": [{"id": "origin", "name": "Why a cross-site POST is refused", "los": [{"id": "L2", "parent": "M1", "…": "…"}],
     "notes": [{"id": "n-host", "kind": "snippet", "source_ref": {"repo": "argus-ui", "path": "server/argus_ui.py", "symbol": "do_POST", "commit": "beab7ba"}}],
     "cta_summary": {"orientation": "…"},
     "tier_2_self_explanation_cards": [{"id": "c-why", "lo": "L2", "note": "n-host", "role": "explain", "front_prompt": "…", "…": "…"},
                                       {"id": "k-origin", "lo": "L2", "note": "n-host", "role": "explain", "check": true, "…": "…"}]}]}]}
```
A full example is `tests/deck-fixtures/good-course.json`; `python3 scripts/check-deck.py` checks a course before it goes in the inbox (the C rules in the [deck rubric](mentor-rubric.md)).
- **Roles:** `term`, `recall`, `explain`, `find-bug`, `choose-design`, `drill`, and since 4.32 `predict`, `trace`, `parsons` and `write` (in a lesson's `code_cards` list, below). `make` (tasks and the capstone) comes later; until then such a card is skipped and named in Lessons.
- **Check items** (`"check": true`) are kept for module checks: they're never served as practice, never hold back a lesson's other cards, and never count as waiting. Their Learn cards wait with them (a teach card or pre-read would show the answer). Every LO needs at least 2 practice cards and 1 check item.
- **Source references:** `{repo, path, symbol, commit, lines}` for code, `{cite, url, doi}` for a paper, `{note, path}` for your own notes. A symbol is the bare name (`host_ok`); `host_ok()` and `H.do_GET` are read as `host_ok` and `do_GET`. `commit` is a commit id. Cards show the symbol, never the path.
- **Loose lessons:** every lesson in the older format belongs to the built-in course *Loose lessons*, one module per project. Nothing moves in Lessons: a course's lessons show as one group under the course's name, in course order.
- **Re-importing** a changed course keeps your history; a lesson, note or LO the file no longer has goes (its attempts and schedule rows stay). Lesson ids are unique within a course; a file whose course `id` changes replaces its old course instead of adding a second one.

**Review log.** Every rating also stores what it was, as Anki's review log does: `review` (*learn* until the card is first passed with Hard or better, *review*, *relearn* after an Again, *manual* when practising ahead), `ivl_before` and `ivl_after` (days), and `took` (time, capped at 60 s; the raw `ms` stays for the grader). This is what fitting FSRS to you will read later.

## Code cards, unlocking and module checks (4.32)
Four card roles for reading code before writing it (spec sections 5 and 8; read and trace before write, Xie et al., 2019). They go in a lesson's `code_cards` list, each with `id`, `lo`, `note`, `role`, `front_prompt` (the question), and `lang` (`python` by default; only Python is parsed):

| Role | You see | You do | Graded | Needs |
|---|---|---|---|---|
| `predict` | the code, with line numbers | type what it prints or returns | key ideas, against the model answer (`answer`) | `code`, `answer`, `eval_rubric` |
| `trace` | the code, with line numbers, and one box per step ("Step 2: after line 3") | type each name's value after that line | each step on its own: its `state` or an `accept` wording | `code`, `steps: [{"line": 3, "state": "total = 2", "accept": ["2"]}]` |
| `parsons` | the lines, mixed (never in their right order) | put them in order with **Up** / **Down** on each line | exact order: one point per line in its right place (4 of 5 in place = 80%) | `lines`, in their right order (3 to 12) |
| `write` | a box, starting from `starter` if given | write the code (<kbd>Enter</kbd> keeps the indent) | key ideas; Python's own syntax error is shown beside them (parsed, never run) | `answer` (the model code), `eval_rubric`, optional `starter` |

```json
"code_cards": [
  {"id": "p-1", "lo": "L1", "note": "n-read", "role": "predict", "front_prompt": "What does this print?",
   "code": "total = 0\nfor n in [1, 2, 3]:\n    total = total + n\nprint(total)", "answer": "6",
   "eval_rubric": [{"idea": "it prints 6", "any": ["6"]}]},
  {"id": "z-1", "lo": "L3", "note": "n-write", "role": "parsons", "front_prompt": "Put the lines in order so the function adds up a list.",
   "lines": ["def total(items):", "    result = 0", "    for x in items:", "        result = result + x", "    return result"]}
]
```
The full example, one lesson requiring another, is `tests/deck-fixtures/good-roles.json`; the checker's rules for each role are C10 to C13 in the [deck rubric](mentor-rubric.md).
- **Key ideas in code.** On these cards words like `for`, `in`, `is`, `and` and `or` count (in a written explanation they are skipped), so `{"idea": "loops over the items", "any": ["for"]}` works. A trace step accepts its `state` (all its words: `total = 2` needs `total` and `2`) or any `accept` wording; a value counts only in its own step.
- **Parsons by keyboard.** Every line has **Up** and **Down** buttons (44 px). Focus starts on the first line's Down; after a move, focus stays on the same button of the line you moved, so pressing again keeps moving it; <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>Alt</kbd>+<kbd>↓</kbd> on a line's button moves it too. A line read out for screen readers says where it went ("Line moved to place 2 of 5"), or that it is already first or last. <kbd>Ctrl</kbd>+<kbd>Enter</kbd> checks.
- **The local AI** (if on) scores written code in shadow mode, as it does explanations: shown, labelled, never the rating. It never writes or changes course material.
- **Unlocking.** A course lesson can name the lessons of its course it builds on: `"requires": ["read"]`. It opens when each of them is **mastered**: 80% of its practice cards answered right (the spec's module pass threshold). *Right* means rated Good or Easy with no hint above the second rung (the expert's first move); one right answer per card is enough, and an undone rating doesn't count. A module's `requires` (other modules) works the same way: its lessons open once every lesson of the required modules is mastered. Until then the lesson serves nothing, its cards don't count as new, Lessons shows it as **Locked** with what opens it, and choosing it in Study says the same. A card studied before its lesson became locked keeps its reviews. Loose lessons are never locked.
- **Module checks.** Check items (`"check": true`) are still never practice. Once every lesson of their module is mastered, each one is asked once, as the **module check** (after the reviews due, before new cards; the card says *module check*, and the rating buttons show no review times because a check is not scheduled). The check passes at 80% right. A missed item comes back the next day, alone, until it passes. Undo works on a check answer too.
- **The course map.** In Lessons, a course shows each module with its lessons under it: *2 of 3 lessons mastered* or *Locked: opens when … is mastered*, a bar for the share answered right, and the check's state (*once every lesson is mastered*, *ready: 3 questions to answer*, *passed: 4 of 4 right*, *not passed yet*). With bury siblings on, a check question whose note had a card practised today waits until tomorrow, and the map says *ready: 4 questions tomorrow*; it counts what the queue will serve. Each lesson row shows *75% right* or *100% right · mastered*, or **Locked** and what opens it. The counts line adds the module check questions ready now, and Home's line says so when nothing else waits.
- `stats` returns `checks` and `pass`, each course module's `done`, `progress`, `mastered`, `locked`, `waiting_on` and `check`, and each course lesson's `progress`, `mastered`, `locked`, `waiting_on`; `next` returns `locked` (the sentence) when a chosen lesson waits. The database gained `modules.requires` (added on start, once; nothing else changes).

## Menus and submenus (4.22.0)
A lesson's `metadata.project` names where it sits in the Study picker. A plain project (`Sound-Haptics-Lab`) puts the lesson under **Lessons** as "project: name". A project with the separator ` › ` (space, U+203A, space), such as `GAME_RESEARCH › Topics`, puts it in its own submenu; the picker offers **Study all** for that submenu and **Study all of GAME_RESEARCH** for the whole menu. Group choices travel as `group:<project>` (`next?deck=group:GAME_RESEARCH`) and take every lesson whose project is that name or lies under it.

## Placeholders: your machines, never in a lesson
A lesson is meant to move between people (and to sit in a public repository), so it never names a real machine, path or account. It says `{{SERVER}}` instead, and Mentor fills that in every time it shows a card, from `~/.config/leafy/realm.json` on the machine that runs it (yours alone; never commit it). Every field a card shows is filled: prompts, answers, hints, snippets, the Lessons view. Grading compares your answer against the filled-in text, so you type your server's real name. The database keeps the `{{…}}` form, so editing `realm.json` takes effect on the next card, with no restart and no re-import.

| Placeholder | Means | Default (no `realm.json`) |
|---|---|---|
| `{{SERVER}}` | the always-on machine that runs Argus | `homeserver` |
| `{{PC}}` | the computer you code on | `desktop` |
| `{{PHONE}}` | your phone | `phone` |
| `{{SSH}}` | the ssh name of the server (`ssh {{SSH}}`) | `server` |
| `{{HOME_PC}}` | your home folder on the PC | `C:\Users\you` |
| `{{HOME_SERVER}}` | your home folder on the server | `~` |
| `{{REPO_URL}}` | your clone's URL | `https://github.com/you/argus-ui` |

Copy [`realm.example.json`](realm.example.json) to `~/.config/leafy/realm.json` and change the values; keys you leave out keep their default, and key case doesn't matter. A missing or broken file means the defaults (`LEAFY_REALM` points Mentor at another file). Unknown `{{NAMES}}` and `{{BLANK_n}}` are left alone. `scripts/check-private.sh` stops a push that names a real home path, host, address or email (see `CLAUDE.md`).

## Keys, learning steps, undo and siblings (4.31.0)
Anki's study behaviours, on top of FSRS (spec section 7):

| Key | Where | What it does |
|---|---|---|
| <kbd>Space</kbd> | A practice card's question, when no text box, button or other control has focus | Shows the answer. With something typed it checks it (the result shows the model answer); with nothing typed it opens the last hint rung, the answer (which counts as a blank, so Again is suggested), and puts focus on *Rate it*. Inside a text box Space types a space. |
| <kbd>Esc</kbd> | In an answer box | Leaves the box for the question, so Space and Ctrl+Z reach Mentor. |
| <kbd>1</kbd>–<kbd>4</kbd>, <kbd>Enter</kbd> | The result | Pick Again, Hard, Good or Easy; Enter saves. |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | Anywhere on Mentor, except a text box with text in it, or one you emptied when there is no rating to take back (that box keeps its own undo) | Takes back the last rating of this session: the card's schedule returns to exactly what it was, and the card is asked again. Only one step back: a second press says *Nothing to undo*. The rating's toast also has an **Undo** button. |
| <kbd>Alt</kbd>+<kbd>H</kbd> | A practice card's question | The next hint. |

- **Learning steps.** A new card comes back after **1 min**, then **10 min**, before FSRS schedules it in days: *Again* goes back to the first step, *Hard* waits a little (6 min on the first step, between the two; the same step again later), *Good* moves to the next step and graduates from the last one, *Easy* graduates at once. A review card you forget (*Again*) relearns with one **10 min** step (Hard: 15 min), then FSRS takes over with the new, shorter stability. The first rating sets the card's FSRS memory; the steps on the same day leave it as it is (FSRS-4.5 learns from one review a day). Each rating button shows exactly when the card comes back ("In 1 min", "In 6 min", "In 10 min", "In 14 days"). A card on its steps is served when its minutes are up and then counts as due (also on Home); until then the session can end with "The next card comes back in 10 min", and *Practise ahead* brings it early. The counts line shows how many come back later today. Cards scheduled before 4.29 carry on in review as they were (no step).
- **Undo.** Before a rating changes a card, its schedule is saved with that answer's log row (`prev_json`). Undo writes it back and marks the row `undone=1`; no row is ever deleted. An undone rating is left out of the history that later ratings look at (relearn/review, the drill level, holds), out of the grader's labels, and the export carries the `undone` flag. If the rating had sent a lesson card back (held for a day), that card is no longer sent back. The server only undoes the latest rating, never a rating from before 4.29 and never two in a row (`POST undo {"attempt": id}` returns `{"undone": false}` otherwise).
- **Bury siblings** (on by default). Siblings are cards made from the same **note** of a course (only course cards have notes; a Loose lesson card has none, so nothing is buried there). Once you rate one today, the others wait until tomorrow (local midnight): they are not served, not counted as due or new, and don't hold back the rest of the lesson. A Learn card is never buried, nor a card on its learning steps. Undoing the rating brings the siblings back. Turn it off under **Study settings** (under the counts on the Study page); the choice is stored in the database (`settings` table, `POST settings {"bury": false}`), next to the history it shapes.

## How a card works
1. Read the prompt and type: the missing code in each box (levels 1–2), the whole body (level 3; <kbd>Enter</kbd> keeps the indent and adds one after a colon), the missing term, or your explanation. Say how sure you are.
2. Mentor checks it:
   - **Blanks** are compared as code: spacing around symbols, quote style and extra brackets don't matter (`(a)` = `a`). A blank can accept alternatives.
   - **Whole bodies** are parsed with Python's `ast` (never run). Same structure as the model = full marks; otherwise you see both versions, how alike they are, and Python's own syntax error with its line number.
   - **Terms** allow small typos; part of a multi-word term counts as close.
   - **Explanations** use the key-idea rubric (below).
3. The result comes in one band under the question, the same place every time: **Correct** (green, a tick), **Partly right** (amber, a minus), **Not quite** (red, a cross) or **Answer shown**, always with the word and the icon, never colour alone, and the coach line saying why or where to look. Key ideas are marked "✓ Got it" / "✕ Missing"; a long model answer shows its first paragraph, with the rest (evidence, notes, sources) behind *Show the full answer and sources*. Then pick how well you knew it, in Anki's order: **1 Again · 2 Hard · 3 Good · 4 Easy**, each showing when the card comes back (keys 1–4, Enter saves, Ctrl+Z takes the last rating back; a Learn card has no rating: *Next card* marks it read). If Mentor's grade was off, *Report a grading problem* holds the "grade was wrong" flag ([FSRS-4.5](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm); stored as 1–4).
4. If Mentor's grade was off, tick **Mentor's grade was wrong**. That flag is training data for the learning grader.

The stats line also tracks **calibration**: how your confidence compares with what you actually got right.

## Grading roadmap
| Stage | Grader | Status |
|---|---|---|
| A | Key-point rubric for explanations (key ideas with accepted wordings; typos and word endings tolerated); code-aware blank matching; `ast` structure match and token similarity for whole bodies | **4.2.0**, code grading **4.7.0** |
| B | Local similarity model adds a meaning-based score (runs on your own machine) | planned |
| Bv2 | A small model trained on *your* saved attempts (features + your ratings + "grade was wrong" flags) predicts grades and coaching hints | planned; data is collected from the first answer |

Every attempt is stored in `~/.local/share/argus-ui/mentor.db` (`attempts` table): answer, confidence, time taken, card kind and drill level, grader features (rubric hits; blanks right; syntax ok, same structure, token similarity), the highest hint rung reached and the reflections typed, the stuck signal if any, whether a Learn card was skipped, and the suggested and final rating. Older databases gain the new columns on start; nothing is lost.

## Formats
### Lesson (what `/mentor` writes)
The full schema is in [`docs/mentor-command.md`](mentor-command.md). In short (the Learn fields are in the section below):
```json
{
  "metadata": {"timestamp": "2026-10-20T14:22:33", "module_name": "weather_cache", "project": "argus-ui",
               "source_files": ["server/sky.py"], "concepts_covered": ["context managers"]},
  "cta_summary": {"schematic_mental_model": "…", "design_rules_heuristics": "…",
                  "hard_rules_invariants": "…", "hci_human_factors_bridge": "…"},
  "tier_1_faded_code_drills": [{"id": "drill_01", "file_breadcrumb": "server -> sky.py -> current()",
      "context_comment": "…", "full_canonical_code": "…",
      "level_1_fade": "… return {{BLANK_1}} …", "level_2_fade": "…", "level_3_fade": "def f(x):\n    \"\"\"…\"\"\"\n    {{BLANK_1}}",
      "answers": {"level_1": ["_mem"], "level_2": ["…"], "level_3": ["body, indented relative to the blank's line"]},
      "python_fluency_note": "…"}],
  "tier_2_self_explanation_cards": [{"id": "card_01", "card_type": "Pre-Mortem", "file_breadcrumb": "…",
      "front_prompt": "… code may go in ``` fences …", "back_explanation": "…",
      "eval_rubric": [{"idea": "a crash leaves a half-written file", "any": ["half", "partial", "truncated"]}]}],
  "tier_3_terminology_cards": [{"id": "term_01", "term": "context manager", "category": "Python Syntax",
      "concise_definition": "…", "project_anchor": "sky.py -> current(): `with _lock:`",
      "contrast_anchor": "Unlike …", "cloze_prompt": "`with _lock:` uses the lock as a {{BLANK}} …"}]
}
```
Each `{{BLANK_n}}` needs one answer per level, in order; a level that doesn't match is skipped and reported in **Lessons**. `eval_rubric` lines may also be plain sentences (as in the first version of the command); they're graded on their content words, more roughly, and the coach says so. Files in the first draft's shape (`faded_code_drills`, `self_explanation_flashcards`) also import.

### Plain deck
Built-in decks ship in the theme (`themes/<theme>/decks/`). Your own go in `~/.local/share/argus-ui/decks/` and load on restart; editing a deck keeps your history. A lesson can also be placed there to ship it with a theme. Plain decks have no Learn phase (their cards are self-contained) but do get the hint ladder (the expert's move and the answer).
```json
{
  "id": "ux-hci", "name": "UX & HCI terms", "blurb": "One line about the deck",
  "cards": [
    {"id": "fitts", "prompt": "Define: Fitts's law",
     "answer": "The model answer shown after you try.",
     "points": [
       {"idea": "time to point at a target", "any": ["time", "point", "acquire", "fast"]},
       {"idea": "increases with distance",   "any": ["distance", "far", "close"]},
       {"idea": "decreases with target size", "any": ["size", "bigger", "width"], "weight": 1}
     ]}
  ]
}
```
A key idea counts as covered when **all** words of **any** of its phrases appear in the answer (common words ignored, endings like -s/-ing/-ed ignored, small typos allowed). `weight` defaults to 1.

## Notes for changing it
- Mentor's code is a bundled server plugin (`docs/leafy-plugin.md`), `plugins/mentor/`: `mentor.py` (import with derived Learn cards, grading, the hint ladder, stuck detection, scheduling, levels), `plugin.py` (the door: `api/mentor/...` and Home's `status` line, one request at a time on the database), `page.js` (the page), `page.css`, `plugin.json` (`"agent": true`). Tests: `tests/mentor.test.js`, and `tests/bundled.test.js` for the plugin side.
- A local AI can add a meaning score and feedback, off by default and never used for the rating yet: `docs/mentor-ai.md`. `python plugins/mentor/mentor.py export` writes your rated attempts as JSON lines for a grader that learns from you.
- Your data did not move: the database is still `~/.local/share/argus-ui/mentor.db` (or `ARGUS_MENTOR_DB`), the inbox `~/.local/share/argus-ui/inbox`, your decks `~/.local/share/argus-ui/decks`. To try a changed Mentor without a deploy, copy `plugins/mentor/` to `~/.config/argus-ui/plugins/mentor/` and restart Elaia: your copy wins over the bundled one.
- The server's Mentor routes are fixed (`decks`, `next`, `stats` to read; `answer`, `rate`, `undo`, `settings` to write; POST bodies are at most 4 KB). A drill's blanks travel in `answer` as a JSON list in `text`; a worked example's reflections and self-explanation as a JSON object; `answer` with `hint: k` returns rung k without writing an attempt, and the final answer carries `hints` (highest rung) and `reflections`; `rate` with `rating: 0` marks a Learn card read; `next?card=<id>` returns one Learn card to read again. Lessons and inbox status come with `stats`.
- Typed code is only ever parsed (`ast.parse`, `tokenize`), never executed.
