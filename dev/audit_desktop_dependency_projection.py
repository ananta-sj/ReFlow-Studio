"""Point-in-time public advisory check for the desktop package proposal."""
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', choices=['desktop-candidate', 'desktop-security-candidate'], default='desktop-candidate')
    parser.add_argument('--resolved-lock', action='store_true')
    parser.add_argument('--lock-path', type=Path)
    parser.add_argument('--output-prefix')
    args = parser.parse_args()
    destination = OUT / ('2026-10-13-desktop-resolved-lock-advisories.json' if args.resolved_lock
                         else '2026-10-13-' + args.prefix + '-advisories.json')
    if args.output_prefix:
        assert args.output_prefix.replace('-', '').isalnum()
        destination = OUT / (args.output_prefix + '-advisories.json')
    assert not destination.exists(), 'Preserve historical advisory evidence'
    source = OUT / ('2026-10-13-desktop-candidate-lock-review.json' if args.resolved_lock
                    else '2026-10-13-' + args.prefix + '-dependency-projection.json')
    if args.lock_path:
        source = args.lock_path.resolve()
        assert source.is_relative_to(OUT.resolve())
    projection = json.loads(source.read_text())
    queries = [dict(package=dict(name=row['name'], ecosystem='PyPI'), version=row['version'])
               for row in projection['packages']]
    request = urllib.request.Request('https://api.osv.dev/v1/querybatch',
        data=json.dumps(dict(queries=queries)).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read(5_000_001)
    assert len(payload) <= 5_000_000
    data = json.loads(payload)
    assert len(data['results']) == len(queries)
    matches = [dict(package=query['package']['name'], version=query['version'], vulns=result['vulns'])
               for query, result in zip(queries, data['results']) if result.get('vulns')]
    receipt = dict(source='https://api.osv.dev/v1/querybatch', checked_at=datetime.now(timezone.utc).isoformat(),
                   complete=True, packages=len(queries), matches=matches,
                   match_count=sum(len(row['vulns']) for row in matches),
                   security_certification=False, packages_installed=False)
    destination.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
