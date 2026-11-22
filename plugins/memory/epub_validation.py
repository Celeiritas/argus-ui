"""Optional local EPUBCheck adapter for staging; never called by reader requests."""
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile


def validate(source, jar, java, report):
    source, jar, report = Path(source).resolve(), Path(jar).resolve(), Path(report)
    if not jar.is_file(): raise ValueError('Configured EPUBCheck jar is missing')
    if report.exists() or report.with_suffix('.log').exists():
        raise ValueError('Choose new validation report paths; previous reports are retained')
    if source.stat().st_size > 64 * 1024 * 1024: raise ValueError('EPUB exceeds the validation size limit')
    try:
        with zipfile.ZipFile(source) as z:
            members=z.infolist();names=[i.filename for i in members]
            if len(members)>4096 or len(names)!=len(set(names)) or sum(i.file_size for i in members)>128*1024*1024:
                raise ValueError('EPUB container exceeds safe validation bounds')
            for i in members:
                p=PurePosixPath(i.filename)
                if p.is_absolute() or '..' in p.parts or '\\' in i.filename or ':' in i.filename or i.file_size>8*1024*1024 or i.flag_bits & 1:
                    raise ValueError('Unsafe, encrypted or oversized EPUB member')
    except zipfile.BadZipFile as e: raise ValueError('Not a readable EPUB archive') from e
    command=[str(java),'-Xmx512m','-jar',str(jar),str(source),'--json',str(report.resolve()),'--quiet','--locale','en']
    try:
        with report.with_suffix('.log').open('x',encoding='utf-8') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60,check=False)
    except subprocess.TimeoutExpired as e: raise ValueError('EPUBCheck timed out; source and partial report retained') from e
    try:
        if report.stat().st_size>16*1024*1024:raise ValueError('EPUBCheck report exceeds its limit')
        data=json.loads(report.read_text(encoding='utf-8'));checker=data['checker']
        counts={k:checker[k] for k in ('nFatal','nError','nWarning')}
        if any(type(v) is not int or v<0 for v in counts.values()):raise ValueError('Invalid validation counts')
        version=checker['checkerVersion']
        if not isinstance(version,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-zA-Z0-9.-]+)?',version):
            raise ValueError('Invalid validator version')
    except (OSError,KeyError,TypeError,json.JSONDecodeError) as e:
        raise ValueError('EPUBCheck did not produce a usable report; see the retained log') from e
    if result.returncode!=0 or counts['nFatal'] or counts['nError']:
        raise ValueError('EPUBCheck found errors or failed; review the retained validation report')
    return dict(tool='EPUBCheck',version=version,errors=0,warnings=counts['nWarning'],report=report.name)
