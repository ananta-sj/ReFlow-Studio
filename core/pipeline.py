from pathlib import Path
import os
import sys
import subprocess
import gc
import time
import logging
import shutil
import datetime
import threading
import json
import math
import tempfile
import uuid
import wave
from contextlib import contextmanager, nullcontext
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pydub import AudioSegment, effects
from core.render_context import current_job, check_cancelled, bind_job, run_process, RenderCancelled
from core.audio_utils import load_playable_audio, load_speech_audio
from audio_separator import AudioSeparator
from settings import Settings
from core.languages import LANGUAGE_NAMES
from core.providers.base import require_translation_text, release_speech
from core.transcription import normalize_transcription
from core.pipeline_contracts import PipelineSpec, TEMPLATES, SettingsSnapshot, identify_cues, finalize_grouped_cues
from core.run_manifest import RunManifest, bind_manifest, current_manifest, observe_provider, file_identity
from core.source_language import normalize_source_selection, resolve_source_language, SOURCE_LANGUAGE_NAMES, AUTO_SOURCE_MIN_CONFIDENCE
from core.speech_language import resolve_speech_language, preflight_speech, actor_uses_f5
from core.model_registry import ModelRegistry
from core.parallel_policy import segment_buffer_window
from core.providers import resolve as providers

# Ensure we can find config.py in the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ffmpeg/ffprobe calls throughout this pipeline are local, deterministic
# muxing/extraction steps - legitimately fast even for a long video. None
# of them previously had a timeout at all, so a hang (corrupt input,
# ffmpeg waiting on a stdin prompt it'll never get) could block the
# render thread - and therefore that whole job - indefinitely, with
# nothing surfaced to the UI. 30 minutes is generous headroom for even a
# very long video's mux step while guaranteeing a genuinely hung job
# eventually raises a visible error. The render worker in bridge/api.py
# turns these exceptions into a render_error event.
_FFMPEG_TIMEOUT_SEC = 1800
_FFPROBE_TIMEOUT_SEC = 60
_DIAGNOSTIC_TAIL_BYTES = 6000

# Launched one notch below normal priority on Windows so a heavy encode
# doesn't starve the OS/other apps of CPU time - the render itself doesn't
# finish meaningfully slower (ffmpeg still gets scheduled whenever the
# system isn't busy with something the user is actively interacting with),
# but the rest of the machine - including this app's own UI thread -
# stays responsive instead of everything feeling like it's crawling while
# a render is active. No equivalent flag exists on macOS/Linux via
# subprocess directly (would need os.nice() in a preexec_fn there), so
# this is Windows-only for now, matching the rest of this codebase's
# Windows-primary scope (WinForms pywebview backend).
_LOW_PRIORITY_FLAGS = subprocess.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 0


def _preflight_native_cue_durations(provider, transcript, cast_list, total_duration=None):
    """Assess all native windows, persist conflicts, then stop before speech."""
    from core.dialogue_adaptation import assess, DialogueReviewRequired
    manifest = current_manifest()
    operation = manifest.operation('dialogue', provider) if manifest else nullcontext()
    with operation as observation:
        report = assess(provider, transcript, cast_list, manifest, total_duration=total_duration)
        if observation is not None:
            observation['result_status'] = report['status']
        if manifest is not None:
            manifest.report('dialogue', report)
        if report['status'] == 'needs_review':
            raise DialogueReviewRequired(report)


def _release_translation(provider):
    if getattr(provider, 'engine_id', None) in ('indictrans2', 'nllb', 'ollama_m2m100'):
        provider.release()


@contextmanager
def _translation_stage(provider):
    """Release the stage-owned worker on success, failure and generator close."""
    try:
        yield
    except BaseException:
        try:
            _release_translation(provider)
        except Exception as error:
            # Keep the original stage failure/cancellation. Cleanup diagnostics
            # may contain provider details, so log only the exception type.
            logging.warning('Translation worker release failed while unwinding: %s', type(error).__name__)
        raise
    else:
        _release_translation(provider)


def _run_media_command(cmd, timeout, **kwargs):
    """Keep diagnostics on disk, exposing only a bounded tail on failure."""
    with tempfile.TemporaryFile() as diagnostics:
        # Older callers suppressed stderr. Always retain it for failures.
        kwargs.pop("stderr", None)
        kwargs.pop("check", None)
        kwargs.setdefault("stdout", subprocess.DEVNULL)
        kwargs.setdefault("stdin", subprocess.DEVNULL)
        try:
            return run_process(cmd, timeout=timeout, creationflags=_LOW_PRIORITY_FLAGS,
                                  stderr=diagnostics, check=True, **kwargs)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            diagnostics.seek(0, os.SEEK_END)
            diagnostics.seek(max(0, diagnostics.tell() - _DIAGNOSTIC_TAIL_BYTES))
            detail = diagnostics.read().decode("utf-8", errors="replace").strip()
            tool = os.path.basename(str(cmd[0]))
            if isinstance(exc, subprocess.TimeoutExpired):
                reason = f"timed out after {timeout}s"
            elif isinstance(exc, subprocess.CalledProcessError):
                reason = f"failed with exit code {exc.returncode}"
            else:
                reason = f"could not start: {exc}"
            raise RuntimeError(f"{tool} {reason}" + (f":\n{detail}" if detail else "")) from exc


def _run_ffmpeg(cmd, **kwargs):
    manifest = current_manifest()
    if manifest is None:
        return _run_media_command(cmd, _FFMPEG_TIMEOUT_SEC, **kwargs)
    with manifest.operation('media', evidence={'tool': 'ffmpeg'}) as item:
        result = _run_media_command(cmd, _FFMPEG_TIMEOUT_SEC, **kwargs)
        if isinstance(cmd[-1], str) and os.path.isfile(cmd[-1]):
            item['artifact'] = {**file_identity(cmd[-1]), 'retention': 'temporary-unless-exported'}
        return result


from core.media_io import _staged_output

def _validate_media(file_path, expected_streams):
    manifest = current_manifest()
    if manifest is None:
        return _validate_media_inner(file_path, expected_streams)
    with manifest.operation('media-validation', evidence={'path': os.path.abspath(file_path),
                            'required_streams': sorted(expected_streams)}) as item:
        duration = _validate_media_inner(file_path, expected_streams)
        item['duration_seconds'] = duration
        return duration


def _validate_media_inner(file_path, expected_streams):
    from core.media_io import validate_media_inner
    return validate_media_inner(file_path,expected_streams,_run_media_command)


def _bundle_path(output_path):
    return os.path.join(os.path.splitext(output_path)[0], os.path.basename(output_path))


@contextmanager
def _staged_bundle(output_path):
    """Publish the main render and all stems together by renaming one directory."""
    output_path = os.path.abspath(output_path)
    destination = os.path.splitext(output_path)[0]
    if os.path.exists(destination):
        raise RuntimeError('Output bundle already exists; it will be preserved')
    with tempfile.TemporaryDirectory(prefix='.reflow-bundle-', dir=os.path.dirname(output_path)) as folder:
        pending = os.path.join(folder, os.path.basename(output_path))
        yield pending
        if not os.path.isfile(pending) or not os.path.getsize(pending):
            raise RuntimeError('Output bundle has no main render')
        check_cancelled()
        if os.path.exists(destination):
            raise RuntimeError('Output bundle destination appeared; it will be preserved')
        job = current_job()
        if job:
            job.publish(folder, destination)
        else:
            os.replace(folder, destination)


