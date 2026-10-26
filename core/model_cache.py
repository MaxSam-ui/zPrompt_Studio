"""One cache destination for model loading and diagnostics; no implicit migration."""
import json
import os
import tempfile
from pathlib import Path

from core import config


def resolve_cache_dir(value):
    value = str(value or '').strip()
    if not value:
        from huggingface_hub.constants import HF_HUB_CACHE
        return os.path.abspath(HF_HUB_CACHE)
    path = os.path.expandvars(os.path.expanduser(value))
    if not os.path.isabs(path):
        path = os.path.join(config.STUDIO_ROOT_DIR, path)
    return os.path.abspath(path)


def get_cache_dir():
    return resolve_cache_dir(config._config.get('VLM_CACHE_DIR', ''))


def save_cache_dir(value):
    """Validate writability before atomically updating settings; preserve other keys."""
    path = resolve_cache_dir(value)
    os.makedirs(path, exist_ok=True)
    with tempfile.TemporaryFile(dir=path):
        pass
    settings_path = Path(config.SETTINGS_FILE)
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    settings['VLM_CACHE_DIR'] = path if str(value or '').strip() else ''
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=settings_path.parent,
                                         suffix='.tmp', delete=False) as handle:
            temporary = handle.name
            json.dump(settings, handle, indent=4, ensure_ascii=False)
        os.replace(temporary, settings_path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    config._config['VLM_CACHE_DIR'] = settings['VLM_CACHE_DIR']
    return path
