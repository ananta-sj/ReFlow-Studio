"""Measure waveform edges; do not infer audible quality or word boundaries."""
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def main():
    import numpy as np
    from core.audio_utils import load_speech_audio
    validation = ROOT / 'docs/validation'
    native = json.loads((validation / '2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    noise = json.loads((validation / '2026-10-04-hindi-noise.json').read_text(encoding='utf-8'))
    report = dict(human_listening_performed=False, measurements={})

    def finite(value):
        return value if math.isfinite(value) else None

    for name in ('sujata', 'abhishek'):
        for stage, path in [('raw', Path(native['review_directory']) / (name + '-raw.wav')),
                            ('processed', Path(noise['review_directory']) / (name + '.wav'))]:
            if not path.resolve().is_relative_to(validation.resolve()):
                raise ValueError('Audio outside validation storage')
            clip = load_speech_audio(path)
            samples = np.asarray(clip.get_array_of_samples(), dtype=float)/clip.max_possible_amplitude
            count = clip.frame_rate//10
            row = dict(seconds=len(clip)/1000, first_sample=float(samples[0]), last_sample=float(samples[-1]),
                       first100ms_max_jump=float(np.max(np.abs(np.diff(samples[:count])))),
                       last100ms_max_jump=float(np.max(np.abs(np.diff(samples[-count:])))), edges={})
            for ms in (10, 30, 100, 250, 500):
                row['edges'][str(ms)] = dict(start_rms_dbfs=finite(clip[:ms].dBFS),
                    start_peak_dbfs=finite(clip[:ms].max_dBFS),
                    end_rms_dbfs=finite(clip[-ms:].dBFS), end_peak_dbfs=finite(clip[-ms:].max_dBFS),
                    end_digital_silence=clip[-ms:].max == 0)
            report['measurements'][name + '-' + stage] = row
    (validation / '2026-10-04-hindi-edge-audit.json').write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('Four waveform edge measurements saved; null levels denote digital silence/unmeasurable RMS.')


if __name__ == '__main__':
    main()
