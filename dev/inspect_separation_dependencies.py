"""Installed metadata only: identify Demucs gaps without importing AI packages."""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from core.runtime_integrity import sha


def installed(folder):
    groups={};invalid=[]
    for dist in metadata.distributions(path=[str(folder/'Lib/site-packages')]):
        name=dist.metadata.get('Name')
        if not name or not dist.version:
            invalid.append(str(dist._path));continue
        groups.setdefault(canonicalize_name(name),[]).append(dist)
    return groups,invalid


def main():
    legacy,invalid_legacy=installed(ROOT/'build/windows-portable')
    modern,invalid_modern=installed(ROOT/'runtime_profiles/xtts-security-candidate')
    env={**default_environment(),'python_version':'3.13','python_full_version':'3.13.16','extra':''}
    pending=['demucs'];selected={};missing=[];conflicts=[];links=[]
    while pending:
        name=canonicalize_name(pending.pop())
        if name in selected:continue
        options=modern.get(name) or legacy.get(name)
        if not options:
            missing.append(name);selected[name]=None;continue
        if len(options)!=1:
            conflicts.append(dict(package=name,reason='duplicate metadata',versions=[dist.version for dist in options]));selected[name]=None;continue
        dist=options[0]
        source='modern' if name in modern else 'legacy'
        selected[name]=dict(version=dist.version,source=source,requires_python=dist.metadata.get('Requires-Python'),
            metadata_sha256=sha(Path(dist._path)/'METADATA'),wheel=dist.read_text('WHEEL'),requires_dist=dist.requires or [])
        for raw in dist.requires or []:
            req=Requirement(raw)
            if req.marker and not req.marker.evaluate(env):continue
            dependency=canonicalize_name(req.name);candidates=modern.get(dependency) or legacy.get(dependency) or []
            links.append(dict(parent=name,requirement=raw,dependency=dependency))
            if len(candidates)==1 and req.specifier and not req.specifier.contains(candidates[0].version,prereleases=True):
                conflicts.append(dict(package=dependency,parent=name,required=str(req.specifier),available=candidates[0].version))
            pending.append(dependency)
    report=dict(metadata_only=True,packages_installed=False,artifacts_downloaded=False,models_downloaded=False,
        proposed_runtime_built=False,ready_to_install=False,release_ready=False,target_python='3.13.16',
        sources=selected,missing_metadata=sorted(set(missing)),conflicts=conflicts,active_links=links,
        malformed_distribution_paths=dict(legacy=invalid_legacy,modern=invalid_modern),
        legacy_packages_requiring_artifact_review=sorted(name for name,row in selected.items() if row and row['source']=='legacy'),
        limitations=['This is not a resolver lock or approval request.',
            'Requires-Python, wheel/native ABI, extras, transitive provenance and current advisories require a reviewed artifact plan.',
            'Existing legacy metadata is inconsistent; never select among duplicate distributions implicitly.',
            'Demucs compatibility with modern Torch and real stem quality have not been established.'])
    target=ROOT/'docs/validation/2026-10-16-separation-dependency-feasibility.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
