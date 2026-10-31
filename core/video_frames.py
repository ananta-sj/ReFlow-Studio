"""Checked frame-stage publication shared by enhancement and visual filtering."""
import math
from core.render_context import check_cancelled


def transform_video(video_path, output_path, transform, upscale=1):
    import cv2
    from core.media_io import _staged_output, _validate_media

    reader = cv2.VideoCapture(video_path)
    writer = None
    try:
        if not reader.isOpened():
            raise RuntimeError('Cannot open video for frame processing')
        fps = reader.get(cv2.CAP_PROP_FPS)
        width = int(reader.get(cv2.CAP_PROP_FRAME_WIDTH)) * upscale
        height = int(reader.get(cv2.CAP_PROP_FRAME_HEIGHT)) * upscale
        expected = int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or width <= 0 or height <= 0:
            raise RuntimeError('Invalid video dimensions or frame rate')
        with _staged_output(output_path) as pending:
            writer = cv2.VideoWriter(pending, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
            count = 0
            try:
                if not writer.isOpened():
                    raise RuntimeError('Cannot open output video writer')
                while True:
                    check_cancelled()
                    ok, frame = reader.read()
                    if not ok:
                        break
                    result = transform(frame, count)
                    if result is None or result.shape != (height, width, 3) or str(result.dtype) != 'uint8':
                        raise RuntimeError(f'Frame {count + 1}: provider returned invalid dimensions or pixels')
                    writer.write(result)
                    count += 1
            finally:
                # Release Windows file handles before staged-output cleanup.
                writer.release()
                writer = None
            if not count or expected > 0 and count != expected:
                raise RuntimeError(f'Incomplete frame processing: {count}/{expected} frames')
            _validate_media(pending, {'video'})
        return output_path
    finally:
        reader.release()
        if writer is not None:
            writer.release()
