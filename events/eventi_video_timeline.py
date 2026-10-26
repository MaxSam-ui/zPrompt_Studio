# events/eventi_video_timeline.py

import gradio as gr
from core import log, sessione, config
from utils import timeline
from events.eventi_video_helpers import aggiorna_durate_da_timeline_solo_stato


def gestisci_click_timeline(trigger_val, sec, tipo, zoom, mov, audio, testo_timeline, s):
    if not trigger_val or "_" not in str(trigger_val):
        return (
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), testo_timeline, gr.update(), gr.update(),
            gr.update()
        )
    
    try:
        parti = str(trigger_val).split("_")
        azione = parti[0]
        idx = int(parti[1])
        blocchi = timeline._parse_timeline(testo_timeline)
        
        if azione == "EDIT":
            if 0 <= idx < len(blocchi):
                b = blocchi[idx]
                
                tipo_mappato = timeline._mappa_valore_a_scelta_ui(b["tipo"], config.TIPI_INQUADRATURA) if hasattr(timeline, '_mappa_valore_a_scelta_ui') else b["tipo"]
                zoom_mappato = timeline._mappa_valore_a_scelta_ui(b["zoom"], config.TIPI_ZOOM) if hasattr(timeline, '_mappa_valore_a_scelta_ui') else b["zoom"]
                
                return (
                    gr.update(value=b["mov"]),
                    gr.update(value=b["audio"]),
                    gr.update(value=tipo_mappato),   
                    gr.update(value=zoom_mappato), 
                    gr.update(visible=True),   
                    gr.update(visible=False),  
                    gr.update(visible=False),  
                    gr.update(visible=False),  
                    gr.update(value=f"#{idx+1}"),
                    testo_timeline,
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(open=True)
                )
        elif azione == "DELETE":
            if 0 <= idx < len(blocchi):
                blocchi.pop(idx)
                nuovo_testo = timeline._build_timeline_text(blocchi)
                timeline.salva_timeline_sessione(nuovo_testo, s)
                
                default_shot = config.TIPI_INQUADRATURA[0] if config.TIPI_INQUADRATURA else "🧍 [Shot] Medium Shot"
                default_motion = config.TIPI_ZOOM[0] if config.TIPI_ZOOM else "⏹️ [Static] Static (No Zoom)"
                
                return (
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=default_shot),
                    gr.update(value=default_motion),
                    gr.update(visible=False),  
                    gr.update(visible=True),   
                    gr.update(visible=True),   
                    gr.update(visible=True),   
                    gr.update(value=""),
                    nuovo_testo,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(open=False)
                )
    except Exception as e:
        log.registra(f"Error handling timeline click: {e}", "WARNING")
        
    return (
        gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update(), testo_timeline, gr.update(), gr.update(),
        gr.update()
    )


def ui_aggiorna_spezzone_timeline(selettore_id, sec, tipo, zoom, mov, audio, testo, s):
    default_shot = config.TIPI_INQUADRATURA[0] if config.TIPI_INQUADRATURA else "🧍 [Shot] Medium Shot"
    default_motion = config.TIPI_ZOOM[0] if config.TIPI_ZOOM else "⏹️ [Static] Static (No Zoom)"
    
    if not selettore_id or not selettore_id.startswith("#"):
        return (
            testo, "", "", gr.update(value=default_shot), gr.update(value=default_motion),
            gr.update(value=""), gr.update(visible=False), gr.update(visible=True), gr.update(visible=True),
            gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
            gr.update(open=False)
        )
    try:
        idx = int(selettore_id.replace("#", "")) - 1
        blocchi = timeline._parse_timeline(testo)
        if 0 <= idx < len(blocchi):
            # CORREZIONE: preserva la durata originale impostata dal drag o dall'AI senza forzare il valore statico sec=3.0
            blocchi[idx]["mov"] = mov
            blocchi[idx]["audio"] = audio
            blocchi[idx]["tipo"] = tipo
            blocchi[idx]["zoom"] = zoom
            
            nuovo_testo = timeline._build_timeline_text(blocchi)
            timeline.salva_timeline_sessione(nuovo_testo, s)
            return (
                nuovo_testo, "", "", gr.update(value=default_shot), gr.update(value=default_motion),
                gr.update(value=""), gr.update(visible=False), gr.update(visible=True), gr.update(visible=True),
                gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                gr.update(open=False)
            )
    except Exception as e:
        log.registra(f"Error updating timeline block: {e}", "WARNING")
        
    return (
        testo, "", "", gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
        gr.update()
    )


