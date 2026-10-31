"""Preserve accepted question and reviewed rest PCM; splice in their shared pause."""
import json
import os
from pathlib import Path
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')

def main():
    import numpy as np
    import soundfile as sf
    from core.cue_review import digest
    from core.render_context import run_process
    base=ROOT/'docs/validation'
    boundaries=json.loads((base/'2026-10-09-question-splice-boundary.json').read_text(encoding='utf-8'))
    acceptance=json.loads((base/'2026-10-09-question-seed7-user-feedback.json').read_text(encoding='utf-8'))
    assert acceptance['question_delivery_accepted']
    question_receipt=json.loads((base/acceptance['review_receipt']).read_text(encoding='utf-8'))
    assert digest(question_receipt['listening'])==acceptance['listening_sha256']
    rows={row['name']:row for row in boundaries['rows']}
    arrays={}
    for name,row in rows.items():
        assert digest(row['audio'])==row['sha256']
        arrays[name],rate=sf.read(row['audio'],dtype='int16')
        assert rate==24000 and arrays[name].ndim==1
        assert any(span['start']<=1.17 and span['end']>=1.23 for span in row['low_energy_spans'])
    new,old=arrays['accepted_question'],arrays['reviewed_rest']
    assert len(new)==len(old)==76800
    # Both ASR question boundaries precede this window; the first chart word
    # crosses it only in ASR's coarse timestamps, while RMS indicates a pause.
    # Preserve a margin beyond the new ASR question end (1.08 seconds).
    indices=np.arange(round(1.17*rate),round(1.23*rate))
    cost=np.abs(new[indices-1].astype('int32'))+np.abs(old[indices].astype('int32'))
    cost+=np.abs(new[indices-1].astype('int32')-old[indices].astype('int32'))
    cut=int(indices[np.argmin(cost)])
    jump=int(abs(int(new[cut-1])-int(old[cut])))
    assert jump<=33, 'Splice discontinuity exceeds -60 dBFS; require another plan'
    joined=np.concatenate([new[:cut],old[cut:]])
    assert np.array_equal(joined[:cut],new[:cut]) and np.array_equal(joined[cut:],old[cut:])
    folder=base/('2026-10-09-question-only-splice-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    output=folder/'question-only-spliced-intro.wav'
    sf.write(output,joined,rate,subtype='PCM_16')
    restored,restored_rate=sf.read(output,dtype='int16')
    assert restored_rate==rate and np.array_equal(restored,joined)
    run_process(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],capture_output=True,check=True)
    report=dict(completed=True,question_human_accepted=True,video_human_accepted=False,
        operation='PCM splice within shared low-energy pause',live_tts=False,time_stretch=False,
        output=str(output),output_sha256=digest(output),actual_seconds=len(joined)/rate,
        cut_sample=cut,cut_seconds=cut/rate,splice_jump_pcm16=jump,
        question_prefix_sample_exact=True,reviewed_rest_suffix_sample_exact=True,
        chart_timing_changed=False,full_decode_pass=True,
        boundary_receipt='2026-10-09-question-splice-boundary.json',
        question_acceptance='2026-10-09-question-seed7-user-feedback.json',sources=rows)
    receipt=folder.with_suffix('.json')
    receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(receipt,flush=True)

if __name__=='__main__': main()
