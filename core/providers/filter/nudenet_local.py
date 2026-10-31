from core.render_context import check_cancelled
"""Local NudeNet content-filter provider - wraps VisionHandler.

The frame-by-frame video loop used to live directly in
core/pipeline.py::apply_content_filter(); moved here so pipeline.py can
treat content filtering the same uniform way it treats every other
stage (video in, video out), regardless of which provider is active.
"""

import os

from core.providers.base import FilterProvider


class NudeNetLocalProvider(FilterProvider):
    def scan_and_blur(self, video_path, output_path):
        from core.optional_runtime import interpreter, run_feature
        if interpreter("vision"):
            from pipeline import _staged_output, _validate_media
            with _staged_output(output_path) as pending:
                run_feature("vision", "visual_filter", {
                    "video_path": os.path.abspath(video_path), "output_path": pending})
                _validate_media(pending, {"video"})
            return output_path
        from vision.vision_handler import VisionHandler
        scanner = VisionHandler()
        if not scanner.enabled:
            raise RuntimeError('Visual filter detector is unavailable')
        from core.video_frames import transform_video
        def transform(frame, index):
            for box in scanner.scan_frame(frame):
                frame = scanner.blur_zone(frame, box)
            return frame
        return transform_video(video_path, output_path, transform)
