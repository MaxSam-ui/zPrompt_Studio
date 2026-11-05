import json
import tempfile
import unittest
from pathlib import Path
from core.comfyui_setup import resolve_portable, save_portable

class PortableSetupTests(unittest.TestCase):
    def test_root_and_nested_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('python_embeded/python.exe', 'ComfyUI/main.py'):
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.touch()
            self.assertEqual(resolve_portable(str(root), tmp), str(root.resolve()))
            self.assertEqual(resolve_portable(str(root / 'ComfyUI'), tmp), str(root.resolve()))
            settings = root / 'settings.json'
            settings.write_text(json.dumps({'COMFYUI_URL': 'http://remote:8188', 'other': 42}))
            save_portable(str(root), tmp, settings)
            saved = json.loads(settings.read_text())
            self.assertEqual(saved['other'], 42)
            self.assertEqual(saved['COMFYUI_URL'], 'http://remote:8188')

    def test_invalid_does_not_modify_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            settings.write_text('{"other": 42}')
            for invalid in ('', tmp, str(Path(tmp) / 'missing')):
                with self.assertRaises(ValueError):
                    save_portable(invalid, tmp, settings)
                self.assertEqual(settings.read_text(), '{"other": 42}')
