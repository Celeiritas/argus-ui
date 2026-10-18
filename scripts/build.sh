#!/bin/bash
# build.sh [theme] - make an installable package: dist/argus-ui-<version>-<theme>.tar.gz
set -e
R=$(cd "$(dirname "$0")/.." && pwd); THEME=${1:-leafy-realm}; T=$R/themes/$THEME; V=$(cat $R/VERSION)
[ -f $T/theme.json ] || { echo "no theme at $T"; exit 1; }
O=$R/dist/argus-ui-$V-$THEME; rm -rf $O; mkdir -p $O/static/icons $O/static/sfx
cp $R/server/argus_ui.py $O/; cp $R/scripts/install.sh $O/; chmod +x $O/install.sh
cp $R/web/manifest.webmanifest $R/web/sw.js $O/static/
cp $T/theme.json $O/static/; cp $T/icons/*.png $O/static/icons/; cp $T/sfx/*.mp3 $O/static/sfx/ 2>/dev/null || true
cp $T/argus-192.png $T/argus-512.png $O/static/ 2>/dev/null || true
# Medusa's SVG is inlined into the page so her snakes and effects can animate
python3 - "$R/web/index.html" "$T/gods/medusa.svg" "$O/static/index.html" <<'PY'
import sys
page, med, out = sys.argv[1:]
m = open(med).read().replace('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 234 234" class="medusa"',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 234 234" class="medusa" id="medusa" role="img" aria-label="Medusa"', 1)
open(out, 'w').write(open(page).read().replace('<!--MEDUSA-->', m))
PY
echo $V > $O/static/VERSION
tar -czf $O.tar.gz -C $O . && echo "built $O.tar.gz ($(du -h $O.tar.gz | cut -f1))"
