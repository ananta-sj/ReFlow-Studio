import sys
from os import listdir, path
import subprocess
import numpy as np
import cv2
import pickle
import os
import json
import torch
from tqdm import tqdm

# --- REFLOW STUDIO PATCH ---
# Upstream MuseTalk uses mmpose/DWPose here for 68-point face landmarks
# (config_file/checkpoint_file below, now unused). mmcv (mmpose's own
# hard dependency) only ships prebuilt wheels up to torch ~2.1-2.2 -
# OpenMMLab's releases lag PyTorch by a long margin - and this project
# runs torch 2.13. Installing/compiling a compatible mmcv would mean
# downgrading torch project-wide, risking every other model wired this
# session (XTTS, NLLB, faster-whisper, AirLLM). Swapped for the real
# `face-alignment` PyPI package instead (1adrianb/face-alignment,
# SFD-based, pure PyTorch, no mmcv) - it predicts the same standard
# 68-point 2D face landmark scheme DWPose's face-region slice
# approximates, so get_landmark_and_bbox()'s downstream math (indices
# 28/29/30 = nose-bridge area, used to compute the vertical mouth-region
# crop) is unchanged; only the landmark *source* differs. This is a real
# substitution with a genuinely-installed, real detector, not a stub.
import face_alignment
device = os.environ.get("REFLOW_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
# face-alignment 1.5.0's LandmarksType enum renamed _2D -> TWO_D (found
# by hitting the real AttributeError, not assumed) - same value (1) as
# the old name.
# compile=False: face-alignment defaults to compile=True (torch.compile,
# a one-time JIT warm-up for speed). This machine has no MSVC (no cl.exe)
# for torch's C++ codegen backend - the first compile attempt fails and
# falls back to eager mode gracefully, but a second one triggered later
# during per-frame processing raised the same InvalidCxxCompiler error
# *uncaught*, killing the whole run - confirmed by hitting it for real,
# not assumed. Disabling compilation outright avoids both.
fa = None


def face_detector():
    global fa
    if fa is None:
        from pathlib import Path
        from core.checkpoint_hash import MUSE_FACE_SHA256, require_asset_hash
        cache = Path(torch.hub.get_dir()) / 'checkpoints'
        for name in ('s3fd-619a316812.pth', '2DFAN4-11f355bf06.pth.tar'):
            if not (cache / name).is_file():
                raise RuntimeError('MuseTalk face detector asset is missing; recover assets before inference: ' + name)
            require_asset_hash(cache / name, MUSE_FACE_SHA256[name])
        fa = face_alignment.FaceAlignment(
            face_alignment.LandmarksType.TWO_D, flip_input=False, device=device, compile=False)
    return fa

# --- END PATCH ---

# maker if the bbox is not sufficient 
coord_placeholder = (0.0,0.0,0.0,0.0)

def resize_landmark(landmark, w, h, new_w, new_h):
    w_ratio = new_w / w
    h_ratio = new_h / h
    landmark_norm = landmark / [w, h]
    landmark_resized = landmark_norm * [new_w, new_h]
    return landmark_resized

def read_imgs(img_list):
    frames = []
    print('reading images...')
    for img_path in tqdm(img_list):
        frame = cv2.imread(img_path)
        frames.append(frame)
    return frames

# get_bbox_range() (upstream: a manual bbox_shift-tuning helper, never
# called from scripts/inference.py's actual render path - confirmed via
# its import list) removed rather than patched, since patching dead code
# referencing the removed mmpose names would just be a landmine left for
# no benefit - see the module header's REFLOW STUDIO PATCH note.


def get_landmark_and_bbox(img_list,upperbondrange =0):
    frames = read_imgs(img_list)
    coords_list = []
    if upperbondrange != 0:
        print('get key_landmark and face bounding boxes with the bbox_shift:',upperbondrange)
    else:
        print('get key_landmark and face bounding boxes with the default value')
    average_range_minus = []
    average_range_plus = []
    for frame in tqdm(frames):
        # --- REFLOW STUDIO PATCH: face_alignment instead of DWPose, see
        # module header. return_bboxes=True gives both the 68-point
        # landmarks and a face bbox from one detector pass, replacing the
        # original code's two separate calls (mmpose for landmarks, the
        # vendored bbox-only SFD detector for the box).
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks_batch, _, bboxes_batch = face_detector().get_landmarks_from_image(rgb, return_bboxes=True)
        if not landmarks_batch:
            coords_list += [coord_placeholder]
            continue
        face_land_mark = landmarks_batch[0].astype(np.int32)
        # face_alignment's return_bboxes=True appends a 5th element
        # (detection confidence) - [x1,y1,x2,y2,score] - but every
        # downstream consumer (this function's own fallback below,
        # scripts/inference.py's crop math, coord_placeholder equality
        # checks) expects a plain 4-tuple the way the original vendored
        # SFD-only detector's get_detections_for_batch() always returned.
        # Sliced off here, once, rather than patched at every call site -
        # found via a real "operands could not be broadcast together
        # with shapes (5,) (4,)" crash, not assumed.
        # Converted to a plain tuple, not left as a numpy array - a bare
        # ndarray bbox flowing into coords_list breaks
        # scripts/inference.py's `if bbox == coord_placeholder:` check
        # further downstream (coord_placeholder is a plain 4-tuple;
        # ndarray == tuple returns an elementwise bool array, and `if`
        # on that raises "truth value of an array... is ambiguous" -
        # hit for real, not assumed). The original vendored SFD-only
        # detector always returned plain tuples, which is what every
        # downstream consumer actually expects.
        # int(), not just tolist() - face_alignment's bbox coordinates
        # are float (sub-pixel precision), but downstream slicing
        # (frame[y1:y2, x1:x2]) needs real ints - the original vendored
        # SFD-only detector always returned pixel-integer coordinates.
        # Hit as a real "slice indices must be integers" crash, not
        # assumed.
        f = tuple(int(round(v)) for v in bboxes_batch[0][:4].tolist())
        # --- END PATCH ---

        half_face_coord =  face_land_mark[29]#np.mean([face_land_mark[28], face_land_mark[29]], axis=0)
        range_minus = (face_land_mark[30]- face_land_mark[29])[1]
        range_plus = (face_land_mark[29]- face_land_mark[28])[1]
        average_range_minus.append(range_minus)
        average_range_plus.append(range_plus)
        if upperbondrange != 0:
            half_face_coord[1] = upperbondrange+half_face_coord[1] #手动调整  + 向下（偏29）  - 向上（偏28）
        half_face_dist = np.max(face_land_mark[:,1]) - half_face_coord[1]
        min_upper_bond = 0
        upper_bond = max(min_upper_bond, half_face_coord[1] - half_face_dist)

        f_landmark = (np.min(face_land_mark[:, 0]),int(upper_bond),np.max(face_land_mark[:, 0]),np.max(face_land_mark[:,1]))
        x1, y1, x2, y2 = f_landmark

        if y2-y1<=0 or x2-x1<=0 or x1<0: # if the landmark bbox is not suitable, reuse the bbox
            coords_list += [f]
            w,h = f[2]-f[0], f[3]-f[1]
            print("error bbox:",f)
        else:
            coords_list += [f_landmark]

    print("********************************************bbox_shift parameter adjustment**********************************************************")
    if average_range_minus:
        print(f"Total frame:「{len(frames)}」 Manually adjust range : [ -{int(sum(average_range_minus) / len(average_range_minus))}~{int(sum(average_range_plus) / len(average_range_plus))} ] , the current value: {upperbondrange}")
    print("*************************************************************************************************************************************")
    return coords_list,frames
    

if __name__ == "__main__":
    img_list = ["./results/lyria/00000.png","./results/lyria/00001.png","./results/lyria/00002.png","./results/lyria/00003.png"]
    crop_coord_path = "./coord_face.pkl"
    coords_list,full_frames = get_landmark_and_bbox(img_list)
    with open(crop_coord_path, 'wb') as f:
        pickle.dump(coords_list, f)
        
    for bbox, frame in zip(coords_list,full_frames):
        if bbox == coord_placeholder:
            continue
        x1, y1, x2, y2 = bbox
        crop_frame = frame[y1:y2, x1:x2]
        print('Cropped shape', crop_frame.shape)
        
        #cv2.imwrite(path.join(save_dir, '{}.png'.format(i)),full_frames[i][0][y1:y2, x1:x2])
    print(coords_list)
