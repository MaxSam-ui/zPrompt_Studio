from utils.progress_status import phase_progress
# generators/image_utils.py

import os
import time
import glob
import random
import re
import hashlib
import requests
import shutil
import gradio as gr
from PIL import Image

from core import config, log, sessione, workflow_registry
from generators import workflow
from services import comfyui_manager
from services.comfyui_manager import client_id
from utils.websocket_monitor import stream_webhook_events, recupera_file_generato
from utils.media_utils import depura_nome_file_infinito


def sposta_file_sicuro(src, dst):
    """Safely moves a file, with fallback to copy+delete."""
    try:
        shutil.move(src, dst)
        return True
    except PermissionError:
        try:
            shutil.copy2(src, dst)
            try:
                os.remove(src)
            except Exception:
                pass
            return True
        except Exception:
            return False
    except Exception:
        return False


def get_ws_url():
    """Returns ComfyUI WebSocket URL."""
    return config.COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?clientId={client_id}"


def prepara_vlm_per_generazione():
    """Prepares VLM models and VRAM for generation."""
    from core import hardware
    hardware.prepara_vram("COMFY_IMG")


def _calcola_hash_prompt(prompt_text):
    if not prompt_text:
        return "empty_prompt"
    p_norm = prompt_text.strip().lower()
    return hashlib.md5(p_norm.encode('utf-8')).hexdigest()


def sanitizza_prompt_vlm(testo):
    if not testo:
        return ""

    testo_pulito = re.sub(r'```[a-zA-Z]*\n', '', testo)
    testo_pulito = testo_pulito.replace("```", "").strip()

    pattern_rimozione = [
        r'^(?:here is a detailed description of the image|here is a description of the image|this image features|this image depicts|certainly|sure|here is the prompt|descriptive prompt|description|prompt|descrivi|immagine)\b[\s,:\-\.]*',
        r'^(?:the image shows|the image illustrates|the photo shows|the photograph shows|the picture shows|this portrait shows|this shot features)\b[\s,:\-\.]*',
        r'^(?:disegno|fotografia|scatto|ritratto)\b[\s,:\-\.]*'
    ]

    for pat in pattern_rimozione:
        testo_pulito = re.sub(pat, '', testo_pulito, flags=re.IGNORECASE)

    return testo_pulito.strip()


def invia_prompt_a_coda_comfyui(
    prompt, modello_immagine_attivo,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h, steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    seed_da_usare
):
    """Costruisce il workflow e lo invia immediatamente alla coda di ComfyUI, restituendo (prompt_id, wf, seed, err)."""
    prompt_sanitizzato = sanitizza_prompt_vlm(prompt)
    file_wf = workflow_registry.risolvi_percorso_json_immagine(modello_immagine_attivo)

    if modello_immagine_attivo == "Flux.2 Klein":
        wf = workflow.prepara_workflow_flux2(
            file_wf, prompt_sanitizzato,
            l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
            w, h, 1,
            steps=steps, sampler_name=sampler_name, scheduler=scheduler,
            hires_steps=hires_steps, hires_denoise=hires_denoise,
            seed_mode="fixed", custom_seed=seed_da_usare
        )
    elif modello_immagine_attivo == "Krea-2 Turbo":
        wf = workflow.prepara_workflow_krea2(
            file_wf, prompt_sanitizzato,
            l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
            w, h, 1,
            steps=steps, sampler_name=sampler_name, scheduler=scheduler,
            seed_mode="fixed", custom_seed=seed_da_usare
        )
    else:
        wf = workflow.prepara_workflow_z_image(
            file_wf, prompt_sanitizzato,
            l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
            w, h, 1,
            steps=steps, sampler_name=sampler_name, scheduler=scheduler,
            hires_steps=hires_steps, hires_denoise=hires_denoise, hires_scale=hires_scale,
            seed_mode="fixed", custom_seed=seed_da_usare
        )

    if wf is None:
        return None, None, seed_da_usare, "❌ ComfyUI Offline or Invalid Workflow"

    try:
        resp = requests.post(config.COMFYUI_URL + "/prompt", json={"prompt": wf, "client_id": client_id}, timeout=10)
        if resp.status_code != 200:
            try:
                err_data = resp.json()
                dettaglio_err = err_data.get("error", {}).get("message", err_data.get("node_errors", str(resp.text)))
            except Exception:
                dettaglio_err = resp.text
            return None, None, seed_da_usare, f"❌ ComfyUI Error ({resp.status_code}): {dettaglio_err}"
        prompt_id = resp.json()["prompt_id"]
        return prompt_id, wf, seed_da_usare, None
    except Exception as e:
        return None, None, seed_da_usare, f"❌ Submission failed: {e}"


