"""Inspect live-run output and retained evidence; performs no model calls."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frames(path):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path),
        '-map', '0:v:0', '-f', 'framemd5', '-'], capture_output=True, check=True, timeout=120)
    return [tuple(part.strip() for part in line.split(',')) for line in result.stdout.decode('utf-8').splitlines()
            if line.strip() and not line.startswith('#')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    report = read(args.receipt)
    folder = Path(report['output_folder'])
    first, second = report['passes']
    output = Path(second['output'])
    manifest = read(second['manifest_path'])
    speech = next(item for item in manifest['cue_artifacts'] if item['phase'] == 'speech-input')
    cues = read(speech['path'])['segments']
    from core.loudness import measure_loudness
    from core.audio_utils import load_playable_audio, AudioEngineer
    base = output.with_suffix('')
    paths = {role: Path(str(base) + '_stem_' + role + '.wav') for role in ('vocals', 'background', 'master', 'dubbed')}
    stems = {role: load_playable_audio(path) for role, path in paths.items()}
    mixed = AudioEngineer().dynamic_mix(stems['dubbed'], stems['background'], ducking_db=-12)
    source_frames, output_frames = frames(folder / 'source-excerpt.mp4'), frames(output)
    comparison = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(folder / 'source-excerpt.mp4'),
        '-i', str(output), '-lavfi', 'ssim', '-an', '-f', 'null', '-'], capture_output=True, check=True, timeout=120)
    quality = re.findall(r'All:([0-9.]+)', comparison.stderr.decode('utf-8', errors='replace'))
    if not quality:
        raise RuntimeError('FFmpeg did not report video SSIM')
    ssim = float(quality[-1])
    checks = {
        'execution_stages_and_cleanup_completed': second.get('full_decode_pass')
            and all(item['workspace_removed'] and item['owned_processes_released']
                and item['speech_sessions_released'] for item in report['passes'])
            and report['persistent_state_unchanged'] and report['source_unchanged'],
        'real_speech_cancellation_and_restart': first.get('cancelled') and first.get('speech_generating_observed')
            and first['manifest_status'] == 'cancelled' and second['manifest_status'] == 'completed',
        'first_recognition_and_translation_were_fresh': {'stt', 'translation'} <=
            {item['stage'] for item in first['checkpoints'] if item['status'] == 'stored'}
            and not any(item['status'] == 'hit' for item in first['checkpoints']),
        'restart_reused_verified_stages': {'stt', 'translation'} <=
            {item['stage'] for item in second['checkpoints'] if item['status'] == 'hit'},
        'video_frame_timing_preserved': bool(source_frames) and [row[:4] for row in source_frames] == [row[:4] for row in output_frames],
        'video_similarity_after_expected_h264_encode': ssim >= .97,
        'output_matches_manifest': manifest['output']['sha256'] == sha(output) == second['output_sha256'],
        'cue_artifact_hashes_match': all(sha(item['path']) == item['sha256'] for item in manifest['cue_artifacts']),
        'canonical_source_and_translation_retained': bool(cues) and all(cue.get('cue_id')
            and cue.get('source_text') and cue.get('translated_text') for cue in cues),
        'cue_windows_within_video': all(0 <= cue['start'] < cue['end'] <= second['duration_seconds'] + .1 for cue in cues),
        'stems_match_source_timeline': all(abs(len(audio) / 1000 - report['excerpt_seconds']) < .2 for audio in stems.values()),
        'dubbed_voice_non_silent': stems['dubbed'].rms > 0,
        'background_non_silent': stems['background'].rms > 0,
        'published_master_is_ducked_dub_plus_background': mixed.raw_data == stems['master'].raw_data,
        'completed_expected_stages': {'source', 'separate', 'stt', 'translation', 'speech', 'timing', 'media'} <=
            {op['stage'] for op in manifest['operations'] if op['status'] == 'completed'} | {'stt', 'translation'},
    }
    result = dict(passed=all(checks.values()), checks=checks, receipt=str(args.receipt.resolve()),
        driver_reported_passed=report['passed'],
        driver_stem_record_count=len(second.get('stems', [])),
        verified_stem_paths={role:str(path) for role,path in paths.items()},
        output=str(output), output_sha256=sha(output), duration_seconds=second['duration_seconds'],
        frame_count=len(output_frames), video_ssim=ssim, video_ssim_threshold=.97,
        decoded_video_pixels_identical=source_frames == output_frames,
        expected_video_reencoding=True, cues=[{key:cue.get(key) for key in
            ('cue_id', 'start', 'end', 'source_text', 'translated_text')} for cue in cues],
        loudness={role:measure_loudness(path) for role,path in paths.items()},
        stem_rms={role:audio.rms for role,audio in stems.items()},
        human_quality_accepted=False, no_english_leakage_proven=False,
        speech_shot_alignment_human_verified=False)
    destination = args.receipt.with_name(args.receipt.stem + '-output-audit.json')
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(destination)
    print(json.dumps(checks, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
