"""Validate and persist a local portable installation without changing live processes."""
import json
import os
import tempfile
from pathlib import Path


def server_available(url, timeout=2):
    """Recognize ComfyUI, not merely an open TCP port."""
    from urllib.request import urlopen
    from urllib.parse import urlsplit
    try:
        if urlsplit(str(url)).scheme not in ('http', 'https'):
            return False
        with urlopen(str(url).rstrip('/') + '/system_stats', timeout=timeout) as response:
            data = json.loads(response.read(1024 * 1024))
        return isinstance(data, dict) and isinstance(data.get('system'), dict)
    except (OSError, ValueError, TypeError):
        return False


def needs_setup(folder, root, url):
    if server_available(url):
        return False
    try:
        resolve_portable(folder, root)
        return False
    except (ValueError, OSError):
        return True


def choose_folder():
    """Run the native dialog on its own main thread; cancellation changes nothing."""
    import subprocess
    import sys
    script = (
        "import tkinter as tk; from tkinter import filedialog; import json; "
        "r=tk.Tk(); r.withdraw(); r.attributes('-topmost', True); "
        "p=filedialog.askdirectory(parent=r,title='Select ComfyUI Portable folder'); "
        "print(json.dumps(p)); r.destroy()"
    )
    result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                            text=True, timeout=120, check=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return json.loads(result.stdout.strip())


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
