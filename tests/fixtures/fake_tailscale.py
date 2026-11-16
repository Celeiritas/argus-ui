#!/usr/bin/env python3
"""A stand-in for `tailscale status --json` (tests/devices_test.py, tests/devices.test.js; docs/devices.md).
It answers devices/tailscale-status.json beside it. devices/tailscale-mode, when there, changes that:
  ok (the default), fail (exit 1), hang (sleeps past the probe's timeout), garbage (not JSON), stopped (BackendState Stopped),
  flood (writes without end, to test the size limit while reading)."""
import os, sys, time
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devices')
if sys.argv[1:] != ['status', '--json']: sys.exit('fake tailscale: only "status --json"')
try: mode = open(os.path.join(here, 'tailscale-mode')).read().strip()
except OSError: mode = 'ok'
if mode == 'fail': sys.exit('fake tailscale: failed on purpose')
if mode == 'hang': time.sleep(30)
if mode == 'flood':
    try:
        while True: sys.stdout.buffer.write(b'{' * 65536)
    except (BrokenPipeError, OSError): sys.exit(0)
if mode == 'garbage': print('this is not JSON'); sys.exit(0)
doc = open(os.path.join(here, 'tailscale-status.json'), encoding='utf-8').read()
if mode == 'stopped': doc = doc.replace('"BackendState": "Running"', '"BackendState": "Stopped"')
sys.stdout.write(doc)
