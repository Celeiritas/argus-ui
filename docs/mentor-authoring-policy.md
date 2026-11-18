# Mentor authoring policy

The policy lessons are written and checked against lives in `plugins/mentor/policy.json` (`"id": "mentor-policy/1"`). It is small on purpose: eight rules, each with one **bad** example (a lesson item that went wrong) and one **good** rewrite. Those pairs are the regression examples: a new authoring command or prompt should hold the bad ones and pass the good ones.

| Rule | In short |
|---|---|
| `git-steps` | Fetch, integrate, commit and push are four different steps. |
| `language-evaluator` | Grade code in its own language; a predicted output keeps every sign. |
| `state-assumptions` | State every assumption that changes the solution. |
| `no-leak-keep-data` | The front never prints what it asks for; an application keeps the numbers it needs. |
| `scope-of-findings` | One study's threshold is not a universal limit; "not significant" is not "the same". |
| `vocabulary-first` | Teach the words before asking for an explanation that uses them. |
| `refine-not-repeat` | The same concept again revises its one lesson, with a reason. |
| `concrete-answers` | Ask for a concrete prediction or decision, not "test with users". |

**How it is used.** Every lesson's evidence names the policy id it was checked against (`docs/mentor.md` "Clean slate and publication"). The server holds a lesson whose evidence names another policy, so changing the rules means a new id (`mentor-policy/2`), never editing `/1` in place. Lessons published under an older policy stay published.

**Changing it.** Add a rule only with a real bad example from a lesson, and a good rewrite that would pass. Keep each rule one or two sentences.
