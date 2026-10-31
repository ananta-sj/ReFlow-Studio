from core.render_context import check_cancelled
import os
import sys
import torch
import warnings
from types import SimpleNamespace

# Suppress warnings
warnings.filterwarnings("ignore")

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

try:
    from gfpgan import GFPGANer
except ImportError:
    print("[ENHANCER] ❌ GFPGAN not installed correctly.")
    GFPGANer = None

class FaceEnhancer:
    def __init__(self, device=None, upscale=1, model_path=None):
        # 1. SMART DEVICE DETECTION
        # An explicit device (e.g. from the user's hardware-panel selection)
        # wins; otherwise auto-detect. If Torch says "No CUDA", we MUST pass
        # device='cpu' or it will crash.
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        # "Texture Quality" in the UI: 1x/2x/4x GFPGAN upscale factor.
        self.upscale = upscale if upscale in (1, 2, 4) else 1

        print(f"[ENHANCER] ⏳ Loading GFPGAN Engine on {self.device.upper()} ({self.upscale}x)...")

        self.restorer = None
        if GFPGANer is None:
            raise RuntimeError("Enhancement requires an importable GFPGAN engine")
        from core.model_assets import ensure_assets
        if model_path is None:
            ensure_assets("gfpgan")
        else:
            ensure_assets('gfpgan', include={'gfpgan/weights/parsing_parsenet.pth',
                                           'gfpgan/weights/detection_Resnet50_Final.pth'})
        self.model_path = model_path or os.path.join(config.BASE_DIR, "gfpgan", "weights", "GFPGANv1.4.pth")

        if not os.path.exists(self.model_path):
            print(f"[ENHANCER] ⚠️ Model missing: {self.model_path}")
            raise RuntimeError("GFPGAN checkpoint is missing")

        try:
            # 2. INITIALIZE WITH CORRECT DEVICE
            from gfpgan.archs.gfpganv1_clean_arch import GFPGANv1Clean
            from facexlib.utils.face_restoration_helper import FaceRestoreHelper
            model = GFPGANv1Clean(out_size=512, num_style_feat=512, channel_multiplier=2,
                decoder_load_path=None, fix_decoder=False, num_mlp=8, input_is_latent=True,
                different_w=True, narrow=1, sft_half=True)
            weights = torch.load(self.model_path, map_location='cpu', weights_only=True)
            model.load_state_dict(weights['params_ema'] if 'params_ema' in weights else weights['params'], strict=True)
            model.to(self.device).eval()
            helper = FaceRestoreHelper(self.upscale, face_size=512, crop_ratio=(1, 1),
                det_model='retinaface_resnet50', save_ext='png', use_parse=True,
                device=torch.device(self.device), model_rootpath=os.path.join(config.BASE_DIR, 'gfpgan', 'weights'))
            self.restorer = SimpleNamespace(gfpgan=model, face_helper=helper, device=self.device)
            print("[ENHANCER] ✅ Engine Loaded.")

        except Exception as e:
            raise RuntimeError(f'GFPGAN initialization failed: {e}') from e

    def enhance(self, video_path, output_path):
        if self.restorer is None:
            raise RuntimeError('Enhancement engine is not ready')
        from core.video_frames import transform_video
        def transform(frame, index):
            return _restore_frame(self.restorer, frame)
        return transform_video(video_path, output_path, transform, upscale=self.upscale)


def _restore_frame(restorer, frame):
    """Restore without upstream's silent inference-error-to-original fallback."""
    from basicsr.utils import img2tensor, tensor2img
    from torchvision.transforms.functional import normalize
    helper = restorer.face_helper
    helper.clean_all()
    helper.read_image(frame)
    helper.get_face_landmarks_5(only_center_face=False, eye_dist_threshold=5)
    helper.align_warp_face()
    with torch.inference_mode():
        for face in helper.cropped_faces:
            value = img2tensor(face / 255., bgr2rgb=True, float32=True)
            normalize(value, (.5, .5, .5), (.5, .5, .5), inplace=True)
            result = restorer.gfpgan(value.unsqueeze(0).to(restorer.device), return_rgb=False, weight=.5)[0]
            if result.ndim != 4 or result.shape[0] != 1 or not torch.isfinite(result).all():
                raise RuntimeError('GFPGAN returned invalid face predictions')
            restored = tensor2img(result.squeeze(0), rgb2bgr=True, min_max=(-1, 1))
            helper.add_restored_face(restored.astype('uint8'))
    helper.get_inverse_affine(None)
    return helper.paste_faces_to_input_image(upsample_img=None)
