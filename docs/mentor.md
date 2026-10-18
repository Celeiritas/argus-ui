# Mentor – Practice
Spaced-repetition practice with typed answers, built into Argus UI. Open `<base>/mentor` (**Mentor · Practice** in the section bar).

## How a card works
1. Read the prompt, type your answer in your own words (or leave it blank), and say how sure you are.
2. Mentor checks which **key ideas** you covered, shows the model answer, and suggests a rating.
3. You pick how well you knew it (Very well / Well enough / Not well / Needs work, or keys 1–4), then confirm with the button. Each choice shows when the card returns ([FSRS-4.5](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm) scheduling; internally Easy / Good / Hard / Again, stored as 4–1).
4. If Mentor's grade was off, tick **Mentor's grade was wrong**. That flag is training data for the learning grader.

The stats line also tracks **calibration**: how your confidence compares with what you actually covered.

## Grading roadmap
| Stage | Grader | Status |
|---|---|---|
| A | Key-point rubric: each card lists key ideas with accepted wordings; typos and word endings tolerated | **4.2.0** |
| B | Local similarity model adds a meaning-based score (runs on your own machine) | planned |
| Bv2 | A small model trained on *your* saved attempts (features + your ratings + "grade was wrong" flags) predicts grades and coaching hints | planned; data is collected from the first answer |

Every attempt is stored in `~/.local/share/argus-ui/mentor.db` (`attempts` table): answer, confidence, time taken, rubric features, suggested and final rating.

## Deck format
Built-in decks ship in the theme (`themes/<theme>/decks/`). Your own go in `~/.local/share/argus-ui/decks/` and load on restart; editing a deck keeps your history.
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
