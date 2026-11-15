"""Align reliable caption text with inferred voices, respecting explicit labels."""
from collections import defaultdict
from pathlib import Path


def assign(audio, transcript, result, folder, namespace, manifest=None, excluded=()):
    if result.get('cue_embeddings') and any(c.get('speaker_hint') for c in transcript):
        from core.caption_voice_identity import assign as assign_by_identity
        return assign_by_identity(audio, transcript, result, folder, namespace, manifest, excluded)
    from core.diarization import references, validate_turns
    from core.pipeline_contracts import identify_cues
    from core.speech_performance import measure
    turns = validate_turns(result)
    destination = manifest.folder/'speaker-references' if manifest else Path(folder)/'references'
    destination.mkdir(exist_ok=True)
    grouped_folder = destination/'groups'
    grouped_folder.mkdir(exist_ok=True)
    group_refs = references(audio, result, grouped_folder, excluded)
    def scores(cue):
        values = defaultdict(float)
        for turn in turns:
            overlap = min(cue['end'], turn['end'])-max(cue['start'], turn['start'])
            if overlap > 0:
                values[turn['speaker']] += overlap
        return sorted(values.items(), key=lambda item:item[1], reverse=True)
    votes = defaultdict(lambda:defaultdict(float))
    for cue in transcript:
        if cue.get('speaker_hint') and not cue.get('multiple_caption_speakers') and not cue.get('speaker_collective'):
            values = scores(cue)
            if values and values[0][1] >= .65*sum(value for _,value in values):
                votes[cue['speaker_hint']][values[0][0]] += values[0][1]
    group_votes = defaultdict(lambda:defaultdict(float))
    for name, values in votes.items():
        for group, amount in values.items():
            group_votes[group][name] += amount
    names_by_group = defaultdict(set)
    for group, values in group_votes.items():
        ranked = sorted(values.items(), key=lambda item:item[1], reverse=True)
        name, amount = ranked[0]
        # A single syllable is weak evidence: diarizers commonly absorb it
        # into an adjacent character. It must not rename a whole cast group.
        if amount >= 1.5 and amount >= .8*sum(values.values()):
            names_by_group[group].add(name)
        elif sum(value >= 1.5 for _, value in ranked) > 1:
            names_by_group[group].update(name for name,value in ranked if value >= 1.5)
    named_turns = []
    for index, cue in enumerate(transcript):
        if not cue.get('speaker_hint') or cue.get('multiple_caption_speakers') or cue.get('speaker_collective'):
            continue
        if any(other is not cue and other['start'] < cue['end'] and other['end'] > cue['start'] for other in transcript):
            continue
        named_turns.append(dict(start=cue['start'], end=cue['end'], speaker=cue['speaker_hint']))
    named_folder = destination/'named'
    named_folder.mkdir(exist_ok=True)
    named_refs = references(audio, dict(audio_seconds=len(audio)/1000, turns=named_turns,
        overlapping_turns=result.get('overlapping_turns', turns)), named_folder, excluded) if named_turns else {}
    for group, names in names_by_group.items():
        if len(names) == 1 and group in group_refs:
            named_refs.setdefault(next(iter(names)), group_refs[group])
    rows, cues = [], []
    for index, source in enumerate(transcript):
        cue = dict(source)
        name, reference, reason = cue.get('speaker_hint'), None, None
        if cue.get('multiple_caption_speakers') or cue.get('speaker_collective'):
            name, reason = None, 'multiple_source_speakers'
        elif name:
            reference = named_refs.get(name)
        else:
            values = scores(cue)
            if not values or values[0][1] < .8*sum(value for _,value in values):
                reason = 'mixed_source_voices' if values else 'no_detected_source_voice'
            else:
                group = values[0][0]
                names = names_by_group.get(group, set())
                if len(names) > 1:
                    reason = 'merged_character_group'
                else:
                    name = next(iter(names)) if names else group
                    reference = named_refs.get(name, group_refs.get(group))
                    if cue['end']-cue['start'] < 1.8:
                        reason = 'short_unlabelled_reply'
        if not reference:
            reason = reason or 'no_clean_character_reference'
        cue.update(speaker=name, speaker_match='needs_review' if reason else 'matched')
        cues.append(cue)
        rows.append(dict(index=index, start=cue['start'], end=cue['end'], speaker=name,
            status=cue['speaker_match'], reference=reference, reason=reason,
            source_measure=measure(audio[round(cue['start']*1000):round(cue['end']*1000)], pitch=True, source=True)))
    cues = transcript.with_segments(identify_cues(cues, namespace))
    mapping = {}
    for cue, row in zip(cues, rows):
        row['cue_id'] = cue['cue_id']
        mapping[cue['cue_id']] = row
    if manifest:
        used = {row['speaker']:row['reference'] for row in rows if row['reference']}
        manifest.report('batch-character-matching', dict(status='needs_review' if any(row['reason'] for row in rows) else 'matched',
            engine='community-1-and-source-captions', speakers=[dict(speaker=name, reference=ref) for name,ref in used.items()],
            cues=rows, device=result['device']))
    return cues, mapping
