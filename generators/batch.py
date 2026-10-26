# generators/batch.py

import os
import time
import glob
import random
import requests
import shutil
import re
import gradio as gr
from PIL import Image
import json

from core import config, sessione, log, lingua, hardware
from services import comfyui_manager, local_vlm
from services.comfyui_manager import client_id
from utils.media_utils import compila_galleria_html
from generators.image_utils import (
    sanitizza_prompt_vlm,
    prepara_vlm_per_generazione,
    invia_prompt_a_coda_comfyui,
    monitora_e_salva_singolo_task
)

def _normalizza_lora(nome, modello_attivo):
    """Verifica se il nome LoRA esiste ed è compatibile con il modello attivo nel Batch."""
    if nome in ["-", "Nessuno", "None", "nessuno", "none"]:
        return "-"
    if modello_attivo == "Flux.2 Klein":
        cartelle = [config.ottieni_lora_flux2_dir()]
    elif modello_attivo == "Krea-2 Turbo":
        cartelle = [config.ottieni_lora_krea2_dir()]
    else:
        cartelle = config.ottieni_lora_zimage_dirs()
    lista_validi = config.elenca_lora(cartelle)
    if nome in lista_validi:
        return nome
    else:
        log.registra(f"Batch LoRA: '{nome}' invalid or incompatible with {modello_attivo}. Excluded from rendering.", "WARNING")
        return "-"

def formatta_progresso_batch(status, idx, total, name, dl):
    percent = re.search(r'\d+(?:[.,]\d+)?%', status)
    if percent:
        detail = status[percent.start():]
        key = 'batch_status_rendering'
    else:
        detail = re.sub(r'^⏳[^:]*:\s*', '', status)
        key = 'batch_status_processing'
    return dl[key].replace('{data}%', '{data}').format(idx=idx, tot=total, data=detail, name=name)

def _estrai_percorso_file_sicuro(file_obj):
    if file_obj is None:
        return None
    if isinstance(file_obj, str):
        return file_obj
    if isinstance(file_obj, dict):
        return file_obj.get("path") or file_obj.get("name")
    if hasattr(file_obj, "path"):
        return file_obj.path
    if hasattr(file_obj, "name"):
        return file_obj.name
    return str(file_obj)

def _ridimensiona_immagine_per_VLM(immagine_pil, max_size=1024):
    if immagine_pil is None:
        return None
    w, h = immagine_pil.size
    if max(w, h) <= max_size:
        return immagine_pil.copy()
    ratio = max_size / max(w, h)
    nuova_w = int(w * ratio)
    nuova_h = int(h * ratio)
    return immagine_pil.resize((nuova_w, nuova_h), Image.LANCZOS)

