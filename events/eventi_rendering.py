from events.lora_controls import bind_lora_controls
# events/eventi_rendering.py

import gradio as gr

from core import sessione, log, lingua, config
from services import prompt_manager, catalog_manager, comfyui_manager
from utils.media_utils import allinea_video_a_generata, carica_da_immagine_upload
from events.rendering_logic import (
    storyboard_pronto_per_taglio,
    gestisci_cambio_modello_immagine,
    gestisci_cambio_modalita,
    aggiorna_stato_visuale_seme,
    clicca_toggle_seme,
    svuota_vista_galleria,
    gestisci_trigger_galleria_html,
    avvia_blocco_generazione_immagine,
    gestisci_interruzione_immagine_sicura,
    gestisci_skip_immagine_sicura,
    avvia_affinamento_adattivo,
    avvia_generazione_immagine_con_normalizzazione,
    gestisci_aggiunta_lora_img,
    gestisci_rimozione_lora_img,
    gestisci_compilazione_testo_storyboard,
    avvia_taglio_storyboard_con_monitor,
    sincronizza_prompt_da_analisi,
    get_prompt_save_success_msg,
    imposta_classe_post_affinamento,
    imposta_classe_post_rendering,
    imposta_stato_successo_affinamento
)


def ricarica_prompt_salvati_rendering():
    prompts = ["-"] + (prompt_manager.elenca_prompt_salvati_img() if prompt_manager.elenca_prompt_salvati_img() else [])
    return gr.update(choices=prompts)


def ricarica_preset_sequenza():
    s_seq_list = config.elenca_suggerimenti(config.SUGGESTION_SEQUENCE_DIR)
    choices_sequence = ["-"] + (list(s_seq_list) if s_seq_list else [])
    return gr.update(choices=choices_sequence)


def ricarica_preset_storyboard():
    s_list = config.elenca_suggerimenti(config.SUGGESTION_STORYBOARD_DIR)
    choices_story = ["-"] + (list(s_list) if s_list else [])
    return gr.update(choices=choices_story)


def sblocca_stato_dopo_affinamento():
    """Garantisce lo sblocco del flag di generazione e riattiva i pulsanti dell'UI."""
    comfyui_manager.generazione_attiva = False
    return gr.update(interactive=True), gr.update(interactive=True)


