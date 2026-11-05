import ast
import os
import tempfile
import unittest
from pathlib import Path

class LoraDirectoryTests(unittest.TestCase):
    def load_helpers(self, root, settings):
        tree=ast.parse(Path('core/config.py').read_text(encoding='utf-8'))
        names={'_lora_dir','ottieni_lora_zimage_dirs','ottieni_lora_qwen21_dir'}
        module=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
        env={'os':os,'_config':settings,'COMFYUI_DIR':root,'_rendi_percorso_assoluto':lambda p:os.path.abspath(os.path.join(root,p))}
        exec(compile(module,'config_helpers','exec'),env)
        return env

    def test_new_install_single_directory(self):
        with tempfile.TemporaryDirectory() as root:
            env=self.load_helpers(root,{})
            self.assertEqual(env['ottieni_lora_zimage_dirs'](),[os.path.join(root,'ComfyUI','models','loras','Z-Image')])
            self.assertTrue(env['ottieni_lora_qwen21_dir']().endswith('Qwen2.1'))

    def test_existing_and_custom_legacy_sources_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            legacy=Path(root)/'ComfyUI/models/loras/Z-Image1';legacy.mkdir(parents=True)
            env=self.load_helpers(root,{'LORA_ZIMAGE_DIR_2':'custom'})
            self.assertEqual(env['ottieni_lora_zimage_dirs'](),[os.path.join(root,'ComfyUI','models','loras','Z-Image'),str(legacy),os.path.join(root,'custom')])
