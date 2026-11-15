"""Match caption-sized voices to clean labelled anchors, not whole-scene clusters."""
from collections import defaultdict
from pathlib import Path
import math


def unit(vector):
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError('Invalid source voice vector')
    length = math.sqrt(sum(value*value for value in vector))
    if length == 0:
        raise ValueError('Empty source voice vector')
    return [value/length for value in vector]


def cosine(left, right):
    if len(left) != len(right):
        raise ValueError('Inconsistent source voice dimensions')
    return sum(a*b for a,b in zip(left,right))


def profiles(cues, vectors, blocked=()):
    from core.batch_speakers import group_vectors
    from core.source_captions import generic_speaker
    labels = defaultdict(list)
    for index, cue in enumerate(cues):
        duration=cue.get('end',float('inf'))-cue.get('start',0)
        if duration>=1.5 and cue.get('speaker_hint') and not cue.get('speaker_collective') and not cue.get('multiple_caption_speakers') and index in vectors and index not in blocked:
            labels[cue['speaker_hint']].append(index)
    result, named = {}, {}
    for label, indices in labels.items():
        generic=generic_speaker(label) or any(cues[i].get('speaker_generic') for i in indices)
        groups = group_vectors([vectors[i] for i in indices], minimum_similarity=.65)[0] if generic else [1]*len(indices)
        buckets = defaultdict(list)
        for index, group in zip(indices,groups):
            buckets[group].append(index)
        for number, members in enumerate(buckets.values(),1):
            key = label+' / '+str(number)
            center = unit([sum(vectors[i][column] for i in members) for column in range(len(vectors[members[0]]))])
            result[key] = dict(label=label,indices=members,center=center,generic=generic)
            named.update({i:key for i in members})
    return result, named


def match(vector, templates, *, minimum=.60, margin=.08):
    scores = sorted(((key,cosine(vector,profile['center'])) for key,profile in templates.items()),
                    key=lambda item:item[1],reverse=True)
    if not scores:
        return None, 0., 0.
    best, score = scores[0]
    # Multiple acoustic styles of a labelled character need not be treated
    # as competing character names. Generic roles still get distinct refs.
    other = next((value for key,value in scores[1:] if templates[best].get('generic') or templates[key]['label']!=templates[best]['label']), -1.)
    difference = score-other
    return (best if score >= minimum and difference >= margin else None), score, difference


def match_cue(cue,vector,templates,*,trust_hint=True):
    hint=cue.get('speaker_hint') if trust_hint else None
    if hint:
        candidates={key:row for key,row in templates.items() if row['label']==hint}
        if len(candidates)==1 and not next(iter(candidates.values())).get('generic'):
            return next(iter(candidates)),1.,1.
        templates=candidates
    if vector is None:
        return None,0.,0.
    short=cue['end']-cue['start']<1.5
    return match(vector,templates,minimum=.75 if short else .6,margin=.2 if short else .08)


def choose_cues(cues,vectors,templates,named,blocked=()):
    """One conservative corroboration pass; promoted cues never train others."""
    choices={}; evidence={}; weak={}
    from core.voice_discriminant import train,propose
    discriminant=train(templates,vectors)
    for i,cue in enumerate(cues):
        key,score,margin=(named[i],1.,1.) if i in named else match_cue(cue,vectors.get(i),templates)
        if i in blocked or cue.get('speaker_collective') or cue.get('multiple_caption_speakers'):
            key=None
        choices[i]=key
        evidence[i]=dict(similarity=round(score,4),margin=round(margin,4),method='caption_or_voice')
        if (key is None and i not in blocked and not cue.get('speaker_hint')
                and not cue.get('speaker_collective') and not cue.get('multiple_caption_speakers')
                and cue['end']-cue['start']>=1.5):
            proposed,detail=propose(vectors.get(i),discriminant)
            if proposed:
                choices[i]=key=proposed
                evidence[i]=detail
        if (key is None and i not in blocked and i in vectors and not cue.get('speaker_hint')
                and not cue.get('speaker_collective') and not cue.get('multiple_caption_speakers')
                and cue['end']-cue['start']>=1.5):
            candidate,_,_=match(vectors[i],templates,minimum=.55,margin=.15)
            if candidate and not templates[candidate].get('generic'):
                weak[i]=candidate
    # New proposals cannot become supporting examples for further promotions.
    initial={i:(key if evidence[i]['method']!='labelled_source_discriminant' else None)
             for i,key in choices.items()}
    # Require two independent, already-confident nearby examples. This cannot
    # spread a new assignment recursively through a whole scene or episode.
    for i,key in weak.items():
        supporters=[j for j,other in initial.items() if j!=i and other==key and j in vectors
            and cues[j]['end']-cues[j]['start']>=1.5
            and abs(cues[j]['start']-cues[i]['start'])<=90
            and cosine(vectors[i],vectors[j])>=.7]
        if len(supporters)>=2:
            choices[i]=key
            evidence[i].update(method='two_source_examples',supporters=supporters)
    # Several adjacent caption fragments may constitute one utterance. Join
    # their evidence only when each already proposes the same named identity
    # and the neighbouring voice vectors agree. Never cross a rival speaker.
    groups=[]
    for i,cue in enumerate(cues):
        key=initial[i] or weak.get(i)
        if (groups and key and key==groups[-1][0] and not templates[key].get('generic')
                and i in vectors and groups[-1][1][-1] in vectors
                and 0<=cue['start']-cues[groups[-1][1][-1]]['end']<=.55
                and cue['end']-cues[groups[-1][1][0]]['start']<=10
                and cosine(vectors[i],vectors[groups[-1][1][-1]])>=.55):
            groups[-1][1].append(i)
        else:
            groups.append((key,[i]))
    for key,indices in groups:
        if not key or len(indices)<2 or any(i not in vectors for i in indices):continue
        combined=unit([sum(vectors[i][column] for i in indices) for column in range(len(vectors[indices[0]]))])
        combined_key,score,margin=match(combined,templates,minimum=.65,margin=.15)
        if combined_key!=key:continue
        for i in indices:
            if i in weak:
                choices[i]=key
                evidence[i].update(method='consistent_utterance',utterance_cues=indices,
                    combined_similarity=round(score,4),combined_margin=round(margin,4))
    return choices,evidence


