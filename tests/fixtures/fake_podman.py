#!/usr/bin/env python3
# A stand-in for `podman [--option ...] exec <name> <cmd>` used by the tests. FAKE_PODMAN_DIR holds, per container <name>:
#   <name>.mountinfo   what `cat /proc/self/mountinfo` prints (no file: the container is not running, exit 125)
#   <name>.readable    one path per line that can be read; any other path fails like a dead drive: Input/output error
import os, sys
a = sys.argv[1:]
d = os.environ['FAKE_PODMAN_DIR']
flags = []                         # podman's own options before `exec` (--events-backend=none), written to calls.log for the tests
while a and a[0].startswith('--'): flags.append(a.pop(0))
with open(os.path.join(d, 'calls.log'), 'a') as f: f.write(' '.join(flags + a) + '\n')
if a[:1] != ['exec'] or len(a) < 3: sys.exit(125)
name, cmd = a[1], a[2:]
mi = os.path.join(d, name + '.mountinfo')
if not os.path.exists(mi): print('no such container', file=sys.stderr); sys.exit(125)
if cmd == ['cat', '/proc/self/mountinfo']: sys.stdout.write(open(mi).read()); sys.exit(0)
ok = os.path.join(d, name + '.readable')
readable = open(ok).read().split('\n') if os.path.exists(ok) else []
path = cmd[-1]
if path in readable:
    sys.stdout.write('data\n' if cmd[0] == 'head' else 'entry\n'); sys.exit(0)
print(f'{cmd[0]}: {path}: Input/output error', file=sys.stderr); sys.exit(1)
