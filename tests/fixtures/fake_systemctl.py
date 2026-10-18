#!/usr/bin/env python3
# A stand-in for `systemctl --user` used by the tests: units and their state live in units.json next to this file.
import sys, json, os
F=os.path.join(os.path.dirname(__file__),'units.json')
U=json.load(open(F))
a=[x for x in sys.argv[1:] if x not in('--user','--no-legend','--no-block','--now','--type=service')]
def save(): json.dump(U,open(F,'w'),indent=1)
cmd=a[0]
if cmd=='list-unit-files':
  for n in U: print(n+'.service enabled enabled')
elif cmd=='show':
  unit=a[1]; base,kind=unit.rsplit('.',1); u=U.get(base)
  if not u: print('LoadState=not-found'); sys.exit()
  if kind=='timer':
    if not u.get('timer'): print('LoadState=not-found'); sys.exit()
    print('LoadState=loaded'); print('NextElapseUSecRealtime=Sun 2026-10-25 04:00:00 MDT' if u.get('timer_on') else 'NextElapseUSecRealtime='); print('ActiveState='+('active' if u.get('timer_on') else 'inactive'))
  else:
    for k in ['Result','ActiveState','ExecMainExitTimestamp','ExecMainStartTimestamp','MemoryPeak','IOWriteBytes','Description']: print(f'{k}={u.get(k,"")}')
elif cmd=='is-enabled':
  base,kind=a[1].rsplit('.',1); u=U[base]; print('enabled' if u.get(kind+'_en') else 'disabled')
elif cmd=='is-active':
  base,kind=a[1].rsplit('.',1); print(U[base].get('ActiveState','inactive'))
elif cmd in('stop','start','enable','disable'):
  for unit in a[1:]:
    base,kind=unit.rsplit('.',1); u=U[base]
    if cmd=='enable': u[kind+'_en']=True; 
    if cmd=='disable': u[kind+'_en']=False
    if kind=='timer' and cmd in('stop','disable'): u['timer_on']=False
    if kind=='timer' and cmd in('start','enable') and '--now' in sys.argv or (kind=='timer' and cmd=='start'): u['timer_on']=True
    if kind=='service' and cmd=='stop': u['ActiveState']='inactive'
    if kind=='service' and cmd=='start': u['ActiveState']='active'
  save()
