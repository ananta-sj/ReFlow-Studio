"""Prepare GitHub-sized download parts using only Python/Windows built-ins."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): value.update(block)
    return value.hexdigest()


def write_helper(output,source_name,parts,whole_sha):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.zip',source_name) or not re.fullmatch(r'[0-9a-f]{64}',whole_sha):
        raise ValueError('Invalid assembly metadata')
    checks=[]
    for row in parts:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\.part[0-9]+',row['name']) or not re.fullmatch(r'[0-9a-f]{64}',row['sha256']):
            raise ValueError('Invalid download-part metadata')
        checks.append("if ((FileHash '%s') -ne '%s') { throw 'A download part is incomplete or changed. Download it again.' }" % (row['name'],row['sha256'].upper()))
    names=','.join("'%s'" % row['name'] for row in parts)
    function=("function FileHash($path) { $sha=[Security.Cryptography.SHA256]::Create(); try { $file=[IO.File]::OpenRead($path); "
        "try { return [BitConverter]::ToString($sha.ComputeHash($file)).Replace('-','') } finally { $file.Dispose() } } finally { $sha.Dispose() } }; ")
    command=("$ErrorActionPreference='Stop'; "+function+'; '.join(checks)+
        "; $parts=@(%s); $created=$false; try { $dest=[IO.File]::Open('%s',[IO.FileMode]::CreateNew); $created=$true; " % (names,source_name)+
        "try { foreach($part in $parts) { $stream=[IO.File]::OpenRead($part); try { $stream.CopyTo($dest) } finally { $stream.Dispose() } } } finally { $dest.Dispose() }; "+
        "if ((FileHash '%s') -ne '%s') { throw 'Combined ZIP checksum mismatch' } } " % (source_name,whole_sha.upper())+
        "catch { if($created) { [IO.File]::Delete('%s') }; throw }; [Console]::WriteLine('Verified ZIP created. Extract it and open ReflowStudio.exe.')" % source_name)
    script=('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
            'powershell.exe -NoProfile -Command "'+command+'"\r\n'
            'if errorlevel 1 (\r\n echo Assembly failed. No existing ZIP was replaced.\r\n'
            ' if not defined REFLOW_ASSEMBLY_NO_PAUSE pause\r\n exit /b 1\r\n)\r\n'
            'if not defined REFLOW_ASSEMBLY_NO_PAUSE pause\r\nexit /b 0\r\n')
    (output/'Assemble-ReflowStudio.cmd').write_bytes(script.encode('ascii'))
    sums=[row['sha256']+'  '+row['name'] for row in parts]
    sums += [digest(output/'Assemble-ReflowStudio.cmd')+'  Assemble-ReflowStudio.cmd']
    (output/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='ascii')


def split(source,output,part_bytes=1_900_000_000):
    source=source.resolve();output=output.resolve()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.zip',source.name):
        raise ValueError('Use a simple ASCII ZIP filename')
    if not 1<=part_bytes<2*1024**3:
        raise ValueError('Release parts must be under 2 GiB')
    if output.exists(): raise RuntimeError('Download folder already exists; refusing replacement')
    output.mkdir(parents=True)
    parts=[];whole=hashlib.sha256()
    with source.open('rb') as stream:
        index=0
        while True:
            block=stream.read(min(1024*1024,part_bytes))
            if not block: break
            index+=1;remaining=part_bytes;value=hashlib.sha256();written=0
            name=source.name+'.part%02d' % index
            with (output/name).open('xb') as target:
                while block:
                    target.write(block);value.update(block);whole.update(block)
                    written+=len(block);remaining-=len(block)
                    if not remaining: break
                    block=stream.read(min(1024*1024,remaining))
            parts.append(dict(name=name,bytes=written,sha256=value.hexdigest()))
    if not parts: raise ValueError('Cannot split an empty ZIP')
    if whole.hexdigest()!=digest(source): raise RuntimeError('Source changed while splitting')
    joined=hashlib.sha256()
    for row in parts:
        if digest(output/row['name'])!=row['sha256']: raise RuntimeError('Part copy differs')
        with (output/row['name']).open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''): joined.update(block)
    if joined.hexdigest()!=whole.hexdigest(): raise RuntimeError('Parts do not reproduce original ZIP')
    write_helper(output,source.name,parts,whole.hexdigest())
    (output/'README.txt').write_text('Download every .part file and Assemble-ReflowStudio.cmd into ONE folder.\n'
        'Double-click Assemble-ReflowStudio.cmd. It verifies each part and creates the complete ZIP.\n'
        'It uses built-in Windows tools; no extra archive software is needed.\n'
        'Then extract the complete ZIP and open ReflowStudio.exe inside its folder.\n'
        'Keep all application companion files. The EXE alone will not run.\n'
        'An existing complete ZIP is never overwritten. Keep the parts until assembly succeeds.\n'
        'This is a test candidate; no release has been published.\n',encoding='utf-8')
    report=dict(source_name=source.name,source_bytes=source.stat().st_size,source_sha256=whole.hexdigest(),
                parts=parts,parts_reproduce_original=True,github_each_part_under_2_GiB=True,
                release_ready=False)
    (output/'download-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'dist'):
        raise ValueError('Download output must be inside dist')
    print(json.dumps(split(args.source,args.output),indent=2),flush=True)


if __name__=='__main__': main()
