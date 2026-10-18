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
systemctl --user daemon-reload; systemctl --user enable argus-ui >/dev/null 2>&1; systemctl --user restart argus-ui; sleep 2
echo "== argus-ui $(cat $S/static/VERSION 2>/dev/null): $(systemctl --user is-active argus-ui)"
curl -s -o /dev/null -w "== page: HTTP %{http_code}  ->  http://$(hostname):$PORT\n" http://127.0.0.1:$PORT/ || true
if [ -n "$TAILSCALE_PATH" ]; then sudo tailscale serve --bg --set-path $TAILSCALE_PATH http://127.0.0.1:$PORT && tailscale serve status; fi
