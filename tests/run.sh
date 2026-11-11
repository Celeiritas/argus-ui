#!/bin/bash
# tests/run.sh - build the package, run it against fake systemd units, and run the browser checks.
#   bash tests/run.sh            all checks          bash tests/run.sh olympus      just tests/olympus.test.js
#   bash tests/run.sh demo       records docs/screenshots/preview.gif for the README (needs ffmpeg)
# PYTHON=python bash tests/run.sh   uses another interpreter (on Windows python3 is a Store stub).
# Needs python3, node and Playwright with Chromium (npm install; npx playwright install chromium).
# Nothing outside a temporary folder is touched: a throwaway HOME, fake systemctl/journalctl, a saved weather reading.
set -e
PYTHON=${PYTHON:-python3}; export PYTHON
R=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d); PORT=${PORT:-8097}
# phone alerts (docs/phone-alerts.md): tests/phone-alerts.test.js runs a fake push service here; the server may send only to it
PUSH_PORT=${PUSH_PORT:-8099}; export PUSH_PORT
export NODE_PATH="${NODE_PATH:-$R/node_modules:$(npm root -g 2>/dev/null)}"
TH=${THEME:-leafy-realm}; bash "$R/scripts/build.sh" $TH >/dev/null; V=$(cat "$R/VERSION")
mkdir -p "$T/pod" "$T/pkg" "$T/home/.cache/argus-ui" "$T/fx"; tar xzf "$R/dist/argus-ui-$V-$TH.tar.gz" -C "$T/pkg"
cp -r "$R"/tests/fixtures/. "$T/fx/"; chmod +x "$T"/fx/*.py "$T"/fx/*.sh
# the Memory page reads ~/.mnemosyne/<Server>-brain/: three fixture snapshots and some decoys (tests/memory.test.js)
mkdir -p "$T/home/.mnemosyne"; cp -r "$R/tests/fixtures/memory/Server-brain" "$T/home/.mnemosyne/"
# LeafyPlugins: the demo plugin(s) live where installs keep them, inside the throwaway HOME
mkdir -p "$T/home/.config/argus-ui/plugins"; cp -r "$R"/tests/plugin-fixtures/. "$T/home/.config/argus-ui/plugins/"
# and bundled ones, as an install puts them next to Elaia (an agent-claiming plugin, and a demo-server that yours replaces)
cp -r "$R"/tests/bundled-fixtures/. "$T/pkg/bundled/"
$PYTHON -c "import json,time,sys; json.dump({'sky':'rain','desc':'Light rain','is_day':True,'temp':48,'unit':'F','precip':.6,'clouds':90,'wind':14,'south':False,'at':int(time.time()),'source':'Open-Meteo'}, open(sys.argv[1],'w'))" "$T/home/.cache/argus-ui/sky.json"
# the server's own state goes to explicit paths outside HOME (on Windows ~ follows USERPROFILE, so both point at the temp HOME)
ST="$T/state"; mkdir -p "$ST"; export ARGUS_EVENTS="$ST/events.jsonl"
# ARGUS_SERVE_UID: this runner counts as Tailscale Serve, so the real identity check runs and a test that sends
# Tailscale-User-Login itself is believed (no people file: everyone is the owner anyway; docs/people.md)
HOME="$T/home" USERPROFILE="$T/home" ARGUS_SERVE_UID=$(id -u) ARGUS_WATCH_STATE="$ST/watch.json" ARGUS_DEV=1 ARGUS_WEATHER=40,-111 ARGUS_STATIC="$T/pkg/static" ARGUS_BUNDLED="$T/pkg/bundled" ARGUS_SYSTEMCTL="$T/fx/fake_systemctl.py" ARGUS_JOURNALCTL="$T/fx/fake_journal.sh" ARGUS_PORT=$PORT \
  ARGUS_SUMMARY=0 ARGUS_PUSH_TEST_ORIGIN="http://127.0.0.1:$PUSH_PORT" ARGUS_WATCH_INTERVAL=1 ARGUS_MOUNTINFO="$T/fx/watch/host-good.mountinfo" FAKE_PODMAN_DIR="$T/pod" ARGUS_CONTROLLERS_SYSROOT="$T/fx/controllers-sysfs/four" ARGUS_CONTROLLERS="$T/fx/controllers.json" \
  $PYTHON "$T/pkg/argus_ui.py" > "$T/server.log" 2>&1 & PID=$!
# a stand-in local model server for tests/mentor-ai.test.js (docs/mentor-ai.md); off for every other check
MODEL_PORT=${MODEL_PORT:-8098}; $PYTHON "$T/fx/fake_model.py" $MODEL_PORT > "$T/model.log" 2>&1 & MPID=$!; export MODEL_PORT
trap 'kill $PID $MPID 2>/dev/null; echo "(server log and screenshots: $T)"' EXIT
for i in $(seq 50); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep .2; done
fail=0
# the deck rubric (docs/mentor-rubric.md): the shipped decks pass, and the checker still catches each rule
if [ -z "$1" ] || [ "$1" = mentor ]; then
  echo "== deck rubric"
  res=$($PYTHON "$R/scripts/check-deck.py" "$R"/themes/*/decks "$R/tests/deck-fixtures/good-lesson.json" "$R/tests/deck-fixtures/good-course.json" "$R/tests/deck-fixtures/good-roles.json" "$R/tests/deck-fixtures/good-items.json") || { echo "$res"; fail=1; }
  tail -1 <<<"$res"
  out=$($PYTHON "$R/scripts/check-deck.py" "$R/tests/deck-fixtures/bad-lesson.json") && { echo "FAIL the bad fixture passed"; fail=1; }
  for r in 'ERROR R1 file' 'WARN R1 repo' 'R2 ' 'R3 ' 'R4 ' 'R5 '; do grep -q "$r" <<<"$out" || { echo "FAIL the checker missed: $r"; fail=1; }; done
  grep -q 'drill_01: ERROR R1 file' <<<"$out" && { echo "FAIL a file name inside code was reported"; fail=1; }
  # checker v2 (courses): the bad course breaks each rule once
  out=$($PYTHON "$R/scripts/check-deck.py" --repo argus-ui="$R" "$R/tests/deck-fixtures/bad-course.json") && { echo "FAIL the bad course passed"; fail=1; }
  for r in C1 C2 C3 C4 C5 C6 C7 C8; do grep -q "ERROR $r " <<<"$out" || { echo "FAIL the course checker missed: $r"; echo "$out"; fail=1; }; done
  grep -q "no_such_function" <<<"$out" && grep -q "no_such_file.py" <<<"$out" || { echo "FAIL a missing symbol or file was not reported"; fail=1; }
  # 4.32: each card role's fields (C10 predict, C11 trace, C12 parsons, C13 write): one bad fixture per role, refused for that rule
  for r in predict:C10 trace:C11 parsons:C12 write:C13; do
    out=$($PYTHON "$R/scripts/check-deck.py" "$R/tests/deck-fixtures/bad-${r%%:*}.json") && { echo "FAIL bad-${r%%:*}.json passed"; fail=1; }
    grep -q "ERROR ${r##*:} " <<<"$out" || { echo "FAIL the checker missed ${r##*:} in bad-${r%%:*}.json"; echo "$out"; fail=1; }
  done
  # 4.34: exam-style item files (docs/mentor-items.md): one small bad fixture per rule N1-N8, refused for exactly that rule
  for n in 1 2 3 4 5 6 7 8; do
    out=$($PYTHON "$R/scripts/check-deck.py" "$R/tests/deck-fixtures/bad-items-n$n.json") && { echo "FAIL bad-items-n$n.json passed"; fail=1; }
    grep -q "ERROR N$n " <<<"$out" || { echo "FAIL the checker missed N$n in bad-items-n$n.json"; echo "$out"; fail=1; }
    other=$(grep " ERROR N" <<<"$out" | grep -v "ERROR N$n " || true)     # each bad file breaks its own rule and no other
    [ -z "$other" ] || { echo "FAIL bad-items-n$n.json also fires another rule"; echo "$other"; fail=1; }
  done
  # the good course's code references resolve in this repository at their commit
  out=$($PYTHON "$R/scripts/check-deck.py" --repo argus-ui="$R" "$R/tests/deck-fixtures/good-course.json") || { echo "$out"; fail=1; }
  grep -q "INFO C8" <<<"$out" && { echo "FAIL a reference was not checked"; echo "$out"; fail=1; }
  echo "== mentor model"   # courses, Loose lessons, the review log: no browser (tests/mentor_model_test.py)
  $PYTHON "$R/tests/mentor_model_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
  echo "== mentor people"  # 4.38: who is studying, one database per person, the AI fence (tests/mentor_people_test.py)
  $PYTHON "$R/tests/mentor_people_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
  echo "== mentor today"   # 4.38: tracks, pin and shelf, question first, the daily new limit (tests/mentor_today_test.py)
  $PYTHON "$R/tests/mentor_today_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
