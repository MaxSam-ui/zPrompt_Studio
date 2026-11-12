from events.lora_controls import bind_lora_controls
# events/eventi_video_generazione.py

import os
import re
import gradio as gr
from core import config, sessione, log, lingua, workflow_registry
from services import prompt_manager, comfyui_manager, director_ai
from utils import timeline
from utils.media_utils import sync_immagine_sorgente_i2v, gestore_estensione_video, calcola_stato_spia_video
from generators.video import sanitizza_prompt_video
from events.rendering_gallery_sync import gestisci_trigger_galleria_video_html

from events.eventi_video_helpers import (
    _ottieni_traduzione_istantanea,
    avvia_miglioramento_soggetto,
    ripristina_miglioramento_soggetto,
    avvia_scrittura_sceneggiatura,
    ui_ripristina_scrittura_sceneggiatura,
    avvia_generazione_dialoghi,
    ripristina_generazione_dialoghi,
    avvia_compilazione_regia,
    ripristina_compilazione_regia,
    avvia_blocco_generazione_video,
    ripristina_blocco_generazione_video,
    sblocca_tutti_i_pulsanti_video,
    gestisci_interruzione_video_sicura,
    imposta_classe_post_compilazione_regia,
    imposta_classe_post_sceneggiatura,
    carica_suggerimento_sceneggiatura,
    aggiorna_durate_da_timeline_solo_stato,
    aggiorna_durata_da_drag,
    aggiorna_spia_su_cambio_parametro,
    gestisci_aggiunta_lora_vid,
    gestisci_rimozione_lora_vid,
    gestisci_generazione_video_con_monitor
)


def gestisci_cambio_modello_video(modello_selezionato):
    sessione.salva_sessione({"modello_video_attivo": modello_selezionato})
    is_minimax = modello_selezionato == "MiniMax H3"
    
    scelte_lora = workflow_registry.ottieni_lora_disponibili_video(modello_selezionato)
    s_attiva = sessione.carica_ultima_sessione()
    
    if is_minimax:
        l1_val = s_attiva.get("lora_video1_name_minimax", "-")
        l2_val = s_attiva.get("lora_video2_name_minimax", "-")
        l3_val = s_attiva.get("lora_video3_name_minimax", "-")
        l1_str = s_attiva.get("lora_video1_str_minimax", 1.0)
        l2_str = s_attiva.get("lora_video2_str_minimax", 1.0)
        l3_str = s_attiva.get("lora_video3_str_minimax", 1.0)
    else:
        l1_val = s_attiva.get("lora_video1_name", "-")
        l2_val = s_attiva.get("lora_video2_name", "-")
        l3_val = s_attiva.get("lora_video3_name", "-")
        l1_str = s_attiva.get("lora_video1_str", 1.0)
        l2_str = s_attiva.get("lora_video2_str", 1.0)
        l3_str = s_attiva.get("lora_video3_str", 1.0)

    l1_val = workflow_registry.normalizza_lora_per_scelte(l1_val, scelte_lora)
    l2_val = workflow_registry.normalizza_lora_per_scelte(l2_val, scelte_lora)
    l3_val = workflow_registry.normalizza_lora_per_scelte(l3_val, scelte_lora)

    return (
        gr.update(visible=not is_minimax),  
        gr.update(visible=not is_minimax),  
        gr.update(visible=is_minimax),      
        gr.update(visible=is_minimax),      
        gr.update(choices=scelte_lora, value=l1_val), 
        gr.update(choices=scelte_lora, value=l2_val), 
        gr.update(choices=scelte_lora, value=l3_val),
        gr.update(value=float(l1_str)),
        gr.update(value=float(l2_str)),
        gr.update(value=float(l3_str)),
        gr.update(choices=["24"] if is_minimax else ["16", "24", "30", "60"], value="24", interactive=not is_minimax)
    )


