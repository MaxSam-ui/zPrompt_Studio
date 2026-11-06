"""Timeline timing is authoritative even when the model rounds clip lengths."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('director_timing', ROOT / 'utils/director_prompt.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DirectorTimingTest(unittest.TestCase):
    def test_ten_seconds_does_not_require_second_generation(self):
        scenes = [[3.3, 'Wide', 'Static', 'Walk'], [3.4, 'Close', 'Static', 'Turn'],
                  [3.3, 'Wide', 'Static', 'Stop']]
        text = 'A traveler.\n[0-4] Walk.\n[4-8] Turn.\n[8-12] Stop.'
        result = module.align_director_prompt(text, scenes)
        self.assertIsNotNone(result)
        self.assertEqual(module.TIMECODE.findall(result), [('0.0', '3.3'), ('3.3', '6.7'), ('6.7', '10.0')])
        for phrase in ('A traveler.', 'Walk.', 'Turn.', 'Stop.'):
            self.assertIn(phrase, result)

    def test_uneven_scene_lengths_and_typographic_codes(self):
        result = module.align_director_prompt('[0–4] Walk. [4–8] Stop.',
                                               [[2.5, 'Wide', 'Static'], [7.5, 'Close', 'Static']])
        self.assertEqual(module.TIMECODE.findall(result), [('0.0', '2.5'), ('2.5', '10.0')])

    def test_ambiguous_spans_still_require_repair(self):
        scenes = [[5, 'Wide', 'Static'], [5, 'Close', 'Static']]
        for text in ('[0-4] Walk.', '[0-4] Walk. [3-8] Stop.',
                     '[0-4] Walk. [5-8] Stop.', '[0-4] Walk. [4-4] Stop.',
                     '[0-4] [4-8] Stop.'):
            with self.subTest(text=text):
                self.assertIsNone(module.align_director_prompt(text, scenes))

    def test_single_scene_and_invalid_duration(self):
        self.assertIn('[0.0s - 10.0s]', module.align_director_prompt('Walk.', [[10, 'Wide', 'Static']]))
        self.assertIsNone(module.align_director_prompt('[0-4] Walk.', [[float('nan'), 'Wide', 'Static']]))


if __name__ == '__main__':
    unittest.main()
