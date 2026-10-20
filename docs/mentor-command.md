---
description: Silently extract a 3-tier Cognitive Task Analysis JSON (Mentor module) from recent code changes into ./mentor_inbox/ without polluting chat context.
---

# STEALTH TELEMETRY & COGNITIVE TASK ANALYSIS (CTA) EXPORT

## 1. OPERATIONAL DIRECTIVE (STERILE CONTEXT RULE)
You are executing an out-of-band knowledge extraction for my external "Mentor" training program. 
- **DO NOT** print the JSON payload, architectural lectures, or flashcard contents into our active chat window. Preserving our conversational context window for production coding is your highest priority (Liu et al., 2024; Monsell, 2003).
- **DO NOT** modify, refactor, or break any existing project source code while running this command.
- Your sole output action is to inspect the target code, write a strictly formatted JSON file to `./mentor_inbox/`, and reply in the chat with a single-line confirmation.

## 2. TARGET SCOPE RESOLUTION
Determine what code to reverse-engineer based on `$ARGUMENTS`:
- If `$ARGUMENTS` is provided (`$ARGUMENTS`), focus your extraction specifically on the files, functions, or concepts mentioned in `$ARGUMENTS`.
- If `$ARGUMENTS` is empty, inspect the most recent code we wrote or modified in this session (or run `git diff HEAD` / `git log -n 1 -p` if needed to see the latest working delta).

## 3. THEORETICAL EXTRACTION PROTOCOL
Decompile the target code using Cognitive Task Analysis (Clark et al., 2008) and the 4C/ID model (Van Merriënboer & Kirschner, 2018) across three cognitive tiers:
1. **Tier 1: Recurrent Skills (Faded Worked Examples):** Isolate 5-to-15 line Minimal Viable Snippets (MVS) that strip out extraneous boilerplate (Sweller et al., 2019). Create a 3-stage backward-fading progression (Renkl & Atkinson, 2003) moving from low cognitive load (terminal syntax/return bindings blanked) to moderate load (control flow/comprehensions blanked) to high load (full body blanked below docstring/signature).
2. **Tier 2: Non-Recurrent Schemas (Self-Explanation Cards):** Create diagnostic prompts utilizing the Self-Explanation Effect (Chi et al., 1989) and Test-Enhanced Learning (Roediger & Karpicke, 2006). Include:
   - `Pre-Mortem`: Inject a subtle bug or invariant violation into a copy of our snippet and ask me to diagnose the failure mode.
   - `Trade-Off`: Ask why this specific design pattern was chosen over a naive alternative and how it scales.
   - `HCI-Bridge`: Connect the code mechanic to Human Factors / HCI engineering (e.g., latency perception, error prevention, mode confusion, developer cognitive ergonomics, state visibility).
3. **Tier 3: Declarative Pre-Training (Terminology Chunks):** Extract key Python, Software Architecture, and Human Factors vocabulary used in the code to support pre-training chunking (Mayer & Pilegard, 2014). Define terms functionally in under 20 words, anchor them to the exact variable/line in our codebase, and contrast them with a commonly confused sibling term.
4. **Tier 0: Learn-first material (teach before test).** Mentor shows these once, before the practice cards, so write them as the lesson, not as tests:
   - `cta_summary.orientation`: 3 sentences in plain words — what the code does, in which files, and what I will be able to do after. `cta_summary.expert_move`: the first thing an expert looks at in this code, one sentence, no answer tokens.
   - For every term: `spot_it` = a 2-6 line snippet from the same code with `line` (1-based) = where the term's instance is and `why` (one sentence); `teach_order` so no term's anchor uses a term taught later; `expert_move` (how to recognise it); `hints` = [a question that points at the principle without naming it, a 2-4 line near example with different names].
   - For every drill: `level_0_worked` = `annotations` (3-6, each `line`, `note` ≤ 8 words, `why` ≤ 25 words, in reading order, saying *why* the line exists, not what it does) and `self_explain` (`prompt` asking why, `rubric` of 1-3 `{idea, any}` ideas); `expert_move`; `look_at` = per level, 1-2 places to look when a blank is wrong; `hints` = per level, [nudge question, near example in different code].
   - For every explain card: `preread` = `key_ideas` (2-4 statements the rubric assumes) and `near_example` (`code`, `ask`, `answer`: the same principle in different code); `expert_move`; `hints` as above.

