# services/prompt_manager.py

import os
import re
import gradio as gr

from core import config, log

CARTELLA_IMG = config.PROMPT_IMG_DIR
CARTELLA_VID = config.PROMPT_VID_DIR


def _ottieni_none_label():
    return "-"


def elenca_prompt_salvati_img():
    if not os.path.exists(CARTELLA_IMG):
        os.makedirs(CARTELLA_IMG, exist_ok=True)
    file_txt = [f for f in os.listdir(CARTELLA_IMG) if f.endswith(".txt")]
    return sorted(file_txt)


def elenca_prompt_salvati_vid():
    if not os.path.exists(CARTELLA_VID):
        os.makedirs(CARTELLA_VID, exist_ok=True)
    file_txt = [f for f in os.listdir(CARTELLA_VID) if f.endswith(".txt")]
    return sorted(file_txt)


def leggi_prompt_salvato_img(nome_file):
    if not nome_file or nome_file in ["-", "Nessuno", "None", "nessuno", "none"]:
        return ""
    percorso = os.path.join(CARTELLA_IMG, nome_file)
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.registra(f"Error reading saved image prompt: {e}")
        return gr.update()


def leggi_prompt_salvato_vid(nome_file):
    if not nome_file or nome_file in ["-", "Nessuno", "None", "nessuno", "none"]:
        return ""
    percorso = os.path.join(CARTELLA_VID, nome_file)
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.registra(f"Error reading saved video prompt: {e}")
        return gr.update()


def salva_prompt_immagine_su_disco(prompt_testo, modello_selezionato, stato_gen=None):
    none_lbl = _ottieni_none_label()
    if not prompt_testo or not prompt_testo.strip():
        log.registra("Save failed: image prompt is empty.")
        scelte = [none_lbl] + elenca_prompt_salvati_img()
        return log.ottieni_tutti_i_log(), gr.update(choices=scelte)
        
    if not os.path.exists(CARTELLA_IMG):
        os.makedirs(CARTELLA_IMG, exist_ok=True)
    
    percorso_immagine = stato_gen.get("percorso_immagine_selezionata") if stato_gen else None
    
    if percorso_immagine and os.path.exists(percorso_immagine):
        nome_base_immagine = os.path.splitext(os.path.basename(percorso_immagine))[0]
        nome_base_immagine = re.sub(r'[\\/*?:"<>|]', '_', nome_base_immagine)
        nome_file = f"{nome_base_immagine}.txt"
        percorso_completo = os.path.join(CARTELLA_IMG, nome_file)
        
        contatore = 1
        while os.path.exists(percorso_completo):
            nome_file = f"{nome_base_immagine}_{contatore}.txt"
            percorso_completo = os.path.join(CARTELLA_IMG, nome_file)
            contatore += 1
    else:
        nome_modello_pulito = "prompt_img"
        if modello_selezionato:
            nome_modello_pulito = re.sub(r'[^\w\-_]', '_', str(modello_selezionato).split(":")[0].lower())
        
        contatore = 1
        while True:
            nome_file = f"{nome_modello_pulito}_prompt{contatore:03d}.txt"
            percorso_completo = os.path.join(CARTELLA_IMG, nome_file)
            if not os.path.exists(percorso_completo):
                break
            contatore += 1
            
    try:
        with open(percorso_completo, "w", encoding="utf-8") as f:
            f.write(prompt_testo)
        log.registra(f"Image prompt saved to: {percorso_completo}")
    except Exception as e:
        log.registra(f"Error saving image prompt: {str(e)}")
        
    scelte = [none_lbl] + elenca_prompt_salvati_img()
    return log.ottieni_tutti_i_log(), gr.update(choices=scelte, value=nome_file)


def salva_prompt_video_su_disco(prompt_testo, modello_selezionato, stato_gen=None):
    none_lbl = _ottieni_none_label()
    if not prompt_testo or not prompt_testo.strip():
        log.registra("Save failed: video prompt is empty.")
        scelte = [none_lbl] + elenca_prompt_salvati_vid()
        return log.ottieni_tutti_i_log(), gr.update(choices=scelte)
        
    if not os.path.exists(CARTELLA_VID):
        os.makedirs(CARTELLA_VID, exist_ok=True)
    
    percorso_immagine = stato_gen.get("percorso_immagine_selezionata") if stato_gen else None
    
    if percorso_immagine and os.path.exists(percorso_immagine):
        nome_base_immagine = os.path.splitext(os.path.basename(percorso_immagine))[0]
        nome_base_immagine = re.sub(r'[\\/*?:"<>|]', '_', nome_base_immagine)
        nome_file = f"{nome_base_immagine}.txt"
        percorso_completo = os.path.join(CARTELLA_VID, nome_file)
        
        contatore = 1
        while os.path.exists(percorso_completo):
            nome_file = f"{nome_base_immagine}_{contatore}.txt"
            percorso_completo = os.path.join(CARTELLA_VID, nome_file)
            contatore += 1
    else:
        nome_modello_pulito = "prompt_vid"
        if modello_selezionato:
            nome_modello_pulito = re.sub(r'[^\w\-_]', '_', str(modello_selezionato).split(":")[0].lower())
        
        contatore = 1
        while True:
            nome_file = f"{nome_modello_pulito}_prompt{contatore:03d}.txt"
            percorso_completo = os.path.join(CARTELLA_VID, nome_file)
            if not os.path.exists(percorso_completo):
                break
            contatore += 1
            
    try:
        with open(percorso_completo, "w", encoding="utf-8") as f:
            f.write(prompt_testo)
        log.registra(f"Video prompt saved to: {percorso_completo}")
    except Exception as e:
        log.registra(f"Error saving video prompt: {str(e)}")
        
    scelte = [none_lbl] + elenca_prompt_salvati_vid()
    return log.ottieni_tutti_i_log(), gr.update(choices=scelte, value=nome_file)