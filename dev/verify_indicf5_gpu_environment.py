"""Verify isolated CUDA package origins and real GPU operations before readiness."""
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'runtime_profiles/indicf5-gpu-evaluation'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'


def main():
    if Path(sys.executable).resolve().parent != PROFILE.resolve():
        raise ValueError('Use the isolated GPU evaluation interpreter')
    report = dict(passed=False, cpu_profile_changed=False, core_runtime_changed=False,
                  trained_speech_tested=False, human_quality_accepted=False, packages={})
    started = time.monotonic()
    try:
        print(json.dumps({'stage': 'checking-gpu-package-origins'}), flush=True)
        import torch
        import torchaudio
        import torchvision
        for name, package, version in (('torch', torch, '2.9.1+cu128'),
                                       ('torchvision', torchvision, '0.24.1+cu128'),
                                       ('torchaudio', torchaudio, '2.9.1+cu128')):
            origin = Path(package.__file__).resolve()
            if PROFILE / 'Lib/site-packages' not in origin.parents:
                raise ValueError('GPU package fell through to shared CPU profile: ' + name)
            if metadata.version(name) != version:
                raise ValueError('Unexpected CUDA package version for ' + name)
            report['packages'][name] = dict(version=version, path=str(origin))
        if not torch.cuda.is_available() or torch.version.cuda != '12.8':
            raise RuntimeError('CUDA 12.8 execution is unavailable')
        report.update(device=torch.cuda.get_device_name(0),
                      device_memory_bytes=torch.cuda.get_device_properties(0).total_memory,
                      cuda_version=torch.version.cuda)
        device = torch.device('cuda:0')
        values = torch.arange(16, dtype=torch.float32).reshape(4, 4)
        result = values.to(device) @ values.T.to(device)
        if not torch.equal(result.cpu(), values @ values.T):
            raise RuntimeError('CUDA matrix operation failed')
        boxes = torch.tensor([[0., 0., 2., 2.], [0., 0., 2., 2.], [4., 4., 5., 5.]], device=device)
        scores = torch.tensor([.9, .8, .7], device=device)
        if torchvision.ops.nms(boxes, scores, .5).cpu().tolist() != [0, 2]:
            raise RuntimeError('Torchvision CUDA operator failed')
        waveform = torch.sin(torch.arange(1600, dtype=torch.float32, device=device)*.02).unsqueeze(0)
        resampled = torchaudio.transforms.Resample(16000, 24000).to(device)(waveform)
        if resampled.shape != (1, 2400) or not torch.isfinite(resampled).all():
            raise RuntimeError('Torchaudio CUDA operation failed')
        torch.cuda.synchronize()
        report.update(passed=True, cuda_matrix_pass=True, torchvision_cuda_pass=True,
                      torchaudio_cuda_pass=True, peak_allocated_bytes=torch.cuda.max_memory_allocated())
        profile = json.loads((PROFILE / 'profile.json').read_text(encoding='utf-8'))
        profile.update(status='gpu-environment-verified', cuda_version='12.8', device=report['device'],
                       trained_speech_verified=False)
        (PROFILE / 'profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (ROOT / 'docs/validation/2026-10-06-indicf5-gpu-environment.json').write_text(
            json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
