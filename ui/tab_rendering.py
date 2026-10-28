# ui/tab_rendering.py

import os
import gradio as gr
from typing import Dict, Any, List

from ui import style, rendering_catalog_ui, rendering_settings_ui
from services import prompt_manager
from utils import media_utils
from core import config, sessione, workflow_registry, lingua


def crea_tab_rendering(
    d: Dict[str, str],
    s: Dict[str, Any],
    LORA_ZIMAGE: List[str] = None,
) -> Dict[str, Any]:
    with gr.Tab(d["tab_render"]) as tab_el:
        with gr.Row(elem_id="row-rendering"):
            
            # =========================================================================
            # COLONNA DI SINISTRA: SELETTORI, CATALOGO, PROMPT E MODIFICA
            # =========================================================================
            with gr.Column(scale=1, min_width=340, elem_id="rendering-editor", elem_classes=["analisi-col-box"]) as colonna_sinistra_rendering:
                
                is_fixed_startup = s.get("img_seed_mode", "randomize") == "fixed"
                btn_genera_testo = d.get("btn_genera_img", "Genera Immagine")
                btn_genera_story_testo = d.get("btn_genera_griglia_storyboard", "🎨 Genera Griglia Storyboard")
                btn_genera_seq_testo = "📸 Genera Sequenza AI"
                btn_genera_edit_testo = d.get("btn_genera_edit", "🎨 Applica Modifica (Edit)")

                mode_iniziale = s.get("generation_mode", "Classica (1 Immagine)")
                is_edit_iniziale = (mode_iniziale == "Modifica Immagine (Edit)")

                modello_attuale = s.get("modello_immagine_attivo", "Z-Image Turbo")
                if is_edit_iniziale and modello_attuale not in ("Krea-2 Turbo", "Qwen Image 2.1"):
                    modello_attuale = "Krea-2 Turbo"
                elif not is_edit_iniziale and modello_attuale == "Qwen Image 2.1":
                    modello_attuale = "Z-Image Turbo"

                scelte_lora_init = workflow_registry.ottieni_lora_disponibili_immagine(modello_attuale)

                if modello_attuale == "Qwen Image 2.1":
                    lora1_key, lora2_key, lora3_key = "lora1_name_qwen21_edit", "lora2_name_qwen21_edit", "lora3_name_qwen21_edit"
                    lora1_str_init = s.get("lora1_str_qwen21_edit", 1.0)
                    lora2_str_init = s.get("lora2_str_qwen21_edit", 1.0)
                    lora3_str_init = s.get("lora3_str_qwen21_edit", 1.0)
                elif modello_attuale == "Flux.2 Klein":
                    lora1_key, lora2_key, lora3_key = "lora1_name_flux2", "lora2_name_flux2", "lora3_name_flux2"
                    lora1_str_init = s.get("lora1_str_flux2") if s.get("lora1_str_flux2") is not None else s.get("lora1_str", 1.0)
                    lora2_str_init = s.get("lora2_str_flux2") if s.get("lora2_str_flux2") is not None else s.get("lora2_str", 1.0)
                    lora3_str_init = s.get("lora3_str_flux2") if s.get("lora3_str_flux2") is not None else s.get("lora3_str", 1.0)
                elif modello_attuale == "Krea-2 Turbo":
                    lora1_key, lora2_key, lora3_key = "lora1_name_krea2", "lora2_name_krea2", "lora3_name_krea2"
                    lora1_str_init = s.get("lora1_str_krea2") if s.get("lora1_str_krea2") is not None else s.get("lora1_str", 1.0)
                    lora2_str_init = s.get("lora2_str_krea2") if s.get("lora2_str_krea2") is not None else s.get("lora2_str", 1.0)
                    lora3_str_init = s.get("lora3_str_krea2") if s.get("lora3_str_krea2") is not None else s.get("lora3_str", 1.0)
                else:
                    lora1_key, lora2_key, lora3_key = "lora1_name_zimage", "lora2_name_zimage", "lora3_name_zimage"
                    lora1_str_init = s.get("lora1_str_zimage") if s.get("lora1_str_zimage") is not None else s.get("lora1_str", 1.0)
                    lora2_str_init = s.get("lora2_str_zimage") if s.get("lora2_str_zimage") is not None else s.get("lora2_str", 1.0)
                    lora3_str_init = s.get("lora3_str_zimage") if s.get("lora3_str_zimage") is not None else s.get("lora3_str", 1.0)

                lora1_raw = s.get(lora1_key) or s.get("lora1_name", "-")
                lora2_raw = s.get(lora2_key) or s.get("lora2_name", "-")
                lora3_raw = s.get(lora3_key) or s.get("lora3_name", "-")

                lora1_val = workflow_registry.normalizza_lora_per_scelte(lora1_raw, scelte_lora_init)
                lora2_val = workflow_registry.normalizza_lora_per_scelte(lora2_raw, scelte_lora_init)
                lora3_val = workflow_registry.normalizza_lora_per_scelte(lora3_raw, scelte_lora_init)

                with gr.Row():
                    choices_modelli = ["Krea-2 Turbo", "Qwen Image 2.1"] if is_edit_iniziale else ["Z-Image Turbo", "Flux.2 Klein", "Krea-2 Turbo"]
                    dropdown_image_model = gr.Dropdown(
                        choices=choices_modelli, value=modello_attuale,
                        label=d.get("modello_immagine_label", "🎨 Modello Immagine"),
                        allow_custom_value=False, scale=1
                    )
                    
                    generation_mode = gr.Dropdown(
                        choices=lingua.generation_mode_choices(d),
                        value=s.get("generation_mode", "Classica (1 Immagine)"),
                        label=d.get("modalita_generazione_label", "🎬 Modalità Generazione"),
                        allow_custom_value=False, scale=1
                    )

                s_seq_list = config.elenca_suggerimenti(config.SUGGESTION_SEQUENCE_DIR)
                choices_sequence = ["-"] + (list(s_seq_list) if s_seq_list else [])

                with gr.Row(visible=("sequenza" in mode_iniziale.lower() or "storyboard" in mode_iniziale.lower())) as row_sequenza_scatti:
                    dropdown_sugg_sequenza = gr.Dropdown(
                        choices=choices_sequence, value=s.get("suggerimento_sequenza_selezionato", "-"), 
                        label=d["presets_sequence_label"], allow_custom_value=False, scale=3
                    )
                    selettore_sequenza_scatti = gr.Slider(
                        minimum=2, maximum=5, step=1,
                        value=int(s.get("sequenza_num_scatti", 5)),
                        label=d["sequence_count_label"], scale=2, visible="sequenza" in mode_iniziale.lower()
                    )

                prompt_render_header = gr.Markdown(
                    "📖 Idea Scena e Prompt Sequenza AI" if "sequenza" in mode_iniziale.lower() else d.get("prompt_render_label", "✍️ Prompt da Inviare a ComfyUI"),
                    visible=(s.get("generation_mode") != "Modifica Immagine (Edit)")
                )

                prompts_salvati = ["-"] + (prompt_manager.elenca_prompt_salvati_img() if prompt_manager.elenca_prompt_salvati_img() else [])
                dropdown_saved_prompts = gr.Dropdown(
                    choices=prompts_salvati, value="-",
                    label=d.get("carica_prompt_salvato_label", "Carica Prompt Salvato"),
                    allow_custom_value=False, visible=(s.get("generation_mode") != "Modifica Immagine (Edit)")
                )
                
                prompt_to_send_img = gr.Textbox(
                    value=s.get("prompt_to_send_img", "") or "", lines=8, max_lines=18,
                    show_label=False, elem_id="rendering-prompt", elem_classes=["scrollable-textbox"],
                    visible=(s.get("generation_mode") != "Modifica Immagine (Edit)")
                )

                cat_dict = rendering_catalog_ui.crea_sezione_catalogo(
                    d, s, mode_iniziale, prompt_to_send_img, selettore_sequenza_scatti
                )

                btn_send_label = btn_genera_edit_testo if is_edit_iniziale else btn_genera_seq_testo if "sequenza" in mode_iniziale.lower() else btn_genera_story_testo if mode_iniziale == "Storyboard" else btn_genera_testo
                is_edit_mode = s.get("generation_mode") == "Modifica Immagine (Edit)"
                
                raffina_titolo_md = gr.Markdown(d.get("edit_title", "🪄 Modifica Immagine con AI") if is_edit_mode else d.get("raffina_titolo", "🪄 Affina Descrizione con AI"))
                refine_instructions = gr.Textbox(
                    value=s.get("krea2_edit_instruction" if is_edit_mode else "refine_instructions", "") or "",
                    label=d.get("edit_instructions_label", "Cosa vuoi fare o cambiare nell'immagine?") if is_edit_mode else d.get("raffina_istruzioni_label", "Istruzioni di Affinamento"),
                    placeholder=d.get("edit_placeholder", "Es: Rendi la donna bionda...") if is_edit_mode else d.get("raffina_placeholder", "Es: Cambia l'ora del giorno..."),
                    lines=3,
                )
                
                krea2_edit_grounding_px = gr.Slider(
                    minimum=256, maximum=1024, step=64,
                    value=int(s.get("krea2_edit_grounding_px", 768)),
                    label=d.get("grounding_resolution_label", "🎯 Risoluzione Grounding (Edit)"),
                    info=d.get("grounding_resolution_info", "Definisce l'area di precisione per la modifica dell'immagine di origine."),
                    visible=is_edit_mode and modello_attuale != "Qwen Image 2.1", scale=1
                )

                with gr.Row(elem_id="rendering-actions"):
                    btn_refine = gr.Button(
                        d.get("btn_optimize_instruction", "🪄 Ottimizza Istruzione AI") if is_edit_mode else "📖 Compila Sequenza AI" if "sequenza" in mode_iniziale.lower() else d.get("btn_raffina", "🪄 Affina Descrizione"),
                        variant="secondary"
                    )
                    btn_send_comfy_img = gr.Button(btn_send_label, variant="primary", interactive=False, elem_id="rendering-generate")

            # =========================================================================
            # COLONNA DI DESTRA: GALLERIA, STORYBOARD E IMPOSTAZIONI AVANZATE
            # =========================================================================
            with gr.Column(scale=1, min_width=340, elem_id="colonna-destra-rendering"):
                
                with gr.Column(elem_classes=["analisi-col-box"]) as colonna_destra_rendering_box1:

                    with gr.Accordion(d["stato_galleria"], open=True, elem_id="accordion-galleria-flat") as accordion_stato_gall:
                        with gr.Group(elem_classes=["contenitore-galleria-relativo"]):
                            # HTML components can be remounted during parent updates.
                            # Keep mutually exclusive visibility on layout containers.
                            with gr.Group(visible=(s.get("generation_mode") != "Storyboard"), elem_id="gallery-classic-slot") as gallery_classic_slot:
                                gallery_img = gr.HTML(value=media_utils.compila_galleria_html(s.get("immagini_generate_cumulate", [])), elem_id="gallery-img-html")
                            with gr.Group(visible=(s.get("generation_mode") == "Storyboard"), elem_id="gallery-storyboard-slot") as gallery_storyboard_slot:
                                gallery_storyboard = gr.HTML(value=media_utils.compila_galleria_html(s.get("lista_frame_storyboard_attivi", [])), elem_id="gallery-storyboard-html")
                            hidden_gallery_trigger = gr.Textbox(visible=True, elem_classes=["nascondi-textbox"], elem_id="hidden-gallery-trigger")

                        seed_visualizzato = gr.Textbox(label=d["seed_visualizzato_label"], interactive=False, show_label=True, text_align="center")

                        with gr.Row():
                            btn_save_prompt = gr.Button(d["btn_salva_prompt"], variant="secondary", scale=2, visible=(s.get("generation_mode") != "Modifica Immagine (Edit)"))
                            btn_load_from_image = gr.UploadButton(label=d.get("source_edit_label", "Sorgente Edit") if is_edit_mode else d.get("btn_carica_da_immagine", "Carica da Immagine"), file_types=["image"], type="filepath", variant="secondary", size="sm", scale=2)
                            btn_toggle_seed = gr.Button("🔒" if is_fixed_startup else "🔓", variant="secondary", size="sm", scale=1, min_width=40)
                            btn_clear_gallery = gr.Button("🧹", variant="secondary", size="sm", scale=1, min_width=40)

                    output_comfy_vid_status, btn_skip_img, btn_interrupt_vid = style.crea_barra_stato_unificata(d["in_attesa"], "tasto-stop-img", "tasto-skip-img")

                    s_list = config.elenca_suggerimenti(config.SUGGESTION_STORYBOARD_DIR)
                    choices_story = ["-"] + (list(s_list) if s_list else [])
                    
                    with gr.Group(visible=(s.get("generation_mode") == "Storyboard"), elem_classes=["box-storyboard-ai"]) as box_storyboard:
                        gr.Markdown(d.get("storyboard_ai_titolo", "📖 Storyboard AI"))
                        with gr.Row():
                            dropdown_sugg_storyboard = gr.Dropdown(
                                choices=choices_story, 
                                value=s.get("suggerimento_storyboard_selezionato", "-"), 
                                label=d.get("preset_storyboard_label", "📋 Preset Regia Storyboard"), 
                                allow_custom_value=False, scale=3
                            )
                            selettore_storyboard_pannelli = gr.Slider(minimum=2, maximum=4, step=1, value=int(s.get("storyboard_pannelli", 3)), label=d.get("numero_fotogrammi_label", "Numero di Fotogrammi"), scale=2)
                        with gr.Row():
                            attiva_refine_storyboard = gr.Checkbox(label=d.get("raffina_fotogrammi_label", "Raffina fotogrammi (Refine Img2Img)"), value=s.get("attiva_refine_storyboard", False), scale=1)
                            refine_denoise = gr.Slider(minimum=0.05, maximum=0.95, step=0.05, value=s.get("refine_denoise", 0.35), label=d.get("refine_denoise_label", "Forza Refine (Denoise)"), scale=2)
                        with gr.Row():
                            btn_genera_storyboard_ai = gr.Button(d.get("btn_compila_storyboard_ai", "📖 Compila Storyboard AI"), variant="secondary", scale=1)
                            btn_taglia_storyboard = gr.Button(d.get("btn_taglia_storyboard", "✂️ Taglia Pannelli"), variant="primary", interactive=False, scale=1)
                        

                sett_dict = rendering_settings_ui.crea_sezione_impostazioni_avanzate(
                    d, s, modello_attuale, is_edit_iniziale, scelte_lora_init,
                    lora1_val, lora1_str_init, lora2_val, lora2_str_init, lora3_val, lora3_str_init, is_fixed_startup
                )

        dict_restituito = {
            "tab_el": tab_el, "dropdown_image_model": dropdown_image_model, "prompt_render_header": prompt_render_header,
            "dropdown_saved_prompts": dropdown_saved_prompts, "prompt_to_send_img": prompt_to_send_img,
            "btn_send_comfy_img": btn_send_comfy_img, "status_img": output_comfy_vid_status,
            "btn_skip_img": btn_skip_img, "btn_interrupt_img": btn_interrupt_vid,
            "gallery_img": gallery_img, "gallery_storyboard": gallery_storyboard, "seed_visualizzato": seed_visualizzato,
            "gallery_classic_slot": gallery_classic_slot, "gallery_storyboard_slot": gallery_storyboard_slot,
            "btn_save_prompt": btn_save_prompt, "btn_load_from_image": btn_load_from_image, "btn_clear_gallery": btn_clear_gallery,
            "raffina_titolo_md": raffina_titolo_md, "refine_instructions": refine_instructions, "btn_refine": btn_refine,
            "btn_toggle_seed": btn_toggle_seed, "generation_mode": generation_mode, "box_storyboard": box_storyboard,
            "dropdown_sugg_storyboard": dropdown_sugg_storyboard, "selettore_storyboard_pannelli": selettore_storyboard_pannelli,
            "attiva_refine_storyboard": attiva_refine_storyboard, "refine_denoise": refine_denoise, 
            "btn_genera_storyboard_ai": btn_genera_storyboard_ai, "btn_taglia_storyboard": btn_taglia_storyboard,
            "hidden_gallery_trigger": hidden_gallery_trigger, "accordion_stato_gall": accordion_stato_gall,
            "colonna_sinistra_rendering": colonna_sinistra_rendering, "colonna_destra_rendering_box1": colonna_destra_rendering_box1,
            "krea2_edit_grounding_px": krea2_edit_grounding_px, "row_sequenza_scatti": row_sequenza_scatti,
            "dropdown_sugg_sequenza": dropdown_sugg_sequenza, "selettore_sequenza_scatti": selettore_sequenza_scatti
        }
        
        dict_restituito.update(cat_dict)
        dict_restituito.update(sett_dict)

        return dict_restituito
