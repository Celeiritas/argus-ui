#!/bin/bash
# tests/run.sh - build the package, run it against fake systemd units, and run the browser checks.
#   bash tests/run.sh            all checks          bash tests/run.sh olympus      just tests/olympus.test.js
#   bash tests/run.sh demo       records docs/screenshots/preview.gif for the README (needs ffmpeg)
# Needs python3, node and Playwright with Chromium (npm install; npx playwright install chromium).
# Nothing outside a temporary folder is touched: a throwaway HOME, fake systemctl/journalctl, a saved weather reading.
set -e
R=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d); PORT=${PORT:-8097}
export NODE_PATH="${NODE_PATH:-$R/node_modules:$(npm root -g 2>/dev/null)}"
TH=${THEME:-leafy-realm}; bash "$R/scripts/build.sh" $TH >/dev/null; V=$(cat "$R/VERSION")
mkdir -p "$T/pkg" "$T/home/.cache/argus-ui" "$T/fx"; tar xzf "$R/dist/argus-ui-$V-$TH.tar.gz" -C "$T/pkg"
cp "$R"/tests/fixtures/* "$T/fx/"; chmod +x "$T"/fx/*.py "$T"/fx/*.sh
# LeafyPlugins: the demo plugin(s) live where installs keep them, inside the throwaway HOME
mkdir -p "$T/home/.config/argus-ui/plugins"; cp -r "$R"/tests/plugin-fixtures/. "$T/home/.config/argus-ui/plugins/"
# and bundled ones, as an install puts them next to Elaia (an agent-claiming plugin, and a demo-server that yours replaces)
cp -r "$R"/tests/bundled-fixtures/. "$T/pkg/bundled/"
python3 -c "import json,time,sys; json.dump({'sky':'rain','desc':'Light rain','is_day':True,'temp':48,'unit':'F','precip':.6,'clouds':90,'wind':14,'south':False,'at':int(time.time()),'source':'Open-Meteo'}, open(sys.argv[1],'w'))" "$T/home/.cache/argus-ui/sky.json"
HOME="$T/home" ARGUS_DEV=1 ARGUS_WEATHER=40,-111 ARGUS_STATIC="$T/pkg/static" ARGUS_BUNDLED="$T/pkg/bundled" ARGUS_SYSTEMCTL="$T/fx/fake_systemctl.py" ARGUS_JOURNALCTL="$T/fx/fake_journal.sh" ARGUS_PORT=$PORT \
  python3 "$T/pkg/argus_ui.py" > "$T/server.log" 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null; echo "(server log and screenshots: $T)"' EXIT
for i in $(seq 50); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep .2; done
fail=0
if [ "$1" = demo ]; then   # bash tests/run.sh demo: record the README preview GIF
  BASE="http://127.0.0.1:$PORT/argus/" FIXTURES="$T/fx" SHOTS="$T" node "$R/tests/demo.js" || exit 1
  ffmpeg -loglevel error -y -ss 1.5 -i "$T/demo.webm" -vf "setpts=PTS/1.5,fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" "$R/docs/screenshots/preview.gif"
  echo "== wrote docs/screenshots/preview.gif ($(du -h "$R/docs/screenshots/preview.gif" | cut -f1))"; exit 0
fi
for t in "$R"/tests/${1:-*}.test.js; do
  echo "== $(basename "$t" .test.js)"
  BASE="http://127.0.0.1:$PORT/argus/" FIXTURES="$T/fx" SHOTS="$T" node "$t" || fail=1
done
[ $fail = 0 ] && echo "== all checks passed (version $V)" || echo "== some checks failed"
exit $fail
