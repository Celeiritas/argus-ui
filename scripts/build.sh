#!/bin/bash
# build.sh [theme] - make an installable package: dist/argus-ui-<version>-<theme>.tar.gz
set -e
R=$(cd "$(dirname "$0")/.." && pwd); THEME=${1:-leafy-realm}; T=$R/themes/$THEME; V=$(cat $R/VERSION)
[ -f $T/theme.json ] || { echo "no theme at $T"; exit 1; }
O=$R/dist/argus-ui-$V-$THEME; rm -rf $O; mkdir -p $O/static/icons $O/static/sfx
cp $R/server/argus_ui.py $R/server/sky.py $R/server/watch.py $R/server/notify.py $R/server/identity.py $R/server/push.py $R/server/summary.py $O/; cp $R/scripts/install.sh $O/; chmod +x $O/install.sh
cp $R/web/manifest.webmanifest $R/web/sw.js $O/static/
mkdir -p $O/bundled; [ -d $R/plugins ] && cp -r $R/plugins/. $O/bundled/   # bundled LeafyPlugins (docs/leafy-plugin.md)
cp -r $R/web/css $R/web/js $R/web/fonts $O/static/   # fonts: the page's own Nunito and its licence (OFL.txt), nothing fetched elsewhere
cp $T/theme.json $O/static/; mkdir -p $O/static/decks; cp $T/decks/*.json $O/static/decks/ 2>/dev/null || true; cp $T/icons/*.png $O/static/icons/; cp $T/sfx/*.mp3 $O/static/sfx/ 2>/dev/null || true
cp $T/argus-192.png $T/argus-512.png $O/static/ 2>/dev/null || true
# Medusa's SVG is inlined into the page so her snakes and effects can animate; script/style URLs get the version.
# The Run tool shows the theme's own Zeus (icons/zeus.png) when it has one, so Zeus is drawn once; a theme without it keeps the plain bolt.
# A theme's "colors" (docs/themes.md) become CSS custom properties in the page; argus.css holds the neutral ones for a theme without.
${PYTHON:-python3} - "$R/web/index.html" "$T/gods/medusa.svg" "$O/static/index.html" "$V" "$T/icons/zeus.png" "$T/theme.json" <<'PY'
import json, os, re, sys
page, med, out, ver, zeus, theme = sys.argv[1:]
COLORS = ('server-bg', 'server-border', 'server-name', 'server-words')     # the server's band on Today (4.45.0)
cs = json.load(open(theme, encoding='utf-8')).get('colors') or {}
bad = [k for k in cs if k not in COLORS] if isinstance(cs, dict) else ['colors is not an object']
bad += [f'{k}: {v!r}' for k, v in (cs.items() if isinstance(cs, dict) else ()) if not (isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?', v))]
if bad: sys.exit(f'build.sh: {theme}: "colors" may only hold {", ".join(COLORS)} as #rgb or #rrggbb; not {"; ".join(bad)}')
style = '<style>:root{' + ';'.join(f'--{k}:{v}' for k, v in cs.items()) + '}</style>' if cs else ''
m = open(med).read().replace('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 234 234" class="medusa"',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 234 234" class="medusa" id="medusa" role="img" aria-label="Medusa"', 1)
html = open(page).read().replace('<!--MEDUSA-->', m).replace('__V__', ver)   # ?v=<version> so browsers never mix old and new files
assert '<!--THEME-COLORS-->' in html, 'index.html lost its <!--THEME-COLORS--> marker'
html = html.replace('<!--THEME-COLORS-->', style)
if os.path.exists(zeus):
    html, n = re.subn(r'<!--BOLT-->.*?<!--/BOLT-->', '<img id="bolt" src="static/icons/zeus.png" alt="" draggable="false">', html, count=1, flags=re.S)
    assert n == 1, 'index.html lost its <!--BOLT--> markers'
open(out, 'w').write(html)
PY
echo $V > $O/static/VERSION
tar -czf $O.tar.gz -C $O . && echo "built $O.tar.gz ($(du -h $O.tar.gz | cut -f1))"
