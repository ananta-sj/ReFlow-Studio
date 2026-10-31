"""Review cue identity and original-source provenance, including legacy reads."""
from copy import deepcopy
import math
import re
from core.pipeline_contracts import identify_cues, _identity


def attach(cue, namespace, index, recognized=None):
    original = identify_cues([recognized], namespace=f'{namespace}:{index}')[0] if recognized else identify_cues(
        [dict(start=cue['start'], end=cue['end'], text=cue['source_text'])],
        namespace=f'{namespace}:{index}')[0]
    original.update(source_origin='recognition' if recognized else 'legacy-current-review-snapshot',
                    original_source_known=bool(recognized))
    if not recognized:
        original['translated_text'] = None  # Old records cannot establish raw model output.
    cue['cue_id'] = original['cue_id']
    cue['cue_contract'] = original
    sync(cue, increment=False)


def migrate(manifest):
    for index, cue in enumerate(manifest['cues']):
        if 'cue_contract' not in cue and 'cue_id' not in cue:
            attach(cue, manifest['id'], index)
    validate(manifest['cues'])
    return manifest


def sync(cue, increment=True):
    contract = cue['cue_contract']
    contract.update(text=cue['text'], start=cue['start'], end=cue['end'],
        corrected_source_text=cue['source_text'] if cue['source_text'] != contract['source_text'] else None,
        adapted_text=cue['text'] if cue['text'] != contract.get('translated_text') else None)
    if increment:
        contract['revision'] += 1


def combine(left, right):
    a, b = deepcopy(left['cue_contract']), deepcopy(right['cue_contract'])
    parents = [a['cue_id'], b['cue_id']]
    contract = deepcopy(a)
    contract.update(cue_id='cue-' + _identity(['review-combine', parents]), parent_ids=parents,
        source_text=a['source_text'].strip()+' '+b['source_text'].strip(),
        source_start=a['source_start'], source_end=b['source_end'], revision=0,
        source_fragments=deepcopy(a.get('source_fragments') or [a]) + deepcopy(b.get('source_fragments') or [b]),
        original_source_known=a['original_source_known'] and b['original_source_known'],
        source_origin='combined-review-cues',
        translated_text=(a['translated_text']+' '+b['translated_text'])
            if isinstance(a.get('translated_text'), str) and isinstance(b.get('translated_text'), str) else None)
    left.update(cue_id=contract['cue_id'], cue_contract=contract)
    sync(left, increment=False)


def validate(cues):
    identifiers = set()
    for cue in cues:
        if 'cue_contract' not in cue and 'cue_id' not in cue:
            continue  # Version 1 records are upgraded only in memory on load.
        contract = cue.get('cue_contract')
        if not isinstance(contract, dict):
            raise ValueError('Invalid review cue contract.')
        identifier = contract.get('cue_id')
        if (not isinstance(identifier, str) or not re.fullmatch('cue-[a-f0-9]{24}', identifier)
                or identifier != cue.get('cue_id') or identifier in identifiers):
            raise ValueError('Invalid or duplicate review cue identity.')
        identifiers.add(identifier)
        if contract.get('schema') != 'reflow.cue.v1' or type(contract.get('revision')) is not int or contract['revision'] < 0:
            raise ValueError('Invalid review cue version.')
        if any(contract.get(field) != cue[field] for field in ('start', 'end', 'text')):
            raise ValueError('Review cue contract disagrees with current text or timing.')
        if not isinstance(contract.get('source_text'), str) or not contract['source_text'].strip():
            raise ValueError('Invalid original review source.')
        times = [contract.get(field) for field in ('source_start', 'source_end')]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in times) or not 0 <= times[0] < times[1]:
            raise ValueError('Invalid original review timing.')
        if type(contract.get('original_source_known')) is not bool or not isinstance(contract.get('source_origin'), str):
            raise ValueError('Missing original-source provenance.')
        parents = contract.get('parent_ids')
        if not isinstance(parents, list) or any(not isinstance(item, str) or item == identifier for item in parents):
            raise ValueError('Invalid review cue lineage.')
        if any(contract.get(field) is not None and not isinstance(contract[field], str)
               for field in ('translated_text', 'adapted_text', 'corrected_source_text')):
            raise ValueError('Invalid review text provenance.')
