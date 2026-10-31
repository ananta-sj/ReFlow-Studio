"""Verify installed RECORD payloads and collect notices without changing packages."""
import base64,csv,hashlib,json,os,sys
from email.parser import Parser
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.runtime_integrity import sha,safe_path

def main():
    from core.visual_runtime import validate,model_contract
    route=validate();model_contract(verify_weights=True)
    site=Path(route['profile'])/'Lib/site-packages';out=ROOT/'docs/validation';notices={};files={};skipped=[]
    notice_root=out/'2026-10-16-visual-candidate-notices';notice_root.mkdir(exist_ok=True)
    for metadata in sorted(site.glob('*.dist-info/METADATA')):
        name=Parser().parsestr(metadata.read_text(encoding='utf-8'))['Name'];notices[name]=[]
        for filename,digest,size in csv.reader((metadata.parent/'RECORD').read_text(encoding='utf-8').splitlines()):
            rel=PurePosixPath(filename.replace('\\','/'))
            if rel.is_absolute() or '..' in rel.parts or ':' in filename or any(part.endswith('.data') for part in rel.parts) or rel.suffix in {'.pyc','.pyo'}:
                skipped.append(dict(package=name,file=filename));continue
            path=safe_path(site.joinpath(*rel.parts));assert path.is_file(),(name,filename)
            actual=sha(path)
            if digest:assert digest=='sha256='+base64.urlsafe_b64encode(bytes.fromhex(actual)).decode().rstrip('='),(name,filename)
            if size:assert path.stat().st_size==int(size),(name,filename)
            key=str(path.relative_to(site));assert key not in files or files[key]==actual
            files[key]=actual
            if any(term in rel.name.lower() for term in ('license','licence','copying','notice')):
                target=notice_root/name/Path(*rel.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
                notices[name].append(dict(file=str(target.relative_to(ROOT)),sha256=actual))
    unexpected=[];total=0;count=0;caches=[]
    for folder,dirs,names in os.walk(Path(route['profile']),followlinks=False):
        for path in [Path(folder),*(Path(folder)/name for name in dirs+names)]:safe_path(path)
        caches.extend(str(Path(folder)/name) for name in dirs if name=='__pycache__')
        for filename in names:
            path=Path(folder)/filename;total+=path.stat().st_size;count+=1
            if path.is_relative_to(site) and str(path.relative_to(site)) not in files:unexpected.append(str(path.relative_to(site)))
    assert not unexpected,unexpected
    report=dict(passed=True,runtime_identity=route['identity'],package_count=len(notices),verified_payload_files=len(files),
        candidate_bytes=total,candidate_files=count,cache_directories=caches,skipped_record_entries=skipped,
        packages_without_installed_notice=[name for name,rows in notices.items() if not rows],package_notices=notices,
        distribution_rights_cleared=False,release_ready=False,model_hashes_verified=True,
        payload_sha256=files)
    (out/'2026-10-16-visual-candidate-payload.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key not in {'payload_sha256','package_notices','skipped_record_entries'}},indent=2))
if __name__=='__main__':main()
