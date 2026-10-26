# events/rendering_ui_sync.py

import os
import gradio as gr

from core import sessione, log, lingua, config, workflow_registry
from utils import media_utils
from utils.lora_ui import lora_row_update


def _ottieni_aggiornamenti_modello(modello_selezionato, s, is_editing, is_batch=False):
    cfg = workflow_registry.ottieni_config_modello_immagine(modello_selezionato)
    
    if is_editing and modello_selezionato != "Qwen Image 2.1":
        cfg = workflow_registry.ottieni_config_modifica_immagine(modello_selezionato)
        prefix = "qwen21_edit" if modello_selezionato == "Qwen Image 2.1" else "krea2_edit"
        steps_val = s.get(f"steps_{prefix}") or cfg["steps"]["default"]
        steps_val = max(cfg["steps"]["min"], min(cfg["steps"]["max"], steps_val))
        sampler_val = s.get(f"sampler_{prefix}") or cfg["default_sampler"]
        scheduler_val = s.get(f"scheduler_{prefix}") or cfg["default_scheduler"]
        
        if sampler_val not in cfg["samplers"]:
            sampler_val = cfg["default_sampler"]
        if scheduler_val not in cfg["schedulers"]:
            scheduler_val = cfg["default_scheduler"]
        
        return (
            gr.update(minimum=cfg["steps"]["min"], maximum=cfg["steps"]["max"], value=steps_val, label="Steps"),
            gr.update(value=sampler_val, choices=cfg["samplers"]),
            gr.update(value=scheduler_val, choices=cfg["schedulers"]),
            gr.update(visible=False), gr.update(visible=False), lora_row_update(False), lora_row_update(False),
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(choices=["-"], value="-"), gr.update(value=1.0),
            gr.update(choices=["-"], value="-"), gr.update(value=1.0),
            gr.update(choices=["-"], value="-"), gr.update(value=1.0)
        )

    suffix = "_batch" if is_batch else ""
    lora_visibili_key = "lora_batch_visibili_count" if is_batch else "lora_visibili_count"
    prefix = cfg["session_prefix"]

    scelte_lora = workflow_registry.ottieni_lora_disponibili_immagine(modello_selezionato)
    
    steps_val = s.get(f"steps{prefix}{suffix}") or cfg["steps"]["default"]
    steps_val = max(cfg["steps"]["min"], min(cfg["steps"]["max"], steps_val))
    sampler_val = s.get(f"sampler{prefix}{suffix}") or cfg["default_sampler"]
    scheduler_val = s.get(f"scheduler{prefix}{suffix}") or cfg["default_scheduler"]
    
    if sampler_val not in cfg["samplers"]:
        sampler_val = cfg["default_sampler"]
    if scheduler_val not in cfg["schedulers"]:
        scheduler_val = cfg["default_scheduler"]
    
    hires_steps_val = s.get(f"hires_steps{suffix}", 13)
    hires_denoise_val = s.get(f"hires_denoise{suffix}", 0.32)
    hires_scale_val = s.get(f"hires_scale{suffix}", 1.5)

    lora1_n = workflow_registry.normalizza_lora_per_scelte(s.get(f"lora1_name{prefix}{suffix}", "-"), scelte_lora)
    lora1_s = s.get(f"lora1_str{prefix}{suffix}") if s.get(f"lora1_str{prefix}{suffix}") is not None else 1.0
    lora2_n = workflow_registry.normalizza_lora_per_scelte(s.get(f"lora2_name{prefix}{suffix}", "-"), scelte_lora)
    lora2_s = s.get(f"lora2_str{prefix}{suffix}") if s.get(f"lora2_str{prefix}{suffix}") is not None else 1.0
    lora3_n = workflow_registry.normalizza_lora_per_scelte(s.get(f"lora3_name{prefix}{suffix}", "-"), scelte_lora)
    lora3_s = s.get(f"lora3_str{prefix}{suffix}") if s.get(f"lora3_str{prefix}{suffix}") is not None else 1.0
    visibili_count = s.get(lora_visibili_key) or 1

    has_hires = cfg.get("has_hires_fix", False)

    return (
        gr.update(minimum=cfg["steps"]["min"], maximum=cfg["steps"]["max"], value=steps_val, label="Steps"),
        gr.update(value=sampler_val, choices=cfg["samplers"]),
        gr.update(value=scheduler_val, choices=cfg["schedulers"]),
        gr.update(visible=True), gr.update(visible=True),
        lora_row_update(visibili_count >= 2), lora_row_update(visibili_count >= 3),
        gr.update(visible=False, value=hires_scale_val),  
        gr.update(visible=has_hires, value=hires_steps_val),
        gr.update(visible=has_hires, value=hires_denoise_val),
        gr.update(value=lora1_n, choices=scelte_lora), gr.update(value=lora1_s),
        gr.update(value=lora2_n, choices=scelte_lora), gr.update(value=lora2_s),
        gr.update(value=lora3_n, choices=scelte_lora), gr.update(value=lora3_s)
    )


