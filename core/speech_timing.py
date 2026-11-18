"""Natural speech fitting policy and durable measured-overflow evidence."""
import math,uuid

def dialogue_end(cue, next_start=None):
    """Allow a brief natural tail, never fill a long scene pause with speech."""
    end = float(cue['end'])
    if next_start is None:
        return end
    return max(end, min(float(next_start), end+.35))

def bounded_cues(transcript,total_duration):
    """Honor existing ASR rounding tolerance without offering time past the media."""
    from core.transcription import require_media_bounds
    require_media_bounds(transcript,total_duration)
    result=[]
    for cue in transcript:
        bounded=dict(cue,end=min(cue['end'],total_duration))
        if bounded['start']>=bounded['end']:raise ValueError('Speech cue has no time inside the source media')
        result.append(bounded)
    return result

class SpeechTimingReviewRequired(RuntimeError):
    def __init__(self,report):
        self.report=report
        super().__init__(f"Segment {report['index']+1}, voice '{report['actor']}': generated speech cannot fit without cutting words: "
            f"needs {report['measured_seconds']:.3f}s after timing adjustment, available {report['available_seconds']:.3f}s. "
            'Review the wording or cue spacing; the speech speed limit was preserved.'+
            (' The generated take is saved with this run.' if report.get('candidate') else ''))

def speed_for_window(duration_ms,available_ms,language,native_delivery=False):
    if any(not math.isfinite(value) or value<=0 for value in [duration_ms,available_ms]):raise ValueError('Speech durations must be finite and positive')
    if native_delivery:return 1.0
    # Spare time is silence on the source timeline, not a reason to stretch words.
    limit = 1.15 if language == 'hi' else 1.3
    return max(1.0, min(duration_ms/available_ms, limit))

def measured_conflict(manifest,clip,*,index,segment,actor,generated_seconds,available_seconds,speed,native_delivery):
    report=dict(schema='reflow.measured-speech-timing.v1',status='needs_review',index=index,cue_id=segment.get('cue_id'),actor=actor,
        source_text=segment.get('source_text'),text=segment['text'],start=segment['start'],end=segment['end'],
        generated_seconds=generated_seconds,measured_seconds=len(clip)/1000,available_seconds=available_seconds,
        excess_seconds=max(0,len(clip)/1000-available_seconds),speed=speed,native_delivery=native_delivery,
        words_cut=False,auto_rewrite=False,meaning_assessed=False,candidate=None)
    if manifest is not None:
        from core.media_io import _staged_output
        from core.run_manifest import file_identity
        from core.render_context import check_cancelled
        check_cancelled()
        # RLock also serializes the report index during parallel cue failures.
        with manifest.lock:
            path=manifest.folder/('timing-candidate-'+uuid.uuid4().hex+'.wav')
            with _staged_output(str(path)) as pending:clip.export(pending,format='wav').close()
            report['candidate']={**file_identity(path),'retention':'review-evidence','fits':False}
            manifest.report('measured-speech-timing',report)
    return report


def estimate_from_samples(text, samples):
    """Advisory natural duration from independently observed, compatible takes."""
    from statistics import median
    import unicodedata

    def units(value):
        return sum(unicodedata.category(char)[0] in 'LMN' for char in value)

    length = units(text)
    rates = []
    for sample in samples:
        seconds = sample.get('seconds')
        count = units(sample.get('text', ''))
        if (type(seconds) in (int, float) and math.isfinite(seconds)
                and seconds >= .4 and count >= 4):
            rates.append(count / seconds)
    if length < 4 or len(rates) < 3:
        return None
    return dict(estimated_seconds=length / median(rates), sample_count=len(rates),
                basis='observed_natural_takes')
