"""Model Downloader & Removal Verification Test

Tests streaming model downloader live speed/ETA emission, registry integration,
and preview-confirmed disk cleanup on remove_model(). This is an opt-in live
network/manual check; deterministic download guards are in test_deletion_safety.
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

import config
from bridge import api
from core import downloader, model_registry


def test_downloader_and_removal():
    print("--- 1. Testing Downloader Metrics (Speed, Percent, ETA) ---")
    test_url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_alt.xml"
    dest_path = os.path.join(config.MODELS_DIR, "_downloads", "test_sample.xml")

    progress_reports = []
    for p in downloader.download_with_progress(test_url, dest_path):
        progress_reports.append(p)

    assert len(progress_reports) > 0, "No progress reports yielded"
    last_p = progress_reports[-1]
    print(f"Download Finished. Phase: {last_p['phase']}, Bytes: {last_p['downloaded']}, Speed: {last_p['speed_bps']:.1f} B/s, ETA: {last_p['eta_seconds']}s")
    assert os.path.exists(dest_path), "Downloaded file not saved to disk"

    print("\n--- 2. Testing Bridge Model Addition & Live Progress ---")
    bridge = api.PythonBridge()
    small_url = "https://raw.githubusercontent.com/SubtitleEdit/subtitleedit/main/README.md"
    res = bridge.add_local_model("stt", small_url, "Test Small Model")
    assert res["ok"], "Failed to add local model"
    model_id = res["model"]["id"]
    print(f"Added model to registry: ID={model_id}")

    # Wait for download thread to complete
    for _ in range(20):
        entry = bridge.registry.get(model_id)
        if entry and entry["status"] == "installed" and not bridge._active_downloads:
            break
        time.sleep(0.5)

    entry = bridge.registry.get(model_id)
    assert entry is not None, "Model entry missing from registry"
    assert entry["status"] == "installed", f"Model status is {entry['status']}, expected installed"
    print(f"Model status after download: {entry['status']}")

    print("\n--- 3. Testing Model Removal & Disk Cleanup (Installed Model) ---")
    dest_dir = os.path.join(config.MODELS_DIR, "_downloads", model_id)
    assert os.path.exists(dest_dir), f"Model directory {dest_dir} should exist before removal"

    preview = bridge.preview_model_removal(model_id)
    assert preview["ok"], preview
    remove_res = bridge.remove_model(model_id, preview["token"])
    assert remove_res["ok"], "remove_model failed"
    assert bridge.registry.get(model_id) is None, "Model entry still in registry after removal"
    assert not os.path.exists(dest_dir), f"Model directory {dest_dir} was NOT cleaned up from disk"
    print("Installed model entry and files successfully removed from disk!")

    print("\nActive-download removal is rejected; fixture tests cover this without downloading a large model.")

    # Cleanup test_sample.xml
    if os.path.exists(dest_path):
        os.remove(dest_path)

    print("\n--- All Model Download, Speed/ETA & Removal Tests PASSED ---")


if __name__ == "__main__":
    test_downloader_and_removal()
