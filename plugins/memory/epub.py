"""Bounded, offline text extraction for reflowable EPUB 2/3. No rendering or model calls."""
import hashlib
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_TEXT = 12 * 1024 * 1024
VERSION = 'epub-spine-text/1'
OPF = '{http://www.idpf.org/2007/opf}'
XHTML = '{http://www.w3.org/1999/xhtml}'
DC = '{http://purl.org/dc/elements/1.1/}'
CONTAINER = '{urn:oasis:names:tc:opendocument:xmlns:container}'


class BoundedTree(ET.TreeBuilder):
    def __init__(self):
        super().__init__(); self.depth = 0; self.nodes = 0

    def doctype(self, name, pubid, system):
        raise ValueError('DTD/entity declarations are not supported')

    def start(self, tag, attrs):
        self.depth += 1; self.nodes += 1
        if self.depth > 100 or self.nodes > 100000: raise ValueError('XML structure exceeds the import limit')
        return super().start(tag, attrs)

    def end(self, tag):
        result = super().end(tag); self.depth -= 1; return result


def xml(raw):
    try: return ET.fromstring(raw, parser=ET.XMLParser(target=BoundedTree()))
    except ET.ParseError as e: raise ValueError('Malformed EPUB XML') from e


def member_path(base, href):
    u = urlsplit(href)
    if u.scheme or u.netloc or u.query or u.fragment: raise ValueError('EPUB content must be a local document')
    path = unquote(u.path, errors='strict')
    if not path or '\\' in path or ':' in path or path.startswith('/') or '\0' in path:
        raise ValueError('Unsafe EPUB content path')
    result = posixpath.normpath(posixpath.join(base, path))
    if result == '..' or result.startswith('../'): raise ValueError('EPUB path leaves its container')
    return result


def chapter_text(root):
    body = root.find(XHTML + 'body')
    if root.tag != XHTML + 'html' or body is None: raise ValueError('Spine content must be XHTML with a body')
    pieces = []
    blocks = {'p','div','section','article','header','footer','aside','blockquote','li','h1','h2','h3','h4','h5','h6','pre','tr'}
    hidden = {'script','style','noscript','template','head'}
    def visit(el):
        tag = el.tag.rsplit('}', 1)[-1] if isinstance(el.tag, str) else ''
        if tag in hidden: return
        if tag in ('math','svg'): raise ValueError('MathML/SVG needs a separate reviewed extraction')
        if tag in blocks: pieces.append('\n\n')
        if tag == 'br': pieces.append('\n')
        if tag in ('td','th'): pieces.append('\t')
        if tag == 'img' and el.get('alt'): pieces.append('[Image description: ' + el.get('alt') + ']')
        if el.text: pieces.append(el.text)
        for child in el:
            visit(child)
            if child.tail: pieces.append(child.tail)
        if tag in blocks: pieces.append('\n\n')
    visit(body)
    text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', ''.join(pieces)).strip()
    heading = next((e for e in body.iter() if e.tag in (XHTML+'h1', XHTML+'h2')), None)
    label = ' '.join(''.join(heading.itertext()).split()) if heading is not None else ''
    return text, label


def extract(path):
    path = Path(path)
    if path.stat().st_size > MAX_ARCHIVE: raise ValueError('EPUB exceeds 64 MB')
    try:
        with zipfile.ZipFile(path) as book:
            members = book.infolist(); names = [m.filename for m in members]
            if len(names) > 4096 or len(names) != len(set(names)): raise ValueError('Too many or duplicate EPUB members')
            if sum(m.file_size for m in members) > MAX_TOTAL: raise ValueError('EPUB expansion exceeds 128 MB')
            for m in members:
                name = PurePosixPath(m.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in m.filename or ':' in m.filename or '\0' in m.filename:
                    raise ValueError('Unsafe EPUB member name')
                if m.flag_bits & 1 or m.file_size > MAX_MEMBER: raise ValueError('Encrypted or oversized EPUB member')
            if 'META-INF/encryption.xml' in names: raise ValueError('Encrypted or obfuscated EPUB resources are not supported')
            def read(name):
                with book.open(name) as f: raw = f.read(MAX_MEMBER + 1)
                if len(raw) > MAX_MEMBER: raise ValueError('EPUB member exceeds its limit')
                return raw
            if read('mimetype') != b'application/epub+zip': raise ValueError('Not an EPUB container')
            container = xml(read('META-INF/container.xml'))
            roots = container.findall(CONTAINER+'rootfiles/'+CONTAINER+'rootfile')
            if len(roots) != 1: raise ValueError('Select one EPUB rendition before importing')
            package_path = member_path('', roots[0].get('full-path',''))
            package = xml(read(package_path)); base = posixpath.dirname(package_path)
            if package.tag != OPF+'package' or package.get('version','').split('.')[0] not in ('2','3'):
                raise ValueError('Only EPUB 2/3 packages are supported')
            metadata = package.find(OPF+'metadata'); manifest = package.find(OPF+'manifest'); spine = package.find(OPF+'spine')
            if metadata is None or manifest is None or spine is None: raise ValueError('Incomplete EPUB package')
            if any(m.get('property') == 'rendition:layout' and (m.text or '').strip() == 'pre-paginated' for m in metadata):
                raise ValueError('Fixed-layout EPUB needs a separate reviewed extraction')
            items = {}
            for item in manifest:
                key = item.get('id')
                if not key or key in items: raise ValueError('Missing or duplicate manifest item id')
                items[key] = item
            chapters = []; seen = set(); total = 0
            for ref in spine:
                if ref.tag != OPF+'itemref': continue
                item = items.get(ref.get('idref'))
                if item is None or item.get('media-type') != 'application/xhtml+xml': raise ValueError('Unsupported or missing spine content')
                if 'rendition:layout-pre-paginated' in ref.get('properties','').split(): raise ValueError('Fixed-layout chapter is unsupported')
                member = member_path(base,item.get('href',''))
                if member in seen: raise ValueError('Duplicate spine document')
                seen.add(member)
                text, label = chapter_text(xml(read(member)))
                total += len(text.encode('utf-8'))
                if total > MAX_TEXT: raise ValueError('Extracted EPUB text exceeds 12 MB')
                chapters.append(dict(member=member,label=label or f'Chapter {len(chapters)+1}',text=text,
                                     linear=ref.get('linear','yes') != 'no'))
            if not chapters or not any(c['text'].strip() for c in chapters): raise ValueError('No readable EPUB spine text')
            title = ' '.join(metadata.findtext(DC+'title',default=path.stem).split())
            authors = [' '.join(''.join(e.itertext()).split()) for e in metadata.findall(DC+'creator')]
            return dict(title=title,authorship='; '.join(authors) or 'unknown',chapters=chapters,
                        source_version=hashlib.sha256(path.read_bytes()).hexdigest(),extraction_version=VERSION)
    except (zipfile.BadZipFile, KeyError, UnicodeError, RuntimeError) as e:
        raise ValueError('EPUB container could not be read: ' + str(e)) from e
