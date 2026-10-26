# generators/image_sequence.py

import os
import re
import time
import random
import gradio as gr

from core import config, sessione, log, lingua, workflow_registry
from generators import workflow
from services import local_vlm, comfyui_manager, vlm_loader
from services.comfyui_manager import client_id
from utils.media_utils import compila_galleria_html
from generators.image_utils import (
    get_ws_url,
    prepara_vlm_per_generazione,
    invia_prompt_a_coda_comfyui,
    monitora_e_salva_singolo_task
)


from utils.sequence_prompts import (split_sequence, sequence_complete, extract_sequence_prompts,
                                    normalize_catalog_sequence)
from utils.prompt_templates import SCENE_CONTRACT, render_template, system_template
from utils.vlm_status import VLMStatus


def _is_gia_compilato_sequenza(testo):
    return bool(split_sequence(testo)[1])


def estrai_prompt_sequenza(testo_multiline):
    return extract_sequence_prompts(testo_multiline)


def compila_solo_testo_sequenza(idea_utente, m_vlm, num_scatti=5, sugg_sequenza="-", preserva_catalogo=True):
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    dl = lingua.ottieni_dizionario_lingua(sessione.carica_ultima_sessione().get("lingua_selezionata", "IT"))
    original = idea_utente or ""
    try:
        count = max(2, min(5, int(num_scatti)))
        if not original.strip():
            yield original, dl["msg_prompt_vuoto"]
            return
        style = config.leggi_contenuto_suggerimento(config.SUGGESTION_SEQUENCE_DIR, sugg_sequenza) if sugg_sequenza and sugg_sequenza != "-" else "Preserve the requested medium and scene."
        template = system_template("Photo_Sequence.txt", "Write exactly {num_scatti} entries Photo 1: through Photo {num_scatti}: with shared Characters / Cast: and Environment: first. {regole_estetiche_sequenza}")
        system = render_template(template, num_scatti=count, regole_estetiche_sequenza=style) + "\n\n" + SCENE_CONTRACT
        result = ""
        for chunk in local_vlm.genera_prompt_immagine(None, system, original, m_vlm, max_new_tokens=1536):
            if comfyui_manager.vlm_interrotto:
                break
            if str(chunk).lstrip().startswith(("❌", "Errore", "Error", "⚠", "⏹", "🛑")):
                yield original, str(chunk) if str(chunk).lstrip().startswith(("❌", "⚠", "⏹", "🛑")) else "❌ " + str(chunk)
                return
            if isinstance(chunk, VLMStatus):
                yield original, str(chunk)
                continue
            result = chunk or ""
            yield original, dl["vlm_compiling_sequence"]
        if comfyui_manager.vlm_interrotto:
            yield original, dl["batch_status_interrupted"]
            return
        # Validate before normalization so duplicate/missing AI entries cannot be hidden.
        if not sequence_complete(result, count):
            yield original, dl["sequence_invalid_structure"].format(count=count)
            return
        if preserva_catalogo:
            result = normalize_catalog_sequence(original, result, count, style)
        if not sequence_complete(result, count):
            yield original, dl["sequence_invalid_structure"].format(count=count)
            return
        yield result.strip(), dl["vlm_sequence_compiled"]
    except Exception as error:
        log.registra(f"Sequence compilation: {error}", "ERROR")
        yield original, "❌ " + str(error)
    finally:
        comfyui_manager.generazione_attiva = False


