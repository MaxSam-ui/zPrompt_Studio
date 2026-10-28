"""CPU-only checks for editable prompt composition; no model downloads."""
import ast
import importlib.util
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SystemTemplatesTest(unittest.TestCase):
    def setUp(self):
        self.config = types.SimpleNamespace(SUGGESTION_SYSTEM_DIR=str(ROOT / 'suggestions/system'))
        spec = importlib.util.spec_from_file_location('tested_templates', ROOT / 'utils/prompt_templates.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'core': types.SimpleNamespace(config=self.config)}):
            spec.loader.exec_module(self.module)

    def test_every_static_composer_has_matching_placeholders(self):
        count = 0
        for folder in ('services', 'generators', 'events', 'utils'):
            for path in (ROOT / folder).glob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                        continue
                    if node.func.id not in ('compose_system', 'system_template') or not node.args:
                        continue
                    if not isinstance(node.args[0], ast.Constant):
                        continue
                    name = node.args[0].value
                    text = self.module.system_template(name)
                    if node.func.id == 'compose_system':
                        keys = {k.arg for k in node.keywords}
                        required = set(re.findall(r'\{([A-Za-z_][A-Za-z_0-9]*)\}', text))
                        self.assertFalse(required - keys, (str(path), name, required - keys))
                        rendered = self.module.compose_system(name, **{k: 'MIA_PERSONA {literal} [0.0s - 4.0s]' for k in keys})
                        self.assertNotIn('{value_', rendered)
                    count += 1
        self.assertGreater(count, 20)

    def test_override_reload_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.config.SUGGESTION_SYSTEM_DIR = tmp
            (base/'Example.txt').write_text('Default {idea}', encoding='utf-8')
            (base/'custom').mkdir()
            custom = base/'custom/Example.txt'
            custom.write_text('Custom {idea}', encoding='utf-8-sig')
            self.assertEqual(self.module.compose_system('Example.txt', idea='{keep_literal}'), 'Custom {keep_literal}')
            custom.write_text('Changed {idea}', encoding='utf-8')
            self.assertEqual(self.module.compose_system('Example.txt', idea='scene'), 'Changed scene')
            custom.unlink()
            self.assertEqual(self.module.compose_system('Example.txt', idea='scene'), 'Default scene')

    def test_invalid_files_do_not_inject_hidden_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.config.SUGGESTION_SYSTEM_DIR = tmp
            with self.assertRaises(ValueError): self.module.system_template('Missing.txt')
            path = Path(tmp)/'Empty.txt'
            path.write_text('', encoding='utf-8')
            with self.assertRaises(ValueError): self.module.system_template('Empty.txt')
            self.assertEqual(self.module.system_template('Empty.txt', allow_empty=True), '')
            path.write_text('{unknown}', encoding='utf-8')
            with self.assertRaises(ValueError): self.module.compose_system('Empty.txt', idea='scene')

    def test_all_shipped_templates_render_without_recursive_substitution(self):
        for path in (ROOT/'suggestions/system').glob('*.txt'):
            text = path.read_text(encoding='utf-8-sig')
            keys = set(re.findall(r'\{([A-Za-z_][A-Za-z_0-9]*)\}', text))
            result = self.module.compose_system(path.name, **{k: '{literal_user_text}' for k in keys})
            self.assertTrue(result.strip(), path.name)
            if keys: self.assertIn('{literal_user_text}', result)

    def test_model_and_reference_branches_preserve_source(self):
        spec = importlib.util.spec_from_file_location('tested_video_prompt', ROOT/'utils/video_model_prompt.py')
        video = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(video)
        source = 'MIA_PERSONA walks. [0.0s - 4.0s] Static camera. Water sound.'
        with patch.dict(sys.modules, {'utils.prompt_templates': self.module}):
            for references in (0, 1, 2):
                prompt = video.minimax_compiler_instruction(source, references, direct=True)
                self.assertIn(source, prompt)
                if references:
                    self.assertIn(f'<Picture {references}>', prompt)
                else:
                    self.assertNotIn('<Picture 1>', prompt)
            for template in ('Timeline_First_Last_Context.txt', 'Video_First_Last_Context.txt'):
                context = self.module.compose_system(template, prompt_img='START_ANCHOR', desc_last_frame='END_ANCHOR')
                self.assertIn('START_ANCHOR', context)
                self.assertIn('END_ANCHOR', context)

    def test_vision_modes_and_optional_rules(self):
        self.config.leggi_contenuto_suggerimento = lambda *_: 'Selected watercolor style'
        self.config.SUGGESTION_VISION_DIR = 'unused'
        for text_only in (False, True):
            prompt = self.module.build_vision_prompt('style', text_only=text_only, max_tokens=512)
            self.assertIn('Selected watercolor style', prompt)
            self.assertIn('512', prompt)
            self.assertIn('SCENE AND STYLE PRIORITIES', prompt)


if __name__ == '__main__':
    unittest.main()
