import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('installation_hints', Path(__file__).resolve().parents[1] / 'services/installation_check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModelLocationHintTest(unittest.TestCase):
    def test_subfolder_and_multiple_candidates(self):
        choices = ['Qwen\\encoder.safetensors', 'Other/encoder.safetensors']
        it, en = module.model_location_hint('encoder.safetensors', choices)
        for text in (it, en):
            self.assertIn('Qwen/encoder.safetensors', text)
            self.assertIn('Other/encoder.safetensors', text)
        self.assertIn('no path was changed', en)
        self.assertEqual(choices[0], 'Qwen\\encoder.safetensors')

    def test_missing_model_points_to_help(self):
        it, en = module.model_location_hint('encoder.safetensors', ['different.safetensors'])
        self.assertIn('non elencato', it)
        self.assertIn('Help', en)
        self.assertIn('restart ComfyUI', en)
