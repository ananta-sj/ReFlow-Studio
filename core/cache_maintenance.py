"""Disposable source caches and positively identified abandoned job workspaces."""
import json,logging,math,os,shutil,stat,time
from pathlib import Path

SKIP={'.git','.venv','venv','runtime_profiles','build','models','node_modules',
      'outputs','output','temp','release-assets','docs','.codex','.agents','.aws'}

def plain(path):
    path=Path(os.path.abspath(path))
    for part in (*reversed(path.parents),path):
        if part.exists():
            info=part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Disposable cleanup cannot follow links or junctions')
    return path

def bytecode(project):
    root=plain(project);result=dict(files=0,bytes=0,directories=0,skipped=0)
    def remove(path):
        try:
            target=plain(path)
            if not target.is_relative_to(root) or target==root:raise ValueError('Cache escaped project')
            size=target.stat().st_size;target.unlink()
            result['files']+=1;result['bytes']+=size
        except (OSError,ValueError):result['skipped']+=1
    for directory,dirs,files in os.walk(root,followlinks=False):
        parent=Path(directory)
        for name in list(dirs):
            child=parent/name
            if name.casefold() in SKIP or child.is_symlink() or getattr(child.lstat(),'st_file_attributes',0)&0x400:
                dirs.remove(name);continue
            if name=='__pycache__':
                dirs.remove(name)
                for cached in child.iterdir():
                    if cached.is_file() and cached.suffix in ('.pyc','.pyo'):remove(cached)
                try:child.rmdir();result['directories']+=1
                except OSError:pass  # Unknown files are preserved, not classified as trash.
        for name in files:
            if Path(name).suffix in ('.pyc','.pyo'):remove(parent/name)
    return result

def abandoned_jobs(project,*,now=None,minimum_age=24*3600):
    import psutil
    root=plain(project);jobs=plain(root/'temp/jobs')
    result=dict(jobs=0,bytes=0,skipped=0)
    if not jobs.exists():return result
    now=time.time() if now is None else now
    for folder in jobs.iterdir():
        try:
            plain(folder)
            if not folder.is_dir() or not folder.name.startswith('job-'):continue
            marker=plain(folder/'workspace-owner.json')
            if not marker.is_file() or marker.stat().st_size>4096:continue
            owner=json.loads(marker.read_text(encoding='utf-8'))
            if not isinstance(owner,dict):continue
            if owner.get('schema')!='reflow.workspace-owner.v1' or owner.get('workspace')!=folder.name:continue
            pid,created,started=owner.get('pid'),owner.get('process_created'),owner.get('created_at')
            if type(pid) is not int or pid<=0 or any(type(v) not in (int,float) or not math.isfinite(v) for v in (created,started)):continue
            if now-started<minimum_age:continue
            try:
                if abs(psutil.Process(pid).create_time()-created)<.01:continue
            except psutil.NoSuchProcess:pass
            size=0
            # Validate every entry before any recursive deletion.
            for directory,dirs,files in os.walk(folder,followlinks=False):
                for name in dirs+files:plain(Path(directory)/name)
                size+=sum((Path(directory)/name).stat().st_size for name in files)
                if any(now-(Path(directory)/name).stat().st_mtime<minimum_age for name in files):
                    raise ValueError('Workspace has recent activity')
            shutil.rmtree(folder);result['jobs']+=1;result['bytes']+=size
        except (OSError,ValueError,psutil.Error):result['skipped']+=1
    return result

def maintain(project):
    result=dict(bytecode=bytecode(project),abandoned=abandoned_jobs(project))
    logging.getLogger(__name__).info('Disposable cleanup: %d bytecode files; %d abandoned jobs; %d bytes',
        result['bytecode']['files'],result['abandoned']['jobs'],result['bytecode']['bytes']+result['abandoned']['bytes'])
    return result
