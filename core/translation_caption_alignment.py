"""Timing-compatible auxiliary caption evidence; not a semantic guarantee."""


def align(cues,captions,*,language='en'):
    proposals,issues={},{}
    for index,cue in enumerate(cues):
        matches=[]
        for j,caption in enumerate(captions):
            overlap=max(0,min(cue['end'],caption['end'])-max(cue['start'],caption['start']))
            if overlap<=0:continue
            if overlap<=.15 and (caption['start']<cue['start'] or caption['end']>cue['end']):continue
            duration=caption['end']-caption['start']
            if duration<=0 or overlap/duration<.85:
                issues[index]='auxiliary_caption_crosses_turn';matches=[];break
            crosses=any(k!=index and min(other['end'],caption['end'])-max(other['start'],caption['start'])>.35
                        for k,other in enumerate(cues))
            if crosses:
                issues[index]='auxiliary_caption_crosses_turn';matches=[];break
            matches.append((j,caption,overlap))
        if not matches:issues.setdefault(index,'auxiliary_caption_unavailable');continue
        start,end=matches[0][1]['start'],matches[-1][1]['end']
        coverage=sum(row[2] for row in matches)/(cue['end']-cue['start'])
        if coverage<.65 or abs(start-cue['start'])>.5 or abs(end-cue['end'])>1:
            issues[index]='auxiliary_caption_timing_uncertain';continue
        proposals[index]=dict(text=' '.join(row[1]['text'] for row in matches),language=language,
            caption_indices=[row[0] for row in matches],timing_coverage=round(min(1,coverage),4),
            original_source_text=cue.get('source_text',cue.get('text','')),meaning_verified=False)
    owners={}
    for index,proposal in proposals.items():
        for caption_index in proposal['caption_indices']:owners.setdefault(caption_index,[]).append(index)
    conflicts={index for indices in owners.values() if len(indices)>1 for index in indices}
    for index in conflicts:
        proposals.pop(index,None);issues[index]='auxiliary_caption_reused_across_turns'
    return proposals,issues
