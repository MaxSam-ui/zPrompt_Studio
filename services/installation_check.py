"""On-demand environment checks. No model downloads or generation jobs."""
import html
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
MODEL_KEYS = {'ckpt_name', 'unet_name', 'clip_name', 'clip_name1', 'clip_name2',
              'clip_name3', 'vae_name', 'lora_name', 'model_name'}


def model_location_hint(value, choices):
    """Explain mismatches without selecting or moving model weights."""
    name = value.replace('\\', '/').rsplit('/', 1)[-1]
    matches = sorted({str(x).replace('\\', '/') for x in choices
                      if str(x).replace('\\', '/').rsplit('/', 1)[-1] == name})
    if matches:
        locations = ', '.join(matches)
        return (f'{value}: ComfyUI elenca file omonimi in: {locations}. Non riscaricare subito: verifica la cartella prevista nell’help. Il nome uguale non garantisce che sia lo stesso modello; nessun percorso è stato modificato.',
                f'{value}: ComfyUI lists same-named files at: {locations}. Before downloading again, check the expected folder in Help. Matching names do not guarantee the same model; no path was changed.')
    return (f'{value}: non elencato da ComfyUI. Consulta Help → Scarica i modelli dei workflow per link e cartella; dopo la copia riavvia ComfyUI e ripeti la verifica.',
            f'{value}: not listed by ComfyUI. See Help → Download workflow models for links and destination folders; after copying, restart ComfyUI and run the check again.')


