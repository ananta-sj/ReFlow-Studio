"""Pipeline Dry-Run Test Script

Tests running ReflowPipeline with sample input and dummy/mocked stage execution
or subtitle translation template to verify step-by-step generator output, logging,
and output file creation without hanging on long model downloads.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from bridge import api
from core import pipeline


def test_dryrun():
    print("--- 1. Testing Bridge Queue API ---")
    bridge = api.PythonBridge()
    item = bridge.add_queue_item(os.path.join(PROJECT_ROOT, "Sample", "1.mp4"), {"lang": "es"}, "video_dub")
    print(f"Added item to queue: {item['id']}, status: {item['status']}")

    items = bridge.get_queue_items()
    assert len(items) == 1, "Queue item count mismatch"
    print("Queue retrieval successful.")

    print("\n--- 2. Testing Hardware Auto-Tuner & Benchmark ---")
    bench = bridge.run_hardware_benchmark()
    print(f"Benchmark output: device={bench['device_id']}, score={bench['score']}, recommended_workers={bench['recommended_workers']}")

    print("\n--- 3. Testing Subtitle Translate Template ---")
    pipe = pipeline.ReflowPipeline()
    sample_srt = os.path.join(PROJECT_ROOT, "temp", "temp_subs.srt")
    with open(sample_srt, "w", encoding="utf-8") as f:
        f.write("1\n00:00:01,000 --> 00:00:03,000\nHello welcome to Reflow Studio.\n\n")

    out_path = None
    for percent, status, res in pipe.run("subtitle_translate", sample_srt, {"target_lang": "es"}):
        print(f"[{percent}%] {status}")
        if res:
            out_path = res

    assert out_path and os.path.exists(out_path), "Subtitle translate output missing"
    print(f"Subtitle translation complete! Output: {out_path}")

    print("\n--- Dry Run Completed Successfully! ---")

if __name__ == "__main__":
    test_dryrun()
