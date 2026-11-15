"""Read generated dialogue back with the installed recognizer; flag uncertainty."""
from difflib import SequenceMatcher
import math
import unicodedata


def similarity(expected, observed, language):
    from core.xtts_text import prepare_speech_text
    def normalized(value):
        value = prepare_speech_text(value, language)
        return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold()
                       if c.isalnum() or unicodedata.category(c).startswith('M'))
    left, right = normalized(expected), normalized(observed)
    return SequenceMatcher(None, left, right, autojunk=False).ratio() if left and right else 0.


def verify(voice_track, transcript, provider, language, preserved, manifest):
    from pydub import AudioSegment
    from core.render_context import current_job, check_cancelled, RenderCancelled
    from core.transcription import normalize_transcription
    folder = current_job().workspace/'speech-readback'
    folder.mkdir(exist_ok=True)
    rows, paths = [], []
    for index, cue in enumerate(transcript):
        if index in (preserved or {}) or not cue['text'].strip():
            continue
        check_cancelled()
        from core.speech_timing import dialogue_end
        following = transcript[index+1]['start'] if index+1 < len(transcript) else len(voice_track)/1000
        end = min(len(voice_track)/1000, dialogue_end(cue, following))
        clip = voice_track[round(cue['start']*1000):round(end*1000)]
        path = folder/(str(index)+'.wav')
        padded_ms = math.ceil((len(clip)+1000)/30000)*30000
        (clip+AudioSegment.silent(duration=padded_ms-len(clip))).export(path, format='wav').close()
        rows.append(dict(index=index, cue_id=cue.get('cue_id'), start=cue['start'], end=cue['end'],
                         expected=cue['text']))
        paths.append(str(path))
    try:
        try:
            results = provider.transcribe_takes(paths, language) if paths else []
            if len(results) != len(rows):
                raise ValueError('Speech readback returned an incomplete batch')
        except RenderCancelled:
            raise
        except Exception:
            results = [None]*len(rows)
        for row, path, result in zip(rows, paths, results):
            check_cancelled()
            try:
                if result is None:
                    single = provider.transcribe_takes([path], language)
                    if len(single) != 1:
                        raise ValueError('Speech readback returned an incomplete line')
                    result = single[0]
                observed = ' '.join(cue['text'] for cue in normalize_transcription(result))
            except RenderCancelled:
                raise
            except Exception as error:
                from core.failure_diagnostics import summarize
                row.update(status='needs_review', reason='speech_readback_unavailable', error=summarize(error))
                continue
            score = similarity(row['expected'], observed, language)
            row.update(observed=observed, similarity=round(score, 3),
                       status='needs_review' if score < .55 else 'passed_readback')
        report = dict(status='needs_review' if any(r['status'] == 'needs_review' for r in rows)
                      else 'passed_readback', cues=rows,
                      limitation='Recognition agreement is a screening check, not proof of natural delivery.')
    except RenderCancelled:
        raise
    except Exception as error:
        from core.failure_diagnostics import summarize
        report = dict(status='needs_review', cues=rows, error=summarize(error),
                      reason='speech_readback_unavailable')
    finally:
        release = getattr(provider, 'release', None)
        if release:
            release()
    if manifest:
        manifest.report('batch-intelligibility', report)
    return report
