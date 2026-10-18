# Changelog

## 4.3.0 – 2026-10-18
- **Section bar**: Argus · Watch (default), Mentor · Practice, and themed "coming later" sections (Spartamelee · Play in the Leafy Realm theme)
- Mentor gets his own page: his medallion takes the centre, and Argus keeps watch from the corner (select him to go back to watching)
- **Alerts**: when a task fails, all of Argus's eyes turn red and glow, a red aura pulses, an alarm badge counts the failures (also on the Argus section button), and a short chime plays when something newly fails (muted with Mute sounds)
- Eyes redrawn to match the medallion's almond eyes and cover them, so a blink no longer shows a second eye behind; blinks close to a lid line; the top grey eye has a pupil

## 4.2.2 – 2026-10-18
- Practice ratings in plain words: Very well (quick, easy recall), Well enough (took moderate thought), Not well (hard to remember or explain), Needs work (run this card again soon)
- Each choice shows when the card will come back; Mentor's suggestion is preselected
- Rating is now pick-then-confirm: a verb button follows your choice ("Run again in 10 min" or "Save and next card"); keys 1–4 choose in on-screen order, Enter confirms

## 4.2.1 – 2026-10-18
- Mentor medallion: hooded dark grey robe, broad-shouldered torso, scraggly beard, Athena's owl with wing lines, a tan scroll rolled top and bottom

## 4.2.0 – 2026-10-18
- **Mentor / Practice tab**: typed-answer flashcards with key-idea (rubric) grading, model answers, coaching notes, confidence and calibration tracking, FSRS-4.5 spaced repetition, keys 1–4 to rate, "Practice ahead" when caught up
- Every attempt is saved with grading features and your final rating, as training data for a future learning grader (docs/mentor.md)
- Decks: UX & HCI terms (25), Psych behind design (8), AI-assisted coding habits (9); add your own in `~/.local/share/argus-ui/decks/`
- Ultrawide: Argus scales with the window (up to 360px), content column widens to 1600px, header aligns with it
- Mentor agent in the Leafy Realm theme (icon draft)

## 4.1.0 – 2026-10-18
UX audit (VectorLab UX skills) and security review.
- **Type:** 16/14/12px scale (no text under 12px), task details at 14px, weights 400/600 only, body line-height 1.5
- **Targets:** every control has a 44px hit area; nav links and the log toggle are 44px tall
- **Keyboard:** Medusa and Zeus's bolt are real buttons. Press one, then Enter on a task (Esc cancels). Tooltips show on hover *and* focus. Argus's eyes follow keyboard focus too.
- **Confirm before interrupting:** freezing or restarting a task that is running right now asks first (named task, Cancel focused, Esc cancels). Freezing anything else offers **Undo**.
- **Copy:** verb-first buttons ("Show log", "Mute sounds"), plain-language results, errors say what happened and what to do next
- **Motion:** UI transitions use 150/200/300ms tokens and only transform/opacity; tools fly with transforms; reduced-motion skips particles and strikes (fade only); Argus stops wandering/blinking under reduced motion
- **Layout:** header is full width (only main content is capped); counts are plain text, not pills; sound toggle moved into the nav
- **Security:** CSRF and DNS-rebinding protection, `ARGUS_BIND`, `ARGUS_ALLOWED_HOSTS`, safe static paths, body size cap, `</script>` escaping, a lock around freeze/thaw, atomic frozen-list writes, and systemctl failures are reported instead of ignored

## 4.0.0 – 2026-10-18
First version in this repository. Same features as the author's "v4" home install, generalized:
- Agent list, titles and registry folder come from the theme (`theme.json`) instead of being hard-coded
- Build script (`scripts/build.sh <theme>`) and generic installer (`scripts/install.sh`, keeps the previous version)
- Large centered Argus with pointer-tracking, blinking, glaring eyes
- Compact task cards, persona pages at `<base>/<agent>`
- Medusa freeze/thaw with green stone effects (sounds optional, bring your own); Zeus's bolt run/restart with lightning effect and sound
- Works directly on a port or behind `tailscale serve --set-path /argus`; installable as a phone app

## Earlier (before this repo)
- v3 – persona groups with medallion icons, moving eyes, Medusa freeze/thaw (frost/fire), Tailscale path
- v2 – first web page (status cards, Run now)
