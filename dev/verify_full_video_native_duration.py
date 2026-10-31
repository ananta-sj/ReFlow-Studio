"""Compare native timing predictions against all published review waveforms."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
import soundfile as sf


def main():
    report_path = ROOT / 'docs/validation/2026-10-08-spoken-hindi-full-video-887151ac.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    prediction = json.loads((ROOT / 'docs/validation/2026-10-08-native-duration-preflight.json').read_text())
    required = ['completed', 'automatic_pipeline_pass', 'full_decode_pass', 'source_unchanged',
                'workspace_removed', 'model_worker_reused', 'gpu_worker_released']
    assert all(report[key] is True for key in required)
    assert len(report['cues']) == len(prediction['cues']) == 14
    folder = Path(report['directory'])
    output = folder / report['output']
    output_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    source_sha = hashlib.sha256((ROOT / 'Sample/2.mp4').read_bytes()).hexdigest()
    assert output_sha == report['output_sha256']
    assert source_sha == report['source_sha256']
    checks = []
    for cue, estimated in zip(report['cues'], prediction['cues']):
        wave = folder / cue['file']
        info = sf.info(wave)
        measured = info.frames / info.samplerate
        assert abs(measured-estimated['predicted']) <= 1 / info.samplerate
        assert measured <= estimated['available'] + .001
        assert hashlib.sha256(wave.read_bytes()).hexdigest() == cue['result']['output_sha256']
        checks.append(dict(cue=cue['index']+1, predicted=estimated['predicted'], measured=measured,
                           available=estimated['available'], fits=True, hash_matches=True))
    evidence = dict(completed=True, all_14_match_within_one_sample=True, all_14_fit=True,
                    output=str(output), output_sha256=output_sha, source_sha256=source_sha,
                    render_receipt=str(report_path.relative_to(ROOT)), cues=checks,
                    human_quality_accepted=False,
                    note='Post-render verification. Current render started before duration preflight was added.')
    destination = ROOT / 'docs/validation/2026-10-08-full-video-native-duration-verified.json'
    destination.write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(completed=True, verified_cues=len(checks), output=str(output))))


if __name__ == '__main__':
    main()
