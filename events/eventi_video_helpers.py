# events/eventi_video_helpers.py

import os
import gradio as gr
from core import config, sessione, log, lingua
from services import comfyui_manager
from utils.media_utils import calcola_stato_spia_video


def _ottieni_traduzione_istantanea(chiave):
    try:
        s_attiva = sessione.carica_ultima_sessione()
        lang = s_attiva.get("lingua_selezionata", "IT")
        return lingua.LINGUE[lang][chiave]
    except Exception:
        return "..."


def _ottieni_label_pulsante(chiave, default_val):
    try:
        s_attiva = sessione.carica_ultima_sessione()
        lang = s_attiva.get("lingua_selezionata", "IT")
        return lingua.LINGUE[lang].get(chiave, default_val)
    except Exception:
        return default_val


# 1. CREATE / IMPROVE SUBJECT (🪄)
def avvia_miglioramento_soggetto():
    comfyui_manager.vlm_interrotto = False  
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    lbl = "🪄 ..."
    msg_status = dl.get("msg_improving_subject", "🪄 AI Writer: Creating / Enhancing movie subject...")
    return (
        gr.update(interactive=False, value=lbl),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        msg_status
    )

def ripristina_miglioramento_soggetto():
    lbl = _ottieni_label_pulsante("btn_improve_subject", "🪄 Create / Enhance Subject")
    return (
        gr.update(interactive=True, value=lbl),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True)
    )


# 2. WRITE TIMELINE (🎬)
def avvia_scrittura_sceneggiatura():
    comfyui_manager.vlm_interrotto = False  
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    testo_btn = "🎬 ..."
    testo_loading_timeline = dl.get("script_writing_status", "🎬 AI Screenwriter at work... Writing screenplay and timeline in progress...")
    return (
        gr.update(interactive=False),
        gr.update(interactive=False, value=testo_btn),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        testo_loading_timeline
    )

def ui_ripristina_scrittura_sceneggiatura():
    lbl = _ottieni_label_pulsante("btn_genera_auto_timeline_label", "🎬 Write Timeline")
    return (
        gr.update(interactive=True),
        gr.update(interactive=True, value=lbl),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True)
    )


# 3. GENERATE DIALOGUES (💬)
def avvia_generazione_dialoghi():
    comfyui_manager.vlm_interrotto = False  
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    lbl = "💬 ..."
    return (
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False, value=lbl),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        _ottieni_traduzione_istantanea("msg_generating_dialogues")
    )

def ripristina_generazione_dialoghi():
    lbl = _ottieni_label_pulsante("btn_generate_dialogues", "💬 Generate Dialogues")
    return (
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True, value=lbl),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True)
    )


# 4. COMPILE DIRECTION (🧠)
def avvia_compilazione_regia():
    comfyui_manager.vlm_interrotto = False  
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    testo_btn = "🧠 ..."
    testo_loading_prompt = dl.get("director_compiling_status", "🧠 AI Director at work... Analyzing timeline and compiling video prompt in progress...")
    return (
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False, value=testo_btn),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        testo_loading_prompt
    )

def ripristina_compilazione_regia():
    lbl = _ottieni_label_pulsante("btn_compila_regia", "🧠 Compile AI Direction")
    return (
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True, value=lbl),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True)
    )


# 5. GENERATE VIDEO (🎥)
def avvia_blocco_generazione_video():
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    lbl = "🎥 ..."
    return (
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False, value=lbl),
        gr.update(interactive=False),
        gr.update(interactive=False),
        _ottieni_traduzione_istantanea("prog_vid_init")
    )

def ripristina_blocco_generazione_video():
    lbl = _ottieni_label_pulsante("btn_genera_video", "Generate Video")
    return (
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True, value=lbl),
        gr.update(interactive=True),
        gr.update(interactive=True)
    )


def sblocca_tutti_i_pulsanti_video():
    """Sblocca immediatamente tutti i comandi della UI del Tab Video e resetta le classi CSS."""
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    lbl_subj = dl.get("btn_improve_subject", "🪄 Create / Enhance Subject")
    lbl_script = dl.get("btn_genera_auto_timeline_label", "🎬 Write Timeline")
    lbl_diag = dl.get("btn_generate_dialogues", "💬 Generate Dialogues")
    lbl_dir = dl.get("btn_compila_regia", "🧠 Compile AI Direction")
    lbl_vid = dl.get("btn_genera_video", "Generate Video")
    lbl_ext = dl.get("btn_estendi_video", "Extend Video")
    lbl_save = dl.get("btn_salva_prompt", "Save Prompt")

    return (
        gr.update(interactive=True, value=lbl_subj),
        gr.update(interactive=True, value=lbl_script),
        gr.update(interactive=True, value=lbl_diag),
        gr.update(interactive=True, value=lbl_dir),
        gr.update(interactive=True, value=lbl_vid),
        gr.update(interactive=True, value=lbl_ext),
        gr.update(interactive=True, value=lbl_save),
        gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"]),
        gr.update(elem_classes=["analisi-col-box"]),
        gr.update(elem_classes=["analisi-col-box"])
    )


def gestisci_interruzione_video_sicura():
    return comfyui_manager.interrompi_comfyui()


