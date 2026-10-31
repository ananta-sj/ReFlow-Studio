"""Reflow Studio Core Test Suite

Automated diagnostic and verification script for backend components.
Runs isolated unit/integration checks on srt_utils, graph_model, node_registry,
hardware_monitor, model_registry, janitor, credential_store, languages,
bridge/api, audio_utils, and path edge cases.
"""

import os
import sys
import tempfile
import unittest
import uuid

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

import config
from core import (
    audio_utils,
    credential_store,
    graph_model,
    hardware_monitor,
    hardware_profile,
    janitor,
    languages,
    marketplace,
    model_detect,
    model_registry,
    node_registry,
    queue_manager,
    recommended_models,
    srt_utils,
)
from bridge import api


class TestSRTUtils(unittest.TestCase):
    def test_parse_srt_standard(self):
        content = (
            "1\n00:00:01,000 --> 00:00:04,500\nHello World!\n\n"
            "2\n00:00:05,100 --> 00:00:08,250\nSecond line subtitle\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".srt", encoding="utf-8", newline="") as f:
            f.write(content)
            temp_path = f.name

        try:
            segments = srt_utils.parse_srt(temp_path)
            self.assertEqual(len(segments), 2)
            self.assertEqual(segments[0]["start"], 1.0)
            self.assertEqual(segments[0]["end"], 4.5)
            self.assertEqual(segments[0]["text"], "Hello World!")
            self.assertEqual(segments[1]["start"], 5.1)
            self.assertEqual(segments[1]["end"], 8.25)
            self.assertEqual(segments[1]["text"], "Second line subtitle")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_parse_srt_crlf_and_dots(self):
        content = (
            "1\r\n00:00:02.000 --> 00:00:05.500\r\nLine 1\r\n\r\n"
            "2\r\n00:00:06.100 --> 00:00:09.250\r\nLine 2\r\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".srt", encoding="utf-8", newline="") as f:
            f.write(content)
            temp_path = f.name

        try:
            segments = srt_utils.parse_srt(temp_path)
            self.assertEqual(len(segments), 2)
            self.assertEqual(segments[0]["start"], 2.0)
            self.assertEqual(segments[0]["end"], 5.5)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestGraphModel(unittest.TestCase):
    def test_default_graph(self):
        graph = node_registry.build_default_graph()
        self.assertIn("input", graph.nodes)
        self.assertIn("stt", graph.nodes)
        self.assertIn("translate", graph.nodes)
        self.assertIn("tts_rvc", graph.nodes)
        self.assertIn("lipsync", graph.nodes)
        self.assertIn("enhance", graph.nodes)
        self.assertIn("output", graph.nodes)

    def test_node_muting(self):
        graph = node_registry.build_default_graph()
        tts_node = graph.nodes["tts_rvc"]
        self.assertTrue(tts_node.enabled)
        tts_node.enabled = False
        self.assertFalse(tts_node.enabled)

    def test_node_removal(self):
        graph = node_registry.build_default_graph()
        # Non-removable fixed backbone node
        removed_fixed = graph.remove_node("stt")
        self.assertFalse(removed_fixed)
        self.assertIn("stt", graph.nodes)


class TestHardwareMonitor(unittest.TestCase):
    def test_hardware_detection(self):
        monitor = hardware_monitor.HardwareMonitor()
        devices = monitor.devices
        self.assertTrue(len(devices) > 0)
        # Should always have CPU at minimum
        cpu_found = any(d.backend == "cpu" for d in devices)
        self.assertTrue(cpu_found)
        default_dev = monitor.default_device_id()
        self.assertIsInstance(default_dev, str)

    def test_system_stats(self):
        monitor = hardware_monitor.HardwareMonitor()
        sample = monitor.sample()
        self.assertIn("cpu_percent", sample)
        self.assertIn("ram_used_gb", sample)
        self.assertIn("ram_total_gb", sample)


class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        patcher = patch.object(model_registry, 'REGISTRY_PATH', os.path.join(self.directory.name, 'models.json'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_registry_lifecycle(self):
        reg = model_registry.ModelRegistry()
        initial_entries = reg.list()
        self.assertIsInstance(initial_entries, list)
        
        # Test active model lookup
        active_stt = reg.get_active("stt")
        # Should return None or entry dict
        if active_stt is not None:
            self.assertIn("id", active_stt)


class TestCredentialStore(unittest.TestCase):
    def test_credential_roundtrip(self):
        test_ref = "test_unit_credential_" + uuid.uuid4().hex
        test_val = "sk-test-secret-12345"
        try:
            credential_store.set_credential(test_ref, test_val)
            retrieved = credential_store.get_credential(test_ref)
            self.assertEqual(retrieved, test_val)
            credential_store.delete_credential(test_ref)
            deleted = credential_store.get_credential(test_ref)
            self.assertIsNone(deleted)
        except credential_store.CredentialError as exc:
            self.skipTest(str(exc))


class TestLanguages(unittest.TestCase):
    def test_language_mappings(self):
        self.assertIn("en", languages.LANGUAGE_NAMES)
        self.assertEqual(languages.LANGUAGE_NAMES["en"], "English")
        self.assertIn("es", languages.LANGUAGE_NAMES)
        self.assertEqual(languages.LANGUAGE_NAMES["es"], "Spanish")


class TestBridgeAPIHelpers(unittest.TestCase):
    def test_safe_download_filename(self):
        self.assertEqual(api._safe_download_filename("http://example.com/models/v1.pth"), "v1.pth")
        self.assertEqual(api._safe_download_filename("http://example.com/path/..\\..\\evil.exe"), "evil.exe")
        self.assertEqual(api._safe_download_filename("http://example.com/"), "model.bin")
        self.assertEqual(api._safe_download_filename("custom_name.bin"), "custom_name.bin")

    def test_parallel_speedup_factor(self):
        factor_cpu = api._parallel_speedup_factor(4, "cpu")
        factor_gpu = api._parallel_speedup_factor(4, "dedicated")
        self.assertGreater(factor_cpu, 0.1)
        self.assertGreater(factor_gpu, 0.1)


class TestQueueManager(unittest.TestCase):
    def test_queue_lifecycle(self):
        qm = queue_manager.QueueManager()
        item1 = qm.add_item("input1.mp4", {"lang": "es"}, "video_dub")
        item2 = qm.add_item("input2.mp4", {"lang": "fr"}, "video_dub")

        self.assertEqual(len(qm.get_items()), 2)
        next_job = qm.get_next_queued()
        self.assertIsNotNone(next_job)
        self.assertEqual(next_job.id, item1["id"])

        qm.update_item(item1["id"], status="processing")
        self.assertEqual(qm.get_items()[0]["status"], "processing")

        qm.update_item(item1["id"], status="completed", progress=100)
        self.assertEqual(qm.get_items()[0]["status"], "completed")

        next_job2 = qm.get_next_queued()
        self.assertEqual(next_job2.id, item2["id"])

        qm.clear_completed()
        self.assertEqual(len(qm.get_items()), 1)


class TestHardwareBenchmark(unittest.TestCase):
    def test_run_benchmark(self):
        mon = hardware_monitor.HardwareMonitor()
        bench = mon.run_benchmark()
        self.assertIn("score", bench)
        self.assertIn("vram_total_mb", bench)
        self.assertIn("recommended_workers", bench)
        self.assertGreater(bench["recommended_workers"], 0)


class TestJanitor(unittest.TestCase):
    def test_janitor_sweep(self):
        # Never sweep the user's project or the suite's shared TEMP directory.
        with tempfile.TemporaryDirectory() as root:
            temp = os.path.join(root, 'legacy-temp')
            os.makedirs(temp)
            obsolete = os.path.join(temp, 'old.wav')
            with open(obsolete, 'wb') as stream:
                stream.write(b'legacy fixture')
            j = janitor.Janitor()
            j.root_dir, j.temp_dir = root, temp
            j.sweep(deep=False)
            self.assertTrue(os.path.isdir(temp))
            self.assertFalse(os.path.exists(obsolete))


class TestPathSafety(unittest.TestCase):
    def test_clean_output_path_generation(self):
        out_mkv = r"C:\mp4_videos\render.mkv"
        base, ext = os.path.splitext(out_mkv)
        clean = f"{base}_CLEAN{ext}"
        self.assertEqual(clean, r"C:\mp4_videos\render_CLEAN.mkv")

    def test_rvc_temp_16k_path_generation(self):
        in_flac = r"C:\audio_files.wav\sample.flac"
        base, _ = os.path.splitext(in_flac)
        temp_16k = f"{base}_16k.wav"
        self.assertEqual(temp_16k, r"C:\audio_files.wav\sample_16k.wav")


if __name__ == "__main__":
    unittest.main(verbosity=2)
