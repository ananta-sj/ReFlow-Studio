"""Dedicated source turns and clean per-character references for batch dubbing."""
import json
import math
import os
from pathlib import Path


def validate_turns(result):
    duration = result['audio_seconds']
    turns = result['turns']
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0 or not turns:
        raise ValueError('Speaker detection returned no usable turns')
    previous = 0.
    for row in turns:
        start, end = row['start'], row['end']
        if (any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end))
                or start < previous-.001 or end <= start or end > duration+.05
                or not isinstance(row['speaker'], str) or not row['speaker']):
            raise ValueError('Invalid exclusive speaker timeline')
        previous = end
    return turns


def clear_ranges(start, end, excluded):
    ranges = [(start, end)]
    for left, right in excluded:
        next_ranges = []
        for a, b in ranges:
            if right <= a or left >= b:
                next_ranges.append((a, b))
            else:
                if a < left:
                    next_ranges.append((a, left))
                if right < b:
                    next_ranges.append((right, b))
        ranges = next_ranges
    return ranges


def coalesce_turns(turns):
    """Join nearby turns of the same voice, without crossing a character change."""
    result = []
    for original in turns:
        row = dict(original)
        if row['end']-row['start'] < .12:
            continue  # Sub-syllabic detector fragments are not dialogue cues.
        if (result and result[-1]['speaker'] == row['speaker']
                and 0 <= row['start']-result[-1]['end'] <= .75
                and row['end']-result[-1]['start'] <= 8):
            result[-1]['end'] = row['end']
        else:
            result.append(row)
    return result


def references(audio, result, folder, excluded=()):
    """Never use overlapping voices or identified music as character anchors."""
    from pydub import AudioSegment
    from core.speaker_matching import speech_excerpt
    from core.render_context import check_cancelled
    turns = coalesce_turns(validate_turns(result))
    regular = result.get('overlapping_turns', turns)
    overlapping = []
    for index, left in enumerate(regular):
        for right in regular[index+1:]:
            if left['speaker'] == right['speaker']:
                continue
            a, b = max(left['start'], right['start']), min(left['end'], right['end'])
            if b > a:
                overlapping.append((a, b))
    candidates = {}
    for row in turns:
        check_cancelled()
        for start, end in clear_ranges(row['start'], row['end'], [*excluded, *overlapping]):
            clip = speech_excerpt(audio[round(start*1000):round(end*1000)])
            if clip is not None:
                candidates.setdefault(row['speaker'], []).append(clip[:6000])
    saved = {}
    for number, (label, clips) in enumerate(candidates.items()):
        clips.sort(key=len, reverse=True)
        reference = clips[0]
        if len(reference) < 6000:
            for extra in clips[1:]:
                reference += AudioSegment.silent(duration=100)+extra
                if len(reference) >= 6000:
                    break
        if len(reference) < 1500:
            continue
        target = Path(folder)/f'character-{number+1}.wav'
        reference[:6000].export(target, format='wav').close()
        saved[label] = str(target)
    return saved


def scene_references(audio,cues,folder,base_refs,excluded=(),overlapping_turns=()):
    """Prefer the current scene's confirmed voice; never borrow another actor."""
    from pydub import AudioSegment
    from core.speaker_matching import speech_excerpt
    from core.render_context import check_cancelled
    from core.media_io import _staged_output
    overlaps=[]
    for i,left in enumerate(overlapping_turns):
        for right in overlapping_turns[i+1:]:
            if left['speaker']!=right['speaker']:
                start,end=max(left['start'],right['start']),min(left['end'],right['end'])
                if end>start:overlaps.append((start,end))
    clips={};result={}
    for index,target in enumerate(cues):
        check_cancelled()
        speaker=target.get('speaker')
        if target.get('speaker_match')!='matched' or speaker not in base_refs:continue
        candidates=[j for j,cue in enumerate(cues) if cue.get('speaker')==speaker and cue.get('speaker_match')=='matched'
            and (j==index or abs((cue['start']+cue['end']-target['start']-target['end'])/2)<=45)]
        candidates.sort(key=lambda j:(j!=index,abs(cues[j]['start']-target['start'])))
        reference=AudioSegment.empty()
        contributors=[]
        for j in candidates:
            check_cancelled()
            if j not in clips:
                clips[j]=[]
                for start,end in clear_ranges(cues[j]['start'],cues[j]['end'],[*excluded,*overlaps]):
                    excerpt=speech_excerpt(audio[round(start*1000):round(end*1000)])
                    if excerpt is not None:clips[j].append(excerpt[:6000])
            for clip in clips[j]:
                if len(reference):reference+=AudioSegment.silent(duration=100)
                reference+=clip;contributors.append(j)
                if len(reference)>=6000:break
            if len(reference)>=6000:break
        # A weak current cue is not a reason to discard a stable reference.
        if index not in contributors or len(reference)<4000:continue
        from core.speech_performance import speech_ranges
        selected=reference[:6000]
        if sum(end-start for start,end in speech_ranges(selected,source=True))<3000:continue
        path=Path(folder)/f'scene-reference-{index+1}.wav'
        with _staged_output(str(path)) as pending:selected.export(pending,format='wav').close()
        result[target['cue_id']]=dict(reference=str(path),source_cues=[cues[j]['cue_id'] for j in dict.fromkeys(contributors)])
    return result


