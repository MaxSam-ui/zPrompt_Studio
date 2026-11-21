from events.lora_controls import bind_lora_controls
# events/eventi_batch.py

import os
import gradio as gr
from core import config, sessione, lingua
from services import comfyui_manager
from events.rendering_ui_sync import gestisci_cambio_modello_immagine_batch
from events.rendering_logic import gestisci_rimozione_lora_batch, gestisci_aggiunta_lora_batch
from events.rendering_gallery_sync import (
    gestisci_trigger_galleria_batch_html, 
    svuota_vista_galleria_batch,
    ricarica_vista_galleria_batch
)
from ui.tab_batch import _ottieni_prompt_preset_adattivo_batch

def avvia_blocco_generazione_batch():
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    comfyui_manager.batch_attivo = True
    
    s_reale = sessione.carica_ultima_sessione()
    lang = s_reale.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    msg_init = dl.get("init_batch", "⏳ Initializing batch...")
    
    return (
        gr.update(interactive=False), 
        gr.update(interactive=False), 
        gr.update(interactive=False), 
        msg_init,
        gr.update(elem_classes=["elaborazione-attiva"])
    )

def gestisci_suggerimento_batch(scelta):
    sessione.salva_sessione({"suggerimento_vision_selezionato_batch": scelta})
    nuovo_prompt = _ottieni_prompt_preset_adattivo_batch(scelta)
    sessione.salva_sessione({"sys_prompt_batch": nuovo_prompt})
    return nuovo_prompt

def gestisci_cambio_modalita_batch(scelta):
    sessione.salva_sessione({"batch_mode": scelta})
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    scelta_str = str(scelta).lower()
    is_text_mode = "testo" in scelta_str or "text" in scelta_str or "prompt" in scelta_str
    
    if is_text_mode:
        label_acc = dl.get("carica_prompts_batch_label", "📂 Load Text Files (Prompts)")
        return (
            gr.update(visible=False), 
            gr.update(visible=True),  
            gr.update(visible=False), 
            gr.update(visible=False), 
            gr.update(visible=False), 
            gr.update(visible=False), 
            gr.update(label=label_acc, open=True) 
        )
    else:
        label_acc = dl.get("carica_immagini_batch", "Load Batch Images")
        return (
            gr.update(visible=True),  
            gr.update(visible=False), 
            gr.update(visible=True),  
            gr.update(visible=True),  
            gr.update(visible=True),  
            gr.update(visible=True),  
            gr.update(label=label_acc, open=True) 
        )

def gestisci_interruzione_batch_sicura():
    comfyui_manager.batch_attivo = False
    comfyui_manager.generazione_attiva = False
    return comfyui_manager.interrompi_comfyui()


def gestisci_skip_batch_sicura():
    return comfyui_manager.salta_generazione_corrente()


def gestisci_generazione_batch_con_monitor(*args):
    from generators.batch import genera_batch_con_monitor
    try:
        yield from genera_batch_con_monitor(*args)
    finally:
        comfyui_manager.batch_attivo = False
        comfyui_manager.generazione_attiva = False


def stato_finale_batch(status):
    success = str(status).strip().startswith(("✅", "📸")) and not comfyui_manager.vlm_interrotto
    return gr.update(elem_classes=["completato-successo"] if success else [])


