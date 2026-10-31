"""Conservative deletion inventories. Execution receives server-generated plans."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid


def _inside(path, root):
    return path == root or root in path.parents


def safe_path(path, base):
    base = Path(base).absolute()
    path = Path(path).absolute()
    if path == base or not _inside(path, base):
        raise ValueError(f"Refusing deletion path outside owned storage: {path}")
    for entry in (base, path):
        if entry.exists() or entry.is_symlink():
            if entry.is_symlink() or getattr(entry.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError(f"Refusing reparse path: {entry}")
    parent = path.parent
    while parent != base:
        if parent.is_symlink() or (parent.exists() and getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError(f"Refusing reparse path: {parent}")
        parent = parent.parent
    if path.resolve() != path or base.resolve() != base:
        raise ValueError(f"Refusing noncanonical path: {path}")
    return path


def inventory(path, base):
    path = safe_path(path, base)
    entries = []
    if not path.exists():
        return {'path': str(path), 'files': 0, 'bytes': 0, 'entries': []}
    pending = [path]
    while pending:
        entry = safe_path(pending.pop(), base)
        stat = entry.lstat()
        directory = entry.is_dir()
        entries.append([str(entry), directory, stat.st_size, stat.st_mtime_ns])
        if directory:
            pending.extend(entry.iterdir())
    entries.sort()
    files = [entry for entry in entries if not entry[1]]
    return {'path': str(path), 'files': len(files), 'bytes': sum(entry[2] for entry in files), 'entries': entries}


def fingerprint(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode('utf-8')).hexdigest()


def model_plan(base, models, entry, all_entries):
    model_id = entry['id']
    if str(uuid.UUID(model_id)) != model_id.lower():
        raise ValueError('Invalid model identifier.')
    base = Path(base).absolute()
    models = safe_path(models, base)
    owned = safe_path(models / '_downloads' / model_id, base)
    retained = []
    shared = []
    for other in all_entries:
        if other['id'] != model_id and other.get('local_path'):
            reference = Path(other['local_path']).absolute().resolve()
            if _inside(reference, owned) or _inside(owned, reference):
                shared.append(other['id'])
    candidates = []
    if shared:
        retained.append({'path': str(owned), 'reason': 'Referenced by another model entry.'})
    else:
        candidates.append(inventory(owned, base))
    local = entry.get('local_path')
    if local and (shared or not _inside(Path(local).absolute(), owned)
                  or Path(local).absolute().resolve() != Path(local).absolute()):
        retained.append({'path': str(local), 'reason': 'Exclusive entry ownership is unverified; connection only will be removed.'})
    return {'operation': 'model', 'model_id': model_id, 'candidates': candidates,
            'retained': retained, 'registry': all_entries}


def reset_plan(base, temp, outputs, models):
    base = Path(base).absolute()
    protected_names = {'.git', '.codex', '.agents', '.aws', '.venv', 'venv', 'build',
                       'models', 'sample', 'samples', 'inputs', 'ffmpeg', 'node_modules',
                       '.cancellation-npm-cache', '.deletion-npm-cache'}
    protected = [base / name for name in protected_names] + [Path(models).absolute()]
    roots = [safe_path(temp, base), safe_path(outputs, base)]
    if _inside(roots[0], roots[1]) or _inside(roots[1], roots[0]):
        raise ValueError('Reset directories overlap.')
    for root in roots:
        if any(_inside(root, keep) or _inside(keep, root) for keep in protected):
            raise ValueError(f'Reset directory overlaps protected storage: {root}')
    candidates = [inventory(root, base) for root in roots]
    for directory, dirs, files in os.walk(base, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            child = parent / name
            if (name.lower() in protected_names or any(_inside(child, root) for root in roots)
                    or any(_inside(child, keep) for keep in protected)
                    or child.is_symlink() or getattr(child.lstat(), 'st_file_attributes', 0) & 0x400):
                dirs.remove(name)
            elif name == '__pycache__':
                candidates.append(inventory(child, base))
                dirs.remove(name)
    return {'operation': 'reset', 'candidates': candidates, 'retained': [],
            'recreate': [str(root) for root in roots]}


def public_preview(plan, token):
    return {'ok': True, 'token': token, 'candidates': [
        {key: candidate[key] for key in ('path', 'files', 'bytes')} for candidate in plan['candidates']],
        'retained': plan['retained'],
        'files': sum(candidate['files'] for candidate in plan['candidates']),
        'bytes': sum(candidate['bytes'] for candidate in plan['candidates'])}


def execute(plan, base):
    removed = []
    try:
        for candidate in plan['candidates']:
            path = safe_path(candidate['path'], base)
            # Revalidate each tree immediately before deleting it too.
            if inventory(path, base) != candidate:
                raise ValueError('Files changed after preview; request a new preview.')
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            removed.append(str(path))
            if str(path) in plan.get('recreate', []):
                path.mkdir(parents=True, exist_ok=True)
        return {'ok': True, 'removed': removed, 'retained': plan['retained']}
    except (OSError, ValueError) as exc:
        return {'ok': False, 'message': f'{exc} Some files may already have been removed; review the remaining paths before retrying.', 'removed': removed,
                'remaining': [item['path'] for item in plan['candidates'] if item['path'] not in removed],
                'retained': plan['retained']}
