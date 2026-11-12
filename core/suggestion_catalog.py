"""Compact stock style menus without deleting or rewriting legacy presets."""
import hashlib
import json
from pathlib import Path


def visible_presets(folder, names, session_path):
    folder = Path(folder)
    try:
        catalog = json.loads((folder.parent / 'style_catalog.json').read_text(encoding='utf-8'))
        legacy = catalog['legacy'].get(folder.name, {})
        if catalog.get('schema_version') != 1 or not legacy:
            return names
    except (OSError, ValueError, KeyError, TypeError):
        return names
    # Read raw data: calling session loading here would recurse through its
    # choice validation. Keep saved legacy choices available without migration.
    try:
        session = json.loads(Path(session_path).read_text(encoding='utf-8'))
        selected = {v for k, v in session.items()
                    if k.startswith('suggerimento_') and isinstance(v, str)}
    except (OSError, ValueError, AttributeError):
        selected = set()
    result = []
    for name in names:
        if name not in legacy or name in selected or name + '.txt' in selected:
            result.append(name)
            continue
        try:
            digest = hashlib.sha256((folder / (name + '.txt')).read_bytes()).hexdigest()
        except OSError:
            result.append(name)
            continue
        # Any local edit makes a legacy file a user preset: never hide it.
        if digest != legacy[name]:
            result.append(name)
    return result
