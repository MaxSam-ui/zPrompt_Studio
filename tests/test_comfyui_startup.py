import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import comfyui_setup_window as setup
from core.comfyui_setup import save_portable


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.defaults = {'COMFYUI_DIR': '', 'COMFYUI_URL': 'http://localhost:8188', 'other': 42}
        (self.root / 'config/settings.example.json').write_text(json.dumps(self.defaults))

    def portable(self):
        folder = self.root / 'Portable'
        for name in ('python_embeded/python.exe', 'ComfyUI/main.py'):
            p = folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        return folder

    def test_first_save_preserves_defaults_before_main_starts(self):
        target, defaults = setup.load_settings(self.root)
        self.assertFalse(target.exists())
        folder = self.portable()
        save_portable(str(folder / 'ComfyUI'), self.root, target, defaults=defaults)
        _, saved = setup.load_settings(self.root)
        self.assertEqual(saved['COMFYUI_DIR'], str(folder.resolve()))
        self.assertEqual(saved['other'], 42)
        self.assertEqual(saved['COMFYUI_URL'], self.defaults['COMFYUI_URL'])

    def test_remote_server_skips_setup(self):
        with patch.object(setup, 'server_available', return_value=True), patch.object(setup, 'show_setup') as dialog:
            self.assertEqual(setup.main(self.root), 0)
            dialog.assert_not_called()

    def test_valid_local_folder_skips_setup(self):
        folder = self.portable()
        (self.root / 'settings.json').write_text(json.dumps({'COMFYUI_DIR': str(folder)}))
        with patch.object(setup, 'server_available', return_value=False), patch.object(setup, 'show_setup') as dialog:
            self.assertEqual(setup.main(self.root), 0)
            dialog.assert_not_called()

    def test_cancel_stops_launcher_without_creating_settings(self):
        with patch.object(setup, 'server_available', return_value=False), patch.object(setup, 'show_setup', return_value=2):
            self.assertEqual(setup.main(self.root), 2)
        self.assertFalse((self.root / 'data/settings.json').exists())

    def test_unavailable_dialog_allows_manual_configuration(self):
        with patch.object(setup, 'server_available', return_value=False), patch.object(setup, 'show_setup', side_effect=RuntimeError('No display')):
            self.assertEqual(setup.main(self.root), 0)
        self.assertFalse((self.root / 'data/settings.json').exists())

    def test_existing_private_settings_win_over_example(self):
        (self.root / 'data').mkdir()
        (self.root / 'settings.json').write_text('{"other":1}')
        (self.root / 'data/settings.json').write_text('{"other":2}')
        _, settings = setup.load_settings(self.root)
        self.assertEqual(settings['other'], 2)


if __name__ == '__main__':
    unittest.main()
