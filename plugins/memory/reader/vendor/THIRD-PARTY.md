# Third-party code in the book reader

Copied by `scripts/vendor-foliate.sh` (checksum-pinned); never edited by hand. To update, change the commit and checksums in that script and rerun it.

| Code | Version | Licence | Notice |
|---|---|---|---|
| foliate-js (johnfactotum/foliate-js) | commit 78914aef4466eb960965702401634c2cb348e9b1 | MIT | `foliate-js/LICENSE` |
| pdf.js (Mozilla), in `foliate-js/vendor/pdfjs/`: `pdf.mjs` and `pdf.worker.mjs` are the **legacy build** from pdfjs-dist 5.5.207 (npm, sha512-pinned) in place of foliate's modern build, so PDFs open in older browsers such as e-readers'; the two `*_layer_builder.css` files come with foliate-js | 5.5.207 | Apache-2.0 | `vendor/pdfjs/LICENSE`, header of `pdf.mjs` and `pdf.worker.mjs` |
| pdf.js CMaps (Adobe), `vendor/pdfjs/cmaps/` | as shipped with pdf.js 5.5.207 | BSD-3-Clause | `cmaps/LICENSE` |
| pdf.js standard fonts (Foxit, Liberation) | as shipped with pdf.js 5.5.207 | BSD-style (Foxit), SIL OFL 1.1 (Liberation) | `standard_fonts/LICENSE_FOXIT`, `LICENSE_LIBERATION` |
| zip.js (gildas-lormeau), `vendor/zip.js` | as bundled by foliate-js | BSD-3-Clause | upstream repository |
| fflate (101arrowz), `vendor/fflate.js` | as bundled by foliate-js | MIT | upstream repository |

No GPL or AGPL code. Only the reader's own files (`../index.html`, `../reader.js`, `../reader.css`) are Argus UI code (MIT).
