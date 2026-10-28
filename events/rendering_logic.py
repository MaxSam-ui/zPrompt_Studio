# events/rendering_logic.py

import os
import gradio as gr

from core import sessione, log, lingua, config, workflow_registry
from services import local_vlm, comfyui_manager

from events.rendering_ui_sync import (
    gestisci_cambio_modello_immagine,
    gestisci_cambio_modalita,
    gestisci_cambio_modello_immagine_batch
)

from events.rendering_gallery_sync import (
    aggiorna_stato_visuale_seme,
    clicca_toggle_seme,
    svuota_vista_galleria,
    gestisci_trigger_galleria_html
)


def _ottieni_dizionario_lingua_corrente():
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    return lingua.ottieni_dizionario_lingua(lang)


def imposta_stato_successo_affinamento(gen_mode):
    dl = _ottieni_dizionario_lingua_corrente()
    
    mode_str = str(gen_mode).lower()
    if "edit" in mode_str or "modifica" in mode_str:
        return dl.get("edit_success", "...")
    elif "sequenza" in mode_str or "sequence" in mode_str:
        return dl.get("sequence_compile_success", "...")
    return dl.get("refine_success", "...")


def sincronizza_prompt_da_analisi(modalita, prompt_analisi, prompt_rendering_corrente):
    mode_str = str(modalita).lower()
    if "edit" not in mode_str and "modifica" not in mode_str:
        if prompt_rendering_corrente and prompt_rendering_corrente.strip():
            return gr.update()
        if prompt_analisi and prompt_analisi.strip():
            return gr.update(value=prompt_analisi)
    return gr.update()


def get_prompt_save_success_msg():
    dl = _ottieni_dizionario_lingua_corrente()
    return dl.get("prompt_save_success", "...")


def imposta_classe_post_affinamento(status=""):
    if getattr(comfyui_manager, "vlm_interrotto", False) or not str(status).startswith("✅"):
        return gr.update(elem_classes=["analisi-col-box"]), gr.update(elem_classes=["analisi-col-box"])
    return gr.update(elem_classes=["analisi-col-box", "completato-successo"]), gr.update(elem_classes=["analisi-col-box"])


def imposta_classe_post_rendering(status=""):
    # Generators report handled failures as status text rather than exceptions.
    # Only an explicit final success can mark the output panel green.
    if getattr(comfyui_manager, "vlm_interrotto", False) or not str(status).lstrip().startswith(("✅", "📸")):
        return gr.update(elem_classes=["analisi-col-box"]), gr.update(elem_classes=["analisi-col-box"])
    return gr.update(elem_classes=["analisi-col-box", "completato-successo"]), gr.update(elem_classes=["analisi-col-box"])


def gestisci_aggiunta_lora_img(c):
    nuovo_count = min(c + 1, 3)
    sessione.salva_sessione({"lora_visibili_count": nuovo_count})
    return nuovo_count, gr.update(visible=(nuovo_count >= 2)), gr.update(visible=(nuovo_count == 3))


def gestisci_aggiunta_lora_batch(c):
    nuovo_count = min(c + 1, 3)
    sessione.salva_sessione({"lora_batch_visibili_count": nuovo_count})
    return nuovo_count, gr.update(visible=(nuovo_count >= 2)), gr.update(visible=(nuovo_count == 3))


def gestisci_rimozione_lora_generica(c, is_batch=False):
    nuovo_count = max(c - 1, 1)
    s_attiva = sessione.carica_ultima_sessione()
    suffix = "_batch" if is_batch else ""
    key_count = "lora_batch_visibili_count" if is_batch else "lora_visibili_count"
    key_model = "modello_immagine_attivo_batch" if is_batch else "modello_immagine_attivo"
    modello = s_attiva.get(key_model, "Z-Image Turbo")
    
    cfg = workflow_registry.ottieni_config_modello_immagine(modello)
    prefix = cfg.get("session_prefix", "_zimage")

    updates_sessione = {key_count: nuovo_count}
    
    aggiorna_riga2 = gr.update(visible=(nuovo_count >= 2))
    aggiorna_riga3 = gr.update(visible=(nuovo_count == 3))
    
    reset_name2 = gr.update()
    reset_str2 = gr.update()
    reset_name3 = gr.update()
    reset_str3 = gr.update()
    
    if nuovo_count == 2:
        reset_name3 = gr.update(value="-")
        reset_str3 = gr.update(value=1.0)
        updates_sessione[f"lora3_name{prefix}{suffix}"] = "-"
        updates_sessione[f"lora3_str{prefix}{suffix}"] = 1.0
    elif nuovo_count == 1:
        reset_name2 = gr.update(value="-")
        reset_str2 = gr.update(value=1.0)
        reset_name3 = gr.update(value="-")
        reset_str3 = gr.update(value=1.0)
        updates_sessione[f"lora2_name{prefix}{suffix}"] = "-"
        updates_sessione[f"lora2_str{prefix}{suffix}"] = 1.0
        updates_sessione[f"lora3_name{prefix}{suffix}"] = "-"
        updates_sessione[f"lora3_str{prefix}{suffix}"] = 1.0
        
    sessione.salva_sessione(updates_sessione)
    return nuovo_count, aggiorna_riga2, aggiorna_riga3, reset_name2, reset_str2, reset_name3, reset_str3


