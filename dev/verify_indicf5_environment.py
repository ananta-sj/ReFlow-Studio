"""Offline package/architecture readiness, explicitly not speech acceptance."""
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'runtime_profiles/indicf5-evaluation'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['WANDB_MODE'] = 'disabled'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MPLCONFIGDIR'] = str(ROOT / 'temp/indicf5-matplotlib')
os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/cache')


def main():
    started = time.monotonic()
    report = dict(imports_pass=False, core_runtime_changed=False, model_weights_loaded=False,
                  synthesis_tested=False, speech_quality_accepted=False)
    try:
        if Path(sys.executable).resolve().parent != PROFILE.resolve():
            raise ValueError('Use the isolated IndicF5 evaluation interpreter')
        import torch
        shared = ROOT / 'ffmpeg/shared_libs'
        dll = os.add_dll_directory(str(shared)) if shared.is_dir() and hasattr(os, 'add_dll_directory') else None
        from f5_tts.api import F5TTS
        from f5_tts.model import CFM, DiT
        import f5_tts.api
        from packaging.requirements import Requirement
        mismatches = []
        for specification in metadata.requires('f5-tts') or []:
            requirement = Requirement(specification)
            if requirement.marker and not requirement.marker.evaluate():
                continue
            try:
                version = metadata.version(requirement.name)
            except metadata.PackageNotFoundError:
                mismatches.append(dict(package=requirement.name, reason='missing'))
                continue
            if requirement.specifier and version not in requirement.specifier:
                mismatches.append(dict(package=requirement.name, version=version, requires=str(requirement.specifier)))
        if mismatches:
            report['dependency_mismatches'] = mismatches
            raise RuntimeError('Declared IndicF5 package dependencies do not match')
        report.update(imports_pass=True, package_version=metadata.version('f5-tts'),
                      torch_version=torch.__version__, package_path=f5_tts.api.__file__,
                      interpreter=sys.executable, declared_dependencies_match=True)
        if not Path(f5_tts.api.__file__).resolve().is_relative_to(PROFILE.resolve()):
            raise ValueError('Package imported outside isolated profile')
        small = DiT(dim=64, depth=1, heads=2, dim_head=32, text_dim=32,
                    text_num_embeds=128, conv_layers=1).eval()
        with torch.no_grad():
            output = small(x=torch.zeros(1, 8, 100), cond=torch.zeros(1, 8, 100),
                           text=torch.tensor([[1, 2, 3]]), time=torch.tensor([0.5]),
                           drop_audio_cond=False, drop_text=False)
        if tuple(output.shape) != (1, 8, 100) or not torch.isfinite(output).all():
            raise RuntimeError('Small architecture forward failed shape/finite checks')
        report.update(small_architecture_forward_pass=True, trained_model_inference_tested=False)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (ROOT / 'docs/validation/2026-10-06-indicf5-environment.json').write_text(
            json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
