"""Conservative source-voice references for normal batch dubbing."""
import json
from pathlib import Path


def pause_turns(audio, start, end):
    """Split long ASR blocks only at measured silence, never inside a word."""
    from pydub.silence import detect_nonsilent
    import math
    clip = audio[round(start*1000):round(end*1000)]
    if len(clip) <= 3000 or not math.isfinite(clip.dBFS):
        return [(start, end)]
    regions = detect_nonsilent(clip, min_silence_len=180, silence_thresh=max(-48, clip.dBFS-16))
    cuts = [0]
    for left, right in zip(regions, regions[1:]):
        cut = (left[1]+right[0])//2
        if cut-cuts[-1] >= 800 and len(clip)-cut >= 800:
            cuts.append(cut)
    cuts.append(len(clip))
    return [(start+left/1000, min(end, start+right/1000)) for left, right in zip(cuts, cuts[1:])]


def refine_turns(audio_path, transcript, provider):
    from pydub import AudioSegment
    from core.render_context import current_job, check_cancelled
    from core.transcription import normalize_transcription
    from core.pipeline_contracts import identify_cues
    with open(audio_path, 'rb') as source_audio:
        audio = AudioSegment.from_wav(source_audio).set_channels(1)
    folder = current_job().workspace/'source-turns'
    folder.mkdir(exist_ok=True)
    plans, paths = [], []
    for index, cue in enumerate(transcript):
        turns = pause_turns(audio, cue['start'], cue['end'])
        plans.append(turns)
        if len(turns) > 1:
            for part, (start, end) in enumerate(turns):
                check_cancelled()
                path = folder/f'{index}-{part}.wav'
                clip = audio[round(start*1000):round(end*1000)]
                (clip+AudioSegment.silent(duration=max(1000, 30000-len(clip)))).export(path, format='wav').close()
                paths.append(str(path))
    if not paths:
        return transcript
    try:
        results = provider.transcribe_takes(paths, transcript.language or 'auto')
    finally:
        release = getattr(provider, 'release', None)
        if release:
            release()
    if len(results) != len(paths):
        raise RuntimeError('Source-turn recognition returned incomplete dialogue')
    offset, refined = 0, []
    for cue, turns in zip(transcript, plans):
        if len(turns) == 1:
            refined.append(dict(cue))
            continue
        candidates = []
        for start, end in turns:
            result = normalize_transcription(results[offset])
            offset += 1
            text = ' '.join(row['text'].strip() for row in result
                            if row['start'] < end-start and any(c.isalnum() for c in row['text']))
            candidates.append(dict(start=start, end=end, text=text,
                                   source_text=text, source_start=start, source_end=end))
        refined.extend(candidates if all(row['text'] for row in candidates) else [dict(cue)])
    return transcript.with_segments(identify_cues(refined, 'source-character-turns'))


def group_vectors(vectors, minimum_similarity=.62):
    import numpy as np
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    matrix = np.asarray(vectors, dtype=float)
    if matrix.ndim != 2 or not len(matrix) or not np.isfinite(matrix).all():
        raise ValueError('Invalid speaker embeddings')
    norms = np.linalg.norm(matrix, axis=1)
    if (norms <= 0).any():
        raise ValueError('Empty speaker embedding')
    matrix = matrix / norms[:, None]
    similarities = np.clip(matrix @ matrix.T, -1, 1)
    distances = 1-similarities
    np.fill_diagonal(distances, 0)
    labels = ([1] if len(matrix) == 1 else fcluster(
        linkage(squareform(distances, checks=False), method='complete'),
        1-minimum_similarity, criterion='distance').tolist())
    # IDs follow first occurrence rather than the arbitrary cluster numbering.
    names = {}
    for label in labels:
        names.setdefault(label, 'Speaker '+str(len(names)+1))
    return [names[label] for label in labels], similarities


