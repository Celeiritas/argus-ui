---
name: mentor-deck-writing
description: Write or fix a Mentor lesson or deck so it teaches in plain words. Use when creating, editing or reviewing a lesson JSON (themes/*/decks, a Mentor inbox file, /mentor output) or when someone says the cards are unclear or cluttered.
---

# Writing a Mentor lesson or deck

1. Read `docs/mentor-rubric.md` (the five rules) and the format in `docs/mentor-command.md` §4.
2. Run `python3 scripts/check-deck.py <file or folder>` (on Windows: `python`). Fix every ERROR; look at each WARN.
3. For the parts the script can't check, use the skills the rubric's table names (they sit next to this one, CC BY-SA 4.0: `.claude/skills/LICENSE-education-skills.md`). `cognitive-load-analyser` first when a card feels crowded.
4. When editing a shipped deck, keep every card `id`, the number of terms, drills and explain cards, and each `spot_it.line`: ids carry the learner's history, and `tests/mentor.test.js` relies on the structure. Change wording only, and update a test that quotes the old text.
5. Personal lessons (real machines, paths, hosts) never go in `themes/`: they go in the Mentor inbox or the decks folder on the host.
