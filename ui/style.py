# ui/style.py

import os
import gradio as gr

from core.config import TIPI_INQUADRATURA, TIPI_ZOOM

TEMA = gr.themes.Soft(
    primary_hue="blue", 
    secondary_hue="slate",
    text_size="md"
).set(
    body_background_fill="#101216",
    body_background_fill_dark="#101216",
    body_text_color="#e6e9ef",
    body_text_color_dark="#e6e9ef",
    block_background_fill="#191c22",
    block_background_fill_dark="#191c22",
    block_label_text_color="#b8c0cd",
    block_label_text_color_dark="#b8c0cd",
    block_title_text_color="#e6e9ef",
    block_title_text_color_dark="#e6e9ef",
    input_background_fill="#111419",
    input_background_fill_dark="#111419",
    input_border_color="#343b47",
    input_border_color_dark="#343b47",
    input_placeholder_color="#8e99aa",
    input_placeholder_color_dark="#8e99aa",
    button_primary_background_fill="#326bd6",
    button_primary_background_fill_dark="#326bd6",
    button_primary_text_color="#ffffff",
    button_primary_text_color_dark="#ffffff",
    button_secondary_background_fill="#252b35",
    button_secondary_background_fill_dark="#252b35",
    button_secondary_text_color="#e6e9ef",
    button_secondary_text_color_dark="#e6e9ef"
)

CSS = ""
percorsi_da_tentare = [
    os.path.join(os.path.dirname(__file__), "style.css"),                           
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "style.css"),        
    "style.css",                                                                   
    os.path.abspath("ui/style.css")                                               
]

css_trovato = False
for p in percorsi_da_tentare:
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                CSS = f.read()
            css_trovato = True
            break
        except Exception:
            pass


with open(os.path.join(os.path.dirname(__file__), "studio.css"), encoding="utf-8") as f:
    CSS += "\n" + f.read()


def crea_barra_stato_unificata(placeholder, elem_id_stop, elem_id_skip=None, mostra_skip=None):
    if mostra_skip is None:
        mostra_skip = (elem_id_skip is not None)

    from ui.status_feedback import update_status_feedback, render_status_feedback
    status_box = gr.Textbox(visible=False)
    with gr.Row(variant="compact", elem_classes=["barra-stato-unificata", "studio-operation-row"]):
        feedback = gr.HTML(value=render_status_feedback(placeholder), elem_classes=["studio-status-details"])
        
        if mostra_skip:
            btn_skip = gr.Button(
                "⏭️", 
                variant="secondary", 
                size="sm", 
                elem_id=elem_id_skip if elem_id_skip else f"{elem_id_stop}-skip", 
                elem_classes=["tasto-skip-unificato"],
                scale=1, 
                min_width=44
            )
            btn_stop = gr.Button(
                "⏹️", 
                variant="stop", 
                size="sm", 
                elem_id=elem_id_stop, 
                elem_classes=["tasto-stop-unificato"],
                scale=1, 
                min_width=44
            )
        else:
            btn_stop = gr.Button(
                "⏹️", 
                variant="stop", 
                size="sm", 
                elem_id=elem_id_stop, 
                elem_classes=["tasto-stop-unificato"],
                scale=1, 
                min_width=44
            )
    status_box.change(
        fn=update_status_feedback,
        inputs=[status_box], outputs=[feedback],
        queue=False, show_progress="hidden",
    )
    status_box._studio_feedback = feedback
    if mostra_skip:
        return status_box, btn_skip, btn_stop
    return status_box, btn_stop
