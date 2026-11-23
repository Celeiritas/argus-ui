"""Conservative, offline DOCX body-text extraction. Optional python-docx dependency.

This is not a Word renderer. Unsupported text-bearing features are held, never
silently promoted as complete searchable text. No relationship URL is fetched.
"""
import hashlib
import io
from pathlib import Path, PurePosixPath
import zipfile
import xml.etree.ElementTree as ET

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
MAX_TEXT = 12 * 1024 * 1024
MAX_BLOCKS = 10000
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
MATH = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
UNSUPPORTED = set(('ins del moveFrom moveTo moveFromRangeStart moveToRangeStart '
                   'sdt smartTag customXml fldSimple fldChar instrText drawing pict object '
                   'txbxContent footnoteReference endnoteReference commentReference '
                   'altChunk subDoc sym gridSpan vMerge hMerge gridBefore gridAfter '
                   'vanish webHidden rPrChange pPrChange tblPrChange trPrChange '
                   'tcPrChange sectPrChange numberingChange').split())


def _xml(raw):
    probe = raw.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in probe or b'<!ENTITY' in probe:
        raise ValueError('DOCX XML declarations/entities are unsupported; original kept')
    depth = count = 0
    for event, element in ET.iterparse(io.BytesIO(raw), events=('start', 'end')):
        if event == 'start':
            depth += 1; count += 1
            if depth > 100 or count > 100000:
                raise ValueError('DOCX XML exceeds depth or element limit')
        else: depth -= 1
    return element


