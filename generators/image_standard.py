# generators/image_standard.py

import os
import time
import gradio as gr

from core import config, sessione, log
from services import comfyui_manager
from utils.media_utils import compila_galleria_html
from generators.image_utils import esegui_rendering_comfyui_core

def genera_immagine_standard(
    prompt,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h, copie,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo,
    img_seed_mode,
    img_seed,
    imm_gen_esistenti,
    seed_esistenti,
    html_avvio,
    ws_url,
    dl
):
    """
    Coordinated single generation pipeline on Core Engine.
    Sends real-time progress to UI and populates gallery progressively.
    """
    totale_copie = int(copie)

    for copia_idx in range(totale_copie):
        if not comfyui_manager.generazione_attiva:
            msg_stop = dl.get("batch_status_interrupted", "⏹️ Generation interrupted.")
            yield msg_stop, compila_galleria_html(imm_gen_esistenti)
            return

        for status_msg, is_done, final_path, seed_pulito in esegui_rendering_comfyui_core(
            prompt, modello_immagine_attivo,
            l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
            w, h, steps, sampler_name, scheduler,
            hires_steps, hires_denoise, hires_scale,
            img_seed_mode, img_seed, copia_idx, totale_copie,
            ws_url, dl, sub_dir=config.STUDIO_IMG_SUBDIR
        ):
            if is_done and final_path:
                imm_gen_esistenti.append(final_path)
                seed_esistenti.append(seed_pulito)
                yield status_msg, compila_galleria_html(imm_gen_esistenti)
            else:
                yield status_msg, compila_galleria_html(imm_gen_esistenti)

            if status_msg.startswith("❌") or status_msg.startswith("⏹️"):
                return

    sessione.salva_sessione({
        "immagini_generate_cumulate": imm_gen_esistenti,
        "seed_attuali_cumulati": seed_esistenti
    })