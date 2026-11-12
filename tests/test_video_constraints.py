import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('constraint_test', ROOT/'utils/video_constraints.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VideoConstraintsTest(unittest.TestCase):
    def setUp(self):
        template = lambda name: (ROOT/'suggestions/system'/name).read_text(encoding='utf-8')
        self.mock = patch.dict(sys.modules, {'utils.prompt_templates': types.SimpleNamespace(system_template=template)})
        self.mock.start(); self.addCleanup(self.mock.stop)

    def test_demo_constraints_survive_subject_and_final_compile(self):
        idea = module.preserve_video_constraints('She turns to the sea.', 'Camera fixed. No music, no speech, no cuts.')
        final = module.preserve_video_constraints('[0.0s - 10.0s] She turns.\nAudio: Waves and wind.', idea)
        for clause in ('No music.', 'No speech.', 'Continuous shot, no cuts.', 'Waves and wind.'):
            self.assertIn(clause, final)
        self.assertEqual(final, module.preserve_video_constraints(final, idea))

    def test_italian_and_audio_field(self):
        text = module.preserve_video_constraints('Scene.', 'Niente musica e niente dialoghi; nessun taglio.', 'Waves.')
        self.assertIn('No music.', text)
        self.assertIn('No speech.', text)
        self.assertIn('Continuous shot, no cuts.', text)
        self.assertIn('No music.', module.preserve_video_constraints('Scene.', '', 'No music.'))

    def test_do_not_expand_conditional_or_quoted_requests(self):
        for source in ('No music until the last scene.', 'She says "no music".', 'Do not use no music.', 'Music begins after silence.'):
            self.assertEqual('Scene.', module.preserve_video_constraints('Scene.', source))

    def test_editable_rules_can_disable_preservation(self):
        with patch.dict(sys.modules, {'utils.prompt_templates': types.SimpleNamespace(system_template=lambda _: '{}')}):
            self.assertEqual('Scene.', module.preserve_video_constraints('Scene.', 'No music.'))
