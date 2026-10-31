"""Feature-scoped dependency checks before extraction or expensive synthesis."""
import importlib
import os

from core.optional_runtime import interpreter
from core.providers.resolve import voice_entry
from core.model_contract import local_contract
from core.network_policy import require_network_allowed


def _engine(module, profile=None):
    if profile and interpreter(profile):
        return
    try:
        importlib.import_module(module)
    except Exception as exc:
        detail = f' Install the optional {profile} runtime.' if profile else ' Repair this feature’s runtime dependencies.'
        raise RuntimeError(f'Feature engine {module} is unavailable: {exc}.{detail}') from exc


def _selection(entry):
    if not entry:
        return
    if entry.get('kind') in ('cloud_api', 'local_api'):
        require_network_allowed(entry.get('api_base_url', ''))
    elif entry.get('request_preset') != 'airllm':
        local_contract(entry['stage_type'], entry.get('local_path'), entry.get('request_preset'))


def preflight(registry, params, template):
    active = {stage: registry.get_active(stage) if registry else None for stage in
              ('stt', 'tts', 'translation', 'profanity_filter', 'lipsync', 'enhancer', 'filter')}
    stages = ['translation'] if params.get('lang', 'en') != 'source' else []
    if 'translation' in stages:
        translation = active['translation']
        if not translation and params.get('m2m100_runtime')=='isolated':
            from core.m2m100_runtime import validate,model_contract
            validate();model_contract()
        if translation and translation.get('request_preset') == 'airllm':
            _engine('airllm')
        elif translation and translation.get('kind') == 'local_file':
            contract = local_contract('translation', translation.get('local_path'), translation.get('request_preset'))
            if contract['adapter'] == 'indictrans2':
                from core.indictrans2_assets import isolated_interpreter
                isolated_interpreter()
                if params.get('lang') != 'hi':
                    raise ValueError('This IndicTrans2 route supports Hindi output only; select NLLB for other languages.')
            elif contract['adapter'] == 'nllb' and params.get('nllb_runtime') == 'isolated':
                from core.nllb_runtime import validate
                validate()
            else:
                _engine('transformers')
    if active['profanity_filter']:
        stages.append('profanity_filter')
    if template != 'subtitle_translate':
        stages.append('stt')
        _selection(active['stt'])
        if not active['stt'] or active['stt'].get('kind') == 'local_file':
            if active['stt'] and active['stt'].get('request_preset') == 'whisper_turbo':
                from core.whisper_turbo_assets import isolated_interpreter
                isolated_interpreter()
            else:
                selection = params.get('recognition_runtime') or 'legacy'
                if selection == 'isolated':
                    from core.recognition_runtime import validate
                    validate()
                elif selection == 'legacy':
                    _engine('faster_whisper')
                else:
                    raise ValueError('Unknown recognition runtime selection')
        if params.get('keep_bg', True):
            if params.get('separation_runtime', 'legacy') == 'isolated':
                if (params.get('compute_device') or 'cpu') != 'cpu':
                    raise ValueError('The isolated separation runtime supports CPU only')
                from core.separation_runtime import validate, model_contract
                validate(); model_contract()
            elif params.get('separation_runtime') in (None, 'legacy'):
                _engine('demucs.separate')
            else:
                raise ValueError('Unknown separation runtime selection')
        actors = params.get('cast_list') or [params.get('voice', 'CLONED_USER')]
        needs_tts = False
        for actor in actors:
            entry = voice_entry(registry, actor) if actor != 'CLONED_USER' else None
            _selection(entry)
            f5 = entry and entry.get('request_preset') == 'f5tts' and entry.get('kind') == 'local_file'
            needs_tts |= not f5
            if f5:
                _engine('f5_tts.api', 'f5')
            elif actor != 'CLONED_USER' and (not entry or entry.get('kind') == 'local_file'):
                _engine('rvc_python.infer')
        if needs_tts:
            stages.append('tts')
            if not active['tts'] or active['tts'].get('kind') == 'local_file':
                entry = active['tts']
                contract = local_contract('tts', entry.get('local_path'), entry.get('request_preset')) if entry else None
                if contract and contract['adapter'] == 'indicf5':
                    from core.providers.tts.indicf5_local import load_reference_profile, isolated_interpreter
                    meta = entry.get('meta') or {}
                    load_reference_profile(meta.get('reference_profile'))
                    isolated_interpreter(meta.get('speech_device') or 'cpu')
                else:
                    runtime = params.get('xtts_runtime', 'legacy')
                    if runtime == 'isolated':
                        device = params.get('compute_device') or 'cpu'
                        if device.startswith('other:'):
                            device = 'cpu'
                        if device != 'cpu':
                            raise ValueError('The isolated XTTS runtime supports CPU only; select CPU for this job.')
                        from core.xtts_runtime import validate
                        validate()
                    elif runtime in (None, 'legacy'):
                        _engine('TTS.tts.configs.xtts_config')
                        _engine('TTS.tts.models.xtts')
                    else:
                        raise ValueError('Unknown XTTS runtime selection')
    if template in ('video_dub', 'video_dub_lipsync'):
        for flag, stage, module, profile in (
            ('enhance', 'enhancer', 'gfpgan', None), ('content_filter', 'filter', 'nudenet', 'vision'),
            ('lipsync', 'lipsync', 'face_alignment', 'musetalk')):
            if not params.get(flag):
                continue
            stages.append(stage)
            entry = active[stage]
            if entry and entry.get('kind') in ('cloud_api', 'local_api'):
                continue
            if stage=='enhancer' and params.get('enhancement_runtime') not in (None,'legacy','isolated'):raise ValueError('Unknown face enhancement runtime')
            if stage == 'enhancer' and params.get('enhancement_runtime')=='isolated':
                if params.get('compute_device') not in (None,'cpu'):raise ValueError('Isolated face enhancement supports CPU only')
                from core.visual_runtime import validate,model_contract
                validate();model_contract(entry.get('local_path') if entry else None)
            elif stage == 'filter' and entry and entry.get('request_preset') == 'image_classifier':
                _engine('transformers')
            elif stage == 'lipsync' and (not entry or os.path.isfile(entry.get('local_path') or '')):
                _engine('torch')  # Wav2Lip uses vendored detection code.
            else:
                _engine(module, profile)
    for stage in set(stages):
        _selection(active[stage])