fi
if [ -z "$1" ] || [ "$1" = mentor ] || [ "$1" = items ]; then
  echo "== mentor items"   # exam-style items: scoring, ratings, rules N1-N8, no browser (tests/items_test.py)
  $PYTHON "$R/tests/items_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
fi
if [ -z "$1" ] || [ "$1" = memory ]; then
  echo "== memory model"   # the Memory page's server side, no browser (tests/memory_test.py)
  $PYTHON "$R/tests/memory_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
fi
# Leafy Controllers' probe over fixture sysfs trees, and the old names (pads.json, ARGUS_PADS, <base>/pads) on a real server:
# tests/controllers_test.py; the browser side is tests/controllers.test.js
if [ -z "$1" ] || [ "$1" = controllers ]; then
  echo "== controllers model"
  $PYTHON "$R/tests/controllers_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
fi
# "Works, not just runs" (watch.py, docs/checks.md): canned mount tables, a fake container runtime, a real server in its own process
if [ -z "$1" ] || [ "$1" = works ]; then
  echo "== watch works"
  $PYTHON "$R/tests/watch_works_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
fi
# people and roles (docs/people.md): the connection tables and the people file, then every route against each role on a
# real server; no browser. The Linux run reads the real /proc and says so ("real /proc lookup"); elsewhere it is simulated.
if [ -z "$1" ] || [ "$1" = people ] || [ "$1" = plugins ]; then
  echo "== people and roles"
  for t in identity_test gate_test mentor_gate_test; do       # the line saying which identity path ran, the summary; everything when it fails
    st=0; out=$($PYTHON -W ignore::ResourceWarning "$R/tests/$t.py" 2>&1) || st=$?
    if [ $st = 0 ]; then grep -E "real /proc|identity path|^Ran|^OK|skipped" <<<"$out" || true; else echo "$out"; fail=1; fi
  done
fi
# phone alerts (server/push.py, server/summary.py): RFC 8291 / 8292, the host rule, a fake push service, the sink, the daily
# summary and the routes; no browser (tests/push_test.py). In CI it fails, never skips, when the cryptography package is missing.
if [ -z "$1" ] || [ "$1" = phone-alerts ] || [ "$1" = push ]; then
  echo "== phone alerts"
  st=0; out=$($PYTHON -W ignore::ResourceWarning "$R/tests/push_test.py" 2>&1) || st=$?
  if [ $st = 0 ]; then grep -E "^Ran|^OK|skipped|mode 600" <<<"$out" || true; else echo "$out"; fail=1; fi
fi
if [ -z "$1" ] || [ "$1" = plugins ]; then
  echo "== plugin cache"   # ETag, Last-Modified, 304 and Cache-Control on raw headers: no browser (tests/plugin_cache_test.py)
  $PYTHON -W ignore::ResourceWarning "$R/tests/plugin_cache_test.py" 2>&1 | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
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
