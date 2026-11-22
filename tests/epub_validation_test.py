"""Optional validator integration without Java downloads in CI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

s=importlib.util.spec_from_file_location('validation',Path(__file__).resolve().parents[1]/'plugins/memory/epub_validation.py')
v=importlib.util.module_from_spec(s);s.loader.exec_module(v)

class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/'book.epub';self.jar=self.root/'epubcheck.jar';self.jar.write_bytes(b'fixture')
        self.report=self.root/'validation.json'
        with zipfile.ZipFile(self.source,'w') as z:z.writestr('mimetype','application/epub+zip')
    def run_validator(self):return v.validate(self.source,self.jar,'java fixture',self.report)
    def fake(self,cmd,**kwargs):
        self.assertEqual(cmd[0],'java fixture');self.assertNotIn('shell',kwargs)
        self.assertEqual(kwargs['timeout'],60);self.assertIn('-Xmx512m',cmd)
        self.report.write_text(json.dumps(dict(checker=dict(checkerVersion='5.4.0',nFatal=0,nError=0,nWarning=2))),encoding='utf-8')
        return types.SimpleNamespace(returncode=0)
    def test_valid_report_retains_warnings_and_uses_argument_list(self):
        with patch.object(v.subprocess,'run',self.fake):r=self.run_validator()
        self.assertEqual(r['warnings'],2);self.assertEqual(r['tool'],'EPUBCheck')
    def test_nonzero_exit_cannot_be_treated_as_success(self):
        def failed(cmd,**kwargs):self.fake(cmd,**kwargs);return types.SimpleNamespace(returncode=1)
        with patch.object(v.subprocess,'run',failed),self.assertRaises(ValueError):self.run_validator()
    def test_error_count_even_with_zero_exit_is_held(self):
        def failed(cmd,**kwargs):
            self.fake(cmd,**kwargs);d=json.loads(self.report.read_text());d['checker']['nError']=1;self.report.write_text(json.dumps(d));return types.SimpleNamespace(returncode=0)
        with patch.object(v.subprocess,'run',failed),self.assertRaises(ValueError):self.run_validator()
    def test_missing_report_and_timeout_fail_closed(self):
        with patch.object(v.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)),self.assertRaises(ValueError):self.run_validator()
        self.report=self.root/'timeout.json'
        with patch.object(v.subprocess,'run',side_effect=subprocess.TimeoutExpired('java',60)),self.assertRaisesRegex(ValueError,'timed out'):self.run_validator()
    def test_unsafe_archive_never_starts_java(self):
        with zipfile.ZipFile(self.source,'a') as z:z.writestr('../outside','bad')
        with patch.object(v.subprocess,'run') as run,self.assertRaises(ValueError):self.run_validator()
        run.assert_not_called()
    def test_existing_report_and_missing_jar_refused(self):
        self.report.write_text('keep',encoding='utf-8')
        with self.assertRaises(ValueError):self.run_validator()
        self.assertEqual(self.report.read_text(),'keep')
        self.report=self.root/'new.json';self.jar=self.root/'missing.jar'
        with self.assertRaises(ValueError):self.run_validator()

if __name__=='__main__':unittest.main()
