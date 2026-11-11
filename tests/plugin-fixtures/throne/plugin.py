# Test stand-in for the Throne (Zeus's deploys, the zeus repo): one deploy waits for a yes. Elaia shows it as Approvals.
def get(path, query, ctx):
    if path == 'status': return 200, {'line': '1 deploy waiting · app 9.9.8 live', 'needs': True, 'action': 'Review app 9.9.9', 'count': 1}
    return 404, {'ok': False, 'msg': 'not found'}
def post(path, body, ctx): return 404, {'ok': False}
