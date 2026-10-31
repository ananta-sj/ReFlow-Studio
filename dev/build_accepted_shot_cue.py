"""Build reviewed cue 12 from accepted PCM with explicit diagnostic tail anchors."""
import json
from pathlib import Path

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def build(output,old,base):
    import numpy as np
    import soundfile as sf
    from core.cue_review import digest
    approval=read(base/'2026-10-09-question-only-video-user-feedback.json')
    video=read(base/approval['review_receipt'])
    assert approval['short_video_human_accepted']
    assert digest(video['output'])==approval['video_sha256']==video['output_sha256']
    splice=read(base/'2026-10-09-question-only-splice-53f89903.json')
    shots=read(base/'2026-10-08-shot-bounded-hindi-38a36120.json')
    tail=read(base/'2026-10-09-source-tail-word-timing.json')
    assert tail['source_offset_seconds']==99.16 and tail['diagnostic_only']
    assert "wordplay" in tail['rows'][0]['result']['text']
    placements=[]
    chunks=[]
    def add(path,start,text,sha):
        assert digest(path)==sha
        pcm,rate=sf.read(path,dtype='int16')
        assert rate==24000 and pcm.ndim==1
        chunks.append((start,pcm))
        placements.append(dict(start=start,end=start+len(pcm)/rate,text=text,
            sha256=sha,source_file=str(path),sample_exact=True))
    add(splice['output'],90,'बोर हो गए? जगाने को ये एनिमेटेड चार्ट।',splice['output_sha256'])
    for name in ['family','lighthouse']:
        row=next(row for row in shots['phrases'] if row['shot']==name)
        add(row['output'],row['start'],row['text'],row['sha256'])
    previous=old['cues'][11]
    source=Path(old['directory'])/previous['file']
    assert digest(source)==previous['result']['output_sha256']
    pcm,rate=sf.read(source,dtype='int16')
    assert rate==24000 and pcm.ndim==1
    offset=0
    # Explicit review anchors. Source word timing is approximate; these are
    # edited placements, not automatic alignment or human acceptance.
    starts=[99.36,101.45,104.64,111.06]
    for index,row in enumerate(previous['result']['sentences']):
        chunk=pcm[offset:offset+row['frames']]
        assert len(chunk)==row['frames']
        if index>=2:
            start=starts[index-2]
            chunks.append((start,chunk))
            placements.append(dict(start=start,end=start+len(chunk)/rate,text=row['text'],
                source_file=str(source),source_start_sample=offset,frames=len(chunk),sample_exact=True))
        offset+=row['frames']+(4800 if index<5 else 0)
    assert offset==len(pcm)
    end=round((placements[-1]['end']-90)*rate)
    joined=np.zeros(end,dtype='int16')
    previous_end=0
    for start,chunk in chunks:
        first=round((start-90)*rate)
        assert first>=previous_end
        joined[first:first+len(chunk)]=chunk
        assert np.array_equal(joined[first:first+len(chunk)],chunk)
        previous_end=first+len(chunk)
    sf.write(output,joined,rate,subtype='PCM_16')
    restored,actual_rate=sf.read(output,dtype='int16')
    assert actual_rate==rate and np.array_equal(restored,joined)
    return dict(placements=placements,accepted_short_section_preserved=True,
        speech_pcm_chunks_sample_exact=True,speech_resynthesized=False,time_stretch=False,
        following_four_sentences_retimed=True,tail_word_timing_receipt='2026-10-09-source-tail-word-timing.json',
        diagnostic_editorial_anchors=True,human_tail_timing_accepted=False,
        subtitle_text=' '.join(row['text'] for row in placements),cue_sha256=digest(output))