def ui_annulla_editing_timeline(testo, s):
    default_shot = config.TIPI_INQUADRATURA[0] if config.TIPI_INQUADRATURA else "🧍 [Shot] Medium Shot"
    default_motion = config.TIPI_ZOOM[0] if config.TIPI_ZOOM else "⏹️ [Static] Static (No Zoom)"
    
    return (
        "", "", gr.update(value=default_shot), gr.update(value=default_motion),
        "", gr.update(visible=False), gr.update(visible=True), gr.update(visible=True),
        gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
        gr.update(open=False)
    )


def collega_timeline(t3, stato_sessione):
    """Binds visual timeline interactions."""
    t3["hidden_timeline_trigger"].change(
        fn=gestisci_click_timeline,  
        inputs=[
            t3["hidden_timeline_trigger"], t3["scena_sec"], t3["scena_tipo"], t3["scena_zoom"],
            t3["scena_mov"], t3["scena_audio"], t3["tabella_regia_view"], stato_sessione
        ],
        outputs=[
            t3["scena_mov"], t3["scena_audio"], t3["scena_tipo"], t3["scena_zoom"],
            t3["btn_update_timeline"], 
            t3["btn_add_timeline"], t3["btn_remove_last_timeline"], t3["btn_clear_timeline"],
            t3["selettore_blocco_edit"],
            t3["tabella_regia_view"],
            t3["btn_cancel_timeline"],
            t3["riga_update_timeline"],
            t3["accordion_modifica_clip"]  
        ],
        show_progress="hidden"
    ).then(
        fn=lambda: "",
        inputs=None,
        outputs=[t3["hidden_timeline_trigger"]],
        show_progress="hidden"
    )

    t3["btn_update_timeline"].click(
        fn=ui_aggiorna_spezzone_timeline,  
        inputs=[
            t3["selettore_blocco_edit"], t3["scena_sec"], t3["scena_tipo"], t3["scena_zoom"],
            t3["scena_mov"], t3["scena_audio"], t3["tabella_regia_view"], stato_sessione
        ],
        outputs=[
            t3["tabella_regia_view"], t3["scena_mov"], t3["scena_audio"], t3["scena_tipo"], t3["scena_zoom"],
            t3["selettore_blocco_edit"], t3["btn_update_timeline"], t3["btn_add_timeline"], t3["btn_remove_last_timeline"], t3["btn_clear_timeline"],
            t3["btn_cancel_timeline"],
            t3["riga_update_timeline"],
            t3["accordion_modifica_clip"]  
        ],
        show_progress="hidden"
    )
    
    t3["btn_cancel_timeline"].click(
        fn=ui_annulla_editing_timeline,  
        inputs=[t3["tabella_regia_view"], stato_sessione],
        outputs=[
            t3["scena_mov"], t3["scena_audio"], t3["scena_tipo"], t3["scena_zoom"],
            t3["selettore_blocco_edit"],
            t3["btn_update_timeline"], t3["btn_add_timeline"], t3["btn_remove_last_timeline"], t3["btn_clear_timeline"],
            t3["btn_cancel_timeline"],
            t3["riga_update_timeline"],
            t3["accordion_modifica_clip"]  
        ],
        show_progress="hidden"
    ).then(
        fn=None,
        inputs=None,
        outputs=None,
        js="() => { document.querySelectorAll('.timeline-visual-item').forEach(item => item.classList.remove('editing')); }"
    )

    t3["btn_add_timeline"].click(
        fn=timeline.aggiungi_spezzone_testuale,
        inputs=[t3["scena_sec"], t3["scena_tipo"], t3["scena_zoom"], t3["scena_mov"], t3["scena_audio"], t3["tabella_regia_view"], stato_sessione],
        outputs=[t3["tabella_regia_view"], t3["scena_mov"], t3["scena_audio"]],
        show_progress="hidden"
    )
    t3["btn_remove_last_timeline"].click(
        fn=timeline.rimuovi_ultimo_spezzone,
        inputs=[t3["tabella_regia_view"], stato_sessione],
        outputs=[t3["tabella_regia_view"]],
        show_progress="hidden"
    )
    t3["btn_clear_timeline"].click(
        fn=timeline.svuota_timeline_completa,
        inputs=[stato_sessione],
        outputs=[t3["tabella_regia_view"], t3["scena_mov"], t3["scena_audio"]],
        show_progress="hidden"
    )
    
    t3["tabella_regia_view"].change(
        fn=timeline.compila_timeline_html,
        inputs=[t3["tabella_regia_view"]],
        outputs=[t3["timeline_visuale"]],
        show_progress="hidden"
    ).then(
        fn=aggiorna_durate_da_timeline_solo_stato,
        inputs=[t3["tabella_regia_view"]],
        outputs=[t3["video_durata_totale"]],
        show_progress="hidden"
    )
