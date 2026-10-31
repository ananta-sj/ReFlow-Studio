"""Speech-window assessments and bounded, explicitly unapproved wording proposals."""
import math
import re
import unicodedata
from contextlib import nullcontext
from core.render_context import check_cancelled


class DialogueReviewRequired(RuntimeError):
    def __init__(self, report):
        self.report = report
        conflicts = [cue for cue in report['cues'] if cue['status'] == 'needs_review']
        first = conflicts[0]
        super().__init__(f"Segment {first['index']+1}: native speech is predicted to need "
            f"{first['predicted_seconds']:.3f}s but only {first['available_seconds']:.3f}s is available. "
            f"{len(conflicts)} of {len(report['cues'])} lines need wording or timing review before speech generation.")


def seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError('Speech timing estimate must be finite and positive.')
    return value


def assess(provider, transcript, cast, manifest=None, *, total_duration=None):
    supported = (getattr(provider, 'preserves_native_delivery', False) is True
        and callable(getattr(provider, 'estimate_duration_seconds', None))
        and all(actor == 'CLONED_USER' for actor in cast))
    report = dict(schema='reflow.dialogue-report.v1', status='not_assessed',
        policy='native-speed-preserved', meaning_assessed=False, auto_rewrite=False, cues=[])
    if not supported:
        report['reason'] = 'Selected speech route has no verified native duration estimator.'
        return report
    if total_duration is not None:
        seconds(total_duration)
        from core.speech_timing import bounded_cues
        transcript=bounded_cues(transcript,total_duration)
    for index, cue in enumerate(transcript):
        check_cancelled()
        following = transcript[index+1]['start'] if index+1 < len(transcript) else max(cue['end'],total_duration or cue['end'])
        available = seconds(max(cue['end']-cue['start'], following-cue['start']))
        operation = manifest.operation('timing-preflight', provider, evidence=dict(
            cue_id=cue.get('cue_id'), available_seconds=available)) if manifest else nullcontext()
        with operation as observation:
            predicted = seconds(provider.estimate_duration_seconds(cue['text']))
            if observation is not None:
                observation['predicted_seconds'] = predicted
        report['cues'].append(dict(cue_id=cue.get('cue_id'), index=index, source_text=cue.get('source_text'),
            translated_text=cue.get('translated_text'), text=cue['text'], start=cue['start'], end=cue['end'],
            available_seconds=available, predicted_seconds=predicted,
            excess_seconds=max(0, predicted-available),
            status='fits_prediction' if predicted <= available+.001 else 'needs_review'))
    report['status'] = 'needs_review' if any(c['status']=='needs_review' for c in report['cues']) else 'fits_prediction'
    return report


def numbers(text):
    return re.findall(r'\d+(?:[.,]\d+)*', unicodedata.normalize('NFKC', text))


def propose(provider, translator, source_text, current_text, target_name, source_language, available):
    """One model request, at most three complete candidates; no automatic acceptance."""
    seconds(available)
    if any(not isinstance(text,str) or not text.strip() or len(text)>4000 for text in (source_text,current_text)):
        raise ValueError('Dialogue proposals require 1–4000 characters of source and target text.')
    if getattr(provider, 'preserves_native_delivery', False) is not True:
        raise ValueError('Wording suggestions require the selected native Hindi speech estimator.')
    if not callable(getattr(translator, 'suggest_dialogue', None)):
        raise ValueError('The selected translation engine does not support bounded wording alternatives.')
    check_cancelled()
    candidates = translator.suggest_dialogue(source_text, target_name, source_language=source_language, max_candidates=3)
    if not isinstance(candidates, list) or len(candidates)>3:
        raise ValueError('Translation engine exceeded the three-candidate proposal budget.')
    result = dict(schema='reflow.dialogue-options.v1', available_seconds=available,
        input_text=current_text, source_text=source_text, model_requests=1, candidate_limit=3,
        meaning_assessed=False, human_review_required=True, candidates=[])
    seen={current_text.strip()}
    for text in candidates:
        check_cancelled()
        if not isinstance(text, str) or not text.strip() or len(text)>4000:
            raise ValueError('Invalid wording alternative.')
        text=text.strip()
        if text in seen:
            continue
        seen.add(text)
        predicted=seconds(provider.estimate_duration_seconds(text))
        warnings=[]
        if numbers(current_text)!=numbers(text):
            warnings.append('Numbers differ from the current translation; verify the source carefully.')
        result['candidates'].append(dict(text=text, predicted_seconds=predicted,
            fits=predicted<=available+.001, warnings=warnings, approved=False))
    result['candidates'].sort(key=lambda c:(not c['fits'], bool(c['warnings']), c['predicted_seconds']))
    result['status']='proposals_need_review' if result['candidates'] else 'no_distinct_alternative'
    from core.run_manifest import provider_identity
    result['translation_engine']=provider_identity(translator)
    result['speech_engine']=provider_identity(provider)
    return result


def validate_options(cue):
    options=cue.get('dialogue_options')
    if options is None:
        return
    if (not isinstance(options, dict) or options.get('schema')!='reflow.dialogue-options.v1'
            or options.get('input_text')!=cue['text'] or options.get('source_text')!=cue['source_text']
            or options.get('available_seconds')!=cue['available_seconds']
            or options.get('human_review_required') is not True or options.get('meaning_assessed') is not False
            or options.get('model_requests')!=1 or options.get('candidate_limit')!=3):
        raise ValueError('Invalid or stale dialogue alternatives.')
    candidates=options.get('candidates')
    if not isinstance(candidates,list) or len(candidates)>3:
        raise ValueError('Dialogue alternative budget exceeded.')
    for candidate in candidates:
        if (not isinstance(candidate,dict) or not isinstance(candidate.get('text'),str)
                or not candidate['text'].strip() or len(candidate['text'])>4000
                or candidate.get('approved') is not False or not isinstance(candidate.get('warnings'),list)
                or any(not isinstance(w,str) for w in candidate['warnings'])):
            raise ValueError('Invalid dialogue alternative.')
        predicted=seconds(candidate.get('predicted_seconds'))
        if type(candidate.get('fits')) is not bool or candidate['fits']!=(predicted<=options['available_seconds']+.001):
            raise ValueError('Invalid dialogue alternative timing.')
