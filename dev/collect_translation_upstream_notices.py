"""Collect version-tagged missing license texts without changing packages."""
import hashlib
import json
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
SOURCES={
    'sentencepiece':'https://raw.githubusercontent.com/google/sentencepiece/v0.2.2/LICENSE',
    'tokenizers':'https://raw.githubusercontent.com/huggingface/tokenizers/v0.23.3/LICENSE',
}


def main():
    notices=OUT/'2026-10-16-translation-candidate-notices'
    receipts=[]
    for name,url in SOURCES.items():
        with urllib.request.urlopen(url,timeout=25) as response:
            assert urlsplit(response.url).hostname=='raw.githubusercontent.com'
            payload=response.read(100_001)
        assert len(payload)<=100_000 and b'Apache License' in payload[:150]
        target=notices/name/'upstream-version-tag-LICENSE.txt'
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
        receipts.append(dict(package=name,url=url,file=str(target.relative_to(ROOT)),
            sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),origin='upstream version tag; absent from installed RECORD'))
    result=dict(collected=True,packages_modified=False,package_archives_downloaded=False,
                sources=receipts,distribution_rights_cleared=False,release_ready=False)
    (OUT/'2026-10-16-translation-candidate-upstream-notices.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