def collega_batch(t4, t5, num_lora_batch, stato_generazione):
    
    t4["dropdown_sugg_batch"].change(
        fn=gestisci_suggerimento_batch,
        inputs=[t4["dropdown_sugg_batch"]],
        outputs=[t4["sys_prompt_batch"]]
    )

    t4["batch_mode"].change(
        fn=gestisci_cambio_modalita_batch,
        inputs=[t4["batch_mode"]],
        outputs=[
            t4["input_files"],
            t4["input_text_files"],
            t4["dropdown_model_batch"],
            t4["dropdown_sugg_batch"],
            t4["sys_prompt_batch"],
            t4["user_hints_batch"],
            t4["accordion_upload"]
        ]
    )

    bind_lora_controls(
        t4["btn_add_lora_batch"], t4["btn_rem_lora_batch"], num_lora_batch,
        [t4["row_lora_batch2"], t4["row_lora_batch3"]],
        [t4["lora2_name"], t4["lora2_str"], t4["lora3_name"], t4["lora3_str"]],
        gestisci_aggiunta_lora_batch, gestisci_rimozione_lora_batch, "lora-controls-batch"
    )

    t4["dropdown_image_model_batch"].change(
        fn=gestisci_cambio_modello_immagine_batch,
        inputs=[t4["dropdown_image_model_batch"]],
        outputs=[
            t4["steps_slider"],
            t4["sampler_dropdown"],
            t4["scheduler_dropdown"],
            t4["btn_add_lora_batch"],
            t4["btn_rem_lora_batch"],
            t4["row_lora_batch2"],
            t4["row_lora_batch3"],
            t4["hires_scale_slider"],
            t4["hires_steps_slider"],
            t4["hires_denoise_slider"],
            t4["lora1_name"],
            t4["lora1_str"],
            t4["lora2_name"],
            t4["lora2_str"],
            t4["lora3_name"],
            t4["lora3_str"]
        ]
    )

    t4["hidden_gallery_trigger_batch"].change(
        fn=gestisci_trigger_galleria_batch_html,
        inputs=[t4["hidden_gallery_trigger_batch"], stato_generazione],
        outputs=[
            stato_generazione,
            t4["gallery_batch"],
            t4["status_batch"],
            t4["batch_prompt_corrente"],
            t4["accordion_stato_batch"]
        ],
        show_progress="hidden",
        trigger_mode="multiple",
        concurrency_id="gallery-selection",
        concurrency_limit=1
    )

    t4["btn_refresh_gallery_batch"].click(
        fn=ricarica_vista_galleria_batch,
        inputs=[stato_generazione],
        outputs=[
            stato_generazione,
            t4["gallery_batch"],
            t4["status_batch"],
            t4["batch_prompt_corrente"],
            t4["accordion_stato_batch"]
        ]
    )

    t4["btn_clear_gallery_batch"].click(
        fn=svuota_vista_galleria_batch,
        inputs=[stato_generazione],
        outputs=[
            stato_generazione,
            t4["gallery_batch"],
            t4["status_batch"],
            t4["batch_prompt_corrente"],
            t4["accordion_stato_batch"]
        ]
    )

    t4["btn_skip_batch"].click(
        fn=gestisci_skip_batch_sicura,
        inputs=None,
        outputs=[t4["status_batch"]]
    )

    t4["btn_interrupt_batch"].click(
        fn=gestisci_interruzione_batch_sicura,
        inputs=None,
        outputs=[t4["status_batch"]]
    ).then(
        fn=lambda: (
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(elem_classes=["analisi-col-box"])
        ),
        inputs=None,
        outputs=[
            t4["btn_start_batch"],
            t4["input_files"],
            t4["input_text_files"],
            t4["accordion_stato_batch"]
        ]
    )

    t4["btn_start_batch"].click(
        fn=avvia_blocco_generazione_batch,  
        inputs=None, 
        outputs=[t4["btn_start_batch"], t4["input_files"], t4["input_text_files"], t4["status_batch"], t4["accordion_stato_batch"]]
    ).then(
        fn=gestisci_generazione_batch_con_monitor,
        inputs=[
            t4["input_files"], t4["dropdown_model_batch"], t4["sys_prompt_batch"], t4["user_hints_batch"],
            num_lora_batch,
            t4["lora1_name"], t4["lora1_str"],
            t4["lora2_name"], t4["lora2_str"],
            t4["lora3_name"], t4["lora3_str"],
            t4["img_width"], t4["img_height"], t4["img_copies"],
            t4["steps_slider"], t4["sampler_dropdown"], t4["scheduler_dropdown"],
            t4["hires_steps_slider"], t4["hires_denoise_slider"], t4["hires_scale_slider"],
            stato_generazione,
            t4["dropdown_image_model_batch"],
            t4["batch_mode"],            
            t4["input_text_files"]
        ],
        outputs=[t4["status_batch"], t4["gallery_batch"], t5["box_log_terminale"], stato_generazione, t4["accordion_stato_batch"], t4["batch_prompt_corrente"]]
    ).then(
        fn=stato_finale_batch,
        inputs=[t4["status_batch"]],
        outputs=[t4["accordion_stato_batch"]]
    ).then(
        fn=lambda: (gr.update(interactive=True), gr.update(interactive=True), gr.update(interactive=True)),
        inputs=None, outputs=[t4["btn_start_batch"], t4["input_files"], t4["input_text_files"]]
    )

    def reset_bordo_batch_default():
        return gr.update(elem_classes=[])

    t4["input_files"].change(fn=reset_bordo_batch_default, inputs=None, outputs=[t4["accordion_stato_batch"]])
    t4["input_text_files"].change(fn=reset_bordo_batch_default, inputs=None, outputs=[t4["accordion_stato_batch"]])
    t4["batch_mode"].change(fn=reset_bordo_batch_default, inputs=None, outputs=[t4["accordion_stato_batch"]])
