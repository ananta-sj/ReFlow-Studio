"""Restart, merge, validation and recovery of app-owned UI state."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core.ui_preferences import UIPreferences

class UIPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'preferences.json'

    def test_fresh_instance_restores_choices_and_merges_other_writers(self):
        first, second = UIPreferences(self.path), UIPreferences(self.path)
        first.update({'reflow-experience-level': 'advanced'})
        second.update({'reflow-theme': 'light'})
        cfg = {'lang': 'hi', 'sourceLanguage': 'en', 'voice': 'CLONED_USER', 'parallelWorkers': 4}
        first.update({'reflow.renderConfig': json.dumps(cfg)})
        saved = UIPreferences(self.path).all()
        self.assertEqual(saved['reflow-experience-level'], 'advanced')
        self.assertEqual(saved['reflow-theme'], 'light')
        self.assertEqual(json.loads(saved['reflow.renderConfig']), cfg)

    def test_unknown_credentials_and_invalid_render_values_leave_previous_state(self):
        store = UIPreferences(self.path)
        store.update({'reflow-theme': 'dark'})
        original = self.path.read_bytes()
        invalid = [{'api_key': 'secret'}, {'reflow-theme': 'blue'},
                   {'reflow.renderConfig': '[]'}, {'reflow.renderConfig': '{"parallelWorkers":true}'},
                   {'reflow.renderConfig': '{"lang":"invented"}'},
                   {'reflow.renderConfig': '{"device_id":"cuda:0"}'},
                   {'reflow.renderConfig': '{"taskPriority":NaN}'}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                store.update(value)
            self.assertEqual(self.path.read_bytes(), original)

    def test_corruption_retains_bytes_and_recovers_without_touching_other_stores(self):
        self.path.write_bytes(b'{broken')
        self.assertEqual(UIPreferences(self.path).all(), {})
        backups = list(self.path.parent.glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b'{broken')
        UIPreferences(self.path).update({'reflow.tourComplete': 'true'})
        self.assertEqual(UIPreferences(self.path).all(), {'reflow.tourComplete': 'true'})

    def test_failed_publication_preserves_last_saved_preferences(self):
        store = UIPreferences(self.path)
        store.update({'reflow-theme': 'dark'})
        original = self.path.read_bytes()
        with patch('core.json_store.os.replace', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                store.update({'reflow-theme': 'light'})
        self.assertEqual(self.path.read_bytes(), original)

if __name__ == '__main__':
    unittest.main()
