"""Replay a hash-bound actual XTTS take: review overflow and preserve native pace."""
import hashlib,json,os,shutil,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))

def main():
    from core.pipeline import ReflowPipeline
    from core.speech_timing import SpeechTimingReviewRequired
    from core.audio_utils import AudioEngineer,load_speech_audio
    from core.render_context import RenderContext,bind_job
    from core.run_manifest import RunManifest
    from core.pipeline_contracts import PipelineSpec,RegistrySnapshot,SettingsSnapshot
    from core.runtime_integrity import sha
    diagnosis=json.loads((ROOT/'docs/validation/2026-10-16-speech-overflow-diagnosis.json').read_text())
    raw=Path(diagnosis['output']);assert diagnosis['passed'] and sha(raw)==diagnosis['output_sha256']
    folder=ROOT/'docs/validation/2026-10-16-speech-timing-replay';folder.mkdir(exist_ok=True)
    text="Before long a standard news report visual language established itself, one that's immediately recognizable to any"
    segment=dict(start=0.,end=6.,text=text,cue_id='measured-dense-cue')
    registry=RegistrySnapshot(dict(entries=[],active={}))
    class Replay:
        preserves_native_delivery=False
        calls=0
        def synthesize(self,text,output_path,**kwargs):
            self.calls+=1;shutil.copy2(raw,output_path)
    provider=Replay();job=RenderContext(ROOT/'temp');report=dict(passed=False,checks={},new_model_calls=0,quality_accepted=False,raw_source_sha256=sha(raw))
    def check(name,value):
        report['checks'][name]=bool(value)
        if not value:raise AssertionError(name)
    try:
        with bind_job(job):
            subject=ReflowPipeline.__new__(ReflowPipeline);subject.registry=registry;subject.temp_dir=str(job.workspace)
            record=RunManifest(folder,PipelineSpec('audio_dub',dict(target_lang='source')) ,str(raw),registry,SettingsSnapshot({}))
            subject._manifest=record
            try:subject._dub_segment(0,segment,['CLONED_USER'],'en',provider,{},None,str(raw),'cpu',AudioEngineer())
            except SpeechTimingReviewRequired as error:
                review=error.report;report['measured_conflict']=review
                check('real_audio_overflow_is_review_required',review['status']=='needs_review' and review['measured_seconds']>6 and review['speed']==1.3)
                check('complete_candidate_persisted',Path(review['candidate']['path']).is_file() and sha(Path(review['candidate']['path']))==review['candidate']['sha256'])
                check('no_cut_or_automatic_rewrite',review['words_cut'] is False and review['auto_rewrite'] is False)
                check('manifest_exposes_review_required',json.loads(record.path.read_text())['review_required'] is True)
            else:raise AssertionError('Dense measured speech should not be forced into six seconds')
            # Separate synthetic media-window control, not an extension of the failed video.
            subject._manifest=None
            gen=subject._dub_all_segments([segment],['CLONED_USER'],'en',provider,{},None,str(raw),'cpu',AudioEngineer(),12.,45,30,max_workers=2)
            while True:
                try:next(gen)
                except StopIteration as done:track=done.value;break
            check('parallel_final_cue_uses_available_media_tail',len(track)==12000 and track[9000:9500].max>0)
            timed=job.workspace/'spare-media-tail.wav';track.export(timed,format='wav').close()
            job.publish(timed,folder/'spare-media-tail.wav')
            roomy=subject._dub_segment(0,{**segment,'end':12.},['CLONED_USER'],'en',provider,{},None,str(raw),'cpu',AudioEngineer())
            check('spacious_cue_preserves_generated_duration',abs(len(roomy)-diagnosis['raw_seconds']*1000)<=2)
            check('all_uses_replay_one_actual_take',provider.calls==3 and sha(raw)==diagnosis['output_sha256'])
            report.update(passed=True,original_seconds=diagnosis['raw_seconds'],roomy_cue_seconds=len(roomy)/1000,synthetic_media_seconds=12,
                candidate=review['candidate']['path'],manifest=str(record.path),synthetic_tail_output=str(folder/'spare-media-tail.wav'))
    except BaseException as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup();report['workspace_removed']=not job.workspace.exists()
        (ROOT/'docs/validation/2026-10-16-speech-timing-replay.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
