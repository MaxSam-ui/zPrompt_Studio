import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import hashlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog_test', ROOT / 'core/suggestion_catalog.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class SuggestionCatalogTest(unittest.TestCase):
    def test_common_styles_have_identical_visual_contract(self):
        data = json.loads((ROOT / 'suggestions/style_catalog.json').read_text())
        self.assertEqual(len(data['styles']), 13)
        for name in data['styles']:
            vision = (ROOT / 'suggestions/vision' / (name + '.txt')).read_text(encoding='utf-8')
            direction = (ROOT / 'suggestions/direction' / (name + '.txt')).read_text(encoding='utf-8')
            self.assertEqual(vision.split('STILL-IMAGE APPLICATION:')[0], direction.split('VIDEO APPLICATION:')[0])
            self.assertIn('timeline boundary', direction)

    def test_stock_hidden_custom_and_selected_legacy_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / 'vision'; folder.mkdir()
            old = folder / 'old.txt'; old.write_text('original')
            (root / 'style_catalog.json').write_text(json.dumps({'schema_version': 1, 'legacy': {'vision': {'old': hashlib.sha256(old.read_bytes()).hexdigest()}}}))
            session = root / 'session.json'
            names = ['new', 'old', 'personal']
            self.assertEqual(catalog.visible_presets(folder, names, session), ['new', 'personal'])
            session.write_text(json.dumps({'suggerimento_vision_selezionato': 'old'}))
            self.assertEqual(catalog.visible_presets(folder, names, session), names)
            session.write_text('{}'); old.write_text('my modifications')
            self.assertEqual(catalog.visible_presets(folder, names, session), names)
            (root / 'style_catalog.json').write_text('broken')
            self.assertEqual(catalog.visible_presets(folder, names, session), names)

    def test_clean_install_has_same_thirteen_choices_in_both_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            menus = []
            for phase in ('vision', 'direction'):
                folder = ROOT / 'suggestions' / phase
                menus.append(catalog.visible_presets(folder, sorted(p.stem for p in folder.glob('*.txt')), Path(tmp) / 'missing.json'))
            self.assertEqual(menus[0], menus[1])
            self.assertEqual(len(menus[0]), 13)
