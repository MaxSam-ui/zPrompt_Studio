import unittest
from utils.prompt_aspect import align_prompt_aspect

class PromptAspectTests(unittest.TestCase):
    def test_matches_render_dimensions(self):
        self.assertEqual(align_prompt_aspect('A scene. Aspect ratio: 21:9.',1536,864),'A scene. Aspect ratio: 16:9.')
        self.assertEqual(align_prompt_aspect('Aspect ratio 2:1',768,1024),'Aspect ratio 3:4')
    def test_preserves_scene_numbers_and_quoted_text(self):
        text='Three panels, 0:04 on a clock; a sign reads "Aspect ratio: 21:9".'
        self.assertEqual(align_prompt_aspect(text,1024,1024),text)
    def test_no_annotation_or_invalid_size(self):
        self.assertEqual(align_prompt_aspect('A widescreen scene',1024,1024),'A widescreen scene')
        self.assertEqual(align_prompt_aspect('Aspect ratio: 2:1',0,100),'Aspect ratio: 2:1')
