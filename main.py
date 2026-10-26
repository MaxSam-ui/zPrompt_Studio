# main.py

import sys
import asyncio
import tempfile
import time
import os
import threading
import signal
if __name__ == "__main__":
    print("[START 1/3] Loading web interface...", flush=True)
import gradio as gr

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core import config, sessione, log, hardware, lingua
if __name__ == "__main__":
    print("[START 2/3] Loading AI libraries...", flush=True)
from services import local_vlm, comfyui_manager
from services.help_routes import manual_routes
from ui import style, tab_analisi, tab_rendering, tab_video, tab_batch, tab_log
from ui.barra_superiore import crea_barra_superiore, aggiorna_stato_comfyui
from events import eventi_analisi, eventi_rendering, eventi_video, eventi_batch, eventi_sistema, eventi_sessione, eventi_lingua
from utils import js_helpers, media_utils

from services.gradio_compat import configure_warnings
configure_warnings()

log.registra("Start application zPrompt Studio...")
if __name__ == "__main__":
    print("[START 3/3] Building application controls...", flush=True)

# REGISTRAZIONE GESTORE SEGNALI DI SISTEMA PER CHIUSURA PULITA
def gestisci_chiusura_sistema(signum, frame):
    log.registra(f"Shutdown signal received ({signum}). Terminating ComfyUI and exiting...")
    comfyui_manager.stop_comfyui()
    sys.exit(0)

try:
    signal.signal(signal.SIGINT, gestisci_chiusura_sistema)
    signal.signal(signal.SIGTERM, gestisci_chiusura_sistema)
except Exception:
    pass

s = sessione.carica_ultima_sessione()
d = lingua.ottieni_dizionario_lingua(s.get("lingua_selezionata", "IT"))

modello_warmup = s.get("modello_vlm", "huihui_ai/qwen3-vl-abliterated:8b")

lista_modelli_vlm = local_vlm.ottieni_modelli_disponibili()
SUGG_VISION_LIST = config.elenca_suggerimenti(config.SUGGESTION_VISION_DIR)

stato_iniziale = {
    "seed_attuali": s.get("seed_attuali_cumulati", []),
    "percorso_immagine_selezionata": s.get("percorso_immagine_selezionata", None),
    "percorso_immagine_destinazione": s.get("percorso_immagine_destinazione", None),
    "immagini_generate_cumulate": s.get("immagini_generate_cumulate", []),
    "lista_frame_storyboard_attivi": s.get("lista_frame_storyboard_attivi", []),
    "seed_attuali_cumulati": s.get("seed_attuali_cumulati", []),
    "immagini_generate_batch": s.get("immagini_generate_batch", []), 
    "gallery_no_sync": True
}

js_traduci_tab_header = js_helpers.genera_script_traduci_tab_header()

