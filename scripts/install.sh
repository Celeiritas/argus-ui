#!/bin/bash
# install.sh - run on the machine to watch, from the unpacked package folder: bash install.sh
# Installs to ~/.local/bin/argus-ui + ~/.local/share/argus-ui/static and runs it as a systemd --user service.
# An existing install is MOVED to ~/.local/share/argus-ui/.set-aside-<date>/ (never deleted).
#   PORT=8095 (default)      TAILSCALE_PATH=/argus  -> also publish on your tailnet (needs sudo once)
set -e
D=$(cd "$(dirname "$0")" && pwd); S=~/.local/share/argus-ui; U=~/.config/systemd/user; PORT=${PORT:-8095}
mkdir -p $S ~/.local/bin $U
if [ -e ~/.local/bin/argus-ui ] || [ -d $S/static ]; then
  B=$S/.set-aside-$(date +%F-%H%M); mkdir -p $B
  [ -e ~/.local/bin/argus-ui ] && cp -a ~/.local/bin/argus-ui $B/argus-ui.py
  [ -d $S/static ] && mv $S/static $B/static
  echo "== previous version kept in $B"
fi
cp "$D/argus_ui.py" ~/.local/bin/argus-ui; chmod +x ~/.local/bin/argus-ui
cp "$D/mentor.py" $S/mentor.py; mkdir -p $S/decks   # your own decks go in ~/.local/share/argus-ui/decks
cp -r "$D/static" $S/static
if [ ! -f $U/argus-ui.service ]; then
cat > $U/argus-ui.service <<UNIT
[Unit]
Description=Argus UI - agent and task dashboard (port $PORT)
[Service]
Environment=ARGUS_PORT=$PORT
ExecStart=/usr/bin/python3 %h/.local/bin/argus-ui
Restart=on-failure
[Install]
WantedBy=default.target
UNIT
fi
# listen address: this machine only by default, reached from other devices through `tailscale serve` (HTTPS).
# Kept across upgrades; to allow plain http on your LAN instead: BIND=0.0.0.0 ./install.sh (or edit the file below).
mkdir -p $U/argus-ui.service.d
if [ ! -f $U/argus-ui.service.d/bind.conf ] || [ -n "$BIND" ]; then
  printf '[Service]\nEnvironment=ARGUS_BIND=%s\n' "${BIND:-127.0.0.1}" > $U/argus-ui.service.d/bind.conf
  echo "== listening on ${BIND:-127.0.0.1} ($U/argus-ui.service.d/bind.conf)"
fi
systemctl --user daemon-reload; systemctl --user enable argus-ui >/dev/null 2>&1; systemctl --user restart argus-ui; sleep 2
echo "== argus-ui $(cat $S/static/VERSION 2>/dev/null): $(systemctl --user is-active argus-ui)"
curl -s -o /dev/null -w "== page on this machine: HTTP %{http_code}\n" http://127.0.0.1:$PORT/ || true
TS=$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null)
if [ -n "$TS" ]; then
  curl -s -o /dev/null -w "== over Tailscale HTTPS: HTTP %{http_code}  ->  https://$TS/argus/\n" https://$TS/argus/ || echo "== Tailscale HTTPS not answering. Run once: sudo tailscale serve --bg --set-path /argus http://127.0.0.1:$PORT"
fi
grep -q '0.0.0.0' $U/argus-ui.service.d/bind.conf 2>/dev/null && echo "== also on your LAN: http://$(hostname):$PORT" || true
if [ -n "$TAILSCALE_PATH" ]; then sudo tailscale serve --bg --set-path $TAILSCALE_PATH http://127.0.0.1:$PORT && tailscale serve status; fi