def gestisci_rimozione_lora_img(c):
    return gestisci_rimozione_lora_generica(c, is_batch=False)


def gestisci_rimozione_lora_batch(c):
    return gestisci_rimozione_lora_generica(c, is_batch=True)


def storyboard_pronto_per_taglio(gen_mode, stato_gen):
    path = (stato_gen or {}).get("ultima_griglia_storyboard")
    return bool("storyboard" in str(gen_mode).lower() and path and os.path.isfile(path))


def avvia_blocco_generazione_immagine():
    comfyui_manager.generazione_attiva = True
    comfyui_manager.vlm_interrotto = False
    return (
        gr.update(interactive=False),  
        gr.update(interactive=False),  
        gr.update(interactive=False),  
        gr.update(interactive=False),  
        gr.update(interactive=False),  
        gr.update(interactive=False),  
        "⏳ Initializing...",
        gr.update(interactive=False),  # Panel slicing must wait for the grid.
    )


def gestisci_interruzione_immagine_sicura():
    return comfyui_manager.interrompi_comfyui()


def gestisci_skip_immagine_sicura():
    return comfyui_manager.salta_generazione_corrente()


def avvia_affinamento_adattivo(prompt_corrente, istruzioni, modello, gen_mode, sequenza_num_scatti=5, sugg_sequenza="-"):
    from utils.prompt_templates import scene_contract, system_template
    from utils.vlm_status import VLMStatus
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    dl = _ottieni_dizionario_lingua_corrente()
    mode = str(gen_mode).lower()
    is_sequence = "sequenza" in mode or "sequence" in mode
    is_edit = "edit" in mode or "modifica" in mode
    def row(prompt, instructions, status, busy=False):
        return gr.update(interactive=not busy), gr.update(interactive=not busy), busy, prompt, instructions, status
    original, changes = prompt_corrente or "", istruzioni or ""
    try:
        if not (original.strip() or changes.strip()):
            yield row(original, changes, dl["msg_prompt_vuoto"])
            return
        yield row(original, changes, dl["vlm_connecting"], True)
        if is_sequence:
            from generators.image_sequence import compila_solo_testo_sequenza
            from utils.prompt_templates import compose_system
            idea = compose_system('Sequence_Refine.txt', original=original, changes=changes) if changes.strip() else original
            status, result = dl["analysis_empty_result"], original
            for candidate, status in compila_solo_testo_sequenza(idea, modello, sequenza_num_scatti, sugg_sequenza,
                                                                preserva_catalogo=not bool(changes.strip())):
                if str(status).startswith("✅"):
                    result = candidate
                yield row(result, changes, status, True)
            if str(status).startswith("✅") and not comfyui_manager.vlm_interrotto:
                sessione.salva_sessione({"prompt_to_send_img": result})
            else:
                result = original
            yield row(result, changes, status)
            return
        if is_edit:
            system = system_template("Edit_Prompt.txt") + "\n" + scene_contract()
            user = f"EXISTING EDIT REQUEST:\n{original}\n\nLATEST USER CHANGES:\n{changes}"
            stream = local_vlm.genera_prompt_immagine(None, system, user, modello)
        else:
            system = system_template("Image_Refine_System.txt") + "\n" + scene_contract()
            stream = local_vlm.affina_descrizione_immagine(original, changes, system, modello)
        result = ""
        for chunk in stream:
            if comfyui_manager.vlm_interrotto:
                break
            if str(chunk).lstrip().startswith(("❌", "Errore", "Error", "⚠", "⏹", "🛑")):
                status = str(chunk) if str(chunk).lstrip().startswith(("❌", "⚠", "⏹", "🛑")) else "❌ " + str(chunk)
                yield row(original, changes, status)
                return
            if isinstance(chunk, VLMStatus):
                yield row(original, changes, str(chunk), True)
                continue
            result = chunk or ""
            yield row(result, changes, dl["vlm_optimizing_realtime" if is_edit else "vlm_refining_realtime"], True)
        if comfyui_manager.vlm_interrotto:
            yield row(original, changes, dl["msg_interruzione_edit" if is_edit else "msg_interruzione_refine"])
            return
        if not result.strip():
            yield row(original, changes, dl["analysis_empty_result"])
            return
        sessione.salva_sessione({"prompt_to_send_img": result.strip()})
        yield row(result.strip(), result.strip() if is_edit else changes, dl["edit_success" if is_edit else "refine_success"])
    except Exception as error:
        log.registra(f"Prompt refinement: {error}", "ERROR")
        yield row(original, changes, "❌ " + str(error))
    finally:
        comfyui_manager.generazione_attiva = False


