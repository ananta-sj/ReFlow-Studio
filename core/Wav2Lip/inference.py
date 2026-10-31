import sys
import os

# Force path to find local modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import argparse
import numpy as np
import cv2
import subprocess
from tqdm import tqdm
import torch

# Disable CuDNN Benchmarking for stability
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True

try:
    import audio
    from models import Wav2Lip
except ImportError as e:
    print(f"[FATAL] Local import failed: {e}")
    sys.exit(1)

def get_smoothened_boxes(boxes, T):
    for i in range(len(boxes)):
        if i + T > len(boxes):
            window = boxes[len(boxes) - T:]
        else:
            window = boxes[i : i + T]
        boxes[i] = np.mean(window, axis=0)
    return boxes

def face_detect(images, batch_size, smooth=True):
    cascade_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_detection", "ibug", "haarcascade_frontalface_alt.xml")
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError('Wav2Lip face detector asset is unavailable')
    
    results = []
    print("[LIPSYNC] Detecting faces...")
    
    # Process sequentially to avoid memory spikes
    for image in tqdm(images):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        rects = detector.detectMultiScale(gray, 1.3, 5)
        
        if len(rects) == 0:
            raise RuntimeError('Wav2Lip could not detect a face in a source frame')
            
        # Get the largest face
        rect = max(rects, key=lambda x: x[2] * x[3])
        x, y, w, h = rect
        results.append([x, y, w, h]) # x, y, w, h

    boxes = np.array(results)
    # Smooth the boxes to reduce "Jitter"
    if smooth:
        boxes = get_smoothened_boxes(boxes, T=min(5, len(boxes)))
    return boxes

