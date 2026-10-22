# Test stand-in for a server plugin (docs/leafy-plugin.md): answers api/demo-server/... from Elaia's server.
import os

CTX = None

def init(ctx):
    # called once at startup; data_dir is this plugin's own folder for files it keeps
    global CTX
    CTX = ctx
    with open(os.path.join(ctx.data_dir, 'started.txt'), 'w') as f: f.write(ctx.version)

def get(path, query, ctx):
    if path == 'ping':
        return 200, {'pong': True, 'id': ctx.id, 'data_dir_ok': os.path.isfile(os.path.join(CTX.data_dir, 'started.txt')),
                     'user': ctx.headers.get('Tailscale-User-Login'), 'q': (query.get('q') or [''])[0]}
    if path == 'status': return 200, {'line': '1 ping answered · all well'}
    if path == 'boom': raise RuntimeError('a plugin bug')
    return 404, {'ok': False, 'msg': 'not found'}

def post(path, body, ctx):
    if path == 'echo': return 200, {'ok': True, 'echo': str(body.get('text', ''))[:100]}
    return 404, {'ok': False, 'msg': 'not found'}
