import json
import tempfile
import unittest
from pathlib import Path
from core.runtime_paths import prepare_runtime_files


class RuntimePathsTest(unittest.TestCase):
    def test_existing_session_and_settings_survive_migration_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "settings.json").write_text(json.dumps({"SESSION_FILE": "session.json", "custom": "keep"}))
            payload = b'{"example": "session"}'
            (root / "session.json").write_bytes(payload)
            path = prepare_runtime_files(root)
            self.assertEqual(json.loads(path.read_text())["custom"], "keep")
            self.assertEqual(json.loads(path.read_text())["SESSION_FILE"], "data/session.json")
            self.assertEqual((root / "data/session.json").read_bytes(), payload)
            self.assertFalse((root / "settings.json").exists())
            self.assertFalse((root / "session.json").exists())
            self.assertEqual(prepare_runtime_files(root), path)

    def test_custom_session_location_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "settings.json").write_text(json.dumps({"SESSION_FILE": "custom/session.json"}))
            path = prepare_runtime_files(root)
            self.assertEqual(json.loads(path.read_text())["SESSION_FILE"], "custom/session.json")

    def test_conflicting_sessions_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "settings.json").write_text('{}')
            (root / "session.json").write_text('old')
            (root / "data/session.json").write_text('new')
            with self.assertRaises(ValueError):
                prepare_runtime_files(root)
            self.assertEqual((root / "session.json").read_text(), 'old')
            self.assertEqual((root / "data/session.json").read_text(), 'new')

    def test_invalid_settings_remain_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "settings.json").write_text('broken')
            with self.assertRaises(ValueError):
                prepare_runtime_files(root)
            self.assertEqual((root / "settings.json").read_text(), 'broken')
