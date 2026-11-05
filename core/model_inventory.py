"""Conservative local weight inventory; presence is not a compatibility test."""
import json
from pathlib import Path


def snapshot_has_weights(snapshot):
    snapshot = Path(snapshot)
    indexes = list(snapshot.glob('*.index.json'))
    for index in indexes:
        if not index.name.endswith(('safetensors.index.json', 'bin.index.json')):
            continue
        try:
            shards = set(json.loads(index.read_text(encoding='utf-8'))['weight_map'].values())
            if shards and all((snapshot / name).is_file() and (snapshot / name).stat().st_size > 0
                              for name in shards):
                return True
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    # A partial sharded checkpoint must never pass as a single-file model.
    return any(p.is_file() and p.stat().st_size > 0 for name in
               ('model.safetensors', 'pytorch_model.bin') for p in [snapshot / name])


def completed_cached_models(cache):
    result = []
    root = Path(cache)
    if not root.is_dir():
        return result
    for folder in root.glob('models--*'):
        try:
            if any(snapshot_has_weights(p) for p in (folder / 'snapshots').iterdir() if p.is_dir()):
                result.append(folder.name[len('models--'):].replace('--', '/', 1))
        except OSError:
            continue
    return sorted(set(result))
