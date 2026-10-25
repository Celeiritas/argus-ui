# Mentor courses – spec (draft for the owner's approval)

**Status:** approved by the owner 2026-10-25 (section 15). Nothing here is built yet. The UI it builds on is the approved mockup (study flow, Lessons, phone, Sound Lab link).

## 1. Goal
Mentor becomes a personal course platform: each of the owner's projects is dissected into a **course** with tiered learning objectives (LOs), so that by the end of it the learner can rebuild that project alone, understanding its terms, its language (Python, C#, JS), and its tools (git, GitHub, Linux).

**Not goals (for now):** multi-user, sync, a marketplace, exporting to Anki (kept as a later option, section 11).

**Licence rule:** the app stays MIT. Anki (AGPL-3.0) is read for behaviour only, never copied. py-fsrs (MIT) may be used. The CC BY-SA education skills are authoring tools, not part of the app.

## 2. What the design rests on (short; sources in section 13)
- **Backward design and alignment:** write the LO, then the check that proves it, then the teaching (Wiggins & McTighe; Biggs). One observable verb per LO; condition and standard stated (Mager).
- **Tiers:** revised Bloom (remember → create) with programming split into *reading* and *writing* code (Fuller et al., 2007). Read and trace before write (Xie et al., 2019).
- **Mastery:** teach → check → fix the misses → retest (Bloom; Kulik). An LO counts as mastered only after a later spaced review succeeds (Khan's "Mastered").
- **Practice formats with evidence:** retrieval practice, interleaving of confusable types, Parsons problems, PRIMM / Use-Modify-Create, subgoal labels, explain-in-plain-English.
- **Feedback:** explained feedback beats right/wrong alone (Van der Kleij et al., 2015); the verdict in one fixed place, never colour alone.
- **Scheduling:** Anki's behaviours on top of FSRS: learning steps, button interval preview, bury siblings, leeches, desired retention, per-answer review log.
- **AI:** an answer-giving chatbot raised practice scores but lowered exam scores (Bastani et al., 2025); a tutor with strict teaching rules and pre-written solutions helped (Kestin et al., 2025). LLM-written material is often wrong and invents citations, so every generated item is checked before a learner sees it.

## 3. The levels
| Level | Holds | Size |
|---|---|---|
| **Course** | one project. 3–6 *terminal* LOs (create/evaluate level), prerequisites (other courses), modules, a capstone, sources | weeks |
| **Module** | one slice of the project (as a whole task, 4C/ID). 2–5 LOs, each pointing at a course LO; `requires` (other modules); a module check | a few days |
| **Lesson** | one sitting, 15–30 min. 1–3 LOs; the fixed order below | one sitting |
| **Note** | one source item: a term, a concept, a code snippet, a claim from a paper, each with a `source_ref`. Makes one or more cards | – |
| **Card** | one prompt, linked to exactly one LO, with a `role` | seconds |

**Lesson order** (Gagné, Rosenshine): try-first question → "You'll be able to…" (the LOs) → recall what it builds on → teach (one idea per screen) → worked example with subgoal labels → guided practice → independent practice → exit check → back to the try-first answer → replay mistakes.

## 4. Learning objectives
Each LO: `{id, text, verb, bloom, mode, knowledge, condition, standard, parent}`
- `verb`: one observable verb (trace, predict, explain, write, fix, choose, build). Never know/understand/learn about.
- `bloom`: remember | understand | apply | analyse | evaluate | create.
- `mode`: `read` (interpret code) or `write` (produce code); concepts outside code use `read`.
- `knowledge`: factual | conceptual | procedural | metacognitive.
- `condition`: what is allowed (hints up to rung N, the AI tutor, docs, none).
- `standard`: e.g. "all tests pass", "3 of 4 key ideas", "right on the first try".
- `parent`: the module or course LO it serves.

Example (Elaia's server, module "Safe POSTs"): *"Explain, without hints, why the server rejects a POST whose Origin is another site (2 of 2 key ideas)."* → understand / read / conceptual.

## 5. Card roles (what each Bloom level gets)
| LO level | Card roles |
|---|---|
| remember | `term` (cloze of the term, contrast shown after), `recall` |
| understand · read | `predict` (what does this print / return), `trace` (values after each line), `explain` (own words, rubric) |
| apply · write | `parsons` (put the given lines in order), `drill` (faded levels 1–3), `write` (small function, checked by tests or `ast`) |
| analyse / evaluate | `find-bug` (only after the correct version was taught), `choose-design` (which and why) |
| create | `make` tasks and the capstone only |

Rules: every LO has at least 2 practice cards and 1 check item; check items never appear in practice. Teach cards, worked examples and pre-reads stay as Learn cards (read once, back when stuck).

## 6. Notes and source references
A **note** is the unit an author edits; its cards render from it (Anki's note → cards).
`source_ref`: `{repo, path, symbol, commit, lines}` for code; `{cite, url, doi}` for papers; `{note, path}` for the owner's research notes.
- Cards show the **symbol** only (`current()`), never the path. The Lessons view and "Card info" show the full reference with an Open link.
- **Staleness:** a rebuild compares each note's `symbol` at the new commit. Unchanged → nothing. Changed → the note's cards are flagged "code changed" and the author redrafts them (history kept). Gone → cards are marked orphaned; the learner is asked before they retire.

## 7. Scheduling (Anki behaviours on FSRS)
- **Review log:** one row per answer: card, time, rating 1–4, interval before and after, ms (capped at 60 s), kind (learn / review / relearn / manual), hints used. Today's `attempts` table grows these columns.
- **Learning steps:** new cards 1 m → 10 m, then FSRS days; relearning 10 m. Hard on step 1 = average of steps 1 and 2.
- **Button preview:** each rating button shows its next interval ("in 10 min", "in 4 days"). Keys 1–4; Space shows the answer; Ctrl+Z undoes the last rating.
- **Bury siblings:** on by default: cards from the same note never appear the same day.
- **Leech:** 8 lapses → the card is flagged, its Learn card comes back, and the author sees "split or rewrite this card". No silent suspension.
- **Limits:** new *lessons* per day (default 1) instead of new cards; reviews per day (default 200). Desired retention 0.90 per course; maximum interval 1 year.
- **Optimise:** fit FSRS weights per course from the review log once there are ~400 reviews; again monthly or on request.
- **Practice now** (Anki's filtered decks): "practise this module" and "review what I forgot today" run in preview mode and don't move the schedule.

## 8. Unlock and mastery
- A lesson unlocks when the LOs it builds on are at least **practised** (each card answered right once).
- An LO is **mastered** when its cards' average recall chance (FSRS retrievability) is ≥ the desired retention and its latest check item passed unaided at least a week after first learning.
- A **module check**: interleaved items across the module's LOs plus one Modify task on the real code. Pass = ≥ 80% right on the first try with no hint above rung 2. Fail → a short corrective lesson for the missed LOs, then a parallel retest.
- The **capstone** unlocks when every module passed: rebuild a reduced slice of the project from a written spec, no hints, no AI; checked by tests plus an explain-the-design rubric.
- **Test out:** any lesson or module check can be taken early; passing marks its LOs practised.

## 9. Who writes courses, and the local model
**Authoring (the course builder):** a Claude Code session in the project's repo runs a `/course` command (successor of `/mentor`):
1. map the project: modules from its structure and git history; terms; the languages and tools it uses;
2. write course and module LOs first, then check items, then lessons and notes (backward design);
3. run the checker (section 10) and fix every error;
4. drop the course into Mentor's inbox as **Draft**.

In Mentor, **Drafts** shows each new or changed note for the learner to accept, edit or reject before it is studied (the "human checks every generated item" rule). Personal courses never go in `themes/`.

**The local model (qwen2.5:7b-instruct + nomic-embed-text on the server):**
- *Keeps:* the meaning score and short feedback on written answers (shadow mode, never the rating).
- *Gains:* a **tutor** on each card: Socratic, hint-only, given the card, its LO, the worked solution and the learner's recent misses; it never prints the answer, and its use is logged with the attempt (Bastani's guardrail; Kestin's rules).
- *Not:* writing or approving course material. It may later suggest *distractors* or *rewordings* into Drafts, never directly into study.

## 10. The checker (check-deck v2)
Refuses a course that breaks: the schema; one verb per LO; every card linked to an LO; ≥ 2 practice + 1 check per LO; no cycles in `requires`; the rubric (R1–R5 from 4.24.0); every `source_ref` resolves (file and symbol exist at the commit; URLs answer; DOIs resolve); every `write` / `parsons` / `drill` answer parses (`ast` for Python; a C# parse check later); citations in one format (section 12).

## 11. Anki export (later, optional)
Write a course's cards as an `.apkg` (genanki; licence to confirm) so the material is never locked in. Not part of the first phases.

## 12. Sources shown to the learner
One line each, one format: **Author(s) (year). *Title.* Venue.** + one button: *Open paper* (URL/DOI), *Find it* (book: library search), *Open note* (the owner's research note). Shown behind "Show the full answer and sources", and in Card info. Never inside a card's text.

## 13. Worked example: course "Rebuild Elaia's server"
Terminal LOs (create): build a stdlib HTTP server that serves a static page and JSON; reject unsafe requests (host allowlist, JSON-only POST, Origin check); control `systemd --user` units safely; load plugins at start-up; cache an outside API.
| Module | Built from | Example LOs |
|---|---|---|
| 1. Python you need | the whole file | trace a dict/list comprehension (understand·read); write a function with an early return (apply·write) |
| 2. Serving pages | `H.do_GET`, `out()`, `path_parts()`, `page()` | predict the response to a URL (understand·read); write a route (apply·write) |
| 3. Safe POSTs | `do_POST`, `host_ok()`, `deny()` | explain why a cross-site POST is refused (understand); find the bug in a weakened check (analyse) |
| 4. Talking to systemd | `run()`, `sc()`, `units()`, `info()`, `freeze()` / `thaw()` | trace a `systemctl` call and its output parsing; choose between `run` and `run_ok` (evaluate) |
| 5. Plugins | `plugin_dirs()`, `manifest()`, `load_server_plugins()`, `plugin_call()` | explain how a plugin is found and loaded; modify a manifest check |
| 6. Weather cache | `sky.py` | write the cache function (apply·write); explain the atomic write |
| 7. Tools around it | `scripts/build.sh`, git, GitHub PRs, CI | do a branch → PR → merge cycle; read a CI failure |
| Capstone | – | rebuild a 150-line server with two routes, a host check and a JSON POST, tests provided |

## 14. Phases (one PR each, tests and a real-lesson check every time)
1. **Data model:** courses, modules, lessons, LOs, notes, review-log columns; the old lesson format imports as one "Loose lessons" course. Checker v2.
2. **Study screen** from the mockup: fixed verdict band, Space / 1–4 / Ctrl+Z, interval preview, learning steps, bury siblings, wrapped code, end-of-lesson replay.
3. **Course map** (Lessons): Continue, due reviews, modules with progress and lock state, sources behind a toggle; Sound Lab link and Home tile.
4. **New card roles:** predict, trace, Parsons, write; mastery and unlock rules; module checks.
5. **Course builder** (`/course`) and **Drafts** review in Mentor.
6. **Tutor** on the local model (hint-only), logged.
7. **First course:** "Rebuild Elaia's server", studied by the owner; adjust from the review log.

## 15. Decisions (owner, 2026-10-25)
1. Levels, LO format and unlock rules (sections 3, 4, 8): approved as written.
2. Authoring: Claude Code `/course` sessions + checker + a Drafts review in Mentor; the local model is a hint-only tutor and keeps scoring written answers, never writes course material.
3. Defaults: 1 new lesson a day, 200 reviews a day, desired retention 0.90, bury siblings on, leech at 8 lapses, module pass 80%.
4. Order: UI first: phases 2 and 3 (study screen, course map, Sound Lab link) ship on the existing lessons, then phase 1 and on.

## Sources
Anderson & Krathwohl (2001) revised Bloom – bu.edu/provost/files/2013/10/Anderson-Krathwohl-Revision-to-Blooms-Taxonomy-of-Educational-Objectives.pdf · Fuller et al. (2007) CS learning taxonomy – cs.kent.ac.uk/pubs/2007/2798 · Biggs, constructive alignment – biologie.uzh.ch (ConstructiveAlignment_Biggs.pdf) · Wiggins & McTighe, backward design – cft.vanderbilt.edu/?p=984 · Khan Academy mastery – support.khanacademy.org/hc/en-us/articles/360007253831 · Exercism syllabus – exercism.org/docs/building/tracks/syllabus · Rosenshine (2012) – aft.org/sites/default/files/periodicals/Rosenshine.pdf · Brunmair & Richter (2019) interleaving · Ericson, Parsons problems – hg.gatech.edu/node/603172 · Sentance et al., PRIMM – eprints.gla.ac.uk/229013 · Xie et al. (2019) – faculty.washington.edu/ajko/papers/Xie2019IntroCSTheoryOfInstruction.pdf · Linn & Clancy (1992) case studies – people.eecs.berkeley.edu/~clancy/web/case.studies.html · Van der Kleij et al. (2015) feedback – acuresearchbank.acu.edu.au/item/86y84 · Matuschak, How to write good prompts – andymatuschak.org/prompts · Anki manual – docs.ankiweb.net · Bastani et al. (2025) – papers.ssrn.com/abstract=4895486 · Kestin et al. (2025) – pmc.ncbi.nlm.nih.gov/articles/PMC12179260 · Walters & Wilder (2023) fabricated citations – doaj.org/article/fc88ea07ec994a7c8a144f8516c48cbf
