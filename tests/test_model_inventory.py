import json
import tempfile
import unittest
from pathlib import Path
from core.model_inventory import completed_cached_models, snapshot_has_weights

class ModelInventoryTests(unittest.TestCase):
    def test_partial_and_complete_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp); snapshot=cache/'models--owner--model/snapshots/revision'
            snapshot.mkdir(parents=True)
            (snapshot/'config.json').write_text('{}')
            self.assertEqual(completed_cached_models(cache),[])
            (snapshot/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'a':'part1.safetensors','b':'part2.safetensors'}}))
            (snapshot/'part1.safetensors').write_bytes(b'weight')
            self.assertFalse(snapshot_has_weights(snapshot))
            (snapshot/'part2.safetensors').touch()
            self.assertFalse(snapshot_has_weights(snapshot))
            (snapshot/'part2.safetensors').write_bytes(b'weight')
            self.assertEqual(completed_cached_models(cache),['owner/model'])

    def test_unsharded_and_invalid_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'model.safetensors.index.json').write_text('invalid')
            self.assertFalse(snapshot_has_weights(p))
            (p/'model.safetensors').write_bytes(b'weight')
            self.assertTrue(snapshot_has_weights(p))
