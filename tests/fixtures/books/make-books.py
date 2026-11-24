"""Writes the book reader's test books (4.69.0, tests/library-reader.test.js) into a folder; stdlib only, made at test time.

tiny.epub: three chapters of 2000 numbered words (c1w0 c1w1 ...). Chapter 2 also carries three scripts that must never run
in the reader (an inline <script>, an <img onerror> and <script src="evil.js">, each setting window.parent.BAD).
tiny.pdf: three pages, "Page one" / "Page two" / "Page three".
    python tests/fixtures/books/make-books.py <folder>
"""
import os, sys, zipfile

OPF = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:identifier id="uid">urn:uuid:00000000-0000-4000-8000-000000000001</dc:identifier>
  <dc:title>Tiny Fixture Book</dc:title><dc:language>en</dc:language>
  <meta property="dcterms:modified">2026-11-24T00:00:00Z</meta>
 </metadata>
 <manifest>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>
  <item id="c2" href="c2.xhtml" media-type="application/xhtml+xml" properties="scripted"/>
  <item id="c3" href="c3.xhtml" media-type="application/xhtml+xml"/>
  <item id="evil" href="evil.js" media-type="application/javascript"/>
 </manifest>
 <spine><itemref idref="c1"/><itemref idref="c2"/><itemref idref="c3"/></spine>
</package>'''
CONTAINER = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
 <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
NAV = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head>
<body><nav epub:type="toc"><ol><li><a href="c1.xhtml">One</a></li><li><a href="c2.xhtml">Two</a></li><li><a href="c3.xhtml">Three</a></li></ol></nav></body></html>'''
TRAPS = ('<script>window.parent.BAD = 1;</script>\n<p><img src="x" alt="" onerror="window.parent.BAD = 2"/></p>\n'
         '<script src="evil.js"></script>\n')


def chapter(n, traps=''):
    paras = []
    for start in range(0, 2000, 50):
        paras.append('<p>' + ' '.join(f'c{n}w{i}' for i in range(start, start + 50)) + '</p>')
    return ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter '
            f'{n}</title></head>\n<body><h1>Chapter {n}</h1>\n{traps}' + '\n'.join(paras) + '\n</body></html>')


def epub(path):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip')          # first and stored, as the format asks
        z.writestr('META-INF/container.xml', CONTAINER, zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/content.opf', OPF, zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/nav.xhtml', NAV, zipfile.ZIP_DEFLATED)
        for n in (1, 2, 3):
            z.writestr(f'OEBPS/c{n}.xhtml', chapter(n, TRAPS if n == 2 else ''), zipfile.ZIP_DEFLATED)
        z.writestr('OEBPS/evil.js', 'window.parent.BAD = 3;', zipfile.ZIP_DEFLATED)


def pdf(path):
    words = ['one', 'two', 'three']
    objs = ['<< /Type /Catalog /Pages 2 0 R >>',
            '<< /Type /Pages /Kids [' + ' '.join(f'{4 + 2 * i} 0 R' for i in range(3)) + '] /Count 3 >>',
            '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for i, w in enumerate(words):
        stream = f'BT /F1 36 Tf 72 700 Td (Page {w}) Tj ET'.encode()
        objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>')
        objs.append(f'<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream')
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out)); out += f'{n} 0 obj\n{body}\nendobj\n'.encode()
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
    out += b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    with open(path, 'wb') as f: f.write(out)


if __name__ == '__main__':
    folder = sys.argv[1]
    os.makedirs(folder, exist_ok=True)
    epub(os.path.join(folder, 'tiny.epub')); pdf(os.path.join(folder, 'tiny.pdf'))
    print('made', os.path.join(folder, 'tiny.epub'), os.path.join(folder, 'tiny.pdf'))