def _preflight(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if len(infos) > 4096 or sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise ValueError('DOCX archive exceeds expansion limit')
        seen = set(); document = None
        for info in infos:
            name = info.filename; path = PurePosixPath(name)
            if (name != info.orig_filename or name in seen or path.is_absolute() or '..' in path.parts or '\\' in name
                    or ':' in name or info.flag_bits & 1 or info.file_size > MAX_MEMBER):
                raise ValueError('Unsafe, duplicate, encrypted or oversized DOCX member')
            seen.add(name)
            if info.is_dir(): continue
            if name.lower().endswith('.bin') or name.startswith('word/embeddings/'):
                raise ValueError('Embedded objects or macros are unsupported')
            if not name.lower().endswith(('.xml', '.rels')): continue
            tree = _xml(z.read(info))
            if name in ('word/styles.xml','word/stylesWithEffects.xml'):
                defaults = tree.find(W+'docDefaults')
                if defaults is not None and any(n.tag in (W+'vanish',W+'webHidden') for n in defaults.iter()):
                    raise ValueError('Hidden DOCX default text requires review')
            if name == 'word/document.xml': document = tree
            if name.endswith('.rels'):
                for rel in tree:
                    if rel.get('TargetMode') == 'External' and rel.get('Type') != 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink':
                        raise ValueError('External DOCX content is unsupported; nothing fetched')
            if name.startswith('word/') and name.endswith('.xml') and name not in ('word/styles.xml','word/stylesWithEffects.xml','word/numbering.xml','word/settings.xml','word/fontTable.xml','word/webSettings.xml') and '/theme/' not in name:
                for node in tree.iter():
                    if node.tag.startswith(MATH) or node.tag in {W+t for t in UNSUPPORTED}:
                        raise ValueError('Unsupported DOCX feature: '+node.tag.split('}')[-1])
                if name != 'word/document.xml' and any((n.text or '').strip() for n in tree.iter(W+'t')):
                    raise ValueError('Text outside the document body requires review (notes, comments, headers or footers)')
        if document is None: raise ValueError('DOCX document body is missing')
        body = document.find(W+'body')
        if body is None: raise ValueError('DOCX document body is missing')
        # Validate container structure so the library cannot silently skip a block.
        def container(node, allowed):
            for child in node:
                if child.tag not in {W+t for t in allowed}:
                    raise ValueError('Unsupported DOCX container: '+child.tag.split('}')[-1])
        container(body, ('p','tbl','sectPr'))
        for node in body.iter():
            if node.tag == W+'tbl': container(node, ('tblPr','tblGrid','tr'))
            elif node.tag == W+'tr': container(node, ('trPr','tc'))
            elif node.tag == W+'tc': container(node, ('tcPr','p','tbl'))
            elif node.tag == W+'p': container(node, ('pPr','r','hyperlink','bookmarkStart','bookmarkEnd','proofErr'))
            elif node.tag == W+'hyperlink': container(node, ('r','bookmarkStart','bookmarkEnd','proofErr'))
            elif node.tag == W+'r': container(node, ('rPr','t','tab','br','cr','lastRenderedPageBreak'))


def _style_check(style):
    seen = set()
    while style is not None:
        key = style.style_id
        if key in seen: raise ValueError('Cyclic DOCX style inheritance')
        seen.add(key)
        if style.element.find('.//'+W+'numPr') is not None:
            raise ValueError('Numbered or bulleted DOCX lists require review')
        if any(n.tag in (W+'vanish',W+'webHidden') for n in style.element.iter()):
            raise ValueError('Hidden DOCX text requires review')
        style = style.base_style


def extract(path, fallback_title=None):
    with Path(path).open('rb') as f: raw = f.read(MAX_ARCHIVE+1)
    if len(raw) > MAX_ARCHIVE: raise ValueError('DOCX exceeds 64 MB')
    try:
        _preflight(raw)
    except (zipfile.BadZipFile, ET.ParseError, RuntimeError, NotImplementedError) as e:
        raise ValueError('Invalid or unsupported DOCX package') from e
    try:
        import docx
        from docx.text.paragraph import Paragraph
        from docx.table import Table
    except ImportError as e:
        raise ValueError('Install optional requirements-mnemosyne-docx.txt in the importer environment; original kept') from e
    if docx.__version__ != '1.2.0':
        raise ValueError('Use reviewed python-docx 1.2.0 from requirements-mnemosyne-docx.txt')
    try:
        doc = docx.Document(io.BytesIO(raw))
        pieces = []; locations = []; offset = byte_count = 0
        def walk(parent, prefix, depth=0):
            nonlocal offset, byte_count
            if depth > 30: raise ValueError('DOCX nested tables exceed the limit')
            counts = {'p':0, 'tbl':0}
            for block in parent.iter_inner_content():
                tag = 'p' if isinstance(block, Paragraph) else 'tbl'
                counts[tag] += 1; locator = f'{prefix}/{tag}[{counts[tag]}]'
                if isinstance(block, Paragraph):
                    if block._p.find('.//'+W+'numPr') is not None:
                        raise ValueError('Numbered or bulleted DOCX lists require review')
                    _style_check(block.style)
                    for inline in block.iter_inner_content():
                        for run in getattr(inline,'runs',[inline]): _style_check(run.style)
                    text = block.text
                    if not text.strip(): continue
                    if any(c == '\ufffd' or ord(c) % 65536 in (65534,65535) or 0xFDD0 <= ord(c) <= 0xFDEF for c in text):
                        raise ValueError('Damaged DOCX text requires review')
                    byte_count += len(text.encode('utf-8')) + (2 if pieces else 0)
                    if byte_count > MAX_TEXT or len(pieces) >= MAX_BLOCKS:
                        raise ValueError('DOCX extracted text or block count exceeds limit')
                    if pieces: offset += 2
                    locations.append(dict(path=locator,start=offset,end=offset+len(text)))
                    offset += len(text); pieces.append(text)
                elif isinstance(block, Table):
                    _style_check(block.style)
                    for row_no, row in enumerate(block.rows,1):
                        for cell_no, cell in enumerate(row.cells,1):
                            walk(cell,f'{locator}/tr[{row_no}]/tc[{cell_no}]',depth+1)
        walk(doc,'word/document.xml/body')
        if not pieces: raise ValueError('DOCX has no supported nonempty body text')
        return dict(title=(doc.core_properties.title or fallback_title or Path(path).stem).strip() or 'Untitled document',
                    authorship=(doc.core_properties.author or '').strip() or 'unknown',
                    source_version=hashlib.sha256(raw).hexdigest(),
                    extraction_version='mnemosyne-docx/1;python-docx/'+docx.__version__,
                    text='\n\n'.join(pieces),locations=locations)
    except ValueError: raise
    except Exception as e:
        raise ValueError('DOCX could not be read completely; original kept for review') from e