def analyze(audio_path, cues, folder, encode):
    from pydub import AudioSegment
    from core.speaker_matching import speech_excerpt
    from core.render_context import check_cancelled
    with open(audio_path, 'rb') as source_audio:
        audio = AudioSegment.from_wav(source_audio).set_channels(1)
    clips, vectors, indices, rows = {}, [], [], []
    for index, cue in enumerate(cues):
        check_cancelled()
        row = dict(index=index, cue_id=cue.get('cue_id'), start=cue['start'], end=cue['end'],
                   status='needs_review', reason='insufficient_speech')
        rows.append(row)
        from core.speech_performance import measure
        row['source_measure'] = measure(audio[round(cue['start']*1000):round(cue['end']*1000)],
                                        pitch=True, source=True)
        if any(j != index and min(cue['end'], other['end'])-max(cue['start'], other['start']) > .08
               for j, other in enumerate(cues)):
            row['reason'] = 'overlapping_speech'
            continue
        clip = speech_excerpt(audio[round(cue['start']*1000):round(cue['end']*1000)])
        if clip is None:
            continue
        clip = clip[:6000]
        clips[index] = clip
        indices.append(index)
        vectors.append(encode(clip))
    if not vectors:
        return dict(status='needs_review', speakers=[], cues=rows)
    labels, similarities = group_vectors(vectors)
    groups = {}
    for position, label in enumerate(labels):
        groups.setdefault(label, []).append(position)
    speakers = []
    for label, positions in groups.items():
        candidates = [p for p in positions if len(clips[indices[p]]) >= 1500]
        if len(positions) < 2 or not candidates:
            for p in positions:
                rows[indices[p]]['reason'] = 'unconfirmed_character'
            continue
        others = [p for p in range(len(labels)) if p not in positions]
        confident = []
        for p in positions:
            own = min(float(similarities[p, q]) for q in positions if q != p)
            other = max((float(similarities[p, q]) for q in others), default=-1)
            if own-other >= .10:
                confident.append(p)
            else:
                rows[indices[p]]['reason'] = 'ambiguous_character'
        candidates = [p for p in candidates if p in confident]
        if len(confident) < 2 or not candidates:
            continue
        best = max(candidates, key=lambda p: len(clips[indices[p]]))
        reference = Path(folder)/('speaker-'+str(indices[best])+'.wav')
        clips[indices[best]].export(reference, format='wav').close()
        speakers.append(dict(speaker=label, reference=str(reference), reference_cue=indices[best]))
        for p in confident:
            index = indices[p]
            # Detect handoffs within a recognizer cue. Never label mixed turns
            # merely because their combined embedding matched one character.
            clip = clips[index]
            mixed = False
            if len(clip) >= 2400:
                import numpy as np
                for part in (clip[:len(clip)//2], clip[len(clip)//2:]):
                    sample = speech_excerpt(part)
                    if sample is not None and float(np.dot(encode(sample), vectors[best])) < .50:
                        mixed = True
            if mixed:
                rows[index]['reason'] = 'possible_speaker_handoff'
                continue
            rows[index].update(status='matched', speaker=label, reference=str(reference), reason=None)
    # Uncertain turns get their own source reference, never the entire episode
    # or a guessed neighbouring character. They remain explicit review items.
    for index, clip in clips.items():
        if rows[index]['status'] != 'matched' and len(clip) >= 1000:
            reference = Path(folder)/('uncertain-'+str(index)+'.wav')
            clip.export(reference, format='wav').close()
            rows[index]['reference'] = str(reference)
    return dict(status='needs_review' if any(r['status'] != 'matched' for r in rows) else 'matched',
                speakers=speakers, cues=rows)


def prepare(audio_path, transcript, model_path, device, manifest=None):
    import os
    import psutil
    from core.python_runtime import project_root
    from core.render_context import current_job, run_process
    job = current_job()
    if job is None:
        raise RuntimeError('Character matching requires an owned render job')
    folder = job.workspace/'batch-speakers'
    folder.mkdir(exist_ok=True)
    if str(device).startswith('cuda'):
        from core.cuda_runtime import validate
        executable = validate('speech')['executable']
        device = 'cuda:0'
    else:
        from core.xtts_runtime import validate
        executable = validate()['executable']
        device = 'cpu'
    request = folder/'request.json'
    result_path = folder/'result.json'
    request.write_text(json.dumps(dict(audio_path=str(Path(audio_path).resolve()),
        cues=[dict(cue) for cue in transcript], model_path=str(model_path),
        folder=str(folder), device=device)), encoding='utf-8')
    with (folder/'worker.log').open('wb') as log:
        try:
            run_process([executable, '-B', str(project_root()/'core/batch_speaker_worker.py'), str(request)],
                        stdout=log, stderr=log, check=True, timeout=1800,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8',
                             'REFLOW_PARENT_PID': str(os.getpid()),
                             'REFLOW_PARENT_CREATED': str(psutil.Process().create_time()),
                             'TEMP': str(folder), 'TMP': str(folder)})
        except Exception as error:
            detail = (folder/'worker.log').read_text(encoding='utf-8', errors='replace')[-1800:]
            raise RuntimeError('Source voice matching failed: '+detail) from error
    result = json.loads(result_path.read_text(encoding='utf-8'))
    saved_refs = {}
    if manifest:
        import shutil
        retained = manifest.folder/'speaker-references'
        retained.mkdir(exist_ok=True)
        for row in result['cues']:
            if not row.get('reference'):
                continue
            original = Path(row['reference']).resolve()
            if not original.is_relative_to(folder.resolve()) or not original.is_file():
                raise ValueError('Invalid source character reference')
            if str(original) not in saved_refs:
                target = retained/original.name
                shutil.copy2(original, target)
                saved_refs[str(original)] = str(target)
    for row in result['cues']:
        if row.get('reference'):
            reference = Path(row['reference']).resolve()
            if not reference.is_relative_to(folder.resolve()) or not reference.is_file():
                raise ValueError('Invalid source character reference')
            row['reference'] = saved_refs.get(str(reference), str(reference))
        cue = transcript[row['index']]
        cue.update(speaker=row.get('speaker'), speaker_match=row['status'])
    if manifest:
        for speaker in result['speakers']:
            speaker['reference'] = saved_refs.get(speaker['reference'], speaker['reference'])
        manifest.report('batch-character-matching', result)
    if not any(row['status'] == 'matched' for row in result['cues']):
        raise RuntimeError('Source characters could not be matched reliably. No batch speech was generated. '
                           'Use the Character Review workflow to confirm source character samples. '
                           'The batch character report and source references have been retained.')
    return {transcript[row['index']]['cue_id']: row for row in result['cues']}


def assess_take(clip, character):
    """Acoustic warning evidence; not a claim of semantic intelligibility."""
    from core.speech_performance import measure
    import math
    spoken = measure(clip, pitch=True)
    source = character.get('source_measure')
    reasons = []
    evidence = dict(speaker=character.get('speaker'), source_match=character['status'])
    if character['status'] != 'matched':
        reasons.append('character_uncertain')
    if not spoken:
        reasons.append('no_measurable_speech')
    elif source:
        span = max(1, source['end']-source['start'])
        ratio = (spoken['end']-spoken['start'])/span
        evidence.update(speech_span_ratio=round(ratio, 3), onset_delta_ms=spoken['start']-source['start'],
                        end_delta_ms=spoken['end']-source['end'])
        if ratio < .65 or ratio > 1.35:
            reasons.append('delivery_duration')
        if abs(spoken['start']-source['start']) > 250:
            reasons.append('dialogue_onset')
        if source.get('pitch') and spoken.get('pitch'):
            semitones = abs(12*math.log2(spoken['pitch']/source['pitch']))
            evidence['pitch_delta_semitones'] = round(semitones, 2)
            if semitones > 8:
                reasons.append('voice_pitch')
    return dict(status='needs_review' if reasons else 'passed_acoustic_checks', reasons=reasons, **evidence)
