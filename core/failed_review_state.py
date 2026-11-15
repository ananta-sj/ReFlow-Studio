"""Persist a bounded run identifier, never an arbitrary review file path."""
import json
from pathlib import Path
import re
import config
from core.json_store import JsonStore,require
from core.stage_checkpoints import safe_path


def _validate(value):
    require(isinstance(value,dict) and set(value)=={'version','run_id'},'Invalid dialogue review marker')
    require(value['version']==1 and type(value['version']) is int,'Invalid dialogue review marker version')
    require(isinstance(value['run_id'],str) and re.fullmatch('[a-f0-9]{32}',value['run_id']) is not None,'Invalid dialogue review run')
    return value


def _store():
    return JsonStore(safe_path(Path(config.OUTPUT_PATH)/'last-dialogue-review.json'),None,_validate)


def remember(manifest_path):
    path=safe_path(manifest_path).resolve()
    records=safe_path(Path(config.OUTPUT_PATH)/'run_records').resolve()
    if path.name!='manifest.json' or path.parent.parent!=records or path.stat().st_size>32*1024*1024:
        raise ValueError('Dialogue review must belong to this application run')
    marker=_validate(dict(version=1,run_id=path.parent.name))
    manifest=json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('run_id')!=marker['run_id']:raise ValueError('Dialogue review run identity changed')
    _store().replace(marker)


def recall():
    marker=_store().read()
    if marker is None:return None
    path=safe_path(Path(config.OUTPUT_PATH)/'run_records'/marker['run_id']/'manifest.json')
    if not path.is_file():return None
    if path.stat().st_size>32*1024*1024:raise ValueError('Dialogue review manifest is too large')
    if json.loads(path.read_text(encoding='utf-8')).get('run_id')!=marker['run_id']:
        raise ValueError('Dialogue review run identity changed')
    return str(path)


def clear():
    _store().clear()
