#!/bin/bash
# install.sh - run on the machine to watch, from the unpacked package folder: bash install.sh
# Installs to ~/.local/bin/argus-ui + ~/.local/share/argus-ui/static and runs it as a systemd --user service.
# An existing install is MOVED to ~/.local/share/argus-ui/.set-aside-<date>/ (never deleted). Your sounds: ~/.config/argus-ui/sfx/
#   PORT=8095 (default)      TAILSCALE_PATH=/argus  -> also publish on your tailnet (needs sudo once)
set -e
D=$(cd "$(dirname "$0")" && pwd); S=~/.local/share/argus-ui; U=~/.config/systemd/user; PORT=${PORT:-8095}
mkdir -p $S ~/.local/bin $U; B=
if [ -e ~/.local/bin/argus-ui ] || [ -d $S/static ]; then
  B=$S/.set-aside-$(date +%F-%H%M); mkdir -p $B
  [ -e ~/.local/bin/argus-ui ] && cp -a ~/.local/bin/argus-ui $B/argus-ui.py
  [ -d $S/static ] && mv $S/static $B/static
  [ -d $S/bundled ] && mv $S/bundled $B/bundled
  echo "== previous version kept in $B"
fi
cp "$D/argus_ui.py" ~/.local/bin/argus-ui; chmod +x ~/.local/bin/argus-ui
cp "$D/mentor.py" $S/mentor.py; cp "$D/sky.py" $S/sky.py; mkdir -p $S/decks   # your own decks go in ~/.local/share/argus-ui/decks
cp -r "$D/static" $S/static
mkdir -p $S/bundled; cp -r "$D/bundled/." $S/bundled/ 2>/dev/null || true   # plugins that ship with Elaia; yours in ~/.config/argus-ui/plugins win on the same id
# your own sounds live in ~/.config/argus-ui/sfx/ and are added on every install, so a package built from git
# (which carries no sound files) keeps them. The first time, it is filled from the sounds already installed.
X=~/.config/argus-ui/sfx; mkdir -p $X
[ -n "$B" ] && [ -d $B/static/sfx ] && for f in $B/static/sfx/*.mp3; do [ -e "$f" ] && [ ! -e "$X/$(basename "$f")" ] && cp "$f" $X/; done
for f in "$D"/static/sfx/*.mp3; do [ -e "$f" ] && [ ! -e "$X/$(basename "$f")" ] && cp "$f" $X/; done
cp $X/*.mp3 $S/static/sfx/ 2>/dev/null && echo "== sounds: $(ls $X/*.mp3 2>/dev/null | wc -l) from $X" || echo "== no sound files (the page works silently; put .mp3s in $X)"
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
# weather for the background scene: WEATHER=<lat>,<lon> ./install.sh  (kept in ~/.config/argus-ui/weather.json; add UNITS=c for Celsius)
if [ -n "$WEATHER" ]; then mkdir -p ~/.config/argus-ui
  printf '{"lat": %s, "lon": %s, "units": "%s"}\n' "${WEATHER%%,*}" "${WEATHER##*,}" "${UNITS:-f}" > ~/.config/argus-ui/weather.json
  echo "== weather location saved (~/.config/argus-ui/weather.json)"; fi
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
curl -s http://127.0.0.1:$PORT/api/sky | python3 -c 'import json,sys; d=json.load(sys.stdin); print("== weather:", d.get("desc") or d.get("reason"), d.get("temp", ""), d.get("unit", ""))' 2>/dev/null || true
TS=$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null)
if [ -n "$TS" ]; then
  curl -s -o /dev/null -w "== over Tailscale HTTPS: HTTP %{http_code}  ->  https://$TS/argus/\n" https://$TS/argus/ || echo "== Tailscale HTTPS not answering. Run once: sudo tailscale serve --bg --set-path /argus http://127.0.0.1:$PORT"
fi
grep -q '0.0.0.0' $U/argus-ui.service.d/bind.conf 2>/dev/null && echo "== also on your LAN: http://$(hostname):$PORT" || true
if [ -n "$TAILSCALE_PATH" ]; then sudo tailscale serve --bg --set-path $TAILSCALE_PATH http://127.0.0.1:$PORT && tailscale serve status; fi