def datagen(frames, mels, boxes, args):
    img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []

    for i, m in enumerate(mels):
        idx = i % len(frames)
        frame_to_save = frames[idx].copy()
        
        # [CRITICAL] Smart Cropping logic
        x, y, w, h = boxes[idx]
        x, y, w, h = int(x), int(y), int(w), int(h)
        
        height, width = frame_to_save.shape[:2]
        if min(w, h) <= 0 or min(x, y) < 0 or x + w > width or y + h > height:
            raise RuntimeError('Wav2Lip face crop lies outside its source frame')
        face = cv2.resize(frame_to_save[y:y+h, x:x+w], (96, 96))
        coords = (x, y, w, h)

        img_batch.append(face)
        mel_batch.append(m)
        frame_batch.append(frame_to_save) # Keep FULL 1080p frame
        coords_batch.append(coords)

        if len(img_batch) >= args.wav2lip_batch_size:
            img_batch, mel_batch = np.asarray(img_batch), np.asarray(mel_batch)

            img_masked = img_batch.copy()
            img_masked[:, img_masked.shape[1]//2:] = 0

            img_batch = np.concatenate((img_masked, img_batch), axis=3) / 255.
            mel_batch = np.reshape(mel_batch, [len(mel_batch), mel_batch.shape[1], mel_batch.shape[2], 1])

            yield img_batch, mel_batch, frame_batch, coords_batch
            img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []

    if len(img_batch) > 0:
        img_batch, mel_batch = np.asarray(img_batch), np.asarray(mel_batch)
        img_masked = img_batch.copy()
        img_masked[:, img_masked.shape[1]//2:] = 0
        img_batch = np.concatenate((img_masked, img_batch), axis=3) / 255.
        mel_batch = np.reshape(mel_batch, [len(mel_batch), mel_batch.shape[1], mel_batch.shape[2], 1])
        yield img_batch, mel_batch, frame_batch, coords_batch

def load_model(path, device=None):
    device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[LIPSYNC] Loading Checkpoint on {device}...")
    model = Wav2Lip()
    # weights_only=True restricts unpickling to a safe allowlist (tensors +
    # basic Python builtins), preventing arbitrary code execution from a
    # malicious/compromised .pth file - torch.load() uses pickle by
    # default, which can run arbitrary code via a crafted __reduce__ on
    # load. Verified this checkpoint's actual structure (state_dict +
    # optimizer state, no exotic objects) still loads correctly under it.
    checkpoint = torch.load(path, map_location=torch.device('cpu'), weights_only=True)
    s = checkpoint["state_dict"]
    new_s = {}
    for k, v in s.items():
        new_s[k.replace('module.', '')] = v
    model.load_state_dict(new_s)
    model = model.to(device)
    return model.eval()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work_dir", default=".")
    parser.add_argument("--device", default=None)
    parser.add_argument('--checkpoint_path', type=str, required=True)
    parser.add_argument('--face', type=str, required=True)
    parser.add_argument('--audio', type=str, required=True)
    parser.add_argument('--outfile', type=str, default='results/result_voice.mp4')
    parser.add_argument('--static', type=bool, default=False)
    parser.add_argument('--fps', type=float, default=25., required=False)
    parser.add_argument('--pads', nargs='+', type=int, default=[0, 10, 0, 0])
    
    # Safe Defaults
    parser.add_argument('--face_det_batch_size', type=int, default=4) 
    parser.add_argument('--wav2lip_batch_size', type=int, default=8)
    
    parser.add_argument('--resize_factor', default=1, type=int)
    parser.add_argument('--crop', nargs='+', type=int, default=[0, -1, 0, -1])
    parser.add_argument('--box', nargs='+', type=int, default=[-1, -1, -1, -1])
    parser.add_argument('--rotate', default=False, action='store_true')
    parser.add_argument('--nosmooth', default=False, action='store_true')
    parser.add_argument('--gpu_batch_size', type=int, default=16)

    args = parser.parse_args()
    
    # Clean VRAM
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    if device.startswith('cuda') and not torch.cuda.is_available():
        raise ValueError('Selected CUDA device is unavailable')

    if not os.path.isfile(args.face):
        raise ValueError('--face argument must be a valid path')

    # Audio Prep
    os.makedirs(args.work_dir, exist_ok=True)
    temp_audio_clean = os.path.join(args.work_dir, "temp_clean.wav")
    subprocess.run(['ffmpeg', '-y', '-i', args.audio, '-ac', '1', '-ar', '16000', temp_audio_clean], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800, check=True)
    args.audio = temp_audio_clean

    wav = audio.load_wav(args.audio, 16000)
    mel = audio.melspectrogram(wav)
    if mel.ndim != 2 or mel.shape[1] == 0 or not np.isfinite(mel).all():
        raise ValueError('Wav2Lip audio has invalid mel features')
    model = load_model(args.checkpoint_path, device=device)
    temp_avi = os.path.join(args.work_dir, "temp_output.avi")
    sys.path.insert(0, os.path.dirname(os.path.dirname(current_dir)))
    from core.wav2lip_stream import frame_batches, mel_window
    batches = frame_batches(args.face, args.wav2lip_batch_size, args.fps, len(wav) / 16000)
    out = None
    frame_index = 0
    try:
        for fps, source_frames in batches:
            if out is None:
                h_out, w_out = source_frames[0].shape[:2]
                out = cv2.VideoWriter(temp_avi, cv2.VideoWriter_fourcc(*'DIVX'), fps, (w_out, h_out))
                if not out.isOpened():
                    raise RuntimeError('Cannot open Wav2Lip video encoder')
            faces_boxes = face_detect(source_frames, args.face_det_batch_size, smooth=not args.nosmooth)
            chunks = [mel_window(mel, frame_index + offset, fps) for offset in range(len(source_frames))]
            for img_batch, mel_batch, frames, coords in datagen(source_frames, chunks, faces_boxes, args):
                img_batch = torch.FloatTensor(np.transpose(img_batch, (0, 3, 1, 2))).to(device)
                mel_batch = torch.FloatTensor(np.transpose(mel_batch, (0, 3, 1, 2))).to(device)
                with torch.no_grad():
                    pred = model(mel_batch, img_batch)
                pred = pred.cpu().numpy().transpose(0, 2, 3, 1)
                if len(pred) != len(frames) or not np.isfinite(pred).all():
                    raise RuntimeError('Wav2Lip returned incomplete or invalid face predictions')
                for patch, frame, (x, y, w, h) in zip(pred, frames, coords):
                    pixels = np.clip(patch * 255, 0, 255).astype(np.uint8)
                    frame[y:y+h, x:x+w] = cv2.resize(pixels, (w, h))
                    out.write(frame)
                    frame_index += 1
        if frame_index == 0:
            raise RuntimeError('Wav2Lip produced no frames')
    finally:
        batches.close()
        if out is not None:
            out.release()

    subprocess.run(['ffmpeg', '-y', '-i', args.audio, '-i', temp_avi,
                    '-map', '1:v:0', '-map', '0:a:0', '-c:v', 'libx264', '-crf', '18',
                    '-c:a', 'aac', '-shortest', args.outfile], check=True, timeout=1800)
    
    for f in [temp_avi, temp_audio_clean]:
        if os.path.exists(f): os.remove(f)

if __name__ == '__main__':
    main()
