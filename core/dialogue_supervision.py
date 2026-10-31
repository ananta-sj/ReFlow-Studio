"""Bounded rewrite/review orchestration; model opinions never accept speech."""
from copy import deepcopy
from contextlib import nullcontext
from core.dialogue_adaptation import seconds, numbers
from core.render_context import check_cancelled
from core.dialogue_evidence import PROTOCOL, LEGACY, validate_evidence


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError('Dialogue text must contain 1–4000 characters.')
    return value.strip()


def _warnings(current_text, text, target_language='hi'):
    result = []
    if numbers(current_text) != numbers(text):
        result.append('Numbers differ from the current translation.')
    if target_language == 'hi' and not any('\u0900' <= char <= '\u097f' for char in text):
        result.append('No Devanagari text found for the Hindi target.')
    if target_language == 'en' and (not any(c.isascii() and c.isalpha() for c in text)
            or any(c.isalpha() and not c.isascii() for c in text)):
        result.append('English target contains missing or unexpected alphabetic script; verify names and language.')
    return result


def supervise(provider, writer, reviewer, source_text, current_text, available,
              source_language='en', target_language='hi', manifest=None, review_binding=None, before_request=None,
              measured_take=None):
    """One rewrite query and at most one batch review; retain original wording.

    Writer and reviewer are explicitly supplied services. No provider is
    discovered, installed, substituted or invoked by a normal pipeline run.
    A preserved-meaning opinion is advisory, even when it fits prediction.
    """
    # Validate without changing the exact saved inputs that bind the report.
    _text(source_text)
    _text(current_text)
    available = seconds(available)
    measured = measured_take is not None
    if source_language != 'en' or target_language not in (('en', 'hi') if measured else ('hi',)):
        raise ValueError('Dialogue supervision requires a supported source/target pair.')
    if measured:
        _measured_take(measured_take, available)
    elif (getattr(provider, 'preserves_native_delivery', False) is not True
            or not callable(getattr(provider, 'estimate_duration_seconds', None))):
        raise ValueError('Dialogue supervision requires the native speech estimator.')
    if not callable(getattr(writer, 'rewrite_dialogue', None)) or not callable(getattr(reviewer, 'review_dialogue', None)):
        raise ValueError('Explicit dialogue writer and meaning reviewer are required.')
    check_cancelled()
    original_prediction = None if measured else seconds(provider.estimate_duration_seconds(current_text))
    protocol = PROTOCOL if getattr(reviewer, 'review_protocol', None) == PROTOCOL else LEGACY
    schema_version = (4 if measured else 3) if protocol == PROTOCOL else (2 if measured else 1)
    report = dict(schema=f'reflow.dialogue-supervision.v{schema_version}', status='needs_review',
        source_text=source_text, input_text=current_text, available_seconds=available,
        original_predicted_seconds=original_prediction, source_language=source_language,
        target_language=target_language, candidate_limit=3, request_limit=2,
        writer_requests=0, reviewer_requests=0, auto_rewrite=False,
        human_review_required=True, meaning_review_protocol=protocol, candidates=[])
    if measured:
        report['measured_take'] = deepcopy(measured_take)
    from core.run_manifest import provider_identity
    report['engines'] = {name: provider_identity(engine) for name, engine in
        (('speech', provider), ('writer', writer), ('reviewer', reviewer))}
    if review_binding is not None:
        report['review_binding'] = deepcopy(review_binding)
    if not measured and original_prediction <= available + .001:
        report['status'] = 'fits_prediction'
        report['outcome'] = 'original_fits_prediction'
        return _publish(report, manifest)
    report['writer_requests'] = 1
    with (manifest.operation('dialogue-rewrite', writer, evidence=dict(candidate_limit=3))
            if manifest else nullcontext()):
        if before_request is not None:
            before_request()
        generated = writer.rewrite_dialogue(source_text=source_text, current_text=current_text,
            source_language=source_language, target_language=target_language,
            available_seconds=available, current_predicted_seconds=original_prediction,
            **({'current_measured_seconds': measured_take['seconds']} if measured else {}),
            max_candidates=3)
    check_cancelled()
    if not isinstance(generated, list) or len(generated) > 3:
        raise ValueError('Dialogue writer exceeded its three-candidate budget.')
    seen = {current_text.strip()}
    for raw in generated:
        check_cancelled()
        text = _text(raw)
        if text in seen:
            continue
        seen.add(text)
        predicted = None if measured else seconds(provider.estimate_duration_seconds(text))
        warnings = _warnings(current_text, text, target_language)
        report['candidates'].append(dict(id='candidate-'+str(len(report['candidates'])+1),
            text=text, predicted_seconds=predicted, fits=None if measured else predicted <= available + .001,
            warnings=warnings, meaning_status='not_reviewed', meaning_reasons=[], meaning_evidence=[], approved=False))
    # Never spend a critic query on variants already blocked by objective checks.
    eligible = [c for c in report['candidates'] if (measured or c['fits']) and not c['warnings']]
    if eligible:
        report['reviewer_requests'] = 1
        with (manifest.operation('dialogue-meaning-review', reviewer,
                evidence=dict(candidate_ids=[c['id'] for c in eligible]))
                if manifest else nullcontext()):
            if before_request is not None:
                before_request()
            opinions = reviewer.review_dialogue(source_text=source_text,
                current_text=current_text, source_language=source_language,
                target_language=target_language,
                candidates=deepcopy([dict(id=c['id'], text=c['text']) for c in eligible]))
        check_cancelled()
        if not isinstance(opinions, list) or len(opinions) != len(eligible):
            raise ValueError('Meaning reviewer must return exactly one opinion per candidate.')
        expected = {c['id']: c for c in eligible}
        observed = set()
        for opinion in opinions:
            if not isinstance(opinion, dict):
                raise ValueError('Invalid meaning review opinion.')
            identifier = opinion.get('id')
            status = opinion.get('status')
            reasons = opinion.get('reasons')
            if (not isinstance(identifier, str) or identifier not in expected or identifier in observed
                    or status not in ('preserved', 'changed', 'uncertain')
                    or not isinstance(reasons, list) or not 1 <= len(reasons) <= 8
                    or any(not isinstance(r, str) or not r.strip() or len(r) > 1000 for r in reasons)):
                raise ValueError('Invalid or unbound meaning review opinion.')
            observed.add(identifier)
            evidence = validate_evidence(status, opinion.get('evidence'), source_text, expected[identifier]['text']) if protocol == PROTOCOL else []
            expected[identifier].update(meaning_status=status, meaning_reasons=list(reasons), meaning_evidence=evidence)
    report['outcome'] = 'proposals_need_human_review' if any(
        c['meaning_status'] == 'preserved' for c in report['candidates']) else ('no_reviewed_alternative' if measured else 'no_reviewed_fitting_alternative')
    return _publish(report, manifest)