def collect_checks(root=ROOT, on_result=None):
    rows = []

    def add(status, name, it, en):
        row = (status, name, it, en)
        rows.append(row)
        if on_result is not None:
            on_result(row)

    def run(code, timeout=60):
        return subprocess.run([sys.executable, '-c', code], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    valid = sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8
    add('OK' if valid else 'ERROR', 'Python', sys.version.split()[0] + ' / 64-bit' if valid else
        'Richiesto Python 3.11 a 64 bit.', 'Python 3.11 64-bit required.' if not valid else sys.version.split()[0] + ' / 64-bit')
    try:
        result = run("import subprocess,sys; sys.exit(subprocess.call([sys.executable,'-m','pip','check']))")
        detail = (result.stdout + result.stderr).strip()
        add('OK' if result.returncode == 0 else 'ERROR', 'Dependencies', detail, detail)
    except Exception as exc:
        add('ERROR', 'Dependencies', str(exc), str(exc))
    try:
        result = run("import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; "
                     "x=torch.ones(1,device='cuda'); assert x.sum().item()==1; "
                     "print(torch.__version__, 'CUDA', torch.version.cuda, torch.cuda.get_device_name(0))")
        detail = (result.stdout + result.stderr).strip()
        add('OK' if result.returncode == 0 else 'CONFIG', 'GPU / CUDA', detail, detail)
    except Exception as exc:
        add('CONFIG', 'GPU / CUDA', str(exc), str(exc))
    add('OK' if shutil.which('git') else 'CONFIG', 'Git',
        'Necessario per update.bat da un clone Git.', 'Required for update.bat from a Git clone.')
    try:
        from core.runtime_paths import prepare_runtime_files
        settings = json.loads(prepare_runtime_files(root).read_text(encoding='utf-8-sig'))
        if not isinstance(settings, dict):
            raise ValueError('settings.json must contain an object')
    except Exception as exc:
        add('ERROR', 'settings.json', str(exc), str(exc))
        return rows

    def resolve(value):
        path = Path(os.path.expandvars(os.path.expanduser(str(value))))
        return path if path.is_absolute() else root / path

    cache = settings.get('VLM_CACHE_DIR')
    if not cache:
        cache = os.getenv('HF_HUB_CACHE') or os.getenv('HUGGINGFACE_HUB_CACHE')
        if not cache:
            home = os.getenv('HF_HOME') or str(Path(os.getenv('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'huggingface')
            cache = str(Path(home) / 'hub')
    for name, value in [('Output', settings.get('STUDIO_OUTPUT_DIR', 'output')),
                        ('LLM cache', cache),
                        ('Session', str(resolve(settings.get('SESSION_FILE', 'session.json')).parent))]:
        try:
            path = resolve(value)
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=path):
                pass
            free = shutil.disk_usage(path).free / 1024**3
            add('OK' if free >= 10 else 'CONFIG', name,
                f'{path} — {free:.1f} GB liberi. Lo spazio richiesto dipende dal modello.',
                f'{path} — {free:.1f} GB free. Required space depends on the model.')
        except Exception as exc:
            add('ERROR', name, str(exc), str(exc))
    comfy = resolve(settings.get('COMFYUI_DIR', ''))
    portable = (comfy / 'python_embeded/python.exe').is_file() and (comfy / 'ComfyUI/main.py').is_file()
    add('OK' if portable else 'CONFIG', 'ComfyUI portable',
        f'{comfy}. Percorso necessario per avvio automatico locale; un server esterno può essere usato separatamente.',
        f'{comfy}. Required for local auto-start; an external server can be used separately.')
    info = None
    try:
        url = str(settings.get('COMFYUI_URL', 'http://127.0.0.1:8188')).rstrip('/')
        if not url.startswith(('http://', 'https://')):
            raise ValueError('COMFYUI_URL requires http:// or https://')
        with urllib.request.urlopen(url + '/object_info', timeout=8) as response:
            info = json.load(response)
        if not isinstance(info, dict) or not info:
            raise ValueError('Invalid ComfyUI object_info response')
        add('OK', 'ComfyUI API', 'Server raggiungibile.', 'Server reachable.')
    except Exception as exc:
        info = None
        add('CONFIG', 'ComfyUI API', f'Avvia ComfyUI e ripeti il controllo: {exc}',
            f'Start ComfyUI and run the check again: {exc}')
    workflows = sorted((root / 'workflows').glob('*_api.json'))
    if not workflows:
        add('ERROR', 'Workflows', 'Nessun workflow trovato.', 'No workflows found.')
    for path in workflows:
        try:
            workflow = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(workflow, dict) or not workflow or any(
                    not isinstance(n, dict) or not n.get('class_type') or not isinstance(n.get('inputs'), dict)
                    for n in workflow.values()):
                raise ValueError('Invalid API workflow')
            from core.workflow_profiles import check_workflow_profile
            profile = check_workflow_profile(path, workflow)
            mode = profile.get('image_mode', profile['adapter'])
            add('OK', path.stem + ' profile',
                f'Collegamenti del profilo validi. Modalità immagini: {mode}.',
                f'Profile bindings valid. Image mode: {mode}.')
            if info is not None and mode == 'native_keyframes':
                required = {'MiniMaxH3ImageToVideo'}
                if profile['capabilities']['middle_image']:
                    required.add('MiniMaxH3AddGuide')
                absent = required - info.keys()
                if absent:
                    raise ValueError('Missing nodes required by workflow profile: ' + ', '.join(sorted(absent)))
            if info is None:
                add('CONFIG', path.stem, 'JSON valido; nodi e modelli da verificare con ComfyUI avviato.',
                    'Valid JSON; nodes and models require a running ComfyUI server.')
                continue
            missing, unchecked = set(), set()
            hints_it, hints_en = [], []
            for node in workflow.values():
                kind = node['class_type']
                if kind not in info:
                    missing.add('Node: ' + kind)
                    hints_it.append(f'{kind}: installa il nodo tramite ComfyUI Manager, se disponibile, e riavvia ComfyUI.')
                    hints_en.append(f'{kind}: install the node through ComfyUI Manager, if available, and restart ComfyUI.')
                    continue
                schema = info[kind].get('input', {})
                fields = {**schema.get('required', {}), **schema.get('optional', {})}
                for key, value in node['inputs'].items():
                    if key not in MODEL_KEYS or not isinstance(value, str) or value.lower() in ('none', ''):
                        continue
                    spec = fields.get(key)
                    options = None
                    if spec and isinstance(spec[0], list):
                        options = spec[0]
                    elif (spec and spec[0] == 'COMBO' and len(spec) > 1
                          and isinstance(spec[1], dict)
                          and isinstance(spec[1].get('options'), list)):
                        options = spec[1]['options']
                    if options is not None:
                        choices = [str(x).replace('\\', '/') for x in options]
                        if value.replace('\\', '/') not in choices:
                            missing.add(key + ': ' + value)
                            it, en = model_location_hint(value, choices)
                            hints_it.append(it)
                            hints_en.append(en)
                    else:
                        unchecked.add(key + ': ' + value)
            detail = '; '.join(sorted(missing | unchecked))
            add('CONFIG' if missing or unchecked else 'OK', path.stem,
                ('Mancante o da verificare: ' + detail + '\n' + '\n'.join(dict.fromkeys(hints_it))) if detail else 'Nodi e modelli dichiarati disponibili; generazione non eseguita.',
                ('Missing or unverified: ' + detail + '\n' + '\n'.join(dict.fromkeys(hints_en))) if detail else 'Declared nodes and models available; generation not executed.')
        except Exception as exc:
            add('ERROR', path.stem, str(exc), str(exc))
    add('INFO', 'LLM / Video / VRAM',
        'Nessun modello scaricato o caricato. Qualità, memoria sufficiente e generazione reale richiedono una prova per il modello scelto. I modelli dei workflow sono quelli salvati nei JSON, prima delle sostituzioni della UI.',
        'No models downloaded or loaded. Quality, sufficient memory and generation require a test with the selected model. Workflow checks use saved JSON defaults, before UI substitutions.')
    return rows


def render_checks(rows, lang='IT'):
    index = 2 if lang == 'IT' else 3
    labels = {'OK': 'OK', 'CONFIG': 'DA CONFIGURARE' if lang == 'IT' else 'CONFIGURE',
              'ERROR': 'ERRORE' if lang == 'IT' else 'ERROR', 'INFO': 'INFO'}
    return '<div>' + ''.join(f'<p><b>[{labels[r[0]]}] {html.escape(r[1])}</b><br>{html.escape(r[index])}</p>' for r in rows) + '</div>'


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    print('Checking installation (may take a minute)...', flush=True)
    results = collect_checks()
    for row in results:
        print(f'[{row[0]}] {row[1]}: {row[3]}', flush=True)
    print('CONFIG = setup or further checks required; OK does not certify a generation run.')
    sys.exit(1 if any(r[0] == 'ERROR' for r in results) else 0)
