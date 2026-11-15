"""Persistent character assignments and original-voice references for cue review."""
import uuid

from core.render_context import check_cancelled, current_job


MATCH_STATES = ('confirmed', 'matched', 'insufficient_speech', 'ambiguous', 'mixed_speakers')


def valid_name(name):
    return (isinstance(name, str) and 0 < len(name) <= 64 and name == name.strip()
            and name.isprintable())


def validate(manifest):
    if not manifest.get('speaker_matching'):
        return
    if (manifest['speaker_matching'] is not True or type(manifest.get('speaker_dirty')) is not bool
            or manifest['actor'] != 'CLONED_USER' or not isinstance(manifest.get('speaker_references'), dict)):
        raise ValueError('Invalid character review settings')
    refs = manifest['speaker_references']
    owners = manifest.get('speaker_reference_cues', {})
    if not isinstance(owners, dict) or any(name not in refs or not isinstance(cue_id, str)
                                          for name, cue_id in owners.items()):
        raise ValueError('Invalid saved character reference owners')
    for name, filename in refs.items():
        if not valid_name(name) or not isinstance(filename, str) or filename not in manifest['assets']:
            raise ValueError('Invalid saved character reference')
    for cue in manifest['cues']:
        state = cue.get('speaker_match')
        name = cue.get('speaker')
        if state is not None and (not isinstance(state, str) or state not in MATCH_STATES):
            raise ValueError('Invalid character match state')
        if state in ('confirmed', 'matched'):
            if not valid_name(name):
                raise ValueError('Invalid assigned character')
        elif name is not None:
            raise ValueError('Unresolved cue has a character assignment')
        if not manifest['speaker_dirty'] and (cue.get('accepted') or cue.get('candidate')) and name not in refs:
            raise ValueError('Saved take has no character reference')


def set_speaker(store, identifier, revision, index, name):
    manifest = store.load(identifier, revision)
    if not manifest.get('speaker_matching'):
        raise ValueError('This review uses a single voice.')
    cue = store.cue(manifest, index)
    if not isinstance(name, str) or (name.strip() and not valid_name(name.strip())):
        raise ValueError('Enter a character name of up to 64 characters.')
    name = name.strip()
    if name:
        name = next((item['speaker'] for item in manifest['cues']
                     if item.get('speaker') and item['speaker'].casefold() == name.casefold()), name)
    if name and cue.get('speaker') == name and cue.get('speaker_match') == 'confirmed':
        return store.public(identifier)
    if not name and not cue.get('speaker'):
        return store.public(identifier)
    if name != cue.get('speaker'):
        _clear_takes(cue)
    if name:
        cue.update(speaker=name, speaker_match='confirmed')
    else:
        cue.pop('speaker', None)
        cue.pop('speaker_match', None)
    manifest['speaker_dirty'] = True
    manifest['revision'] += 1
    store.save(manifest, expected_revision=revision)
    return store.public(identifier)


def _clear_takes(cue):
    from core.cue_review import _clear_take_assessment
    cue.update(candidate=None, accepted=None)
    cue.pop('first_pass', None)
    _clear_take_assessment(cue)