with gr.Blocks(title="zPrompt Studio") as demo:
    stato_sessione = gr.State(value=s)
    stato_generazione = gr.State(value=stato_iniziale)

    bar_dict = crea_barra_superiore(d)
    titolo_app = bar_dict["titolo_app"]
    testo_hardware = bar_dict["testo_hardware"]
    spia_comfy = bar_dict["spia_comfy"]
    btn_clean_mem = bar_dict["btn_clean_mem"]
    btn_hard_reset = bar_dict["btn_hard_reset"]
    barra_sup_row = bar_dict["barra_superiore"]

    num_lora_img = gr.State(value=s.get("lora_visibili_count", 1))
    num_lora_vid = gr.State(value=s.get("lora_video_visibili_count", 1))
    num_lora_batch = gr.State(value=s.get("lora_batch_visibili_count", 1)) 

    testo_iniziale_timeline = s.get("lista_scene_salvate", "")

    with gr.Tabs(elem_id="main-tabs-container") as tabs_container:
        t1 = tab_analisi.crea_tab_analisi(d, s, lista_modelli_vlm, SUGG_VISION_LIST)
        t2 = tab_rendering.crea_tab_rendering(d, s)
        t3 = tab_video.crea_tab_video(d, s, lista_modelli_vlm, [], testo_iniziale_timeline)
        t4 = tab_batch.crea_tab_batch(d, s, lista_modelli_vlm, [])
        t5 = tab_log.crea_tab_log(d, s)

    # MODALE LIGHTBOX UNICO GLOBALE
    gr.HTML(value=media_utils.ottieni_lightbox_modal_html(), visible=True)

    timer_hardware = gr.Timer(value=5.0)
    timer_hardware.tick(fn=hardware.ottieni_stato_risorse, inputs=None, outputs=testo_hardware)
    btn_clean_mem.click(fn=lambda: hardware.libera_risorse_sistema(), inputs=None, outputs=testo_hardware)

    # CORREZIONE: Mappatura completa e simmetrica a 12 elementi per bloccare tutti i pulsanti VLM durante la generazione
    timer_comfyui = gr.Timer(value=3.0)
    timer_comfyui.tick(
        fn=aggiorna_stato_comfyui, 
        inputs=None,
        outputs=[
            spia_comfy, 
            t2["btn_send_comfy_img"], 
            t3["btn_send_comfy_vid"], 
            t4["btn_start_batch"],
            t1["btn_analyze"], 
            t2["btn_refine"], 
            t3["btn_improve_subject"],
            t3["btn_generate_dialogues"],
            t3["btn_generate_auto_timeline"],
            t3["btn_generate_video_prompt"], 
            barra_sup_row, 
            tabs_container 
        ],
        js=js_helpers.JS_AGGIORNA_TABS_LAVORO
    )

    # REGISTRAZIONE DEGLI EVENTI
    eventi_lingua.collega_lingua(t1, t2, t3, t4, t5, titolo_app, js_traduci_tab_header)
    eventi_analisi.collega_analisi(t1, t2, t3, t5, stato_generazione)
    eventi_rendering.collega_rendering(t1, t2, t3, t5, num_lora_img, stato_generazione)
    eventi_video.collega_video(t1, t2, t3, t5, num_lora_vid, stato_generazione, stato_sessione)
    eventi_batch.collega_batch(t4, t5, num_lora_batch, stato_generazione) 
    eventi_sistema.collega_sistema(t1, t2, t3, t4, t5, barra_sup_row, tabs_container, spia_comfy, testo_hardware, btn_hard_reset)
    eventi_sessione.collega_funzioni_sessione(t1, t2, t3, t4, t5, num_lora_img, num_lora_vid, d)

    demo.load(fn=None, inputs=None, outputs=None, js=js_helpers.genera_script_inizializzazione())

if __name__ == "__main__":
    def bootstrap_sistema():
        log.registra("Checking the available ComfyUI service before startup...")

        hardware.suggerisci_highvram()

        # Start the server independently of an optional first-time VLM download.
        log.registra("Starting ComfyUI in background...")
        comfyui_manager.start_comfyui_background()

        if config.KEEP_MODELS_WARM:
            log.registra(f"Priority startup VLM warmup for {modello_warmup}...")
            try:
                local_vlm.warm_up_vlm(modello_warmup)
                log.registra("VLM warmup completed successfully.")
            except Exception as e:
                log.registra(f"Error during priority VLM warmup: {e}", "WARNING")
            time.sleep(2.0)
        

    threading.Thread(target=bootstrap_sistema, daemon=True).start()

    output_comfy_path = os.path.abspath(os.path.join(config.COMFYUI_DIR, "ComfyUI", "output"))
    
    demo.queue(default_concurrency_limit=10)
    try:
        demo.launch(
            app_kwargs={"routes": manual_routes()},
            theme=style.TEMA,
            css=style.CSS,
            inbrowser=True, 
            allowed_paths=[output_comfy_path, os.path.abspath(config.STUDIO_OUTPUT_DIR), os.path.abspath(tempfile.gettempdir())]
        )
    finally:
        log.registra("Shutting down zPrompt Studio: cleaning up all background processes...")
        comfyui_manager.stop_comfyui()
