"""Check installed Python source against distribution RECORD hashes, read-only."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'runtime_profiles/xtts-security-candidate/Lib/site-packages'
OUT=ROOT/'docs/validation'

def main():
    checked=0;byte_count=0;failures=[];distributions=0
    for record in SITE.glob('*.dist-info/RECORD'):
        distributions+=1
        for name,digest,size in csv.reader(io.StringIO(record.read_text(encoding='utf-8'))):
            if not name.endswith('.py') or not digest:continue
            parts=PurePosixPath(name)
            # Generated host console launchers were deliberately removed.
            if '..' in parts.parts or parts.is_absolute():continue
            source=SITE/name
            if not source.is_file():failures.append(dict(file=name,error='missing'));continue
            payload=source.read_bytes()
            expected='sha256='+base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip('=')
            if digest!=expected or len(payload)!=int(size):failures.append(dict(file=name,error='hash/size mismatch'))
            checked+=1;byte_count+=len(payload)
    report=dict(passed=distributions==99 and checked>1000 and not failures,
        distributions=distributions,python_source_files_checked=checked,source_bytes_checked=byte_count,
        failures=failures,third_party_sources_modified=False,
        scope='Hashed in-profile Python sources only; not a native binary security audit')
    (OUT/'2026-10-13-xtts-security-candidate-source-records.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return not report['passed']

if __name__=='__main__':raise SystemExit(main())
