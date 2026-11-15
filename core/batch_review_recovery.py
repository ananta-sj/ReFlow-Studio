"""Recover text into an editable draft; never treat a batch diagnostic as approval."""
import hashlib,json
from pathlib import Path
from core.stage_checkpoints import safe_path


def payload(manifest_path):
    path=safe_path(manifest_path)
    if path.stat().st_size>32*1024*1024:raise ValueError('Oversized run record')
    manifest=json.loads(path.read_text(encoding='utf-8'))
    if path.name!='manifest.json' or manifest.get('run_id')!=path.parent.name:
        raise ValueError('Run identity changed')
    artifacts=manifest.get('cue_artifacts',[])
    selected=None
    for phase in ('speech-input','source-character-turns','source-captions','recognition-grouped'):
        selected=next((row for row in reversed(artifacts) if row.get('phase')==phase),None)
        if selected:break
    if not selected:raise ValueError('This run has no saved dialogue to recover')
    artifact=safe_path(selected['path'])
    if artifact.parent.resolve()!=path.parent.resolve() or artifact.stat().st_size>32*1024*1024:
        raise ValueError('Saved dialogue must belong to this run')
    raw=artifact.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=selected.get('sha256'):
        raise ValueError('Saved dialogue changed')
    cues=json.loads(raw.decode('utf-8')).get('segments')
    if not isinstance(cues,list) or not cues:raise ValueError('No saved dialogue')
    parameters=manifest['plan']['parameters']
    translated=selected['phase']=='speech-input'
    recovered=[]
    for cue in cues:
        source=cue.get('source_text') if translated else cue.get('text')
        if not isinstance(source,str) or not source.strip():
            raise ValueError('Saved dialogue lacks its original wording')
        recovered.append(dict(start=cue['start'],end=cue['end'],text=source,
            recovered_translation=cue['text'] if translated and not cue.get('translation_review') else None,
            original_cue_id=cue.get('cue_id')))
    preserved=[]
    caption_report=next((row for row in reversed(manifest.get('quality_reports',[]))
                         if row.get('kind')=='source-captions'),None)
    if caption_report:
        report_path=safe_path(caption_report['path'])
        if report_path.parent.resolve()!=path.parent.resolve() or report_path.stat().st_size>32*1024*1024:
            raise ValueError('Caption evidence must belong to this run')
        content=report_path.read_bytes()
        if hashlib.sha256(content).hexdigest()!=caption_report.get('sha256'):
            raise ValueError('Caption preservation evidence changed')
        evidence=json.loads(content.decode('utf-8'))
        if parameters.get('source_language') in (None,'auto'):
            parameters=dict(parameters,source_language=evidence.get('language','auto'))
        for event in evidence.get('preserved_events',[]):
            from core.dub_quality import MUSIC_REASONS
            if event.get('reason') in MUSIC_REASONS:
                if any(cue['start']<event['end'] and cue['end']>event['start'] for cue in recovered):
                    raise ValueError('Preserved song or sound overlaps saved dialogue; prepare a new review')
                preserved.append(dict(start=event['start'],end=event['end'],reason=event['reason']))
    return dict(run_id=manifest['run_id'],source=manifest['source'],parameters=parameters,
                cues=recovered,phase=selected['phase'],preserved_events=preserved)


def verify_source(recovery,input_path):
    from core.run_manifest import file_identity
    identity=file_identity(input_path)
    if any(identity[key]!=recovery['source'][key] for key in ('bytes','sha256')):
        raise ValueError('The original media changed; prepare a new review')