def _require_visual_output(stage, result, destination, expected_duration=None):
    if not isinstance(result, str) or os.path.abspath(result) != os.path.abspath(destination):
        raise RuntimeError(f'{stage}: enabled provider did not produce the requested output')
    duration = _validate_media(result, {'video'})
    if expected_duration is not None and abs(duration - expected_duration) > 0.25:
        raise RuntimeError(f'{stage}: output duration changed from {expected_duration:.3f}s to {duration:.3f}s')
    return result


class ReflowPipeline:
    def __init__(self):
        # [PATCH v0.5.5] Centralized Config & Dynamic Paths
        self.root_dir = config.BASE_DIR
        self.temp_dir = str(current_job().workspace) if current_job() else config.TEMP_PATH
        self.output_dir = config.OUTPUT_PATH
        self.registry = ModelRegistry()

        # Check for High-Quality GAN Model (Downloaded by Integrity Guard)
        self.gan_model_path = os.path.join(self.root_dir, "core", "Wav2Lip", "checkpoints", "Wav2Lip_GAN.pth")
        
        # Auto-create directories
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        logging.info(f"Pipeline Initialized at: {self.root_dir}")

    def _settings(self):
        snapshot = getattr(self, '_run_settings', None)
        return snapshot if snapshot is not None else Settings()

    def _observe(self, stage, provider, method, *args, cue_id=None, **kwargs):
        return observe_provider(getattr(self, '_manifest', None), stage, provider, method,
                                *args, cue_id=cue_id, **kwargs)

    def _save_cues(self, phase, transcript):
        manifest = getattr(self, '_manifest', None)
        if manifest is not None:
            manifest.cues(phase, transcript)

    def _cue_namespace(self, kind):
        manifest = getattr(self, '_manifest', None)
        return kind + ':' + manifest.data['source']['sha256'] if manifest else kind

    def clear_vram(self):
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except (ImportError, OSError, RuntimeError):
            pass

    def format_timestamp(self, seconds):
        td = datetime.timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((seconds - total_seconds) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}h:{m:02d}m:{s:02d}s" if h > 0 else f"{m:02d}m:{s:02d}s"

    def generate_srt(self, transcript, output_path):
        with _staged_output(output_path) as pending:
            with open(pending, 'w', encoding='utf-8') as f:
                cue_count = 0
                for i, seg in enumerate(transcript):
                    if (not math.isfinite(seg['start']) or not math.isfinite(seg['end'])
                            or seg['start'] < 0 or seg['end'] <= seg['start']):
                        raise ValueError(f"Invalid subtitle timing at cue {i+1}")
                    start = self.format_timestamp(seg['start'])
                    end = self.format_timestamp(seg['end'])
                    text = seg['text'].strip()
                    if not text: continue
                    cue_count += 1
                    f.write(f"{cue_count}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
                if cue_count == 0:
                    raise RuntimeError("No nonempty subtitle cues were produced.")

    def get_duration(self, file_path):
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        result = _run_media_command(cmd, _FFPROBE_TIMEOUT_SEC, stdout=subprocess.PIPE)
        try:
            duration = float(result.stdout.strip())
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("duration must be finite and positive")
            return duration
        except ValueError as exc:
            raise RuntimeError(f"Could not read a valid duration of {file_path}: {exc}") from exc

    def speed_change(self, sound, speed=1.0):
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.01 <= speed <= 100:
            raise ValueError('Speech tempo must be a finite number between 0.01 and 100.')
        if speed == 1.0: return sound
        with tempfile.TemporaryDirectory(prefix="reflow-stretch-", dir=self.temp_dir) as work_dir:
            temp_in = os.path.join(work_dir, "in.wav")
            temp_out = os.path.join(work_dir, "out.wav")
            sound.export(temp_in, format="wav").close()
            # The existing atempo route audibly distorted reviewed Hindi takes.
            # Rubber Band is already compiled into the bundled FFmpeg. Keep
            # pitch unchanged; never silently substitute the rejected method.
            cmd = ['ffmpeg', '-y', '-i', temp_in, '-filter:a',
                   f"rubberband=tempo={speed}:pitch=1", '-ar', str(sound.frame_rate),
                   '-ac', str(sound.channels), '-c:a', 'pcm_s16le', '-vn', temp_out]
            try:
                _run_ffmpeg(cmd)
            except RuntimeError as exc:
                if 'rubberband' in str(exc) and ('No such filter' in str(exc) or 'Filter not found' in str(exc)):
                    raise RuntimeError('Pitch-preserving speech tempo requires the Rubber Band filter. '
                                       'Use the bundled FFmpeg build or retain the original pace.') from exc
                raise
            _validate_media(temp_out, {'audio'})
            with open(temp_out, 'rb') as audio_file:
                result = AudioSegment.from_file(audio_file, format='wav')
            if abs(len(result)-len(sound)/speed) > 100 or (sound.max and not result.max):
                raise RuntimeError('Speech tempo processing changed timing unexpectedly or removed audio.')
            if result.max:
                from core.loudness import measure_loudness
                peak = measure_loudness(temp_out)['input_tp']
                if not math.isfinite(peak):
                    raise RuntimeError('Speech tempo processing produced an invalid true peak.')
                if peak > -1.2:
                    # Same gain-only headroom correction as the accepted take;
                    # no compression, timing change or second normalization.
                    result = result.apply_gain(-max(0.0, peak + 1.5 + .05))
            return result

    # [UPDATED] MERGE WITH BURN-IN & CUSTOM SUBTITLE STYLE SUPPORT
    def merge_av(self, video_path, audio_path, subtitle_path, output_path, burn_subs=False, ffmpeg_preset="slow", sub_style=None, subtitle_language='eng'):
        for source in (video_path, audio_path):
            if not os.path.isfile(source) or os.path.getsize(source) == 0:
                raise RuntimeError(f"Missing or empty merge input: {source}")
        has_subtitles = os.path.isfile(subtitle_path) and os.path.getsize(subtitle_path) > 10
        if burn_subs and not has_subtitles:
            raise RuntimeError("Subtitle burn-in was requested but no usable subtitles were produced.")

        # Work beside the destination: replacement stays on the same filesystem,
        # and no failed mux/subtitle pass can overwrite an earlier good render.
        with _staged_output(output_path) as pending:
            with tempfile.TemporaryDirectory(prefix=".reflow-mux-", dir=os.path.dirname(pending)) as work_dir:
                clean_output = os.path.join(work_dir, "clean.mp4")
                _run_ffmpeg([
                    'ffmpeg', '-y', '-i', video_path, '-i', audio_path,
                    '-c:v', 'libx264', '-preset', ffmpeg_preset, '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                    '-map', '0:v:0', '-map', '1:a:0', clean_output,
                ])
                expected_streams = {'video', 'audio'}
                if has_subtitles:
                    if burn_subs:
                        local_sub = os.path.join(work_dir, "burn_subs.srt")
                        shutil.copy(subtitle_path, local_sub)
                        escaped_sub = local_sub.replace("\\", "/").replace(":", "\\:")
                        style = {
                            "font_size": 24, "primary_color": "&H00FFFFFF",
                            "outline_color": "&H00000000", "back_color": "&H80000000",
                            "border_style": 3, "margin_v": 10,
                        }
                        if isinstance(sub_style, dict):
                            style.update(sub_style)
                        force_style = (
                            f"Fontsize={style['font_size']},PrimaryColour={style['primary_color']},"
                            f"OutlineColour={style['outline_color']},BackColour={style['back_color']},"
                            f"BorderStyle={style['border_style']},MarginV={style['margin_v']}"
                        )
                        _run_ffmpeg([
                            'ffmpeg', '-y', '-i', clean_output,
                            '-vf', f"subtitles='{escaped_sub}':force_style='{force_style}'",
                            '-c:a', 'copy', pending,
                        ])
                    else:
                        _run_ffmpeg([
                            'ffmpeg', '-y', '-i', clean_output, '-i', subtitle_path,
                            '-c', 'copy', '-c:s', 'mov_text', '-map', '0', '-map', '1',
                            '-metadata:s:s:0', 'language='+subtitle_language, pending,
                        ])
                        expected_streams.add('subtitle')
                else:
                    os.replace(clean_output, pending)
                _validate_media(pending, expected_streams)

    def _dub_segment(self, *args, **kwargs):
        job = kwargs.pop("job_context", current_job())
        manifest = getattr(self, '_manifest', None)
        segment = args[1] if len(args) > 1 else kwargs.get('segment', {})
        operation = manifest.operation('cue-processing', evidence={'cue_id': segment.get('cue_id')}) if manifest else nullcontext()
        with bind_job(job), operation:
            check_cancelled()
            result = self._dub_segment_bound(*args, **kwargs)
            check_cancelled()
            return result

    def _dub_segment_bound(self, index, segment, cast_list, target_lang, tts_provider,
                      voice_providers_by_actor, clean_ref_wav, source_reference,
                      effective_device, sound_engineer, inference_lock=None, actor_lock=None,
                      next_start=None, allow_overflow=False):
        """Return a playable clip, or None only for a legitimate blank gap."""
        text = segment['text'].strip()
        if not text:
            return None
        actor = cast_list[index % len(cast_list)]
        is_cloned = actor == "CLONED_USER"
        stage = "timing validation"
        try:
            start, end = segment['start'], segment['end']
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
                raise ValueError("segment timing must be finite, nonnegative, and increasing")
            target_dur = (end - start) * 1000
            if target_dur < 1:
                raise ValueError("dialogue window is shorter than one millisecond")
            if next_start is not None and (not math.isfinite(next_start) or next_start < start):
                raise ValueError("next segment start is invalid")
            # Unique per invocation: neither an earlier failure nor another
            # segment worker can supply stale files to this line.
            with tempfile.TemporaryDirectory(prefix=f"reflow-segment-{index+1}-", dir=self.temp_dir) as work_dir:
                seg_tts = os.path.join(work_dir, "synthesized.wav")
                seg_final = os.path.join(work_dir, "selected_voice.wav")
                reference = clean_ref_wav if clean_ref_wav is not None else source_reference
                stage = "selected voice resolution"
                if not is_cloned:
                    def ensure_actor():
                        if actor not in voice_providers_by_actor:
                            voice_providers_by_actor[actor] = providers.resolve_voice_for_actor(
                                self.registry, actor, effective_device)
                    self._maybe_locked(actor_lock, ensure_actor)
                is_f5tts = actor_uses_f5(self.registry, actor)
                if is_f5tts:
                    stage = "F5 speech generation"
                    self._maybe_locked(inference_lock, lambda: self._observe('voice', voice_providers_by_actor[actor], 'convert',
                        None, seg_final, model_name=actor, text=text, reference_audio=reference, cue_id=segment.get('cue_id')))
                    load_speech_audio(seg_final)
                else:
                    stage = "speech generation"
                    preflight_speech(self.registry, [actor], target_lang)
                    self._maybe_locked(inference_lock, lambda: self._observe('speech', tts_provider, 'synthesize',
                        text, seg_tts, language=target_lang, reference_audio=reference, cue_id=segment.get('cue_id')))
                    raw = load_speech_audio(seg_tts)
                    if is_cloned:
                        shutil.copy(seg_tts, seg_final)
                    else:
                        stage = "audio normalization"
                        effects.normalize(raw, headroom=3.0).export(seg_tts, format="wav").close()
                        stage = "selected voice conversion"
                        self._maybe_locked(inference_lock, lambda: self._observe('voice', voice_providers_by_actor[actor], 'convert',
                            seg_tts, seg_final, model_name=actor, cue_id=segment.get('cue_id')))
                        load_speech_audio(seg_final)
                stage = "mastering"
                native_delivery = is_cloned and getattr(tts_provider, 'preserves_native_delivery', False) is True
                if native_delivery:
                    # Provider already prepared the reviewed native speech. Reprocessing
                    # would invalidate its reference-pair and listening recipe.
                    pass
                elif is_cloned or is_f5tts:
                    # Share the reviewed loudness treatment across generated
                    # voices and languages without changing their native timbre
                    # with an extra compressor/treble overlay.
                    from core.loudness import normalize_voice_loudness
                    normalize_voice_loudness(seg_final)
                else:
                    sound_engineer.master_voice_segment(seg_final)
                clip = load_speech_audio(seg_final)
                generated_seconds = len(clip)/1000
                stage = "timing adjustment"
                max_allowed_dur = max(target_dur, (next_start - start) * 1000) if next_start is not None else target_dur
                # Use available inter-cue silence before accelerating speech.
                fit_duration = max_allowed_dur if len(clip) > target_dur else target_dur
                from core.speech_timing import speed_for_window,measured_conflict,SpeechTimingReviewRequired
                speed = speed_for_window(len(clip),fit_duration,target_lang,native_delivery)
                clip = self.speed_change(clip, speed)
                if len(clip) > max_allowed_dur and not allow_overflow:
                    if clip[int(max_allowed_dur):].max:
                        raise SpeechTimingReviewRequired(measured_conflict(getattr(self,'_manifest',None),clip,
                            index=index,segment=segment,actor=actor,generated_seconds=generated_seconds,
                            available_seconds=max_allowed_dur/1000,speed=speed,native_delivery=native_delivery))
                    # Discard only exact digital silence, never audible content.
                    clip = clip[:int(max_allowed_dur)]
                if len(clip) <= 0:
                    raise RuntimeError("timing adjustment produced no playable samples")
                if clip.max == 0:
                    raise RuntimeError("timing adjustment removed all generated speech")
                manifest = getattr(self, '_manifest', None)
                if manifest:
                    with manifest.operation('timing', evidence=dict(cue_id=segment.get('cue_id'),
                        actor=actor, speed=speed, duration_seconds=len(clip)/1000,
                        available_seconds=max_allowed_dur/1000, native_delivery=native_delivery)):
                        pass
                return clip
        except Exception as exc:
            from core.speech_timing import SpeechTimingReviewRequired
            if isinstance(exc, (RenderCancelled,SpeechTimingReviewRequired)):
                raise
            raise RuntimeError(f"Segment {index+1}, voice '{actor}', {stage} failed: {exc}") from exc

    @staticmethod
    def _require_dialogue(transcript):
        if not any(isinstance(seg.get('text'), str) and seg['text'].strip() for seg in transcript):
            raise RuntimeError("No dialogue detected. Check the source audio or transcription settings.")

    @staticmethod
    def _maybe_locked(lock, fn):
        check_cancelled()
        if lock:
            with lock:
                check_cancelled()
                result = fn()
        else:
            result = fn()
        check_cancelled()
        return result

    @staticmethod
    def _merge_short_segments(transcript, min_duration_sec=2.5, max_gap_sec=0.6,
                              max_merged_sec=9.0, allow_sentence_continuations=False):
        """Join short cues, optionally joining a conservative sentence continuation.

        An unfinished line followed by a lowercase word can be one sentence
        even when the first cue is long. All joins retain the source window,
        pause/length bounds and speaker identity. Additional sentence joins
        are enabled only for a single voice: cue indexes assign alternating
        voices in the current multi-voice pipeline.
        """
        if not transcript:
            return transcript
        merged = [dict(transcript[0])]
        if transcript[0].get('cue_id'):
            merged[0]['source_fragments'] = [dict(transcript[0])]
        for seg in transcript[1:]:
            prev = merged[-1]
            gap = seg['start'] - prev['end']
            prev_dur = prev['end'] - prev['start']
            candidate_dur = seg['end'] - prev['start']
            preceding = prev['text'].strip().rstrip('\"\'”’»)]}')
            following = seg['text'].strip().lstrip('\"\'“‘«([{')
            continuation = (allow_sentence_continuations and bool(preceding) and bool(following)
                            and preceding[-1] not in '.?!।॥'
                            and following[0].islower())
            same_speaker = all(prev.get(key) == seg.get(key) for key in ('speaker', 'speaker_id'))
            if (0 <= gap <= max_gap_sec and candidate_dur <= max_merged_sec and same_speaker
                    and (prev_dur < min_duration_sec or continuation)):
                prev['end'] = seg['end']
                prev['text'] = f"{prev['text'].strip()} {seg['text'].strip()}".strip()
                if prev.get('cue_id'):
                    prev['source_fragments'].append(dict(seg))
            else:
                merged.append(dict(seg))
                if seg.get('cue_id'):
                    merged[-1]['source_fragments'] = [dict(seg)]
        return merged

    def _dub_all_segments(self, transcript, cast_list, target_lang, tts_provider, voice_providers_by_actor,
                           clean_ref_wav, source_reference, effective_device, sound_engineer,
                           total_duration, progress_start, progress_span, max_workers=1):
        """Generator - yields (percent, status, None) tuples as segments
        complete, and returns the finished voice_track AudioSegment
        (retrievable via `voice_track = yield from self._dub_all_segments(...)`).

        Nonblank dialogue must produce playable audio. Failures propagate
        in both sequential and existing segment-worker execution.

        Segment files are isolated in unique temporary folders. Existing
        Shared speech inference is serialized on every device; actor resolution
        has its own lock. Independent audio processing remains parallel. Mixing happens
        in segment order after worker results are available; this does not
        establish thread safety for every underlying speech engine."""
        self._require_dialogue(transcript)
        if not math.isfinite(total_duration) or total_duration <= 0:
            raise ValueError("Source duration must be finite and positive.")
        from core.speech_timing import bounded_cues
        bounded=bounded_cues(transcript,total_duration)
        changes=[dict(cue_id=old.get('cue_id'),original_end=old['end'],end=new['end'])
                 for old,new in zip(transcript,bounded) if old['end']!=new['end']]
        if changes and getattr(self,'_manifest',None):
            self._manifest.report('speech-boundary',dict(status='adjusted',reason='Existing ASR rounding tolerance capped at source end',changes=changes))
        transcript=bounded
        voice_track = AudioSegment.silent(duration=int(total_duration * 1000))
        total = len(transcript)

        window_size = segment_buffer_window(max_workers)
        if max_workers <= 1:
            for i, segment in enumerate(transcript):
                check_cancelled()
                percent = progress_start + int((i / total) * progress_span)
                check_cancelled()
                yield (percent, f"DUBBING SEG {i+1}/{total}", None)
                next_start = transcript[i + 1]['start'] if i + 1 < total else max(segment['end'],total_duration)
                clip = self._dub_segment(
                    i, segment, cast_list, target_lang, tts_provider, voice_providers_by_actor,
                    clean_ref_wav, source_reference, effective_device, sound_engineer,
                    next_start=next_start,
                )
                if clip is None and segment['text'].strip():
                    raise RuntimeError(f"Segment {i+1} produced no dialogue audio.")
                if clip is not None:
                    voice_track = voice_track.overlay(clip, position=int(segment['start'] * 1000))
            return voice_track

        # CPU providers also cache mutable engines and RVC writes shared model
        # configuration. Protect initialization and inference across all actors,
        # including when a requested GPU engine falls back to CPU.
        inference_lock = threading.Lock()
        actor_lock = threading.Lock()
        clips_by_index = {}

        next_submit = next_mix = done_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            try:
                while next_mix < total:
                    check_cancelled()
                    # Bound both futures and out-of-order clips by the mixing
                    # cursor. A slow first segment cannot grow the buffer forever.
                    while next_submit < min(total, next_mix + window_size):
                        index = next_submit
                        future = pool.submit(self._dub_segment, index, transcript[index],
                            cast_list, target_lang, tts_provider, voice_providers_by_actor,
                            clean_ref_wav, source_reference, effective_device, sound_engineer,
                            inference_lock, actor_lock,
                            transcript[index + 1]['start'] if index + 1 < total else max(transcript[index]['end'],total_duration),
                            job_context=current_job())
                        futures[future] = index
                        next_submit += 1
                    completed, _ = wait(futures, timeout=.2, return_when=FIRST_COMPLETED)
                    for future in completed:
                        index = futures.pop(future)
                        clip = future.result()
                        if clip is None and transcript[index]['text'].strip():
                            raise RuntimeError(f'Segment {index + 1} produced no dialogue audio')
                        clips_by_index[index] = clip
                        done_count += 1
                        check_cancelled()
                        percent = progress_start + int((done_count / total) * progress_span)
                        yield (percent, f'DUBBING SEG {done_count}/{total} (parallel x{max_workers})', None)
                    while next_mix in clips_by_index:
                        clip = clips_by_index.pop(next_mix)
                        if clip is not None:
                            voice_track = voice_track.overlay(clip, position=int(transcript[next_mix]['start'] * 1000))
                        next_mix += 1
            finally:
                for future in futures:
                    future.cancel()
        return voice_track

    def _resolve_translation_and_filter(self, settings):
        """Resolves the active translation provider together with whatever
        custom_instructions the user set on it in the Marketplace, plus -
        only if a profanity_filter model is active - that provider too.
        Profanity filtering is opt-in purely by being connected/activated
        (same "on iff connected" pattern AirLLM uses for translation
        itself), so filter_provider is None whenever nothing is set up for
        that stage, and callers should skip calling it entirely in that
        case rather than passing through a no-op."""
        translation_provider = providers.resolve_translation(self.registry, settings.get("ollama_host"),
            **({'runtime': settings.get('nllb_runtime')} if settings.get('nllb_runtime') == 'isolated' else {}),
            **({'fallback_runtime':'isolated'} if settings.get('m2m100_runtime') == 'isolated' else {}))
        translation_entry = self.registry.get_active("translation")
        translation_instructions = (translation_entry or {}).get("custom_instructions") or ""

        filter_provider = None
        filter_instructions = ""
        filter_entry = self.registry.get_active("profanity_filter")
        if filter_entry:
            filter_provider = providers.resolve_profanity_filter(self.registry, settings.get("ollama_host"))
            filter_instructions = filter_entry.get("custom_instructions") or ""

        return translation_provider, translation_instructions, filter_provider, filter_instructions

    @staticmethod
    def _translation_target(target_lang):
        if target_lang not in LANGUAGE_NAMES:
            raise ValueError(f"Unknown translation target code: {target_lang}")
        return LANGUAGE_NAMES[target_lang]

    @staticmethod
    def _translate_line(text, target_name, translation_provider, translation_instructions,
                        filter_provider, filter_instructions, context="Translation", source_language=None, cue=None):
        check_cancelled()
        if not isinstance(text, str):
            raise RuntimeError(f"{context}: translation input must be a string.")
        if not text.strip():
            return text
        try:
            text = require_translation_text(observe_provider(current_manifest(), 'translation',
                translation_provider, 'translate', text, target_name,
                custom_instructions=translation_instructions, source_language=source_language,
                cue_id=cue.get('cue_id') if cue else None))
            if cue is not None:
                cue['translated_text'] = text
        except Exception as exc:
            if isinstance(exc, RenderCancelled):
                raise
            raise RuntimeError(f"{context}, translation to {target_name} failed: {exc}") from exc
        if filter_provider:
            text = ReflowPipeline._filter_line(text, filter_provider, filter_instructions, context)
        if cue is not None:
            cue['adapted_text'] = text if text != cue.get('translated_text') else None
            cue['revision'] = cue.get('revision', 0) + 1
            if current_manifest() is not None:
                current_manifest().cues('translation-cue', [dict(cue, text=text)])
        check_cancelled()
        return text

    @staticmethod
    def _filter_line(text, provider, instructions, context='Moderation'):
        check_cancelled()
        result = observe_provider(current_manifest(), 'moderation', provider, 'filter_text', text, custom_instructions=instructions)
        if result == '' and getattr(provider, 'supports_line_removal', False):
            return ''
        try:
            return require_translation_text(result)
        except Exception as error:
            raise RuntimeError(f'{context}: invalid profanity-filter result: {error}') from error

    def _moderate_source(self, transcript, settings):
        entry = self.registry.get_active('profanity_filter') if self.registry else None
        if entry:
            provider = providers.resolve_profanity_filter(self.registry, settings.get('ollama_host'))
            for index, segment in enumerate(transcript):
                if segment['text'].strip():
                    segment['text'] = self._filter_line(segment['text'], provider,
                        entry.get('custom_instructions') or '', f'Segment {index + 1}')
                    segment['adapted_text'] = segment['text'] if segment['text'] != segment.get('source_text') else None
                    segment['revision'] = segment.get('revision', 0) + 1
            if not any(segment['text'].strip() for segment in transcript):
                raise RuntimeError('Profanity filtering removed all dialogue; no output was published')
        return transcript

    def _transcribe_source(self, stt_provider, audio_path, allow_sentence_continuations=False, source_language='auto'):
        check_cancelled()
        source_language = normalize_source_selection(source_language)
        from core.stage_checkpoints import recognition_inputs
        checkpoints = getattr(self, '_checkpoints', None)
        key = inputs = None
        if checkpoints:
            try:
                inputs = recognition_inputs(audio_path, allow_sentence_continuations, stt_provider, source_language)
            except (OSError, ValueError, EOFError, wave.Error):
                checkpoints.event('stt', 'disabled', reason='unreadable-pcm-input')
            else:
                key = checkpoints.key('stt', stt_provider, inputs)
                cached = checkpoints.load('stt', key, inputs)
                if cached is not None:
                    return cached
        transcript = normalize_transcription(self._observe('stt', stt_provider, 'transcribe', audio_path,
            **({'source_language': source_language} if source_language != 'auto' else {})))
        transcript = transcript.with_segments(identify_cues(transcript, self._cue_namespace('recognition')))
        self._require_dialogue(transcript)
        if (allow_sentence_continuations and
                getattr(stt_provider, 'prefers_sentence_groups', False) is True):
            from core.sentence_grouping import group_sentences
            grouped = group_sentences(transcript)
        else:
            grouped = transcript.with_segments(self._merge_short_segments(
                transcript, allow_sentence_continuations=allow_sentence_continuations))
        result = grouped.with_segments(finalize_grouped_cues(grouped))
        self._save_cues('recognition-grouped', result)
        if checkpoints and key:
            checkpoints.store('stt', key, inputs, result, stt_provider)
        return result

    def _translate_cues(self, transcript, target_name, provider, instructions,
                        filter_provider, filter_instructions, source, context='Segment'):
        from copy import deepcopy
        checkpoints = getattr(self, '_checkpoints', None)
        inputs = dict(transcript=deepcopy(normalize_transcription(transcript).to_payload()), target=target_name,
                      source=dict(code=getattr(source, 'code', None), origin=getattr(source, 'origin', None)),
                      instructions=instructions)
        key = checkpoints.key('translation', provider, inputs, disabled=bool(filter_provider)) if checkpoints else None
        cached = checkpoints.load('translation', key, inputs) if checkpoints else None
        if cached is not None:
            transcript[:] = cached
            for index in range(len(transcript)):
                check_cancelled()
                yield index
            return
        for index, cue in enumerate(transcript):
            cue['text'] = self._translate_line(cue['text'], target_name, provider, instructions,
                filter_provider, filter_instructions, context=f'{context} {index+1}',
                source_language=source, cue=cue)
            yield index
        if checkpoints:
            checkpoints.store('translation', key, inputs, normalize_transcription(transcript), provider)

    def _report_source_language(self, source, transcript=None):
        callback = getattr(self, "source_language_callback", None)
        hinted = getattr(transcript, 'language_origin', None) == 'hint'
        detected = resolve_source_language("auto", None if hinted else getattr(transcript, "language", None),
                                           getattr(transcript, "language_probability", None))
        payload = {"source_code": source.code, "source_name": SOURCE_LANGUAGE_NAMES.get(source.code),
                   "origin": source.origin, "resolved": source.resolved,
                   "detected_language": detected.detected_label,
                   "detected_name": SOURCE_LANGUAGE_NAMES.get(detected.code),
                   "probability": detected.probability, "minimum_confidence": AUTO_SOURCE_MIN_CONFIDENCE}
        manifest = getattr(self, '_manifest', None)
        if manifest is not None:
            with manifest.lock:
                manifest.data['source_language_resolution'] = dict(payload)
                manifest.save()
        if callback is None:
            return
        try:
            callback(payload)
        except Exception as exc:
            logging.warning("Could not deliver source language feedback: %s", exc)

    def _transcribe_and_translate(self, audio_path, target_lang, settings, source_language="auto", speech_cast=None):
        """STT + (optional) translation - shared by every template that
        starts from an audio/video source (video_dub, audio_dub). Not used
        by subtitle_translate, which already has text and skips STT
        entirely."""
        source_language = normalize_source_selection(source_language)
        stt_provider = providers.resolve_stt(self.registry, settings.get("whisper_model_size"),
            **({'runtime': settings.get('recognition_runtime')} if settings.get('recognition_runtime') == 'isolated' else {}))
        transcript = self._transcribe_source(stt_provider, audio_path,
            allow_sentence_continuations=len(speech_cast or ['CLONED_USER']) == 1, source_language=source_language)
        source = resolve_source_language(source_language, transcript.language, transcript.language_probability)
        self._report_source_language(source, transcript)

        if speech_cast is not None:
            self._check_speech_routes(speech_cast, resolve_speech_language(target_lang, source), transcript)

        if target_lang != "source":
            target_name = self._translation_target(target_lang)
            translation_provider, translation_instructions, filter_provider, filter_instructions = \
                self._resolve_translation_and_filter(settings)
            with _translation_stage(translation_provider):
                for _ in self._translate_cues(transcript, target_name, translation_provider,
                        translation_instructions, filter_provider, filter_instructions, source):
                    pass
            # Translation/classifier weights have finished their stage. Release
            # them before loading speech and visual engines on small machines.
            del translation_provider, filter_provider
            self.clear_vram()

        else:
            self._moderate_source(transcript, settings)

        self._save_cues('speech-input', transcript)
        return transcript

    def _check_speech_routes(self, cast_list, language, transcript=None):
        actors = cast_list or ["CLONED_USER"]
        if transcript is not None:
            actors = [actors[i % len(actors)] for i, segment in enumerate(transcript) if segment['text'].strip()]
        preflight_speech(self.registry, actors, language)

    def _early_speech_check(self, cast_list, target_lang, source_language):
        actors = cast_list or ["CLONED_USER"]
        # Mixed casts need the transcript to identify which actors actually speak.
        if any(actor_uses_f5(self.registry, actor) for actor in actors):
            return
        if target_lang != "source" or source_language != "auto":
            self._check_speech_routes(cast_list, resolve_speech_language(target_lang, source_language))

    # --- MAIN PROCESSOR ---
    # ffmpeg encoding presets, speed-priority (0) to quality-priority (100).
    _PRESET_LADDER = ["veryfast", "fast", "medium", "slow", "veryslow"]

    def process_video_gen(self, video_path, cast_list, blur_strength=15, pitch_shift=0, target_lang="en", user_voice_path=None, lip_sync_active=False, enhance_active=False, keep_background=True, burn_subtitles=False, content_filter_active=False, compute_device=None, task_priority=75, texture_quality=1, parallel_workers=1, sub_style=None, export_stems=False, source_language="auto", include_subtitles=True):
        import time
        from core.janitor import Janitor

        settings = self._settings()
        source_language = normalize_source_selection(source_language)
        self._early_speech_check(cast_list, target_lang, source_language)
        from core.runtime_checks import preflight
        preflight(self.registry, {'cast_list': cast_list, 'lang': target_lang, 'keep_bg': keep_background,
            'lipsync': lip_sync_active, 'enhance': enhance_active, 'content_filter': content_filter_active,
            'xtts_runtime': settings.get('xtts_runtime'),
            'recognition_runtime': settings.get('recognition_runtime'),
            'nllb_runtime': settings.get('nllb_runtime'),
            'm2m100_runtime': settings.get('m2m100_runtime'),
            'separation_runtime': settings.get('separation_runtime'),
            'enhancement_runtime': settings.get('enhancement_runtime'),
            'compute_device': compute_device or config.DEVICE}, 'video_dub')

        # Resolve the compute device once: an explicit selection from the
        # hardware panel wins; "other:<name>" adapters aren't torch-usable,
        # so fall back to CPU rather than pass a device string torch can't use.
        effective_device = compute_device or config.DEVICE
        if effective_device.startswith("other:"):
            logging.warning(f"'{effective_device}' isn't a torch-accelerated device; using CPU instead.")
            effective_device = "cpu"

        # "Task Priority" (0=fastest, 100=highest quality) picks the ffmpeg
        # encode preset for the final mux.
        priority_idx = min(len(self._PRESET_LADDER) - 1, max(0, int(task_priority) * len(self._PRESET_LADDER) // 101))
        ffmpeg_preset = self._PRESET_LADDER[priority_idx]

        # 1. PRE-RUN CLEANUP
        janitor = Janitor()
        if current_job() is None:
            janitor.sweep(deep=False)

        start_time = time.time()
        print(f"[DEBUG] Pipeline Started at {time.strftime('%H:%M:%S')}")
        
        from audio_utils import AudioEngineer
        sound_engineer = AudioEngineer()

        if not os.path.exists(video_path): 
            check_cancelled()
            yield (0, "ERROR: NO VIDEO FILE", None)
            return

        if not cast_list: cast_list = ["CLONED_USER"]
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        final_output = os.path.join(self.output_dir, f"{base_name}_DUBBED_{target_lang.upper()}_{uuid.uuid4().hex[:12]}.mp4")
        
        # Paths
        temp_video_out = os.path.join(self.temp_dir, "temp_visuals.mp4")
        temp_audio_in = os.path.join(self.temp_dir, "original_audio.wav")
        temp_srt = os.path.join(self.temp_dir, "temp_subs.srt")
        master_audio_path = os.path.join(self.temp_dir, "master_audio.wav")
        
        # Clean User Reference
        clean_ref_wav = None
        if providers.uses_exact_reference(self.registry):
            clean_ref_wav = providers.confirmed_reference(self.registry, user_voice_path)
        elif user_voice_path and os.path.exists(user_voice_path):
            clean_ref_wav = os.path.join(self.temp_dir, "clean_reference.wav")
            sound_engineer.clean_reference_audio(user_voice_path, clean_ref_wav)
        
        # Extraction
        _run_ffmpeg(['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', temp_audio_in], stdout=subprocess.DEVNULL)
        total_duration = self.get_duration(video_path)

        # STAGE 0: SEPARATION (UVR5 Logic)
        check_cancelled()
        yield (10, "SEPARATING AUDIO", None)
        bg_track = None
        if keep_background:
            separator = AudioSeparator(device=effective_device, **({'runtime': 'isolated'} if settings.get('separation_runtime') == 'isolated' else {}))
            vocals_path, bg_path = self._observe('separate', separator, 'separate', temp_audio_in)
            if bg_path:
                bg_track = AudioSegment.from_file(bg_path)
        else:
            vocals_path = temp_audio_in

        # STAGE 1: TRANSCRIBING
        check_cancelled()
        yield (20, "TRANSCRIBING", None)
        transcription_source = vocals_path if (keep_background and vocals_path) else temp_audio_in
        whisper_model_size = settings.get("whisper_model_size")
        stt_provider = providers.resolve_stt(self.registry, whisper_model_size,
            **({'runtime': settings.get('recognition_runtime')} if settings.get('recognition_runtime') == 'isolated' else {}))
        transcript = self._transcribe_source(stt_provider, transcription_source,
            allow_sentence_continuations=len(cast_list) == 1, source_language=source_language)
        source = resolve_source_language(source_language, transcript.language, transcript.language_probability)
        self._report_source_language(source, transcript)
        speech_lang = resolve_speech_language(target_lang, source)
        self._check_speech_routes(cast_list, speech_lang, transcript)

        # STAGE 2: TRANSLATION (Hybrid Logic)
        if target_lang != "source":
            check_cancelled()
            yield (35, "AI TRANSLATING", None)
            target_name = self._translation_target(target_lang)
            translation_provider, translation_instructions, filter_provider, filter_instructions = \
                self._resolve_translation_and_filter(settings)
            with _translation_stage(translation_provider):
                for _ in self._translate_cues(transcript, target_name, translation_provider,
                        translation_instructions, filter_provider, filter_instructions, source):
                    pass

        if target_lang == "source":
            self._moderate_source(transcript, settings)
        self._save_cues('speech-input', transcript)
        if include_subtitles:
            self.generate_srt(transcript, temp_srt)
        elif burn_subtitles:
            raise ValueError("Subtitle burn-in requires subtitles to be enabled")
        else:
            temp_srt = None

        if target_lang != "source":
            del translation_provider, filter_provider
            self.clear_vram()

        # STAGE 3: VISION PREP
        _run_ffmpeg(['ffmpeg', '-y', '-i', video_path, '-c:v', 'copy', '-an', temp_video_out], stdout=subprocess.DEVNULL)

        # STAGE 4: DUBBING
        check_cancelled()
        yield (45, "INITIALIZING TTS", None)
        tts_provider = providers.resolve_tts(self.registry, effective_device, runtime=settings.get('xtts_runtime'))
        _preflight_native_cue_durations(tts_provider, transcript, cast_list, total_duration)
        # Voice is picked per cast member, not a single active model, so
        # each actor gets its own resolved (and cached, for the segment
        # loop below) provider instead of one shared instance.
        voice_providers_by_actor = {}

        # Fallback reference logic
        source_reference = vocals_path if (keep_background and vocals_path and os.path.exists(vocals_path)) else temp_audio_in

        voice_track = yield from self._dub_all_segments(
            transcript, cast_list, speech_lang, tts_provider, voice_providers_by_actor,
            clean_ref_wav, source_reference, effective_device, sound_engineer,
            total_duration, progress_start=45, progress_span=30, max_workers=parallel_workers,
        )

        # Mix Background
        if bg_track:
            check_cancelled()
            yield (75, "MIXING AUDIO", None)
            final_mix = sound_engineer.dynamic_mix(voice_track, bg_track, ducking_db=-12)
        else:
            final_mix = voice_track

        final_mix.export(master_audio_path, format="wav")
        release_speech(tts_provider)
        del tts_provider, voice_providers_by_actor
        self.clear_vram()

        # STAGE 5: LIP SYNC
        video_to_merge = temp_video_out
        visual_duration = _validate_media(temp_video_out, {'video'}) if (
            lip_sync_active or enhance_active or content_filter_active) else None
        if lip_sync_active:
            check_cancelled()
            yield (80, "LIP SYNCING", None)
            lipsync_provider = providers.resolve_lipsync(self.registry, effective_device)
            result_video = self._observe("lipsync", lipsync_provider, "execute", temp_video_out, master_audio_path, os.path.join(self.temp_dir, "temp_visuals_lipsync.mp4"))
            video_to_merge = _require_visual_output("Lip sync", result_video, os.path.join(self.temp_dir, "temp_visuals_lipsync.mp4"), visual_duration)

        # STAGE 6: ENHANCEMENT (independent of lip-sync - it's a general
        # face-restoration pass over whatever video is currently in hand)
        if enhance_active:
            check_cancelled()
            yield (90, "ENHANCING FACE", None)
            enhancer_provider = providers.resolve_enhancer(self.registry, effective_device, texture_quality, **({"runtime":"isolated"} if settings.get("enhancement_runtime")=="isolated" else {}))
            result_enhanced = self._observe('enhancer', enhancer_provider, 'enhance', video_to_merge, os.path.join(self.temp_dir, "temp_visuals_enhanced.mp4"))
            video_to_merge = _require_visual_output("Enhancement", result_enhanced, os.path.join(self.temp_dir, "temp_visuals_enhanced.mp4"), visual_duration)

        # STAGE 6.5: CONTENT FILTER
        if content_filter_active:
            check_cancelled()
            yield (93, "CONTENT FILTER SCAN", None)
            filter_provider = providers.resolve_filter(self.registry, effective_device)
            result_filtered = self._observe("filter", filter_provider, "scan_and_blur", video_to_merge, os.path.join(self.temp_dir, "temp_visuals_filtered.mp4"))
            video_to_merge = _require_visual_output("Visual filtering", result_filtered, os.path.join(self.temp_dir, "temp_visuals_filtered.mp4"), visual_duration)

        # STAGE 7: MERGE (With Burn-in Option)
        check_cancelled()
        yield (95, "FINAL MERGE", None)
        if export_stems:
            with _staged_bundle(final_output) as pending:
                self._export_stems(pending, vocals_path, bg_path if keep_background else None, master_audio_path, voice_track)
                self.merge_av(video_to_merge, master_audio_path, temp_srt, pending, burn_subs=burn_subtitles, ffmpeg_preset=ffmpeg_preset, sub_style=sub_style, subtitle_language={'hi':'hin','en':'eng'}.get(speech_lang,'und'))
            final_output = _bundle_path(final_output)
        else:
            self.merge_av(video_to_merge, master_audio_path, temp_srt, final_output, burn_subs=burn_subtitles, ffmpeg_preset=ffmpeg_preset, sub_style=sub_style, subtitle_language={'hi':'hin','en':'eng'}.get(speech_lang,'und'))

        elapsed = self.format_time(time.time() - start_time)
        log_message = (
            f"COMPLETE ✅\n"
            f"--------------------------\n"
            f"⏱️ Total Time: {elapsed}\n"
            f"📂 Output: {os.path.basename(final_output)}"
        )
        check_cancelled()
        yield (100, log_message, final_output)

    def _export_stems(self, final_output, vocals, background, master, dubbed):
        base = os.path.splitext(final_output)[0]
        for role, source in (('vocals', vocals), ('background', background), ('master', master)):
            if source is None:
                continue
            _validate_media(source, {'audio'})
            with _staged_output(base + '_stem_' + role + '.wav') as pending:
                _run_ffmpeg(['ffmpeg', '-y', '-i', source, '-vn', '-c:a', 'pcm_s16le', pending])
                _validate_media(pending, {'audio'})
        with _staged_output(base + '_stem_dubbed.wav') as pending:
            dubbed.export(pending, format='wav').close()
            _validate_media(pending, {'audio'})

    def process_audio_dub_gen(self, audio_path, cast_list, target_lang="en", user_voice_path=None,
                               keep_background=True, compute_device=None, parallel_workers=1, sub_style=None, export_stems=False, source_language="auto"):
        """audio_dub template: audio -> stt -> translate -> tts(+rvc) ->
        audio, no video at all. Reuses the exact STT/translation
        (_transcribe_and_translate) and per-segment dubbing (_dub_segment)
        logic process_video_gen uses - only the orchestration around them
        differs, since there's no video to extract from, lip-sync,
        enhance, or filter."""
        from core.janitor import Janitor


        if sub_style:
            raise ValueError('Audio-only jobs do not support subtitle styling')
        settings = self._settings()
        source_language = normalize_source_selection(source_language)
        self._early_speech_check(cast_list, target_lang, source_language)
        from core.runtime_checks import preflight
        preflight(self.registry, {'cast_list': cast_list, 'lang': target_lang, 'keep_bg': keep_background,
            'xtts_runtime': settings.get('xtts_runtime'),
            'recognition_runtime': settings.get('recognition_runtime'),
            'nllb_runtime': settings.get('nllb_runtime'),
            'm2m100_runtime': settings.get('m2m100_runtime'),
            'separation_runtime': settings.get('separation_runtime'),
            'enhancement_runtime': settings.get('enhancement_runtime'),
            'compute_device': compute_device or config.DEVICE}, 'audio_dub')
        effective_device = compute_device or config.DEVICE
        if effective_device.startswith("other:"):
            logging.warning(f"'{effective_device}' isn't a torch-accelerated device; using CPU instead.")
            effective_device = "cpu"

        if current_job() is None:
            Janitor().sweep(deep=False)
        start_time = time.time()

        from audio_utils import AudioEngineer
        sound_engineer = AudioEngineer()

        if not os.path.exists(audio_path):
            check_cancelled()
            yield (0, "ERROR: NO AUDIO FILE", None)
            return

        if not cast_list: cast_list = ["CLONED_USER"]
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        final_output = os.path.join(self.output_dir, f"{base_name}_DUBBED_{target_lang.upper()}_{uuid.uuid4().hex[:12]}.wav")
        total_duration = self.get_duration(audio_path)

        clean_ref_wav = None
        if providers.uses_exact_reference(self.registry):
            clean_ref_wav = providers.confirmed_reference(self.registry, user_voice_path)
        elif user_voice_path and os.path.exists(user_voice_path):
            clean_ref_wav = os.path.join(self.temp_dir, "clean_reference.wav")
            sound_engineer.clean_reference_audio(user_voice_path, clean_ref_wav)

        check_cancelled()
        yield (10, "SEPARATING AUDIO", None)
        bg_track = None
        if keep_background:
            separator = AudioSeparator(device=effective_device, **({'runtime': 'isolated'} if settings.get('separation_runtime') == 'isolated' else {}))
            vocals_path, bg_path = self._observe('separate', separator, 'separate', audio_path)
            if bg_path:
                bg_track = AudioSegment.from_file(bg_path)
        else:
            vocals_path = audio_path

        check_cancelled()
        yield (20, "TRANSCRIBING", None)
        transcription_source = vocals_path if (keep_background and vocals_path) else audio_path
        transcript = self._transcribe_and_translate(transcription_source, target_lang, settings, source_language, speech_cast=cast_list)
        speech_lang = resolve_speech_language(target_lang, resolve_source_language(
            source_language, transcript.language, transcript.language_probability))

        check_cancelled()
        yield (45, "INITIALIZING TTS", None)
        tts_provider = providers.resolve_tts(self.registry, effective_device, runtime=settings.get('xtts_runtime'))
        _preflight_native_cue_durations(tts_provider, transcript, cast_list, total_duration)
        voice_providers_by_actor = {}
        source_reference = vocals_path if (keep_background and vocals_path and os.path.exists(vocals_path)) else audio_path

        voice_track = yield from self._dub_all_segments(
            transcript, cast_list, speech_lang, tts_provider, voice_providers_by_actor,
            clean_ref_wav, source_reference, effective_device, sound_engineer,
            total_duration, progress_start=45, progress_span=40, max_workers=parallel_workers,
        )

        if bg_track:
            check_cancelled()
            yield (90, "MIXING AUDIO", None)
            final_mix = sound_engineer.dynamic_mix(voice_track, bg_track, ducking_db=-12)
        else:
            final_mix = voice_track

        if export_stems:
            with _staged_bundle(final_output) as pending:
                final_mix.export(pending, format="wav").close()
                _validate_media(pending, {'audio'})
                self._export_stems(pending, vocals_path, bg_path if keep_background else None, pending, voice_track)
            final_output = _bundle_path(final_output)
        else:
            with _staged_output(final_output) as pending:
                final_mix.export(pending, format="wav").close()
                _validate_media(pending, {'audio'})
        release_speech(tts_provider)
        del tts_provider, voice_providers_by_actor
        self.clear_vram()

        elapsed = self.format_time(time.time() - start_time)
        log_message = (
            f"COMPLETE ✅\n"
            f"--------------------------\n"
            f"⏱️ Total Time: {elapsed}\n"
            f"📂 Output: {os.path.basename(final_output)}"
        )
        check_cancelled()
        yield (100, log_message, final_output)

    def process_subtitle_translate_gen(self, subtitle_path, target_lang="en", source_language="auto"):
        """subtitle_translate template: subtitle file -> translate ->
        subtitle file. Skips STT/TTS/video entirely - the input already
        has correctly-timed segments and text, so only the translation
        provider is needed."""
        from core.srt_utils import parse_srt

        settings = self._settings()
        source = resolve_source_language(source_language)
        self._report_source_language(source)
        start_time = time.time()

        if not os.path.exists(subtitle_path):
            check_cancelled()
            yield (0, "ERROR: NO SUBTITLE FILE", None)
            return

        base_name = os.path.splitext(os.path.basename(subtitle_path))[0]
        final_output = os.path.join(self.output_dir, f"{base_name}_TRANSLATED_{target_lang.upper()}_{uuid.uuid4().hex[:12]}.srt")

        check_cancelled()
        yield (10, "PARSING SUBTITLES", None)
        transcript = identify_cues(parse_srt(subtitle_path), namespace=self._cue_namespace('subtitle'))
        self._save_cues('subtitle-source', transcript)
        if not transcript:
            check_cancelled()
            yield (0, "ERROR: NO SUBTITLE CUES FOUND", None)
            return

        from core.runtime_checks import preflight
        preflight(self.registry, {'lang': target_lang, 'nllb_runtime': settings.get('nllb_runtime'),
            'm2m100_runtime':settings.get('m2m100_runtime')}, 'subtitle_translate')

        if target_lang != "source":
            check_cancelled()
            yield (30, "AI TRANSLATING", None)
            target_name = self._translation_target(target_lang)
            translation_provider, translation_instructions, filter_provider, filter_instructions = \
                self._resolve_translation_and_filter(settings)
            total = len(transcript)
            with _translation_stage(translation_provider):
                for i in self._translate_cues(transcript, target_name, translation_provider,
                        translation_instructions, filter_provider, filter_instructions, source, context='Subtitle cue'):
                    check_cancelled()
                    yield (30 + int((i / total) * 60), f"TRANSLATING CUE {i+1}/{total}", None)
            del translation_provider, filter_provider
            self.clear_vram()

        check_cancelled()
        yield (95, "WRITING SUBTITLES", None)
        if target_lang == "source":
            self._moderate_source(transcript, settings)
        self._save_cues('subtitle-output', transcript)
        self.generate_srt(transcript, final_output)

        elapsed = self.format_time(time.time() - start_time)
        log_message = (
            f"COMPLETE ✅\n"
            f"--------------------------\n"
            f"⏱️ Total Time: {elapsed}\n"
            f"📂 Output: {os.path.basename(final_output)}"
        )
        check_cancelled()
        yield (100, log_message, final_output)

    # --- pipeline templates ---
    # The 5 flows a video-dubbing tool can physically support: soft-subtitle
    # attachment isn't a separate template - it's merge_av()'s existing
    # burn_subs=False path (mux the .srt as a real subtitle stream instead
    # of burning pixels), already reachable via video_dub's burn_subtitles
    # param, so it doesn't need its own entry here.
    PIPELINE_TEMPLATES = TEMPLATES

    def run(self, template_id, input_path, params=None):
        """Compile one fixed plan, freeze selections and retain real execution evidence."""
        params = params or {}
        normalize_source_selection(params.get('source_language', 'auto'))
        if params.get('target_lang', 'en') != 'source':
            self._translation_target(params.get('target_lang', 'en'))
        spec = PipelineSpec(template_id, params, default_device=config.DEVICE)
        for warning in spec.to_payload()['warnings']:
            logging.warning(warning)
        registry = self.registry
        old_settings = getattr(self, '_run_settings', None)
        old_manifest = getattr(self, '_manifest', None)
        old_checkpoints = getattr(self, '_checkpoints', None)
        frozen_registry = registry.snapshot()
        frozen_settings = SettingsSnapshot(Settings().all())
        manifest = RunManifest(os.path.join(self.output_dir, 'run_records'), spec, input_path,
                               frozen_registry, frozen_settings)
        self.registry = frozen_registry
        self._run_settings = frozen_settings
        self._manifest = manifest
        from core.stage_checkpoints import StageCheckpoints
        self._checkpoints = StageCheckpoints(Path(self.output_dir) / 'stage_checkpoints',
            manifest, frozen_registry, config.BASE_DIR)
        self.last_manifest_path = str(manifest.path)
        generator = None
        try:
            with bind_manifest(manifest):
                with manifest.operation('source'):
                    manifest.capture_source(input_path)
                methods = {'video_dub': self.process_video_gen,
                           'video_dub_lipsync': self.process_video_gen,
                           'audio_dub': self.process_audio_dub_gen,
                           'subtitle_translate': self.process_subtitle_translate_gen}
                generator = methods[template_id](input_path, **spec.parameters)
                output = None
                for event in generator:
                    if event[2]:
                        output = event[2]
                    yield event
                if not output:
                    raise RuntimeError('Process finished without output.')
                manifest.finish('completed', output=output)
        except BaseException as error:
            manifest.finish('cancelled' if isinstance(error, (GeneratorExit, RenderCancelled)) else 'failed', error=error)
            raise
        finally:
            try:
                close = getattr(generator, 'close', None)
                if callable(close):
                    close()
            finally:
                self.registry = registry
                self._run_settings = old_settings
                self._manifest = old_manifest
                self._checkpoints = old_checkpoints