def match(store, manifest, progress):
    import numpy as np
    from pydub import AudioSegment
    from core.cue_review import digest
    from core.python_runtime import project_root
    from core.speaker_matching import load_encoder, speech_excerpt, match_excerpt

    if not manifest.get('speaker_matching'):
        raise ValueError('This review uses a single voice.')
    cues = manifest['cues']
    confirmed = [cue for cue in cues if cue.get('speaker_match') == 'confirmed']
    if len({cue['speaker'] for cue in confirmed}) < 2:
        raise ValueError('Confirm a clear line from at least two different characters first.')
    source = store.asset(manifest, 'vocals.wav')
    if digest(source) != manifest['assets']['vocals.wav']:
        raise ValueError('Saved source vocals changed. Prepare a new review.')
    with source.open('rb') as stream:
        audio = AudioSegment.from_file(stream, format='wav')
    excerpts = {}
    for index, cue in enumerate(cues):
        check_cancelled()
        excerpts[index] = speech_excerpt(audio[round(cue['start']*1000):round(cue['end']*1000)])
    progress(10, 'LOADING LOCAL SPEAKER ENCODER')
    encode = load_encoder(project_root() / 'models/xtts/default/model.pth')
    references, best, confirmed_samples = {}, {}, {}
    for index, cue in enumerate(cues):
        check_cancelled()
        clip = excerpts[index]
        if cue.get('speaker_match') != 'confirmed' or clip is None or len(clip) < 1000:
            continue
        name = cue['speaker']
        sample = clip[:6000]
        confirmed_samples[cue['cue_id']] = (name, sample)
        references.setdefault(name, []).append(encode(sample))
        if name not in best or len(sample) > len(best[name][1]):
            best[name] = cue['cue_id'], sample
    if len(references) < 2:
        raise ValueError('Confirm at least one clear line longer than a second for two different characters.')
    for name, vectors in references.items():
        for other, alternatives in references.items():
            if other > name and any(float(np.dot(left, right)) >= .87
                                    for left in vectors for right in alternatives):
                raise ValueError(f'Samples for {name} and {other} sound like the same speaker. Check their confirmed lines.')

    previous_refs = manifest['speaker_references']
    new_refs, owners = {}, {}
    for name, (cue_id, sample) in best.items():
        prior_owner = manifest.get('speaker_reference_cues', {}).get(name)
        if prior_owner in confirmed_samples and confirmed_samples[prior_owner][0] == name:
            cue_id, sample = prior_owner, confirmed_samples[prior_owner][1]
        owners[name] = cue_id
        filename = 'speaker-' + uuid.uuid4().hex + '.wav'
        pending = current_job().workspace / filename
        sample.export(pending, format='wav').close()
        checksum = digest(pending)
        previous = previous_refs.get(name)
        if previous and checksum == manifest['assets'][previous] and digest(store.asset(manifest, previous)) == checksum:
            new_refs[name] = previous
        else:
            current_job().publish(pending, store.asset(manifest, filename))
            manifest['assets'][filename] = checksum
            new_refs[name] = filename

    for index, cue in enumerate(cues):
        check_cancelled()
        previous = cue.get('speaker')
        if cue.get('speaker_match') == 'confirmed':
            name, state = previous, 'confirmed'
        else:
            name, state = match_excerpt(excerpts[index], encode, references)
        if previous != name or previous_refs.get(previous) != new_refs.get(name):
            _clear_takes(cue)
        if name is None:
            cue.pop('speaker', None)
        else:
            cue['speaker'] = name
        cue['speaker_match'] = state
        progress(20 + int(75 * (index+1)/len(cues)), f'MATCHING CHARACTER {index+1}/{len(cues)}')
    manifest['speaker_references'] = new_refs
    manifest['speaker_reference_cues'] = owners
    manifest['speaker_dirty'] = False
    previous_revision = manifest['revision']
    manifest['revision'] += 1
    store.save(manifest, expected_revision=previous_revision)
    remaining = sum(cue.get('speaker') not in new_refs for cue in cues)
    progress(100, f'CHARACTERS MATCHED — {remaining} LINES NEED A CHARACTER OR REFERENCE')


def reference_for(store, manifest, cue=None):
    from core.cue_review import digest

    filename = 'reference.wav'
    if manifest.get('speaker_matching'):
        filename = manifest['speaker_references'].get(cue.get('speaker'))
        if filename is None:
            raise ValueError('Confirm this character and match references before generating the line.')
    path = store.asset(manifest, filename)
    if digest(path) != manifest['assets'][filename]:
        raise ValueError('Review reference audio changed. Prepare a new review.')
    return str(path)
