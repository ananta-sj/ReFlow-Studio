"""Independently check the dry-run report against Windows CPython 3.13 markers."""
import hashlib
import json
from pathlib import Path
import argparse
from urllib.parse import unquote, urlsplit
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.tags import cpython_tags, compatible_tags

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='scoped-mirror')
    parser.add_argument('--plan',type=Path,default=OUT/'2026-10-13-runtime-repair-plan.json')
    parser.add_argument('--prefix',default='xtts-candidate')
    args=parser.parse_args()
    assert args.label.replace('-','').isalnum() and args.prefix.replace('-','').isalnum()
    assert args.plan.resolve().is_relative_to(OUT.resolve())
    report = json.loads((OUT/f'2026-10-13-xtts-{args.label}-resolution-report.json').read_text(encoding='utf-8'))
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    selected = {canonicalize_name(item['metadata']['name']): item for item in report['install']}
    env = default_environment()
    env.update(python_version='3.13', python_full_version='3.13.16', os_name='nt',
               sys_platform='win32', platform_system='Windows', platform_machine='AMD64',
               implementation_name='cpython', platform_python_implementation='CPython',
               implementation_version='3.13.16')
    extras = {name:set() for name in selected}
    # Propagate requested extras to a fixed point before validating all active edges.
    for _ in range(len(selected)+1):
        changed = False
        for name, item in selected.items():
            for value in item['metadata'].get('requires_dist', []):
                req = Requirement(value)
                active = not req.marker or any(req.marker.evaluate(dict(env, extra=e)) for e in {''}|extras[name])
                dep = canonicalize_name(req.name)
                if active and dep in extras:
                    before = len(extras[dep]); extras[dep].update(req.extras)
                    changed |= before != len(extras[dep])
        if not changed: break
    tags = set(cpython_tags((3,13), abis=['cp313'], platforms=['win_amd64']))
    tags.update(compatible_tags((3,13), interpreter='cp313', platforms=['win_amd64']))
    issues=[]; edges=[]; artifacts=[]
    for name,item in selected.items():
        meta=item['metadata']; info=item['download_info']; url=info['url']
        filename=unquote(urlsplit(url).path.rsplit('/',1)[-1])
        digest=info.get('archive_info',{}).get('hashes',{}).get('sha256')
        try: compatible=bool(parse_wheel_filename(filename)[3]&tags)
        except Exception: compatible=False
        if not compatible: issues.append(f'{name}: incompatible/missing wheel')
        if not digest or len(digest)!=64: issues.append(f'{name}: missing SHA256')
        if meta.get('requires_python') and '3.13.16' not in SpecifierSet(meta['requires_python']):
            issues.append(f'{name}: Python requirement excludes target')
        for value in meta.get('requires_dist',[]):
            req=Requirement(value)
            if req.marker and not any(req.marker.evaluate(dict(env,extra=e)) for e in {''}|extras[name]): continue
            dep=canonicalize_name(req.name)
            ok=dep in selected and selected[dep]['metadata']['version'] in req.specifier
            edges.append(dict(parent=name,requirement=value,satisfied=ok))
            if not ok: issues.append(f'{name}: unsatisfied {value}')
        artifacts.append(dict(name=name,version=meta['version'],url=url,filename=filename,
                              sha256=digest,license=meta.get('license'),
                              license_expression=meta.get('license_expression'),
                              requested_extras=sorted(extras[name])))
    for root in plan['xtts_candidate_roots']:
        name=canonicalize_name(root['name'])
        if name not in selected or selected[name]['metadata']['version']!=root['version']:
            issues.append(f'{name}: root pin not satisfied')
    reachable={canonicalize_name(root['name']) for root in plan['xtts_candidate_roots']}
    for _ in range(len(selected)+1):
        before=len(reachable)
        for edge in edges:
            if edge['parent'] in reachable:
                reachable.add(canonicalize_name(Requirement(edge['requirement']).name))
        if len(reachable)==before: break
    excluded=sorted(set(selected)-reachable)
    artifacts=[item for item in artifacts if item['name'] in reachable]
    edges=[edge for edge in edges if edge['parent'] in reachable]
    lock=dict(schema='reflow.xtts.candidate-lock.review.v1',target_environment=env,
              metadata_closure_valid=not issues,install_authorized=False,
              runtime_execution_verified=False,release_ready=False,
              packages=sorted(artifacts,key=lambda x:x['name']),edges=edges,issues=issues,
              excluded_host_marker_packages=excluded,
              download_size_verified=False,notice_review_complete=False)
    (OUT/f'2026-10-13-{args.prefix}-lock-review.json').write_text(json.dumps(lock,indent=2),encoding='utf-8')
    if not issues:
        lines=['# Review candidate only; installation NOT authorized. Windows CPython 3.13.16.',
               '# Exact artifact URLs/hashes; local Docopt wheel is retained alongside this evidence.']
        for item in lock['packages']:
            lines.append(f"{item['name']} @ {item['url']} --hash=sha256:{item['sha256']}")
        (OUT/f'2026-10-13-{args.prefix}-review.lock.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(packages=len(artifacts),active_edges=len(edges),excluded_host_marker_packages=excluded,issues=issues),indent=2))
    return bool(issues)

if __name__=='__main__':raise SystemExit(main())
