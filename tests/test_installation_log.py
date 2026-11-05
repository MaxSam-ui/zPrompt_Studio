import ast,unittest
from pathlib import Path
from queue import Queue
from threading import Thread
from types import SimpleNamespace

class InstallationLogTests(unittest.TestCase):
    def run_check(self, collector, lang):
        logs=['existing log']
        env={'Queue':Queue,'Thread':Thread,'gr':SimpleNamespace(update=lambda **kw:kw),'log':SimpleNamespace(registra=logs.append,ottieni_tutti_i_log=lambda:'\n'.join(logs)),'collect_checks':collector}
        tree=ast.parse(Path('services/installation_ui.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'diagnostics','exec'),env)
        return list(env['installation_log_updates'](lang))

    def test_streams_results_without_erasing_existing_log(self):
        def collect(on_result):
            on_result(('OK','Python','Pronto','Ready'))
            on_result(('CONFIG','Model','Da configurare','Configure'))
        updates=self.run_check(collect,'IT')
        self.assertFalse(updates[0][1]['interactive'])
        self.assertIn('[OK] Python: Pronto',updates[1][0])
        self.assertIn('existing log',updates[-1][0])
        self.assertIn('0 errori, 1 elementi',updates[-1][0])
        self.assertTrue(updates[-1][1]['interactive'])

    def test_exception_is_logged_and_button_restored(self):
        def collect(on_result):raise RuntimeError('test failure')
        updates=self.run_check(collect,'EN')
        self.assertIn('test failure',updates[-1][0])
        self.assertIn('1 errors',updates[-1][0])
        self.assertEqual(updates[-1][1],{'interactive':True,'value':'Check installation'})
