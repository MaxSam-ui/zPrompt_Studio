import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

def function_source(path,name):
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    return ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name],type_ignores=[])

class VideoLoraSelectionTests(unittest.TestCase):
    def test_windows_paths_and_zero_strength_survive_switch(self):
        env={'Any':object,'List':list}
        exec(compile(function_source('core/workflow_registry.py','normalizza_lora_per_scelte'),'normalizer','exec'),env)
        for model,suffix in [('LTX-Video 2.5',''),('MiniMax H3','_minimax')]:
            state={'lora_video1_name'+suffix:'family\\model.safetensors','lora_video1_str'+suffix:0.0,'lora_video2_name'+suffix:'missing.safetensors'}
            env.update(gr=SimpleNamespace(update=lambda **kwargs:kwargs),
                       sessione=SimpleNamespace(salva_sessione=state.update,carica_ultima_sessione=lambda:dict(state)),
                       workflow_registry=SimpleNamespace(ottieni_lora_disponibili_video=lambda model:['-','family/model.safetensors'],normalizza_lora_per_scelte=env['normalizza_lora_per_scelte']))
            exec(compile(function_source('events/eventi_video_generazione.py','gestisci_cambio_modello_video'),'video_callback','exec'),env)
            result=env['gestisci_cambio_modello_video'](model)
            self.assertEqual(result[4]['value'],'family/model.safetensors')
            self.assertEqual(result[5]['value'],'-')
            self.assertEqual(result[7]['value'],0.0)
