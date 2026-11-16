# Test stand-in for a bundled server plugin that takes over an agent's section ("agent": true), as Mentor will.
import os

def get(path, query, ctx):
    if path == 'where':
        return 200, {'config_dir': os.path.basename(os.path.dirname(ctx.config_dir)), 'theme_ok': os.path.isfile(os.path.join(ctx.theme_dir, 'theme.json'))}
    if path == 'status': return 200, {'line': '2 workouts this week · 1 skipped', 'needs': True, 'action': 'Log a workout and more words than fit'}
    return 404, {'ok': False, 'msg': 'not found'}
