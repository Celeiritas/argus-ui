#!/usr/bin/env python3
"""Stage supported DOCX text for review. Never publish or replace a collection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'plugins/memory'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def main():
    importer=module('docx_import');library=module('library')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--collection',required=True);p.add_argument('--key',required=True)
    p.add_argument('--kind',choices=library.KINDS,default='note')
    a=p.parse_args();created=False
    def save(name, value):
        with (a.output/name).open('x',encoding='utf-8',newline='') as f:
            json.dump(value,f,ensure_ascii=False,indent=2)
    try:
        if a.output.exists():raise ValueError('Choose a new staging directory; existing files are kept')
        with a.file.open('rb') as f:raw=f.read(importer.MAX_ARCHIVE+1)
        if len(raw)>importer.MAX_ARCHIVE:raise ValueError('DOCX exceeds 64 MB')
        a.output.mkdir(mode=0o700,parents=True,exist_ok=False);created=True
        original=a.output/'original.docx'
        with original.open('xb') as f:f.write(raw)
        digest=hashlib.sha256(raw).hexdigest();del raw
        result=importer.extract(original,fallback_title=a.file.stem)
        if result['source_version']!=digest:raise ValueError('Staged original changed')
        text=result.pop('text');locations=result.pop('locations')
        with (a.output/'text.txt').open('x',encoding='utf-8',newline='') as f:f.write(text)
        mapping=dict(schema='mnemosyne-docx-locations/1',source_sha256=digest,
                     text_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                     offset_unit='unicode-code-points',locations=locations)
        save('locations.json',mapping)
        record=dict(result,collection=a.collection,key=a.key,kind=a.kind,file_format='docx',health='ready',
                    page_scheme='none',text='text.txt',diagnostic='DOCX body paragraphs and table cells in document order. Tables are linearized; styling and pagination are not reproduced. Original and exact block/cell offset map retained in staging.')
        manifest=dict(schema='mnemosyne-manifest/1',complete=True,collections=[a.collection],sources=[record])
        library.prepare(manifest,a.output)
        if hashlib.sha256(original.read_bytes()).hexdigest()!=digest:raise ValueError('Staged original changed')
        manifest['complete']=False
        save('draft-manifest.json',manifest)
        save('READY-FOR-REVIEW.json',dict(original='original.docx',sha256=digest,blocks=len(locations),published=False))
        print(json.dumps(dict(staged=True,blocks=len(locations),published=False,message='Review text and combine into a complete collection inventory; draft cannot be published as-is.')))
        return 0
    except (ValueError,OSError) as e:
        if created:save('HELD-FOR-REVIEW.json',dict(published=False,reason=str(e)))
        print('Not published: '+str(e),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
