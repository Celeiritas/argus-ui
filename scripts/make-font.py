# make-font.py: Nunito[wght].ttf -> web/fonts/nunito.<hash>.woff2, the page's own copy of its font (4.44.0; no Google Fonts).
# Source: github.com/googlefonts/nunito, fonts/variable/Nunito[wght].ttf (blob 2ec1f4b0, commit 8c6a9bb9 of 2025-02-26).
# Licence: SIL Open Font License 1.1, no Reserved Font Name; web/fonts/OFL.txt is that repository's OFL.txt, unchanged.
# Keeps the weight axis from 400 to 600 (the page uses only 400 and 600), Latin and Latin Extended plus the punctuation,
# arrows and symbols the page writes, every OpenType feature and every name record (the copyright line stays in the font;
# the style names now say Regular, the new default, instead of ExtraLight).
# The name carries the first 8 hex digits of the file's SHA-256, so the server can let browsers keep it a year.
# Needs fontTools and brotli (made with fonttools 4.55.3 and brotli 1.1.0 in a throwaway venv); never needed to build or run Elaia.
# usage: python -I scripts/make-font.py <Nunito[wght].ttf> <out dir>   -> prints the file it wrote; update the two names
#        in web/index.html (preload) and web/css/argus.css (@font-face)
import hashlib, os, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

src, outdir = sys.argv[1], sys.argv[2]
RANGES = [(0x0000, 0x024F), (0x0259, 0x0259), (0x02B0, 0x036F), (0x1E00, 0x1EFF), (0x2000, 0x206F), (0x20A0, 0x20CF),
          (0x2100, 0x218F), (0x2190, 0x21FF), (0x2212, 0x2215), (0x25A0, 0x25FF), (0x2600, 0x26FF), (0x2700, 0x27BF),
          (0xFEFF, 0xFEFF), (0xFFFD, 0xFFFD)]
font = TTFont(src)
axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font['fvar'].axes}
print('axes before', axes)
opt = subset.Options()   # subset first, then limit the axis (the other order trips over a lazily loaded glyph table)
opt.layout_features = ['*']; opt.name_IDs = ['*']; opt.name_languages = ['*']; opt.name_legacy = True
opt.notdef_outline = True; opt.glyph_names = False
s = subset.Subsetter(options=opt)
s.populate(unicodes=[u for a, b in RANGES for u in range(a, b + 1)])
s.subset(font)
os.makedirs(outdir, exist_ok=True); mid = os.path.join(outdir, 'nunito.subset.ttf'); font.save(mid); font = TTFont(mid)
font = instancer.instantiateVariableFont(font, {'wght': (400, 600)}, updateFontNames=True)   # its default is now Regular (400), not ExtraLight
names = {r.nameID: r.toUnicode() for r in font['name'].names if r.platformID == 3}
print('names after', {k: names.get(k) for k in (1, 2, 4, 6, 16, 17)})
print('axes after', {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font['fvar'].axes})
tmp = os.path.join(outdir, 'nunito.tmp.woff2')
font.flavor = 'woff2'; font.save(tmp)
data = open(tmp, 'rb').read(); assert data[:4] == b'wOF2', data[:4]
name = 'nunito.%s.woff2' % hashlib.sha256(data).hexdigest()[:8]
os.replace(tmp, os.path.join(outdir, name))
cmap = TTFont(os.path.join(outdir, name)).getBestCmap()
print('wrote', name, len(data), 'bytes,', len(cmap), 'characters; has', ' '.join('U+%04X' % c for c in (0xB7, 0x2013, 0xB0, 0x2192, 0x2713) if c in cmap))
print('copyright:', TTFont(os.path.join(outdir, name))['name'].getDebugName(0))