def monitora_e_salva_singolo_task(
    prompt_id, wf, prompt_testo, modello_immagine_attivo,
    seed_usato, copia_idx, totale_copie,
    ws_url, dl, sub_dir="images", nome_sorgente_specifico=None
):
    """Monitora l'esecuzione di un prompt_id già in coda ComfyUI e archivia l'immagine generata."""
    prompt_sanitizzato = sanitizza_prompt_vlm(prompt_testo)
    percorso_catturato = None

    for event_type, data in stream_webhook_events(prompt_id, ws_url, wf, timeout=float(config.TIMEOUT_COMFY_IMMAGINE)):
        if not comfyui_manager.generazione_attiva and not comfyui_manager.batch_attivo:
            yield dl.get("batch_status_interrupted", "⏹️ Generation interrupted."), False, None, seed_usato
            return

        if event_type == 'skip':
            yield "⏭️ Current generation skipped by user.", False, None, seed_usato
            return
        elif event_type == 'stale_interrupt':
            break
        elif event_type == 'progress':
            msg_rendering = dl.get("img_rendering", "🎨 Rendering Copy {copia_idx}/{totale_copie}: {data}%").replace("{data}%", "{data}").format(
                copia_idx=copia_idx+1, totale_copie=totale_copie, data=phase_progress(data)
            )
            yield msg_rendering, False, None, seed_usato
        elif event_type == 'executing':
            msg_processing = dl.get("img_processing", "⏳ Processing Copy {copia_idx}/{totale_copie}: {data}...").format(
                copia_idx=copia_idx+1, totale_copie=totale_copie, data=data
            )
            yield msg_processing, False, None, seed_usato
        elif event_type in ('executed_file', 'executed_info'):
            if data and os.path.exists(data):
                percorso_catturato = data
        elif event_type == 'done':
            break
        elif event_type == 'error':
            msg_err = dl.get("story_err_refine", "❌ Error on copy {copia_idx}.").format(copia_idx=copia_idx+1, idx=copia_idx+1)
            yield msg_err, False, None, seed_usato
            return
        elif event_type == 'timeout':
            msg_timeout = dl.get("story_timeout_refine", "⏳ Timeout copy {copia_idx}.").format(copia_idx=copia_idx+1, idx=copia_idx+1)
            yield msg_timeout, False, None, seed_usato
            continue

    if not comfyui_manager.generazione_attiva and not comfyui_manager.batch_attivo:
        yield "⏹️ Generation interrupted.", False, None, seed_usato
        return

    if percorso_catturato and os.path.exists(percorso_catturato):
        percorso_generato = percorso_catturato
    else:
        percorso_generato = recupera_file_generato(prompt_id)

    if not percorso_generato:
        if not comfyui_manager.generazione_attiva and not comfyui_manager.batch_attivo:
            yield "⏹️ Generation interrupted.", False, None, seed_usato
            return
        msg_missing = dl.get("img_err_missing", "❌ Unable to find generated file for copy {copia_idx}.").format(copia_idx=copia_idx+1)
        yield msg_missing, False, None, seed_usato
        return

    if percorso_generato:
        local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, sub_dir)
        os.makedirs(local_dir, exist_ok=True)
        ext = os.path.splitext(percorso_generato)[1][1:]

        s_curr = sessione.carica_ultima_sessione()
        generation_mode = s_curr.get("generation_mode", "Classica (1 Immagine)")
        is_batch = (sub_dir == config.STUDIO_BATCH_SUBDIR or getattr(comfyui_manager, "batch_attivo", False))

        if nome_sorgente_specifico:
            nome_sorgente = nome_sorgente_specifico
        else:
            percorso_sel = s_curr.get("percorso_immagine_selezionata")
            is_esterno = False
            if percorso_sel and os.path.exists(percorso_sel):
                output_dir_abs = os.path.abspath(config.STUDIO_OUTPUT_DIR)
                is_esterno = not os.path.abspath(percorso_sel).lower().startswith(output_dir_abs.lower())

            nome_sorgente = ""
            if is_batch or (is_esterno and "storyboard" not in str(generation_mode).lower()):
                nome_sorgente = s_curr.get("nome_immagine_sorgente", "")

        nome_sorgente_pulito = depura_nome_file_infinito(nome_sorgente)

        keywords_generati = {
            "zimage", "flux2", "flux2k", "krea2", "krea2_edit", "flux",
            "studio_output", "flux2_klein", "flux2_klein_refined",
            "frame_esteso", "frame"
        }
        if nome_sorgente_pulito.lower() in keywords_generati:
            nome_sorgente_pulito = ""

        base_prefix = "flux2" if modello_immagine_attivo == "Flux.2 Klein" else "krea2" if modello_immagine_attivo == "Krea-2 Turbo" else "zimage"

        if nome_sorgente_pulito:
            prefisso = f"{nome_sorgente_pulito}_{base_prefix}"
        else:
            prefisso = base_prefix

        prefisso = re.sub(r'__+', '_', prefisso).strip('_')

        nuovo_nome = config.genera_nome_univoco(local_dir, prefisso, ext)
        dest_path = os.path.abspath(os.path.join(local_dir, nuovo_nome))

        if sposta_file_sicuro(percorso_generato, dest_path):
            log.registra(f"Core Engine: File archived and moved successfully to {dest_path}")

            idea_attuale = s_curr.get("sceneggiatura_prompt", "")
            if idea_attuale.strip():
                hash_p = _calcola_hash_prompt(prompt_sanitizzato)
                subjects_dir = os.path.join(config.STUDIO_OUTPUT_DIR, "subjects")
                os.makedirs(subjects_dir, exist_ok=True)
                subj_path = os.path.join(subjects_dir, f"{hash_p}.txt")
                try:
                    with open(subj_path, "w", encoding="utf-8") as f_sub:
                        f_sub.write(idea_attuale.strip())
                    log.registra(f"Movie subject saved (VLM core): {subj_path}")
                except Exception as e:
                    log.registra(f"Unable to save subject file (hash): {e}", "WARNING")

            msg_done = dl.get("img_copy_done", "📸 Copy {copia_idx}/{totale_copie} generated!").format(copia_idx=copia_idx+1, totale_copie=totale_copie)
            yield msg_done, True, dest_path, seed_usato
        else:
            yield f"❌ Error during file transfer for copy {copia_idx+1}", False, None, seed_usato


