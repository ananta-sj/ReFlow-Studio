"""Actual subtitle export and translation reuse after list compatibility repair."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')


def main():
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext,bind_job
    folder=ROOT/'docs/validation'/('2026-10-09-subtitle-checkpoint-'+uuid.uuid4().hex[:8]);folder.mkdir()
    source=folder/'source.srt'
    source.write_text('1\n00:00:00,000 --> 00:00:04,000\nThis is a short test of the translation pipeline.\n\n',encoding='utf-8')
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    state={name:sha(ROOT/name) for name in ('models.json','settings.json')}
    report=dict(source=str(source),source_sha256=sha(source),passes=[])
    for number in (1,2):
        job=RenderContext(ROOT/'temp');started=time.monotonic()
        try:
            with bind_job(job):
                pipe=ReflowPipeline();pipe.output_dir=str(folder)
                if pipe.registry.get_active('translation')['request_preset']!='indictrans2':
                    raise RuntimeError('Expected the existing selected IndicTrans2 engine.')
                output=None
                for percent,status,result in pipe.run('subtitle_translate',str(source),dict(target_lang='hi',source_language='en')):
                    print(number,percent,status,flush=True)
                    if result:output=result
                manifest=json.loads(Path(pipe.last_manifest_path).read_text(encoding='utf-8'))
                if manifest['status']!='completed' or not output:raise RuntimeError('Subtitle export incomplete.')
                report['passes'].append(dict(run_id=manifest['run_id'],manifest_path=pipe.last_manifest_path,
                    output=output,output_sha256=sha(output),output_text=Path(output).read_text(encoding='utf-8'),
                    translation_calls=sum(op['stage']=='translation' for op in manifest['operations']),
                    checkpoints=manifest['checkpoints'],elapsed_seconds=time.monotonic()-started))
        finally:job.cleanup()
        report['passes'][-1]['workspace_removed']=not job.workspace.exists()
    first,second=report['passes']
    report.update(saved_state_unchanged=state=={name:sha(ROOT/name) for name in state},source_unchanged=sha(source)==report['source_sha256'],
        identical_export=first['output_sha256']==second['output_sha256'],second_hit=any(e['status']=='hit' and e['stage']=='translation' for e in second['checkpoints']))
    report['passed']=all(report[k] for k in ('saved_state_unchanged','source_unchanged','identical_export','second_hit')) and first['translation_calls']==1 and second['translation_calls']==0
    files=['core/pipeline.py','core/stage_checkpoints.py','core/cue_review.py','core/review_cue_contracts.py']
    report['implementation_sha256']={name:sha(ROOT/name) for name in files}
    path=folder.with_suffix('.json');path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('REPORT',path,'passed=',report['passed'],flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
