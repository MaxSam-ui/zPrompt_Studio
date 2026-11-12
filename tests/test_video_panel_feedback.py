import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load_function(path,name,env):
    tree=ast.parse((ROOT/path).read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
    return env[name]

class VideoPanelFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.env={'gr':SimpleNamespace(update=lambda **k:k),'comfyui_manager':SimpleNamespace(vlm_interrotto=False)}
    def test_each_operation_highlights_one_panel_and_clears_previous(self):
        fn=load_function('events/eventi_video_generazione.py','avvia_cornici_video',self.env)
        for i,name in enumerate(('subject','timeline','prompt','video')):
            updates=fn(name)
            self.assertEqual([j for j,u in enumerate(updates) if 'elaborazione-attiva' in u['elem_classes']],[i])
            self.assertTrue(all('completato-successo' not in u['elem_classes'] for u in updates))
            self.assertIn('analisi-destra-box',updates[3]['elem_classes'])
    def test_only_success_turns_green(self):
        fn=load_function('events/eventi_video_helpers.py','imposta_classe_post_compilazione_regia',self.env)
        for status in ('Working','❌ Error','⏹ Stopped','⚠ Invalid',''):
            self.assertEqual(fn(status)['elem_classes'],['analisi-col-box'])
        self.assertIn('completato-successo',fn('✅ Done')['elem_classes'])
        self.env['comfyui_manager'].vlm_interrotto=True
        self.assertEqual(fn('✅ Done')['elem_classes'],['analisi-col-box'])
    def test_stop_clears_all_four_panels(self):
        self.env.update(sessione=SimpleNamespace(carica_ultima_sessione=lambda:{}),lingua=SimpleNamespace(LINGUE={'IT':{}}))
        fn=load_function('events/eventi_video_helpers.py','sblocca_tutti_i_pulsanti_video',self.env)
        updates=fn();self.assertEqual(len(updates),11)
        for item in updates[-4:]:
            self.assertNotIn('elaborazione-attiva',item['elem_classes'])
            self.assertNotIn('completato-successo',item['elem_classes'])
    def test_subject_chain_uses_subject_panel_and_shared_reset(self):
        source=(ROOT/'events/eventi_video_generazione.py').read_text(encoding='utf-8')
        part=source.split('# Improve Subject')[1].split('# Generate Dialogues')[0]
        self.assertIn('avvia_cornici_video("subject")',part)
        self.assertIn('outputs=[t3["colonna_soggetto_video"]]',part)
        self.assertNotIn('outputs=[t3["colonna_top_timeline"]]',part)
        for target in ('subject','timeline','prompt','video'):
            self.assertIn('avvia_cornici_video("'+target+'")',source)
