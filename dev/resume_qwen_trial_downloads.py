"""Small, bounded, retryable official byte-range downloads for this approved trial."""
import argparse,concurrent.futures,hashlib,json,shutil,sys,threading,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
import requests
from dev.prepare_qwen_dialogue_trial import ASSETS,sha,owned
RUNNER=dict(name='llama-b12375-bin-win-vulkan-x64.zip',size=38113510,sha256='8990615f25d4fa12a7f1d8fc9da995538ce739fec01838f003fa9ff099d643f0',url='https://github.com/ggml-org/llama.cpp/releases/download/b12375/llama-b12375-bin-win-vulkan-x64.zip')


def transfer(asset,target,seed=None,workers=16,probe=None):
    if target.is_file() and target.stat().st_size==asset['size'] and sha(target)==asset['sha256']:return True
    width=1024**2; folder=target.parent/('.segments-'+asset['sha256'][:16]);folder.mkdir(exist_ok=True)
    if seed and seed.is_file():
        with seed.open('rb') as stream:
            for i in range((seed.stat().st_size+width-1)//width):
                block=stream.read(width);piece=folder/str(i)
                if not piece.exists():piece.write_bytes(block)
    total=(asset['size']+width-1)//width; counts={i:(folder/str(i)).stat().st_size if (folder/str(i)).exists() else 0 for i in range(total)}
    lock=threading.Lock();last=[0.];deadline=time.monotonic()+1800
    def fetch(index):
        start=index*width;end=min(asset['size'],start+width)-1;piece=folder/str(index);size=end-start+1
        for attempt in range(6):
            offset=piece.stat().st_size if piece.exists() else 0
            if offset==size:return
            if offset>size:raise ValueError('Oversized source range')
            if time.monotonic()>deadline:raise TimeoutError('Trial download reached its 30-minute transfer budget')
            try:
                url=asset['url']+'?download=true&reflow_segment='+str(start+offset)
                with requests.get(url,headers={'Range':f'bytes={start+offset}-{end}','Accept-Encoding':'identity'},stream=True,timeout=(15,30)) as response:
                    response.raise_for_status()
                    if response.status_code!=206 or response.headers.get('Content-Range')!=f'bytes {start+offset}-{end}/{asset["size"]}':
                        raise ValueError('Range response did not match pinned source')
                    with piece.open('ab' if offset else 'wb') as stream:
                        for block in response.iter_content(64*1024):
                            if offset+len(block)>size:raise ValueError('Oversized range body')
                            stream.write(block);offset+=len(block)
                            with lock:
                                counts[index]=offset
                                if time.monotonic()-last[0]>10:
                                    print(json.dumps(dict(asset=asset['name'],downloaded_bytes=sum(counts.values()),total_bytes=asset['size'])),flush=True);last[0]=time.monotonic()
                if offset==size:return
            except requests.RequestException:
                if attempt==5:raise
            time.sleep(min(2**attempt,8))
        raise IOError('Range incomplete after bounded retries')
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(fetch,range(min(total,probe) if probe else total)))
    if probe:return False
    partial=target.with_suffix(target.suffix+'.verified-part')
    with partial.open('wb') as stream:
        for i in range(total):
            with (folder/str(i)).open('rb') as piece:shutil.copyfileobj(piece,stream)
    if partial.stat().st_size!=asset['size'] or sha(partial)!=asset['sha256']:raise ValueError('Pinned source checksum mismatch')
    partial.replace(target)
    for i in range(total):(folder/str(i)).unlink()
    folder.rmdir()
    print('Verified '+asset['name'],flush=True)
    return True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--asset',choices=['model','runner','all'],default='all');parser.add_argument('--probe',type=int);parser.add_argument('--workers',type=int,default=16);args=parser.parse_args()
    if not 1<=args.workers<=32:raise ValueError('Download concurrency must be between one and 32')
    runtime=ROOT/'runtime_profiles/dialogue-qwen-evaluation';downloads=ROOT/'build/qwen-dialogue-downloads'
    for folder in (runtime,downloads):owned(folder)
    for asset,target,seed in [(ASSETS[-1],runtime/'model.gguf',runtime/'model-native.gguf.part'),(RUNNER,downloads/RUNNER['name'],downloads/'vulkan-native.zip.part')]:
        kind='model' if asset['name'].endswith('gguf') else 'runner'
        if args.asset not in ('all',kind):continue
        completed=transfer(asset,target,seed,workers=args.workers,probe=args.probe)
        if completed and kind=='runner':
            with zipfile.ZipFile(target) as archive:
                for item in archive.infolist():
                    path=(runtime/'bin'/item.filename).resolve()
                    if not path.is_relative_to((runtime/'bin').resolve()) or ':' in item.filename or '\\' in item.filename or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive entry')
                archive.extractall(runtime/'bin')
    if (runtime/'model.gguf').is_file() and (runtime/'bin').is_dir():
        receipt=dict(status='prepared-for-isolated-evaluation',model=ASSETS[-1],runner=RUNNER,
            backend='portable Vulkan; existing NVIDIA driver',production_route_changed=False,
            files={str(p.relative_to(runtime)):sha(p) for p in [runtime/'model.gguf',*list((runtime/'bin').rglob('*'))] if p.is_file()})
        (runtime/'profile.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')


if __name__=='__main__':main()