## 4. FILE SYSTEM EXECUTION & JSON SCHEMA
1. Ensure the directory `./mentor_inbox/` exists (create it if it does not).
2. Generate a filename using the current timestamp and module slug: `./mentor_inbox/YYYYMMDD_HHMMSS_<module_slug>.json`.
3. Write the JSON file matching this exact schema (ensure valid JSON escaping for all code strings):

```json
{
  "metadata": {
    "timestamp": "ISO-8601 String",
    "module_name": "String (e.g., combat_state_machine)",
    "project": "Name of the repository folder (e.g., argus-ui)",
    "source_files": ["List of relative file paths analyzed"],
    "concepts_covered": ["List of Python, Architecture, and HCI tags"],
    "lint": ["Any rule from section 6b this file breaks, one line each (Mentor shows them under the lesson)"]
  },
  "cta_summary": {
    "schematic_mental_model": "2-3 sentences explaining high-level data flow, component coupling, and state transitions.",
    "design_rules_heuristics": "Why this specific design pattern/idiom was chosen over naive alternatives.",
    "hard_rules_invariants": "Strict system constraints that must never be violated (mutability, frame-timing, state safety, Big-O).",
    "hci_human_factors_bridge": "How this backend/UI architecture affects human-in-the-loop performance, error tolerance, or cognitive load.",
    "orientation": "3 sentences, plain words: what this code does, in which files, and what I will be able to do after.",
    "expert_move": "Lesson-level default: the first thing an expert looks at in this code."
  },
  "tier_1_faded_code_drills": [
    {
      "id": "drill_01",
      "file_breadcrumb": "Folder -> File.py -> Class/Function",
      "context_comment": "Brief explanation of what this isolated 5-15 line Minimal Viable Snippet accomplishes and its inputs/outputs.",
      "full_canonical_code": "Clean, idiomatic Python snippet.",
      "level_1_fade": "Code with 1-2 terminal syntax elements or return bindings replaced with {{BLANK_1}}, {{BLANK_2}}.",
      "level_2_fade": "Code with core control flow, comprehensions, or decorators replaced with {{BLANK_1}}, {{BLANK_2}}.",
      "level_3_fade": "Only the function signature, type hints, and docstring constraints—body replaced with {{BLANK_1}}.",
      "answers": {
        "level_1": ["exact string for BLANK_1", "exact string for BLANK_2"],
        "level_2": ["exact string for BLANK_1", "exact string for BLANK_2"],
        "level_3": ["full canonical body implementation"]
      },
      "python_fluency_note": "Why this specific Python syntax is idiomatic (e.g., PEP-8, memory efficiency, generator evaluation, type safety).",
      "expert_move": "The first thing an expert scans for in this snippet, one sentence.",
      "look_at": {"level_1": ["where to look when blank 1 is wrong", "…"], "level_2": ["…"], "level_3": ["…"]},
      "level_0_worked": {
        "annotations": [{"line": 3, "note": "≤ 8 words", "why": "≤ 25 words: why this line exists"}],
        "self_explain": {"prompt": "A why-question about the whole snippet", "rubric": [{"idea": "key idea", "any": ["wording", "another"]}]}
      },
      "hints": {"level_1": ["nudge question", "near example, 2-4 lines, different names"], "level_2": ["…", "…"], "level_3": ["…", "…"]}
    }
  ],
  "tier_2_self_explanation_cards": [
    {
      "id": "card_01",
      "card_type": "Pre-Mortem | Trade-Off | HCI-Bridge",
      "file_breadcrumb": "Folder -> File.py -> Class/Function",
      "front_prompt": "Diagnostic scenario or mutated code snippet containing a subtle bug/anti-pattern.",
      "back_explanation": "Deep architectural or cognitive principle explaining WHY it breaks or WHY the design rule holds.",
      "eval_rubric": [
        {"idea": "Key causal mechanism my typed explanation must mention", "any": ["short phrase", "another wording", "a synonym"]},
        {"idea": "Key invariant or Python mechanic", "any": ["short phrase", "another wording"]},
        {"idea": "System or HCI consequence", "any": ["short phrase", "another wording"]}
      ],
      "expert_move": "The question an expert asks first about this failure mode.",
      "preread": {
        "key_ideas": ["2-4 statements the rubric assumes, taught once before the card"],
        "near_example": {"code": "the same principle in different code", "ask": "What would break here?", "answer": "one line"}
      },
      "hints": ["nudge question", "near example in different code"]
  "tier_3_terminology_cards": [
    {
      "id": "term_01",
      "teach_order": 1,
      "expert_move": "How an expert recognises it, one sentence (no answer tokens).",
      "spot_it": {"snippet": "2-6 lines from our code", "line": 2, "why": "one sentence: what makes that line the instance"},
      "hints": ["A question that points at the principle without naming it", "A 2-4 line near example with different names"],
      "term": "Exact Python, Architecture, or HCI/Human Factors term",
      "category": "Python Syntax | Software Architecture | HCI & Human Factors",
      "concise_definition": "Functional mechanical definition in under 20 words.",
      "project_anchor": "Exact function, class, or variable in our codebase where this concept is implemented.",
      "contrast_anchor": "1-line distinction against a commonly confused sibling term (e.g., 'Unlike X, which does Y...').",
      "cloze_prompt": "A single contextual sentence testing the term, with the term itself replaced by {{BLANK}}."
    }
  ]
}
```

