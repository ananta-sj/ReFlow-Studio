"""A concise, persistent list of batch lines requiring a listening decision."""
import json
from pathlib import Path


def build(manifest_path):
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    def read_artifact(value):
        from core.stage_checkpoints import safe_path
        artifact = safe_path(value).resolve()
        if not artifact.is_relative_to(path.parent.resolve()) or artifact.stat().st_size > 32*1024*1024:
            raise ValueError('Review artifact must belong to this run')
        return json.loads(artifact.read_text(encoding='utf-8'))
    speech_cues = {}
    for phase in ('speech-input','source-character-turns','source-captions','recognition-grouped'):
        artifact = next((a for a in reversed(manifest.get('cue_artifacts',[])) if a['phase']==phase),None)
        if artifact:
            payload = read_artifact(artifact['path'])
            speech_cues = {cue.get('cue_id'):cue for cue in payload.get('segments', [])}
            break
    decisions = {}
    def add(cue, reason):
        key = cue.get('cue_id') or str(cue.get('index'))
        row = decisions.setdefault(key, dict(cue_id=cue.get('cue_id'), index=cue.get('index'),
            start=cue.get('start'), end=cue.get('end'), reasons=[]))
        if cue.get('observed'):
            row['observed'] = str(cue['observed'])[:800]
        if reason not in row['reasons']:
            row['reasons'].append(reason)
        return row
    reports = manifest.get('quality_reports', [])
    latest_readback = next((item['path'] for item in reversed(reports) if item['kind'] == 'batch-intelligibility'), None)
    coverage = None
    for item in reports:
        if item['kind']=='dub-coverage':
            coverage = read_artifact(item['path'])
            for cue in coverage['cues']:
                add(cue,cue['reason'])
            continue
        if item['kind'] == 'batch-intelligibility' and item['path'] != latest_readback:
            continue
        if item['kind'] not in ('batch-character-matching', 'batch-delivery', 'batch-intelligibility', 'original-audio-kept', 'translation-integrity', 'dialogue-integrity','measured-speech-timing'):
            continue
        payload = read_artifact(item['path'])
        if item['kind']=='measured-speech-timing':
            import math
            row=add(payload,'timing_overflow')
            values={name:payload.get(name) for name in ('measured_seconds','available_seconds','excess_seconds')}
            if all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values.values()):
                if payload.get('candidate') or not row.get('has_saved_take'):
                    row['timing']=values
                    row['has_saved_take']=bool(payload.get('candidate'))
        elif item['kind'] == 'batch-character-matching':
            for cue in payload['cues']:
                if cue['status'] != 'matched':
                    add(cue, cue.get('reason') or 'character_uncertain')
        elif item['kind'] == 'batch-delivery' and payload['status'] == 'needs_review':
            for reason in payload['reasons']:
                add(payload, reason)
        elif item['kind'] == 'original-audio-kept':
            for cue in payload['cues']:
                add(cue, 'original_audio_retained: '+cue['reason'])
        elif item['kind'] == 'batch-intelligibility':
            for cue in payload['cues']:
                if cue.get('status') == 'needs_review' or payload.get('error'):
                    add(cue, cue.get('reason') or payload.get('reason') or 'speech_readback_mismatch')
        elif item['kind'] in ('translation-integrity', 'dialogue-integrity'):
            add(payload, payload['reason'])
    result = dict(status='needs_review' if decisions else 'no_acoustic_flags',
                  human_quality_accepted=False, manifest=str(path), cues=list(decisions.values()),coverage=coverage)
    for row in result['cues']:
        source = speech_cues.get(row['cue_id'], {})
        for name in ('start', 'end'):
            if row[name] is None:
                row[name] = source.get(name)
        row['text'] = str(source.get('text', ''))[:800]
        row['source_text'] = str(source.get('source_text', ''))[:800]
    return result


def timing_candidate(manifest_path,cue_id):
    """Read only a checksum-verified overlong take retained inside this run."""
    import hashlib
    from core.stage_checkpoints import safe_path
    path=safe_path(manifest_path)
    if path.stat().st_size>32*1024*1024:raise ValueError('Oversized run record')
    manifest=json.loads(path.read_text(encoding='utf-8'))
    for item in reversed(manifest.get('quality_reports',[])):
        if item.get('kind')!='measured-speech-timing':continue
        report=safe_path(item['path'])
        if report.parent.resolve()!=path.parent.resolve() or report.stat().st_size>1024*1024:
            raise ValueError('Timing evidence must belong to this run')
        body=report.read_bytes()
        if item.get('sha256') and hashlib.sha256(body).hexdigest()!=item['sha256']:
            raise ValueError('Timing evidence changed')
        payload=json.loads(body.decode('utf-8'))
        if payload.get('cue_id')!=cue_id or not payload.get('candidate'):continue
        candidate=payload['candidate'];audio=safe_path(candidate['path'])
        if audio.parent.resolve()!=path.parent.resolve() or audio.suffix.lower()!='.wav':
            raise ValueError('Saved take must belong to this run')
        if not 0<audio.stat().st_size<=16*1024*1024:raise ValueError('Saved take is too large')
        raw=audio.read_bytes()
        if len(raw)!=candidate.get('bytes') or hashlib.sha256(raw).hexdigest()!=candidate.get('sha256'):
            raise ValueError('Saved take changed')
        return raw
    raise ValueError('No saved timing take is available for this line')


def publish(manifest_path, output_path):
    result = build(manifest_path)
    destination = Path(str(output_path)+'.review.json')
    from core.run_manifest import _publish_bytes
    _publish_bytes(destination, (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    return result
