import os
import math
from pydub import AudioSegment, effects
from pydub.silence import detect_nonsilent


def load_playable_audio(path):
    """Decode a real nonempty clip; file existence alone is not success."""
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"Missing or empty audio: {path}")
    try:
        with open(path, 'rb') as audio_file:
            clip = AudioSegment.from_file(audio_file)
    except Exception as exc:
        raise RuntimeError(f"Audio could not be decoded: {path}: {exc}") from exc
    if len(clip) <= 0:
        raise RuntimeError(f"Audio has no playable samples: {path}")
    return clip


def load_speech_audio(path):
    """Generated dialogue must contain signal; silent backgrounds remain valid."""
    clip = load_playable_audio(path)
    if clip.max == 0:
        raise RuntimeError(f'Generated speech is digitally silent: {path}')
    return clip

class AudioEngineer:
    def __init__(self):
        pass

    def clean_reference_audio(self, input_path, output_path):
        """
        Prepares the reference audio for the AI.
        Removes silence, normalizes volume, and filters out low rumble.
        """
        if not os.path.exists(input_path): return input_path

        print(f"[AUDIO FX] 🧼 Scrubbing reference audio: {os.path.basename(input_path)}")
        audio = load_playable_audio(input_path)

        # 1. Convert to Mono (AI prefers mono reference)
        audio = audio.set_channels(1)

        # 2. High Pass Filter (Removes hum/rumble below 80Hz)
        audio = audio.high_pass_filter(80)

        # 3. Smart Silence Removal (Trims start/end silence)
        # This prevents the AI from learning "silence" as part of the voice
        ranges = detect_nonsilent(audio, min_silence_len=500, silence_thresh=audio.dBFS-16)
        if ranges:
            start = ranges[0][0]
            end = ranges[-1][1]
            audio = audio[start:end]

        # 4. Compression & Normalization
        audio = effects.normalize(audio)
        
        audio.export(output_path, format="wav").close()
        return output_path

    def master_voice_segment(self, segment_path):
        """
        Post-processes the AI generated line to sound punchy and clear.
        """
        if not os.path.exists(segment_path): return
        
        audio = load_playable_audio(segment_path)

        # 1. Mild Compression (Makes quiet parts louder)
        audio = effects.compress_dynamic_range(audio, threshold=-20.0, ratio=2.5, attack=5.0, release=50.0)

        # 2. Slight Treble Boost (Adds clarity/crispness)
        # Pydub doesn't have a simple EQ, so we cheat by overlaying a high-pass copy slightly
        treble = audio.high_pass_filter(2000).apply_gain(-4)
        # Integer PCM overlay saturates before later normalization can repair
        # it. Reserve enough headroom for both signals BEFORE summing them.
        combined_peak_bound = audio.max + treble.max
        if combined_peak_bound:
            headroom_db = max(0.0, 20 * math.log10(
                combined_peak_bound / audio.max_possible_amplitude) + 1.0)
            audio = audio.apply_gain(-headroom_db)
            treble = treble.apply_gain(-headroom_db)
        audio = effects.normalize(audio.overlay(treble), headroom=1.0)

        from core.loudness import normalize_voice_loudness
        from core.media_io import _staged_output
        with _staged_output(segment_path) as pending:
            audio.export(pending, format="wav").close()
            result = normalize_voice_loudness(pending)
            load_playable_audio(pending)
        return result

    def dynamic_mix(self, voice_track, bg_track, ducking_db=-8, active_ducking_db=-24):
        """
        Mixes voice and background.
        'Ducks' (lowers) the background volume automatically when the voice is speaking.

        active_ducking_db (much stronger than the idle ducking_db) applies
        specifically during the new voice_track's actual speech ranges.
        keep_background's "background" track isn't pure music/ambience -
        it's whatever Demucs' vocal-separation model didn't classify as
        vocals, which for narration-style content (a documentary
        presenter over street noise, not a singer over a mix) routinely
        still contains an audible, imperfectly-removed trace of the
        *original* narration. A single flat reduction across the whole
        track wasn't enough to mask that residue specifically during the
        moments the new dub is also speaking - reported directly as
        "the original and the Hindi narration are both audible, out of
        order". Real per-range ducking (a true implementation of what
        the previous flat-reduction version's own comment described as
        a temporary stand-in) pushes the background dramatically further
        down only where it would otherwise compete with the new line,
        while leaving genuine ambience closer to its natural level during
        actual silence.
        """
        # Ensure tracks are same length
        if len(bg_track) < len(voice_track):
            diff = len(voice_track) - len(bg_track)
            silence = AudioSegment.silent(duration=diff)
            bg_track = bg_track + silence
        else:
            bg_track = bg_track[:len(voice_track)]

        if voice_track.dBFS == float("-inf"):
            # Nothing was ever actually dubbed (e.g. every segment got
            # dropped) - no speech to duck around, fall back to the old
            # flat reduction rather than feeding an all-silent track's
            # -inf dBFS into detect_nonsilent's threshold math.
            return voice_track.overlay(bg_track.apply_gain(ducking_db))

        speech_ranges = detect_nonsilent(
            voice_track, min_silence_len=200, silence_thresh=voice_track.dBFS - 16
        )

        bg_out = AudioSegment.silent(duration=0)
        cursor = 0
        for start, end in speech_ranges:
            if start > cursor:
                bg_out += bg_track[cursor:start].apply_gain(ducking_db)
            bg_out += bg_track[start:end].apply_gain(active_ducking_db)
            cursor = end
        if cursor < len(bg_track):
            bg_out += bg_track[cursor:].apply_gain(ducking_db)

        # Integer PCM overlay clips irreversibly before export. Reserve enough
        # space for both signals; a later normalization cannot repair saturation.
        voice_track, bg_out = AudioSegment._sync(voice_track, bg_out)
        peak_bound = voice_track.max + bg_out.max
        if peak_bound > voice_track.max_possible_amplitude:
            gain = -20 * math.log10(peak_bound / voice_track.max_possible_amplitude) - .1
            voice_track = voice_track.apply_gain(gain)
            bg_out = bg_out.apply_gain(gain)
        final_mix = voice_track.overlay(bg_out)

        return final_mix
