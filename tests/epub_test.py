"""Synthetic EPUBs only: chapter order, bounded offline parsing and deliberate refusals."""
import importlib.util
from pathlib import Path
import tempfile
import json
import subprocess
import sys
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('epub',Path(__file__).resolve().parents[1]/'plugins/memory/epub.py')
epub=importlib.util.module_from_spec(spec);spec.loader.exec_module(epub)

class EpubTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'book.epub'
        self.files={
          'mimetype':'application/epub+zip',
          'META-INF/container.xml':'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>',
          'OPS/book.opf':'<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Example book</dc:title><dc:creator>Fixture author</dc:creator></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="b"/><itemref idref="a" linear="no"/></spine></package>',
          'OPS/a.xhtml':'<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Appendix</h1><p>Secondary text.</p></body></html>',
          'OPS/b.xhtml':'<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Beginning</h1><p>Hello <em>reader</em>.</p><script>forbidden script</script><p>Next paragraph.</p></body></html>'}
    def write(self):
        with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as z:
            for name,value in self.files.items():z.writestr(name,value)
    def test_staging_cli_preserves_original_and_requires_collection_review(self):
        self.write();out=self.path.parent/'staged'
        cli=Path(__file__).resolve().parents[1]/'scripts/mnemosyne-epub.py'
        command=[sys.executable,str(cli),str(self.path),'--output',str(out),'--collection','books','--key','fixture']
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        draft=json.loads((out/'draft-manifest.json').read_text(encoding='utf-8'))
        self.assertFalse(draft['complete']);self.assertEqual(draft['sources'][0]['kind'],'book')
        self.assertEqual((out/'original.epub').read_bytes(),self.path.read_bytes())
        again=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(again.returncode,0)

    def test_spine_order_inline_text_and_non_linear_content(self):
        self.write();r=epub.extract(self.path)
        self.assertEqual(r['title'],'Example book');self.assertEqual(r['authorship'],'Fixture author')
        self.assertEqual([c['member'] for c in r['chapters']],['OPS/b.xhtml','OPS/a.xhtml'])
        self.assertIn('Hello reader.',r['chapters'][0]['text'])
        self.assertNotIn('forbidden',r['chapters'][0]['text'])
        self.assertFalse(r['chapters'][1]['linear'])
    def test_external_spine_and_traversal_refused(self):
        original=self.files['OPS/book.opf']
        for href in ('https://example.invalid/book.xhtml','../../outside.xhtml','%2foutside.xhtml'):
            self.files['OPS/book.opf']=original.replace('a.xhtml',href);self.write()
            with self.subTest(href=href), self.assertRaises(ValueError):epub.extract(self.path)
    def test_member_traversal_and_duplicate_names_refused(self):
        self.files['../outside']='No';self.write()
        with self.assertRaises(ValueError):epub.extract(self.path)
        self.files.pop('../outside');self.write()
        with zipfile.ZipFile(self.path,'a') as z:z.writestr('mimetype','application/epub+zip')
        with self.assertRaises(ValueError):epub.extract(self.path)
    def test_doctype_rejected_in_utf8_and_utf16(self):
        source='<!DOCTYPE html [<!ENTITY bomb "EXPAND">]><html xmlns="http://www.w3.org/1999/xhtml"><body>&bomb;</body></html>'
        for encoding in ('utf-8','utf-16'):
            self.files['OPS/a.xhtml']=source.encode(encoding);self.write()
            with self.subTest(encoding=encoding),self.assertRaises(ValueError):epub.extract(self.path)
    def test_encryption_fixed_layout_and_math_refused(self):
        self.files['META-INF/encryption.xml']='<encryption/>';self.write()
        with self.assertRaises(ValueError):epub.extract(self.path)
        self.files.pop('META-INF/encryption.xml')
        original=self.files['OPS/book.opf']
        self.files['OPS/book.opf']=original.replace('</metadata>','<meta property="rendition:layout">pre-paginated</meta></metadata>');self.write()
        with self.assertRaises(ValueError):epub.extract(self.path)
        self.files['OPS/book.opf']=original
        self.files['OPS/a.xhtml']=self.files['OPS/a.xhtml'].replace('</body>','<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math></body>');self.write()
        with self.assertRaises(ValueError):epub.extract(self.path)
    def test_size_and_xml_depth_limits(self):
        self.write();limit=epub.MAX_MEMBER
        try:
            epub.MAX_MEMBER=100
            with self.assertRaises(ValueError):epub.extract(self.path)
        finally:epub.MAX_MEMBER=limit
        self.files['OPS/a.xhtml']='<html xmlns="http://www.w3.org/1999/xhtml"><body>'+'<div>'*110+'x'+'</div>'*110+'</body></html>';self.write()
        with self.assertRaises(ValueError):epub.extract(self.path)

if __name__=='__main__':unittest.main()
