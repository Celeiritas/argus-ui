#!/usr/bin/env bash
# Copy the pinned foliate-js (MIT) into plugins/memory/reader/vendor/foliate-js/ for Mnemosyne's book reader (4.69.0).
# Only the files the reader loads; no source maps, no demo reader, no text-to-speech. The tarball must match the checksum
# below, so a changed upstream never slips in: to move to a newer commit, change COMMIT and SHA256 together, rerun, test.
# foliate's vendor/pdfjs is pdf.js's modern build, which needs JavaScript newer than many e-readers' browsers have
# (Map.getOrInsertComputed, Math.sumPrecise, ...): its pdf.mjs and pdf.worker.mjs are replaced by the LEGACY build of the
# same pdf.js version (pdfjs-dist, Apache-2.0, the same code with polyfills), checked against npm's sha512.
#   bash scripts/vendor-foliate.sh
set -euo pipefail
COMMIT=78914aef4466eb960965702401634c2cb348e9b1       # 2026-05-01; its vendor/pdfjs is pdf.js 5.5.207
SHA256=4878cd5f04073af5046ea543da73a963a7f9e1a4b30ddc63ac86cea5adf02f38
PDFJS=5.5.207                                          # must be the version foliate's vendor/pdfjs carries
PDFJS_SHA512=WMqqw06w1vUt9ZfT0gOFhMf3wHsWhaCrxGrckGs5Cci6ybDW87IvPaOd2pnBwT6BJuP/CzXDZxjFgmSULLdsdw==   # npm dist.integrity
R="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$R/plugins/memory/reader/vendor/foliate-js"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fsSL -o "$TMP/foliate.tar.gz" "https://codeload.github.com/johnfactotum/foliate-js/tar.gz/$COMMIT"
echo "$SHA256  $TMP/foliate.tar.gz" | sha256sum -c --quiet - || { echo "vendor-foliate: checksum differs, nothing copied" >&2; exit 1; }
curl -fsSL -o "$TMP/pdfjs.tgz" "https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-$PDFJS.tgz"
got="$(openssl dgst -sha512 -binary "$TMP/pdfjs.tgz" | openssl base64 -A)"
[ "$got" = "$PDFJS_SHA512" ] || { echo "vendor-foliate: pdfjs-dist checksum differs, nothing copied" >&2; exit 1; }
tar xzf "$TMP/foliate.tar.gz" -C "$TMP"; tar xzf "$TMP/pdfjs.tgz" -C "$TMP"
SRC="$TMP/foliate-js-$COMMIT"
grep -q "pdfjsVersion = \"$PDFJS\"\|version = \"$PDFJS\"\|$PDFJS" "$SRC/vendor/pdfjs/pdf.mjs" || { echo "vendor-foliate: foliate's pdf.js is not $PDFJS" >&2; exit 1; }
FILES="LICENSE view.js epub.js epubcfi.js paginator.js fixed-layout.js pdf.js progress.js overlayer.js text-walker.js
       footnotes.js search.js comic-book.js fb2.js mobi.js uri-template.js vendor/zip.js vendor/fflate.js
       vendor/pdfjs/cmaps vendor/pdfjs/standard_fonts
       vendor/pdfjs/text_layer_builder.css vendor/pdfjs/annotation_layer_builder.css"
rm -rf "$OUT"; mkdir -p "$OUT/vendor/pdfjs"
for f in $FILES; do cp -R "$SRC/$f" "$OUT/$f"; done
cp "$TMP/package/legacy/build/pdf.mjs" "$TMP/package/legacy/build/pdf.worker.mjs" "$OUT/vendor/pdfjs/"
cp "$TMP/package/LICENSE" "$OUT/vendor/pdfjs/LICENSE"
echo "vendor-foliate: foliate-js $COMMIT + pdf.js $PDFJS legacy build copied to plugins/memory/reader/vendor/foliate-js ($(du -sh "$OUT" | cut -f1))"
