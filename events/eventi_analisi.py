# events/eventi_analisi.py

import gradio as gr
from core import sessione, log, lingua, config
from services import comfyui_manager, local_vlm
from utils.media_utils import gestore_analisi_adattivo, aggiorna_dopo_analisi

def _ottieni_traduzione_istantanea(chiave):
    try:
        s_attiva = sessione.carica_ultima_sessione()
        lang = s_attiva.get("lingua_selezionata", "IT")
        return lingua.LINGUE[lang][chiave]
    except Exception:
        return "..."

def ripristina_bottone_analisi(solo_testo):
    comfyui_manager.generazione_attiva = False
    
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    nuovo_testo = dl.get("btn_genera_prompt_testo", "Generate Prompt") if solo_testo else dl.get("btn_analizza", "Analyze")
    return gr.update(interactive=True, value=nuovo_testo)

def gestisci_interruzione_vlm_sicura():
    log.registra("VLM: Inference interruption request received.")
    return comfyui_manager.interrompi_comfyui()

def get_prompt_success_msg(status=""):
    if str(status).startswith(("❌", "⚠", "⏹", "🛑")):
        return gr.update()
    if getattr(comfyui_manager, "vlm_interrotto", False):
        return gr.update()
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    return lingua.LINGUE.get(lang, {}).get("prompt_success", "✅ Prompt generated successfully!")

def imposta_classe_post_analisi(status=""):
    if getattr(comfyui_manager, "vlm_interrotto", False) or str(status).startswith(("❌", "⚠", "⏹", "🛑")):
        return gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"])
    return gr.update(elem_classes=["analisi-col-box", "analisi-destra-box", "completato-successo"])

def reset_prompt_residui_nuova_immagine():
    """Resets visual border and clears residual video prompts in session without clearing Rendering prompt."""
    sessione.salva_sessione({
        "output_prompt_video": ""
    })
    return (
        gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"]),
        gr.update(value="")
    )


def analisi_con_stato(*args):
    from utils.vlm_status import VLMStatus
    produced = False
    failed = False
    for chunk in gestore_analisi_adattivo(*args):
        if isinstance(chunk, VLMStatus):
            yield gr.update(), str(chunk)
        elif str(chunk).startswith(("⚠", "⏹", "🛑")):
            failed = True
            yield gr.update(), str(chunk)
        elif str(chunk).startswith(("❌", "Errore")):
            failed = True
            yield gr.update(), "❌ " + str(chunk).removeprefix("❌ ")
        else:
            produced = bool(str(chunk or '').strip())
            yield chunk, gr.update()
    if not produced and not failed and not getattr(comfyui_manager, 'vlm_interrotto', False):
        yield gr.update(), _ottieni_traduzione_istantanea('analysis_empty_result')


def sincronizza_analisi_valida(prompt, image, status):
    if not str(prompt or '').strip() or str(status).startswith(("❌", "⚠", "⏹", "🛑")):
        return tuple(gr.update() for _ in range(6))
    return aggiorna_dopo_analisi(prompt, image)


def sincronizza_stile_video(scelta):
    """Mirror explicit user selections only, without rewriting generated text."""
    scelte = config.elenca_suggerimenti(config.SUGGESTION_DIRECTION_DIR)
    if scelta != "-" and scelta not in scelte:
        return gr.update()
    sessione.salva_sessione({"suggerimento_regia_selezionato": scelta})
    return gr.update(choices=["-"] + scelte, value=scelta)


def collega_analisi(t1, t2, t3, t5, stato_generazione):
    # .input excludes programmatic updates from session loading/language changes.
    t1["dropdown_sugg_vision"].input(
        fn=sincronizza_stile_video,
        inputs=[t1["dropdown_sugg_vision"]],
        outputs=[t3["dropdown_sugg_director"]],
        queue=False, show_progress="hidden"
    )
    t1["btn_analyze"].click(
        fn=lambda solo_testo, hints: (
            gr.update(interactive=False, value="⏳..."), 
            gr.update() if solo_testo and not str(hints or "").strip() else "",
            gr.update() if solo_testo and not str(hints or "").strip() else "",
            "⏳ " + _ottieni_traduzione_istantanea("vlm_elaborazione"),
            gr.update(elem_classes=["analisi-col-box", "analisi-destra-box", "elaborazione-attiva"])
        ),
        inputs=[t1["solo_testo_checkbox"], t1["user_hints"]], 
        outputs=[t1["btn_analyze"], t1["output_prompt_img"], t2["prompt_to_send_img"], t1["status_vlm"], t1["colonna_destra_analisi"]]
    ).then(
        fn=analisi_con_stato,
        inputs=[t1["input_image"], t1["sys_prompt"], t1["user_hints"], t1["dropdown_model"], t1["solo_testo_checkbox"], t1["vlm_max_tokens"]],
        outputs=[t1["output_prompt_img"], t1["status_vlm"]]
    ).then(
        fn=sincronizza_analisi_valida,
        inputs=[t1["output_prompt_img"], t1["input_image"], t1["status_vlm"]],
        outputs=[t2["prompt_to_send_img"], t5["box_log_terminale"], t2["img_width"], t2["img_height"], t3["video_rapporto"], t3["video_risoluzione"]]
    ).then(
        fn=get_prompt_success_msg,
        inputs=[t1["status_vlm"]],
        outputs=[t1["status_vlm"]]
    ).then(
        fn=imposta_classe_post_analisi,
        inputs=[t1["status_vlm"]],
        outputs=[t1["colonna_destra_analisi"]]
    ).then(
        fn=lambda: setattr(comfyui_manager, 'generazione_attiva', False),
        inputs=None, outputs=None
    ).then(
        fn=ripristina_bottone_analisi,
        inputs=[t1["solo_testo_checkbox"]],
        outputs=t1["btn_analyze"]
    )
    
    t1["btn_interrupt_vlm"].click(
        fn=gestisci_interruzione_vlm_sicura,
        inputs=None,
        outputs=[t1["status_vlm"]]
    ).then(
        fn=ripristina_bottone_analisi,
        inputs=[t1["solo_testo_checkbox"]],
        outputs=t1["btn_analyze"]
    ).then(
        fn=lambda: gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"]),
        inputs=None,
        outputs=[t1["colonna_destra_analisi"]]
    )

    t1["input_image"].change(
        fn=reset_prompt_residui_nuova_immagine,
        inputs=None,
        outputs=[t1["colonna_destra_analisi"], t3["output_prompt_video"]]
    )
    t1["user_hints"].change(
        fn=lambda: gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"]),
        inputs=None,
        outputs=[t1["colonna_destra_analisi"]]
    )
    t1["sys_prompt"].change(
        fn=lambda: gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"]),
        inputs=None,
        outputs=[t1["colonna_destra_analisi"]]
    )
