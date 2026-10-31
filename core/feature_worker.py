"""Small worker entry point; imports only packages belonging to its feature."""
import json
from pathlib import Path
import sys
import os
import time
import traceback
import gc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def speech_setup():
    import torch
    shared = ROOT / "ffmpeg" / "shared_libs"
    if hasattr(os, "add_dll_directory") and shared.is_dir():
        return os.add_dll_directory(str(shared))
    return None


def prepare_f5_asr(params):
    if params.get('reference_text', '').strip():
        return
    from f5_tts.infer import utils_infer
    if utils_infer.asr_pipe is None:
        import torch
        from transformers import pipeline
        model = ROOT / 'models/f5/reference-asr'
        if not (model / 'model.safetensors').is_file():
            raise RuntimeError('F5 reference transcription assets have not been recovered')
        utils_infer.asr_pipe = pipeline('automatic-speech-recognition', model=str(model),
                                      torch_dtype=torch.float32, device=params['device'])


def prepare_f5_reference(params, cache=None):
    reference = params['reference_audio']
    text = params.get('reference_text', '').strip()
    if text:
        return reference, text
    stat = Path(reference).stat()
    key = (str(Path(reference).resolve()), stat.st_size, stat.st_mtime_ns)
    if cache is not None and key in cache:
        return reference, cache[key]
    from f5_tts.infer import utils_infer
    prepare_f5_asr(params)
    try:
        _, text = utils_infer.preprocess_ref_audio_text(reference, '')
        if not any(character.isalnum() for character in text):
            raise RuntimeError('F5 reference transcription detected no usable speech')
    finally:
        # The ASR weights have completed their stage. Retain the transcript,
        # not a second large model, while F5 performs diffusion synthesis.
        utils_infer.asr_pipe = None
        gc.collect()
        if str(params['device']).startswith('cuda'):
            import torch
            torch.cuda.empty_cache()
    if cache is not None:
        if len(cache) >= 64:
            cache.pop(next(iter(cache)))
        cache[key] = text
    return reference, text


def f5_speech(params):
    dll_handle = speech_setup()
    from core.f5_imports import load_f5_api
    F5TTS = load_f5_api()
    reference, text = prepare_f5_reference(params)
    engine = F5TTS(device=params["device"], ckpt_file=params["checkpoint_path"],
                   vocab_file=params["vocab_path"], model=params["recipe"],
                   hf_cache_dir=str(ROOT / "models" / "f5" / "cache"))
    engine.infer(ref_file=reference, ref_text=text,
                 gen_text=params["text"], file_wave=params["output_path"])


def f5_session(params):
    """Keep one isolated model loaded until its render job closes the session."""
    dll_handle = speech_setup()
    from core.f5_imports import load_f5_api
    F5TTS = load_f5_api()
    engine = None
    folder = Path(params['session_dir'])
    last_processed = 0
    references = {}
    while not (folder / 'stop').exists():
        pending = sorted(folder.glob('call-????????.json'))
        for request_path in pending:
            sequence = int(request_path.stem[5:])
            if sequence <= last_processed:
                continue
            call = json.loads(request_path.read_text(encoding='utf-8'))
            response = {'ok': False, 'worker_pid': os.getpid(), 'sequence': sequence}
            try:
                reference, text = prepare_f5_reference({**call, 'device': params['device']}, references)
                if engine is None:
                    engine = F5TTS(device=params['device'], ckpt_file=params['checkpoint_path'],
                        vocab_file=params['vocab_path'], model=params['recipe'],
                        hf_cache_dir=str(ROOT / 'models/f5/cache'))
                engine.infer(ref_file=reference, ref_text=text,
                    gen_text=call['text'], file_wave=call['output_path'])
                response['ok'] = True
            except Exception:
                response['error'] = traceback.format_exc()[-6000:]
            temporary = request_path.with_suffix('.response.tmp')
            temporary.write_text(json.dumps(response), encoding='utf-8')
            os.replace(temporary, request_path.with_suffix('.response.json'))
            last_processed = sequence
        time.sleep(.05)


def musetalk(params):
    import runpy
    source = ROOT / "core" / "MuseTalk"
    sys.path.insert(0, str(source))
    os.chdir(source)
    os.environ["REFLOW_DEVICE"] = params["device"]
    sys.argv = ["scripts.inference", *params["args"]]
    runpy.run_module("scripts.inference", run_name="__main__")


def visual_filter(params):
    import cv2
    import math
    from core.vision.vision_handler import VisionHandler
    source = cv2.VideoCapture(params["video_path"])
    writer = None
    try:
        if not source.isOpened():
            raise RuntimeError("Cannot open source video")
        fps = source.get(cv2.CAP_PROP_FPS)
        width, height = (int(source.get(key)) for key in
                         (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT))
        expected = int(source.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or min(width, height) <= 0:
            raise RuntimeError("Invalid video dimensions or frame rate")
        scanner = VisionHandler()
        writer = cv2.VideoWriter(params["output_path"], cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError("Cannot open video encoder")
        count = 0
        while True:
            ok, frame = source.read()
            if not ok:
                break
            for box in scanner.scan_frame(frame):
                frame = scanner.blur_zone(frame, box)
            writer.write(frame)
            count += 1
        if count == 0 or (expected > 0 and count != expected):
            raise RuntimeError(f"Video decoded {count} of {expected} frames")
        print(json.dumps({"frames": count, "fps": fps}))
    finally:
        source.release()
        if writer is not None:
            writer.release()


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    operations = {"visual_filter": visual_filter, "f5_speech": f5_speech, "f5_session": f5_session, "musetalk": musetalk}
    if request["operation"] not in operations:
        raise ValueError("Unsupported feature operation")
    operations[request["operation"]](request["params"])


if __name__ == "__main__":
    main()