def assign(audio, transcript, result, folder, namespace, manifest=None, excluded=()):
    from core.pipeline_contracts import identify_cues, finalize_grouped_cues
    from core.diarization import references
    from core.speech_performance import measure
    cues = identify_cues(transcript, namespace)
    by_id = {row['cue_id']:unit(row['vector']) for row in result['cue_embeddings']}
    vectors = {i:(by_id.get(c['cue_id']) or by_id.get(c.get('provider_cue_id')) or by_id.get('caption-'+str(i)))
               for i,c in enumerate(cues)}
    vectors = {i:value for i,value in vectors.items() if value is not None}
    blocked = {i for i,c in enumerate(cues) if any(j!=i and other['start']<c['end'] and other['end']>c['start']
               for j,other in enumerate(cues)) or any(a<c['end'] and b>c['start'] for a,b in excluded)}
    templates, named = profiles(cues, vectors, blocked)
    choices,evidence=choose_cues(cues,vectors,templates,named,blocked)
    destination = manifest.folder/'speaker-references' if manifest else Path(folder)/'references'
    destination.mkdir(exist_ok=True)
    turns = [dict(start=c['start'],end=c['end'],speaker=choices[i]) for i,c in enumerate(cues)
             if choices[i] and i not in blocked]
    anchors = references(audio,dict(audio_seconds=len(audio)/1000,turns=turns,
        overlapping_turns=result.get('overlapping_turns',result['turns'])),destination,excluded) if turns else {}
    assembled = []
    for i,cue in enumerate(cues):
        key = choices[i]
        cue.update(speaker=key, speaker_match='matched' if key in anchors else 'needs_review',
                   voice_identity=evidence[i])
        if (assembled and cue['speaker_match']=='matched' and assembled[-1]['speaker_match']=='matched'
                and assembled[-1]['speaker']==key and 0 <= cue['start']-assembled[-1]['end'] <= .55
                and cue['end']-assembled[-1]['start'] <= 10):
            previous = assembled[-1]
            previous.setdefault('source_fragments',[dict(previous)])
            previous['source_fragments'].append(dict(cue))
            previous['end']=cue['end']
            previous['text'] += ' '+cue['text']
        else:
            assembled.append(cue)
    assembled = finalize_grouped_cues(assembled)
    from core.diarization import scene_references
    local_refs=scene_references(audio,assembled,destination,anchors,excluded,
        result.get('overlapping_turns',result['turns']))
    mapping, rows = {}, []
    for index,cue in enumerate(assembled):
        local=local_refs.get(cue['cue_id'])
        ref = local['reference'] if local else anchors.get(cue['speaker'])
        reason = None if ref else 'multiple_source_speakers' if cue.get('speaker_collective') or cue.get('multiple_caption_speakers') else 'voice_identity_uncertain'
        row = dict(index=index,cue_id=cue['cue_id'],start=cue['start'],end=cue['end'],speaker=cue['speaker'],
            reference=ref,status='matched' if ref else 'needs_review',reason=reason,
            identity=cue['voice_identity'],source_measure=measure(audio[round(cue['start']*1000):round(cue['end']*1000)],pitch=True,source=True))
        row['reference_policy']='nearby_same_character' if local else 'stable_character_fallback'
        if local:row['reference_source_cues']=local['source_cues']
        rows.append(row); mapping[cue['cue_id']]=row
    if manifest:
        manifest.report('batch-character-matching',dict(status='needs_review' if any(r['reason'] for r in rows) else 'matched',
            engine='community-1-caption-voice-identities',source_cue_count=len(cues),utterance_count=len(assembled),
            speakers=[dict(speaker=name,reference=ref) for name,ref in anchors.items()],cues=rows,device=result['device']))
    return transcript.with_segments(assembled), mapping
