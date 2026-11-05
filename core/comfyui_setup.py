"""Validate and persist a local portable installation without changing live processes."""
import json
import os
import tempfile
from pathlib import Path


def resolve_portable(value, root):
    value = str(value or '').strip().strip('"')
    if not value:
        raise ValueError('empty')
    folder = Path(os.path.expandvars(os.path.expanduser(value)))
    if not folder.is_absolute():
        folder = Path(root) / folder
    folder = folder.resolve()
    if folder.name.lower() == 'comfyui' and (folder.parent / 'python_embeded/python.exe').is_file():
        folder = folder.parent
    missing = [name for name in ('python_embeded/python.exe', 'ComfyUI/main.py')
               if not (folder / name).is_file()]
    if missing:
        raise ValueError(', '.join(missing))
    return str(folder)


def save_portable(value, root, settings_path):
    folder = resolve_portable(value, root)
    target = Path(settings_path)
    settings = json.loads(target.read_text(encoding='utf-8-sig'))
    if not isinstance(settings, dict):
        raise ValueError('Settings must be a JSON object')
    settings['COMFYUI_DIR'] = folder
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         suffix='.tmp', delete=False) as handle:
            temporary = handle.name
            json.dump(settings, handle, ensure_ascii=False, indent=4)
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return folder
