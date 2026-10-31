"""Import/device smoke checks only: no checkpoint construction or inference."""
import importlib
from importlib import metadata
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.runtime_probe_contract import ROUTES, require_route

ADAPTERS = set(ROUTES)


def inspect(adapter, device, progress=None):
    require_route(adapter, device)
    report = dict(schema='reflow.runtime-probe.v1', adapter=adapter, device=device,
                  status='failed', versions={}, problems=[], model_loaded=False)
    def mark(phase):
        report['phase'] = phase
        if progress:
            progress({**report, 'status': 'checking'})
    try:
        if adapter=='gfpgan' and Path(sys.executable).parent.name=='visual-candidate':
            from core.visual_runtime import validate
            selected=validate()
            if Path(sys.executable).resolve()!=Path(selected['executable']).resolve():raise RuntimeError('Visual probe started in the wrong interpreter')
            mark('guarded visual imports')
            from core.visual_imports import guarded_imports
            with guarded_imports():
                importlib.import_module('gfpgan')
            torch=importlib.import_module('torch')
            torch.set_num_threads(2)
            if device!='cpu' or not bool(torch.all(torch.ones((2,2))@torch.ones((2,2))==2)):raise RuntimeError('Visual CPU arithmetic/device mismatch')
            report['versions']['torch']=str(torch.__version__)
            report.update(status='passed',phase='complete',runtime_identity=selected['identity'],training_launchers_disabled=True)
            return report
        if adapter=='m2m100':
            from core.m2m100_runtime import validate
            route=validate()
            if Path(sys.executable).resolve()!=Path(route['executable']).resolve():
                raise RuntimeError('M2M100 probe started in the wrong runtime')
            for name in ('torch','transformers','sentencepiece','tokenizers'):
                mark(name+' import');module=importlib.import_module(name)
                if not Path(module.__file__).resolve().is_relative_to(Path(route['profile'])):
                    raise RuntimeError(name+' resolved outside the translation runtime')
                report['versions'][name]=str(getattr(module,'__version__','unknown'))
            from transformers import M2M100Tokenizer,M2M100ForConditionalGeneration
            torch=importlib.import_module('torch')
            if torch.__version__!='2.14.1+cpu' or not bool(torch.all(torch.ones((2,2))@torch.ones((2,2))==2)):
                raise RuntimeError('M2M100 CPU runtime arithmetic/version mismatch')
            report.update(status='passed',phase='complete',runtime_identity=route['identity'])
            return report
        if adapter == 'nllb':
            from core.nllb_runtime import validate
            route = validate()
            if Path(sys.executable).resolve() != Path(route['executable']).resolve():
                raise RuntimeError('NLLB probe started in the wrong interpreter')
            for name in ('torch', 'transformers', 'tokenizers', 'safetensors'):
                mark(name+' import')
                module = importlib.import_module(name)
                if not Path(module.__file__).resolve().is_relative_to(Path(route['profile'])):
                    raise RuntimeError(name+' resolved outside the NLLB CPU runtime')
                report['versions'][name] = str(getattr(module, '__version__', 'unknown'))
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            torch = importlib.import_module('torch')
            if not bool(torch.all(torch.ones((2, 2)) @ torch.ones((2, 2)) == 2)):
                raise RuntimeError('NLLB CPU arithmetic failed')
            report.update(status='passed', phase='complete', runtime_identity=route['identity'])
            return report
        if adapter == 'faster_whisper':
            from core.recognition_runtime import validate
            route = validate()
            if Path(sys.executable).resolve() != Path(route['executable']).resolve():
                raise RuntimeError('Recognition probe is running in the wrong interpreter')
            for name in ('faster_whisper', 'ctranslate2', 'av', 'onnxruntime', 'numpy', 'tokenizers'):
                mark(name+' import')
                module = importlib.import_module(name)
                if not Path(module.__file__).resolve().is_relative_to(Path(route['profile'])):
                    raise RuntimeError(name+' resolved outside the selected recognition runtime')
                report['versions'][name] = str(getattr(module, '__version__', 'unknown'))
            from core.recognition_compat import apply
            apply()
            numpy = importlib.import_module('numpy')
            ort = importlib.import_module('onnxruntime')
            if 'CPUExecutionProvider' not in ort.get_available_providers():
                raise RuntimeError('Recognition ONNX CPU execution provider is unavailable')
            if not bool(numpy.all(numpy.ones((2, 2)) @ numpy.ones((2, 2)) == 2)):
                raise RuntimeError('Recognition CPU arithmetic failed')
            report.update(status='passed', phase='complete', runtime_identity=route['identity'])
            return report
        if adapter == 'nudenet':
            for name in ('numpy', 'cv2', 'onnxruntime', 'nudenet'):
                mark(name + ' import')
                module = importlib.import_module(name)
                report['versions'][name] = str(getattr(module, '__version__', metadata.version('nudenet') if name == 'nudenet' else 'unknown'))
            numpy = importlib.import_module('numpy')
            ort = importlib.import_module('onnxruntime')
            if 'CPUExecutionProvider' not in ort.get_available_providers():
                raise RuntimeError('ONNX Runtime CPU execution provider is unavailable')
            report['execution_providers'] = ort.get_available_providers()
            if not bool(numpy.all(numpy.ones((2, 2)) @ numpy.ones((2, 2)) == 2)):
                raise RuntimeError('CPU arithmetic check failed')
            report.update(status='passed', phase='complete')
            return report
        mark('torch import')
        torch = importlib.import_module('torch')
        report['versions']['torch'] = torch.__version__
        expected = '2.9.1+cu128' if device == 'cuda:0' else '2.9.1+cpu'
        if adapter in ('whisper_turbo', 'indictrans2', 'indicf5') and torch.__version__ != expected:
            raise RuntimeError('This pinned route requires PyTorch ' + expected)
        runtime = Path(sys.executable).resolve().parent
        # IndicTrans2 explicitly shares CUDA packages with the existing GPU profile.
        torch_runtime = runtime.parent / 'indicf5-gpu-evaluation' if adapter == 'indictrans2' else runtime
        report['torch_origin'] = str(Path(torch.__file__).resolve())
        if not Path(torch.__file__).resolve().is_relative_to(torch_runtime):
            raise RuntimeError('PyTorch resolved outside the selected isolated runtime')
        if adapter in ('whisper_turbo', 'indictrans2'):
            mark('transformers imports')
            expected = '5.18.0' if adapter == 'whisper_turbo' else '4.51.3'
            transformers = importlib.import_module('transformers')
            report['versions']['transformers'] = transformers.__version__
            if transformers.__version__ != expected:
                raise RuntimeError('This pinned route requires Transformers ' + expected)
            names = ('AutoProcessor', 'AutoModelForSpeechSeq2Seq', 'StoppingCriteria') if adapter == 'whisper_turbo' else ('AutoTokenizer', 'AutoModelForSeq2SeqLM', 'StoppingCriteria')
            for name in names:
                mark('transformers.' + name)
                getattr(transformers, name)
        elif adapter == 'indicf5':
            report['versions']['f5-tts'] = metadata.version('f5-tts')
            if report['versions']['f5-tts'] != '0.1.0':
                raise RuntimeError('IndicF5 requires f5-tts 0.1.0')
            for name in ('torchaudio', 'soundfile', 'safetensors.torch', 'vocos', 'f5_tts.model', 'f5_tts.infer.utils_infer'):
                mark(name + ' import')
                importlib.import_module(name)
        else:
            imports = {
                'demucs': ('demucs.separate', 'demucs.htdemucs', 'torchaudio', 'soundfile'),
                'f5tts': ('torchaudio', 'torchcodec.decoders'),
                'musetalk': ('torchvision', 'torchaudio', 'diffusers', 'transformers', 'face_alignment', 'librosa', 'omegaconf', 'cv2'),
                'rvc': ('rvc_python.infer', 'librosa', 'soundfile'),
                'gfpgan': ('gfpgan', 'facexlib.utils.face_restoration_helper'),
                'wav2lip': ('cv2', 'librosa', 'core.Wav2Lip.models', 'core.Wav2Lip.audio'),
                'image_classifier': ('transformers',), 'text_classifier': ('transformers',),
            }
            handles = []
            if adapter == 'wav2lip':
                sys.path.insert(0, str(ROOT / 'core/Wav2Lip'))
                if not (ROOT / 'core/Wav2Lip/face_detection/ibug/haarcascade_frontalface_alt.xml').is_file():
                    raise RuntimeError('Wav2Lip face-detection cascade is missing')
            if adapter == 'f5tts':
                import os
                shared = ROOT / 'ffmpeg/shared_libs'
                if hasattr(os, 'add_dll_directory') and shared.is_dir():
                    handles.append(os.add_dll_directory(str(shared)))
            for name in imports[adapter]:
                mark(name + ' import')
                importlib.import_module(name)
            if adapter in ('image_classifier', 'text_classifier'):
                transformers = importlib.import_module('transformers')
                report['versions']['transformers'] = transformers.__version__
                getattr(transformers, 'AutoModelForImageClassification' if adapter == 'image_classifier' else 'AutoModelForSequenceClassification')
                getattr(transformers, 'AutoImageProcessor' if adapter == 'image_classifier' else 'AutoTokenizer')
            if adapter == 'musetalk':
                transformers = importlib.import_module('transformers')
                getattr(transformers, 'WhisperModel')
                getattr(importlib.import_module('diffusers'), 'AutoencoderKL')
                report['versions']['transformers'] = transformers.__version__
                # Import the same entry point as feature_worker, without calling
                # main or constructing its checkpoint-backed objects.
                source = ROOT / 'core/MuseTalk'
                sys.path.insert(0, str(source))
                mark('MuseTalk workflow import')
                workflow = importlib.import_module('scripts.inference')
                if not Path(workflow.__file__).resolve().is_relative_to(source.resolve()):
                    raise RuntimeError('MuseTalk workflow resolved outside the bundled source')
                if not callable(getattr(workflow, 'main', None)):
                    raise RuntimeError('MuseTalk workflow main entry point is unavailable')
            if adapter == 'f5tts':
                mark('F5 speech API check')
                from core.f5_imports import load_f5_api
                engine = load_f5_api()
                if not callable(engine) or not callable(getattr(engine, 'infer', None)):
                    raise RuntimeError('F5 speech API is missing its F5TTS/infer entry points')
                report.update(reference_asr_import_tested=False, reference_asr_deferred=True, training_import_tested=False)
        mark('selected device check')
        if device == 'cuda:0':
            if not torch.cuda.is_available():
                raise RuntimeError('The first NVIDIA GPU is unavailable in this runtime')
            report['device_name'] = torch.cuda.get_device_name(0)
        torch.set_num_threads(2)
        result = torch.ones((2, 2), device=device) @ torch.ones((2, 2), device=device)
        if device == 'cuda:0':
            torch.cuda.synchronize(0)
        if not bool(torch.all(result == 2).item()):
            raise RuntimeError('Selected-device arithmetic check failed')
        report.update(status='passed', phase='complete')
    except Exception as exc:
        report['problems'].append(type(exc).__name__ + ': ' + str(exc)[:1500])
    return report


def main():
    # The parent supplies offline flags and workspace-only cache directories.
    # Block actual socket connections too, including unexpected import effects.
    def offline(event, args):
        if event == 'socket.connect':
            raise RuntimeError('Network access is disabled during runtime inspection')
    sys.addaudithook(offline)
    adapter, device, destination = sys.argv[1:]
    report = inspect(adapter, device, lambda value: Path(destination).write_text(json.dumps(value, allow_nan=False), encoding='utf-8'))
    Path(destination).write_text(json.dumps(report, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