def prepare(audio_path, transcript, recognizer, device, manifest, namespace, excluded=(), reference_audio_path=None):
    import psutil
    from pydub import AudioSegment
    from core.diarization_runtime import validate
    from core.render_context import current_job, run_process, check_cancelled
    from core.python_runtime import project_root
    from core.transcription import normalize_transcription
    from core.pipeline_contracts import identify_cues
    from core.speech_performance import measure
    route = validate()
    job = current_job()
    if job is None:
        raise RuntimeError('Source character detection needs an owned job')
    folder = job.workspace/'community-speakers'
    folder.mkdir(exist_ok=True)
    output = folder/'turns.json'
    extra = []
    if transcript and all(cue.get('source_caption') is True for cue in transcript):
        cue_file = folder/'caption-windows.json'
        cue_file.write_text(json.dumps([dict(cue_id=c.get('cue_id','caption-'+str(i)),start=c['start'],end=c['end'],text=c['text'])
                                       for i,c in enumerate(transcript)]),encoding='utf-8')
        extra = ['--cues',str(cue_file)]
        if reference_audio_path:
            extra += ['--reference-audio',str(Path(reference_audio_path).resolve())]
    device = 'cuda:0' if str(device).startswith('cuda') else 'cpu'
    with (folder/'worker.log').open('wb') as log:
        try:
            run_process([route['executable'], '-B', str(project_root()/'core/diarization_worker.py'),
                str(Path(audio_path).resolve()), str(output), '--device', device, *extra],
                check=True, timeout=3600, stdout=log, stderr=log,
                env={**os.environ, 'PYTHONIOENCODING':'utf-8', 'REFLOW_PARENT_PID':str(os.getpid()),
                     'REFLOW_PARENT_CREATED':str(psutil.Process().create_time()), 'TEMP':str(folder), 'TMP':str(folder)})
        except Exception as error:
            raise RuntimeError('Dedicated speaker detection failed: '+
                (folder/'worker.log').read_text(encoding='utf-8', errors='replace')[-2400:]) from error
    result = json.loads(output.read_text(encoding='utf-8'))
    turns = coalesce_turns(validate_turns(result))
    if result.get('identity') != route['identity']:
        raise ValueError('Speaker model identity changed during inference')
    with Path(audio_path).open('rb') as stream:
        audio = AudioSegment.from_file(stream,format='wav').set_channels(1)
    reference_audio=audio
    if reference_audio_path:
        with Path(reference_audio_path).open('rb') as stream:
            reference_audio=AudioSegment.from_file(stream,format=Path(reference_audio_path).suffix.lstrip('.') or None).set_channels(1)
    if abs(len(reference_audio)-len(audio)) > 50:
        raise ValueError('Separated voice references are not aligned with the source timeline')
    if transcript and all(cue.get('source_caption') is True for cue in transcript):
        from core.caption_speakers import assign
        return assign(reference_audio, transcript, result, folder, namespace, manifest, excluded)
    destination = manifest.folder/'speaker-references' if manifest else folder/'references'
    destination.mkdir(exist_ok=True)
    anchors = references(reference_audio, result, destination, excluded)
    paths = []
    for index, turn in enumerate(turns):
        check_cancelled()
        clip = audio[round(turn['start']*1000):round(turn['end']*1000)]
        # Recognizers decode fixed windows. Padding is recognition-only; cue
        # positions remain the detector's original timeline.
        padded_ms = math.ceil((len(clip)+1000)/30000)*30000
        path = folder/f'turn-{index}.wav'
        (clip+AudioSegment.silent(duration=padded_ms-len(clip))).export(path, format='wav').close()
        paths.append(str(path))
    try:
        recognized = recognizer.transcribe_takes(paths, transcript.language or 'auto')
    finally:
        release = getattr(recognizer, 'release', None)
        if release:
            release()
    if len(recognized) != len(turns):
        raise RuntimeError('Speaker-aligned recognition returned an incomplete set of turns')
    cues, rows = [], []
    for index, (turn, recognized_turn) in enumerate(zip(turns, recognized)):
        text = ' '.join(cue['text'].strip() for cue in normalize_transcription(recognized_turn)
                        if cue['start'] < turn['end']-turn['start'] and any(c.isalnum() for c in cue['text']))
        cue = dict(start=turn['start'], end=turn['end'], text=text, source_text=text,
                   source_start=turn['start'], source_end=turn['end'], speaker=turn['speaker'])
        cues.append(cue)
        ref = anchors.get(turn['speaker']) if text else None
        rows.append(dict(index=index, start=turn['start'], end=turn['end'], speaker=turn['speaker'],
            status='matched' if ref else 'needs_review', reference=ref,
            reason=None if ref else 'source_transcription_uncertain' if not text else 'no_clean_character_reference',
            source_measure=measure(reference_audio[round(turn['start']*1000):round(turn['end']*1000)], pitch=True, source=True)))
    cues = transcript.with_segments(identify_cues(cues, namespace))
    for cue, row in zip(cues, rows):
        row['cue_id'] = cue['cue_id']
        cue['speaker_match'] = row['status']
    if manifest:
        manifest.report('batch-character-matching', dict(status='needs_review' if any(row['status'] != 'matched' for row in rows)
            else 'matched', engine='pyannote-community-1', speakers=[dict(speaker=label, reference=ref)
                for label,ref in anchors.items()], cues=rows, device=device))
    if not anchors:
        raise RuntimeError('No clean single-character references were found; source samples need review')
    return cues, {row['cue_id']:row for row in rows}
