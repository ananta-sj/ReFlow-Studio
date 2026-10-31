from core.render_context import check_cancelled
"""Local image-classifier visual-filter provider - for a "local_file"
Filter Marketplace entry marked request_preset="image_classifier" (see
core/recommended_models.py's Falconsai/nsfw_image_detection entry),
distinct from the NudeNet default (core/providers/filter/nudenet_local.py),
which never actually loads a Marketplace-connected local_file model -
see core/providers/resolve.py.

Unlike NudeNet (an actual detector - returns bounding boxes for
localized blurring), a plain image classifier only scores the WHOLE
frame safe/unsafe, with no localization at all. "Filtering" here means
blurring the entire frame when it's flagged, the same whole-thing-
censored tradeoff ClassifierProfanityFilterProvider makes for text it
can't selectively rewrite.
"""

import os

from core.providers.label_contract import positive_index
from core.providers.base import FilterProvider

_UNSAFE_LABEL = "nsfw"
_DEFAULT_THRESHOLD = 0.5


class VisionClassifierLocalProvider(FilterProvider):
    def __init__(self, model_path, device=None, threshold=_DEFAULT_THRESHOLD):
        self.model_path = model_path
        self.device = device or "cpu"
        self.threshold = threshold
        self._model = None
        self._processor = None
        self._unsafe_index = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        # local_files_only=True - see core/providers/translation/
        # nllb_local.py's comment on the same line: from_pretrained()
        # attempts a network check even for an already-downloaded local
        # directory unless told not to, observed hanging for 15+ minutes
        # on a slow connection.
        self._processor = AutoImageProcessor.from_pretrained(self.model_path, local_files_only=True)
        model = AutoModelForImageClassification.from_pretrained(self.model_path, local_files_only=True)
        if self.device.startswith("cuda") and torch.cuda.is_available():
            model = model.to(self.device)
        else:
            self.device = "cpu"
        model.eval()

        # id2label's exact wording varies by checkpoint - resolved once
        # against the actually-loaded config, not hardcoded to an index,
        # so a differently-labeled classifier fails clearly instead of
        # silently scoring the wrong class as "unsafe".
        positive = positive_index(model.config.id2label, {'nsfw', 'unsafe'}, {'normal', 'sfw', 'safe', 'not_nsfw', 'non_nsfw'})

        self._unsafe_index = positive
        self._model = model

    def _is_unsafe(self, frame_bgr):
        import cv2
        import torch

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        inputs = self._processor(images=rgb, return_tensors="pt").to(self.device)
        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
        return probs[self._unsafe_index].item() >= self.threshold

    def scan_and_blur(self, video_path, output_path):
        import cv2
        from core.video_frames import transform_video
        self._ensure_loaded()
        def transform(frame, index):
            return cv2.GaussianBlur(frame, (99, 99), 0) if self._is_unsafe(frame) else frame
        return transform_video(video_path, output_path, transform)
