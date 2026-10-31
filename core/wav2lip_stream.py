"""Bounded video batches and complete mel windows for the vendored lip-sync CLI."""
import math
import os
import cv2
import numpy as np


def mel_window(mel, frame_index, fps):
    if mel.ndim != 2 or mel.shape[1] == 0:
        raise ValueError('Wav2Lip audio has invalid mel features')
    if not math.isfinite(fps) or fps <= 0 or type(frame_index) is not int or frame_index < 0:
        raise ValueError('Invalid Wav2Lip frame position')
    start = min(int(frame_index * 80 / fps), mel.shape[1] - 1)
    window = mel[:, start:start + 16]
    if not np.isfinite(window).all():
        raise ValueError('Wav2Lip audio has invalid mel features')
    return np.pad(window, ((0, 0), (0, 16 - window.shape[1])), mode='edge')


def frame_batches(path, batch_size, image_fps, audio_duration):
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError('Wav2Lip batches must contain 1 to 32 frames')
    if not math.isfinite(audio_duration) or audio_duration <= 0:
        raise ValueError('Wav2Lip audio duration must be positive')
    if os.path.splitext(path)[1].lower() in ('.jpg', '.jpeg', '.png'):
        if not math.isfinite(image_fps) or image_fps <= 0:
            raise ValueError('Invalid image frame rate')
        image = cv2.imread(path)
        if image is None:
            raise RuntimeError('Cannot decode source image')
        count = math.ceil(audio_duration * image_fps)
        for start in range(0, count, batch_size):
            yield image_fps, [image.copy() for _ in range(min(batch_size, count - start))]
        return
    capture = cv2.VideoCapture(path)
    count = 0
    try:
        if not capture.isOpened():
            raise RuntimeError('Cannot open Wav2Lip source video')
        fps = capture.get(cv2.CAP_PROP_FPS)
        expected = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('Invalid video frame rate')
        while True:
            frames = []
            for _ in range(batch_size):
                ok, frame = capture.read()
                if not ok:
                    break
                if count / fps > audio_duration + .05:
                    raise RuntimeError('Lip-sync audio is shorter than the source video')
                frames.append(frame)
                count += 1
            if not frames:
                break
            yield fps, frames
        if count == 0 or (expected > 0 and count != expected):
            raise RuntimeError(f'Wav2Lip decoded {count} of {expected} frames')
    finally:
        capture.release()
