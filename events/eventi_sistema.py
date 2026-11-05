# events/eventi_sistema.py

import os
import gradio as gr
from core import config, sessione, log, hardware, lingua
from services import comfyui_manager
from ui.tab_log import compila_dashboard_modelli_html

def collega_sistema(t1, t2, t3, t4, t5, barra_superiore, tabs_container, spia_comfy, testo_hardware, btn_hard_reset):
    def save_vlm_cache(path, lang):
        from core.model_cache import save_cache_dir
        d = lingua.ottieni_dizionario_lingua(lang)
        try:
            if comfyui_manager.generazione_attiva:
                log.registra(d['vlm_cache_busy'])
                return gr.update(), log.ottieni_tutti_i_log(), gr.update()
            resolved = save_cache_dir(path)
            log.registra(d['vlm_cache_saved'])
            return resolved, log.ottieni_tutti_i_log(), compila_dashboard_modelli_html()
        except (OSError, ValueError) as exc:
            log.registra(f'Unable to save LLM cache: {exc}', 'ERROR')
            return gr.update(), log.ottieni_tutti_i_log(), gr.update()

    t5['btn_save_vlm_cache'].click(save_vlm_cache,
        [t5['vlm_cache_path'], t5['selettore_lingua']],
        [t5['vlm_cache_path'], t5['vlm_cache_status'], t5['dashboard_modelli']])
    
    t5["btn_refresh_logs"].click(
        fn=lambda: (log.ottieni_tutti_i_log(), compila_dashboard_modelli_html()),
        inputs=None,
        outputs=[t5["box_log_terminale"], t5["dashboard_modelli"]]
    )
    
    t5["btn_clear_logs"].click(
        fn=log.svuota_log,
        inputs=None,
        outputs=t5["box_log_terminale"]
    )

    t5["tab_el"].select(
        fn=lambda: (log.ottieni_tutti_i_log(), compila_dashboard_modelli_html()),
        inputs=None,
        outputs=[t5["box_log_terminale"], t5["dashboard_modelli"]]
    )

    def click_hard_reset_ui():
        stato_risorse = hardware.hard_reset_sistema()
        msg = "⏹️ Complete reset performed."
        return stato_risorse, gr.update(), msg, msg, msg

    btn_hard_reset.click(
        fn=click_hard_reset_ui, 
        outputs=[
            testo_hardware, 
            t1["output_prompt_img"], 
            t2["status_img"], 
            t3["output_comfy_vid_status"], 
            t4["status_batch"]
        ]
    )
