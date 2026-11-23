"""Synthetic Word packages only; no personal documents or Word installation."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'plugins/memory'/f'{name}.py')
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result

adapter = module('docx_import')
library = module('library')

class DocxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.file = self.root/'fixture.docx'
        self.doc = Document(); self.doc.core_properties.title = 'Fixture guide'
        self.doc.core_properties.author = 'Fixture author'
        self.doc.add_paragraph('First paragraph.')

    def save(self): self.doc.save(self.file)

    def mutate(self, member, value):
        with zipfile.ZipFile(self.file) as z: parts = {n:z.read(n) for n in z.namelist()}
        parts[member] = value
        with zipfile.ZipFile(self.file,'w',zipfile.ZIP_DEFLATED) as z:
            for n,v in parts.items(): z.writestr(n,v)

    def test_order_nested_cells_and_exact_offsets(self):
        table = self.doc.add_table(rows=1, cols=2)
        table.cell(0,0).text = 'Left cell'
        nested = table.cell(0,0).add_table(rows=1,cols=1)
        nested.cell(0,0).text = 'Nested cell'
        table.cell(0,1).text = 'Right cell'
        self.doc.add_paragraph('Last paragraph.'); self.save()
        r = adapter.extract(self.file)
        self.assertEqual(r['text'].split('\n\n'), ['First paragraph.','Left cell','Nested cell','Right cell','Last paragraph.'])
        self.assertEqual(r['title'],'Fixture guide')
        self.assertEqual(r['source_version'],hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(len({x['path'] for x in r['locations']}),5)
        self.assertIn('/tr[1]/tc[1]/tbl[1]/',r['locations'][2]['path'])
        for loc,text in zip(r['locations'],r['text'].split('\n\n')):
            self.assertEqual(r['text'][loc['start']:loc['end']],text)

    def test_hyperlink_text_is_kept_without_fetching(self):
        p = self.doc.add_paragraph('Read ')
        h = OxmlElement('w:hyperlink')
        h.set(qn('r:id'),p.part.relate_to('https://example.invalid',RT.HYPERLINK,is_external=True))
        run = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text='linked words'
        run.append(t);h.append(run);p._p.append(h);self.save()
        self.assertIn('Read linked words',adapter.extract(self.file)['text'])

    def test_unsupported_content_is_held(self):
        for tag in ('ins','del','sdt','fldSimple','drawing','pict','object','sym','footnoteReference','endnoteReference','commentReference','altChunk','rPrChange'):
            with self.subTest(tag=tag):
                self.doc = Document();p=self.doc.add_paragraph('Visible')
                p._p.append(OxmlElement('w:'+tag));self.save()
                with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_header_text_numbered_lists_hidden_text_and_merged_cells_held(self):
        self.doc.sections[0].header.paragraphs[0].text='Header evidence';self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.doc=Document();self.doc.add_paragraph('List evidence',style='List Number');self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.doc=Document();self.doc.add_paragraph().add_run('Hidden').font.hidden=True;self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.doc=Document();t=self.doc.add_table(rows=1,cols=2);t.cell(0,0).merge(t.cell(0,1)).text='Merged';self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_external_non_hyperlink_refused(self):
        self.doc.part.relate_to('https://example.invalid/image',RT.IMAGE,is_external=True);self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_unsafe_duplicate_and_oversize_archives_refused(self):
        for name in ('../outside.xml','/absolute.xml'):
            self.save();self.mutate(name,b'<test/>')
            with self.subTest(name=name), self.assertRaises(ValueError):adapter.extract(self.file)
        self.save()
        self.mutate('word/bad.xml',b'<test/>')
        self.file.write_bytes(self.file.read_bytes().replace(b'word/bad.xml',b'word\\bad.xml'))
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.save()
        with zipfile.ZipFile(self.file,'a') as z:z.writestr('word/document.xml','duplicate')
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.save()
        with patch.object(adapter,'MAX_MEMBER',100),self.assertRaises(ValueError):adapter.extract(self.file)

    def test_dtd_in_alternate_encodings_and_deep_xml_refused(self):
        for encoding in ('utf-8','utf-16','utf-32'):
            self.save();self.mutate('extra.xml','<!DOCTYPE x [<!ENTITY x "BAD">]><x>&x;</x>'.encode(encoding))
            with self.subTest(encoding=encoding),self.assertRaises(ValueError):adapter.extract(self.file)
        self.save();self.mutate('extra.xml',('<x>'*110+'t'+'</x>'*110).encode())
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_empty_and_non_zip_refused(self):
        self.file.write_bytes(b'not a Word document')
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.doc=Document();self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_missing_optional_dependency_actionable(self):
        self.save()
        with patch.dict(sys.modules,{'docx':None}),self.assertRaisesRegex(ValueError,'requirements-mnemosyne-docx'):
            adapter.extract(self.file)

    def test_unicode_and_multi_block_reader_reconstructs_exactly(self):
        text='Café 漢字 🎹 evidence ' * 900
        self.doc.add_paragraph(text);self.save();r=adapter.extract(self.file)
        self.assertEqual(r['text'][r['locations'][-1]['start']:r['locations'][-1]['end']],text)
        out=self.root/'text.txt';out.write_text(r['text'],encoding='utf-8',newline='')
        manifest=dict(schema='mnemosyne-manifest/1',complete=True,collections=['fixtures'],sources=[dict(collection='fixtures',key='long',title='Long',kind='note',health='ready',file_format='docx',page_scheme='none',text='text.txt')])
        db=self.root/'long.sqlite';library.initialize(db,manifest,self.root)
        sid=library.search(db,'evidence',kind='note')['passages'][0]['source_id']
        first=library.reader(db,sid);self.assertGreater(first['total'],1)
        reconstructed=''.join(library.reader(db,sid,offset=i)['blocks'][0]['text'] for i in range(first['total']))
        self.assertEqual(reconstructed,r['text'])

    def test_text_and_block_limits(self):
        self.doc.add_paragraph('Second');self.save()
        with patch.object(adapter,'MAX_TEXT',5),self.assertRaises(ValueError):adapter.extract(self.file)
        with patch.object(adapter,'MAX_BLOCKS',1),self.assertRaises(ValueError):adapter.extract(self.file)

    def test_page_and_column_breaks_preserve_word_separators(self):
        from docx.enum.text import WD_BREAK
        for kind in (WD_BREAK.PAGE,WD_BREAK.COLUMN):
            self.doc=Document();run=self.doc.add_paragraph().add_run('Before')
            run.add_break(kind);run.add_text('After');self.save()
            with self.subTest(kind=kind):self.assertEqual(adapter.extract(self.file)['text'],'Before\nAfter')

    def test_alternate_main_part_cannot_bypass_preflight(self):
        self.save()
        with zipfile.ZipFile(self.file) as z:
            rels=z.read('_rels/.rels');body=z.read('word/document.xml');types=z.read('[Content_Types].xml')
        self.mutate('word/alternate.XML',body)
        self.mutate('_rels/.rels',rels.replace(b'word/document.xml',b'word/alternate.XML'))
        self.mutate('[Content_Types].xml',types.replace(b'/word/document.xml',b'/word/alternate.XML'))
        with self.assertRaises(ValueError):adapter.extract(self.file)
        tracked=body.replace(b'</w:body>',b'<w:ins><w:p><w:r><w:t>Inserted evidence</w:t></w:r></w:p></w:ins></w:body>')
        self.mutate('word/alternate.XML',tracked)
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_noncanonical_header_text_cannot_be_silently_dropped(self):
        self.save()
        self.mutate('custom/HEADER.XML',b'<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Header evidence</w:t></w:r></w:p></w:hdr>')
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_xml_content_type_with_binary_extension_is_checked(self):
        self.doc.sections[0].header.paragraphs[0].text='Header evidence';self.save()
        with zipfile.ZipFile(self.file) as z:parts={n:z.read(n) for n in z.namelist()}
        parts['custom/header.dat']=parts.pop('word/header1.xml')
        parts['word/_rels/document.xml.rels']=parts['word/_rels/document.xml.rels'].replace(b'header1.xml',b'../custom/header.dat')
        parts['[Content_Types].xml']=parts['[Content_Types].xml'].replace(b'/word/header1.xml',b'/custom/header.dat')
        with zipfile.ZipFile(self.file,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in parts.items():z.writestr(name,data)
        self.assertEqual(Document(self.file).sections[0].header.paragraphs[0].text,'Header evidence')
        with self.assertRaises(ValueError):adapter.extract(self.file)
        types=ET.fromstring(parts['[Content_Types].xml']);ct='{http://schemas.openxmlformats.org/package/2006/content-types}'
        header_type=None
        for child in list(types):
            if child.get('PartName')=='/custom/header.dat':
                header_type=child.get('ContentType');types.remove(child)
        ET.SubElement(types,ct+'Default',Extension='dat',ContentType=header_type)
        self.mutate('[Content_Types].xml',ET.tostring(types))
        self.assertEqual(Document(self.file).sections[0].header.paragraphs[0].text,'Header evidence')
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_corrupt_compressed_member_keeps_held_diagnostics(self):
        self.save()
        with zipfile.ZipFile(self.file) as z:offset=z.getinfo('word/document.xml').header_offset
        raw=bytearray(self.file.read_bytes());name_size,extra_size=struct.unpack_from('<HH',raw,offset+26)
        raw[offset+30+name_size+extra_size]=0x07;self.file.write_bytes(raw)
        out=self.root/'corrupt'
        result=subprocess.run([sys.executable,str(ROOT/'scripts/mnemosyne-docx.py'),str(self.file),'--output',str(out),'--collection','fixtures','--key','doc'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((out/'original.docx').read_bytes(),raw)
        self.assertTrue((out/'HELD-FOR-REVIEW.json').exists())
        self.assertFalse((out/'READY-FOR-REVIEW.json').exists())

    def test_unknown_container_and_hidden_default_refused(self):
        other=OxmlElement('w:customXml');self.doc._element.body.append(other);self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)
        self.doc=Document();self.doc.add_paragraph('Hidden by default')
        defaults=self.doc.styles.element.find(qn('w:docDefaults'))
        rpr=defaults.find('.//'+qn('w:rPr'));rpr.append(OxmlElement('w:vanish'));self.save()
        with self.assertRaises(ValueError):adapter.extract(self.file)

    def test_cli_and_isolated_catalog_roundtrip(self):
        self.doc.add_paragraph('Unusual test phrase for retrieval.');self.save()
        out=self.root/'stage';cmd=[sys.executable,str(ROOT/'scripts/mnemosyne-docx.py'),str(self.file),'--output',str(out),'--collection','fixtures','--key','doc']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((out/'original.docx').read_bytes(),self.file.read_bytes())
        draft=json.loads((out/'draft-manifest.json').read_text())
        self.assertFalse(draft['complete']);self.assertEqual(draft['sources'][0]['file_format'],'docx')
        with self.assertRaises(ValueError):library.prepare(draft,out)
        draft['complete']=True;db=self.root/'isolated.sqlite';library.initialize(db,draft,out)
        found=library.search(db,'Unusual test phrase',kind='note')['passages'][0]
        read=library.reader(db,found['source_id'])
        self.assertIsNone(read['blocks'][0]['pdf_page'])
        self.assertEqual(read['blocks'][0]['text'],(out/'text.txt').read_text())
        mapping=json.loads((out/'locations.json').read_text())
        self.assertEqual(mapping['text_sha256'],hashlib.sha256((out/'text.txt').read_bytes()).hexdigest())
        before={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
        self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir() if p.is_file()})

    def test_cli_holds_original_and_no_ready_inventory(self):
        self.doc.add_paragraph('List',style='List Number');self.save();out=self.root/'held'
        result=subprocess.run([sys.executable,str(ROOT/'scripts/mnemosyne-docx.py'),str(self.file),'--output',str(out),'--collection','fixtures','--key','doc'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((out/'original.docx').read_bytes(),self.file.read_bytes())
        self.assertTrue((out/'HELD-FOR-REVIEW.json').exists())
        self.assertFalse((out/'READY-FOR-REVIEW.json').exists())
        self.assertFalse((out/'draft-manifest.json').exists())

if __name__=='__main__':unittest.main()
