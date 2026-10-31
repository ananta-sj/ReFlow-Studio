"""Bounded source-image batches for the vendored MuseTalk worker."""
import os


def frame_indices(source_count, audio_count, video_source):
    if source_count <= 0 or audio_count <= 0:
        raise ValueError('MuseTalk requires source frames and audio features')
    if video_source:
        if audio_count < source_count - 1:
            raise RuntimeError('MuseTalk audio is shorter than the source video')
        # A final partial frame may have no distinct feature window. Reuse its
        # immediate predecessor, while always preserving source frame count.
        return ((index, min(index, audio_count - 1)) for index in range(source_count))
    return ((index % source_count, index) for index in range(audio_count))


def frame_groups(indices, batch_size):
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError('MuseTalk batches must contain 1 to 32 frames')
    batch = []
    for item in indices:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def render_batches(paths, chunks, video_source, args, device, vae, unet, pe, timesteps, parser, landmarks, blend):
    import cv2
    import numpy as np
    import torch
    indices = frame_indices(len(paths), len(chunks), video_source)
    count = 0
    for batch in frame_groups(indices, args.batch_size):
        boxes, frames = landmarks([paths[source] for source, _ in batch], args.bbox_shift)
        if len(frames) != len(batch) or len(boxes) != len(batch):
            raise RuntimeError('MuseTalk requires complete frames and landmarks')
        latents, bounded_boxes = [], []
        for box, frame in zip(boxes, frames):
            if frame is None or len(box) != 4:
                raise RuntimeError('MuseTalk could not decode a source face')
            x1, y1, x2, y2 = [int(value) for value in box]
            if args.version == 'v15':
                y2 = min(y2 + args.extra_margin, frame.shape[0])
            if min(x1, y1) < 0 or x2 > frame.shape[1] or y2 > frame.shape[0] or x2 <= x1 or y2 <= y1:
                raise RuntimeError('MuseTalk could not locate a valid face in every frame')
            bounded_boxes.append([x1, y1, x2, y2])
            crop = cv2.resize(frame[y1:y2, x1:x2], (256, 256), interpolation=cv2.INTER_LANCZOS4)
            latents.append(vae.get_latents_for_unet(crop))
        audio = torch.stack([chunks[audio_index] for _, audio_index in batch]).to(device)
        latent_batch = torch.cat(latents, dim=0).to(device=device, dtype=unet.model.dtype)
        predictions = unet.model(latent_batch, timesteps, encoder_hidden_states=pe(audio)).sample
        decoded = vae.decode_latents(predictions)
        if len(decoded) != len(batch):
            raise RuntimeError('MuseTalk returned incomplete face predictions')
        for patch, frame, box in zip(decoded, frames, bounded_boxes):
            if not np.isfinite(patch).all():
                raise RuntimeError('MuseTalk returned invalid face predictions')
            x1, y1, x2, y2 = box
            patch = cv2.resize(np.clip(patch, 0, 255).astype(np.uint8), (x2-x1, y2-y1))
            options = {'mode': args.parsing_mode} if args.version == 'v15' else {}
            combined = blend(frame, patch, box, fp=parser, **options)
            target = os.path.join(args.frame_output_dir, f'{count:08d}.png')
            if combined is None or not cv2.imwrite(target, combined):
                raise RuntimeError(f'MuseTalk could not save frame {count}')
            count += 1
    if count == 0:
        raise RuntimeError('MuseTalk generated no output frames')
    return count
