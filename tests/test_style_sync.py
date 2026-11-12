import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class StyleSyncTest(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'events/eventi_analisi.py'
        self.tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == 'sincronizza_stile_video')
        self.saved = []
        namespace = {
            'gr': SimpleNamespace(update=lambda **kwargs: kwargs),
            'config': SimpleNamespace(SUGGESTION_DIRECTION_DIR='direction', elenca_suggerimenti=lambda _: ['04_Science_Fiction', 'Custom']),
            'sessione': SimpleNamespace(salva_sessione=self.saved.append),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        self.sync = namespace['sincronizza_stile_video']

    def test_matching_styles_only_update_direction(self):
        for name in ('04_Science_Fiction', 'Custom', '-'):
            self.assertEqual(self.sync(name)['value'], name)
            self.assertEqual(self.saved[-1], {'suggerimento_regia_selezionato': name})

    def test_unmatched_presets_preserve_video_choice(self):
        for name in ('Image only', None, ''):
            self.assertEqual(self.sync(name), {})
        self.assertEqual(self.saved, [])

    def test_only_explicit_input_triggers_sync(self):
        calls = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call) and any(k.arg == 'fn' and isinstance(k.value, ast.Name) and k.value.id == 'sincronizza_stile_video' for k in n.keywords)]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].func.attr, 'input')
