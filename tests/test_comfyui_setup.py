import json
import tempfile
import unittest
from pathlib import Path
from core.comfyui_setup import resolve_portable, save_portable
from core.comfyui_setup import needs_setup, server_available, choose_folder
from unittest.mock import patch, MagicMock

class PortableSetupTests(unittest.TestCase):
    def test_picker_cancel_and_unicode_path(self):
        for path in ('', 'C:/Users/José/ComfyUI portable'):
            with patch('subprocess.run', return_value=MagicMock(stdout=json.dumps(path))):
                self.assertEqual(choose_folder(),path)

    def test_failed_atomic_save_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('python_embeded/python.exe','ComfyUI/main.py'):
                p=Path(tmp)/name;p.parent.mkdir(exist_ok=True);p.touch()
            settings=Path(tmp)/'settings.json';settings.write_text('{"other": 42}')
            with patch('core.comfyui_setup.os.replace',side_effect=PermissionError):
                with self.assertRaises(PermissionError):save_portable(tmp,tmp,settings)
            self.assertEqual(settings.read_text(),'{"other": 42}')
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

    def test_online_server_does_not_require_portable_folder(self):
        with patch('core.comfyui_setup.server_available', return_value=True):
            self.assertFalse(needs_setup('', '.', 'http://server:8188'))

    def test_missing_folder_shows_setup_only_if_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('core.comfyui_setup.server_available', return_value=False):
                self.assertTrue(needs_setup(tmp, tmp, 'http://localhost:8188'))
                for name in ('python_embeded/python.exe', 'ComfyUI/main.py'):
                    p=Path(tmp)/name
                    p.parent.mkdir(exist_ok=True)
                    p.touch()
                self.assertFalse(needs_setup(tmp, tmp, 'http://localhost:8188'))

    def test_server_probe_rejects_wrong_service_and_timeout(self):
        response=MagicMock()
        response.__enter__.return_value=response
        with patch('urllib.request.urlopen', return_value=response):
            for body,expected in ((b'{"system": {}}',True),(b'{}',False),(b'[]',False),(b'<html>',False)):
                response.read.return_value=body
                self.assertEqual(server_available('http://localhost:8188'),expected)
        with patch('urllib.request.urlopen', side_effect=TimeoutError):
            self.assertFalse(server_available('http://localhost:8188'))
        self.assertFalse(server_available('file:///tmp'))

    def test_corrupt_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('python_embeded/python.exe','ComfyUI/main.py'):
                p=Path(tmp)/name;p.parent.mkdir(exist_ok=True);p.touch()
            settings=Path(tmp)/'settings.json'
            for original in ('{broken','[]'):
                settings.write_text(original)
                with self.assertRaises(ValueError):save_portable(tmp,tmp,settings)
                self.assertEqual(settings.read_text(),original)

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
