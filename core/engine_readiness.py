"""Selected-route inspection with optional dependency probes; never load models."""
from pathlib import Path
import shutil
from copy import deepcopy
import os

from core.model_contract import local_contract, cloud_contract
from core.network_policy import require_network_allowed
from core.pipeline_contracts import PipelineSpec
from core.providers.resolve import voice_entry
from core.speech_language import preflight_speech, resolve_speech_language


def inspect(registry, template_id, parameters, verify_runtime=False, xtts_runtime=None, recognition_runtime=None, nllb_runtime=None, m2m100_runtime=None, separation_runtime=None, enhancement_runtime=None):
    if type(verify_runtime) is not bool:
        raise ValueError('Runtime verification must be explicitly enabled or disabled')
    plan = PipelineSpec(template_id, parameters).to_payload()
    params = plan['parameters']
    rows = []
    runtime_results = {}

    def xtts(row):
        selection = xtts_runtime if xtts_runtime is not None else os.environ.get('REFLOW_XTTS_RUNTIME', 'legacy')
        if selection == 'legacy':
            return
        if selection != 'isolated':
            raise ValueError('Choose legacy or isolated XTTS runtime')
        if (params.get('compute_device') or 'cpu') != 'cpu':
            raise ValueError('The isolated XTTS runtime is validated for CPU only')
        from core.xtts_runtime import validate
        selected = validate()
        row['adapter'] = 'xtts'
        row['runtime'] = dict(status='unverified', selection='isolated',
                              identity=selected['identity'], device='cpu')
        row['details'].append('Isolated XTTS recipe, Python bootstrap and installed package metadata checked. '
                              'This is an explicit CPU trial; model loading and speech quality are not tested by this inspection.')

    def runtime(row, adapter, executable, device, artifact_checked=False):
        if not verify_runtime:
            return
        if not executable:
            row['runtime'] = dict(status='unverified')
            row['details'].append('This frozen application uses bundled in-process dependencies. A standalone worker cannot verify that environment.')
            return
        from core.runtime_probe import probe
        from core.runtime_probe_contract import require_route
        device = 'cuda:0' if device == 'cuda' else device
        try:
            require_route(adapter, device)
        except ValueError:
            row['runtime'] = dict(status='unverified')
            row['details'].append('Dependency inspection for this engine/device combination is not implemented. Select CPU or the first supported NVIDIA GPU for a supported check.')
            return
        key = (adapter, str(executable), device)
        if key not in runtime_results:
            runtime_results[key] = probe(adapter, executable, device)
        row['runtime'] = deepcopy(runtime_results[key])
        if row['runtime']['status'] == 'passed':
            row['details'].append('Dependency imports and selected-device arithmetic checked. ' +
                                  ('Local artifact contract checked. ' if artifact_checked else 'Checkpoint contents remain unverified. ') +
                                  'Model loading and output quality remain unverified.')
        elif row['runtime']['status'] == 'failed':
            row['status'] = 'needs_setup'
            row['details'].extend(row['runtime']['problems'])
            row['guidance'] = 'Check this runtime and its selected device. No installation or automatic repair was performed.'
        else:
            row['details'].extend(row['runtime']['details'])

    def builtin(stage, row):
        if stage=='enhancer' and enhancement_runtime=='isolated':
            visual(row)
            return
        from core.python_runtime import worker_python, inprocess_python
        from core.optional_runtime import interpreter
        adapter = {'filter': 'nudenet', 'enhancer': 'gfpgan', 'lipsync': 'wav2lip'}[stage]
        device = params.get('compute_device') or 'cpu'
        executable = interpreter('vision') if stage == 'filter' else None
        executable = executable or (worker_python() if stage == 'lipsync' else inprocess_python())
        if stage == 'filter':
            device = 'cpu'
            row['details'].append('Built-in NudeNet filtering uses CPU execution independently of the dashboard device.')
        row['adapter'] = adapter
        runtime(row, adapter, executable, device)

    def visual(row,model_path=None):
        if (params.get('compute_device') or 'cpu')!='cpu':raise ValueError('Isolated face enhancement supports CPU only')
        from core.visual_runtime import validate,model_contract
        selected=validate();model_contract(model_path)
        row['adapter']='gfpgan'
        row['runtime']=dict(status='unverified',selection='isolated',identity=selected['identity'],device='cpu')
        row['details'].append('Guarded CPU face enhancement recipe and local assets checked; image quality remains unverified.')
        runtime(row,'gfpgan',selected['executable'],'cpu',artifact_checked=True)
        row['runtime'].update(selection='isolated',identity=selected['identity'])

    def recognition(row):
        if recognition_runtime in (None, 'legacy'):
            return
        if recognition_runtime != 'isolated':
            raise ValueError('Choose current or isolated recognition runtime')
        from core.recognition_runtime import validate
        route = validate()
        row['adapter'] = 'faster_whisper'
        row['runtime'] = dict(status='unverified', selection='isolated',
                              identity=route['identity'], device='cpu')
        row['details'].append('Isolated CPU recognition recipe, Python bootstrap and package metadata checked. '
                              'The selected checkpoint is unchanged; model loading and language accuracy remain unverified by inspection.')
        runtime(row, 'faster_whisper', route['executable'], 'cpu')
        row['runtime'].update(selection='isolated', identity=route['identity'])

    def check(stage, label, operation):
        row = dict(stage=stage, label=label, status='unverified', details=[])
        try:
            operation(row)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            row.update(status='needs_setup', details=[str(exc)])
            row['guidance'] = 'Check the selected model and runtime installation in Marketplace. No repair or download was performed.'
        rows.append(row)

    def model(stage, entry, row):
        if not entry:
            row['details'].append('Built-in fallback selected; installation and runtime are not verified here.')
            if stage=='translation' and m2m100_runtime=='isolated':
                from core.m2m100_runtime import validate,model_contract
                route=validate();model_contract()
                row['adapter']='m2m100'
                row['runtime']=dict(status='unverified',selection='isolated',identity=route['identity'],device='cpu')
                row['details'].append('Isolated CPU M2M100 fallback recipe and local assets checked. Ollama discovery and output quality are not tested here.')
                runtime(row,'m2m100',route['executable'],'cpu',artifact_checked=True)
                row['runtime'].update(selection='isolated',identity=route['identity'])
            if stage == 'tts':
                xtts(row)
            if stage == 'stt':
                recognition(row)
            if stage in ('filter', 'enhancer', 'lipsync'):
                builtin(stage, row)
            return
        row['model'] = entry.get('display_name') or entry.get('id') or stage
        if entry.get('status') != 'installed':
            raise ValueError('Selected connection is not installed.')
        kind = entry.get('kind')
        if kind in ('cloud_api', 'local_api'):
            metadata = entry.get('meta') or {}
            cloud_contract(stage, entry.get('api_base_url', ''), entry.get('request_preset') or 'custom',
                           metadata.get(stage + '_request'), metadata.get('voice_id'))
            require_network_allowed(entry.get('api_base_url', ''))
            row['details'].append('API configuration checked. Credentials, service availability and quality were not tested.')
            return
        if kind != 'local_file' or entry.get('request_preset') == 'airllm':
            row['details'].append('This route requires a runtime check when the job starts.')
            return
        if stage == 'voice' and entry.get('request_preset') != 'f5tts':
            path = Path(entry.get('local_path') or '')
            if not path.is_file() or not path.stat().st_size:
                raise ValueError('Selected voice checkpoint is missing or empty.')
            if path.suffix.lower() != '.pth':
                raise ValueError('RVC requires an inference .pth checkpoint.')
            row['details'].append('Voice file exists. RVC checkpoint loading and runtime were not tested.')
            row['adapter'] = 'rvc'
            from core.python_runtime import inprocess_python
            runtime(row, 'rvc', inprocess_python(), params.get('compute_device') or 'cpu')
            return  # local_contract for RVC loads tensor weights; forbidden in this inspection.
        contract = local_contract(stage, entry.get('local_path'), entry.get('request_preset'))
        adapter = contract['adapter']
        if adapter=='gfpgan' and enhancement_runtime=='isolated':
            visual(row,contract['checkpoint_path'])
            return
        executable = None
        runtime_device = 'cuda:0'
        row['adapter'] = adapter
        if adapter == 'xtts':
            xtts(row)
        if stage == 'translation' and plan['input_kind'] == 'subtitle' and params['source_language'] == 'auto' and adapter in ('nllb', 'indictrans2'):
            raise ValueError('Select the source language for subtitle translation; subtitle files cannot detect it from audio.')
        if adapter == 'indictrans2':
            if params['target_lang'] != 'hi':
                raise ValueError('This IndicTrans2 route supports Hindi output only.')
            source = params['source_language']
            if source not in ('en', 'auto'):
                raise ValueError('This IndicTrans2 checkpoint supports English source only.')
            if source == 'auto':
                row['details'].append('English source must be confirmed after recognition; auto is unresolved here.')
            from core.indictrans2_assets import isolated_interpreter
            executable = isolated_interpreter()
        elif adapter == 'whisper_turbo':
            from core.whisper_turbo_assets import isolated_interpreter
            executable = isolated_interpreter()
            row['details'].append('This pinned recognition route uses the first NVIDIA GPU, independently of the dashboard device selection. ' +
                                  ('See the explicit runtime result below for GPU verification.' if verify_runtime else 'GPU availability was not probed.'))
        elif adapter == 'indicf5':
            from core.providers.tts.indicf5_local import load_reference_profile, isolated_interpreter
            metadata = entry.get('meta') or {}
            profile = load_reference_profile(metadata.get('reference_profile'))
            if params.get('user_voice_path'):
                from core.providers.resolve import confirmed_reference
                confirmed_reference(registry, params['user_voice_path'])
            selected_device = metadata.get('speech_device') or 'cpu'
            executable = isolated_interpreter(selected_device)
            runtime_device = 'cuda:0' if selected_device.startswith('cuda') else 'cpu'
            row['details'].append('Speech runtime device: ' + str(metadata.get('speech_device') or 'cpu') + '. This is the selected voice profile device, independently of the dashboard device selection.')
            row['details'].append('Confirmed voice: ' + str(profile.get('voice_name') or row['model']))
        elif adapter in ('f5tts', 'musetalk'):
            from core.optional_runtime import interpreter
            profile = 'f5' if adapter == 'f5tts' else 'musetalk'
            executable = interpreter(profile)
            if not executable:
                raise RuntimeError('Optional ' + profile + ' runtime is unavailable.')
            runtime_device = params.get('compute_device') or 'cpu'
        elif adapter in ('gfpgan', 'wav2lip', 'image_classifier', 'text_classifier'):
            from core.python_runtime import worker_python, inprocess_python
            executable = worker_python() if adapter == 'wav2lip' else inprocess_python()
            runtime_device = params.get('compute_device') or 'cpu'
        row['status'] = 'checked'
        row['details'].append('Local artifact contract checked. Model loading, runtime dependencies, hardware and output quality remain unverified.')
        if adapter == 'nllb' and nllb_runtime == 'isolated':
            from core.nllb_runtime import validate
            route = validate()
            row['runtime'] = dict(status='unverified', selection='isolated', identity=route['identity'], device='cpu')
            row['details'].append('NLLB uses the existing modern CPU environment in a separate translation process; model quality is unverified here.')
            runtime(row, 'nllb', route['executable'], 'cpu', artifact_checked=True)
            row['runtime'].update(selection='isolated', identity=route['identity'])
        if adapter == 'faster_whisper':
            recognition(row)
        if executable or adapter in ('gfpgan', 'image_classifier', 'text_classifier'):
            runtime(row, adapter, executable, runtime_device, artifact_checked=True)

    def inspect_voice(actor, row):
        entry = voice_entry(registry, actor)
        if not entry:
            raise ValueError('Selected voice connection was not found.')
        model('voice', entry, row)

    if plan['input_kind'] != 'subtitle':
        def media(row):
            missing = [name for name in ('ffmpeg', 'ffprobe') if not shutil.which(name)]
            if missing:
                raise RuntimeError('Missing media programs on the application path: ' + ', '.join(missing))
            row.update(status='checked', details=['Media programs found; execution was not tested.'])
        check('preprocess', 'Media preparation', media)
        if params['keep_background']:
            def separation(row):
                if separation_runtime in (None, 'legacy'):
                    row['details'].append('Demucs dependencies, weights and speech removal must be checked during execution.')
                    return
                if separation_runtime != 'isolated':raise ValueError('Unknown separation runtime')
                if (params.get('compute_device') or 'cpu') != 'cpu':raise ValueError('The isolated separation runtime supports CPU only')
                from core.separation_runtime import validate,model_contract
                selected=validate();model_contract()
                row['adapter']='demucs'
                row['runtime']=dict(status='unverified',selection='isolated',identity=selected['identity'],device='cpu')
                row['details'].append('Isolated CPU separation recipe and local model presence checked; separation quality remains unverified.')
                runtime(row,'demucs',selected['executable'],'cpu',artifact_checked=True)
            check('separate', 'Background separation', separation)
        check('stt', 'Recognition', lambda row: model('stt', registry.get_active('stt'), row))
    if 'translation' in plan['stages']:
        check('translation', 'Translation', lambda row: model('translation', registry.get_active('translation'), row))
    moderation = registry.get_active('profanity_filter')
    if moderation:
        check('profanity_filter', 'Text moderation', lambda row: model('profanity_filter', moderation, row))
    if plan['input_kind'] != 'subtitle':
        actors = params['cast_list']

        def speech(row):
            from core.speech_language import actor_uses_f5
            if any(not actor_uses_f5(registry, actor) for actor in actors):
                model('tts', registry.get_active('tts'), row)
            target = params['target_lang']
            if target == 'source' and params['source_language'] == 'auto':
                row['status'] = 'unverified'
                row['details'].append('Speech language is unresolved until recognition completes.')
            else:
                language = resolve_speech_language(target, params['source_language'])
                preflight_speech(registry, actors, language)
                row['details'].append('Selected speech language and cast compatibility checked.')
        check('speech', 'Speech generation', speech)
        for actor in dict.fromkeys(actors):
            if actor != 'CLONED_USER':
                check('voice', 'Voice: ' + actor, lambda row, actor=actor: inspect_voice(actor, row))
        for stage in ('lipsync', 'enhancer', 'filter'):
            if stage in plan['stages']:
                check(stage, {'lipsync': 'Lip sync', 'enhancer': 'Video enhancement', 'filter': 'Visual filtering'}[stage],
                      lambda row, stage=stage: model(stage, registry.get_active(stage), row))
    return dict(schema='reflow.engine-readiness.v1', template_id=template_id,
                status='needs_setup' if any(row['status'] == 'needs_setup' for row in rows) else 'inspection_complete',
                checks=rows, warnings=plan['warnings'], live_checks=False,
                runtime_checks_requested=verify_runtime,
                explanation='Setup inspection only. A completed check does not establish end-to-end readiness.')

