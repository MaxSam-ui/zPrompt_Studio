# ui/tab_analisi.py

import os
import gradio as gr
from typing import List, Dict, Any

from core import config, sessione, lingua
from ui import style

def _ottieni_prompt_preset_adattivo(preset_val, solo_attivo, max_tokens=512):
    from utils.prompt_templates import build_vision_prompt
    return build_vision_prompt(preset_val, solo_attivo, max_tokens)


def crea_tab_analisi(
    d: Dict[str, str],
    s: Dict[str, Any],
    lista_modelli_vlm: List[str],
    SUGG_VISION_LIST: List[str],
) -> Dict[str, Any]:
    with gr.Tab(d.get("tab_analisi", "Image Analysis")) as tab_el:
        with gr.Row(equal_height=False, elem_id="row-analisi", elem_classes=["studio-workspace"]):
            
            # =========================================================================
            # COLONNA DI SINISTRA: SELETTORI, PROMPT SISTEMA, ISTRUZIONI EXTRA E TASTO ANALIZZA
            # =========================================================================
            with gr.Column(scale=1, min_width=340, elem_id="analysis-input", elem_classes=["analisi-col-box"]):
                llama_vision_md = gr.Markdown(d.get("llama_vision_titolo", "Vision"), elem_classes=["studio-section-title"])
                
                default_model = s.get("modello_vlm")
                if not default_model or (lista_modelli_vlm and default_model not in lista_modelli_vlm):
                    default_model = lista_modelli_vlm[0] if lista_modelli_vlm else "-"
                
                with gr.Row(equal_height=False):
                    dropdown_model = gr.Dropdown(
                        choices=lista_modelli_vlm if lista_modelli_vlm else ["-"],
                        value=default_model,
                        label=d.get("modello_vision", "Vision Model"),
                        allow_custom_value=True,
                        info=d.get("modello_vision_info", ""),
                        scale=3,
                        min_width=250
                    )
                    
                    vlm_max_tokens = gr.Slider(
                        minimum=256,
                        maximum=896,
                        step=64,
                        value=int(s.get("vlm_max_tokens", 512)),
                        label=d.get("vlm_max_tokens_label", "Max Prompt Tokens"),
                        scale=2,
                        min_width=150
                    )
                
                with gr.Row(equal_height=False):
                    choices_sugg = ["-"] + (list(SUGG_VISION_LIST) if SUGG_VISION_LIST else [])
                    default_sugg = s.get("suggerimento_vision_selezionato")
                    solo_attivo = s.get("solo_testo_attivo", False)
                    
                    if not default_sugg or (choices_sugg and default_sugg not in choices_sugg):
                        default_sugg = "-"
                    
                    dropdown_sugg_vision = gr.Dropdown(
                        choices=choices_sugg,
                        value=default_sugg,
                        label=d.get("preset_vision", "Vision Preset"),
                        allow_custom_value=False,
                        info=d.get("preset_vision_info", ""),
                        scale=4,
                        min_width=180
                    )
                    
                    solo_testo_checkbox = gr.Checkbox(
                        label=d.get("solo_testo_checkbox_label", "Text only"),
                        value=solo_attivo,
                        scale=1,
                        min_width=110,
                        show_label=True
                    )
                
                sys_prompt_salvato = s.get("sys_prompt", "")
                vlm_max_tokens_val = int(s.get("vlm_max_tokens", 512))
                
                if sys_prompt_salvato and sys_prompt_salvato.strip():
                    sys_prompt_value = sys_prompt_salvato
                else:
                    sys_prompt_value = _ottieni_prompt_preset_adattivo(default_sugg, solo_attivo, vlm_max_tokens_val)
                    sessione.salva_sessione({"sys_prompt": sys_prompt_value})

                sys_prompt = gr.Textbox(
                    value=sys_prompt_value, 
                    label=d.get("prompt_sistema", "System Prompt"),
                    elem_id="analysis-system-prompt",
                    lines=3,
                    placeholder=""
                )
                
                user_hints = gr.Textbox(
                    value=s.get("user_hints", ""),
                    **lingua.analysis_hints_options(d, solo_attivo),
                    lines=5,
                    visible=True
                )

                btn_analyze = gr.Button(
                    d.get("btn_genera_prompt_testo", "Generate Prompt") if solo_attivo else d.get("btn_analizza", "Analyze"),
                    variant="primary"
                )

            # =========================================================================
            # COLONNA DI DESTRA: IMMAGINE, PROMPT RISULTATO E BARRA STATO
            # =========================================================================
            with gr.Column(scale=1, min_width=340, elem_id="analysis-result", elem_classes=["analisi-col-box", "analisi-destra-box"]) as colonna_destra_analisi:
                with gr.Column(visible=not solo_attivo) as contenitore_media_analisi:
                    with gr.Accordion(d.get("carica_img", "Load Image"), open=True):
                        input_image = gr.Image(
                            type="filepath", sources=["upload"], height=280,
                            elem_classes=["image-preview"], show_label=False
                        )

                risultato_analisi_header = gr.Markdown(d.get("risultato_analisi", "Result"), elem_classes=["studio-section-title"])
                output_prompt_img = gr.Textbox(
                    label=d.get("prompt_generato_label", "Prompt"),
                    lines=14,
                    placeholder=d.get("placeholder_vision", ""),
                    interactive=True,
                    show_label=False,
                    elem_id="output-prompt-img",
                    elem_classes=["fill-height"]
                )

                status_vlm, btn_interrupt_vlm = style.crea_barra_stato_unificata(d.get("in_attesa", "Waiting..."), "tasto-stop-vlm")

            def on_solo_testo_toggle(solo_attivo, preset_val):
                sessione.salva_sessione({"solo_testo_attivo": solo_attivo})
                
                if solo_attivo:
                    sessione.salva_sessione({"nome_immagine_sorgente": ""})

                s_reale = sessione.carica_ultima_sessione()
                vlm_max_tokens_val = int(s_reale.get("vlm_max_tokens", 512))
                
                prompt_preset = _ottieni_prompt_preset_adattivo(preset_val, solo_attivo, vlm_max_tokens_val)
                sessione.salva_sessione({"sys_prompt": prompt_preset})
                
                lang = s_reale.get("lingua_selezionata", "IT")
                dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
                
                if solo_attivo:
                    return (
                        gr.update(visible=False), 
                        gr.update(),              
                        gr.update(lines=3, value=prompt_preset if prompt_preset else ""), 
                        gr.update(visible=True, **lingua.analysis_hints_options(dl, solo_attivo)),  
                        gr.update(value=dl.get("btn_genera_prompt_testo", "Generate Prompt")),
                        gr.update(value=preset_val)
                    )
                else:
                    return (
                        gr.update(visible=True),  
                        gr.update(),              
                        gr.update(lines=3, value=prompt_preset if prompt_preset else ""), 
                        gr.update(visible=True, **lingua.analysis_hints_options(dl, solo_attivo)),  
                        gr.update(value=dl.get("btn_analizza", "Analyze")),
                        gr.update(value=preset_val)
                    )
            
            def on_dropdown_change(preset_val, solo_attivo):
                s_reale = sessione.carica_ultima_sessione()
                vlm_max_tokens_val = int(s_reale.get("vlm_max_tokens", 512))
                prompt_preset = _ottieni_prompt_preset_adattivo(preset_val, solo_attivo, vlm_max_tokens_val)
                sessione.salva_sessione({"sys_prompt": prompt_preset})
                return gr.update(value=prompt_preset if prompt_preset is not None else "")
            
            def on_max_tokens_change(valore, preset_val, solo_attivo):
                nuovo_prompt = _ottieni_prompt_preset_adattivo(preset_val, solo_attivo, int(valore))
                sessione.salva_sessione({"sys_prompt": nuovo_prompt, "vlm_max_tokens": valore})
                return gr.update(value=nuovo_prompt)
            
            def salva_dropdown_suggerimento(valore):
                sessione.salva_sessione({"suggerimento_vision_selezionato": valore})
                return valore
            
            dropdown_sugg_vision.change(
                fn=salva_dropdown_suggerimento,
                inputs=[dropdown_sugg_vision],
                outputs=[dropdown_sugg_vision]
            ).then(
                fn=on_dropdown_change,
                inputs=[dropdown_sugg_vision, solo_testo_checkbox],
                outputs=[sys_prompt]
            )
            
            solo_testo_checkbox.change(
                fn=on_solo_testo_toggle,
                inputs=[solo_testo_checkbox, dropdown_sugg_vision],
                outputs=[contenitore_media_analisi, input_image, sys_prompt, user_hints, btn_analyze, dropdown_sugg_vision]
            )
            
            vlm_max_tokens.release(
                fn=on_max_tokens_change,
                inputs=[vlm_max_tokens, dropdown_sugg_vision, solo_testo_checkbox],
                outputs=[sys_prompt]
            )

    return {
        "tab_el": tab_el,
        "input_image": input_image,
        "dropdown_model": dropdown_model,
        "dropdown_sugg_vision": dropdown_sugg_vision,
        "sys_prompt": sys_prompt,
        "user_hints": user_hints,
        "btn_analyze": btn_analyze,
        "risultato_analisi_header": risultato_analisi_header,
        "output_prompt_img": output_prompt_img,
        "llama_vision_md": llama_vision_md,
        "contenitore_media_analisi": contenitore_media_analisi,
        "solo_testo_checkbox": solo_testo_checkbox,
        "status_vlm": status_vlm,
        "btn_interrupt_vlm": btn_interrupt_vlm,
        "colonna_destra_analisi": colonna_destra_analisi,
        "vlm_max_tokens": vlm_max_tokens
    }