def avvia_generazione_immagine_con_normalizzazione(
    count, m_vlm, sugg_v, sys_p, hints, prompt,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h, copie,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo,
    img_seed_mode,
    img_seed,
    generation_mode,
    sugg_storyboard,
    storyboard_pannelli,
    attiva_refine_storyboard,
    refine_denoise,
    krea2_edit_grounding_px=768,
    sequenza_num_scatti=5,
    sugg_sequenza="-",
    refine_instructions="",
    krea2_edit_height=1280,
    krea2_edit_lora_strength=0.75
):
    mode_str = str(generation_mode).lower()
    is_edit_mode = "edit" in mode_str or "modifica" in mode_str
    
    if is_edit_mode:
        prompt_effettivo = refine_instructions.strip() if (refine_instructions and refine_instructions.strip()) else prompt
        sessione.salva_sessione({
            "krea2_edit_instruction": prompt_effettivo,
            "krea2_edit_height": str(krea2_edit_height),
            "krea2_edit_lora_strength": float(krea2_edit_lora_strength),
            "krea2_edit_grounding_px": int(krea2_edit_grounding_px)
        })
    else:
        prompt_effettivo = prompt
        if prompt and isinstance(prompt, str) and prompt.strip():
            sessione.salva_sessione({"prompt_to_send_img": prompt.strip()})

    l1_n_norm = workflow_registry.valida_e_normalizza_lora_modello(l1_n, modello_immagine_attivo)
    l2_n_norm = workflow_registry.valida_e_normalizza_lora_modello(l2_n, modello_immagine_attivo)
    l3_n_norm = workflow_registry.valida_e_normalizza_lora_modello(l3_n, modello_immagine_attivo)
    
    cfg_modello = workflow_registry.ottieni_config_modello_immagine(modello_immagine_attivo)
    suffisso = cfg_modello.get("session_prefix", "_zimage")
        
    sessione.salva_sessione({
        f"lora1_name{suffisso}": l1_n_norm,
        f"lora1_str{suffisso}": l1_s,
        f"lora2_name{suffisso}": l2_n_norm,
        f"lora2_str{suffisso}": l2_s,
        f"lora3_name{suffisso}": l3_n_norm,
        f"lora3_str{suffisso}": l3_s
    })
    
    valid_samplers = cfg_modello.get("samplers", ["dpmpp_2m_sde", "euler"])
    if sampler_name not in valid_samplers:
        default_fallback = cfg_modello.get("default_sampler", "dpmpp_2m_sde")
        log.registra(f"Sampler '{sampler_name}' invalid for {modello_immagine_attivo}, defaulted to '{default_fallback}'")
        sampler_name = default_fallback
    
    from generators.image import genera_immagine_con_monitor
    
    yield from genera_immagine_con_monitor(
        count, m_vlm, sugg_v, sys_p, hints, prompt_effettivo,
        l1_n_norm, l1_s, l2_n_norm, l2_s, l3_n_norm, l3_s,
        w, h, copie,
        steps, sampler_name, scheduler,
        hires_steps, hires_denoise, hires_scale,
        stato_gen,
        modello_immagine_attivo,
        img_seed_mode,
        img_seed,
        generation_mode,
        sugg_storyboard,
        storyboard_pannelli,
        attiva_refine_storyboard,
        refine_denoise,
        krea2_edit_grounding_px=krea2_edit_grounding_px,
        sequenza_num_scatti=sequenza_num_scatti,
        sugg_sequenza=sugg_sequenza,
        refine_instructions=refine_instructions,
        krea2_edit_height=krea2_edit_height,
        krea2_edit_lora_strength=krea2_edit_lora_strength
    )


def gestisci_compilazione_testo_storyboard(prompt, m_vlm, sugg_storyboard, storyboard_pannelli, stato_gen):
    from generators.image_storyboard import compila_solo_testo_storyboard
    yield from compila_solo_testo_storyboard(prompt, m_vlm, sugg_storyboard, storyboard_pannelli, stato_gen)


def avvia_taglio_storyboard_con_monitor(
    count,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo,
    storyboard_pannelli,
    attiva_refine_storyboard,
    refine_denoise,
    sugg_storyboard
):
    """Bridge per eseguire la FASE 2 dello Storyboard (Taglio + Refine) dal pulsante dedicato."""
    from generators.image_storyboard import taglia_e_processa_storyboard
    from generators.image_utils import get_ws_url
    
    l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff = workflow_registry.estrai_lora_effettivi(
        count, l1_n, l1_s, l2_n, l2_s, l3_n, l3_s, modello_attivo=modello_immagine_attivo
    )

    ws_url = get_ws_url()
    dl = _ottieni_dizionario_lingua_corrente()

    for msg, gallery_html, prompt_val, timeline_val in taglia_e_processa_storyboard(
        stato_gen,
        modello_immagine_attivo,
        w, h,
        storyboard_pannelli,
        l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff,
        steps, sampler_name, scheduler,
        hires_steps, hires_denoise, hires_scale,
        attiva_refine_storyboard,
        refine_denoise,
        sugg_storyboard,
        ws_url,
        dl
    ):
        yield msg, gallery_html, log.ottieni_tutti_i_log(), stato_gen, prompt_val, timeline_val
