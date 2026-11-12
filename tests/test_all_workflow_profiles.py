"""CPU graph regressions for every non-MiniMax shipped workflow."""
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILES = {'zimage':'z_image_turbo_api.json', 'flux2':'flux2_klein_api.json',
         'krea2':'krea2_turbo_api.json', 'krea2_edit':'krea2_turbo_edit_api.json',
         'qwen21_edit':'qwen_image_2.1_edit_api.json', 'ltx25':'ltx2.5_api.json'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cases():
    result = []
    for adapter, suffix in (('zimage','z_image'), ('flux2','flux2'), ('krea2','krea2')):
        for lora in (False, True):
            loras = dict(l1_n='test.safetensors' if lora else '-',l1_s=0.7,l2_n='-',l2_s=1,l3_n='-',l3_s=1)
            result.append((f'{adapter}_text_{lora}',adapter,'prepara_workflow_'+suffix,dict(prompt_testo='A blue ceramic bowl',larghezza=1024,altezza=768,copie=2,seed_mode='fixed',custom_seed=42,**loras)))
            result.append((f'{adapter}_refine_{lora}',adapter,'prepara_workflow_img2img_'+suffix,dict(input_image_filename='sample.png',prompt_testo='A green ceramic bowl',seed=42,**loras)))
    result.append(('krea_edit','krea2_edit','prepara_workflow_krea2_edit',dict(input_image_filename='sample.png',prompt_testo='Change the color',steps=8,sampler_name='euler',scheduler='normal',seed=42,grounding_px=768)))
    for lora in (False,True):
        result.append((f'qwen_edit_{lora}','qwen21_edit','prepara_workflow_qwen21_edit',dict(input_filename='sample.png',prompt='Change the color',steps=30,sampler_name='euler',scheduler='simple',seed=42,loras=[('test.safetensors',0.7)] if lora else [])))
    for mode in ('text','first','first_last','middle'):
        for lora in (False,True):
            result.append((f'ltx_{mode}_{lora}','ltx25','prepara_workflow_ltx_video',dict(prompt_video='A person walks. Audio: wind.',lv1_n='test.safetensors' if lora else '-',lv1_s=0.7,lv2_n='-',lv2_s=1,lv3_n='-',lv3_s=1,seed_immagine_base=42,solo_testo_video=mode=='text',percorso_immagine_origine='sample.png' if mode!='text' else None,percorso_immagine_destinazione='last.png' if mode in ('first_last','middle') else None,percorso_immagine_intermedia='middle.png' if mode=='middle' else None)))
    return result


class AllProfilesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        for filename in FILES.values():
            for path in (ROOT/'workflows'/filename, (ROOT/'workflows'/filename).with_suffix('.profile.json')):
                (self.folder/path.name).write_bytes(path.read_bytes())
        core = types.ModuleType('core')
        core.config = types.SimpleNamespace(COMFYUI_DIR=str(self.folder))
        core.log = types.SimpleNamespace(registra=lambda *args: None)
        core.sessione = types.SimpleNamespace()
        profiles = load('tested_profiles_all',ROOT/'core/workflow_profiles.py')
        self.profiles = profiles
        self.patch = patch.dict(sys.modules, {
            'core':core, 'core.workflow_profiles':profiles,
            'core.workflow_registry':types.SimpleNamespace(ottieni_parametri_avanzati_workflow=lambda:{}),
            'generators.metadata_extractor':types.SimpleNamespace(estrai_info_da_immagine=lambda *_: ('','')),
            'utils.video_model_prompt':types.SimpleNamespace(ltx_prompt=lambda text:text),
            'utils.prompt_templates':types.SimpleNamespace(system_template=lambda *a,**k:'test negative'),
        })
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.video=load('tested_video_all',ROOT/'generators/workflow_video.py')
        self.patch2=patch.dict(sys.modules,{'generators.workflow_video':self.video})
        self.patch2.start(); self.addCleanup(self.patch2.stop)
        self.image=load('tested_image_all',ROOT/'generators/workflow.py')

    def build(self, case):
        _,adapter,fn,args=case
        module=self.video if adapter=='ltx25' else self.image
        return getattr(module,fn)(str(self.folder/FILES[adapter]),**args)

    def test_default_graphs_match_previous_release(self):
        expected=json.loads((ROOT/'tests/workflow_graph_hashes.json').read_text(encoding='utf-8'))
        for case in cases():
            with self.subTest(case=case[0]):
                graph=self.build(case)
                digest=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
                self.assertEqual(digest,expected[case[0]])

    def test_ltx_builder_uses_cleaned_prompt(self):
        from test_video_prompt_dialects import REF
        prompts=load('real_ltx_prompt_adapter',ROOT/'utils/video_model_prompt.py')
        case=next(c for c in cases() if c[0]=='ltx_text_False')
        args=dict(case[3],prompt_video=REF)
        with patch.dict(sys.modules,{'utils.video_model_prompt':prompts}):
            graph=self.video.prepara_workflow_ltx_video(str(self.folder/FILES['ltx25']),**args)
        payload=graph['5']['inputs']['text']
        self.assertNotIn('<Subject',payload)
        self.assertNotIn('<Picture',payload)
        self.assertIn('MIA_PERSONA',payload)
        self.assertIn('Aspettami!',payload)
        self.assertIn('Wind and footsteps.',payload)

    def test_all_graphs_can_be_renumbered(self):
        expected={case[0]:self.build(case) for case in cases()}
        reverse={}
        for adapter,filename in FILES.items():
            path=self.folder/filename
            graph=json.loads(path.read_text(encoding='utf-8'))
            mapping={key:'external_'+key for key in graph}
            graph=self.profiles._remap_graph(graph,mapping)
            path.write_text(json.dumps(graph), encoding='utf-8')
            path=path.with_suffix('.profile.json'); profile=json.loads(path.read_text(encoding='utf-8'))
            for spec in profile['nodes'].values(): spec['id']=mapping[spec['id']]
            path.write_text(json.dumps(profile), encoding='utf-8')
            reverse[adapter]={v:k for k,v in mapping.items()}
        for case in cases():
            with self.subTest(case=case[0]):
                actual=self.profiles._remap_graph(self.build(case),reverse[case[1]])
                self.assertEqual(actual,expected[case[0]])

    def test_capability_rejection(self):
        path=(self.folder/FILES['qwen21_edit']).with_suffix('.profile.json')
        profile=json.loads(path.read_text(encoding='utf-8')); profile['capabilities']['custom_lora']=False
        path.write_text(json.dumps(profile), encoding='utf-8')
        case=next(c for c in cases() if c[0]=='qwen_edit_True')
        with self.assertRaisesRegex(ValueError,'custom_lora'): self.build(case)

    def test_diagnostics_all_profiles(self):
        for filename in FILES.values():
            path=self.folder/filename
            profile=self.profiles.check_workflow_profile(path,json.loads(path.read_text(encoding='utf-8')))
            self.assertIn(profile['adapter'],FILES)

    def test_missing_slots_and_disconnected_prompt_are_rejected(self):
        path=self.folder/FILES['flux2']; sidecar=path.with_suffix('.profile.json')
        profile=json.loads(sidecar.read_text(encoding='utf-8')); del profile['nodes']['sampling']
        sidecar.write_text(json.dumps(profile), encoding='utf-8')
        case=next(c for c in cases() if c[0]=='flux2_text_False')
        with self.assertRaisesRegex(ValueError,'slots'): self.build(case)
        sidecar.write_bytes((ROOT/'workflows'/sidecar.name).read_bytes())
        graph=json.loads(path.read_text(encoding='utf-8')); graph['13']['inputs']['positive']='disconnected'; graph['13']['inputs']['negative']='disconnected'
        path.write_text(json.dumps(graph), encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'disconnected'): self.build(case)

    def test_extra_nodes_survive_reserved_id_collisions(self):
        path=self.folder/FILES['flux2']; graph=json.loads(path.read_text(encoding='utf-8'))
        graph['90']={'class_type':'Text','inputs':{'text':'User node'}}
        path.write_text(json.dumps(graph), encoding='utf-8')
        case=next(c for c in cases() if c[0]=='flux2_refine_False')
        result=self.build(case)
        self.assertEqual(result['90']['inputs']['text'],'User node')
        self.assertEqual(result['studio_90']['class_type'],'LoadImage')

    def test_image_metadata_survives_renumbering(self):
        extractor=load('tested_metadata',ROOT/'generators/metadata_extractor.py')
        for case in cases():
            if case[1]=='ltx25': continue
            with self.subTest(case=case[0]):
                graph=self.build(case)
                graph=self.profiles._remap_graph(graph,{k:'renamed_'+k for k in graph})
                image=types.SimpleNamespace(info={'prompt':json.dumps(graph),'workflow':'{}'})
                text,seed=extractor.estrai_info_da_immagine(image)
                self.assertEqual(text,case[3].get('prompt_testo',case[3].get('prompt')))
                self.assertEqual(seed,42)


if __name__=='__main__': unittest.main()
