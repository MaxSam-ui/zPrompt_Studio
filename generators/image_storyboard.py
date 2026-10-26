from utils.progress_status import phase_progress
# generators/image_storyboard.py

import os
import time
import re
import glob
import random
import requests
import shutil
import tempfile
from contextlib import contextmanager
import gradio as gr
from functools import wraps
from PIL import Image, ImageOps

from core import config, sessione, log, workflow_registry
from generators import workflow
from generators.image_utils import sposta_file_sicuro, prepara_vlm_per_generazione
from services import comfyui_manager, local_vlm
from services.comfyui_manager import client_id
from utils.media_utils import (
    compila_galleria_html,
    norm_path_sicuro,
    depura_nome_file_infinito,
    pulisci_lista_percorsi_galleria,
    salva_soggetto_scena
)
from utils.image_processing import taglia_storyboard_pil, verifica_layout_storyboard, StoryboardLayoutError
from utils.websocket_monitor import stream_webhook_events, recupera_file_generato
from utils.storyboard_utils import is_vlm_status_message, estrai_prompt_pannello_robusto, storyboard_completo, normalizza_storyboard_catalogo

def _rilascia_stato_generazione(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            yield from fn(*args, **kwargs)
        finally:
            comfyui_manager.generazione_attiva = False
    return wrapped


# =========================================================================
# FUNZIONI HELPER INTERNE
# =========================================================================

@contextmanager
def _pannello_temporaneo_comfy(source):
    directory = os.path.join(config.COMFYUI_DIR, "ComfyUI", "input")
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="storyboard_refine_", suffix=".png", dir=directory, delete=False) as temporary:
        path = temporary.name
    try:
        shutil.copy2(source, path)
        yield os.path.basename(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

def _parse_num_pannelli(valore) -> int:
    """Estrae e normalizza il numero di pannelli (clamp tra 2 e 4)."""
    try:
        if isinstance(valore, (int, float)):
            n = int(valore)
        else:
            match = re.search(r'(\d+)', str(valore))
            n = int(match.group(1)) if match else 3
    except Exception:
        n = 3
    return max(2, min(4, n))


def calcola_geometria_griglia_automatica(target_w: int, target_h: int, num_pannelli: int):
    """
    Calcola le dimensioni della griglia ComfyUI garantendo alta risoluzione per pannello
    mantenendo la proporzione target.
    """
    ratio = float(target_w) / float(target_h)

    if ratio >= 1.25:  # Landscape (Orizzontale)
        h_grid = 576
        shape_desc = "widescreen landscape"
    elif ratio <= 0.8:  # Portrait (Verticale)
        h_grid = 768
        shape_desc = "vertical portrait"
    else:  # Square (Quadrato 1:1)
        h_grid = 640
        shape_desc = "square"

    w_panel_raw = h_grid * ratio
    w_panel = int(w_panel_raw // 32) * 32
    w_grid_raw = num_pannelli * w_panel

    w_grid = max(512, int((w_grid_raw // 64) * 64))
    h_grid = max(384, int((h_grid // 64) * 64))

    return w_grid, h_grid, shape_desc


def _costruisci_template_storyboard(num_pannelli: int, shape_desc: str, stile_preset: str) -> str:
    from utils.prompt_templates import SCENE_CONTRACT, render_template, system_template
    template = system_template("Master_Storyboard_Template.txt",
        "Output a horizontal {num_pannelli_int}-panel storyboard grid, shared context, then panel1: through panel{num_pannelli_int}: with one visible moment each. {regole_estetiche_storyboard}")
    return render_template(template, num_pannelli_int=num_pannelli, shape_desc=shape_desc,
        regole_estetiche_storyboard=stile_preset if stile_preset and stile_preset != "-" else "Preserve the requested visual medium.") + "\n\n" + SCENE_CONTRACT


def _salva_pannello_su_disco(p_sorgente: str, prefisso_tipo: str, target_w: int, target_h: int, prompt_specifico: str, flux_grid_prompt: str) -> str:
    """Salva il pannello ritagliato/raffinato su disco, crea il file .txt adiacente e archivia il soggetto."""
    local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_IMG_SUBDIR)
    os.makedirs(local_dir, exist_ok=True)

    s_curr = sessione.carica_ultima_sessione()
    nome_sorgente = depura_nome_file_infinito(s_curr.get("nome_immagine_sorgente", ""))
    nome_base_orig = depura_nome_file_infinito(os.path.splitext(os.path.basename(p_sorgente))[0])

    if nome_sorgente and nome_sorgente != "studio_output":
        prefisso = f"{nome_base_orig}_{prefisso_tipo}" if nome_sorgente in nome_base_orig else f"{nome_sorgente}_{nome_base_orig}_{prefisso_tipo}"
    else:
        prefisso = f"{nome_base_orig}_{prefisso_tipo}"

    prefisso = depura_nome_file_infinito(prefisso)
    nuovo_nome = config.genera_nome_univoco(local_dir, prefisso, "png")
    dest_path = os.path.abspath(os.path.join(local_dir, nuovo_nome))

    try:
        with Image.open(p_sorgente) as im_raw:
            if im_raw.size != (target_w, target_h):
                im_resized = ImageOps.fit(im_raw, (target_w, target_h), method=Image.LANCZOS)
                im_resized.save(dest_path, "PNG")
            else:
                im_raw.save(dest_path, "PNG")
    except Exception as e:
        log.registra(f"Error saving final panel image: {e}", "WARNING")
        shutil.copy2(p_sorgente, dest_path)

    txt_path = os.path.splitext(dest_path)[0] + ".txt"
    try:
        with open(txt_path, "w", encoding="utf-8") as f_txt:
            f_txt.write(prompt_specifico)
    except Exception as e_txt:
        log.registra(f"Unable to save prompt txt file: {e_txt}", "WARNING")

    idea_attuale = s_curr.get("sceneggiatura_prompt", "")
    if idea_attuale.strip():
        salva_soggetto_scena(flux_grid_prompt, idea_attuale)

    return dest_path


# =========================================================================
# 1. COMPILAZIONE TESTO STORYBOARD (VLM)
# =========================================================================

@_rilascia_stato_generazione
def compila_solo_testo_storyboard(
    prompt, m_vlm, sugg_storyboard, storyboard_pannelli,
    stato_gen
):
    num_pannelli_int = _parse_num_pannelli(storyboard_pannelli)
    prompt_iniziale_sicuro = prompt or ""

    s_active = sessione.carica_ultima_sessione()
    try:
        tw = int(s_active.get("img_width", 1024))
        th = int(s_active.get("img_height", 1024))
    except Exception:
        tw, th = 1024, 1024

    _, _, shape_desc = calcola_geometria_griglia_automatica(tw, th, num_pannelli_int)
    grid_header = f"horizontal {num_pannelli_int}-panel storyboard grid,"

    stile_preset = ""
    if sugg_storyboard and sugg_storyboard != "-":
        stile_preset = config.leggi_contenuto_suggerimento(config.SUGGESTION_STORYBOARD_DIR, sugg_storyboard)

    istruzioni_storyboard = _costruisci_template_storyboard(num_pannelli_int, shape_desc, stile_preset)
    sys_prompt_storyboard = "You are an expert cinematic storyboard prompt engineer."

    lang = s_active.get("lingua_selezionata", "IT")
    from core import lingua
    dl_active = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    if not prompt_iniziale_sicuro.strip():
        yield gr.update(), gr.update(), dl_active["msg_prompt_vuoto"]
        return

    accumulato = ""
    for chunk in local_vlm.affina_descrizione_immagine(
        descrizione_corrente=prompt_iniziale_sicuro,
        istruzioni_affinamento=istruzioni_storyboard,
        sistema_prompt=sys_prompt_storyboard,
        modello_selezionato=m_vlm
    ):
        if str(chunk).startswith(("❌", "⚠", "⏹", "🛑", "Errore", "Error")):
            yield gr.update(), gr.update(), ("❌ " if str(chunk).startswith(("Errore", "Error")) else "") + str(chunk)
            return
        if is_vlm_status_message(chunk, dl_active):
            msg_st = chunk
            testo_inviato = prompt_iniziale_sicuro
        else:
            accumulato = chunk
            msg_st = dl_active.get("story_compiling", "⏳ Compilazione storyboard AI in corso...")
            testo_inviato = accumulato.strip() if accumulato.strip() else prompt_iniziale_sicuro

        yield testo_inviato, gr.update(), msg_st

    if comfyui_manager.vlm_interrotto or not accumulato.strip():
        status = dl_active['batch_status_interrupted'] if comfyui_manager.vlm_interrotto else dl_active['analysis_empty_result']
        yield gr.update(), gr.update(), status
        return
    if not storyboard_completo(accumulato, num_pannelli_int):
        yield gr.update(), gr.update(), dl_active["story_invalid_panels"].format(count=num_pannelli_int)
        return
    testo_pulito = normalizza_storyboard_catalogo(prompt_iniziale_sicuro, accumulato.strip(), num_pannelli_int, stile_preset)
    if not storyboard_completo(testo_pulito, num_pannelli_int):
        yield gr.update(), gr.update(), dl_active["story_invalid_panels"].format(count=num_pannelli_int)
        return

    if not any(k in testo_pulito.lower()[:60] for k in ["grid", "panel", "pannel"]):
        flux_grid_prompt = f"{grid_header}\n\n{testo_pulito}"
    else:
        flux_grid_prompt = testo_pulito

    ltx_timeline = f"[0.0s - 4.0s] 🧍 [Shot] Medium Shot | ⏹️ [Static] Static (No Zoom) | Visual storyboard progression tracking based on the generated panels."

    if stato_gen is not None:
        stato_gen["ultimo_sceneggiato_timeline"] = ltx_timeline
        stato_gen["ultimo_sceneggiato_prompt"] = flux_grid_prompt

    context = {"prompt": flux_grid_prompt, "preset": sugg_storyboard, "panels": num_pannelli_int}
    sessione.salva_sessione({"prompt_to_send_img": flux_grid_prompt, "storyboard_compiled_context": context})
    yield flux_grid_prompt, ltx_timeline, dl_active.get("storyboard_compiled_success", "✅ Storyboard compilato!")


# =========================================================================
# FASE 1: GENERA SOLO GRIGLIA STORYBOARD (ANTEPRIMA)
# =========================================================================

def genera_solo_griglia_storyboard(
    prompt, m_vlm, sugg_storyboard, storyboard_pannelli,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo,
    img_seed_mode,
    img_seed,
    html_avvio,
    ws_url,
    dl
):
    num_pannelli_int = _parse_num_pannelli(storyboard_pannelli)
    flux_grid_prompt = None
    ltx_timeline = None

    comfyui_manager.generazione_attiva = True
    comfyui_manager.vlm_interrotto = False

    try:
        target_w = int(w) if w else 1024
        target_h = int(h) if h else 1024
    except Exception:
        target_w, target_h = 1024, 1024

    w_grid, h_grid, shape_desc = calcola_geometria_griglia_automatica(target_w, target_h, num_pannelli_int)
    grid_header = f"horizontal {num_pannelli_int}-panel storyboard grid,"

    log.registra(f"[Storyboard Phase 1: Grid] Canvas: {w_grid}x{h_grid}")

    try:
        is_storyboard_prompt = False
        if prompt:
            context = sessione.carica_ultima_sessione().get("storyboard_compiled_context", {})
            changed_preset = context.get("prompt") == prompt.strip() and context.get("preset") != sugg_storyboard
            if storyboard_completo(prompt, num_pannelli_int) and not changed_preset:
                is_storyboard_prompt = True
                flux_grid_prompt = prompt.strip()
                if stato_gen and stato_gen.get("ultimo_sceneggiato_timeline"):
                    ltx_timeline = stato_gen.get("ultimo_sceneggiato_timeline")

        stile_preset = ""
        if sugg_storyboard and sugg_storyboard != "-":
            stile_preset = config.leggi_contenuto_suggerimento(config.SUGGESTION_STORYBOARD_DIR, sugg_storyboard)

        if is_storyboard_prompt and flux_grid_prompt:
            log.registra("Storyboard: Using active prompt from UI.")
            if not ltx_timeline:
                ltx_timeline = f"[0.0s - 4.0s] 🧍 [Shot] Medium Shot | ⏹️ [Static] Static (No Zoom) | Storyboard progression."
            sessione.salva_sessione({"prompt_to_send_img": flux_grid_prompt})
            yield dl.get("story_prompt_existing", "📝 Starting grid generation..."), html_avvio, flux_grid_prompt, ltx_timeline
        else:
            prompt_iniziale_sicuro = prompt or ""
            if not prompt_iniziale_sicuro.strip():
                yield dl["msg_prompt_vuoto"], html_avvio, gr.update(), gr.update()
                return
            istruzioni_storyboard = _costruisci_template_storyboard(num_pannelli_int, shape_desc, stile_preset)
            sys_prompt_storyboard = "You are an expert cinematic storyboard prompt engineer."

            llm_raw_output = ""
            for chunk in local_vlm.affina_descrizione_immagine(
                descrizione_corrente=prompt_iniziale_sicuro,
                istruzioni_affinamento=istruzioni_storyboard,
                sistema_prompt=sys_prompt_storyboard,
                modello_selezionato=m_vlm
            ):
                if str(chunk).startswith(("❌", "⚠", "⏹", "🛑", "Errore", "Error")):
                    yield ("❌ " if str(chunk).startswith(("Errore", "Error")) else "") + str(chunk), html_avvio, gr.update(), gr.update()
                    return
                if is_vlm_status_message(chunk, dl):
                    msg_comp = chunk
                else:
                    llm_raw_output = chunk
                    msg_comp = dl.get("story_compiling", "⏳ Compilazione storyboard AI in corso...")

                prompt_visibile = llm_raw_output.strip() if llm_raw_output.strip() else prompt_iniziale_sicuro
                yield msg_comp, html_avvio, prompt_visibile, gr.update()

            if comfyui_manager.vlm_interrotto or not llm_raw_output.strip():
                status = dl['batch_status_interrupted'] if comfyui_manager.vlm_interrotto else dl['analysis_empty_result']
                yield status, html_avvio, gr.update(), gr.update()
                return
            if not storyboard_completo(llm_raw_output, num_pannelli_int):
                yield dl["story_invalid_panels"].format(count=num_pannelli_int), html_avvio, gr.update(), gr.update()
                return
            testo_pulito = normalizza_storyboard_catalogo(prompt_iniziale_sicuro, llm_raw_output.strip(), num_pannelli_int, stile_preset)
            if not storyboard_completo(testo_pulito, num_pannelli_int):
                yield dl["story_invalid_panels"].format(count=num_pannelli_int), html_avvio, gr.update(), gr.update()
                return
            flux_grid_prompt = testo_pulito if any(k in testo_pulito.lower()[:60] for k in ["grid", "panel", "pannel"]) else f"{grid_header}\n\n{testo_pulito}"
            ltx_timeline = f"[0.0s - 4.0s] 🧍 [Shot] Medium Shot | ⏹️ [Static] Static (No Zoom) | Storyboard progression."

            if stato_gen:
                stato_gen["ultimo_sceneggiato_timeline"] = ltx_timeline
                stato_gen["ultimo_sceneggiato_prompt"] = flux_grid_prompt
            sessione.salva_sessione({"prompt_to_send_img": flux_grid_prompt, "storyboard_compiled_context": {"prompt": flux_grid_prompt, "preset": sugg_storyboard, "panels": num_pannelli_int}})

        prepara_vlm_per_generazione()
        comfyui_manager.generazione_attiva = True
        comfyui_manager.vlm_interrotto = False

        composition = {2: "diptych", 3: "triptych", 4: "four-panel strip"}[num_pannelli_int]
        # Photographic composition terms are less likely to evoke the model's
        # habitual 2x2 'storyboard grid', particularly for two-frame requests.
        visual_prompt = re.sub(r"horizontal\s+\d+-panel\s+(?:storyboard\s+)?grid,?", "", flux_grid_prompt, flags=re.I).strip()
        prompt_griglia_effettivo = (
            f"A {composition}. Exactly {num_pannelli_int} equal-sized panels in ONE horizontal row, "
            "read left to right, separated by thin straight vertical borders. "
            "No second row, no extra panels, no inset pictures.\n\n" + visual_prompt
        )

        if img_seed_mode == "fixed" and img_seed and str(img_seed).strip():
            try:
                seed_pulito = int(str(img_seed).strip())
            except ValueError:
                seed_pulito = random.randint(1000000000000, 9999999999999)
        else:
            seed_pulito = random.randint(1000000000000, 9999999999999)

        file_wf = workflow_registry.risolvi_percorso_json_immagine(modello_immagine_attivo)

        if modello_immagine_attivo == "Flux.2 Klein":
            wf = workflow.prepara_workflow_flux2(
                file_wf, prompt_griglia_effettivo,
                l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
                w_grid, h_grid, 1,
                steps=steps, sampler_name=sampler_name, scheduler=scheduler,
                hires_steps=hires_steps, hires_denoise=hires_denoise,
                seed_mode="fixed", custom_seed=seed_pulito
            )
        elif modello_immagine_attivo == "Krea-2 Turbo":
            wf = workflow.prepara_workflow_krea2(
                file_wf, prompt_griglia_effettivo,
                l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
                w_grid, h_grid, 1,
                steps=steps, sampler_name=sampler_name, scheduler=scheduler,
                seed_mode="fixed", custom_seed=seed_pulito
            )
        else:
            wf = workflow.prepara_workflow_z_image(
                file_wf, prompt_griglia_effettivo,
                l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
                w_grid, h_grid, 1,
                steps=steps, sampler_name=sampler_name, scheduler=scheduler,
                hires_steps=hires_steps, hires_denoise=hires_denoise,
                hires_scale=hires_scale,
                seed_mode="fixed", custom_seed=seed_pulito
            )

        if wf is None:
            yield dl.get("comfy_offline", "❌ ComfyUI Offline"), html_avvio, flux_grid_prompt, ltx_timeline
            return

        percorso_catturato_grid = None

        for tentativo_grid in range(2):
            try:
                resp = requests.post(config.COMFYUI_URL + "/prompt", json={"prompt": wf, "client_id": client_id}, timeout=60)
                resp.raise_for_status()
                prompt_id_grid = resp.json()["prompt_id"]
            except Exception as e:
                yield f"❌ Submission failed: {e}", html_avvio, flux_grid_prompt, ltx_timeline
                return

            is_stale_grid = False
            for event_type, data in stream_webhook_events(prompt_id_grid, ws_url, wf, timeout=600.0):
                if not comfyui_manager.generazione_attiva:
                    yield dl.get("batch_status_interrupted", "⏹️ Generation interrupted."), html_avvio, flux_grid_prompt, ltx_timeline
                    return
                if event_type == 'stale_interrupt':
                    is_stale_grid = True
                    break
                elif event_type == 'progress':
                    yield dl.get("story_grid_rendering", "🎨 Storyboard Grid: {data}").replace("{data}%", "{data}").format(data=phase_progress(data)), html_avvio, flux_grid_prompt, ltx_timeline
                elif event_type in ('executed_file', 'executed_info'):
                    if data and os.path.exists(data):
                        percorso_catturato_grid = data
                elif event_type == 'done':
                    break
                elif event_type == 'error':
                    yield dl.get("story_err_grid", "❌ ComfyUI error during grid generation."), html_avvio, flux_grid_prompt, ltx_timeline
                    return
                elif event_type == 'timeout':
                    yield dl.get("story_timeout_grid", "⏳ Timeout on grid."), html_avvio, flux_grid_prompt, ltx_timeline
                    continue

            if is_stale_grid and tentativo_grid == 0:
                time.sleep(0.5)
                continue
            else:
                break

        percorso_griglia = percorso_catturato_grid if (percorso_catturato_grid and os.path.exists(percorso_catturato_grid)) else recupera_file_generato(prompt_id_grid)

        if not percorso_griglia:
            yield dl.get("story_err_grid_missing", "❌ Error: grid not recovered."), html_avvio, flux_grid_prompt, ltx_timeline
            return

        # Salvataggio della griglia per la Fase 2 (Taglio)
        local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_IMG_SUBDIR)
        grid_backup_dir = os.path.join(local_dir, "storyboard_grids")
        os.makedirs(grid_backup_dir, exist_ok=True)
        nuovo_nome_grid = config.genera_nome_univoco(grid_backup_dir, "storyboard_grid", "png")
        dest_path_grid = os.path.abspath(os.path.join(grid_backup_dir, nuovo_nome_grid))
        sposta_file_sicuro(percorso_griglia, dest_path_grid)

        stato_gen["ultima_griglia_storyboard"] = dest_path_grid
        stato_gen["ultimo_seed_griglia"] = seed_pulito
        stato_gen["lista_frame_storyboard_attivi"] = [dest_path_grid]
        stato_gen["seed_attuali_cumulati"] = [seed_pulito]
        stato_gen["gallery_no_sync"] = True

        sessione.salva_sessione({
            "lista_frame_storyboard_attivi": [dest_path_grid],
            "seed_attuali_cumulati": [seed_pulito],
            "prompt_to_send_img": flux_grid_prompt,
            "ultima_griglia_storyboard": dest_path_grid
        })

        msg_preview_done = dl.get("storyboard_grid_done", "✅ Griglia Storyboard generata! Se ti piace, clicca su '✂️ Taglia Pannelli'.")
        try:
            verifica_layout_storyboard(dest_path_grid, num_pannelli_int)
        except StoryboardLayoutError:
            msg_preview_done = dl["story_layout_mismatch"]
        yield msg_preview_done, compila_galleria_html([dest_path_grid]), flux_grid_prompt, ltx_timeline

    except Exception as err_proc:
        import traceback
        log.registra(f"Error in Phase 1 storyboard grid: {err_proc}", "ERROR")
        log.registra(traceback.format_exc(), "ERROR")
        yield f"❌ Error: {err_proc}", html_avvio, flux_grid_prompt, ltx_timeline
    finally:
        comfyui_manager.generazione_attiva = False


# =========================================================================
# FASE 2: APPROVA E TAGLIA PANNELLI (SLICING + EVENTUALE REFINE)
# =========================================================================

@_rilascia_stato_generazione
def taglia_e_processa_storyboard(
    stato_gen,
    modello_immagine_attivo,
    w, h,
    storyboard_pannelli,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    attiva_refine_storyboard,
    refine_denoise,
    sugg_storyboard,
    ws_url,
    dl
):
    if stato_gen is None:
        stato_gen = {}

    s_curr = sessione.carica_ultima_sessione()
    percorso_griglia = stato_gen.get("ultima_griglia_storyboard") or s_curr.get("ultima_griglia_storyboard")

    if not percorso_griglia or not os.path.exists(percorso_griglia):
        msg_no_grid = dl.get("err_no_grid_to_slice", "⚠️ Nessuna griglia disponibile da tagliare. Genera prima una griglia!")
        yield msg_no_grid, gr.update(), gr.update(), gr.update()
        return

    comfyui_manager.generazione_attiva = True
    comfyui_manager.vlm_interrotto = False

    num_pannelli_int = _parse_num_pannelli(storyboard_pannelli)
    flux_grid_prompt = stato_gen.get("ultimo_sceneggiato_prompt") or s_curr.get("prompt_to_send_img", "")
    seed_pulito = stato_gen.get("ultimo_seed_griglia", random.randint(1000000000000, 9999999999999))

    try:
        target_w = int(w) if w else 1024
        target_h = int(h) if h else 1024
    except Exception:
        target_w, target_h = 1024, 1024

    yield dl.get("story_slicing", "✂️ Taglio dei pannelli in corso..."), gr.update(), flux_grid_prompt, gr.update()

    try:
        pannelli_ritagliati = taglia_storyboard_pil(percorso_griglia, num_pannelli_int)
    except StoryboardLayoutError:
        yield dl["story_layout_mismatch"], gr.update(), flux_grid_prompt, gr.update()
        return
    if not pannelli_ritagliati:
        yield dl.get("story_err_slicing", "❌ Errore durante il ritaglio della griglia."), gr.update(), flux_grid_prompt, gr.update()
        return

    stile_preset = ""
    if sugg_storyboard and sugg_storyboard != "-":
        stile_preset = config.leggi_contenuto_suggerimento(config.SUGGESTION_STORYBOARD_DIR, sugg_storyboard)

    finali_tagliati = []
    seed_esistenti = []
    refined_count = 0

    if attiva_refine_storyboard:
        for idx, p_panel in enumerate(pannelli_ritagliati):
            if not comfyui_manager.generazione_attiva:
                break

            msg_ref_init = dl.get("story_refining_init", "🔮 Refining frame {idx}/{total}...").format(idx=idx+1, total=num_pannelli_int)
            yield msg_ref_init, gr.update(), flux_grid_prompt, gr.update()

            with _pannello_temporaneo_comfy(p_panel) as nome_immagine_pannello:
                prompt_pannello_specifico = estrai_prompt_pannello_robusto(flux_grid_prompt, idx, stile_preset=stile_preset)
                file_wf_ref = workflow_registry.risolvi_percorso_json_immagine(modello_immagine_attivo)

                if modello_immagine_attivo == "Flux.2 Klein":
                    wf_ref = workflow.prepara_workflow_img2img_flux2(
                        file_wf_ref, nome_immagine_pannello, prompt_pannello_specifico,
                        steps=steps, sampler_name=sampler_name, scheduler=scheduler,
                        denoise=refine_denoise, seed=seed_pulito,
                        l1_n=l1_n, l1_s=l1_s, l2_n=l2_n, l2_s=l2_s, l3_n=l3_n, l3_s=l3_s,
                        larghezza=target_w, altezza=target_h
                    )
                elif modello_immagine_attivo == "Krea-2 Turbo":
                    wf_ref = workflow.prepara_workflow_img2img_krea2(
                        file_wf_ref, nome_immagine_pannello, prompt_pannello_specifico,
                        steps=steps, sampler_name=sampler_name, scheduler=scheduler,
                        denoise=refine_denoise, seed=seed_pulito,
                        l1_n=l1_n, l1_s=l1_s, l2_n=l2_n, l2_s=l2_s, l3_n=l3_n, l3_s=l3_s,
                        larghezza=target_w, altezza=target_h
                    )
                else:
                    wf_ref = workflow.prepara_workflow_img2img_z_image(
                        file_wf_ref, nome_immagine_pannello, prompt_pannello_specifico,
                        steps=hires_steps, sampler_name=sampler_name, scheduler=scheduler,
                        denoise=refine_denoise, seed=seed_pulito,
                        l1_n=l1_n, l1_s=l1_s, l2_n=l2_n, l2_s=l2_s, l3_n=l3_n, l3_s=l3_s,
                        larghezza=target_w, altezza=target_h, scale_factor=1.0
                    )

                if wf_ref is None:
                    dest_salvato = _salva_pannello_su_disco(p_panel, "panel", target_w, target_h, prompt_pannello_specifico, flux_grid_prompt)
                    finali_tagliati.append(dest_salvato)
                    seed_esistenti.append(seed_pulito)
                    continue

                percorso_catturato_ref = None
                prompt_id_ref = None

                for tentativo_ref in range(2):
                    try:
                        resp_ref = requests.post(config.COMFYUI_URL + "/prompt", json={"prompt": wf_ref, "client_id": client_id}, timeout=30)
                        resp_ref.raise_for_status()
                        prompt_id_ref = resp_ref.json()["prompt_id"]
                    except Exception as error:
                        log.registra(f"Storyboard panel {idx+1}: refinement submission failed: {error}", "WARNING")
                        break

                    is_stale_ref = False
                    for event_type, data in stream_webhook_events(prompt_id_ref, ws_url, wf_ref, timeout=600.0):
                        if not comfyui_manager.generazione_attiva:
                            yield dl.get("batch_status_interrupted", "⏹️ Generation interrupted."), gr.update(), flux_grid_prompt, gr.update()
                            return
                        if event_type == 'stale_interrupt':
                            is_stale_ref = True
                            break
                        elif event_type == 'progress':
                            yield dl.get("story_refining_progress", "🔮 Refining frame {idx}/{total}: {data}").replace("{data}%", "{data}").format(idx=idx+1, total=num_pannelli_int, data=phase_progress(data)), gr.update(), flux_grid_prompt, gr.update()
                        elif event_type in ('executed_file', 'executed_info'):
                            if data and os.path.exists(data):
                                percorso_catturato_ref = data
                        elif event_type == 'done':
                            break
                        elif event_type == 'error':
                            yield dl.get("story_err_refine", "❌ ComfyUI error refining panel {idx}.").format(idx=idx+1), gr.update(), flux_grid_prompt, gr.update()
                            return
                        elif event_type == 'timeout':
                            yield dl.get("story_timeout_refine", "⏳ Timeout refining panel {idx}.").format(idx=idx+1), gr.update(), flux_grid_prompt, gr.update()
                            continue

                    if is_stale_ref and tentativo_ref == 0:
                        time.sleep(0.5)
                        continue
                    else:
                        break

                percorso_raffinato = percorso_catturato_ref if (percorso_catturato_ref and os.path.exists(percorso_catturato_ref)) else (recupera_file_generato(prompt_id_ref) if prompt_id_ref else None)


            sorgente_finale = percorso_raffinato if (percorso_raffinato and os.path.exists(percorso_raffinato)) else p_panel
            prefisso_usato = "refined" if (percorso_raffinato and os.path.exists(percorso_raffinato)) else "panel"
            if prefisso_usato == "refined":
                refined_count += 1

            dest_salvato = _salva_pannello_su_disco(sorgente_finale, prefisso_usato, target_w, target_h, prompt_pannello_specifico, flux_grid_prompt)
            finali_tagliati.append(dest_salvato)
            seed_esistenti.append(seed_pulito)

            if os.path.exists(p_panel) and dest_salvato != p_panel:
                try:
                    os.remove(p_panel)
                except Exception:
                    pass
    else:
        for idx, p_panel in enumerate(pannelli_ritagliati):
            prompt_pannello_specifico = estrai_prompt_pannello_robusto(flux_grid_prompt, idx, stile_preset=stile_preset)
            dest_salvato = _salva_pannello_su_disco(p_panel, "panel", target_w, target_h, prompt_pannello_specifico, flux_grid_prompt)
            finali_tagliati.append(dest_salvato)
            seed_esistenti.append(seed_pulito)

            if os.path.exists(p_panel) and dest_salvato != p_panel:
                try:
                    os.remove(p_panel)
                except Exception:
                    pass

    finali_tagliati[:] = pulisci_lista_percorsi_galleria(finali_tagliati)

    stato_gen["lista_frame_storyboard_attivi"] = finali_tagliati
    stato_gen["seed_attuali_cumulati"] = seed_esistenti
    stato_gen["percorso_immagine_selezionata"] = finali_tagliati[0] if finali_tagliati else None
    stato_gen["gallery_no_sync"] = True

    sessione.salva_sessione({
        "lista_frame_storyboard_attivi": finali_tagliati,
        "seed_attuali_cumulati": seed_esistenti,
        "percorso_immagine_selezionata": finali_tagliati[0] if finali_tagliati else None
    })

    if not comfyui_manager.generazione_attiva:
        msg_done = dl['batch_status_interrupted']
    elif not finali_tagliati:
        msg_done = dl['story_err_slicing']
    elif attiva_refine_storyboard and refined_count < len(finali_tagliati):
        msg_done = dl['story_refine_partial'].format(done=refined_count, total=len(finali_tagliati))
    else:
        msg_done = dl.get("storyboard_slicing_done", "✅ Fotogrammi tagliati e pronti per il Tab Video! ({total} foto)").format(total=len(finali_tagliati))
    yield msg_done, compila_galleria_html(finali_tagliati, percorso_selezionato=finali_tagliati[0] if finali_tagliati else None), flux_grid_prompt, gr.update()
