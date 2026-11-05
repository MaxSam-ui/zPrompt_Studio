import ast,json,unittest
from pathlib import Path
from types import SimpleNamespace

class AnalysisDescriptionTests(unittest.TestCase):
    def extract(self,path,name,env):
        tree=ast.parse(Path(path).read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),path,'exec'),env)
        return env[name]

    def test_blank_text_returns_instruction_before_model_import(self):
        for lang in ('it','en'):
            d=json.loads(Path('languages/'+lang+'.json').read_text(encoding='utf-8'))
            env={'sessione':SimpleNamespace(carica_ultima_sessione=lambda:{'lingua_selezionata':lang.upper()}),'lingua':SimpleNamespace(LINGUE={lang.upper():d})}
            fn=self.extract('utils/media_utils.py','gestore_analisi_adattivo',env)
            for empty in ('',None,' \n\t '):
                self.assertEqual(list(fn(None,'',empty,'unused',True)),[d['analysis_description_required']])

    def test_labels_and_placeholder_switch_in_both_languages(self):
        fn=self.extract('core/lingua.py','analysis_hints_options',{})
        for lang in ('it','en'):
            d=json.loads(Path('languages/'+lang+'.json').read_text(encoding='utf-8'))
            self.assertEqual(fn(d,True)['label'],d['analysis_description_label'])
            self.assertEqual(fn(d,False)['label'],d['analysis_extra_label'])
            self.assertTrue(fn(d,True)['placeholder'])
