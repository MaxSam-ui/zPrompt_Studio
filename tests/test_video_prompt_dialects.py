"""Prompt transport regressions: no models or GPU required."""
import ast
import os
from collections import defaultdict
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

BASE = """integrated_multimodal_description:
[0.0s - 3.3s] [Shot 1] MIA_PERSONA walks with a static camera.
[3.3s - 6.6s] She pauses, then (S1) says <d>[Italian] Aspettami!</d>
[6.6s - 10.0s] She turns. No cuts. No music.

overall_soundscape:
Wind and footsteps.

non_diegetic_music:
None"""
REF = """subject_definitions:
<Subject 1> is MIA_PERSONA, a woman wearing a yellow coat in <Picture 1>.
<Subject 2>: a red bicycle.

summary:
The woman walks toward her bicycle.

retention_analysis:
Preserve the coat and bicycle color.

detailed_description:
[0.0s - 5.0s] <Subject 1> walks toward <Subject 2>.
[5.0s - 10.0s] She says <d>[Italian] Aspettami!</d> and touches <Subject 2>.

overall_soundscape:
Wind and footsteps.

non_diegetic_music:
None"""

class VideoPromptDialectsTest(unittest.TestCase):
    def setUp(self):
        core = types.SimpleNamespace(config=types.SimpleNamespace(SUGGESTION_SYSTEM_DIR=str(ROOT/'suggestions/system')))
        with patch.dict(sys.modules, {'core': core}):
            templates = load('dialect_templates', ROOT/'utils/prompt_templates.py')
        self.prompts = load('dialect_prompts', ROOT/'utils/video_model_prompt.py')
        self.patch = patch.dict(sys.modules, {'utils.prompt_templates': templates})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_profile_selection_and_explicit_hybrid_override(self):
        for mode, expected in [('native_keyframes','base'),('references','reference')]:
            self.assertEqual(self.prompts.minimax_format({'image_mode':mode}), expected)
        self.assertEqual(self.prompts.minimax_format({'image_mode':'native_keyframes','prompt_format':'reference'}),'reference')
        with self.assertRaises(ValueError): self.prompts.minimax_format({'prompt_format':'guess'})

    def test_compiler_selects_schema_before_generation(self):
        for mode, field in [('base','integrated_multimodal_description'),('reference','subject_definitions')]:
            result = self.prompts.minimax_compiler_instruction('MIA_PERSONA [0.0s - 10.0s]',2,format=mode)
            self.assertIn(field,result)
            self.assertIn('MIA_PERSONA [0.0s - 10.0s]',result)
        self.assertNotIn('six section',self.prompts.minimax_compiler_instruction('scene',0,format='base'))

    def test_parsers_reject_mixed_empty_duplicate_and_wrong_formats(self):
        self.assertEqual(len(self.prompts.minimax_sections(BASE)),3)
        self.assertEqual(len(self.prompts.minimax_sections(REF)),6)
        self.assertIsNone(self.prompts.minimax_sections(BASE,format='reference'))
        self.assertIsNone(self.prompts.minimax_sections(REF,format='base'))
        self.assertIsNone(self.prompts.minimax_sections('subject_definitions: x\n'+BASE))
        self.assertIsNone(self.prompts.minimax_sections(BASE+'\nnon_diegetic_music: extra'))
        self.assertIsNone(self.prompts.minimax_sections(BASE.replace('non_diegetic_music:\nNone','non_diegetic_music:')))

    def test_base_modes_align_only_connected_keyframes(self):
        for first,last in [(False,False),(True,False),(True,True),(False,True)]:
            with self.subTest(first=first,last=last):
                result=self.prompts.minimax_payload(BASE,format='base',duration=10,first=first,last=last)
                self.assertEqual(len(self.prompts.minimax_sections(result)),3)
                self.assertIn('From 3.3 to 6.6 seconds',result)
                self.assertIn('<d>[Italian] Aspettami!</d>',result)
                self.assertIn('non_diegetic_music: N/A',result)
                self.assertNotIn('[Shot 2]',result) # interval != cut
                if not first and not last:
                    self.assertTrue(result.startswith('integrated_multimodal_description:'))
                    self.assertNotIn('Picture',result)
                else:
                    self.assertIn('\n\nintegrated_multimodal_description:',result)
                if last: self.assertIn('10.00-second',result)
                if last and not first: self.assertIn('<Picture 1>',result)

    def test_native_middle_guide_does_not_invent_picture_three(self):
        result=self.prompts.minimax_payload(BASE,format='base',duration=10,first=True,last=True,middle=True)
        self.assertIn('intermediate keyframe',result)
        self.assertNotIn('Picture 3',result)

    def test_reference_picture_roles_stay_ordered(self):
        result=self.prompts.minimax_payload(REF,format='reference',duration=10,first=True,last=True,middle=True)
        self.assertIn('<Picture 1>: opening',result)
        self.assertIn('<Picture 2>: ending',result)
        self.assertIn('<Picture 3>: intermediate',result)
        self.assertIn('From 5 to 10 seconds',result)
        self.assertIn('<Subject 2>',result)
        with self.assertRaises(ValueError): self.prompts.minimax_payload(BASE,format='reference',duration=10)

    def test_legacy_reference_to_native_preserves_identities_and_audio(self):
        result=self.prompts.minimax_payload(REF,format='base',duration=10,first=True,last=True)
        self.assertIn('MIA_PERSONA',result)
        self.assertIn('yellow coat',result)
        self.assertIn('red bicycle',result)
        self.assertNotIn('<Subject',result)
        self.assertIn('Wind and footsteps.',result)

    def test_ltx_resolves_subjects_without_rewriting_spoken_words(self):
        result=self.prompts.ltx_prompt(REF)
        self.assertNotIn('<Subject',result)
        self.assertNotIn('<Picture',result)
        self.assertNotIn('<d>',result)
        self.assertIn('MIA_PERSONA',result)
        self.assertIn('red bicycle',result)
        self.assertIn('In Italian: "Aspettami!"',result)
        self.assertIn('From 5 to 10 seconds',result)

    def test_undefined_subject_fails_instead_of_losing_identity(self):
        with self.assertRaises(ValueError): self.prompts.ltx_prompt(REF.replace('<Subject 2>:', '<Subject 3>:'))
        with self.assertRaises(ValueError): self.prompts.ltx_prompt('A scene with <Subject 8>.')

    def test_literal_text_and_silence_are_preserved(self):
        result=self.prompts.ltx_prompt(BASE.replace('Aspettami!','Read <Subject 8> [0.0s - 3.0s].').replace('Wind and footsteps.','Complete silence.'))
        self.assertIn('"Read <Subject 8> [0.0s - 3.0s]."',result)
        self.assertIn('Complete silence.',result)

    def test_old_prose_music_is_not_silently_disabled(self):
        result=self.prompts.minimax_payload('A dancer. Audio: piano music.',format='base',duration=4)
        self.assertIn('piano music',result)
        self.assertNotIn('non_diegetic_music: N/A',result)

    def test_cut_timestamp_uses_decimal_timeline_boundary(self):
        prompt=BASE.replace('She pauses, then', '[Shot 2] At 00:04.000, the camera cuts to a close-up. She pauses, then')
        result=self.prompts.minimax_payload(prompt,format='base',duration=10,first=True,last=True)
        self.assertIn('[Shot 2] At 00:03.300,',result)
        self.assertNotIn('00:04.000',result)
        self.assertIn('Picture 2 (from Shot 2)',result)
        self.assertIn('the camera cuts to a close-up',result)

    def test_summary_constraints_survive_conversion(self):
        prompt=REF.replace('Preserve the coat and bicycle color.', 'Preserve the coat and bicycle color. No camera cuts.')
        for result in (self.prompts.ltx_prompt(prompt),self.prompts.minimax_payload(prompt,format='base',duration=10)):
            self.assertIn('No camera cuts.',result)
            self.assertIn('yellow coat',result)

    def test_ui_timing_remains_valid_before_transport(self):
        from utils.director_prompt import align_director_prompt
        from utils.video_preflight import validate_video_request
        parts=self.prompts.minimax_sections(BASE)
        scenes=[[3.3,'Medium','Static'],[3.3,'Medium','Static'],[3.4,'Medium','Static']]
        parts['integrated_multimodal_description']=align_director_prompt(parts['integrated_multimodal_description'],scenes)
        prompt='\n\n'.join(f'{k}:\n{v}' for k,v in parts.items())
        self.assertIsNone(validate_video_request(prompt,10))
        self.assertIsNotNone(validate_video_request(prompt,12))
        result=self.prompts.minimax_payload(prompt,format='base',duration=10)
        self.assertIn('From 6.6 to 10 seconds',result)
        self.assertIn('[Medium; Static]',result)

    def test_director_compiles_selected_schema_in_one_call(self):
        source=ast.parse((ROOT/'services/director_ai.py').read_text(encoding='utf-8'))
        functions=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('passa_timeline_a_gemma','cronologia_regia_testo')]
        for mode,draft in [('native_keyframes',BASE),('references',REF),
                           ('native_keyframes','Incomplete model response'),
                           ('native_keyframes',BASE.replace('[3.3s - 6.6s]', 'Later')),
                           ('native_keyframes',BASE.replace('[0.0s - 3.3s]', '[[CLIP_1]]').replace('[3.3s - 6.6s]', '[[CLIP_2]]').replace('[6.6s - 10.0s]', '[[CLIP_3]]'))]:
            with self.subTest(mode=mode):
                calls=[]
                def generate(instruction,*args,**kwargs):
                    calls.append(instruction)
                    yield draft[:40]
                    yield draft
                rows=([{'durata':3.3,'tipo':'Medium','zoom':'Static','mov':'Walk','audio':'wind'},
                       {'durata':3.3,'tipo':'Medium','zoom':'Static','mov':'Pause','audio':'wind'},
                       {'durata':3.4,'tipo':'Medium','zoom':'Static','mov':'Turn','audio':'wind'}] if mode=='native_keyframes' else
                      [{'durata':5,'tipo':'Medium','zoom':'Static','mov':'Walk','audio':'wind'},
                       {'durata':5,'tipo':'Medium','zoom':'Static','mov':'Speak','audio':'wind'}])
                state={'modello_video_attivo':'MiniMax H3','lingua_selezionata':'EN'}
                manager=types.SimpleNamespace(vlm_interrotto=False,generazione_attiva=False)
                registry=types.SimpleNamespace(risolvi_percorso_json_video=lambda _:str(ROOT/'workflows/minimax_h3_api.json'))
                dictionary=defaultdict(lambda:'status',director_compile_success='success',director_compile_fallback='fallback',director_generation_error='Error: {error}')
                namespace={'os':os,'re':__import__('re'),'scene_context':lambda t:t,
                           'gr':types.SimpleNamespace(update=lambda *a,**k:None),
                           'sessione':types.SimpleNamespace(carica_ultima_sessione=lambda:state),
                           'lingua':types.SimpleNamespace(LINGUE={'IT':dictionary,'EN':dictionary}),
                           'config':types.SimpleNamespace(SUGGESTION_DIRECTION_DIR=str(ROOT/'data/nonexistent-test-style')),
                           'log':types.SimpleNamespace(registra=lambda *a:None),
                           '_verifica_stop_regia':lambda:None,'_errore_vlm':lambda _:False,
                           'VLMStatus':type('Status',(str,),{}),
                           'local_vlm':types.SimpleNamespace(genera_prompt_video_timeline=generate),
                           'compose_system':sys.modules['utils.prompt_templates'].compose_system}
                fake_timeline=types.SimpleNamespace(_parse_timeline=lambda _:rows,_pulisci_scelta_ui=lambda x:x)
                overrides={'core':types.SimpleNamespace(workflow_registry=registry),
                           'core.workflow_profiles':types.SimpleNamespace(load_minimax_profile=lambda *a:{'image_mode':mode}),
                           'services':types.SimpleNamespace(comfyui_manager=manager),
                           'utils.timeline':fake_timeline,'utils.video_model_prompt':self.prompts}
                import utils
                with patch.dict(sys.modules,overrides),patch.object(utils,'timeline',fake_timeline,create=True):
                    exec(compile(ast.Module(body=functions,type_ignores=[]),'director-test','exec'),namespace)
                    values=list(namespace['passa_timeline_a_gemma']('', 'test-model','timeline',solo_testo_video=True,
                                    soggetto='MIA_PERSONA walks to a red bicycle, says "Aspettami!" in Italian.',prompt_corrente='previous'))
                if draft == 'Incomplete model response':
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(values[-1][0], 'previous')
                    self.assertIn('missing, empty or duplicated sections', values[-1][2])
                    self.assertFalse(manager.generazione_attiva)
                    continue
                if 'Later' in draft:
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(values[-1][0], 'previous')
                    self.assertIn('No untranslated fallback', values[-1][2])
                    self.assertFalse(manager.generazione_attiva)
                    continue
                self.assertEqual(values[-1][2],'success',values[-1])
                self.assertTrue(any(v[0] == draft[:40] for v in values[:-1]))
                self.assertEqual(len(calls),1)
                self.assertIn('MIA_PERSONA',values[-1][0])
                expected='base' if mode=='native_keyframes' else 'reference'
                self.assertIsNotNone(self.prompts.minimax_sections(values[-1][0],format=expected))
                self.assertFalse(manager.generazione_attiva)

    def test_minimax_markdown_headers_are_normalized_without_inventing_content(self):
        decorated = BASE
        for name in self.prompts.MINIMAX_BASE_SECTIONS:
            decorated = decorated.replace(name + ':', '### **' + name.upper() + ':**')
        self.assertEqual(self.prompts.minimax_sections('```text\n' + decorated + '\n```', format='base'),
                         self.prompts.minimax_sections(BASE, format='base'))
        self.assertIsNone(self.prompts.minimax_sections(decorated + '\n**overall_soundscape:** wind', format='base'))

    def test_small_model_clip_first_response_and_exact_duplicate(self):
        raw = ('[[CLIP_1]] The dog floats.\n[[CLIP_2]] The dog turns.\n'
               'overall_soundscape: Ambient hum.\nnon_diegetic_music: N/A\n'
               'non_diegetic_music: N/A')
        result = self.prompts.minimax_compiled_sections(raw, 'base')
        self.assertIsNotNone(result)
        self.assertIn('The dog turns.', result['integrated_multimodal_description'])
        self.assertEqual(result['overall_soundscape'], 'Ambient hum.')
        self.assertEqual(result['non_diegetic_music'], 'N/A')
        self.assertIsNone(self.prompts.minimax_compiled_sections(raw.replace('non_diegetic_music: N/A', 'non_diegetic_music: piano', 1), 'base'))
        self.assertIsNone(self.prompts.minimax_compiled_sections('[[CLIP_1]] Dog.', 'base'))

    def test_storyboard_roles_match_generation_and_extension(self):
        state={'lista_frame_storyboard_attivi':['first','second','middle','last'],
               'percorso_immagine_selezionata':'old-gallery','percorso_immagine_destinazione':'old-last'}
        saved={'generation_mode':'Storyboard'}
        self.assertEqual(self.prompts.selected_video_frames(state,saved),('first','last','middle'))
        self.assertEqual(self.prompts.selected_video_frames(state,saved,True),(None,None,None))
        state['is_extension']=True
        self.assertEqual(self.prompts.selected_video_frames(state,saved),('old-gallery','old-last',None))

if __name__ == '__main__': unittest.main()
