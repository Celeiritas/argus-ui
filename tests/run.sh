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
# a stand-in local model server for tests/mentor-ai.test.js (docs/mentor-ai.md); off for every other check
MODEL_PORT=${MODEL_PORT:-8098}; python3 "$T/fx/fake_model.py" $MODEL_PORT > "$T/model.log" 2>&1 & MPID=$!; export MODEL_PORT
trap 'kill $PID $MPID 2>/dev/null; echo "(server log and screenshots: $T)"' EXIT
for i in $(seq 50); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep .2; done
fail=0
# the deck rubric (docs/mentor-rubric.md): the shipped decks pass, and the checker still catches each rule
if [ -z "$1" ] || [ "$1" = mentor ]; then
  echo "== deck rubric"
  res=$(python3 "$R/scripts/check-deck.py" "$R"/themes/*/decks "$R/tests/deck-fixtures/good-lesson.json" "$R/tests/deck-fixtures/good-course.json") || { echo "$res"; fail=1; }
  tail -1 <<<"$res"
  out=$(python3 "$R/scripts/check-deck.py" "$R/tests/deck-fixtures/bad-lesson.json") && { echo "FAIL the bad fixture passed"; fail=1; }
  for r in 'ERROR R1 file' 'WARN R1 repo' 'R2 ' 'R3 ' 'R4 ' 'R5 '; do grep -q "$r" <<<"$out" || { echo "FAIL the checker missed: $r"; fail=1; }; done
  grep -q 'drill_01: ERROR R1 file' <<<"$out" && { echo "FAIL a file name inside code was reported"; fail=1; }
  # checker v2 (courses): the bad course breaks each rule once
  out=$(python3 "$R/scripts/check-deck.py" --repo argus-ui="$R" "$R/tests/deck-fixtures/bad-course.json") && { echo "FAIL the bad course passed"; fail=1; }
  for r in C1 C2 C3 C4 C5 C6 C7 C8; do grep -q "ERROR $r " <<<"$out" || { echo "FAIL the course checker missed: $r"; echo "$out"; fail=1; }; done
  grep -q "no_such_function" <<<"$out" && grep -q "no_such_file.py" <<<"$out" || { echo "FAIL a missing symbol or file was not reported"; fail=1; }
  # the good course's code references resolve in this repository at their commit
  out=$(python3 "$R/scripts/check-deck.py" --repo argus-ui="$R" "$R/tests/deck-fixtures/good-course.json") || { echo "$out"; fail=1; }
  grep -q "INFO C8" <<<"$out" && { echo "FAIL a reference was not checked"; echo "$out"; fail=1; }
  echo "== mentor model"   # courses, Loose lessons, the review log: no browser (tests/mentor_model_test.py)
  python3 "$R/tests/mentor_model_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
fi
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
