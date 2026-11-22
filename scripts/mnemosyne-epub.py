#!/usr/bin/env python3
"""Stage one EPUB as a draft source record; never publish or retire a collection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'plugins/memory'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def main():
    epub=module('epub');library=module('library')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--collection',required=True);p.add_argument('--key',required=True)
    p.add_argument('--kind',choices=library.KINDS,default='book');a=p.parse_args()
    try:
        if a.output.exists():raise ValueError('Choose a new staging directory; existing files are kept')
        extracted=epub.extract(a.file)
        a.output.mkdir(parents=True,exist_ok=False);(a.output/'texts').mkdir()
        chapters=[]
        for n,chapter in enumerate(extracted.pop('chapters'),1):
            text=chapter.pop('text');relative=f'texts/chapter-{n:04}.txt'
            (a.output/relative).write_text(text,encoding='utf-8',newline='')
            chapters.append(dict(chapter,text=relative))
        record=dict(extracted,collection=a.collection,key=a.key,kind=a.kind,file_format='epub',health='ready',
                    page_scheme='none',chapters=chapters,diagnostic='EPUB text extraction; images and layout are not reproduced. Original retained in import staging.')
        manifest=dict(schema='mnemosyne-manifest/1',complete=True,collections=[a.collection],sources=[record])
        library.prepare(manifest,a.output)
        shutil.copyfile(a.file,a.output/'original.epub')
        if hashlib.sha256((a.output/'original.epub').read_bytes()).hexdigest()!=record['source_version']:
            raise ValueError('Original changed during staging; nothing published')
        manifest['complete']=False
        (a.output/'draft-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        (a.output/'READY-FOR-REVIEW.json').write_text(json.dumps(dict(original='original.epub',sha256=record['source_version'],chapters=len(chapters),published=False)),encoding='utf-8')
        print(json.dumps(dict(staged=True,chapters=len(chapters),published=False,message='Review the text, then combine this source into a complete collection inventory. The draft cannot be published as-is.')))
        return 0
    except (ValueError,OSError) as e:
        print('Not published: '+str(e),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
