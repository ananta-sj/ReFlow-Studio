"""Read-only comparison of tracked checkout files before consolidation."""
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OTHER=ROOT.parent/'Github'/'ReFlow-Studio'

def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args])

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    report={'native':str(ROOT),'github':str(OTHER),'different':[], 'github_only':[], 'same':0}
    paths=git(OTHER,'ls-files','-z').decode().split('\0')
    for name in filter(None,paths):
        left,right=ROOT/name,OTHER/name
        if not left.is_file():report['github_only'].append(name)
        elif digest(left)!=digest(right):report['different'].append(name)
        else:report['same']+=1
    for key,root in [('native',ROOT),('github',OTHER)]:
        report[key+'_head']=git(root,'rev-parse','HEAD').decode().strip()
        report[key+'_status']=git(root,'status','--porcelain').decode()
    destination=ROOT/'docs/diagnostics/checkout-consolidation.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('_status')},indent=2))

if __name__=='__main__':main()