def imposta_classe_post_compilazione_regia(status):
    classes = ["analisi-col-box"]
    if str(status).strip().startswith("✅") and not comfyui_manager.vlm_interrotto:
        classes.append("completato-successo")
    return gr.update(elem_classes=classes)


def imposta_classe_post_sceneggiatura(status):
    return imposta_classe_post_compilazione_regia(status)


def carica_suggerimento_sceneggiatura(scelta, prompt_corrente, stato_gen):
    if stato_gen is None:
        stato_gen = {}
        
    opzioni_nulle = ["-", "Nessuno", "None", "nessuno", "none"]
    
    if scelta in opzioni_nulle or not scelta:
        backup = stato_gen.get("backup_sceneggiatura_prompt") or prompt_corrente
        return backup, stato_gen
        
    if prompt_corrente and prompt_corrente.strip():
        stato_gen["backup_sceneggiatura_prompt"] = prompt_corrente
        
    preset_testo = config.leggi_contenuto_suggerimento(config.SUGGESTION_SCREENPLAY_DIR, scelta)
    return preset_testo if preset_testo and preset_testo.strip() else prompt_corrente, stato_gen


def imposta_caricata_manualmente(stato_gen):
    if stato_gen is None:
        stato_gen = {}
    stato_gen["immagine_caricata_manualmente"] = True
    log.registra("zPromptStudio: Detected manual upload of a new source frame.")
    return stato_gen


def aggiorna_durate_da_timeline_solo_stato(testo_timeline):
    if not testo_timeline or not testo_timeline.strip():
        return 4.0
    try:
        from utils import timeline as utils_timeline
        blocchi = utils_timeline._parse_timeline(testo_timeline)
        if not blocchi:
            return 4.0
        totale = sum(float(b["durata"]) for b in blocchi)
        return totale
    except Exception as e:
        log.registra(f"Error calculating internal duration: {e}", "WARNING")
        return 4.0


def aggiorna_durata_da_drag(valore_drag):
    if not valore_drag or not valore_drag.strip():
        return gr.update(), gr.update()
    try:
        totale = float(valore_drag)
        valore_slider = max(5, min(30, int(round(totale))))
        sessione.salva_sessione({"video_durata_totale": totale, "sceneggiatura_durata": valore_slider})
        return totale, valore_slider
    except Exception as e:
        log.registra(f"Error updating duration from drag: {e}", "WARNING")
        return gr.update(), gr.update()


def aggiorna_spia_su_cambio_parametro(fps, rapporto, risoluzione, solo_testo, stato_gen):
    s_reale = sessione.carica_ultima_sessione()
    s_reale["video_fps"] = fps
    s_reale["video_rapporto"] = rapporto
    s_reale["video_risoluzione"] = risoluzione
    
    sessione.salva_sessione({
        "video_fps": fps,
        "video_rapporto": rapporto,
        "video_risoluzione": risoluzione
    })
    
    html_spia = calcola_stato_spia_video(s_reale, stato_gen, solo_testo)
    return gr.update(value=html_spia)


def gestisci_aggiunta_lora_vid(c):
    nuovo_count = min(c + 1, 3)
    sessione.salva_sessione({"lora_video_visibili_count": nuovo_count})
    return nuovo_count, gr.update(visible=(nuovo_count >= 2)), gr.update(visible=(nuovo_count == 3))


def gestisci_rimozione_lora_vid(c):
    nuovo_count = max(c - 1, 1)
    
    updates_sessione = {"lora_video_visibili_count": nuovo_count}
    
    aggiorna_riga2 = gr.update(visible=(nuovo_count >= 2))
    aggiorna_riga3 = gr.update(visible=(nuovo_count == 3))
    
    reset_name2 = gr.update()
    reset_str2 = gr.update()
    reset_name3 = gr.update()
    reset_str3 = gr.update()
    
    if nuovo_count == 2:
        reset_name3 = gr.update(value="-")
        reset_str3 = gr.update(value=1.0)
        updates_sessione["lora_video3_name"] = "-"
        updates_sessione["lora_video3_str"] = 1.0
        updates_sessione["lora_video3_name_minimax"] = "-"
        updates_sessione["lora_video3_str_minimax"] = 1.0
    elif nuovo_count == 1:
        reset_name2 = gr.update(value="-")
        reset_str2 = gr.update(value=1.0)
        reset_name3 = gr.update(value="-")
        reset_str3 = gr.update(value=1.0)
        updates_sessione["lora_video2_name"] = "-"
        updates_sessione["lora_video2_str"] = 1.0
        updates_sessione["lora_video3_name"] = "-"
        updates_sessione["lora_video3_str"] = 1.0
        updates_sessione["lora_video2_name_minimax"] = "-"
        updates_sessione["lora_video2_str_minimax"] = 1.0
        updates_sessione["lora_video3_name_minimax"] = "-"
        updates_sessione["lora_video3_str_minimax"] = 1.0
        
    sessione.salva_sessione(updates_sessione)
    return nuovo_count, aggiorna_riga2, aggiorna_riga3, reset_name2, reset_str2, reset_name3, reset_str3


def gestisci_generazione_video_con_monitor(*args):
    from generators.video import genera_video_con_monitor
    try:
        yield from genera_video_con_monitor(*args)
    finally:
        comfyui_manager.generazione_attiva = False
