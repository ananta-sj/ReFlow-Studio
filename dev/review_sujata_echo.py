"""Isolate perceived echo: retained native-rate input and one tempo option."""
import json
import math
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.loudness import measure_loudness
    from core.render_context import RenderContext, bind_job, run_process
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-native-playback.json').read_text(encoding='utf-8'))
    native = json.loads((ROOT / 'docs/validation/2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    source = Path(prior['directory']).resolve()
    if not source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside validation storage')
    raw_source = Path(native['review_directory']).resolve() / 'sujata-raw.wav'
    if not raw_source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Raw source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-sujata-echo-' + uuid.uuid4().hex[:8])
    report = dict(new_inference=False, production_changed=False, echo_origin_established=False,
                  human_quality_accepted=False, tempo=1.342, cases=[])
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            input_path = source / 'sujata-native-input.wav'
            baseline = source / 'sujata-native.wav'
            report.update(input_sha256=digest(input_path), baseline_sha256=digest(baseline))
            original = load_speech_audio(input_path)
            if original.channels != 1 or original.frame_rate != 24000:
                raise ValueError('Expected retained native mono input')
            baseline_level = measure_loudness(baseline)
            shutil.copy2(baseline, work / 'current.wav')
            shutil.copy2(input_path, work / 'no-tempo.wav')
            raw = load_speech_audio(raw_source)
            if raw.frame_rate != 22050:
                raise ValueError('Expected retained mislabeled decoder samples')
            raw._spawn(raw.raw_data, overrides={'frame_rate': 24000}).export(
                work / 'raw-native.wav', format='wav').close()
            report['raw_source_sha256'] = digest(raw_source)
            short = work / 'short-window.wav'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(input_path),
                '-af', 'rubberband=tempo=1.342:pitch=1:window=short', '-ar', '24000',
                '-ac', '1', '-c:a', 'pcm_s16le', str(short)], check=True, timeout=60)
            for name in ('no-tempo', 'short-window', 'raw-native'):
                path = work / (name + '.wav')
                audio = load_speech_audio(path)
                before = measure_loudness(path)
                if not all(math.isfinite(before[key]) for key in ('input_i', 'input_tp')):
                    raise RuntimeError('Cannot measure diagnostic audio')
                # Gain only: approximate the current clip's integrated level,
                # while keeping measured true peak below -1.5 dBTP.
                target_level = baseline_level['input_i'] if name == 'short-window' else -18.0
                gain = min(target_level - before['input_i'], -1.55 - before['input_tp'])
                audio.apply_gain(gain).export(path, format='wav').close()
                final = load_speech_audio(path)
                measured = measure_loudness(path)
                expected = len(original) / (1.342 if name == 'short-window' else 1)
                if abs(len(final)-expected) > 100 or measured['input_tp'] > -1.2:
                    raise RuntimeError('Diagnostic timing or peak check failed')
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                report['cases'].append(dict(name=name, seconds=len(final)/1000, gain_db=gain,
                    integrated_lufs=measured['input_i'], true_peak_db=measured['input_tp'], sha256=digest(path)))
            report['short_window_identical_to_current'] = digest(short) == digest(baseline)
            report['baseline_loudness'] = baseline_level
            job.publish(work, destination)
            report['directory'] = str(destination)
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-sujata-echo.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
