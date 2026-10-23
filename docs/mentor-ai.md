# Mentor with a local AI

Mentor grades with a rubric (stage A in `plugins/mentor/mentor.py`). A local model can add to it **on your own machine**, with nothing sent anywhere else. The groundwork is in (4.17): turn it on with one config file once you have a model server running. Until then Mentor works exactly as before.

## What it does (and what it doesn't)
- **A meaning score (stage B).** For a written answer (explain and define cards), an embedding model turns your answer and the model answer into vectors and compares them (cosine similarity). It catches a right answer in other words, which the rubric's key-idea matching misses.
- **Feedback (optional).** A small chat model writes two or three sentences on what the answer got and missed, compared with the model answer.
- **Shown, labelled, kept apart.** After you check an answer, the rubric's result appears at once, as always. A moment later Athena's owl brings the AI's part into the result: *"Local AI · <model> · not used for the rating — Meaning match: 82%"* and the feedback. If the model is off, slow or down, no owl appears and nothing waits.
- **Shadow mode.** The AI's part is stored with the attempt (`attempts.ai`) next to the rubric's score and the rating you chose, but **Mentor still suggests the rating from the rubric**. `use_in_grade` is accepted in the config, but nothing uses it yet. Letting the AI move the suggestion comes only after the export shows it agrees with you more often than the rubric does.
- **A grader that learns from you (stage Bv2), later.** `python plugins/mentor/mentor.py export [mentor.db] > attempts.jsonl` writes every rated attempt (prompt, model answer, your answer, the rubric's features, the AI's part, your rating and the "grade was wrong" flag) as training data. The file holds your answers: keep it on your machine.
- **Never:** it never decides a rating alone, never runs your code, never sees anything but the card and your answer, and never talks to a server that isn't this machine unless you say so.

## The config: `~/.config/argus-ui/mentor-ai.json`
```json
{ "enabled": true, "api": "ollama", "url": "http://127.0.0.1:11434",
  "embed_model": "nomic-embed-text", "chat_model": "qwen2.5:3b-instruct",
  "feedback": false, "use_in_grade": false, "timeout_s": 20 }
```
| Field | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Only `true` turns it on. No file means off. |
| `api` | `ollama` | `ollama` (`/api/embed`, `/api/chat`, `/api/tags`) or `openai`: any OpenAI-compatible server, such as llama.cpp's `llama-server`, LM Studio or vLLM (`/v1/embeddings`, `/v1/chat/completions`, `/v1/models`) |
| `url` | `http://127.0.0.1:11434` | Must be this machine (`127.0.0.1`, `localhost`, `::1`) unless `"allow_remote": true` |
| `embed_model` | `nomic-embed-text` | for the meaning score |
| `chat_model` | none | for feedback; empty means no feedback |
| `feedback` | `false` | ask the chat model for feedback |
| `use_in_grade` | `false` | reserved: not used yet (shadow mode) |
| `timeout_s` | `20` | 2–120 s per call to the model server |
| `allow_remote` | `false` | allow a model server on another machine |

- The file is read again when it changes; no restart needed. Another path can be set with `ARGUS_MENTOR_AI`.
- A broken file, an unknown `api` or a remote URL leaves the AI off. The Lessons view says why, and Elaia's log has one line.
- **Status:** the Lessons view shows "Local AI: off", "on (nomic-embed-text, feedback by …)", or "on, but its server is not answering". The server is asked at most once a minute.

## How it fits together
- `plugins/mentor/assist.py`: reads the config and talks to the model server, using the standard library only.
- `plugins/mentor/plugin.py`: after the rubric answers (`POST answer`), it starts the AI's part in a thread and replies `ai_pending: true`. Only one attempt goes to the model at a time. `GET api/mentor/ai?attempt=N` returns `pending`, `done` (with `similarity`, `feedback`, `model`, `ms`), `error` or `none`. `GET api/mentor/ai` alone returns the status.
- `plugins/mentor/page.js` asks every 1.5 s for up to about a minute, then shows the owl's box or quietly gives up.
- Tests: `tests/mentor-ai.test.js` runs against `tests/fixtures/fake_model.py`, a stand-in server with both APIs that `tests/run.sh` starts on `MODEL_PORT` (8098).

## Hardware notes (the home server)
A Ryzen 7 6800H with 24 GB of memory shared with a Radeon 680M integrated GPU, and Podman installed:
- An embedding model (about 140 M parameters, e.g. `nomic-embed-text`) answers in well under a second on the CPU, so the meaning score is cheap.
- A 3 B–8 B chat model at 4-bit quantisation needs about 2–5 GB of memory and writes roughly 8–15 tokens a second on the CPU, faster with Vulkan on the 680M. Feedback of about 60 words takes a few seconds, which is why it arrives after the rubric's result instead of holding it up.
- Run the model server as a `systemd --user` unit named `mentor-<something>` (for example `mentor-ollama`). Argus then watches it on the Watch page like any task, and Medusa can freeze it when you need the memory back.

## Turning it on (when you decide to)
1. Install a model server under your user (Ollama, in Podman or natively, or llama.cpp's `llama-server`) as `mentor-ollama.service`, listening on `127.0.0.1:11434` only.
2. Pull an embedding model and, if you want feedback, a small instruct model.
3. Write `~/.config/argus-ui/mentor-ai.json` as above.
4. Open Mentor's Lessons view: it should say "Local AI: on". Study as usual, and after a few weeks compare with the export.