def _publish(report, manifest):
    if manifest is not None:
        manifest.report('dialogue-supervision', report)
    return report


def _measured_take(take, available):
    import re
    if (not isinstance(take, dict) or set(take) != {'file', 'seconds', 'fits', 'sha256'}
            or not isinstance(take['file'], str) or re.fullmatch(r'take-[a-f0-9]{32}\.wav', take['file']) is None
            or not isinstance(take['sha256'], str) or re.fullmatch('[a-f0-9]{64}', take['sha256']) is None
            or take['fits'] is not False or seconds(take['seconds']) <= available):
        raise ValueError('Measured assistance requires an intact overflowing review take.')


def validate_saved(cue, configuration):
    """Validate embedded evidence without treating a model opinion as approval."""
    report = cue.get('dialogue_supervision')
    if report is None:
        return
    measured = isinstance(report, dict) and report.get('schema') in ('reflow.dialogue-supervision.v2', 'reflow.dialogue-supervision.v4')
    protocol = report.get('meaning_review_protocol', LEGACY) if isinstance(report, dict) else LEGACY
    grounded_schema = isinstance(report, dict) and report.get('schema') in ('reflow.dialogue-supervision.v3', 'reflow.dialogue-supervision.v4')
    if (not isinstance(report, dict) or report.get('schema') not in tuple(f'reflow.dialogue-supervision.v{i}' for i in (1, 2, 3, 4))
            or report.get('source_text') != cue['source_text'] or report.get('input_text') != cue['text']
            or report.get('available_seconds') != cue['available_seconds']
            or report.get('source_language') != 'en' or report.get('target_language') not in (('en','hi') if measured else ('hi',))
            or report.get('human_review_required') is not True or report.get('auto_rewrite') is not False
            or type(report.get('candidate_limit')) is not int or report['candidate_limit'] != 3
            or type(report.get('request_limit')) is not int or report['request_limit'] != 2
            or protocol not in (PROTOCOL, LEGACY) or grounded_schema != (protocol == PROTOCOL)):
        raise ValueError('Invalid or stale saved dialogue supervision.')
    if measured:
        _measured_take(report.get('measured_take'), cue['available_seconds'])
        if report['measured_take'] != cue.get('candidate') or report.get('original_predicted_seconds') is not None:
            raise ValueError('Measured dialogue evidence changed; request a new review.')
    binding = report.get('review_binding')
    if (not isinstance(binding, dict) or binding.get('cue_id') != cue['cue_id']
            or binding.get('configuration') != configuration
            or type(binding.get('input_revision')) is not int or binding['input_revision'] <= 0
            or not isinstance(binding.get('run_id'), str) or len(binding['run_id']) != 32
            or any(c not in '0123456789abcdef' for c in binding['run_id'])):
        raise ValueError('Invalid dialogue supervision provenance.')
    original = None if measured else seconds(report.get('original_predicted_seconds'))
    engines = report.get('engines')
    if not isinstance(engines, dict) or any(not isinstance(engines.get(role), dict)
            or not isinstance(engines[role].get('adapter'), str) for role in ('speech', 'writer', 'reviewer')):
        raise ValueError('Missing dialogue supervision engine evidence.')
    writer, reviewer = report.get('writer_requests'), report.get('reviewer_requests')
    if type(writer) is not int or type(reviewer) is not int or writer not in (0, 1) or reviewer not in (0, 1):
        raise ValueError('Invalid dialogue request budget.')
    candidates = report.get('candidates')
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ValueError('Invalid dialogue supervision candidate budget.')
    seen = set()
    texts = {cue['text'].strip()}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError('Invalid dialogue supervision candidate.')
        text = _text(candidate.get('text'))
        identifier = candidate.get('id')
        predicted = candidate.get('predicted_seconds') if measured else seconds(candidate.get('predicted_seconds'))
        warnings, reasons = candidate.get('warnings'), candidate.get('meaning_reasons')
        status = candidate.get('meaning_status')
        evidence = candidate.get('meaning_evidence', [])
        if protocol == PROTOCOL and status != 'not_reviewed':
            validate_evidence(status, evidence, cue['source_text'], text)
        elif evidence != []:
            raise ValueError('Unchecked or unreviewed meaning evidence cannot be presented as grounded.')
        if (identifier != 'candidate-'+str(len(seen)+1) or identifier in seen or text in texts
                or candidate.get('approved') is not False
                or (measured and (predicted is not None or candidate.get('fits') is not None))
                or (not measured and (type(candidate.get('fits')) is not bool or candidate['fits'] != (predicted <= cue['available_seconds']+.001)))
                or not isinstance(warnings, list) or len(warnings) > 8
                or any(not isinstance(w, str) or not w.strip() or len(w) > 1000 for w in warnings)
                or warnings != _warnings(cue['text'], text, report['target_language'])
                or status not in ('not_reviewed', 'preserved', 'changed', 'uncertain')
                or not isinstance(reasons, list) or len(reasons) > 8
                or any(not isinstance(r, str) or not r.strip() or len(r) > 1000 for r in reasons)):
            raise ValueError('Invalid saved dialogue candidate assessment.')
        if ((status == 'not_reviewed' and reasons) or
                (status != 'not_reviewed' and (not reasons or not reviewer or warnings or (not measured and not candidate['fits'])))):
            raise ValueError('Unbound saved meaning-review opinion.')
        seen.add(identifier)
        texts.add(text)
    if not measured and original <= cue['available_seconds']+.001:
        valid = (report.get('status') == 'fits_prediction' and report.get('outcome') == 'original_fits_prediction'
                 and writer == reviewer == 0 and not candidates)
    else:
        eligible = [c for c in candidates if (measured or c['fits']) and not c['warnings']]
        outcome = 'proposals_need_human_review' if any(c['meaning_status'] == 'preserved' for c in candidates) else ('no_reviewed_alternative' if measured else 'no_reviewed_fitting_alternative')
        valid = (report.get('status') == 'needs_review' and report.get('outcome') == outcome and writer == 1
                 and reviewer == int(bool(eligible)) and all(c['meaning_status'] != 'not_reviewed' for c in eligible))
    if not valid:
        raise ValueError('Invalid saved dialogue supervision outcome.')
