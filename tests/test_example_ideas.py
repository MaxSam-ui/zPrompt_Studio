import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
class ExampleIdeaTests(unittest.TestCase):
    def test_selection_restores_previous_idea(self):
        tree=ast.parse((ROOT/'events/eventi_video_helpers.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='carica_suggerimento_sceneggiatura')
        env={'config':SimpleNamespace(SUGGESTION_SCREENPLAY_DIR='examples',leggi_contenuto_suggerimento=lambda *args:'Example story')}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'helper','exec'),env)
        fn=env[node.name];text,state=fn('example','My own idea',{})
        self.assertEqual(text,'Example story')
        self.assertEqual(fn('-',text,state)[0],'My own idea')
    def test_programmatic_menu_refresh_does_not_load_example(self):
        tree=ast.parse((ROOT/'events/eventi_video_generazione.py').read_text(encoding='utf-8'))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and any(k.arg=='fn' and isinstance(k.value,ast.Name) and k.value.id=='on_screenplay_preset_change' for k in n.keywords)]
        self.assertEqual(len(calls),1);self.assertEqual(calls[0].func.attr,'input')
