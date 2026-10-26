from utils.lora_ui import lora_row_classes
from ui.accordion_preferences import persistent_accordion
# ui/rendering_settings_ui.py

import gradio as gr
from typing import Dict, Any, List
from core import workflow_registry

def crea_sezione_impostazioni_avanzate(
    d: Dict[str, str],
    s: Dict[str, Any],
    modello_attuale: str,
    is_edit_iniziale: bool,
    scelte_lora_init: List[str],
    lora1_val: str, lora1_str_init: float,
    lora2_val: str, lora2_str_init: float,
    lora3_val: str, lora3_str_init: float,
    is_fixed_startup: bool
) -> Dict[str, Any]:
    """Crea la colonna delle Impostazioni Avanzate (Dimensioni, KSampler, LoRA)."""

    with gr.Column(elem_classes=["analisi-col-box"]) as colonna_impostazioni_avanzate:
        impostazioni_box_md = gr.Markdown(d["impostazioni_box_titolo"])
        
        with persistent_accordion('accordion_dim_img', s, d["dimensioni_copie"], open=True) as accordion_dim_img:
            with gr.Group(visible=(s.get("generation_mode") != "Modifica Immagine (Edit)")) as row_dim_generiche:
                with gr.Row():
                    img_width = gr.Dropdown(choices=["512", "768", "1024", "1280", "1536", "2048"], value=s.get("img_width", "1024"), label=d["larghezza"], allow_custom_value=True, scale=1)
                    img_height = gr.Dropdown(choices=["512", "768", "1024", "1280", "1536", "2048"], value=s.get("img_height", "1024"), label=d["altezza"], allow_custom_value=True, scale=1)
                with gr.Row():
                    img_copies = gr.Slider(minimum=1, maximum=10, value=s.get("img_copies", 1), step=1, label=d["batch_size"], info=d["batch_size_info"], scale=1)

            with gr.Row(visible=(s.get("generation_mode") == "Modifica Immagine (Edit)" and modello_attuale != "Qwen Image 2.1")) as row_dim_edit:
                krea2_edit_height = gr.Dropdown(
                    choices=["512", "768", "1024", "1280", "1536"], 
                    value=s.get("krea2_edit_height", "1280"), 
                    label=d.get("processing_height_label", "Altezza di Elaborazione (Edit)"), 
                    allow_custom_value=True
                )

        with persistent_accordion('accordion_ksampler', s, f"{d.get('impostazioni_ksampler', 'Impostazioni KSampler')} (fixed-seed)" if is_fixed_startup else f"{d.get('impostazioni_ksampler', 'Impostazioni KSampler')} (random)", open=False) as accordion_ksampler:
            cfg = workflow_registry.ottieni_config_modello_immagine(modello_attuale)
            
            if is_edit_iniziale:
                cfg = workflow_registry.ottieni_config_modifica_immagine(modello_attuale)
                edit_prefix = "qwen21_edit" if modello_attuale == "Qwen Image 2.1" else "krea2_edit"
                steps_val = s.get(f"steps_{edit_prefix}") or cfg["steps"]["default"]
                steps_val = max(cfg["steps"]["min"], min(cfg["steps"]["max"], steps_val))
                sampler_val = s.get(f"sampler_{edit_prefix}") or cfg["default_sampler"]
                scheduler_val = s.get(f"scheduler_{edit_prefix}") or cfg["default_scheduler"]
                steps_min, steps_max = cfg["steps"]["min"], cfg["steps"]["max"]
                choices_samplers = cfg["samplers"]
                choices_schedulers = cfg["schedulers"]
            else:
                prefix = cfg["session_prefix"]
                steps_val = s.get(f"steps{prefix}") or s.get("steps", cfg["steps"]["default"])
                sampler_val = s.get(f"sampler{prefix}") or s.get("sampler_name", cfg["default_sampler"])
                scheduler_val = s.get(f"scheduler{prefix}") or s.get("scheduler", cfg["default_scheduler"])
                steps_min, steps_max = cfg["steps"]["min"], cfg["steps"]["max"]
                choices_samplers = cfg["samplers"]
                choices_schedulers = cfg["schedulers"]

            # Validazione di coerenza all'avvio
            if sampler_val not in choices_samplers:
                sampler_val = cfg["default_sampler"]
            if scheduler_val not in choices_schedulers:
                scheduler_val = cfg["default_scheduler"]

            is_flux = modello_attuale == "Flux.2 Klein"
            is_krea2 = modello_attuale == "Krea-2 Turbo"

            with gr.Row():
                sampler_dropdown = gr.Dropdown(choices=choices_samplers, value=sampler_val, label=d.get("sampler_label", "Sampler"), allow_custom_value=True)
                scheduler_dropdown = gr.Dropdown(choices=choices_schedulers, value=scheduler_val, label=d.get("scheduler_label", "Scheduler"), allow_custom_value=True)
            
            with gr.Row():
                steps_slider = gr.Slider(minimum=steps_min, maximum=steps_max, value=steps_val, step=1, label=d["steps_label"], scale=1)
                hires_steps_slider = gr.Slider(minimum=5, maximum=15, value=s.get("hires_steps") or 13, step=1, label="Hi-Res Steps", scale=1, visible=not (is_flux or is_krea2 or is_edit_iniziale))
                hires_denoise_slider = gr.Slider(minimum=0.0, maximum=1.0, value=s.get("hires_denoise") or 0.3, step=0.01, label="Denoise", scale=1, visible=not (is_flux or is_krea2 or is_edit_iniziale))
                hires_scale_val = s.get("hires_scale") if s.get("hires_scale") is not None else 1.5
                hires_scale_slider = gr.Slider(minimum=1.0, maximum=3.0, value=hires_scale_val, step=0.05, label=d.get("hires_scale_label", "Scala Upscale (Hi-Res)"), scale=1, visible=False)
                
            with gr.Row():
                img_seed_mode = gr.Dropdown(choices=["randomize", "fixed"], value=s.get("img_seed_mode", "randomize"), label=d.get("seed_mode_label", "Modalità Seed"), allow_custom_value=False)
                img_seed = gr.Textbox(value=s.get("img_seed", ""), placeholder=d.get("seed_placeholder", "Lascia vuoto per random..."), label=d.get("image_seed_label", "Seed Immagine"))

        with persistent_accordion('accordion_lora_img', s, d["gestione_lora"], open=False) as accordion_lora_img:
            label_forza = d.get("forza_lora", "Forza")
            
            with gr.Column(visible=(s.get("generation_mode") != "Modifica Immagine (Edit)" or modello_attuale == "Qwen Image 2.1"), min_width=0, elem_classes=["studio-lora-stack"]) as group_lora_standard:
                with gr.Row(elem_classes=["studio-lora-row"]) as row_lora_img1:
                    lora1_name = gr.Dropdown(choices=scelte_lora_init, value=lora1_val, label="LoRA 1", allow_custom_value=True)
                    lora1_str = gr.Slider(minimum=0.0, maximum=1.5, value=lora1_str_init, step=0.05, label=f"{label_forza} 1")
                with gr.Row(elem_classes=lora_row_classes(s.get("lora_visibili_count", 1) >= 2)) as row_lora_img2:
                    lora2_name = gr.Dropdown(choices=scelte_lora_init, value=lora2_val, label="LoRA 2", allow_custom_value=True)
                    lora2_str = gr.Slider(minimum=0.0, maximum=1.5, value=lora2_str_init, step=0.05, label=f"{label_forza} 2")
                with gr.Row(elem_classes=lora_row_classes(s.get("lora_visibili_count", 1) == 3)) as row_lora_img3:
                    lora3_name = gr.Dropdown(choices=scelte_lora_init, value=lora3_val, label="LoRA 3", allow_custom_value=True)
                    lora3_str = gr.Slider(minimum=0.0, maximum=1.5, value=lora3_str_init, step=0.05, label=f"{label_forza} 3")
                
                with gr.Row(elem_classes=["studio-lora-actions"]):
                    btn_add_lora_img = gr.Button(d["btn_add_lora"], size="sm", variant="secondary", scale=1, visible=True)
                    btn_rem_lora_img = gr.Button(d["btn_rem_lora"], size="sm", variant="secondary", scale=1, visible=True)
                        
            with gr.Group(visible=(s.get("generation_mode") == "Modifica Immagine (Edit)" and modello_attuale != "Qwen Image 2.1")) as group_lora_edit:
                krea2_edit_lora_strength = gr.Slider(
                    minimum=0.0, maximum=1.5, 
                    value=s.get("krea2_edit_lora_strength", 0.75), 
                    step=0.05, 
                    label=d.get("identity_preservation_label", "Forza Conservazione Identità (LoRA)")
                )

    return {
        "colonna_impostazioni_avanzate": colonna_impostazioni_avanzate,
        "impostazioni_box_titolo": impostazioni_box_md,
        "accordion_dim_img": accordion_dim_img, "row_dim_generiche": row_dim_generiche, "row_dim_edit": row_dim_edit,
        "img_width": img_width, "img_height": img_height, "krea2_edit_height": krea2_edit_height, "img_copies": img_copies,
        "accordion_ksampler": accordion_ksampler, "sampler_dropdown": sampler_dropdown, "scheduler_dropdown": scheduler_dropdown,
        "steps_slider": steps_slider, "hires_steps_slider": hires_steps_slider, "hires_denoise_slider": hires_denoise_slider, "hires_scale_slider": hires_scale_slider,
        "img_seed_mode": img_seed_mode, "img_seed": img_seed,
        "accordion_lora_img": accordion_lora_img, "group_lora_standard": group_lora_standard, "group_lora_edit": group_lora_edit,
        "row_lora_img1": row_lora_img1, "row_lora_img2": row_lora_img2, "row_lora_img3": row_lora_img3,
        "lora1_name": lora1_name, "lora1_str": lora1_str, "lora2_name": lora2_name, "lora2_str": lora2_str, "lora3_name": lora3_name, "lora3_str": lora3_str,
        "btn_add_lora_img": btn_add_lora_img, "btn_rem_lora_img": btn_rem_lora_img, "krea2_edit_lora_strength": krea2_edit_lora_strength
    }
