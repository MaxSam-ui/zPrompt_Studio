"""Small native setup window shown before importing the main application's AI libraries."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.comfyui_setup import resolve_portable, save_portable, server_available


def load_settings(root):
    root = Path(root)
    target = root / 'data/settings.json'
    if not target.exists() and (root / 'settings.json').exists():
        target = root / 'settings.json'
    source = target if target.exists() else root / 'config/settings.example.json'
    settings = json.loads(source.read_text(encoding='utf-8-sig'))
    if not isinstance(settings, dict):
        raise ValueError('Settings must be a JSON object')
    return target, settings


def show_setup(root, target, settings):
    import tkinter as tk
    from tkinter import ttk, filedialog
    import webbrowser

    window = tk.Tk()
    window.title('zPrompt Studio - ComfyUI setup')
    window.geometry('620x340')
    window.resizable(False, False)
    result = 2  # Closing/cancelling stops startup, without changing settings.
    frame = ttk.Frame(window, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Connect ComfyUI', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Choose your ComfyUI Portable folder to generate images and videos.\n'
              'It must contain both ComfyUI and python_embeded.', wraplength=570).pack(anchor='w', pady=(10, 16))
    path = tk.StringVar(value=settings.get('COMFYUI_DIR', ''))
    row = ttk.Frame(frame); row.pack(fill='x')
    entry = ttk.Entry(row, textvariable=path); entry.pack(side='left', fill='x', expand=True)
    message = tk.StringVar(value='Save and start opens Studio automatically. No restart is needed.')

    def browse():
        selected = filedialog.askdirectory(parent=window, title='Select ComfyUI Portable folder')
        if selected:
            path.set(selected)
            message.set('Click Save and start to check this folder.')

    ttk.Button(row, text='Browse...', command=browse).pack(side='left', padx=(8, 0))
    ttk.Label(frame, textvariable=message, wraplength=570).pack(anchor='w', fill='x', pady=16)

    def finish(code):
        nonlocal result
        result = code
        window.destroy()

    def save():
        try:
            resolve_portable(path.get(), root)
        except (ValueError, OSError):
            message.set('Invalid folder. Select the folder containing python_embeded/python.exe and ComfyUI/main.py. Nothing was changed.')
            return
        try:
            save_portable(path.get(), root, target, defaults=settings)
        except (ValueError, OSError) as exc:
            message.set('Cannot save settings. Check file permissions and format. Nothing was overwritten.')
            print('[CONFIG] Unable to save ComfyUI folder: ' + str(exc), flush=True)
            return
        finish(0)

    ttk.Button(frame, text='Need ComfyUI? Open the installation guide',
               command=lambda: webbrowser.open((Path(root) / 'help/help.en.html').as_uri() + '#installazione')).pack(anchor='w')
    buttons = ttk.Frame(frame); buttons.pack(side='bottom', fill='x', pady=(12, 0))
    ttk.Button(buttons, text='Cancel', command=lambda: finish(2)).pack(side='left')
    ttk.Button(buttons, text='Configure later', command=lambda: finish(0)).pack(side='left', padx=8)
    ttk.Button(buttons, text='Save and start', command=save).pack(side='right')
    window.protocol('WM_DELETE_WINDOW', lambda: finish(2))
    entry.focus_set()
    window.mainloop()
    return result


def main(root=ROOT):
    try:
        target, settings = load_settings(root)
        if server_available(settings.get('COMFYUI_URL', 'http://127.0.0.1:8188')):
            print('[OK] ComfyUI server is available.')
            return 0
        try:
            resolve_portable(settings.get('COMFYUI_DIR', ''), root)
            print('[OK] ComfyUI portable installation found.')
            return 0
        except (ValueError, OSError):
            return show_setup(root, target, settings)
    except Exception as exc:
        print('[CONFIG] Setup could not open: ' + str(exc))
        print('You can configure ComfyUI in Studio > Logs & Settings > Folders.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
