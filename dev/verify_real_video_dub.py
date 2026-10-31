"""Current real-video pipeline test; isolated connections and retained failure evidence."""
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['TORCH_HOME'] = str(ROOT / 'models/torch-cache')
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'


def main():
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job, run_process
    from dev.verify_workflows import FixtureRegistry
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-real-video-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, automatic_pipeline_pass=False, human_quality_accepted=False,
                  input='Sample/2.mp4 first 44 seconds, real moving frames', offline=True, device='cpu',
                  original_files_unchanged=True, events=[], source_cues=[], translated_cues=[], cue_audio=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            clip = work / 'source.mp4'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(ROOT / 'Sample/2.mp4'),
                '-t', '44', '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264', '-preset', 'veryfast',
                '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(clip)], check=True, timeout=120)
            reference = work / 'reference.mp3'
            shutil.copy2(Path('C:/Users/19shr/Downloads/HIN_M_AbhishekS.mp3'), reference)
            pipeline = ReflowPipeline()
            pipeline.registry = FixtureRegistry()
            pipeline.output_dir = str(work / 'outputs')
            Path(pipeline.output_dir).mkdir()
            original_stt = pipeline._transcribe_source
            def record_stt(*args, **kwargs):
                result = original_stt(*args, **kwargs)
                report['source_cues'] = [dict(item) for item in result]
                report['detected_language'] = result.language
                return result
            pipeline._transcribe_source = record_stt
            original_all = pipeline._dub_all_segments
            def record_all(*args, **kwargs):
                report['translated_cues'] = [dict(item) for item in args[0]]
                return (yield from original_all(*args, **kwargs))
            pipeline._dub_all_segments = record_all
            original_cue = pipeline._dub_segment
            def record_cue(index, segment, *args, **kwargs):
                before = time.monotonic()
                try:
                    audio = original_cue(index, segment, *args, **kwargs)
                    if audio:
                        path = work / f'cue-{index+1:02d}.wav'
                        audio.export(path, format='wav').close()
                        report['cue_audio'].append(dict(index=index, seconds=len(audio)/1000,
                            file=path.name, elapsed_seconds=round(time.monotonic()-before, 3)))
                    return audio
                except Exception as exc:
                    report['failed_cue'] = dict(index=index, text=segment['text'], error=str(exc),
                                               elapsed_seconds=round(time.monotonic()-before, 3))
                    raise
            pipeline._dub_segment = record_cue
            params = dict(target_lang='hi', source_language='en', cast_list=['CLONED_USER'],
                user_voice_path=str(reference), compute_device='cpu', keep_background=True,
                include_subtitles=True, burn_subtitles=False, export_stems=True, parallel_workers=1,
                lip_sync_active=False, enhance_active=False, content_filter_active=False)
            report['profile'] = dict(params, user_voice_path='copied supplied Abhishek reference')
            try:
                output = None
                for progress, message, result in pipeline.run('video_dub', str(clip), params):
                    report['events'].append(dict(progress=progress, message=message))
                    print(f'{progress}: {message}', flush=True)
                    if result:
                        output = Path(result)
                if not output or not output.is_file():
                    raise RuntimeError('Pipeline did not publish a final video')
                stream_info = run_process(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                    '-of', 'json', str(output)], check=True, capture_output=True, text=True, timeout=60)
                info = json.loads(stream_info.stdout)
                if not {'video', 'audio', 'subtitle'}.issubset({item['codec_type'] for item in info['streams']}):
                    raise RuntimeError('Video/audio/subtitle stream missing')
                if abs(float(info['format']['duration'])-44) > .15:
                    raise RuntimeError('Final video timeline changed')
                run_process(['ffmpeg', '-v', 'error', '-i', str(output), '-map', '0:v:0', '-map', '0:a:0',
                    '-f', 'null', os.devnull], check=True, timeout=120)
                report.update(automatic_pipeline_pass=True, output=str(output.relative_to(work)), streams=info['streams'])
            except Exception as exc:
                report['error'] = str(exc)
                print('TEST FAILED: ' + str(exc), flush=True)
            finally:
                for filename in ('temp_subs.srt', 'clean_reference.wav', 'master_audio.wav'):
                    artifact = Path(pipeline.temp_dir) / filename
                    if artifact.is_file():
                        shutil.copy2(artifact, work / filename)
                (work / 'cue-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                job.publish(work, destination)
                report.update(execution_completed=True, directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started, 3), workspace_removed=not job.workspace.exists())
        (ROOT / 'docs/validation/2026-10-04-real-video-dub.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
