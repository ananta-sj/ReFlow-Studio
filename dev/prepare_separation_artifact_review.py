"""Bounded official release metadata only; no package archives or installation."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from inspect_desktop_dependency_projection import TAGS
from packaging.utils import parse_wheel_filename
from packaging.specifiers import SpecifierSet


def main():
    folder=ROOT/'docs/validation'
    feasibility=json.loads((folder/'2026-10-16-separation-dependency-feasibility.json').read_text())
    results=[]
    for name in feasibility['legacy_packages_requiring_artifact_review']:
        version=feasibility['sources'][name]['version']
        url=f'https://pypi.org/pypi/{name}/{version}/json'
        row=dict(name=name,version=version,metadata_url=url)
        try:
            with urllib.request.urlopen(url,timeout=25) as response:
                assert urlsplit(response.url).hostname=='pypi.org'
                data=response.read(8_000_001)
            if len(data)>8_000_000:raise ValueError('Metadata exceeds bound')
            value=json.loads(data)
            (folder/f'2026-10-16-separation-{name}-release.json').write_bytes(data)
            row.update(requires_python=value['info'].get('requires_python'),requires_dist=value['info'].get('requires_dist') or [])
            wheels=[];sources=[]
            for artifact in value['urls']:
                if artifact.get('yanked'):continue
                if artifact.get('requires_python') and '3.13.16' not in SpecifierSet(artifact['requires_python']):continue
                candidate=dict(filename=artifact['filename'],bytes=artifact['size'],sha256=artifact['digests']['sha256'],url=artifact['url'])
                parsed=urlsplit(candidate['url'])
                assert parsed.scheme=='https' and parsed.hostname=='files.pythonhosted.org'
                if artifact['packagetype']=='bdist_wheel' and parse_wheel_filename(artifact['filename'])[3]&set(TAGS):wheels.append(candidate)
                elif artifact['packagetype']=='sdist':sources.append(candidate)
            row.update(compatible_wheels=wheels,source_archives=sources,source_build_needed=not wheels and bool(sources),
                       no_compatible_artifact=not wheels and not sources)
        except Exception as error:row.update(error_type=type(error).__name__,error=str(error))
        results.append(row)
        print(name,version,'metadata reviewed' if 'compatible_wheels' in row else row['error'],flush=True)
    report=dict(metadata_only=True,package_archives_downloaded=False,packages_installed=False,models_downloaded=False,
        target_python='3.13.16',release_ready=False,ready_to_install=False,packages=results,
        source_build_packages=[row['name'] for row in results if row.get('source_build_needed')],
        unresolved_packages=[row['name'] for row in results if row.get('error') or row.get('no_compatible_artifact')],
        limitations=['Existing local versions were inspected, not recommended as current secure pins.',
            'No wheel METADATA resolver lock, source build, advisory scan or modern Demucs inference acceptance is claimed.',
            'Adding or building packages requires separate explicit approval after the full proposal is ready.'])
    (folder/'2026-10-16-separation-artifact-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
