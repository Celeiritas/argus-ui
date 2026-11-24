#!/usr/bin/env bash
# Copy the pinned foliate-js (MIT) into plugins/memory/reader/vendor/foliate-js/ for Mnemosyne's book reader (4.69.0).
# Only the files the reader loads; no source maps, no demo reader, no text-to-speech. The tarball must match the checksum
# below, so a changed upstream never slips in: to move to a newer commit, change COMMIT and SHA256 together, rerun, test.
#   bash scripts/vendor-foliate.sh
set -euo pipefail
COMMIT=78914aef4466eb960965702401634c2cb348e9b1       # 2026-05-01; its vendor/pdfjs is pdf.js 5.5.207
SHA256=4878cd5f04073af5046ea543da73a963a7f9e1a4b30ddc63ac86cea5adf02f38
R="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$R/plugins/memory/reader/vendor/foliate-js"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fsSL -o "$TMP/foliate.tar.gz" "https://codeload.github.com/johnfactotum/foliate-js/tar.gz/$COMMIT"
echo "$SHA256  $TMP/foliate.tar.gz" | sha256sum -c --quiet - || { echo "vendor-foliate: checksum differs, nothing copied" >&2; exit 1; }
tar xzf "$TMP/foliate.tar.gz" -C "$TMP"
SRC="$TMP/foliate-js-$COMMIT"
FILES="LICENSE view.js epub.js epubcfi.js paginator.js fixed-layout.js pdf.js progress.js overlayer.js text-walker.js
       footnotes.js search.js comic-book.js fb2.js mobi.js uri-template.js vendor/zip.js vendor/fflate.js
       vendor/pdfjs/pdf.mjs vendor/pdfjs/pdf.worker.mjs vendor/pdfjs/cmaps vendor/pdfjs/standard_fonts"
rm -rf "$OUT"; mkdir -p "$OUT/vendor/pdfjs"
for f in $FILES; do cp -R "$SRC/$f" "$OUT/$f"; done
echo "vendor-foliate: foliate-js $COMMIT copied to plugins/memory/reader/vendor/foliate-js ($(du -sh "$OUT" | cut -f1))"
