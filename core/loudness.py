"""Measured voice loudness with the project's existing FFmpeg runtime."""
import json
import math
import os
import subprocess
import tempfile

from pydub import effects
from core.audio_utils import load_playable_audio
from core.render_context import run_process

TARGET_LUFS = -14.0
TRUE_PEAK_DB = -1.5


def _ffmpeg(args):
    with tempfile.TemporaryFile() as diagnostics:
        try:
            run_process(['ffmpeg', '-hide_banner', '-nostats', *args], check=True,
                        timeout=1800, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=diagnostics)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            diagnostics.seek(0, os.SEEK_END)
            diagnostics.seek(max(0, diagnostics.tell() - 6000))
            raise RuntimeError('Voice loudness processing failed: ' +
                               diagnostics.read().decode('utf-8', errors='replace')) from exc
        diagnostics.seek(0, os.SEEK_END)
        diagnostics.seek(max(0, diagnostics.tell() - 16384))
        return diagnostics.read().decode('utf-8', errors='replace')


def measure_loudness(path):
    detail = _ffmpeg(['-i', str(path), '-af',
        f'loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA=7:print_format=json', '-f', 'null', os.devnull])
    try:
        data, _ = json.JSONDecoder().raw_decode(detail[detail.rindex('{'):])
        return {key: float(data[key]) for key in
                ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')}
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError('FFmpeg returned invalid voice loudness measurements') from exc


def normalize_voice_loudness(path):
    """Publish only a validated normalization; preserve silence and short cues."""
    source = load_playable_audio(path)
    if source.max == 0:
        return {'mode': 'silence', 'integrated_loudness_measured': False}
    before = measure_loudness(path)
    from core.pipeline import _staged_output
    with _staged_output(path) as pending:
        if all(math.isfinite(value) for value in before.values()):
            options = (f'loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA=7:'
                f'measured_I={before["input_i"]}:measured_TP={before["input_tp"]}:'
                f'measured_LRA={before["input_lra"]}:measured_thresh={before["input_thresh"]}:'
                f'offset={before["target_offset"]}:linear=false')
            _ffmpeg(['-y', '-i', str(path), '-af', options, '-ar', str(source.frame_rate),
                     '-ac', str(source.channels), '-c:a', 'pcm_s16le', pending])
            mode = 'measured_two_pass'
        else:
            # Very short clips can have no gated loudness measurement.
            effects.normalize(source, headroom=-TRUE_PEAK_DB).export(pending, format='wav').close()
            mode = 'short_clip_peak_fallback'
        result = load_playable_audio(pending)
        if abs(len(result) - len(source)) > 20 or result.channels != source.channels or result.frame_rate != source.frame_rate:
            raise RuntimeError('Voice loudness normalization changed the source timeline or format')
        after = measure_loudness(pending) if mode == 'measured_two_pass' else None
        peak_correction_db = 0.0
        if after and math.isfinite(after['input_tp']) and after['input_tp'] > TRUE_PEAK_DB + 0.3:
            # Resampling can overshoot the limiter's peak. Reduce gain only;
            # do not change pauses, duration, pitch or the rejection threshold.
            peak_correction_db = after['input_tp'] - TRUE_PEAK_DB + 0.05
            result.apply_gain(-peak_correction_db).export(pending, format='wav').close()
            after = measure_loudness(pending)
        if after and (not math.isfinite(after['input_i']) or not math.isfinite(after['input_tp'])
                      or after['input_tp'] > TRUE_PEAK_DB + 0.3):
            raise RuntimeError(f'Voice loudness normalization produced invalid loudness or excessive true peak: {after}')
    return {'mode': mode, 'integrated_loudness_measured': mode == 'measured_two_pass',
            'target_lufs': TARGET_LUFS, 'true_peak_limit_db': TRUE_PEAK_DB,
            'peak_correction_db': peak_correction_db,
            'achieved_lufs': after['input_i'] if after else None,
            'achieved_true_peak_db': after['input_tp'] if after else None}
