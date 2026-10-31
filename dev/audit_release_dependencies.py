"""Inventory installed distribution metadata/notices without loading AI models."""
from collections import Counter
import hashlib
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    packages = []
    for distribution in metadata.distributions():
        name = distribution.metadata.get('Name') or '(missing name)'
        licenses = []
        for file in distribution.files or []:
            if 'license' in str(file).lower() or Path(file).name.lower().startswith('notice'):
                path = Path(distribution.locate_file(file))
                if path.is_file():
                    licenses.append(dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size))
        packages.append(dict(name=name, version=distribution.version,
            declared_license=distribution.metadata.get('License'),
            license_expression=distribution.metadata.get('License-Expression'),
            project_urls=distribution.metadata.get_all('Project-URL') or [], notices=licenses))
    counts = Counter(item['name'].lower().replace('_','-') for item in packages)
    duplicates = {name:[item['version'] for item in packages if item['name'].lower().replace('_','-')==name]
                  for name,count in counts.items() if count>1}
    result = subprocess.run([sys.executable,'-B','-m','pip','check'],capture_output=True,
        text=True,encoding='utf-8',errors='replace',timeout=120)
    (OUT/'2026-10-12-core-dependency-check-captured.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    ffmpeg = subprocess.run([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-version'],capture_output=True,
        text=True,encoding='utf-8',errors='replace',timeout=30)
    bundled_notices = [str(path.relative_to(ROOT)) for path in (ROOT/'ffmpeg').rglob('*')
                      if path.is_file() and any(word in path.name.lower() for word in ('license','notice','copying'))]
    report = dict(schema='reflow.release-dependency-inventory.v1', interpreter=sys.executable,
        distributions=sorted(packages,key=lambda item:(item['name'].lower(),item['version'])),
        duplicate_distribution_metadata=duplicates, pip_check_exit_code=result.returncode,
        dependency_consistency_passed=result.returncode==0 and not duplicates,
        root_license_sha256=digest(ROOT/'LICENSE.txt'),
        root_license_contains_python_history='HISTORY OF THE SOFTWARE' in (ROOT/'LICENSE.txt').read_text(encoding='utf-8'),
        app_license_selected=False, legal_clearance=False,
        ffmpeg_version=ffmpeg.stdout.splitlines()[:4], ffmpeg_bundled_notices=bundled_notices,
        ffmpeg_legal_guidance='https://ffmpeg.org/legal.html',
        limitations=['Inventory is not a legal clearance or vulnerability audit.',
                    'Optional environments and downloaded model terms require their own inventory.',
                    'Duplicate metadata can conceal overwritten runtime files; do not delete metadata as a dependency repair.'])
    path=OUT/'2026-10-12-release-dependency-inventory.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(report=str(path),packages=len(packages),duplicates=duplicates,
        pip_check_exit_code=result.returncode, ffmpeg_notices=len(bundled_notices)),indent=2))


if __name__=='__main__':main()
