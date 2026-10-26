from utils.lora_ui import lora_row_classes
from ui.accordion_preferences import persistent_accordion
# ui/tab_batch.py

import os
import gradio as gr
from typing import Dict, Any, List

from ui import style
from core import config, sessione, lingua, log, workflow_registry
from utils import media_utils


def _ottieni_prompt_preset_adattivo_batch(preset_val):
    from utils.prompt_templates import build_vision_prompt
    return build_vision_prompt(preset_val, text_only=False)


def crea_tab_batch(
    d: Dict[str, str],
    s: Dict[str, Any],
    lista_modelli_vlm: List[str],
    LORA_ZIMAGE: List[str]
) -> Dict[str, Any]:
    
    def update_upload_accordion(files):
        s_attiva = sessione.carica_ultima_sessione()
        lang = s_attiva.get("lingua_selezionata", "IT")
        dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))

        if files is not None and len(files) > 0:
            count = len(files)
            
            is_txt = False
            for f in files:
                path_str = ""
                if isinstance(f, dict):
                    path_str = f.get("name") or f.get("path") or ""
                elif hasattr(f, "name"):
                    path_str = f.name
                elif hasattr(f, "path"):
                    path_str = f.path
                else:
                    path_str = str(f)
                
                if path_str.lower().endswith(".txt"):
                    is_txt = True
                    break
                    
            pref = "Files" if is_txt else dl.get("immagini_parola", "Images")
            new_label = f"{dl.get('caricati_parola', 'Uploaded')} {count} {pref}"
            return gr.update(open=False, label=new_label)
        else:
            mode_attuale = s_attiva.get("batch_mode", "Immagini (Vision)")
            is_text_mode = "testo" in str(mode_attuale).lower() or "text" in str(mode_attuale).lower() or "prompt" in str(mode_attuale).lower()
            if is_text_mode:
                label_default = dl.get("carica_prompts_batch_label", "📂 Load Text Files (Prompts)")
            else:
                label_default = dl.get("carica_immagini_batch", "Load Batch Images")
            return gr.update(open=True, label=label_default)

    with gr.Tab(d.get("tab_batch", "Batch Processing"), elem_id="tab-batch") as tab_el:
        with gr.Row(elem_id="row-batch", elem_classes=["studio-workspace"]):
            with gr.Column(scale=1, min_width=340, elem_id="batch-input", elem_classes=["analisi-col-box"]):
                
                batch_mode = gr.Dropdown(
                    choices=[
                        (d.get("batch_mode_vision_label", "Images (Vision)"), "Immagini (Vision)"),
                        (d.get("batch_mode_text_label", "Text Files (Prompts)"), "File di Testo (Prompts)")
                    ],
                    value=s.get("batch_mode", "Immagini (Vision)"),
                    label=d.get("batch_mode_title", "📁 Batch Mode"),
                    allow_custom_value=False
                )

                is_text_mode_boot = "testo" in str(s.get("batch_mode", "Immagini (Vision)")).lower() or "text" in str(s.get("batch_mode", "Immagini (Vision)")).lower()

                with gr.Accordion(d.get("carica_immagini_batch", "Load Batch Images"), open=True, elem_id="accordion_upload_batch") as accordion_upload:
                    input_files = gr.File(
                        file_count="multiple",
                        file_types=["image"],
                        label=None,
                        elem_id="input-file-batch",
                        visible=not is_text_mode_boot
                    )
                    input_text_files = gr.File(
                        file_count="multiple",
                        file_types=[".txt"],
                        label=None,
                        elem_id="input-text-file-batch",
                        visible=is_text_mode_boot
                    )

                input_files.change(fn=update_upload_accordion, inputs=[input_files], outputs=[accordion_upload])
                input_text_files.change(fn=update_upload_accordion, inputs=[input_text_files], outputs=[accordion_upload])

                default_model = s.get("modello_vlm_batch")
                if not default_model or (lista_modelli_vlm and default_model not in lista_modelli_vlm):
                    default_model = lista_modelli_vlm[0] if lista_modelli_vlm else "-"

                # RACCORDO MODELLO E REGISTRY ALL'AVVIO
                modello_attuale_batch = s.get("modello_immagine_attivo_batch", "Z-Image Turbo")
                cfg_batch = workflow_registry.ottieni_config_modello_immagine(modello_attuale_batch)
                prefix_batch = cfg_batch.get("session_prefix", "_zimage")

                scelte_lora_init = workflow_registry.ottieni_lora_disponibili_immagine(modello_attuale_batch)

                lora1_val = workflow_registry.normalizza_lora_per_scelte(s.get(f"lora1_name{prefix_batch}_batch", "-"), scelte_lora_init)
                lora2_val = workflow_registry.normalizza_lora_per_scelte(s.get(f"lora2_name{prefix_batch}_batch", "-"), scelte_lora_init)
                lora3_val = workflow_registry.normalizza_lora_per_scelte(s.get(f"lora3_name{prefix_batch}_batch", "-"), scelte_lora_init)

                lora1_str_init = s.get(f"lora1_str{prefix_batch}_batch", 1.0)
                lora2_str_init = s.get(f"lora2_str{prefix_batch}_batch", 1.0)
                lora3_str_init = s.get(f"lora3_str{prefix_batch}_batch", 1.0)

                with gr.Row():
                    dropdown_image_model_batch = gr.Dropdown(
                        choices=["Z-Image Turbo", "Flux.2 Klein", "Krea-2 Turbo"],
                        value=modello_attuale_batch,
                        label=d.get("modello_immagine_label", "🎨 Image Model"),
                        allow_custom_value=False,
                        scale=1
                    )
                    dropdown_model_batch = gr.Dropdown(
                        choices=lista_modelli_vlm if lista_modelli_vlm else ["-"],
                        value=default_model,
                        label=d.get("modello_vision", "Vision Model"),
                        visible=not is_text_mode_boot,
                        scale=1
                    )

                SUGG_VISION_LIST = config.elenca_suggerimenti(config.SUGGESTION_VISION_DIR)
                choices_sugg = ["-"] + (list(SUGG_VISION_LIST) if SUGG_VISION_LIST else [])

                default_sugg = s.get("suggerimento_vision_selezionato_batch") or "-"
                if choices_sugg and default_sugg not in choices_sugg:
                    default_sugg = "-"

                dropdown_sugg_batch = gr.Dropdown(
                    choices=choices_sugg,
                    value=default_sugg,
                    label=d.get("preset_vision", "Vision Preset"),
                    allow_custom_value=False,
                    info=d.get("preset_vision_info", ""),
                    visible=not is_text_mode_boot
                )

                sys_prompt_batch_value = s.get("sys_prompt_batch", "") or ""
                if not sys_prompt_batch_value.strip():
                    sys_prompt_batch_value = _ottieni_prompt_preset_adattivo_batch(default_sugg)

                sys_prompt_batch = gr.Textbox(
                    value=sys_prompt_batch_value,
                    label=d.get("prompt_sistema", "System Prompt"),
                    lines=5,
                    visible=not is_text_mode_boot
                )

                user_hints_batch = gr.Textbox(
                    value=s.get("user_hints_batch", ""),
                    placeholder=d.get("placeholder_hints", ""),
                    label=d.get("istruzioni_extra", "Extra Instructions"),
                    lines=3,
                    visible=not is_text_mode_boot
                )

                btn_start_batch = gr.Button(d.get("btn_avvia_batch", "Start Batch"), variant="primary", interactive=False)

            with gr.Column(scale=1, min_width=340, elem_id="colonna-destra-batch"):
                
                with gr.Column(elem_classes=["analisi-col-box"]):

                    with gr.Accordion(d.get("stato_galleria", "Gallery Status"), open=True, elem_id="accordion-galleria-batch") as accordion_stato_batch:
                        
                        with gr.Group(elem_classes=["contenitore-galleria-relativo"]):
                            gallery_batch = gr.HTML(
                                value=media_utils.compila_galleria_html(s.get("immagini_generate_batch", [])),
                                elem_id="gallery-batch-html"
                            )
                            hidden_gallery_trigger_batch = gr.Textbox(visible=True, elem_classes=["nascondi-textbox"], elem_id="hidden-gallery-trigger-batch")

                        with gr.Row():
                            btn_refresh_gallery_batch = gr.Button("🔄", variant="secondary", size="sm", scale=1, min_width=40)
                            btn_clear_gallery_batch = gr.Button("🧹", variant="secondary", size="sm", scale=1, min_width=40)


                    status_batch, btn_skip_batch, btn_interrupt_batch = style.crea_barra_stato_unificata(d.get("in_attesa", "Waiting..."), "tasto-stop-batch", "tasto-skip-batch")

                    batch_prompt_corrente = gr.Textbox(
                        label=d.get("prompt_generato_batch_label", "📝 Current Generated Prompt"),
                        placeholder=d.get("batch_prompt_corrente_placeholder", "The prompt will appear here..."),
                        interactive=False,
                        lines=8,
                        max_lines=12
                    )

                with gr.Column(elem_classes=["analisi-col-box"]):
                    
                    impostazioni_box_batch_md = gr.Markdown(d.get("impostazioni_box_titolo", "Advanced Settings"))
                    
                    # 1. DIMENSIONI E COPIE
                    with persistent_accordion('accordion_dim_batch', s, d.get("dimensioni_copie", "Size and Copies"), open=True) as accordion_dim_batch:
                        with gr.Row():
                            img_width = gr.Dropdown(choices=["512", "768", "1024", "1280", "1536", "2048"], value=s.get("img_width_batch", "1024"), label=d.get("larghezza", "Width"), allow_custom_value=True)
                            img_height = gr.Dropdown(choices=["512", "768", "1024", "1280", "1536", "2048"], value=s.get("img_height_batch", "1024"), label=d.get("altezza", "Height"), allow_custom_value=True)
                        with gr.Row():
                            img_copies = gr.Slider(minimum=1, maximum=5, value=s.get("img_copies_batch", 1), step=1, label=d.get("batch_size", "Number of images"), info=d.get("batch_size_info", "How many images to generate with this prompt."))

                    # 2. IMPOSTAZIONI KSAMPLER (Dinamico da Workflow Registry)
                    with persistent_accordion('accordion_ksampler_batch', s, d.get("impostazioni_ksampler", "KSampler Settings"), open=False) as accordion_ksampler_batch:
                        steps_val = s.get(f"steps{prefix_batch}_batch") or cfg_batch["steps"]["default"]
                        sampler_val = s.get(f"sampler{prefix_batch}_batch") or cfg_batch["default_sampler"]
                        scheduler_val = s.get(f"scheduler{prefix_batch}_batch") or cfg_batch["default_scheduler"]

                        steps_min = cfg_batch["steps"]["min"]
                        steps_max = cfg_batch["steps"]["max"]
                        choices_samplers_batch = cfg_batch["samplers"]
                        choices_schedulers_batch = cfg_batch["schedulers"]
                        has_hires_batch = cfg_batch.get("has_hires_fix", False)

                        sampler_val = sampler_val if sampler_val in choices_samplers_batch else cfg_batch["default_sampler"]
                        scheduler_val = scheduler_val if scheduler_val in choices_schedulers_batch else cfg_batch["default_scheduler"]

                        with gr.Row():
                            sampler_dropdown = gr.Dropdown(choices=choices_samplers_batch, value=sampler_val, label=d.get("sampler_label", "Sampler"), allow_custom_value=True)
                            scheduler_dropdown = gr.Dropdown(choices=choices_schedulers_batch, value=scheduler_val, label=d.get("scheduler_label", "Scheduler"), allow_custom_value=True)
                        
                        with gr.Row():
                            steps_slider = gr.Slider(minimum=steps_min, maximum=steps_max, value=steps_val, step=1, label=d.get("steps_label", "Steps"), scale=1)
                            hires_scale_slider = gr.Slider(minimum=1.0, maximum=3.0, value=s.get("hires_scale_batch") or 1.5, step=0.05, label=d.get("hires_scale_label", "Upscale Factor"), scale=1, visible=False)
                            
                        with gr.Row():
                            hires_steps_slider = gr.Slider(minimum=5, maximum=15, value=s.get("hires_steps_batch") or 13, step=1, label="Hi-Res Steps", scale=1, visible=has_hires_batch)
                            hires_denoise_slider = gr.Slider(minimum=0.0, maximum=1.0, value=s.get("hires_denoise_batch") or 0.3, step=0.01, label="Denoise", scale=1, visible=has_hires_batch)

                    # 3. GESTIONE LORA (Dinamico da Workflow Registry)
                    with persistent_accordion('accordion_lora_batch', s, d.get("gestione_lora", "LoRA Management"), open=False) as accordion_lora_batch:
                        with gr.Column(min_width=0, elem_classes=["studio-lora-stack"]):
                            label_forza = d.get("forza_lora", "Strength")
                            with gr.Row(elem_classes=["studio-lora-row"]) as row_lora_batch1:
                                lora1_name = gr.Dropdown(choices=scelte_lora_init, value=lora1_val, label="LoRA 1", allow_custom_value=True)
                                lora1_str = gr.Slider(minimum=0.0, maximum=1.5, value=lora1_str_init, step=0.05, label=f"{label_forza} 1")
                            with gr.Row(elem_classes=lora_row_classes(s.get("lora_batch_visibili_count", 1) >= 2)) as row_lora_batch2:
                                lora2_name = gr.Dropdown(choices=scelte_lora_init, value=lora2_val, label="LoRA 2", allow_custom_value=True)
                                lora2_str = gr.Slider(minimum=0.0, maximum=1.5, value=lora2_str_init, step=0.05, label=f"{label_forza} 2")
                            with gr.Row(elem_classes=lora_row_classes(s.get("lora_batch_visibili_count", 1) == 3)) as row_lora_batch3:
                                lora3_name = gr.Dropdown(choices=scelte_lora_init, value=lora3_val, label="LoRA 3", allow_custom_value=True)
                                lora3_str = gr.Slider(minimum=0.0, maximum=1.5, value=lora3_str_init, step=0.05, label=f"{label_forza} 3")
                            with gr.Row(elem_classes=["studio-lora-actions"]):
                                btn_add_lora_batch = gr.Button(d.get("btn_add_lora", "Add LoRA"), size="sm", variant="secondary", visible=True)
                                btn_rem_lora_batch = gr.Button(d.get("btn_rem_lora", "Remove LoRA"), size="sm", variant="secondary", visible=True)

    return {
        "tab_el": tab_el,
        "batch_mode": batch_mode,
        "input_files": input_files,
        "input_text_files": input_text_files,
        "dropdown_image_model_batch": dropdown_image_model_batch,
        "dropdown_model_batch": dropdown_model_batch,
        "dropdown_sugg_batch": dropdown_sugg_batch,
        "sys_prompt_batch": sys_prompt_batch,
        "user_hints_batch": user_hints_batch,
        "accordion_lora_batch": accordion_lora_batch,
        "btn_add_lora_batch": btn_add_lora_batch,
        "btn_rem_lora_batch": btn_rem_lora_batch,
        "row_lora_batch1": row_lora_batch1,
        "row_lora_batch2": row_lora_batch2,
        "row_lora_batch3": row_lora_batch3,
        "lora1_name": lora1_name, "lora1_str": lora1_str,
        "lora2_name": lora2_name, "lora2_str": lora2_str,
        "lora3_name": lora3_name, "lora3_str": lora3_str,
        "img_width": img_width, "img_height": img_height, "img_copies": img_copies,
        "steps_slider": steps_slider,
        "sampler_dropdown": sampler_dropdown,
        "scheduler_dropdown": scheduler_dropdown,
        "hires_steps_slider": hires_steps_slider,
        "hires_denoise_slider": hires_denoise_slider,
        "hires_scale_slider": hires_scale_slider,
        "accordion_dim_batch": accordion_dim_batch,
        "btn_start_batch": btn_start_batch,
        "accordion_stato_batch": accordion_stato_batch,
        "gallery_batch": gallery_batch,
        "status_batch": status_batch,
        "btn_skip_batch": btn_skip_batch,
        "btn_interrupt_batch": btn_interrupt_batch,
        "batch_prompt_corrente": batch_prompt_corrente,
        "accordion_ksampler_batch": accordion_ksampler_batch,
        "accordion_upload": accordion_upload,
        "hidden_gallery_trigger_batch": hidden_gallery_trigger_batch,
        "btn_refresh_gallery_batch": btn_refresh_gallery_batch,
        "btn_clear_gallery_batch": btn_clear_gallery_batch
    }
