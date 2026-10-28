# ui/barra_superiore.py

import gradio as gr
import html
from core import hardware, sessione, lingua
from services import comfyui_manager
from services.help_routes import manual_url


def aggiorna_avviso_comfyui():
    key = comfyui_manager.startup_error
    if not key or comfyui_manager.is_comfyui_running():
        return gr.update(value="", visible=False)
    lang = sessione.carica_ultima_sessione().get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    message = html.escape(dl.get(key, key))
    path = html.escape(str(comfyui_manager.COMFYUI_DIR))
    label = html.escape(dl.get("comfy_error_path", "Configured folder"))
    return gr.update(value=f'<div role="alert" style="border:1px solid #e6a23c;border-radius:8px;padding:12px;overflow-wrap:anywhere">'
                           f'⚠️ {message}<br><small>{label}: {path}</small></div>', visible=True)

def crea_barra_superiore(d: dict) -> dict:
    """Crea la barra superiore di visualizzazione risorse e stato del sistema."""
    with gr.Row(elem_classes=["barra-risorse"]) as barra_superiore:
        with gr.Column(scale=4, min_width=240):
            titolo_app = gr.Markdown(f"# {d.get('titolo', 'zPrompt Studio')}", elem_id="titolo-grande-app")
        
        with gr.Column(scale=8, min_width=280, elem_id="studio-hardware"):
            testo_hardware = gr.Markdown(
                value=hardware.ottieni_stato_resources if hasattr(hardware, 'ottieni_stato_resources') else hardware.ottieni_stato_risorse()
            )
            
        with gr.Column(scale=2, min_width=160):
            spia_comfy = gr.HTML(value=d.get("comfy_offline", "<span style='color:red;'>🔴 ComfyUI offline</span>"))
            
        with gr.Column(scale=0, min_width=124, elem_id="colonna-pulsanti-risorse"):
            with gr.Row(variant="compact"):
                btn_clean_mem = gr.Button("🧹", size="sm", variant="secondary")
                btn_hard_reset = gr.Button("🛑", size="sm", variant="stop")
                btn_help = gr.Button("?", link=manual_url(sessione.carica_ultima_sessione().get("lingua_selezionata", "IT")), size="sm", variant="secondary",
                          min_width=36, elem_id="studio-help-button")

    avviso_comfy = gr.HTML(value="", visible=False)
    timer_avviso = gr.Timer(3)
    timer_avviso.tick(aggiorna_avviso_comfyui, outputs=avviso_comfy, queue=False, show_progress="hidden")

    return {
        "barra_superiore": barra_superiore,
        "titolo_app": titolo_app,
        "testo_hardware": testo_hardware,
        "spia_comfy": spia_comfy,
        "btn_clean_mem": btn_clean_mem,
        "btn_hard_reset": btn_hard_reset,
        "btn_help": btn_help
    }


def aggiorna_stato_comfyui():
    """
    Funzione di polling temporizzato per l'aggiornamento dello stato di ComfyUI e il lock globale dei comandi.
    Restituisce esattamente 12 valori allineati con i componenti mappati nel timer di main.py.
    """
    is_attiva = (comfyui_manager.generazione_attiva or comfyui_manager.batch_attivo)
    comfyui_online = comfyui_manager.is_comfyui_running()
    
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    classe_barra = ["barra-risorse", "lavoro-attivo"] if is_attiva else ["barra-risorse"]
    classe_tabs = ["lavoro-attivo-tabs"] if is_attiva else []
    
    # Valori di interattività per i comandi VLM (Analisi, Refine, Timeline, Dialoghi, Soggetto, Regia)
    # Quando una generazione è attiva su qualsiasi tab, TUTTI i comandi VLM devono essere bloccati per prevenire OOM CUDA
    interattivo_vlm = gr.update(interactive=not is_attiva)

    if comfyui_online:
        if is_attiva:
            return (
                gr.update(value=dl.get("comfy_online", "")), 
                gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), 
                gr.update(interactive=False), gr.update(interactive=False), 
                gr.update(interactive=False), gr.update(interactive=False),
                gr.update(interactive=False), gr.update(interactive=False), 
                gr.update(elem_classes=classe_barra), gr.update(elem_classes=classe_tabs) 
            )
        return (
            gr.update(value=dl.get("comfy_online", "")), 
            gr.update(interactive=True), gr.update(interactive=True), gr.update(interactive=True), 
            gr.update(interactive=True), gr.update(interactive=True), 
            gr.update(interactive=True), gr.update(interactive=True),
            gr.update(interactive=True), gr.update(interactive=True), 
            gr.update(elem_classes=classe_barra), gr.update(elem_classes=classe_tabs)
        )
    elif comfyui_manager.comfyui_process is not None and comfyui_manager.comfyui_process.poll() is None:
        return (
            gr.update(value=dl.get("comfy_avvio", "")), 
            gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), 
            interattivo_vlm, interattivo_vlm, 
            interattivo_vlm, interattivo_vlm,
            interattivo_vlm, interattivo_vlm, 
            gr.update(elem_classes=classe_barra), gr.update(elem_classes=classe_tabs)
        )
    else:
        return (
            gr.update(value=dl.get("comfy_offline", "")), 
            gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), 
            interattivo_vlm, interattivo_vlm, 
            interattivo_vlm, interattivo_vlm,
            interattivo_vlm, interattivo_vlm,   
            gr.update(elem_classes=classe_barra), gr.update(elem_classes=classe_tabs)
        )
