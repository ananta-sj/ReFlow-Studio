"""Measure candidate artifact download sizes using metadata/HEAD only."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import argparse
from pathlib import Path
from urllib.parse import urlsplit
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'

def measure(item):
    name=item['name']; url=item['url']; parsed=urlsplit(url)
    result=dict(name=name,version=item['version'])
    if parsed.scheme=='file':
        import urllib.request as request
        path=Path(request.url2pathname(parsed.path))
        assert path.resolve().is_relative_to((OUT/'2026-10-13-docopt-helper').resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
        result.update(bytes=path.stat().st_size,source='approved local build',sha256_verified=True)
    elif name in {'torch','torchaudio'} or name=='torchcodec' and '+' in item['version']:
        assert parsed.scheme=='https' and parsed.hostname in {'download.pytorch.org','download-r2.pytorch.org'}
        head_url=url.replace('https://download-r2.pytorch.org/','https://download.pytorch.org/')
        with urllib.request.urlopen(urllib.request.Request(head_url,method='HEAD'),timeout=30) as response:
            result.update(bytes=int(response.headers['Content-Length']),source=head_url,sha256_verified=True,
                          hash_basis='published index hash retained in pip report; archive not fetched')
    else:
        source=f"https://pypi.org/pypi/{name}/{item['version']}/json"
        with urllib.request.urlopen(source,timeout=30) as response:
            payload=response.read(5000001)
        assert len(payload)<=5000000
        metadata=json.loads(payload)
        matches=[row for row in metadata['urls'] if row['filename']==item['filename'] and row['digests']['sha256']==item['sha256']]
        assert len(matches)==1
        row=matches[0]
        result.update(bytes=row['size'],source=source,sha256_verified=True,yanked=row['yanked'],
                      license_expression=metadata['info'].get('license_expression'),
                      license=metadata['info'].get('license'))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prefix',default='xtts-candidate');args=parser.parse_args()
    assert args.prefix.replace('-','').isalnum()
    path=OUT/f'2026-10-13-{args.prefix}-lock-review.json'
    lock=json.loads(path.read_text(encoding='utf-8'))
    results=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[(item,pool.submit(measure,item)) for item in lock['packages']]
        for item,future in futures:
            try: results.append(future.result())
            except Exception as error: results.append(dict(name=item['name'],error=str(error)))
    complete=all('bytes' in row and row.get('sha256_verified') for row in results)
    receipt=dict(metadata_only=True,archives_downloaded=False,runtime_installed=False,
                 complete=complete,packages=results,total_artifact_bytes=sum(row.get('bytes',0) for row in results),
                 extracted_install_size_verified=False)
    destination=OUT/('2026-10-13-xtts-download-budget.json' if args.prefix=='xtts-candidate' else f'2026-10-13-{args.prefix}-download-budget.json')
    destination.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    lock.update(download_size_verified=complete,artifact_download_bytes=receipt['total_artifact_bytes'])
    path.write_text(json.dumps(lock,indent=2),encoding='utf-8')
    print(json.dumps(dict(complete=complete,total_artifact_bytes=receipt['total_artifact_bytes'],errors=[r for r in results if 'error' in r]),indent=2))
    return not complete

if __name__=='__main__':raise SystemExit(main())
