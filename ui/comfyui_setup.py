"""Native folder picker for the existing settings tab."""
import gradio as gr
from core import log
from core.comfyui_setup import choose_folder


TEXT = {
    'IT': {'picker': 'La finestra di scelta non è disponibile o è scaduta. Incolla il percorso nel campo e premi Verifica e salva.'},
    'EN': {'picker': 'The folder dialog is unavailable or timed out. Paste the path into the field and click Check and save.'},
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
