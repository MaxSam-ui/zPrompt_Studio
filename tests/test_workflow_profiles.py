"""Exercise the real MiniMax graph builder without ComfyUI or GPU sampling."""
import copy
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowProfilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.path = self.folder/'example.json'
        self.graph = json.loads((ROOT/'workflows/minimax_h3_api.json').read_text())
        self.profile = json.loads((ROOT/'workflows/minimax_h3_api.profile.json').read_text())
        self.profiles = module_at('tested_profiles', ROOT/'core/workflow_profiles.py')
        core = types.ModuleType('core')
        core.config = types.SimpleNamespace(COMFYUI_DIR=str(self.folder))
        core.log = types.SimpleNamespace(registra=lambda *args: None)
        core.sessione = types.SimpleNamespace()
        self.patch = patch.dict(sys.modules, {
            'core': core,
            'core.workflow_profiles': self.profiles,
            'core.workflow_registry': types.SimpleNamespace(ottieni_parametri_avanzati_workflow=lambda: {}),
            'utils.video_model_prompt': types.SimpleNamespace(minimax_prompt=lambda text: text),
        })
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.adapter = module_at('tested_workflow_video', ROOT/'generators/workflow_video.py')
        self.images = []
        for name in ('first.png', 'last.png', 'middle.png'):
            image = self.folder/name
            image.touch()
            self.images.append(str(image))
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.graph), encoding='utf-8')
        self.profiles.profile_path(self.path).write_text(json.dumps(self.profile), encoding='utf-8')

    def build(self, **kwargs):
        return self.adapter.prepara_workflow_minimax_h3(str(self.path), 'summary:\nScene\n', seed_immagine_base=42, **kwargs)

    def test_modes_and_references(self):
        for mode in ('references', 'native_keyframes'):
            self.profile['image_mode'] = mode
            self.save()
            for first, last, middle in ((False, False, False), (True, False, False), (True, True, False), (True, True, True), (False, True, False)):
                with self.subTest(mode=mode, first=first, last=last, middle=middle):
                    graph = self.build(percorso_immagine_origine=self.images[0] if first else None,
                                       percorso_immagine_destinazione=self.images[1] if last else None,
                                       percorso_immagine_intermedia=self.images[2] if middle else None)
                    node = graph['265']
                    native = mode == 'native_keyframes' and (first or last)
                    self.assertEqual(node['class_type'], 'MiniMaxH3ImageToVideo' if native else 'MiniMaxH3ReferenceToVideo')
                    if native:
                        self.assertEqual('first_frame' in node['inputs'], first)
                        self.assertEqual('last_frame' in node['inputs'], last)
                    else:
                        refs = [k for k in node['inputs'] if k.startswith('ref_images.')]
                        self.assertEqual(len(refs), int(first)+int(last)+int(middle))
        graph = self.build(solo_testo_video=True, percorso_immagine_origine=self.images[0], percorso_immagine_destinazione=self.images[1])
        self.assertFalse(any(k.startswith('ref_images.') for k in graph['265']['inputs']))

    def test_renumbered_graph_produces_equivalent_result_with_lora(self):
        args = dict(percorso_immagine_origine=self.images[0], percorso_immagine_destinazione=self.images[1], percorso_immagine_intermedia=self.images[2], lv1_n='example.safetensors', lv1_s=0.7)
        original = self.build(**args)
        mapping = {k: 'renumbered_'+k for k in self.graph}
        def rename(graph, mapping):
            result = {}
            for key, node in copy.deepcopy(graph).items():
                for name, value in node['inputs'].items():
                    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                        node['inputs'][name] = [mapping.get(value[0], value[0]), value[1]]
                result[mapping.get(key, key)] = node
            return result
        self.graph = rename(self.graph, mapping)
        for spec in self.profile['nodes'].values(): spec['id'] = mapping[spec['id']]
        self.save()
        changed = self.build(**args)
        self.assertEqual(rename(changed, {v:k for k,v in mapping.items()}), original)

    def test_checkpoint_name_does_not_choose_image_mode(self):
        self.profile['image_mode'] = 'references'
        self.graph['192']['inputs']['unet_name'] = 'some_fl2va_name.safetensors'
        self.save()
        self.assertEqual(self.build(percorso_immagine_origine=self.images[0])['265']['class_type'], 'MiniMaxH3ReferenceToVideo')

    def test_capability_and_connection_failures(self):
        self.profile['capabilities']['custom_lora'] = False
        self.save()
        with self.assertRaisesRegex(ValueError, 'custom LoRA'): self.build(lv1_n='test.safetensors')
        self.graph['263']['class_type'] = 'UnexpectedNode'
        self.save()
        with self.assertRaisesRegex(ValueError, 'Profile prompt'): self.build()
        self.graph['263']['class_type'] = 'Text'
        self.graph['265']['inputs']['prompt'] = 'Disconnected prompt'
        self.save()
        with self.assertRaisesRegex(ValueError, 'disconnected'): self.build()

    def test_override_and_generated_id_collision(self):
        folder = self.folder/'custom'
        folder.mkdir()
        custom = copy.deepcopy(self.profile)
        custom['image_mode'] = 'references'
        (folder/self.profiles.profile_path(self.path).name).write_text(json.dumps(custom))
        self.graph['studio_last_image'] = {'class_type':'Text', 'inputs':{'text':'Keep me'}}
        self.save()
        result = self.build(percorso_immagine_origine=self.images[0], percorso_immagine_destinazione=self.images[1])
        self.assertEqual(result['studio_last_image']['inputs']['text'], 'Keep me')
        self.assertEqual(result['265']['class_type'], 'MiniMaxH3ReferenceToVideo')

    def test_missing_or_inconsistent_profile_fails_without_changing_workflow(self):
        before = self.path.read_bytes()
        self.profiles.profile_path(self.path).unlink()
        with self.assertRaisesRegex(ValueError, 'Cannot read workflow profile'): self.build()
        self.assertEqual(self.path.read_bytes(), before)
        self.profile['capabilities']['first_last_frames'] = False
        self.save()
        with self.assertRaisesRegex(ValueError, 'conflicts'): self.build()
        self.profile['capabilities']['first_last_frames'] = True
        self.profile['nodes']['duration']['id'] = self.profile['nodes']['seed']['id']
        self.save()
        with self.assertRaises(ValueError): self.build()

    def test_shipped_profile_can_be_checked_without_sampling(self):
        profile = self.profiles.load_minimax_profile(self.path, self.graph)
        self.profiles.validate_profile_output(self.graph, profile)
        self.graph['226']['inputs']['noise'] = ['does_not_exist', 0]
        self.save()
        with self.assertRaisesRegex(ValueError, 'Broken workflow link'): self.build()


if __name__ == '__main__':
    unittest.main()
