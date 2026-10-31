"""Run existing backend checks without destructive janitor/keyring tests."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'core')]
classes = ('TestSRTUtils', 'TestGraphModel', 'TestHardwareMonitor', 'TestModelRegistry',
           'TestLanguages', 'TestBridgeAPIHelpers', 'TestQueueManager', 'TestPathSafety')
suite = unittest.TestSuite()
for name in classes:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_suite.' + name))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_model_assets'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_render_queue'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_output_integrity'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_speech_integrity'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_translation_integrity'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_transcription_metadata'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_source_language'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_speech_language'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_cancellation'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_parallel_speech'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_deletion_safety'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_queue_session'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_persistence_safety'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_architecture_contracts'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_visual_contracts'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_feature_session'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_generation_control'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_f5_reference'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_http_media'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_voice_mastering'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_loudness'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_model_contracts'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_cue_review'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_pipeline_foundation'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_stage_checkpoints'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_dialogue_adaptation'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_dialogue_supervision'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('dev.test_dialogue_connections'))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
