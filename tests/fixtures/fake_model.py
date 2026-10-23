#!/usr/bin/env python3
# A stand-in local model server for the Mentor AI checks (docs/mentor-ai.md): Ollama's and OpenAI's routes, answered
# without any model. Embeddings are letter counts, so similar words give similar vectors; feedback is one fixed sentence.
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

def vec(t):
    t = t.lower(); return [t.count(c) for c in 'abcdefghijklmnopqrstuvwxyz'] + [len(t.split())]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, obj):
        b = json.dumps(obj).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path in ('/api/tags', '/v1/models'): return self.send({'models': [{'name': 'fake-embed'}], 'data': [{'id': 'fake-embed'}]})
        self.send_error(404)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if self.path == '/api/embed': return self.send({'embeddings': [vec(t) for t in body['input']]})
        if self.path == '/v1/embeddings': return self.send({'data': [{'embedding': vec(t)} for t in body['input']]})
        text = 'Fake feedback: the answer names the main idea and misses one detail.'
        if self.path == '/api/chat': return self.send({'message': {'role': 'assistant', 'content': text}})
        if self.path == '/v1/chat/completions': return self.send({'choices': [{'message': {'role': 'assistant', 'content': text}}]})
        self.send_error(404)

HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