def genera_batch_con_monitor(
    lista_files, m_vlm, sys_prompt, user_hints,
    count,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w_default, h_default, copie,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo="Z-Image Turbo",
    batch_mode="Immagini (Vision)",       
    lista_files_testo=None
):
    l1_n_eff = l1_n if count >= 1 else "-"
    l1_s_eff = l1_s if count >= 1 else 0.0
    l2_n_eff = l2_n if count >= 2 else "-"
    l2_s_eff = l2_s if count >= 2 else 0.0
    l3_n_eff = l3_n if count == 3 else "-"
    l3_s_eff = l3_s if count == 3 else 0.0

    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))

    immagini_generate_totali = list(stato_gen.get("immagini_generate_batch", [])) if (stato_gen and isinstance(stato_gen.get("immagini_generate_batch"), list)) else []
    initial_count = len(immagini_generate_totali)
    stato_gen["immagini_generate_batch"] = immagini_generate_totali
    html_galleria_avvio = compila_galleria_html(immagini_generate_totali)

    is_text_mode = "testo" in str(batch_mode).lower() or "text" in str(batch_mode).lower() or "prompt" in str(batch_mode).lower()
    target_files = lista_files_testo if is_text_mode else lista_files
    if not target_files:
        msg_no_files = dl.get("batch_err_no_files", "⚠️ No files uploaded.")
        yield msg_no_files, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
        return

    l1_n_eff = _normalizza_lora(l1_n_eff, modello_immagine_attivo)
    l2_n_eff = _normalizza_lora(l2_n_eff, modello_immagine_attivo)
    l3_n_eff = _normalizza_lora(l3_n_eff, modello_immagine_attivo)

    valid_samplers = ["linear/euler", "exponential/res_2s", "res_2s", "dpmpp_2m_sde", "euler_ancestral", "ddim", "euler", "heun", "dpmpp_2m", "uni_pc", "lcm", "er_sde"]
    if sampler_name not in valid_samplers:
        sampler_name = "linear/euler" if modello_immagine_attivo == "Krea-2 Turbo" else "dpmpp_2m_sde"

    comfyui_manager.generazione_attiva = True
    comfyui_manager.batch_attivo = True

    totale_immagini = len(target_files)
    prompts = []  

    local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_BATCH_SUBDIR)
    os.makedirs(local_dir, exist_ok=True)

    try:
        # =========================================================================
        # FASE 1: LETTURA FILE DI TESTO O GENERAZIONE PROMPT VLM PER IMMAGINI
        # =========================================================================
        if is_text_mode:
            prepara_vlm_per_generazione()

            msg_init_text = dl.get("batch_status_init_text", "📂 PHASE 1/2: Reading prompts from text files...")
            yield msg_init_text, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(stato_gen.get('immagini_generate_batch', []))})"), ""
            
            for idx, file_obj in enumerate(target_files):
                if not comfyui_manager.batch_attivo:
                    msg_stop = dl.get("batch_status_interrupted", "⏹️ Batch interrupted.")
                    yield msg_stop, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
                    return

                filepath = _estrai_percorso_file_sicuro(file_obj)
                if not filepath or not os.path.exists(filepath):
                    log.registra(f"Text file not found: {filepath}", "WARNING")
                    continue

                nome_originale = os.path.basename(filepath)
                msg_read = dl.get("batch_status_reading_file", "📂 Reading file [{idx}/{tot}]: {name}...").format(idx=idx+1, tot=totale_immagini, name=nome_originale)
                yield msg_read, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""

                try:
                    try:
                        with open(filepath, "r", encoding="utf-8-sig") as f_text:
                            prompt_caricato = f_text.read().strip()
                    except UnicodeDecodeError:
                        with open(filepath, "r", encoding="latin-1", errors="replace") as f_text:
                            prompt_caricato = f_text.read().strip()
                    
                    w_eff = w_default if w_default else "1024"
                    h_eff = h_default if h_default else "1024"
                    
                    prompts.append((filepath, nome_originale, prompt_caricato, w_eff, h_eff))
                    
                    msg_loaded = dl.get("batch_status_prompt_loaded", "📝 Prompt loaded [{idx}/{tot}]: {prompt}...").format(idx=idx+1, tot=totale_immagini, prompt=prompt_caricato[:60])
                    yield msg_loaded, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), prompt_caricato
                except Exception as e:
                    log.registra(f"Error reading prompt file {nome_originale}: {e}", "WARNING")
                    continue
        else:
            hardware.prepara_vram("VLM")
            
            msg_init_vision = dl.get("batch_status_init_vision", "📝 PHASE 1/2: Generating prompts for all images...")
            yield msg_init_vision, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(stato_gen.get('immagini_generate_batch', []))})"), ""
            
            for idx, file_obj in enumerate(target_files):
                if not comfyui_manager.batch_attivo:
                    msg_stop = dl.get("batch_status_interrupted", "⏹️ Batch interrupted.")
                    yield msg_stop, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
                    return

                filepath = _estrai_percorso_file_sicuro(file_obj)
                if not filepath or not os.path.exists(filepath):
                    log.registra(f"File not found: {filepath}", "WARNING")
                    continue

                nome_originale = os.path.basename(filepath)
                
                msg_vision_init = dl.get("prog_bat_vision", "🔍 Visual analysis [{idx}/{tot}]: {name}...").format(idx=idx+1, tot=totale_immagini, name=nome_originale)
                yield msg_vision_init, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""

                try:
                    with Image.open(filepath) as img_pil:
                        img_resized = _ridimensiona_immagine_per_VLM(img_pil, max_size=1024)
                        w_orig, h_orig = img_pil.size
                except Exception as e:
                    log.registra(f"Error reading image {nome_originale}: {e}", "WARNING")
                    continue

                max_w = int(w_default) if w_default else 1024
                max_h = int(h_default) if h_default else 1024

                rapporto_orig = w_orig / h_orig
                if rapporto_orig >= 1.0:
                    w_target = max_w
                    h_target = int(max_w / rapporto_orig)
                else:
                    h_target = max_h
                    w_target = int(max_h * rapporto_orig)

                scelte_standard = [512, 768, 1024, 1280, 1536, 2048]
                w_eff = str(min(scelte_standard, key=lambda x: abs(x - w_target)))
                h_eff = str(min(scelte_standard, key=lambda x: abs(x - h_target)))

                prompt_finale = ""
                try:
                    last_yield_time = 0
                    for chunk in local_vlm.genera_prompt_immagine(img_resized, sys_prompt, user_hints, m_vlm):
                        if not comfyui_manager.batch_attivo:
                            msg_stop = dl.get("batch_status_interrupted", "⏹️ Batch interrupted.")
                            yield msg_stop, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
                            return
                        
                        from utils.vlm_status import VLMStatus
                        if isinstance(chunk, VLMStatus):
                            yield str(chunk), html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                            continue
                        if str(chunk).startswith(("❌", "⚠", "⏹", "🛑", "Errore")):
                            prompt_finale = ""
                            yield str(chunk), html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                            break
                        prompt_finale = chunk
                        now = time.time()
                        
                        if now - last_yield_time > 0.3:
                            last_yield_time = now
                            msg_vlm_prog = f"🧠 VLM Analysis [{idx+1}/{totale_immagini}] ({nome_originale})..."
                            yield msg_vlm_prog, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), prompt_finale
                    
                    if not str(prompt_finale or "").strip():
                        log.registra(f"Batch: no valid VLM prompt for {nome_originale}; item skipped.", "WARNING")
                        continue
                    nome_base_input = os.path.splitext(nome_originale)[0]
                    txt_path = os.path.join(local_dir, f"{nome_base_input}.txt")
                    with open(txt_path, "w", encoding="utf-8") as f_txt:
                        f_txt.write(prompt_finale)
                    log.registra(f"Batch: Prompt saved in advance to disk: {txt_path}")

                    prompts.append((filepath, nome_originale, prompt_finale, w_eff, h_eff))
                    yield dl.get("prog_bat_prompt", "📝 Prompt generated [{idx}/{tot}]: {prompt}...").format(idx=idx+1, tot=totale_immagini, prompt=prompt_finale[:60]), html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), prompt_finale
                except Exception as e:
                    log.registra(f"Error generating prompt for {nome_originale}: {e}", "WARNING")
                    continue

        if not prompts:
            msg_no_prompts = dl.get("batch_err_no_prompts", "❌ No valid prompt generated or read from files.")
            yield msg_no_prompts, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
            return

        prepara_vlm_per_generazione()
        time.sleep(0.5)

        try:
            totale_copie = int(copie) if copie else 1
        except Exception:
            totale_copie = 1

        totale_rendering_attesi = len(prompts) * totale_copie

        # =========================================================================
        # FASE 2A: INVIO IMMEDIATO DI TUTTI I PROMPT IN BLOCCO ALLA CODA COMFYUI
        # =========================================================================
        msg_queue = dl.get("batch_status_sending_queue", "🔌 Sending {total} requests to ComfyUI queue...").format(total=totale_rendering_attesi)
        yield msg_queue, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(stato_gen.get('immagini_generate_batch', []))})"), ""

        tasks_batch_in_coda = []
        global_task_idx = 0

        for idx, (filepath, nome_originale, prompt_finale, w_eff, h_eff) in enumerate(prompts):
            nome_base_input = os.path.splitext(nome_originale)[0]

            for copia_idx in range(totale_copie):
                if not comfyui_manager.batch_attivo:
                    msg_stop = dl.get("batch_status_interrupted", "⏹️ Batch interrupted.")
                    yield msg_stop, html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
                    return

                seed_casuale = random.randint(1000000000000, 9999999999999)
                prompt_id, wf, seed_usato, err_msg = invia_prompt_a_coda_comfyui(
                    prompt_finale, modello_immagine_attivo,
                    l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff,
                    w_eff, h_eff, steps, sampler_name, scheduler,
                    hires_steps, hires_denoise, hires_scale,
                    seed_casuale
                )

                if err_msg or prompt_id is None:
                    log.registra(f"Batch Error enqueuing task [{global_task_idx+1}/{totale_rendering_attesi}] for {nome_originale}: {err_msg}", "WARNING")
                else:
                    tasks_batch_in_coda.append({
                        "task_idx": global_task_idx,
                        "prompt_id": prompt_id,
                        "wf": wf,
                        "prompt": prompt_finale,
                        "seed": seed_usato,
                        "nome_base": nome_base_input,
                        "nome_originale": nome_originale,
                        "copia_idx": copia_idx
                    })
                    log.registra(f"Batch: Prompt [{global_task_idx+1}/{totale_rendering_attesi}] enqueued (ID: {prompt_id}, file: {nome_originale})")

                global_task_idx += 1

        if not tasks_batch_in_coda:
            yield "❌ Unable to enqueue tasks to ComfyUI.", html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), ""
            return

        # =========================================================================
        # FASE 2B: MONITORAGGIO SEQUENZIALE DELLA CODA E RACCOLTA RISULTATI
        # =========================================================================
        ws_url = config.COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?clientId={client_id}"

        for t_info in tasks_batch_in_coda:
            curr_idx = t_info["task_idx"]
            prompt_id = t_info["prompt_id"]
            wf = t_info["wf"]
            prompt_testo = t_info["prompt"]
            seed_usato = t_info["seed"]
            nome_base_input = t_info["nome_base"]
            nome_originale = t_info["nome_originale"]
            copia_idx = t_info["copia_idx"]

            if not comfyui_manager.batch_attivo:
                msg_stop = dl.get("batch_status_interrupted", "⏹️ Batch interrupted.")
                yield msg_stop, compila_galleria_html(stato_gen.get("immagini_generate_batch", [])), log.ottieni_tutti_i_log(), stato_gen, gr.update(), prompt_testo
                return

            last_progress_yield = 0
            for status_msg, is_done, final_path, seed_pulito in monitora_e_salva_singolo_task(
                prompt_id, wf, prompt_testo, modello_immagine_attivo,
                seed_usato, copia_idx, totale_copie,
                ws_url, dl, sub_dir=config.STUDIO_BATCH_SUBDIR,
                nome_sorgente_specifico=nome_base_input
            ):
                immagini_attuali = list(stato_gen.get("immagini_generate_batch", []))
                html_corrente = compila_galleria_html(immagini_attuali)

                if status_msg.startswith("⏹️"):
                    comfyui_manager.batch_attivo = False
                    comfyui_manager.generazione_attiva = False
                    yield status_msg, html_corrente, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(immagini_attuali)})"), prompt_testo
                    return
                elif status_msg.startswith("❌"):
                    log.registra(f"Batch: Warning on task [{curr_idx+1}/{totale_rendering_attesi}]: {status_msg}. Continuing with next item...", "WARNING")
                    yield status_msg, html_corrente, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(immagini_attuali)})"), prompt_testo
                    break

                if is_done and final_path:
                    immagini_attuali.append(final_path)
                    stato_gen["immagini_generate_batch"] = immagini_attuali
                    sessione.salva_sessione({"immagini_generate_batch": immagini_attuali})

                    html_fine_passo = compila_galleria_html(immagini_attuali)
                    msg_done_step = dl.get("batch_status_step_completed", "📸 Rendering {idx}/{tot} completed.").format(
                        idx=curr_idx+1, tot=totale_rendering_attesi
                    )
                    yield msg_done_step, html_fine_passo, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(immagini_attuali)})"), prompt_testo
                else:
                    now = time.time()
                    if now - last_progress_yield > 0.5:
                        last_progress_yield = now
                        msg_progress = formatta_progresso_batch(
                            status_msg, curr_idx+1, totale_rendering_attesi, nome_originale, dl)
                        yield msg_progress, html_corrente, gr.update(), stato_gen, gr.update(), prompt_testo

        # Rilascio coordinato delle risorse di ComfyUI a fine batch
        hardware.libera_modelli_comfyui()

        immagini_finali = list(stato_gen.get("immagini_generate_batch", []))
        html_galleria_batch_done = compila_galleria_html(immagini_finali)
        
        ultimo_prompt_visibile = prompts[-1][2] if prompts else ""
        new_count = len(immagini_finali) - initial_count
        expected_count = totale_immagini * totale_copie
        if new_count == expected_count:
            final_status = "✅ " + dl.get("prog_bat_done", "Batch completed: {num}").format(num=new_count)
        elif new_count:
            final_status = dl['batch_partial_result'].format(done=new_count, total=expected_count)
        else:
            final_status = dl['batch_no_result']
        yield final_status, html_galleria_batch_done, log.ottieni_tutti_i_log(), stato_gen, gr.update(label=f"{dl.get('stato_galleria', 'Gallery Status')} ({len(immagini_finali)})"), ultimo_prompt_visibile

    finally:
        comfyui_manager.batch_attivo = False
        comfyui_manager.generazione_attiva = False