def genera_sequenza_immagini(
    prompt_multiline,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo,
    img_seed_mode,
    img_seed,
    immagini_generate,
    seed_attuali,
    html_avvio,
    ws_url,
    dl,
    num_scatti=5,
    sugg_sequenza="-"
):
    comfyui_manager.generazione_attiva = True
    comfyui_manager.vlm_interrotto = False
    
    try:
        num_scatti_int = int(num_scatti)
    except:
        num_scatti_int = 5
    num_scatti_int = max(2, min(5, num_scatti_int))

    e_gia_compilato = _is_gia_compilato_sequenza(prompt_multiline)

    if not e_gia_compilato:
        log.registra(f"Sequence AI: Scene idea requires VLM compilation. Starting Phase 1/2 for {num_scatti_int} shots...")
        yield f"⏳ PHASE 1/2: Writing {num_scatti_int} sequential prompts with VLM AI in progress...", html_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
        
        s_attiva = sessione.carica_ultima_sessione()
        m_vlm = s_attiva.get("modello_vlm") or "huihui_ai/qwen3-vl-abliterated:8b"
        
        testo_compilato = prompt_multiline
        for chunk_txt, msg_st in compila_solo_testo_sequenza(prompt_multiline, m_vlm, num_scatti=num_scatti_int, sugg_sequenza=sugg_sequenza):
            if comfyui_manager.vlm_interrotto:
                yield dl.get("batch_status_interrupted", "⏹️ Generation interrupted."), html_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                return
            if chunk_txt:
                testo_compilato = chunk_txt
            msg_stato_visibile = msg_st if msg_st else "🧠 Compiling sequence prompt in progress..."
            yield msg_stato_visibile, html_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, testo_compilato, gr.update()
            
        if not str(msg_st).startswith("✅"):
            comfyui_manager.generazione_attiva = False
            return
        if testo_compilato:
            prompt_multiline = testo_compilato
            sessione.salva_sessione({"prompt_to_send_img": prompt_multiline})

    if comfyui_manager.vlm_interrotto:
        yield dl["batch_status_interrupted"], html_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
        return
    comfyui_manager.generazione_attiva = True

    prompts_list = estrai_prompt_sequenza(prompt_multiline)

    if not sequence_complete(prompt_multiline, num_scatti_int) or len(prompts_list) != num_scatti_int:
        comfyui_manager.generazione_attiva = False
        yield dl["sequence_invalid_structure"].format(count=num_scatti_int), html_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
        return

    seed_str = str(img_seed).strip() if img_seed is not None else ""
    if img_seed_mode == "fixed" and seed_str.isdigit():
        seed_base = int(seed_str)
    else:
        seed_base = random.randint(1000000000000, 9999999999999)

    totale_scatti = len(prompts_list)
    prepara_vlm_per_generazione()

    # =========================================================================
    # FASE 2A: INVIO IMMEDIATO DI TUTTI I PROMPT ALLA CODA DI COMFYUI
    # =========================================================================
    log.registra(f"Sequence AI: Enqueuing {totale_scatti} shots immediately into ComfyUI queue (Locked Seed: [{seed_base}])...")
    msg_enqueuing = f"🔌 Enqueuing all {totale_scatti} sequence shots to ComfyUI..."
    yield msg_enqueuing, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()

    task_in_coda = []
    for idx, prompt_singolo in enumerate(prompts_list):
        if not comfyui_manager.generazione_attiva:
            msg_stop = dl.get("batch_status_interrupted", "⏹️ Generation interrupted.")
            yield msg_stop, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
            return

        seed_scatto = seed_base
        prompt_id, wf, seed_usato, err_msg = invia_prompt_a_coda_comfyui(
            prompt_singolo, modello_immagine_attivo,
            l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
            w, h, steps, sampler_name, scheduler,
            hires_steps, hires_denoise, hires_scale,
            seed_scatto
        )

        if err_msg or prompt_id is None:
            log.registra(f"Sequence AI Error during enqueue for shot {idx+1}: {err_msg}", "ERROR")
            yield f"❌ Enqueue Error on Shot {idx+1}: {err_msg}", compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
            return

        task_in_coda.append({
            "idx": idx,
            "prompt_id": prompt_id,
            "wf": wf,
            "prompt": prompt_singolo,
            "seed": seed_usato
        })
        log.registra(f"Sequence AI: Shot {idx+1}/{totale_scatti} enqueued (ID: {prompt_id})")

    # =========================================================================
    # FASE 2B: MONITORAGGIO WEBSOCKET E SALVATAGGIO DEI RISULTATI MAN MANO
    # =========================================================================
    for task in task_in_coda:
        idx = task["idx"]
        prompt_id = task["prompt_id"]
        wf = task["wf"]
        prompt_singolo = task["prompt"]
        seed_scatto_corrente = task["seed"]

        if not comfyui_manager.generazione_attiva:
            msg_stop = dl.get("batch_status_interrupted", "⏹️ Generation interrupted.")
            yield msg_stop, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
            return

        msg_inizio_scatto = f"📸 Rendering Sequence Shot {idx+1}/{totale_scatti} (Seed {seed_scatto_corrente}) in progress..."
        yield msg_inizio_scatto, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()

        for status_msg, is_done, final_path, seed_pulito in monitora_e_salva_singolo_task(
            prompt_id, wf, prompt_singolo, modello_immagine_attivo,
            seed_scatto_corrente, 0, 1,
            ws_url, dl, sub_dir=config.STUDIO_IMG_SUBDIR
        ):
            if not comfyui_manager.generazione_attiva:
                msg_stop = dl.get("batch_status_interrupted", "⏹️ Generation interrupted.")
                yield msg_stop, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
                return

            if status_msg.startswith("❌") or status_msg.startswith("⏹️"):
                yield status_msg, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
                return

            if is_done and final_path:
                immagini_generate.append(final_path)
                seed_attuali.append(seed_scatto_corrente)
                
                stato_gen["immagini_generate_cumulate"] = immagini_generate
                stato_gen["seed_attuali_cumulati"] = seed_attuali
                sessione.salva_sessione({
                    "immagini_generate_cumulate": immagini_generate,
                    "seed_attuali_cumulati": seed_attuali
                })
                
                html_passo = compila_galleria_html(immagini_generate)
                msg_done = f"✅ Shot {idx+1}/{totale_scatti} completed!"
                yield msg_done, html_passo, gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
            else:
                msg_prog = f"🎨 Rendering Sequence Shot {idx+1}/{totale_scatti}: {status_msg}"
                yield msg_prog, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()

    target_sel = immagini_generate[-1] if immagini_generate else None
    stato_gen["percorso_immagine_selezionata"] = target_sel
    stato_gen["gallery_no_sync"] = True
    
    sessione.salva_sessione({"percorso_immagine_selezionata": target_sel})
    
    html_finale = compila_galleria_html(immagini_generate, percorso_selezionato=target_sel)
    msg_fin = f"📸 Sequence completed successfully! {totale_scatti} shots generated."
    yield msg_fin, html_finale, gr.update(), log.ottieni_tutti_i_log(), stato_gen, prompt_multiline, gr.update()
