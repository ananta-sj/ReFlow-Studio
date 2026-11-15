"""Download only the explicitly approved, pinned portable dialogue trial."""
import hashlib,json,os,shutil,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
import requests
from concurrent.futures import ThreadPoolExecutor
import threading

ASSETS=[
 dict(name='llama-b12375-bin-win-cuda-12.4-x64.zip',size=319401248,sha256='8b7bf8f3b5269531cbf00c52e4ee5d8b0c77cb4ea7af694ed3da3a34e47a7099',url='https://github.com/ggml-org/llama.cpp/releases/download/b12375/llama-b12375-bin-win-cuda-12.4-x64.zip'),
 dict(name='cudart-llama-bin-win-cuda-12.4-x64.zip',size=391443627,sha256='8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6',url='https://github.com/ggml-org/llama.cpp/releases/download/b12375/cudart-llama-bin-win-cuda-12.4-x64.zip'),
 dict(name='Qwen3-4B-Q4_K_M.gguf',size=2497280256,sha256='7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5',url='https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf')]


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):value.update(block)
    return value.hexdigest()


def owned(path):
    if path.exists() and (not (path/'.owner').is_file() or (path/'.owner').read_text()!='reflow.qwen-dialogue-trial.v1'):
        raise ValueError('Unrecognized trial folder: '+str(path))
    path.mkdir(parents=True,exist_ok=True)
    (path/'.owner').write_text('reflow.qwen-dialogue-trial.v1')


def download(asset,path):
    if path.is_file() and path.stat().st_size==asset['size'] and sha(path)==asset['sha256']:
        print('Verified existing '+asset['name'],flush=True);return
    partial=path.with_suffix(path.suffix+'.part')
    pieces=path.parent/('.chunks-'+asset['sha256'][:16]);pieces.mkdir(exist_ok=True)
    width=32*1024*1024; lock=threading.Lock(); last=[0.]; counts={}
    def fetch(index):
        start=index*width;end=min(asset['size'],start+width)-1
        piece=pieces/str(index);expected=end-start+1
        offset=piece.stat().st_size if piece.exists() else 0
        counts[index]=offset
        if offset==expected:return piece
        if offset>expected:raise ValueError('Oversized range fragment')
        url=asset['url']+'?reflow_range='+str(start+offset)
        with requests.get(url,headers={'Range':f'bytes={start+offset}-{end}'},stream=True,timeout=(30,60)) as response:
            response.raise_for_status()
            required=f'bytes {start+offset}-{end}/{asset["size"]}'
            if response.status_code!=206 or response.headers.get('Content-Range')!=required:
                raise ValueError('Download server did not honor the pinned byte range')
            with piece.open('ab' if offset else 'wb') as stream:
                for block in response.iter_content(256*1024):
                    stream.write(block);offset+=len(block)
                    if offset>expected:raise ValueError('Range exceeded pinned size')
                    with lock:
                        counts[index]=offset
                        if time.monotonic()-last[0]>15:
                            print(asset['name']+f' {sum(counts.values())/asset["size"]:.0%}',flush=True);last[0]=time.monotonic()
        if offset!=expected:raise ValueError('Incomplete range; rerun to resume')
        return piece
    with ThreadPoolExecutor(max_workers=8) as pool:
        completed=list(pool.map(fetch,range((asset['size']+width-1)//width)))
    with partial.open('wb') as output:
        for piece in completed:
            with piece.open('rb') as stream:shutil.copyfileobj(stream,output)
    if partial.stat().st_size!=asset['size'] or sha(partial)!=asset['sha256']:
        raise ValueError('Pinned download checksum mismatch: '+asset['name'])
    partial.replace(path)
    for piece in completed:piece.unlink()
    pieces.rmdir()
    print('Checksum verified '+asset['name'],flush=True)


def main():
    if shutil.disk_usage(ROOT).free<8*1024**3:raise ValueError('Need 8 GiB free for isolated trial')
    runtime=ROOT/'runtime_profiles/dialogue-qwen-evaluation';downloads=ROOT/'build/qwen-dialogue-downloads'
    for folder in (runtime,downloads):owned(folder)
    before={name:sha(ROOT/name) for name in ('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')}
    for asset in ASSETS:
        target=(runtime/'model.gguf') if asset['name'].endswith('.gguf') else downloads/asset['name']
        download(asset,target)
        if asset['name'].endswith('.zip'):
            with zipfile.ZipFile(target) as archive:
                for item in archive.infolist():
                    destination=(runtime/'bin'/item.filename).resolve()
                    if ('\\' in item.filename or ':' in item.filename or not destination.is_relative_to((runtime/'bin').resolve())
                            or (item.external_attr>>16)&0o170000==0o120000):raise ValueError('Unsafe archive member')
                archive.extractall(runtime/'bin')
            target.unlink()
    after={name:sha(ROOT/name) for name in before}
    if before!=after:raise ValueError('Application configuration changed during preparation')
    report=dict(status='prepared-for-evaluation',approved=True,model_revision='bc640142c66e1fdd12af0bd68f40445458f3869b',
        runtime_release='b12375',download_bytes=sum(a['size'] for a in ASSETS),assets=ASSETS,
        files={str(p.relative_to(runtime)):sha(p) for p in runtime.rglob('*') if p.is_file() and p.name!='profile.json'},
        application_configuration=after,production_route_changed=False)
    (runtime/'profile.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'docs/validation/2026-11-14-qwen-trial-preparation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Prepared verified isolated trial; application settings unchanged.',flush=True)


if __name__=='__main__':main()