def gestisci_cambio_modello_immagine(modello_selezionato, generation_mode=None):
    s = sessione.carica_ultima_sessione()
    s["modello_immagine_attivo"] = modello_selezionato
    sessione.salva_sessione({"modello_immagine_attivo": modello_selezionato})
    
    gen_mode = generation_mode if generation_mode is not None else s.get("generation_mode", "Classica (1 Immagine)")
    is_editing = "edit" in str(gen_mode).lower() or "modifica" in str(gen_mode).lower()

    return _ottieni_aggiornamenti_modello(modello_selezionato, s, is_editing, is_batch=False)


def gestisci_cambio_modalita(mode, current_model):
    s_attiva = sessione.carica_ultima_sessione()
    mode_str = str(mode).lower()
    is_edit_mode = "edit" in mode_str or "modifica" in mode_str
    is_storyboard_mode = "storyboard" in mode_str
    is_sequenza_mode = "sequenza" in mode_str or "sequence" in mode_str
    
    if is_edit_mode:
        mode_reale = "Modifica Immagine (Edit)"
        orig_model = current_model if current_model in ("Krea-2 Turbo", "Qwen Image 2.1") else "Krea-2 Turbo"
        is_editing = True
    elif is_storyboard_mode:
        mode_reale = "Storyboard"
        orig_model = current_model if current_model in workflow_registry.elenca_modelli_immagine() else "Z-Image Turbo"
        is_editing = False
    elif is_sequenza_mode:
        mode_reale = "Sequenza Immagini AI"
        orig_model = current_model if current_model in workflow_registry.elenca_modelli_immagine() else "Z-Image Turbo"
        is_editing = False
    else:
        mode_reale = "Classica (1 Immagine)"
        orig_model = current_model if current_model in workflow_registry.elenca_modelli_immagine() else "Z-Image Turbo"
        is_editing = False

    s_attiva["generation_mode"] = mode_reale
    sessione.salva_sessione({"generation_mode": mode_reale})
    
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    btn_genera_testo = dl.get("btn_genera_img", "Genera Immagine")
    btn_genera_story_testo = dl.get("btn_genera_storyboard", "Genera Storyboard")
    btn_genera_seq_testo = "📸 Genera Sequenza AI"
    btn_genera_edit_testo = dl.get("btn_genera_edit", "🎨 Applica Modifica (Edit)")

    m = _ottieni_aggiornamenti_modello(orig_model, s_attiva, is_editing, is_batch=False)
    choices_all = workflow_registry.elenca_modelli_immagine()

    s_list_story = config.elenca_suggerimenti(config.SUGGESTION_STORYBOARD_DIR)
    choices_story = ["-"] + (list(s_list_story) if s_list_story else [])
    story_preset = s_attiva.get("suggerimento_storyboard_selezionato", "-")
    if story_preset not in choices_story:
        story_preset = "-"

    story_pannelli = int(s_attiva.get("storyboard_pannelli", 3))
    story_refine = bool(s_attiva.get("attiva_refine_storyboard", True))
    story_denoise = float(s_attiva.get("refine_denoise", 0.35))
    seq_preset = s_attiva.get("suggerimento_sequenza_selezionato", "-")
    seq_scatti = int(s_attiva.get("sequenza_num_scatti", 5))

    edit_grounding = int(s_attiva.get("krea2_edit_grounding_px", 768))

    html_classica = media_utils.compila_galleria_html(s_attiva.get("immagini_generate_cumulate", []))
    html_storyboard = media_utils.compila_galleria_html(s_attiva.get("lista_frame_storyboard_attivi", []))

    if is_sequenza_mode:
        ui_updates = (
            gr.update(visible=False), gr.update(visible=False, value=1), gr.update(value=btn_genera_seq_testo),
            gr.update(visible=True, value=html_classica, elem_classes=[]), gr.update(visible=False, value=html_storyboard),
            gr.update(choices=choices_all, value=orig_model),
            gr.update(visible=True), gr.update(visible=True, value="📖 Idea Scena e Prompt Sequenza AI"), gr.update(visible=True), gr.update(visible=True),
            gr.update(visible=True), gr.update(visible=False, value=edit_grounding),
            gr.update(label=dl.get("raffina_istruzioni_label", "Istruzioni di Affinamento"), value=s_attiva.get("refine_instructions", "")),
            gr.update(value="📖 Compila Sequenza AI"),
            gr.update(value=dl.get("raffina_titolo", "🪄 Affina Descrizione con AI")),
            gr.update(label=dl.get("btn_carica_da_immagine", "Carica da Immagine")),
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
            gr.update(choices=choices_story, value=story_preset), gr.update(value=story_pannelli), gr.update(value=story_refine), gr.update(value=story_denoise),
            gr.update(visible=True), gr.update(value=seq_preset), gr.update(value=seq_scatti),
            gr.update(visible=True, open=True)
        )
    elif is_edit_mode:
        edit_instruction_salvata = s_attiva.get("krea2_edit_instruction", "")
        ui_updates = (
            gr.update(visible=False), gr.update(visible=False, value=1), gr.update(value=btn_genera_edit_testo),
            gr.update(visible=True, value=html_classica, elem_classes=["edit-mode-active"]), gr.update(visible=False, value=html_storyboard),
            gr.update(choices=["Krea-2 Turbo", "Qwen Image 2.1"], value=orig_model),
            gr.update(visible=False, value=edit_instruction_salvata),
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=True), gr.update(visible=orig_model != "Qwen Image 2.1", value=edit_grounding),
            gr.update(label=dl.get("edit_instructions_label", "Cosa vuoi fare o cambiare?"), value=edit_instruction_salvata),
            gr.update(value=dl.get("btn_optimize_instruction", "🪄 Ottimizza Istruzione AI")),
            gr.update(value=dl.get("edit_title", "🪄 Modifica Immagine con AI")),
            gr.update(label=dl.get("source_edit_label", "Sorgente Edit")),
            gr.update(visible=False), gr.update(visible=orig_model != "Qwen Image 2.1"), gr.update(visible=orig_model == "Qwen Image 2.1"), gr.update(visible=orig_model != "Qwen Image 2.1"),
            gr.update(choices=choices_story, value=story_preset), gr.update(value=story_pannelli), gr.update(value=story_refine), gr.update(value=story_denoise),
            gr.update(visible=False), gr.update(value=seq_preset), gr.update(value=seq_scatti),
            gr.update(visible=False, open=False)
        )
    elif is_storyboard_mode:
        ui_updates = (
            gr.update(visible=True), gr.update(visible=False, value=1), gr.update(value=btn_genera_story_testo),
            gr.update(visible=False, value=html_classica), gr.update(visible=True, value=html_storyboard, elem_classes=[]),
            gr.update(choices=choices_all, value=orig_model),
            gr.update(visible=True), gr.update(visible=True, value="✍️ Prompt da Inviare a ComfyUI"), gr.update(visible=True), gr.update(visible=True),
            gr.update(visible=True), gr.update(visible=False, value=edit_grounding),
            gr.update(label=dl.get("raffina_istruzioni_label", "Istruzioni di Affinamento"), value=s_attiva.get("refine_instructions", "")),
            gr.update(value=dl.get("btn_raffina", "Affina Descrizione")),
            gr.update(value=dl.get("raffina_titolo", "🪄 Affina Descrizione con AI")),
            gr.update(label=dl.get("btn_carica_da_immagine", "Carica da Immagine")),
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
            gr.update(choices=choices_story, value=story_preset), gr.update(value=story_pannelli), gr.update(value=story_refine), gr.update(value=story_denoise),
            gr.update(visible=False), gr.update(value=seq_preset), gr.update(value=seq_scatti),
            gr.update(visible=False, open=False)
        )
    else:
        ui_updates = (
            gr.update(visible=False), gr.update(visible=True, value=int(s_attiva.get("img_copies", 1))), gr.update(value=btn_genera_testo),
            gr.update(visible=True, value=html_classica, elem_classes=[]), gr.update(visible=False, value=html_storyboard),
            gr.update(choices=choices_all, value=orig_model),
            gr.update(visible=True), gr.update(visible=True, value="✍️ Prompt da Inviare a ComfyUI"), gr.update(visible=True), gr.update(visible=True),
            gr.update(visible=True), gr.update(visible=False, value=edit_grounding),
            gr.update(label=dl.get("raffina_istruzioni_label", "Istruzioni di Affinamento"), value=s_attiva.get("refine_instructions", "")),
            gr.update(value=dl.get("btn_raffina", "Affina Descrizione")),
            gr.update(value=dl.get("raffina_titolo", "🪄 Affina Descrizione con AI")),
            gr.update(label=dl.get("btn_carica_da_immagine", "Carica da Immagine")),
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
            gr.update(choices=choices_story, value=story_preset), gr.update(value=story_pannelli), gr.update(value=story_refine), gr.update(value=story_denoise),
            gr.update(visible=False), gr.update(value=seq_preset), gr.update(value=seq_scatti),
            gr.update(visible=False, open=False)
        )

    return (
        ui_updates[0], ui_updates[1], ui_updates[2], ui_updates[3], ui_updates[4],
        ui_updates[5], ui_updates[6], ui_updates[7], ui_updates[8], ui_updates[9],
        ui_updates[10], ui_updates[11], ui_updates[12], ui_updates[13], ui_updates[14],
        ui_updates[15],
        m[0], m[1], m[2], m[8], m[9], m[7],
        ui_updates[16], ui_updates[17], ui_updates[18], ui_updates[19],
        m[3], m[4], m[5], m[6],
        m[10], m[11], m[12], m[13], m[14], m[15],
        ui_updates[20], ui_updates[21], ui_updates[22], ui_updates[23],
        ui_updates[24], ui_updates[25], ui_updates[26],
        ui_updates[27]
    )


def gestisci_cambio_modello_immagine_batch(modello_selezionato):
    s = sessione.carica_ultima_sessione()
    s["modello_immagine_attivo_batch"] = modello_selezionato
    sessione.salva_sessione({"modello_immagine_attivo_batch": modello_selezionato})
    
    return _ottieni_aggiornamenti_modello(modello_selezionato, s, is_editing=False, is_batch=True)