## 5. TERMINAL RESPONSE FORMAT
Once the file is written to disk, output ONLY this single line in the chat and nothing else:
📦 [Mentor CTA Exported] -> ./mentor_inbox/<filename>.json (T1: <count> drills | T2: <count> cards | T3: <count> terms | +<count> learn cards)

## 6. RULES THE MENTOR APP DEPENDS ON (its importer checks these)
- Output pure JSON (no comments, no trailing commas); escape newlines in code strings as `\n`.
- Every `{{BLANK_n}}` in a fade has exactly one matching entry in that level's `answers` list, in order. A blank may accept alternatives: give a list, e.g. `["tmp", "tmp_path"]`.
- `level_3_fade` has exactly one blank, `{{BLANK_1}}`, alone on its own line where the body goes. `answers.level_3[0]` is the body with its indentation relative to that line (first line not indented).
- Drill code is Python. Level 3 answers are checked with Python's parser (never run), so the filled-in fade must be valid Python.
- Each `eval_rubric` item is `{"idea", "any"}`: a phrase counts when all its words appear in my answer (common words, word endings and small typos are ignored), so keep phrases to 1-3 words and give several ways of saying the idea. Plain strings still work but are graded roughly.
- `cloze_prompt` contains `{{BLANK}}` exactly once.
- Front prompts may include code in ``` fences; use `inline code` for names.
- Never put credentials, home-directory paths, hostnames or personal data in any field: the file is copied to another machine.

## 6b. AUTHORING LIMITS (cognitive load; check these before writing, and list any you break in `metadata.lint`)
- Snippets: 5-15 lines, one function or one block. Strip imports, logging and type noise unless they are the point.
- Blanks: level 1 ≤ 2, level 2 ≤ 3, level 3 = 1 (the body). A blank is one token or one expression, never two statements.
- Annotations: 3-6 per drill, each ≤ 25 words, attached to one line number, in reading order; the *why*, not the *what* ("holds the lock so a second request can't fetch too", not "acquires lock").
- One new term per card: a teach card introduces its term only; if its anchor line needs a second new term, give that term an earlier `teach_order`.
- Pre-train: every term used in a drill's annotations has a term card in the same lesson.
- Self-explanation prompts ask *why*, not *what*.
- A Pre-Mortem card always has a `preread`, and its code has a drill with a `level_0_worked` (the correct example before the broken one).
- Hints never contain the answer token for that blank; a near example uses different names.
- All Tier 0 fields are optional: without them Mentor derives plainer Learn cards from the fields above, so an older file still works.