def esegui_rendering_comfyui_core(
    prompt, modello_immagine_attivo,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h, steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    img_seed_mode, img_seed, copia_idx, totale_copie,
    ws_url, dl, sub_dir="images"
):
    if img_seed_mode == "fixed" and img_seed and str(img_seed).strip():
        try:
            seed_pulito = int(str(img_seed).strip()) + copia_idx
        except ValueError:
            seed_pulito = random.randint(1000000000000, 9999999999999)
    else:
        seed_pulito = random.randint(1000000000000, 9999999999999)

    prompt_id, wf, seed_usato, err_msg = invia_prompt_a_coda_comfyui(
        prompt, modello_immagine_attivo,
        l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
        w, h, steps, sampler_name, scheduler,
        hires_steps, hires_denoise, hires_scale,
        seed_pulito
    )

    if err_msg or prompt_id is None:
        yield (err_msg or dl.get("comfy_offline", "❌ ComfyUI Offline")), False, None, seed_pulito
        return

    yield from monitora_e_salva_singolo_task(
        prompt_id, wf, prompt, modello_immagine_attivo,
        seed_usato, copia_idx, totale_copie,
        ws_url, dl, sub_dir=sub_dir
    )


def esegui_rendering_comfyui_edit(
    prompt, seed_mode, custom_seed, steps, sampler_name, scheduler,
    grounding_px, input_image_path, ws_url, dl, sub_dir="images",
    krea2_edit_lora_strength=0.75,
    krea2_edit_height=1280, modello_edit="Krea-2 Turbo", loras=None
):
    if seed_mode == "fixed" and custom_seed and str(custom_seed).strip():
        try:
            seed_pulito = int(str(custom_seed).strip())
        except ValueError:
            seed_pulito = random.randint(1000000000000, 9999999999999)
    else:
        seed_pulito = random.randint(1000000000000, 9999999999999)

    prompt_sanitizzato = sanitizza_prompt_vlm(prompt)

    comfy_input_dir = os.path.abspath(os.path.join(config.COMFYUI_DIR, "ComfyUI", "input"))
    os.makedirs(comfy_input_dir, exist_ok=True)

    edit_prefix = "qwen21_edit" if modello_edit == "Qwen Image 2.1" else "krea2_edit"
    input_filename = f"{edit_prefix}_input_{time.time_ns()}{os.path.splitext(input_image_path)[1]}"
    dest_input_path = os.path.join(comfy_input_dir, input_filename)

    try:
        shutil.copy2(input_image_path, dest_input_path)
    except Exception as e:
        yield f"❌ Unable to copy source image: {e}", False, None, seed_pulito
        return

    file_path = os.path.abspath(os.path.join(os.path.dirname(config.WF_ZIMAGE_FILE), "krea2_turbo_edit_api.json"))
    if hasattr(config, "WF_KREA2_EDIT_FILE") and os.path.exists(config.WF_KREA2_EDIT_FILE):
        file_path = config.WF_KREA2_EDIT_FILE

    try:
        if modello_edit == "Qwen Image 2.1":
            file_path = os.path.join(os.path.dirname(config.WF_ZIMAGE_FILE), "qwen_image_2.1_edit_api.json")
            wf = workflow.prepara_workflow_qwen21_edit(file_path, input_filename, prompt_sanitizzato,
                                                      steps, sampler_name, scheduler, seed_pulito, loras=loras)
        else:
            wf = workflow.prepara_workflow_krea2_edit(
                file_path, input_filename, prompt_sanitizzato,
                steps, sampler_name, scheduler, seed_pulito, grounding_px,
                height=krea2_edit_height, krea2_edit_lora_strength=krea2_edit_lora_strength
            )
    except Exception as e:
        yield f"❌ Workflow compilation error: {e}", False, None, seed_pulito
        if os.path.exists(dest_input_path):
            try: os.remove(dest_input_path)
            except: pass
        return

    if wf is None:
        yield dl.get("comfy_offline", "❌ ComfyUI Offline"), False, None, seed_pulito
        if os.path.exists(dest_input_path):
            try: os.remove(dest_input_path)
            except: pass
        return

    percorso_catturato = None

    for tentativo in range(2):
        try:
            resp = requests.post(config.COMFYUI_URL + "/prompt", json={"prompt": wf, "client_id": client_id}, timeout=10)
            if resp.status_code != 200:
                try:
                    err_data = resp.json()
                    dettaglio_err = err_data.get("error", {}).get("message", err_data.get("node_errors", str(resp.text)))
                except Exception:
                    dettaglio_err = resp.text
                yield f"❌ ComfyUI Error ({resp.status_code}): {dettaglio_err}", False, None, seed_pulito
                if os.path.exists(dest_input_path):
                    try: os.remove(dest_input_path)
                    except: pass
                return
            prompt_id = resp.json()["prompt_id"]
        except Exception as e:
            yield f"❌ Submission failed: {e}", False, None, seed_pulito
            if os.path.exists(dest_input_path):
                try: os.remove(dest_input_path)
                except: pass
            return

        is_stale_interrupt = False
        for event_type, data in stream_webhook_events(prompt_id, ws_url, wf, timeout=float(config.TIMEOUT_COMFY_IMMAGINE)):
            if not comfyui_manager.generazione_attiva:
                yield dl.get("batch_status_interrupted", "⏹️ Generation interrupted."), False, None, seed_pulito
                if os.path.exists(dest_input_path):
                    try: os.remove(dest_input_path)
                    except: pass
                return

            if event_type == 'skip':
                yield dl["status_skip_user"], False, None, seed_pulito
                if os.path.exists(dest_input_path):
                    try: os.remove(dest_input_path)
                    except: pass
                return
            elif event_type == 'stale_interrupt':
                is_stale_interrupt = True
                break
            elif event_type == 'progress':
                msg_rendering = dl["status_edit_progress"].format(progress=phase_progress(data))
                yield msg_rendering, False, None, seed_pulito
            elif event_type == 'executing':
                class_type = data
                msg_processing = dl["status_edit_processing"].format(node=class_type)
                yield msg_processing, False, None, seed_pulito
            elif event_type in ('executed_file', 'executed_info'):
                if data and os.path.exists(data):
                    percorso_catturato = data
            elif event_type == 'done':
                break
            elif event_type == 'error':
                yield dl["status_edit_error"], False, None, seed_pulito
                if os.path.exists(dest_input_path):
                    try: os.remove(dest_input_path)
                    except: pass
                return
            elif event_type == 'timeout':
                yield "⏳ Timeout waiting for ComfyUI for image edit.", False, None, seed_pulito
                continue

        if is_stale_interrupt and tentativo == 0:
            log.registra("[Edit Engine] Detected residual interruption from ComfyUI. Auto-resubmitting prompt in 0.5s...")
            time.sleep(0.5)
            continue
        else:
            break

    if percorso_catturato and os.path.exists(percorso_catturato):
        percorso_generato = percorso_catturato
    else:
        percorso_generato = recupera_file_generato(prompt_id)

    if not percorso_generato:
        stopped = not comfyui_manager.generazione_attiva and not comfyui_manager.batch_attivo
        yield (dl["batch_status_interrupted"] if stopped else dl["status_edit_missing"]), False, None, seed_pulito
        if os.path.exists(dest_input_path):
            try: os.remove(dest_input_path)
            except: pass
        return

    if percorso_generato:
        local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, sub_dir)
        os.makedirs(local_dir, exist_ok=True)
        ext = os.path.splitext(percorso_generato)[1][1:]

        nome_sorgente = ""
        if input_image_path and os.path.exists(input_image_path):
            nome_sorgente = os.path.splitext(os.path.basename(input_image_path))[0]

        nome_sorgente_pulito = depura_nome_file_infinito(nome_sorgente)

        keywords_generati = {
            "zimage", "flux2", "flux2k", "krea2", "krea2_edit", "flux",
            "studio_output", "flux2_klein", "flux2_klein_refined",
            "frame_esteso", "frame"
        }
        if nome_sorgente_pulito.lower() in keywords_generati:
            nome_sorgente_pulito = ""

        if nome_sorgente_pulito:
            prefisso = f"{nome_sorgente_pulito}_{edit_prefix}"
        else:
            prefisso = edit_prefix

        prefisso = re.sub(r'__+', '_', prefisso).strip('_')

        nuovo_nome = config.genera_nome_univoco(local_dir, prefisso, ext)
        dest_path = os.path.abspath(os.path.join(local_dir, nuovo_nome))

        if sposta_file_sicuro(percorso_generato, dest_path):
            log.registra(f"Core Engine: Edited file archived successfully in {dest_path}")

            txt_path = os.path.splitext(dest_path)[0] + ".txt"
            try:
                with open(txt_path, "w", encoding="utf-8") as f_txt:
                    f_txt.write(f"{modello_edit} Edit: {prompt_sanitizzato}")
            except Exception as e:
                log.registra(f"Unable to save text file for edit prompt: {e}", "WARNING")

            yield dl["status_edit_done"], True, dest_path, seed_pulito
        else:
            yield dl["status_edit_transfer"], False, None, seed_pulito

    if os.path.exists(dest_input_path):
        try:
            os.remove(dest_input_path)
        except:
            pass