def seleziona_turbo_profile(profile):
    scheduler = "beta"
    if profile == "Attuale / Current":
        import json
        with open(workflow_registry.risolvi_percorso_json_video("MiniMax H3"), encoding="utf-8") as stream:
            inputs = json.load(stream)["332"]["inputs"]
        steps, scheduler = int(inputs["steps"]), str(inputs["scheduler"])
    else:
        steps = {"V4 - 6 steps": 6, "V4 - 8 steps": 8}[profile]
    sessione.salva_sessione({"minimax_turbo_profile": profile,
        "video_steps_minimax": steps, "video_scheduler_minimax": scheduler, "video_denoise_minimax": 1.0})
    return gr.update(value=steps), gr.update(value=scheduler), gr.update(value=1.0)


def salva_e_sincronizza_durata_sceneggiatura(durata_val, testo_timeline):
    sessione.salva_sessione({"sceneggiatura_durata": durata_val})
    blocchi = timeline._parse_timeline(testo_timeline)
    if not blocchi:
        sessione.salva_sessione({"video_durata_totale": float(durata_val)})
        return float(durata_val)
    return gr.update()


def compila_regia_sanitizzata(prompt_img, m_vlm_vid, tabella_regia, audio_desc, durata_totale, stato_gen, sys_prompt, dropdown_model, sugg_director, solo_testo_video=False, prompt_corrente=None, soggetto=None):
    """Sostituisce il segnaposto {NUM_FRAMES} col numero reale di frame e pulisce il prompt video generato in tempo reale."""
    num_frames_reale = 3
    if stato_gen and isinstance(stato_gen.get("lista_frame_storyboard_attivi"), list) and stato_gen["lista_frame_storyboard_attivi"]:
        num_frames_reale = len(stato_gen["lista_frame_storyboard_attivi"])
        
    prompt_img_pulito = (prompt_img or "").replace("{NUM_FRAMES}", str(num_frames_reale)).replace("{num_pannelli_int}", str(num_frames_reale))
    
    for res_vid, res_img, status in director_ai.passa_timeline_a_gemma(
        prompt_img_pulito, m_vlm_vid, tabella_regia, audio_desc, durata_totale, stato_gen, sys_prompt, dropdown_model, sugg_director,
        solo_testo_video=solo_testo_video, prompt_corrente=prompt_corrente, soggetto=soggetto
    ):
        if director_ai._errore_vlm(status):
            yield prompt_corrente if prompt_corrente is not None else gr.update(), prompt_img, status
            continue
        res_vid_pulito = sanitizza_prompt_video(res_vid) if isinstance(res_vid, str) else res_vid
        has_scene_text = isinstance(res_vid_pulito, str) and bool(re.sub(r'\[[^\]]*\]', '', res_vid_pulito).strip())
        if str(status).startswith("✅") and not has_scene_text:
            yield prompt_corrente if prompt_corrente is not None else gr.update(), prompt_img, _ottieni_traduzione_istantanea("analysis_empty_result")
            return
        if str(status).startswith("✅"):
            sessione.salva_sessione({"video_prompt_source": {
                "timeline": tabella_regia, "audio": audio_desc, "prompt": res_vid_pulito,
                "subject": soggetto if soggetto is not None else sessione.carica_ultima_sessione().get("sceneggiatura_prompt", "")
            }})
        yield res_vid_pulito, res_img, status


def stato_finale_video(status):
    import re
    classes = ["analisi-col-box", "analisi-destra-box"]
    status = re.sub(r'^\[[^\]]+\]\s*', '', str(status).strip())
    if status.startswith(("✅", "📸")) and not comfyui_manager.vlm_interrotto:
        classes.append("completato-successo")
    return gr.update(elem_classes=classes)


def avvia_cornici_video(pannello):
    """Only the current output panel glows; remove previous operation feedback."""
    updates = []
    for name in ("subject", "timeline", "prompt", "video"):
        classes = ["analisi-col-box"]
        if name == "video":
            classes.append("analisi-destra-box")
        if name == pannello:
            classes.append("elaborazione-attiva")
        updates.append(gr.update(elem_classes=classes))
    return tuple(updates)