def collega_rendering(t1, t2, t3, t5, num_lora_img, stato_generazione):
    
    affinamento_in_corso = gr.State(False)
    t2["generation_mode"].change(
        fn=lambda mode: (gr.update(visible="storyboard" not in str(mode).lower()),
                         gr.update(visible="storyboard" in str(mode).lower())),
        inputs=[t2["generation_mode"]],
        outputs=[t2["gallery_classic_slot"], t2["gallery_storyboard_slot"]],
        queue=False, show_progress="hidden"
    )
    
    for control in (t2["generation_mode"], t2["selettore_storyboard_pannelli"], t2["selettore_sequenza_scatti"]):
        control.change(
            fn=t2["adatta_azioni_a_modalita"],
            inputs=[t2["generation_mode"], t2["selettore_storyboard_pannelli"], t2["selettore_sequenza_scatti"], t2["num_azioni_seq"]],
            outputs=[t2["limite_azioni_catalogo"], t2["num_azioni_seq"], *[t2[f"dd_azione_{i}"] for i in range(2,6)]],
            queue=False, show_progress="hidden"
        )
    t2["generation_mode"].change(
        fn=lambda mode: gr.update(visible="sequenza" in str(mode).lower() or "sequence" in str(mode).lower()),
        inputs=[t2["generation_mode"]], outputs=[t2["selettore_sequenza_scatti"]], queue=False, show_progress="hidden"
    )

    t2["dropdown_saved_prompts"].focus(
        fn=ricarica_prompt_salvati_rendering,
        inputs=None,
        outputs=[t2["dropdown_saved_prompts"]]
    )

    t2["dropdown_sugg_sequenza"].focus(
        fn=ricarica_preset_sequenza,
        inputs=None,
        outputs=[t2["dropdown_sugg_sequenza"]]
    )

    t2["dropdown_sugg_storyboard"].focus(
        fn=ricarica_preset_storyboard,
        inputs=None,
        outputs=[t2["dropdown_sugg_storyboard"]]
    )

    def aggiorna_catalogo_da_preset_sequenza(preset_selezionato, s1, s2, s3, s4, s5):
        sessione.salva_sessione({"suggerimento_sequenza_selezionato": preset_selezionato})
        
        diz_char = catalog_manager.carica_catalogo("Personaggio", genere=preset_selezionato)
        diz_out = catalog_manager.carica_catalogo("Outfit/Location", genere=preset_selezionato)
        diz_act = catalog_manager.carica_catalogo("Azione", genere=preset_selezionato)
        
        dl = lingua.LINGUE.get(sessione.carica_ultima_sessione().get("lingua_selezionata", "IT"), lingua.LINGUE["IT"])
        label_nessuno = dl["nessuno_catalogo"]
        label_default = dl["default_preset_catalogo"]
        
        scelte_char = [label_nessuno] + list(diz_char.keys())
        scelte_out = [label_default] + list(diz_out.keys())
        scelte_act = [label_nessuno] + list(diz_act.keys())
        
        val_s1 = label_nessuno
        val_s2 = label_nessuno
        val_s3 = label_nessuno
        val_s4 = label_nessuno
        val_s5 = label_nessuno

        val_out = label_default
        val_act = label_nessuno
        
        return (
            gr.update(choices=scelte_char, value=val_s1),
            gr.update(choices=scelte_char, value=val_s2),
            gr.update(choices=scelte_char, value=val_s3),
            gr.update(choices=scelte_char, value=val_s4),
            gr.update(choices=scelte_char, value=val_s5),
            gr.update(choices=scelte_out, value=val_out),
            gr.update(choices=scelte_act, value=val_act),
            gr.update(choices=scelte_act, value=val_act),
            gr.update(choices=scelte_act, value=val_act),
            gr.update(choices=scelte_act, value=val_act),
            gr.update(choices=scelte_act, value=val_act)
        )

    t2["dropdown_sugg_sequenza"].change(
        fn=aggiorna_catalogo_da_preset_sequenza,
        inputs=[
            t2["dropdown_sugg_sequenza"],
            t2["dd_soggetto_1"],
            t2["dd_soggetto_2"],
            t2["dd_soggetto_3"],
            t2["dd_soggetto_4"],
            t2["dd_soggetto_5"]
        ],
        outputs=[
            t2["dd_soggetto_1"],
            t2["dd_soggetto_2"],
            t2["dd_soggetto_3"],
            t2["dd_soggetto_4"],
            t2["dd_soggetto_5"],
            t2["dd_outfit_location"],
            t2["dd_azione_1"],
            t2["dd_azione_2"],
            t2["dd_azione_3"],
            t2["dd_azione_4"],
            t2["dd_azione_5"]
        ]
    ).then(
        fn=t2["refresh_catalog_editor"], inputs=[t2["dd_tipo_salvataggio"]],
        outputs=[t2["dd_seleziona_esistente"], t2["txt_nome_catalogo"], t2["txt_desc_catalogo"]]
    )

    t2["dropdown_saved_prompts"].change(
        fn=prompt_manager.leggi_prompt_salvato_img,
        inputs=[t2["dropdown_saved_prompts"]],
        outputs=[t2["prompt_to_send_img"]]
    )

    t2["btn_skip_img"].click(
        fn=gestisci_skip_immagine_sicura,
        inputs=None,
        outputs=[t2["status_img"]]
    )

    t2["btn_interrupt_img"].click(
        fn=gestisci_interruzione_immagine_sicura,
        inputs=None,
        outputs=[t2["status_img"]]
    ).then(
        fn=lambda: (
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(elem_classes=["analisi-col-box"]),
            gr.update(elem_classes=["analisi-col-box"])
        ),
        inputs=None,
        outputs=[
            t2["btn_send_comfy_img"],
            t2["btn_refine"],
            t2["btn_genera_storyboard_ai"],
            t2["btn_clear_gallery"],
            t2["btn_load_from_image"],
            t2["btn_toggle_seed"],
            t2["colonna_sinistra_rendering"],
            t2["colonna_destra_rendering_box1"]
        ]
    )

    bind_lora_controls(
        t2["btn_add_lora_img"], t2["btn_rem_lora_img"], num_lora_img,
        [t2["row_lora_img2"], t2["row_lora_img3"]],
        [t2["lora2_name"], t2["lora2_str"], t2["lora3_name"], t2["lora3_str"]],
        gestisci_aggiunta_lora_img, gestisci_rimozione_lora_img, "lora-controls-image"
    )

    t2["btn_save_prompt"].click(
        fn=prompt_manager.salva_prompt_immagine_su_disco,
        inputs=[t2["prompt_to_send_img"], t1["dropdown_model"], stato_generazione],
        outputs=[t5["box_log_terminale"], t2["dropdown_saved_prompts"]]
    ).then(
        fn=get_prompt_save_success_msg,
        inputs=None,
        outputs=[t2["status_img"]]
    )

    t2["btn_refine"].click(
        fn=lambda: (
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"]), 
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"])  
        ),
        inputs=None,
        outputs=[t2["colonna_sinistra_rendering"], t2["colonna_destra_rendering_box1"]]
    ).then(
        fn=avvia_affinamento_adattivo,
        inputs=[t2["prompt_to_send_img"], t2["refine_instructions"], t1["dropdown_model"], t2["generation_mode"], t2["selettore_sequenza_scatti"], t2["dropdown_sugg_sequenza"]], 
        outputs=[t2["btn_refine"], t2["btn_send_comfy_img"], affinamento_in_corso, t2["prompt_to_send_img"], t2["refine_instructions"], t2["status_img"]]
    ).then(
        fn=imposta_classe_post_affinamento,
        inputs=[t2["status_img"]],
        outputs=[t2["colonna_sinistra_rendering"], t2["colonna_destra_rendering_box1"]]
    ).then(
        fn=sblocca_stato_dopo_affinamento,
        inputs=None,
        outputs=[t2["btn_send_comfy_img"], t2["btn_refine"]]
    )

    def reset_bordi_rendering_default():
        return (
            gr.update(elem_classes=["analisi-col-box"]),
            gr.update(elem_classes=["analisi-col-box"])
        )

    t2["btn_load_from_image"].upload(
        fn=carica_da_immagine_upload,
        inputs=[t2["btn_load_from_image"], stato_generazione],
        outputs=[
            t2["prompt_to_send_img"], t2["seed_visualizzato"], t2["gallery_img"], stato_generazione,
            t2["img_width"], t2["img_height"], t3["video_rapporto"], t3["video_risoluzione"],
            t2["img_seed_mode"], t2["img_seed"],
            t2["status_img"],
            t3["sceneggiatura_prompt"]
        ]
    ).then(
        fn=lambda stato_gen: stato_gen.get("percorso_immagine_selezionata") if stato_gen else None,
        inputs=[stato_generazione],
        outputs=[t3["immagine_sorgente_i2v"]]
    ).then(
        fn=lambda: (gr.update(value=False), gr.update(visible=True)),
        inputs=None,
        outputs=[t3["solo_testo_video"], t3["colonna_immagine_sorgente"]]
    ).then(
        fn=reset_bordi_rendering_default, 
        inputs=None, 
        outputs=[t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]]
    )

    def inibisci_compilazione_storyboard():
        s_attiva = sessione.carica_ultima_sessione()
        lang = s_attiva.get("lingua_selezionata", "IT")
        dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
        return gr.update(interactive=False), dl.get("storyboard_compiling", "⏳ Compilation Storyboard in corso...")

    def ripristina_compilazione_storyboard():
        return gr.update(interactive=True), gr.update()

    t2["btn_genera_storyboard_ai"].click(
        fn=lambda: (
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"]),
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"])
        ),
        inputs=None,
        outputs=[t2["colonna_sinistra_rendering"], t2["colonna_destra_rendering_box1"]]
    ).then(
        fn=inibisci_compilazione_storyboard,
        inputs=None,
        outputs=[t2["btn_genera_storyboard_ai"], t2["status_img"]]
    ).then(
        fn=gestisci_compilazione_testo_storyboard,
        inputs=[
            t2["prompt_to_send_img"],
            t1["dropdown_model"],
            t2["dropdown_sugg_storyboard"],
            t2["selettore_storyboard_pannelli"],
            stato_generazione
        ],
        outputs=[
            t2["prompt_to_send_img"],
            t3["tabella_regia_view"],
            t2["status_img"]
        ]
    ).then(
        fn=ripristina_compilazione_storyboard,
        inputs=None,
        outputs=[t2["btn_genera_storyboard_ai"], t2["status_img"]]
    ).then(
        fn=imposta_classe_post_rendering,
        inputs=[t2["status_img"]],
        outputs=[t2["colonna_sinistra_rendering"], t2["colonna_destra_rendering_box1"]]
    )

    # FASE 1: GENERA GRIGLIA STORYBOARD (CLICK PRINCIPALE)
    t2["btn_send_comfy_img"].click(
        fn=avvia_blocco_generazione_immagine,  
        inputs=None, 
        outputs=[
            t2["btn_send_comfy_img"],
            t2["btn_refine"],
            t2["btn_genera_storyboard_ai"],
            t2["btn_clear_gallery"], 
            t2["btn_load_from_image"], 
            t2["btn_toggle_seed"], 
            t2["status_img"],
            t2["btn_taglia_storyboard"]
        ],
        queue=False,
        show_progress="hidden"
    ).then(
        fn=lambda: (
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"]), 
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"])  
        ),
        inputs=None,
        outputs=[t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]]
    ).then(
        fn=avvia_generazione_immagine_con_normalizzazione,
        inputs=[
            num_lora_img, t1["dropdown_model"], t1["dropdown_sugg_vision"], t1["sys_prompt"], t1["user_hints"],
            t2["prompt_to_send_img"],
            t2["lora1_name"], t2["lora1_str"],
            t2["lora2_name"], t2["lora2_str"],
            t2["lora3_name"], t2["lora3_str"],
            t2["img_width"], t2["img_height"], t2["img_copies"],
            t2["steps_slider"], t2["sampler_dropdown"], t2["scheduler_dropdown"],
            t2["hires_steps_slider"], t2["hires_denoise_slider"], t2["hires_scale_slider"],
            stato_generazione,
            t2["dropdown_image_model"],
            t2["img_seed_mode"],
            t2["img_seed"],
            t2["generation_mode"],
            t2["dropdown_sugg_storyboard"],
            t2["selettore_storyboard_pannelli"],
            t2["attiva_refine_storyboard"],
            t2["refine_denoise"],
            t2["krea2_edit_grounding_px"],
            t2["selettore_sequenza_scatti"],
            t2["dropdown_sugg_sequenza"],
            t2["refine_instructions"],
            t2["krea2_edit_height"],
            t2["krea2_edit_lora_strength"]
        ],
        outputs=[
            t2["status_img"], 
            t2["gallery_img"], 
            t2["gallery_storyboard"], 
            t5["box_log_terminale"], 
            stato_generazione,
            t2["prompt_to_send_img"],
            t3["tabella_regia_view"]
        ]
    ).then(
        fn=imposta_classe_post_rendering,
        inputs=[t2["status_img"]],
        outputs=[t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]]
    ).then(
        fn=lambda gen_mode, st_gen: (
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=storyboard_pronto_per_taglio(gen_mode, st_gen))
        ),
        inputs=[t2["generation_mode"], stato_generazione],
        outputs=[
            t2["btn_send_comfy_img"], 
            t2["btn_refine"], 
            t2["btn_genera_storyboard_ai"],
            t2["btn_clear_gallery"],
            t2["btn_load_from_image"],
            t2["btn_toggle_seed"],
            t2["btn_taglia_storyboard"]
        ]
    )

    # FASE 2: TAGLIA PANNELLI STORYBOARD (CLICK PULSANTE DEDICATO)
    t2["btn_taglia_storyboard"].click(
        fn=lambda: (
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"]),
            gr.update(elem_classes=["analisi-col-box", "elaborazione-attiva"])
        ),
        inputs=None,
        outputs=[t2["btn_taglia_storyboard"], t2["btn_send_comfy_img"], t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]]
    ).then(
        fn=avvia_taglio_storyboard_con_monitor,
        inputs=[
            num_lora_img,
            t2["lora1_name"], t2["lora1_str"],
            t2["lora2_name"], t2["lora2_str"],
            t2["lora3_name"], t2["lora3_str"],
            t2["img_width"], t2["img_height"],
            t2["steps_slider"], t2["sampler_dropdown"], t2["scheduler_dropdown"],
            t2["hires_steps_slider"], t2["hires_denoise_slider"], t2["hires_scale_slider"],
            stato_generazione,
            t2["dropdown_image_model"],
            t2["selettore_storyboard_pannelli"],
            t2["attiva_refine_storyboard"],
            t2["refine_denoise"],
            t2["dropdown_sugg_storyboard"]
        ],
        outputs=[
            t2["status_img"],
            t2["gallery_storyboard"],
            t5["box_log_terminale"],
            stato_generazione,
            t2["prompt_to_send_img"],
            t3["sceneggiatura_prompt"]
        ]
    ).then(
        fn=allinea_video_a_generata,
        inputs=[stato_generazione],
        outputs=[
            t3["video_rapporto"], 
            t3["video_risoluzione"], 
            t3["immagine_sorgente_i2v"],
            t3["solo_testo_video"],
            t3["colonna_immagine_sorgente"],
            t3["storyboard_video_gallery"]
        ]
    ).then(
        fn=imposta_classe_post_rendering,
        inputs=[t2["status_img"]],
        outputs=[t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]]
    ).then(
        fn=lambda gen_mode, st_gen: (
            gr.update(interactive=storyboard_pronto_per_taglio(gen_mode, st_gen)),
            gr.update(interactive=True)
        ),
        inputs=[t2["generation_mode"], stato_generazione],
        outputs=[t2["btn_taglia_storyboard"], t2["btn_send_comfy_img"]]
    )

    def seleziona_frame_galleria(cmd, stato_gen):
        result = gestisci_trigger_galleria_html(cmd, stato_gen)
        selected = str(cmd).startswith(("SET_FIRST_", "SELECT_")) and bool(result[2].get("value"))
        seed = result[0].get("value") if isinstance(result[0], dict) else None
        return (*result,
                gr.update(value=seed if str(seed).isdigit() else "") if selected else gr.update(),
                gr.update(value=False) if selected else gr.update(),
                gr.update(visible=True) if selected else gr.update())

    t2["hidden_gallery_trigger"].change(
        fn=seleziona_frame_galleria,
        inputs=[t2["hidden_gallery_trigger"], stato_generazione],
        outputs=[
            t2["seed_visualizzato"],
            stato_generazione,
            t3["immagine_sorgente_i2v"],
            t2["gallery_img"],
            t2["gallery_storyboard"], 
            t2["img_seed_mode"],
            t2["img_seed"],
            t2["prompt_to_send_img"],
            t3["sceneggiatura_prompt"],
            t3["storyboard_video_gallery"],
            t3["video_seed"], t3["solo_testo_video"], t3["colonna_immagine_sorgente"]
        ],
        show_progress="hidden",
        trigger_mode="multiple",
        concurrency_id="gallery-selection",
        concurrency_limit=1
    )

    t2["dropdown_image_model"].change(
        fn=gestisci_cambio_modello_immagine,
        inputs=[t2["dropdown_image_model"], t2["generation_mode"]],
        outputs=[
            t2["steps_slider"],
            t2["sampler_dropdown"],
            t2["scheduler_dropdown"],
            t2["btn_add_lora_img"],
            t2["btn_rem_lora_img"],
            t2["row_lora_img2"],
            t2["row_lora_img3"],
            t2["hires_scale_slider"],
            t2["hires_steps_slider"],
            t2["hires_denoise_slider"],
            t2["lora1_name"],
            t2["lora1_str"],
            t2["lora2_name"],
            t2["lora2_str"],
            t2["lora3_name"],
            t2["lora3_str"]
        ]
    )

    def aggiorna_controlli_edit_specifici(model, mode):
        is_edit = "edit" in str(mode).lower() or "modifica" in str(mode).lower()
        visible = is_edit and model != "Qwen Image 2.1"
        return (*[gr.update(visible=visible) for _ in range(3)], gr.update(visible=not is_edit or model == "Qwen Image 2.1"))

    t2["dropdown_image_model"].change(
        fn=aggiorna_controlli_edit_specifici,
        inputs=[t2["dropdown_image_model"], t2["generation_mode"]],
        outputs=[t2["row_dim_edit"], t2["group_lora_edit"], t2["krea2_edit_grounding_px"], t2["group_lora_standard"]],
        show_progress="hidden"
    )

    t2["btn_clear_gallery"].click(
        fn=svuota_vista_galleria,
        inputs=[stato_generazione],
        outputs=[
            t2["gallery_img"],
            t2["gallery_storyboard"],
            t2["seed_visualizzato"],
            stato_generazione,
            t3["immagine_sorgente_i2v"],
            t2["status_img"] 
        ]
    )

    t2["btn_toggle_seed"].click(
        fn=clicca_toggle_seme,
        inputs=[t2["seed_visualizzato"], t2["img_seed_mode"], t2["img_seed"]],
        outputs=[
            t2["img_seed_mode"], t2["img_seed"], t2["status_img"] 
        ]
    )

    t2["img_seed_mode"].change(
        fn=aggiorna_stato_visuale_seme,
        inputs=[t2["img_seed_mode"]],
        outputs=[t2["btn_toggle_seed"], t2["accordion_ksampler"], t2["img_seed"]]
    )

    t2["generation_mode"].change(
        fn=gestisci_cambio_modalita,
        inputs=[t2["generation_mode"], t2["dropdown_image_model"]],
        outputs=[
            t2["box_storyboard"],
            t2["img_copies"],
            t2["btn_send_comfy_img"],
            t2["gallery_img"],
            t2["gallery_storyboard"],
            t2["dropdown_image_model"],
            t2["prompt_to_send_img"],
            t2["prompt_render_header"],
            t2["dropdown_saved_prompts"],
            t2["btn_save_prompt"],
            t2["colonna_impostazioni_avanzate"],
            t2["krea2_edit_grounding_px"],
            t2["refine_instructions"],
            t2["btn_refine"],
            t2["raffina_titolo_md"],
            t2["btn_load_from_image"],
            t2["steps_slider"],
            t2["sampler_dropdown"],
            t2["scheduler_dropdown"],
            t2["hires_steps_slider"],
            t2["hires_denoise_slider"],
            t2["hires_scale_slider"],
            t2["row_dim_generiche"],
            t2["row_dim_edit"],
            t2["group_lora_standard"],
            t2["group_lora_edit"],
            t2["btn_add_lora_img"],
            t2["btn_rem_lora_img"],
            t2["row_lora_img2"],
            t2["row_lora_img3"],
            t2["lora1_name"],
            t2["lora1_str"],
            t2["lora2_name"],
            t2["lora2_str"],
            t2["lora3_name"],
            t2["lora3_str"],
            t2["dropdown_sugg_storyboard"],
            t2["selettore_storyboard_pannelli"],
            t2["attiva_refine_storyboard"],
            t2["refine_denoise"],
            t2["row_sequenza_scatti"],
            t2["dropdown_sugg_sequenza"],
            t2["selettore_sequenza_scatti"],
            t2["box_catalogo_sequenza"]
        ]
    ).then(
        fn=sincronizza_prompt_da_analisi,
        inputs=[t2["generation_mode"], t1["output_prompt_img"], t2["prompt_to_send_img"]],
        outputs=[t2["prompt_to_send_img"]]
    ).then(
        fn=reset_bordi_rendering_default, 
        inputs=None, 
        outputs=[t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]]
    )

    t2["prompt_to_send_img"].change(fn=reset_bordi_rendering_default, inputs=None, outputs=[t2["colonna_destra_rendering_box1"], t2["colonna_sinistra_rendering"]])
