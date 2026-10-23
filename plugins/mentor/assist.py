"""Mentor's local AI (docs/mentor-ai.md): optional, off unless ~/.config/argus-ui/mentor-ai.json turns it on.

A model server on this machine (Ollama, or anything OpenAI-compatible: llama.cpp's llama-server, LM Studio, vLLM) adds
  - a meaning score: embeddings of your answer and the model answer, compared (cosine), one more feature next to the rubric
  - optional feedback: two or three sentences from a small chat model about what the answer got and missed
Shadow mode by default: both are stored with the attempt and shown, labelled, but the rubric still suggests the rating.
The rubric never waits for the AI: Mentor answers at once and the AI's part arrives later (plugin.py runs it in a thread).
Answers about your code stay home: the server must be on this machine unless the config says "allow_remote": true.
Standard library only.
"""
import json, math, os, sys, time, urllib.request, urllib.error
from urllib.parse import urlsplit

CONFIG = os.path.expanduser(os.environ.get('ARGUS_MENTOR_AI', '~/.config/argus-ui/mentor-ai.json'))
DEFAULTS = {'enabled': False, 'api': 'ollama', 'url': 'http://127.0.0.1:11434', 'embed_model': 'nomic-embed-text',
            'chat_model': '', 'feedback': False, 'use_in_grade': False, 'timeout_s': 20, 'allow_remote': False}
LOCAL = {'127.0.0.1', 'localhost', '::1'}
_cfg = [None, None]                     # config file mtime when last read, and the checked config
_told = set()                           # problems already logged: one line each, not one per answer
_alive = [0.0, None]                    # when the server was last asked, and whether it answered

def log_once(msg):
    if msg not in _told:
        _told.add(msg); print(f'argus-ui: mentor ai: {msg}', file=sys.stderr, flush=True)

def config():
    """The checked config. A missing file means off; a broken one means off with one log line. Read again when it changes."""
    try: mt = os.stat(CONFIG).st_mtime
    except OSError: return dict(DEFAULTS, problem='')
    if _cfg[0] == mt: return _cfg[1]
    c = dict(DEFAULTS, problem='')
    try:
        with open(CONFIG, encoding='utf-8') as f: doc = json.load(f)
        if not isinstance(doc, dict): raise ValueError('not a JSON object')
        c.update({k: doc[k] for k in DEFAULTS if k in doc})
        if c['api'] not in ('ollama', 'openai'): raise ValueError(f"api {c['api']!r} is not ollama or openai")
        u = urlsplit(str(c['url']))
        if u.scheme not in ('http', 'https') or not u.hostname: raise ValueError(f"url {c['url']!r} is not http(s)://host:port")
        if u.hostname not in LOCAL and c['allow_remote'] is not True:
            raise ValueError(f'url host {u.hostname} is not this machine; answers about your code stay home unless "allow_remote": true')
        c['timeout_s'] = max(2, min(120, int(c['timeout_s'])))
        c['enabled'] = c['enabled'] is True
    except Exception as e:
        c = dict(DEFAULTS, problem=str(e)); log_once(f'{CONFIG}: {e} (the local AI stays off)')
    _cfg[:] = [mt, c]
    return c

def _call(c, path, body=None, timeout=None):
    req = urllib.request.Request(c['url'].rstrip('/') + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'}, method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout or c['timeout_s']) as r:
        return json.loads(r.read().decode('utf-8') or '{}')

def status():
    """For the page: is it on, which models, does the server answer (asked at most once a minute)."""
    c = config()
    out = {'enabled': c['enabled'], 'api': c['api'], 'embed_model': c['embed_model'], 'chat_model': c['chat_model'],
           'feedback': c['feedback'] and bool(c['chat_model']), 'use_in_grade': c['use_in_grade'], 'problem': c['problem'], 'answering': None}
    if c['enabled'] and not c['problem']:
        if time.time() - _alive[0] > 60:
            try: _call(c, '/api/tags' if c['api'] == 'ollama' else '/v1/models', timeout=3); ok = True
            except Exception as e: ok = False; log_once(f"{c['url']} is not answering ({e.__class__.__name__})")
            _alive[:] = [time.time(), ok]
        out['answering'] = _alive[1]
    return out

def embed(c, texts):
    if c['api'] == 'ollama':
        return _call(c, '/api/embed', {'model': c['embed_model'], 'input': texts})['embeddings']
    return [d['embedding'] for d in _call(c, '/v1/embeddings', {'model': c['embed_model'], 'input': texts})['data']]

def cosine(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0

FEEDBACK = ("You are a patient tutor. A learner answered a question about code they built. In two or three short sentences, "
            "say which key ideas the answer got and which it missed, compared with the model answer. Plain words, no lists, "
            "no praise padding, never invent facts that are not in the model answer.")

def chat(c, prompt, reference, answer):
    msgs = [{'role': 'system', 'content': FEEDBACK},
            {'role': 'user', 'content': f'Question: {prompt}\n\nModel answer: {reference}\n\nLearner\'s answer: {answer}'}]
    if c['api'] == 'ollama':
        r = _call(c, '/api/chat', {'model': c['chat_model'], 'messages': msgs, 'stream': False, 'options': {'temperature': 0.2, 'num_predict': 160}})
        return (r.get('message') or {}).get('content', '').strip()
    r = _call(c, '/v1/chat/completions', {'model': c['chat_model'], 'messages': msgs, 'temperature': 0.2, 'max_tokens': 160})
    return ((r.get('choices') or [{}])[0].get('message') or {}).get('content', '').strip()

def judge(prompt, reference, answer):
    """The AI's part for one attempt: {'similarity', 'feedback', 'model', 'ms'} or {'error'}. Never raises."""
    c = config(); t0 = time.time()
    if not c['enabled'] or c['problem']: return {'error': 'off'}
    out = {'model': c['embed_model']}
    try:
        a, b = embed(c, [answer or ' ', reference or ' '])
        out['similarity'] = round(max(0.0, cosine(a, b)), 3)
        if c['feedback'] and c['chat_model'] and answer.strip():
            out['feedback'] = chat(c, prompt, reference, answer)[:600]; out['chat_model'] = c['chat_model']
    except Exception as e:
        log_once(f"{c['url']}: {e.__class__.__name__}: {str(e)[:120]}")
        return {'error': 'not answering'}
    out['ms'] = int((time.time() - t0) * 1000)
    return out
