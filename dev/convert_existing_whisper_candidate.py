"""Approved offline conversion of existing hash-bound Whisper weights only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
OUT = ROOT / 'docs/validation'
OWNED = ROOT / 'models/whisper/ct2-turbo-candidate'
SOURCE = ROOT / 'models/f5/reference-asr'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    global OWNED
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--compatibility-adapter', action='store_true')
    args = parser.parse_args()
    if args.compatibility_adapter:
        OWNED = ROOT / 'models/whisper/ct2-turbo-candidate-compat'
    from core.whisper_turbo_assets import validate_assets
    source = validate_assets(SOURCE, verify_weights=True)
    assert not OWNED.exists(), 'Preserve any earlier conversion; no automatic replacement'
    assert shutil.disk_usage(ROOT).free > 3_000_000_000
    OWNED.mkdir(parents=True)
    (OWNED / '.owner').write_text('reflow.recognition.conversion.2026-10-15')
    receipt = dict(completed=False, source_verified=True, source=source, model_downloaded=False,
                   quantization='int8', original_preserved=False, converter_runtime=sys.executable)
    path = OUT / ('2026-10-15-recognition-model-conversion-compat.json' if args.compatibility_adapter
                  else '2026-10-15-recognition-model-conversion.json')
    path.write_text(json.dumps(receipt, indent=2))
    os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', OMP_NUM_THREADS='4')
    started = time.monotonic()
    try:
        import ctranslate2
        from ctranslate2.converters import TransformersConverter
        import torch
        import transformers
        torch.set_num_threads(4)
        import socket
        def denied(*args, **kwargs):
            raise RuntimeError('Offline conversion blocks network access')
        class OfflineSocket(socket.socket):
            connect = connect_ex = bind = sendto = denied
        socket.socket = OfflineSocket
        socket.getaddrinfo = socket.create_connection = denied
        converter_class = TransformersConverter
        if args.compatibility_adapter:
            assert ctranslate2.__version__ == '4.6.3' and transformers.__version__ == '4.36.2'
            class CompatibleConverter(TransformersConverter):
                def load_model(self, model_class, model_name_or_path, **kwargs):
                    assert 'dtype' in kwargs and 'torch_dtype' not in kwargs
                    kwargs['torch_dtype'] = kwargs.pop('dtype')
                    return super().load_model(model_class, model_name_or_path, **kwargs)
            converter_class = CompatibleConverter
            receipt['compatibility_adapter'] = 'Process-local dtype -> torch_dtype for CTranslate2 4.6.3 / Transformers 4.36.2 only'
        converter = converter_class(str(SOURCE), copy_files=['tokenizer.json', 'preprocessor_config.json'],
                                           load_as_float16=True, trust_remote_code=False)
        converter.convert(str(OWNED / 'model'), quantization='int8', force=False)
        validate_assets(SOURCE, verify_weights=True)
        files = {p.relative_to(OWNED).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
                 for p in (OWNED / 'model').rglob('*') if p.is_file()}
        assert 'model/model.bin' in files
        receipt.update(completed=True, original_preserved=True, ctranslate2=ctranslate2.__version__,
                       files=files, converted_bytes=sum(row['bytes'] for row in files.values()),
                       elapsed_seconds=round(time.monotonic() - started, 3))
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        path.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
