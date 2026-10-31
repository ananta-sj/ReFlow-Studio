"""Real offline pipeline acceptance; fixture connections never change user settings."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TORCH_HOME'] = str(ROOT / 'models/torch-cache')
from core.render_context import RenderContext, bind_job, run_process
from core.model_assets import RECOVERY_SOURCES


def inspect_video(path):
    result = run_process(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)],
                         check=True, timeout=60, capture_output=True, text=True)
    streams = json.loads(result.stdout)['streams']
    if not {'audio', 'video', 'subtitle'}.issubset({stream['codec_type'] for stream in streams}):
        raise RuntimeError('Final video is missing audio, video or soft subtitles')
    import cv2
    reader = cv2.VideoCapture(str(path))
    try:
        frames = 0
        while reader.read()[0]:
            frames += 1
        if frames != 40:
            raise RuntimeError(f'Expected 40 decoded output frames, found {frames}')
    finally:
        reader.release()
    return dict(decoded_frames=frames, streams=[{key: stream.get(key) for key in
                ('codec_type', 'codec_name', 'width', 'height', 'r_frame_rate')} for stream in streams])


class FixtureRegistry:
    def __init__(self):
        whisper = next((ROOT / 'models/whisper').rglob('model.bin')).parent
        self.entries = []
        for stage, folder in [('stt', whisper), ('tts', ROOT / RECOVERY_SOURCES['xtts']['folder']),
                              ('translation', ROOT / RECOVERY_SOURCES['nllb']['folder'])]:
            self.entries.append(dict(id=stage, stage_type=stage, display_name='Acceptance ' + stage,
                                     kind='local_file', local_path=str(folder), meta={}))

    def get_active(self, stage):
        return next((item for item in self.entries if item['stage_type'] == stage), None)

    def list(self, stage=None):
        return [item for item in self.entries if stage is None or item['stage_type'] == stage]

    def get(self, identifier):
        return next((item for item in self.entries if item['id'] == identifier), None)

    def snapshot(self):
        from core.pipeline_contracts import RegistrySnapshot
        return RegistrySnapshot({'entries': self.entries,
            'active': {entry['stage_type']: entry['id'] for entry in self.entries}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('template', choices=['subtitle_translate', 'audio_dub', 'video_dub', 'video_dub_lipsync'])
    parser.add_argument('--run-label', default='', help='Separate receipt/output suffix for comparison runs')
    parser.add_argument('--audio-seconds', type=int, default=8,
                        help='Explicit audio-only source excerpt length; default fixture remains eight seconds')
    args = parser.parse_args()
    if args.run_label and not all(c.isalnum() or c == '-' for c in args.run_label):
        parser.error('Run label must contain only letters, numbers or hyphens')
    if args.audio_seconds != 8 and (args.template != 'audio_dub' or not args.run_label):
        parser.error('Changed duration requires audio_dub and a separate run label')
    if not 1 <= args.audio_seconds <= 120:
        parser.error('Audio excerpt must be between 1 and 120 seconds')
    suffix = '-' + args.run_label if args.run_label else ''
    job = RenderContext(ROOT / 'temp')
    report = dict(template=args.template, offline=True, acceptance=False, quality_reviewed=False,
                  device='cpu', parallel_workers=2,
                  fixture=f'Sample/2.mp4 first {args.audio_seconds} seconds, static portrait for video',
                  source_excerpt_seconds=args.audio_seconds)
    started = time.monotonic()
    try:
        with bind_job(job):
            from core.pipeline import ReflowPipeline
            pipeline = ReflowPipeline()
            pipeline.registry = FixtureRegistry()
            original_transcribe = pipeline._transcribe_source
            def record_source(*call_args, **call_kwargs):
                result = original_transcribe(*call_args, **call_kwargs)
                report['grouped_source_cues'] = [dict(cue) for cue in result]
                report['detected_source_language'] = result.language
                return result
            pipeline._transcribe_source = record_source
            original_dub = pipeline._dub_all_segments
            def record_dub(*call_args, **call_kwargs):
                report['translated_speech_cues'] = [dict(cue) for cue in call_args[0]]
                return (yield from original_dub(*call_args, **call_kwargs))
            pipeline._dub_all_segments = record_dub
            pipeline.output_dir = str(job.workspace / 'outputs')
            Path(pipeline.output_dir).mkdir()
            params = dict(target_lang='hi', source_language='en')
            if args.template == 'subtitle_translate':
                source = job.workspace / 'input.srt'
                source.write_text('1\n00:00:00,000 --> 00:00:02,000\nGood morning.\n\n2\n00:00:02,000 --> 00:00:04,000\nThis is a short test.\n', encoding='utf-8')
            else:
                audio = job.workspace / 'input.wav'
                run_process(['ffmpeg', '-v', 'error', '-y', '-i', str(ROOT / 'Sample/2.mp4'),
                             '-t', str(args.audio_seconds), '-vn', '-ar', '24000', '-ac', '1', str(audio)], check=True, timeout=60)
                source = audio
                params.update(cast_list=['CLONED_USER'], user_voice_path=str(audio), keep_background=True,
                              compute_device='cpu', parallel_workers=2, export_stems=True)
                if args.template.startswith('video'):
                    portrait = job.workspace / 'portrait.png'
                    run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                                 '-frames:v', '1', '-vf', 'scale=640:-2', str(portrait)], check=True, timeout=60)
                    source = job.workspace / 'input.mp4'
                    run_process(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-framerate', '5', '-i', str(portrait),
                                 '-i', str(audio), '-t', '8', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                                 '-c:a', 'aac', str(source)], check=True, timeout=60)
                    params.update(enhance_active=True, content_filter_active=True, include_subtitles=True,
                                  burn_subtitles=False, texture_quality=1)
            events = []
            report['events'] = events
            output = None
            for progress, message, result in pipeline.run(args.template, str(source), params):
                events.append(dict(progress=progress, message=message))
                print(f'{progress}: {message}', flush=True)
                if result:
                    output = Path(result)
            report['events'] = events
            if output is None or not output.is_file() or not events or events[-1]['progress'] != 100:
                raise RuntimeError('Pipeline did not publish a complete output')
            if args.template == 'subtitle_translate':
                from core.srt_utils import parse_srt
                cues = parse_srt(str(output))
                if len(cues) != 2 or not all(any('\u0900' <= c <= '\u097f' for c in cue['text']) for cue in cues):
                    raise RuntimeError('Translated cues missing/non-Hindi')
                report['cues'] = list(cues)
            else:
                from core.pipeline import _validate_media
                _validate_media(str(output), {'audio', 'video'} if args.template.startswith('video') else {'audio'})
                if args.template.startswith('video'):
                    report.update(inspect_video(output))
                if abs(pipeline.get_duration(str(output)) - args.audio_seconds) > .15:
                    raise RuntimeError('Output duration differs from fixture')
                stems = list(output.parent.glob('*_stem_*.wav'))
                if len(stems) != 4:
                    raise RuntimeError(f'Expected four stems, found {len(stems)}')
                for stem in stems:
                    _validate_media(str(stem), {'audio'})
                    if abs(pipeline.get_duration(str(stem)) - args.audio_seconds) > .15:
                        raise RuntimeError('Stem timeline changed: ' + stem.name)
                report['stems'] = [stem.name for stem in stems]
            preserved = ROOT / 'docs/validation' / ('2026-10-04-' + args.template + suffix + '-output')
            preserved.mkdir(exist_ok=True)
            for artifact in output.parent.iterdir():
                if artifact.is_file():
                    shutil.copy2(artifact, preserved / artifact.name)
            report.update(acceptance=True, output=str(preserved / output.name))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic() - started, 3), workspace_removed=not job.workspace.exists())
        (ROOT / 'docs/validation' / ('2026-10-04-' + args.template + suffix + '-workflow.json')).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
