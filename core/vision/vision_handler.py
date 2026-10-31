import cv2
import os

class VisionHandler:
    def __init__(self):
        self.detector = None
        self.enabled = False
        
        try:
            # Try to import NudeNet
            from nudenet import NudeDetector
            # NudeNet 3.4.1 includes its default 320n ONNX checkpoint.
            self.detector = NudeDetector()
            self.enabled = True
            print("[VISION] 👁️ NudeNet Censorship System Online.")
        except Exception as e:
            # An enabled filter must fail visibly when initialization fails.
            print(f"[VISION] ⚠️ Censorship Module Disabled: {e}")
            raise RuntimeError(f"Visual filter initialization failed: {e}") from e

    def scan_frame(self, frame):
        """
        Returns a list of bounding boxes [x1, y1, x2, y2] for detected nudity.
        """
        if not self.enabled or self.detector is None:
            raise RuntimeError("Visual filter detector is unavailable")

        # NudeNet expects path or image. We pass the frame directly if supported, 
        # but NudeDetector usually prefers file paths. 
        # For real-time, we use the detect() method on the array.
        try:
            # 320 is a good balance for speed/accuracy on video frames
            preds = self.detector.detect(frame)
            
            boxes = []
            for pred in preds:
                # Filter for exposed parts only (adjust labels as needed)
                if pred['class'] in ['FEMALE_BREAST_EXPOSED', 'FEMALE_GENITALIA_EXPOSED', 'MALE_GENITALIA_EXPOSED', 'EXPOSED_BREAST_F', 'EXPOSED_GENITALIA_F', 'EXPOSED_GENITALIA_M']:
                    if pred['score'] > 0.5: # Confidence threshold
                        boxes.append(pred['box']) # [x, y, w, h]
            
            # Convert [x, y, w, h] to [x1, y1, x2, y2]
            final_boxes = []
            for box in boxes:
                x, y, w, h = box
                final_boxes.append([x, y, x + w, y + h])
                
            return final_boxes
            
        except Exception as e:
            # Never publish an unfiltered frame after a detector failure.
            raise RuntimeError(f"Visual filter detection failed: {e}") from e

    def blur_zone(self, frame, box):
        """
        Applies a heavy blur to the specific zone.
        """
        x1, y1, x2, y2 = box
        
        # Safety check for image bounds
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0: return frame
        
        # Apply blur
        roi = cv2.GaussianBlur(roi, (51, 51), 0)
        frame[y1:y2, x1:x2] = roi
        
        return frame
