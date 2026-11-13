"""Small first-run helper, displayed only when neither server nor local setup is found."""
import gradio as gr
from core import config, log
from core.comfyui_setup import choose_folder, needs_setup, save_portable, resolve_portable
from services.help_routes import manual_url


TEXT = {
    'IT': {
        'title': '### Configura ComfyUI',
        'help': 'ComfyUI non è raggiungibile e la cartella locale non è valida. Scegli la cartella che contiene **ComfyUI** e **python_embeded**. Puoi continuare a usare Studio e configurarla più tardi.',
        'folder': 'Cartella ComfyUI Portable', 'browse': 'Scegli cartella',
        'save': 'Verifica e salva', 'guide': 'Non hai ComfyUI? Apri la guida',
        'saved': 'Cartella verificata e salvata. Chiudi e riapri Studio per applicarla. L’indirizzo del server configurato non è stato cambiato.',
        'invalid': 'Cartella non valida: cerca quella che contiene python_embeded/python.exe e ComfyUI/main.py. Le impostazioni precedenti sono rimaste invariate.',
        'error': 'Impossibile salvare le impostazioni. Controlla i permessi e il formato del file settings.json. Nessuna impostazione è stata sovrascritta.',
        'picker': 'La finestra di scelta non è disponibile o è scaduta. Incolla il percorso nel campo e premi Verifica e salva.',
    },
    'EN': {
        'title': '### Set up ComfyUI',
        'help': 'ComfyUI is unreachable and the local folder is invalid. Choose the folder containing **ComfyUI** and **python_embeded**. You can keep using Studio and configure it later.',
        'folder': 'ComfyUI Portable folder', 'browse': 'Choose folder',
        'save': 'Check and save', 'guide': 'Need ComfyUI? Open the guide',
        'saved': 'Folder checked and saved. Close and reopen Studio to apply it. The configured server address has not been changed.',
        'invalid': 'Invalid folder: choose the one containing python_embeded/python.exe and ComfyUI/main.py. Previous settings are unchanged.',
        'error': 'Cannot save settings. Check permissions and the settings.json file format. No settings were overwritten.',
        'picker': 'The folder dialog is unavailable or timed out. Paste the path into the field and click Check and save.',
    },
}


def words(lang):
    return TEXT.get(lang, TEXT['EN'])


def browse(lang):
    try:
        path = choose_folder()
        return path if path else gr.skip(), gr.skip()
    except Exception as exc:
        log.registra(f'Folder picker unavailable: {exc}', 'WARNING')
        return gr.skip(), words(lang)['picker']


def save(value, lang):
    try:
        resolve_portable(value, config.STUDIO_ROOT_DIR)
    except (OSError, ValueError):
        return gr.skip(), words(lang)['invalid'], 'invalid'
    try:
        folder = save_portable(value, config.STUDIO_ROOT_DIR, config.SETTINGS_FILE)
        return folder, words(lang)['saved'], 'saved'
    except (OSError, ValueError):
        return gr.skip(), words(lang)['error'], 'error'


def create(lang):
    w = words(lang)
    with gr.Column(visible=False, variant='panel') as panel:
        heading = gr.Markdown(w['title'] + '\n\n' + w['help'])
        path = gr.Textbox(value=config.COMFYUI_DIR, label=w['folder'])
        with gr.Row():
            pick = gr.Button(w['browse'], size='sm')
            check = gr.Button(w['save'], size='sm', variant='primary')
        guide = gr.Markdown(f"[{w['guide']}]({manual_url(lang)}#installazione)")
        status = gr.Markdown()
        state = gr.State('')
    return panel, heading, path, pick, check, guide, status, state


def connect(demo, controls, language):
    panel, heading, path, pick, check, guide, status, state = controls
    demo.load(lambda: gr.update(visible=needs_setup(config.COMFYUI_DIR, config.STUDIO_ROOT_DIR, config.COMFYUI_URL)),
              outputs=panel, show_progress='hidden')
    pick.click(browse, language, [path, status], concurrency_limit=1)
    check.click(save, [path, language], [path, status, state], concurrency_limit=1)

    def translate(lang, current):
        w = words(lang)
        return (w['title'] + '\n\n' + w['help'], gr.update(label=w['folder']),
                gr.update(value=w['browse']), gr.update(value=w['save']),
                f"[{w['guide']}]({manual_url(lang)}#installazione)", w.get(current, ''))
    language.change(translate, [language, state], [heading, path, pick, check, guide, status], show_progress='hidden')