def collega_generazione(t1, t2, t3, t5, num_lora_vid, stato_generazione, stato_sessione):
    """Binds operational logic, VLM calls, and connection to ComfyUI."""
    
    def aggiorna_titolo_prompt(timeline_text, prompt, audio, subject):
        from utils.video_prompt_state import prompt_header
        saved = sessione.carica_ultima_sessione()
        dictionary = lingua.ottieni_dizionario_lingua(saved.get("lingua_selezionata", "IT"))
        return prompt_header(saved, timeline_text, prompt, audio, dictionary, subject)

    for component in (t3["tabella_regia_view"], t3["output_prompt_video"], t3["audio_descrizione"], t3["sceneggiatura_prompt"]):
        component.change(
            fn=aggiorna_titolo_prompt,
            inputs=[t3["tabella_regia_view"], t3["output_prompt_video"], t3["audio_descrizione"], t3["sceneggiatura_prompt"]],
            outputs=[t3["prompt_cinema_header"]], show_progress="hidden"
        )

    def ripristina_riferimenti_video(stato_gen):
        from utils.media_utils import calcola_frames_tab_video, compila_striscia_video_html
        saved = sessione.carica_ultima_sessione()
        state = stato_gen if stato_gen is not None else saved
        path = state.get("percorso_immagine_selezionata")
        frames = calcola_frames_tab_video(state, saved)
        return (gr.update(value=path if path and os.path.isfile(path) else None),
                compila_striscia_video_html(frames, is_storyboard="storyboard" in str(saved.get("generation_mode", "")).lower()))

    t3["tab_el"].select(
        fn=ripristina_riferimenti_video, inputs=[stato_generazione],
        outputs=[t3["immagine_sorgente_i2v"], t3["storyboard_video_gallery"]],
        show_progress="hidden", concurrency_id="gallery-selection", concurrency_limit=1
    )

    t3["turbo_profile"].change(
        fn=seleziona_turbo_profile, inputs=[t3["turbo_profile"]],
        outputs=[t3["video_steps_vid"], t3["video_scheduler_vid"], t3["video_denoise_vid"]]
    )
    t3["dropdown_saved_video_prompts"].change(
        fn=prompt_manager.leggi_prompt_salvato_vid,
        inputs=[t3["dropdown_saved_video_prompts"]],
        outputs=[t3["output_prompt_video"]]
    )

    t3["btn_interrupt_vid"].click(
        fn=gestisci_interruzione_video_sicura,
        inputs=None,
        outputs=[t3["output_comfy_vid_status"]]
    ).then(
        fn=sblocca_tutti_i_pulsanti_video,
        inputs=None,
        outputs=[
            t3["btn_improve_subject"],
            t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"],
            t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"],
            t3["btn_extend_video"],
            t3["btn_save_video_prompt"],
            t3["colonna_destra_video_player"],
            t3["colonna_prompt_video_box"],
            t3["colonna_top_timeline"],
            t3["colonna_soggetto_video"]
        ]
    )

    t3["hidden_video_gallery_trigger"].change(
        fn=gestisci_trigger_galleria_video_html,
        inputs=[t3["hidden_video_gallery_trigger"], stato_generazione],
        outputs=[
            stato_generazione,
            t3["immagine_sorgente_i2v"],
            t3["storyboard_video_gallery"]
        ],
        show_progress="hidden", trigger_mode="multiple",
        concurrency_id="gallery-selection", concurrency_limit=1
    )

    def on_immagine_sorgente_cambia(filepath, s_sessione, stato_gen, solo_testo):
        stato_gen = stato_gen if stato_gen is not None else {}
        stato_gen["gallery_no_sync"] = False
        stato_gen["is_extension"] = False
        stato_gen["immagine_caricata_manualmente"] = bool(filepath)
        if not filepath:
            stato_gen["percorso_immagine_selezionata"] = None
            sessione.salva_sessione({"percorso_immagine_selezionata": None})
        p_up, ratio_up, res_up, g_img_up, g_story_up, seed_vis, seed_vid, stato_gen, w_up, h_up, seed_mode_up, seed_val_up = sync_immagine_sorgente_i2v(filepath, stato_gen)
        from utils.media_utils import compila_galleria_html
        g_img_up = gr.update(value=compila_galleria_html(stato_gen.get("immagini_generate_cumulate", [])))
        g_story_up = gr.update(value=compila_galleria_html(stato_gen.get("lista_frame_storyboard_attivi", [])))
        spia_html = calcola_stato_spia_video(s_sessione, stato_gen, solo_testo)
        
        # A source-frame upload must not discard the user's film idea.
        sceneggiatura_reset = gr.update()

        return (
            p_up, ratio_up, res_up, g_img_up, g_story_up, seed_vis, seed_vid, 
            stato_gen, gr.update(value=spia_html), w_up, h_up, seed_mode_up, seed_val_up,
            sceneggiatura_reset
        )

    # Only user uploads/removal may import metadata; programmatic selections already own their state.
    t3["immagine_sorgente_i2v"].input(
        fn=on_immagine_sorgente_cambia,
        inputs=[t3["immagine_sorgente_i2v"], stato_sessione, stato_generazione, t3["solo_testo_video"]],
        outputs=[
            t2["prompt_to_send_img"], 
            t3["video_rapporto"], 
            t3["video_risoluzione"], 
            t2["gallery_img"], 
            t2["gallery_storyboard"], 
            t2["seed_visualizzato"],  
            t3["video_seed"],         
            stato_generazione,
            t3["spia_modalita_video"],
            t2["img_width"],          
            t2["img_height"],         
            t2["img_seed_mode"],      
            t2["img_seed"],
            t3["sceneggiatura_prompt"]
        ],
        concurrency_id="gallery-selection", concurrency_limit=1, show_progress="hidden"
    )

    t3["durata_drag_trigger"].change(
        fn=aggiorna_durata_da_drag,
        inputs=[t3["durata_drag_trigger"]],
        outputs=[t3["video_durata_totale"], t3["sceneggiatura_durata"]],
        show_progress="hidden"
    )

    bind_lora_controls(
        t3["btn_add_lora_vid"], t3["btn_rem_lora_vid"], num_lora_vid,
        [t3["row_lora_vid2"], t3["row_lora_vid3"]],
        [t3["lora_vid2_name"], t3["lora_vid2_str"], t3["lora_vid3_name"], t3["lora_vid3_str"]],
        gestisci_aggiunta_lora_vid, gestisci_rimozione_lora_vid, "lora-controls-video"
    )

    t3["btn_save_video_prompt"].click(
        fn=prompt_manager.salva_prompt_video_su_disco,
        inputs=[t3["output_prompt_video"], t3["dropdown_model_video"], stato_generazione],
        outputs=[t5["box_log_terminale"], t3["dropdown_saved_video_prompts"]]
    )

    # Write Timeline (🎬)
    t3["btn_generate_auto_timeline"].click(
        fn=avvia_scrittura_sceneggiatura,
        inputs=None, 
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"], t3["output_comfy_vid_status"]
        ],
        show_progress="hidden"
    ).then(
        fn=lambda: avvia_cornici_video("timeline"),
        inputs=None,
        outputs=[t3["colonna_soggetto_video"], t3["colonna_top_timeline"],
                 t3["colonna_prompt_video_box"], t3["colonna_destra_video_player"]],
        show_progress="hidden"
    ).then(
        fn=director_ai.scrivi_sceneggiatura_automatica,
        inputs=[
            t2["prompt_to_send_img"], t3["dropdown_model_video"], t3["sceneggiatura_prompt"], 
            t3["sceneggiatura_durata"], stato_generazione, t1["sys_prompt"], t1["dropdown_model"],
            t3["solo_testo_video"], t3["tabella_regia_view"], t3["audio_descrizione"]
        ],
        outputs=[t3["tabella_regia_view"], t2["prompt_to_send_img"], t3["audio_descrizione"], t3["output_comfy_vid_status"]],
        show_progress="hidden"
    ).then(
        fn=lambda timeline_txt, prompt, audio, status: sessione.salva_sessione({
            "lista_scene_salvate": timeline_txt,
            "prompt_to_send_img": prompt,
            "audio_descrizione": audio
        }) if str(status).startswith("✅") else None,
        inputs=[t3["tabella_regia_view"], t2["prompt_to_send_img"], t3["audio_descrizione"], t3["output_comfy_vid_status"]],
        outputs=None,
        show_progress="hidden"
    ).then(
        fn=imposta_classe_post_sceneggiatura,
        inputs=[t3["output_comfy_vid_status"]],
        outputs=[t3["colonna_top_timeline"]],
        show_progress="hidden"
    ).then(
        fn=lambda: setattr(comfyui_manager, 'generazione_attiva', False),
        inputs=None, outputs=None,
        show_progress="hidden"
    ).then(
        fn=ui_ripristina_scrittura_sceneggiatura,
        inputs=None, 
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"]
        ],
        show_progress="hidden"
    )

    # Improve Subject (🪄)
    t3["btn_improve_subject"].click(
        fn=avvia_miglioramento_soggetto,
        inputs=None,
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"], t3["output_comfy_vid_status"]
        ],
        show_progress="hidden"
    ).then(
        fn=lambda: avvia_cornici_video("subject"),
        inputs=None,
        outputs=[t3["colonna_soggetto_video"], t3["colonna_top_timeline"],
                 t3["colonna_prompt_video_box"], t3["colonna_destra_video_player"]],
        show_progress="hidden"
    ).then(
        fn=director_ai.migliora_soggetto_con_vlm,
        inputs=[
            t3["sceneggiatura_prompt"], 
            t3["dropdown_model_video"],
            stato_generazione,
            t2["prompt_to_send_img"],
            t3["solo_testo_video"]
        ],
        outputs=[t3["sceneggiatura_prompt"], t3["output_comfy_vid_status"]],
        show_progress="hidden"
    ).then(
        fn=lambda prompt_text, status: sessione.salva_sessione({"sceneggiatura_prompt": prompt_text}) if str(status).startswith("✅") else None,
        inputs=[t3["sceneggiatura_prompt"], t3["output_comfy_vid_status"]],
        outputs=None,
        show_progress="hidden"
    ).then(
        fn=imposta_classe_post_sceneggiatura,
        inputs=[t3["output_comfy_vid_status"]],
        outputs=[t3["colonna_soggetto_video"]],
        show_progress="hidden"
    ).then(
        fn=ripristina_miglioramento_soggetto,
        inputs=None,
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"]
        ],
        show_progress="hidden"
    )

    # Generate Dialogues (💬)
    t3["btn_generate_dialogues"].click(
        fn=avvia_generazione_dialoghi,
        inputs=None,
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"], t3["output_comfy_vid_status"]
        ],
        show_progress="hidden"
    ).then(
        fn=lambda: avvia_cornici_video("timeline"),
        inputs=None,
        outputs=[t3["colonna_soggetto_video"], t3["colonna_top_timeline"],
                 t3["colonna_prompt_video_box"], t3["colonna_destra_video_player"]],
        show_progress="hidden"
    ).then(
        fn=director_ai.genera_dialoghi_timeline,
        inputs=[
            t3["tabella_regia_view"],
            t3["sceneggiatura_prompt"],
            t3["dropdown_model_video"],
            stato_generazione
        ],
        outputs=[t3["tabella_regia_view"], t3["output_comfy_vid_status"]],
        show_progress="hidden"
    ).then(
        fn=lambda timeline_txt, status: sessione.salva_sessione({"lista_scene_salvate": timeline_txt}) if str(status).startswith("✅") else None,
        inputs=[t3["tabella_regia_view"], t3["output_comfy_vid_status"]],
        outputs=None,
        show_progress="hidden"
    ).then(
        fn=imposta_classe_post_sceneggiatura,
        inputs=[t3["output_comfy_vid_status"]],
        outputs=[t3["colonna_top_timeline"]],
        show_progress="hidden"
    ).then(
        fn=ripristina_generazione_dialoghi,
        inputs=None,
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"]
        ],
        show_progress="hidden"
    )

    # Compile Direction (🧠)
    t3["btn_generate_video_prompt"].click(
        fn=avvia_compilazione_regia,
        inputs=None, 
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"], t3["output_comfy_vid_status"]
        ],
        show_progress="hidden"
    ).then(
        fn=lambda: avvia_cornici_video("prompt"),
        inputs=None,
        outputs=[t3["colonna_soggetto_video"], t3["colonna_top_timeline"],
                 t3["colonna_prompt_video_box"], t3["colonna_destra_video_player"]],
        show_progress="hidden"
    ).then(
        fn=compila_regia_sanitizzata,
        inputs=[
            t2["prompt_to_send_img"], t3["dropdown_model_video"], t3["tabella_regia_view"], 
            t3["audio_descrizione"], t3["video_durata_totale"], stato_generazione,
            t1["sys_prompt"], t1["dropdown_model"],
            t3["dropdown_sugg_director"],
            t3["solo_testo_video"], t3["output_prompt_video"], t3["sceneggiatura_prompt"]
        ],
        outputs=[t3["output_prompt_video"], t2["prompt_to_send_img"], t3["output_comfy_vid_status"]],
        show_progress="hidden"
    ).then(
        fn=lambda prompt_vid, prompt_img, status: sessione.salva_sessione({
            "output_prompt_video": prompt_vid,
            "prompt_to_send_img": prompt_img
        }) if str(status).startswith("✅") else None,
        inputs=[t3["output_prompt_video"], t2["prompt_to_send_img"], t3["output_comfy_vid_status"]],
        outputs=None,
        show_progress="hidden"
    ).then(
        fn=imposta_classe_post_compilazione_regia,
        inputs=[t3["output_comfy_vid_status"]],
        outputs=[t3["colonna_prompt_video_box"]],
        show_progress="hidden"
    ).then(
        fn=lambda: setattr(comfyui_manager, 'generazione_attiva', False),
        inputs=None, outputs=None,
        show_progress="hidden"
    ).then(
        fn=log.ottieni_tutti_i_log,
        inputs=None, outputs=t5["box_log_terminale"],
        show_progress="hidden"
    ).then(
        fn=ripristina_compilazione_regia,
        inputs=None, 
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"]
        ],
        show_progress="hidden"
    )

    # Generate Video (🎥)
    t3["btn_send_comfy_vid"].click(
        fn=avvia_blocco_generazione_video,  
        inputs=None, 
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"], t3["output_comfy_vid_status"]
        ]
    ).then(
        fn=lambda: avvia_cornici_video("video"),
        inputs=None,
        outputs=[t3["colonna_soggetto_video"], t3["colonna_top_timeline"],
                 t3["colonna_prompt_video_box"], t3["colonna_destra_video_player"]],
        show_progress="hidden"
    ).then(
        fn=gestisci_generazione_video_con_monitor,
        inputs=[
            num_lora_vid, t3["dropdown_model_video"], t3["output_prompt_video"],
            t3["lora_vid1_name"], t3["lora_vid1_str"], t3["lora_vid2_name"], t3["lora_vid2_str"],
            t3["lora_vid3_name"], t3["lora_vid3_str"], t3["tabella_regia_view"],
            t3["video_fps"], t3["video_durata_totale"], t3["video_rapporto"], t3["video_risoluzione"],
            t3["video_cfg"], t3["video_strength"], t3["video_compression"],
            t3["video_seed"], t3["video_seed_mode"],
            t2["seed_visualizzato"], stato_generazione, t3["audio_descrizione"],
            t3["immagine_sorgente_i2v"],
            t3["solo_testo_video"],
            t3["video_copies"],
            t3["dropdown_image_model_video"],
            t3["video_steps_vid"],
            t3["video_denoise_vid"],
            t3["video_scheduler_vid"]
        ],
        outputs=[t3["video_preview"], t3["output_comfy_vid_status"], t5["box_log_terminale"], stato_generazione]
    ).then(
        fn=stato_finale_video,
        inputs=[t3["output_comfy_vid_status"]],
        outputs=[t3["colonna_destra_video_player"]]
    ).then(
        fn=lambda s_sessione, stato_gen, solo_testo: gr.update(value=calcola_stato_spia_video(s_sessione, stato_gen, solo_testo)),
        inputs=[stato_sessione, stato_generazione, t3["solo_testo_video"]],
        outputs=[t3["spia_modalita_video"]]
    ).then(
        fn=ripristina_blocco_generazione_video,
        inputs=None, 
        outputs=[
            t3["btn_improve_subject"], t3["btn_generate_auto_timeline"],
            t3["btn_generate_dialogues"], t3["btn_generate_video_prompt"],
            t3["btn_send_comfy_vid"], t3["btn_extend_video"],
            t3["btn_save_video_prompt"]
        ]
    )

    t3["btn_extend_video"].click(
        fn=gestore_estensione_video,
        inputs=[t3["video_preview"], t3["immagine_sorgente_i2v"], stato_generazione],
        outputs=[
            t3["output_comfy_vid_status"],
            stato_generazione,
            t2["img_width"],
            t2["img_height"],
            t2["gallery_img"],
            t3["immagine_sorgente_i2v"],
            t3["spia_modalita_video"],
            t3["solo_testo_video"],
            t3["colonna_immagine_sorgente"],
            t3["storyboard_video_gallery"]
        ]
    )

    t3["solo_testo_video"].change(
        fn=lambda s_sessione, stato_gen, solo_testo: (
            gr.update(value=calcola_stato_spia_video(s_sessione, stato_gen, solo_testo)),
            gr.update(visible=not solo_testo)
        ),
        inputs=[stato_sessione, stato_generazione, t3["solo_testo_video"]],
        outputs=[t3["spia_modalita_video"], t3["colonna_immagine_sorgente"]]
    )

    def on_screenplay_preset_change(scelta, prompt_corrente, stato_gen):
        preset_testo, nuovo_stato = carica_suggerimento_sceneggiatura(scelta, prompt_corrente, stato_gen)
        sessione.salva_sessione({
            "suggerimento_sceneggiatura_selezionato": scelta,
            "sceneggiatura_prompt": preset_testo
        })
        return preset_testo, nuovo_stato

    t3["dropdown_sugg_screenplay"].change(
        fn=on_screenplay_preset_change,
        inputs=[t3["dropdown_sugg_screenplay"], t3["sceneggiatura_prompt"], stato_generazione],
        outputs=[t3["sceneggiatura_prompt"], stato_generazione]
    )

    for param in [t3["video_fps"], t3["video_rapporto"], t3["video_risoluzione"]]:
        param.change(
            fn=aggiorna_spia_su_cambio_parametro,
            inputs=[t3["video_fps"], t3["video_rapporto"], t3["video_risoluzione"], t3["solo_testo_video"], stato_generazione],
            outputs=[t3["spia_modalita_video"]]
        )

    t3["output_prompt_video"].input(
        fn=lambda: gr.update(elem_classes=["analisi-col-box"]), 
        inputs=None, 
        outputs=[t3["colonna_prompt_video_box"]]
    )
    t3["immagine_sorgente_i2v"].change(
        fn=lambda: gr.update(elem_classes=["analisi-col-box", "analisi-destra-box"]), 
        inputs=None, 
        outputs=[t3["colonna_destra_video_player"]]
    )

    t3["sceneggiatura_durata"].change(
        fn=salva_e_sincronizza_durata_sceneggiatura, 
        inputs=[t3["sceneggiatura_durata"], t3["tabella_regia_view"]],
        outputs=[t3["video_durata_totale"]]
    )
    t3["sceneggiatura_prompt"].change(
        fn=lambda v: sessione.salva_sessione({"sceneggiatura_prompt": v}), 
        inputs=[t3["sceneggiatura_prompt"]]
    )
    t3["audio_descrizione"].change(
        fn=lambda v: sessione.salva_sessione({"audio_descrizione": v}), 
        inputs=[t3["audio_descrizione"]]
    )
    t3["video_cfg"].change(
        fn=lambda v: sessione.salva_sessione({"video_cfg": v}), 
        inputs=[t3["video_cfg"]]
    )
    t3["video_strength"].change(
        fn=lambda v: sessione.salva_sessione({"video_strength": v}), 
        inputs=[t3["video_strength"]]
    )
    t3["video_compression"].change(
        fn=lambda v: sessione.salva_sessione({"video_compression": v}), 
        inputs=[t3["video_compression"]]
    )
    t3["video_seed"].change(
        fn=lambda v: sessione.salva_sessione({"video_seed": v}), 
        inputs=[t3["video_seed"]]
    )
    t3["video_seed_mode"].change(
        fn=lambda v: sessione.salva_sessione({"video_seed_mode": v}), 
        inputs=[t3["video_seed_mode"]]
    )
    t3["video_copies"].change(
        fn=lambda v: sessione.salva_sessione({"video_copies": v}), 
        inputs=[t3["video_copies"]]
    )
    
    t3["dropdown_model_video"].change(
        fn=lambda v: sessione.salva_sessione({"modello_vlm_video": v}), 
        inputs=[t3["dropdown_model_video"]]
    )
    t3["dropdown_image_model_video"].change(
        fn=gestisci_cambio_modello_video, 
        inputs=[t3["dropdown_image_model_video"]],
        outputs=[
            t3["row_params_ltx_1"],
            t3["row_params_ltx_2"],
            t3["row_params_minimax_1"],
            t3["row_params_minimax_2"],
            t3["lora_vid1_name"],
            t3["lora_vid2_name"],
            t3["lora_vid3_name"],
            t3["lora_vid1_str"],
            t3["lora_vid2_str"],
            t3["lora_vid3_str"],
            t3["video_fps"]
        ]
    )
    t3["dropdown_sugg_director"].change(
        fn=lambda v: sessione.salva_sessione({"suggerimento_regia_selezionato": v}), 
        inputs=[t3["dropdown_sugg_director"]]
    )
    
    t3["lora_vid1_name"].change(
        fn=lambda v, m: sessione.salva_sessione({("lora_video1_name_minimax" if m == "MiniMax H3" else "lora_video1_name"): v}), 
        inputs=[t3["lora_vid1_name"], t3["dropdown_image_model_video"]]
    )
    t3["lora_vid1_str"].change(
        fn=lambda v, m: sessione.salva_sessione({("lora_video1_str_minimax" if m == "MiniMax H3" else "lora_video1_str"): v}), 
        inputs=[t3["lora_vid1_str"], t3["dropdown_image_model_video"]]
    )
    t3["lora_vid2_name"].change(
        fn=lambda v, m: sessione.salva_sessione({("lora_video2_name_minimax" if m == "MiniMax H3" else "lora_video2_name"): v}), 
        inputs=[t3["lora_vid2_name"], t3["dropdown_image_model_video"]]
    )
    t3["lora_vid2_str"].change(
        fn=lambda v, m: sessione.salva_sessione({("lora_video2_str_minimax" if m == "MiniMax H3" else "lora_video2_str"): v}), 
        inputs=[t3["lora_vid2_str"], t3["dropdown_image_model_video"]]
    )
    t3["lora_vid3_name"].change(
        fn=lambda v, m: sessione.salva_sessione({("lora_video3_name_minimax" if m == "MiniMax H3" else "lora_video3_name"): v}), 
        inputs=[t3["lora_vid3_name"], t3["dropdown_image_model_video"]]
    )
    t3["lora_vid3_str"].change(
        fn=lambda v, m: sessione.salva_sessione({("lora_video3_str_minimax" if m == "MiniMax H3" else "lora_video3_str"): v}), 
        inputs=[t3["lora_vid3_str"], t3["dropdown_image_model_video"]]
    )
