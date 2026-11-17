#!/usr/bin/env python3
# A stand-in Mealie for the Mealie section's checks (plugins/mealie, docs/mealie.md); never the real one. It answers the two
# routes the plugin asks, in the shape of Mealie v3.30.0, and only with the right Bearer token:
#   GET /api/households/mealplans?start_date=&end_date=&perPage=&page=   a page of plan entries
#   GET /api/users/self                                                   {"groupSlug": ...}
# What it answers comes from a scenario file, read on every request so a check can change it between asks:
#   {"mode": "ok" | "refuse" | "slow" | "garbage" | "redirect" | "huge", "token": "<the token it accepts>", "group": "kitchen",
#    "delay": 2, "plan": [{"in_days": 0, "entryType": "dinner", "recipe": {"name": "...", "slug": "..."}, "title": ""}, ...]}
# in_days counts from today on this machine. Every request is recorded as {"path", "auth"} in .seen (and appended to
# <scenario>.seen.jsonl when run as a program), so a check can see what reached it, the redirect's target included.
#   python3 tests/fixtures/fake_mealie.py <port> <scenario.json>
import datetime, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

def make_server(port, scenario, log=None):
    seen = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def send(self, code, obj, extra=None):
            b = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b)))
            for k, v in (extra or {}).items(): self.send_header(k, v)
            self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            rec = {'path': self.path, 'auth': self.headers.get('Authorization') or ''}
            seen.append(rec)
            if log:
                with open(log, 'a', encoding='utf-8') as f: f.write(json.dumps(rec) + '\n')
            try:
                with open(scenario, encoding='utf-8') as f: s = json.load(f)
            except (OSError, ValueError): s = {}
            mode = s.get('mode', 'ok')
            if self.path.startswith('/caught'): return self.send(200, {'caught': True})
            if mode == 'slow': time.sleep(float(s.get('delay', 2)))
            if rec['auth'] != 'Bearer ' + str(s.get('token', '')) or mode == 'refuse':
                return self.send(401, {'detail': 'Could not validate credentials'})
            if mode == 'redirect': return self.send(302, {}, {'Location': f'http://127.0.0.1:{self.server.server_port}/caught'})
            if mode == 'garbage': return self.send(200, b'<html>not json</html>')
            u = urlsplit(self.path)
            if u.path == '/api/users/self': return self.send(200, {'id': 'u1', 'username': 'cook', 'groupSlug': s.get('group', 'kitchen'), 'householdSlug': 'family'})
            if u.path != '/api/households/mealplans': return self.send(404, {'detail': 'Not Found'})
            if mode == 'huge': return self.send(200, b'{"items": [' + b'"x",' * 400000 + b'"x"]}')
            q = parse_qs(u.query); today = datetime.date.today()
            start = datetime.date.fromisoformat(q['start_date'][0]) if 'start_date' in q else None
            end = datetime.date.fromisoformat(q['end_date'][0]) if 'end_date' in q else None
            items = []
            for i, e in enumerate(s.get('plan', [])):
                d = today + datetime.timedelta(days=int(e.get('in_days', 0)))
                if (start and d < start) or (end and d > end): continue
                r = e.get('recipe')
                items.append({'date': d.isoformat(), 'endDate': None, 'entryType': e.get('entryType', 'dinner'), 'title': e.get('title', ''),
                              'text': e.get('text', ''), 'recipeId': 'r%d' % i if r else None, 'recipeScale': 1.0, 'id': i + 1,
                              'groupId': 'g', 'userId': 'u1', 'householdId': 'h',
                              'recipe': dict({'id': 'r%d' % i, 'groupId': 'g', 'householdId': 'h'}, **r) if r else None})
            self.send(200, {'page': 1, 'perPage': int(q.get('perPage', ['50'])[0]), 'total': len(items) + int(s.get('extra_total', 0)),
                            'totalPages': 1, 'items': items, 'next': None, 'previous': None})

    srv = ThreadingHTTPServer(('127.0.0.1', port), H); srv.daemon_threads = True
    srv.handle_error = lambda *a: None       # a client that gave up on a slow answer is expected, not news
    srv.seen = seen
    return srv

def start(scenario):
    """For checks in the same process: a server on a free port, serving on a thread. Returns it (.server_port, .seen)."""
    srv = make_server(0, scenario); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv

if __name__ == '__main__':
    make_server(int(sys.argv[1]), sys.argv[2], sys.argv[2] + '.seen.jsonl').serve_forever()
