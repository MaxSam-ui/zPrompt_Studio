from utils.lora_ui import lora_row_classes
from ui.accordion_preferences import persistent_accordion
# ui/tab_video.py

import os
import gradio as gr
from typing import Dict, Any, List

from ui import style
from core import config, sessione, workflow_registry
from utils import media_utils, timeline
from services import prompt_manager
from utils.video_prompt_state import prompt_header
from ui.video_recovery import recovery_button, connect_recovery, create_recovery_control

def _normalizza_valore(valore, scelte):
    if valore in ["-", "Nessuno", "None", "nessuno", "none"]:
        return "-"
    if valore in scelte:
        return valore
    return "-"

def crea_tab_video(
    d: Dict[str, str],
    s: Dict[str, Any],
    lista_modelli_vlm: List[str],
    LORA_LTX: List[str],
    testo_iniziale_timeline: str,
) -> Dict[str, Any]:
    with gr.Tab(d.get("tab_video", "Video Generation")) as tab_el:

        # =====================================================================
        # 1. TIMELINE (FULL WIDTH TOP SECTION)
        # =====================================================================
        with gr.Column(elem_id="video-timeline", elem_classes=["analisi-col-box"]) as colonna_top_timeline:
            timeline_visuale = gr.HTML(
                value=timeline.compila_timeline_html(testo_iniziale_timeline),
                elem_id="timeline-visual-html"
            )
            
            tabella_regia_view = gr.Textbox(
                value=testo_iniziale_timeline,
                lines=5,
                max_lines=8,
                interactive=True,
                show_label=False,
                visible=True,
                elem_classes=["nascondi-textbox"],
                elem_id="tabella-regia-view-textbox"
            )
            
            with gr.Row(elem_classes=["studio-field-heading"]):
                gr.Markdown(d.get("modifica_clip_label", "Timeline"))
                recovery_timeline = recovery_button(tabella_regia_view, d)
            gr.Markdown(d["help_timeline_short"], elem_classes=["studio-usage-hint"])
            scena_sec = gr.State(value=3.0)

        # =====================================================================
        # 2. MAIN SPLIT COLUMNS
        # =====================================================================
        with gr.Row(elem_id="row-video", elem_classes=["studio-workspace"]):

            # -------------------- LEFT COLUMN ----------------------------
            with gr.Column(scale=1, min_width=340, elem_id="video-controls"):

                # ---- 1. CLIP MANAGER ----
                with gr.Column(elem_classes=["analisi-col-box"]) as colonna_modifica_clip_box:
                    with gr.Accordion(d.get("modifica_clip_label", "🎬 Timeline"), open=False) as accordion_modifica_clip:
                        with gr.Row():
                            scena_mov = gr.Textbox(
                                placeholder=d.get("placeholder_spezzone", "Describe what happens in the clip..."),
                                label=d.get("dettagli_spezzone", "Clip Details"),
                                lines=2
                            )
                            scena_audio = gr.Textbox(
                                placeholder=d.get("scena_audio_placeholder", "🔊 Clip sound effects..."),
                                label=d.get("scena_audio_label", "Clip Audio"),
                                lines=2,
                                elem_id="scena-audio-textbox"
                            )

                        with gr.Row():
                            default_shot = config.TIPI_INQUADRATURA[0] if config.TIPI_INQUADRATURA else "🧍 [Shot] Medium Shot"
                            default_motion = config.TIPI_ZOOM[0] if config.TIPI_ZOOM else "⏹️ [Static] Static (No Zoom)"

                            scena_tipo = gr.Dropdown(
                                choices=config.TIPI_INQUADRATURA,
                                value=default_shot,
                                label=d.get("inquadratura", "Shot Type")
                            )
                            scena_zoom = gr.Dropdown(
                                choices=config.TIPI_ZOOM,
                                value=default_motion,
                                label=d.get("movimento", "Camera Motion")
                            )

                        with gr.Row(elem_classes=["riga-pulsanti-timeline"]):
                            btn_add_timeline = gr.Button(d.get("btn_add_timeline", "Add Clip"), variant="secondary")
                            btn_remove_last_timeline = gr.Button(d.get("btn_rem_timeline", "Remove Last"), variant="secondary")
                            btn_clear_timeline = gr.Button(d.get("btn_clear_timeline", "Clear Timeline"), variant="stop")

                    with gr.Row(elem_classes=["riga-pulsanti-timeline"], visible=False) as riga_update_timeline:
                        btn_update_timeline = gr.Button(
                            d.get("btn_update_timeline_label", "🔄 Update"),
                            variant="primary",
                            visible=True
                        )
                        btn_cancel_timeline = gr.Button(
                            d.get("btn_cancel_timeline_label", "❌ Cancel"),
                            variant="secondary",
                            visible=True
                        )

                # ---- 2. AI AUTO-SCREENWRITER ----
                with gr.Column(elem_id="video-screenplay", elem_classes=["analisi-col-box"]):
                    gr.Markdown(d.get("sceneggiatore_ai_label", "✍️ Subject"), elem_classes=["studio-section-title"])

                    with gr.Row():
                        default_video_model = s.get("modello_vlm_video")
                        if not default_video_model or (lista_modelli_vlm and default_video_model not in lista_modelli_vlm):
                            default_video_model = lista_modelli_vlm[0] if lista_modelli_vlm else "-"

                        dropdown_model_video = gr.Dropdown(
                            choices=lista_modelli_vlm if lista_modelli_vlm else ["-"],
                            value=default_video_model,
                            label=d.get("modello_regista", "Director Model"),
                            allow_custom_value=True,
                            scale=1
                        )

                        sugg_screenplay = config.elenca_suggerimenti(config.SUGGESTION_SCREENPLAY_DIR)
                        choices_screenplay = ["-"] + (list(sugg_screenplay) if sugg_screenplay else [])
                        default_screen_preset = s.get("suggerimento_sceneggiatura_selezionato")
                        if not default_screen_preset or (choices_screenplay and default_screen_preset not in choices_screenplay):
                            default_screen_preset = "-"

                        dropdown_sugg_screenplay = gr.Dropdown(
                            choices=choices_screenplay,
                            value=default_screen_preset,
                            label=d.get("selettore_screenplay_label", "📋 Default Genre / Style"),
                            allow_custom_value=False,
                            scale=1
                        )

                        sceneggiatura_durata = gr.Slider(
                            minimum=1, maximum=30,
                            value=min(30, max(1, float(s.get("sceneggiatura_durata") or 12))),
                            step=1,
                            label=d.get("sceneggiatura_durata_label", "Duration (seconds)"),
                            scale=1
                        )

                    prompt_screen_avvio = config.leggi_contenuto_suggerimento(
                        config.SUGGESTION_SCREENPLAY_DIR, default_screen_preset
                    )
                    sceneggiatura_prompt_value = s.get("sceneggiatura_prompt", "") or ""
                    if not sceneggiatura_prompt_value.strip():
                        sceneggiatura_prompt_value = prompt_screen_avvio if prompt_screen_avvio else ""

                    with gr.Row(elem_classes=['studio-field-heading']):
                        gr.Markdown(d.get("sceneggiatura_prompt_label", "Movie Idea or Subject"))
                        subject_restore = create_recovery_control(d)
                    gr.Markdown(d["help_subject_short"], elem_classes=["studio-usage-hint"])
                    sceneggiatura_prompt = gr.Textbox(
                        value=sceneggiatura_prompt_value,
                        placeholder=d.get("sceneggiatura_prompt_placeholder", "e.g., Create a western duel..."),
                        label=d.get("sceneggiatura_prompt_label", "Movie Idea or Subject"),
                        show_label=False,
                        lines=3
                    )
                    recovery_subject = recovery_button(sceneggiatura_prompt, d, button=subject_restore)

                    with gr.Row():
                        btn_improve_subject = gr.Button(
                            d.get("btn_improve_subject", "🪄 Create / Enhance Subject"),
                            variant="secondary"
                        )
                        btn_generate_auto_timeline = gr.Button(
                            d.get("btn_genera_auto_timeline_label", "🎬 Write Timeline"),
                            variant="secondary"
                        )
                        btn_generate_dialogues = gr.Button(
                            d.get("btn_generate_dialogues", "💬 Generate Dialogues"),
                            variant="secondary"
                        )

                with gr.Column(elem_id="video-directing", elem_classes=["analisi-col-box"]):
                    gr.Markdown(d.get("regia_film_label", "🧠 Video Prompt Setup"), elem_classes=["studio-section-title"])

                    with gr.Row():
                        sugg_director = config.elenca_suggerimenti(config.SUGGESTION_DIRECTION_DIR)
                        choices_director = ["-"] + (list(sugg_director) if sugg_director else [])
                        default_dir_preset = s.get("suggerimento_regia_selezionato")
                        if not default_dir_preset or (choices_director and default_dir_preset not in choices_director):
                            default_dir_preset = "-"

                        dropdown_sugg_director = gr.Dropdown(
                            choices=choices_director,
                            value=default_dir_preset,
                            label=d.get("selettore_director_label", "🎬 Director Style (Preset)"),
                            allow_custom_value=True,
                            scale=1
                        )

                    audio_descrizione = gr.Textbox(
                        value=s.get("audio_descrizione", ""),
                        placeholder=d.get("audio_descrizione_placeholder", "Describe the background music and ambient sounds..."),
                        label=d.get("audio_descrizione_label", "Global Atmospheric Sound"),
                        lines=2
                    )

                    btn_generate_video_prompt = gr.Button(
                        d.get("btn_compila_regia", "🧠 Create Video Prompt"),
                        variant="primary"
                    )

                # ---- 3. CINEMATIC PROMPT ---- 
                with gr.Column(elem_id="video-prompt-panel", elem_classes=["analisi-col-box"]) as colonna_prompt_video_box:
                    with gr.Row(elem_classes=["studio-field-heading"]):
                        prompt_cinema_header = gr.Markdown(prompt_header(s, testo_iniziale_timeline, s.get("output_prompt_video", ""), s.get("audio_descrizione", ""), d), elem_classes=["studio-section-title"])
                        prompt_restore = create_recovery_control(d)

                    gr.Markdown(d["help_video_prompt_short"], elem_classes=["studio-usage-hint"])
                    prompts_video_salvati = ["-"] + (
                        prompt_manager.elenca_prompt_salvati_vid()
                        if prompt_manager.elenca_prompt_salvati_vid()
                        else []
                    )
                    dropdown_saved_video_prompts = gr.Dropdown(
                        choices=prompts_video_salvati,
                        value="-",
                        label=d.get("carica_prompt", "Load Prompt"),
                        allow_custom_value=False
                    )

                    output_prompt_video = gr.Textbox(
                        value=s.get("output_prompt_video", ""),
                        lines=6,
                        max_lines=10,
                        interactive=True,
                        show_label=False
                    )

                    recovery_prompt = recovery_button(output_prompt_video, d, button=prompt_restore)
                    connect_recovery([btn_improve_subject, btn_generate_auto_timeline, btn_generate_video_prompt],
                                     [recovery_subject, recovery_timeline, recovery_prompt])

                    btn_send_comfy_vid = gr.Button(
                        d.get("btn_genera_video", "Generate Video"),
                        variant="primary",
                        interactive=False
                    )

            # -------------------- RIGHT COLUMN ----------------------------
            with gr.Column(scale=1, min_width=340, elem_id="video-results"):

                # ---- 1. MONITOR & PLAYER ---- 
                with gr.Column(elem_classes=["analisi-col-box", "analisi-destra-box"]) as colonna_destra_video_player:

                    with gr.Accordion(
                        d.get("monitor_player", "Player"),
                        open=True,
                        elem_id="accordion-player-flat"
                    ) as monitor_player_header:

                        with gr.Row():
                            solo_testo_video = gr.Checkbox(
                                label=d.get("solo_testo_video_label", "Text only / T2V (No Image)"),
                                value=s.get("solo_testo_video_attivo", False),
                                scale=1
                            )
                            spia_modalita_video = gr.HTML(
                                value=media_utils.calcola_stato_spia_video(s, None, s.get("solo_testo_video_attivo", False)),
                                elem_id="spia-modalita-video"
                            )

                        frames_sub = media_utils.calcola_frames_tab_video(stato_gen=None, s_sessione=s)
                        is_storyboard = "storyboard" in str(s.get("generation_mode", "")).lower()
                        storyboard_video_gallery_init = media_utils.compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)

                        with gr.Column(elem_id="video-media"):
                            with gr.Row(
                                visible=not s.get("solo_testo_video_attivo", False),
                                elem_id="video-reference-frames"
                            ) as colonna_immagine_sorgente:
                                immagine_sorgente_i2v = gr.Image(
                                    value=s.get("percorso_immagine_selezionata", None),
                                    type="filepath",
                                    sources=["upload"],
                                    label=d.get("immagine_sorgente_i2v_label", "🖼 Frame 1 (Initial)"),
                                    height=240,
                                    min_width=160,
                                    scale=1,
                                    elem_id="immagine-sorgente-i2v"
                                )
                                storyboard_video_gallery = gr.HTML(
                                    value=storyboard_video_gallery_init,
                                    elem_id="storyboard-video-gallery-html",
                                    min_width=160,
                                    scale=1
                                )
                            video_preview = gr.Video(
                                autoplay=True,
                                sources=["upload"],
                                height=320,
                                show_label=False,
                                elem_id="video-preview-player"
                            )
                        hidden_video_gallery_trigger = gr.Textbox(
                            visible=True,
                            elem_classes=["nascondi-textbox"],
                            elem_id="hidden-video-gallery-trigger"
                        )

                        with gr.Row():
                            btn_save_video_prompt = gr.Button(
                                d.get("btn_salva_prompt", "Save Prompt"),
                                variant="secondary",
                                scale=2
                            )
                            btn_extend_video = gr.Button(
                                d.get("btn_estendi_video", "Extend Video"),
                                variant="secondary",
                                scale=2
                            )


                # ---- 2. ADVANCED SETTINGS ----
                    output_comfy_vid_status, btn_interrupt_vid = style.crea_barra_stato_unificata(
                        d.get("in_attesa", "Waiting..."),
                        "tasto-stop-vid"
                    )

                with gr.Column(elem_classes=["analisi-col-box"]):
                    impostazioni_box_video_md = gr.Markdown(d.get("impostazioni_box_titolo", "Advanced Settings"))

                    with persistent_accordion('impostazioni_output_accordion', s, 
                        d.get("formato_frame_rate_label", "📐 Format & Frame-Rate"),
                        open=False
                    ) as impostazioni_output_accordion:
                        with gr.Group():
                            with gr.Row():
                                default_vid_gen_model = s.get("modello_video_attivo", "LTX-Video 2.5")
                                choices_vid_gen_models = workflow_registry.elenca_modelli_video()
                                if not default_vid_gen_model or default_vid_gen_model not in choices_vid_gen_models:
                                    default_vid_gen_model = choices_vid_gen_models[0] if choices_vid_gen_models else "LTX-Video 2.5"

                                dropdown_image_model_video = gr.Dropdown(
                                    choices=choices_vid_gen_models,
                                    value=default_vid_gen_model,
                                    label=d.get("modello_video_generazione_label", "🎬 Video Generation Model"),
                                    allow_custom_value=False,
                                    scale=1
                                )
                                is_minimax = default_vid_gen_model == "MiniMax H3"
                                video_fps = gr.Dropdown(
                                    choices=["24"] if is_minimax else ["16", "24", "30", "60"],
                                    value="24" if is_minimax else s.get("video_fps", "24"),
                                    interactive=not is_minimax,
                                    label=d.get("fps_label", "Frame-rate (FPS)"),
                                    scale=1
                                )
                                video_rapporto = gr.Dropdown(
                                    choices=["16:9", "9:16", "4:3", "3:4", "1:1"],
                                    value=s.get("video_rapporto", "16:9"),
                                    label=d.get("rapporto_label", "Aspect ratio"),
                                    allow_custom_value=False,
                                    scale=1
                                )
                                video_risoluzione = gr.Dropdown(
                                    choices=["256p", "360p", "480p", "720p", "1080p"],
                                    value=s.get("video_risoluzione", "480p"),
                                    label=d.get("risoluzione_label", "Resolution"),
                                    allow_custom_value=False,
                                    scale=1
                                )
                                video_durata_totale = gr.State(value=4.0)
                            with gr.Row():
                                video_copies = gr.Slider(
                                    minimum=1, maximum=10,
                                    value=s.get("video_copies", 1),
                                    step=1,
                                    label=d.get("video_copies_label", "Number of videos"),
                                    info=d.get("video_copies_info", "How many videos to generate with this prompt."),
                                    scale=1
                                )

                    with persistent_accordion('accordion_parametri_vid', s, 
                        d.get("parameters_label", "🔮 Generation Parameters"),
                        open=False
                    ) as accordion_parametri_vid:
                        with gr.Group():
                            is_minimax = default_vid_gen_model == "MiniMax H3"
                            
                            # CONTROLLI SPECIFICI LTX
                            with gr.Row(visible=not is_minimax) as row_params_ltx_1:
                                video_cfg = gr.Slider(
                                    minimum=1.0, maximum=10.0,
                                    value=1.0,
                                    interactive=False,
                                    step=0.1,
                                    label=d.get("video_cfg_label", "CFG (Guidance Scale)")
                                )
                                video_strength = gr.Slider(
                                    minimum=0.0, maximum=1.0,
                                    value=s.get("video_strength", 0.90),
                                    step=0.05,
                                    label=d.get("video_strength_label", "Strength")
                                )
                            with gr.Row(visible=not is_minimax) as row_params_ltx_2:
                                video_compression = gr.Slider(
                                    minimum=0, maximum=50,
                                    value=s.get("video_compression", 15),
                                    step=1,
                                    label=d.get("video_compression_label", "Compression")
                                )

                            # CONTROLLI SPECIFICI MINIMAX H3 SINGULARITY (DUAL-CLOCK T8)
                            with gr.Row(visible=is_minimax) as row_params_minimax_1:
                                video_steps_vid = gr.Slider(
                                    minimum=1, maximum=20,
                                    value=s.get("video_steps_minimax", 8),
                                    step=1,
                                    label=d.get("steps_label", "Steps")
                                )
                                video_denoise_vid = gr.Slider(
                                    minimum=0.05, maximum=1.0,
                                    value=1.0, interactive=False, visible=False,
                                    step=0.05,
                                    label="Denoise"
                                )
                            with gr.Column(visible=is_minimax) as row_params_minimax_2:
                                minimax_reference_note = gr.Markdown(d.get("minimax_reference_note", ""))
                                with gr.Row():
                                    turbo_profile = gr.Dropdown(
                                        choices=["Attuale / Current", "V4 - 6 steps", "V4 - 8 steps"],
                                        value=s.get("minimax_turbo_profile", "V4 - 8 steps"),
                                        label=d.get("minimax_turbo_label", "Turbo Profile"),
                                        info=d.get("minimax_turbo_info", "Sampling Profile")
                                    )
                                    video_scheduler_vid = gr.Dropdown(
                                        choices=["beta", "simple", "normal", "sgm_uniform", "karras", "exponential", "native_flow", "beta57"],
                                        value=s.get("video_scheduler_minimax", "beta"),
                                        label=d.get("scheduler_label", "Scheduler")
                                    )

                            # CONTROLLI COMUNI (SEED)
                            with gr.Row():
                                video_seed_mode = gr.Dropdown(
                                    choices=["randomize", "fixed"],
                                    value=s.get("video_seed_mode", "randomize"),
                                    label=d.get("video_seed_mode_label", "Seed Mode")
                                )
                                video_seed = gr.Textbox(
                                    value=s.get("video_seed", ""),
                                    placeholder=d.get("video_seed_placeholder", "Seed..."),
                                    label=d.get("video_seed_label", "Video Seed")
                                )

                    with persistent_accordion('accordion_lora_vid', s, 
                        d.get("gestione_lora_video_label", "🎛️ Video LoRA Management"),
                        open=False
                    ) as accordion_lora_vid:
                        with gr.Column(min_width=0, elem_classes=["studio-lora-stack"]):
                            scelte_lora_vid_init = workflow_registry.ottieni_lora_disponibili_video(default_vid_gen_model)
                            
                            if is_minimax:
                                lora_vid1_val = _normalizza_valore(s.get("lora_video1_name_minimax", "-"), scelte_lora_vid_init)
                                lora_vid2_val = _normalizza_valore(s.get("lora_video2_name_minimax", "-"), scelte_lora_vid_init)
                                lora_vid3_val = _normalizza_valore(s.get("lora_video3_name_minimax", "-"), scelte_lora_vid_init)
                            else:
                                lora_vid1_val = _normalizza_valore(s.get("lora_video1_name", "-"), scelte_lora_vid_init)
                                lora_vid2_val = _normalizza_valore(s.get("lora_video2_name", "-"), scelte_lora_vid_init)
                                lora_vid3_val = _normalizza_valore(s.get("lora_video3_name", "-"), scelte_lora_vid_init)

                            label_forza = d.get("forza_lora", "Strength")

                            with gr.Row(elem_classes=["studio-lora-row"]) as row_lora_vid1:
                                lora_vid1_name = gr.Dropdown(
                                    choices=scelte_lora_vid_init,
                                    value=lora_vid1_val,
                                    label="LoRA 1"
                                )
                                lora_vid1_str = gr.Slider(
                                    minimum=0.0, maximum=1.5,
                                    value=s.get("lora_video1_str" if not is_minimax else "lora_video1_str_minimax", 1.0),
                                    step=0.05,
                                    label=f"{label_forza} 1"
                                )
                            with gr.Row(elem_classes=lora_row_classes(s.get("lora_video_visibili_count", 1) >= 2)) as row_lora_vid2:
                                lora_vid2_name = gr.Dropdown(
                                    choices=scelte_lora_vid_init,
                                    value=lora_vid2_val,
                                    label="LoRA 2"
                                )
                                lora_vid2_str = gr.Slider(
                                    minimum=0.0, maximum=1.5,
                                    value=s.get("lora_video2_str" if not is_minimax else "lora_video2_str_minimax", 1.0),
                                    step=0.05,
                                    label=f"{label_forza} 2"
                                )
                            with gr.Row(elem_classes=lora_row_classes(s.get("lora_video_visibili_count", 1) == 3)) as row_lora_vid3:
                                lora_vid3_name = gr.Dropdown(
                                    choices=scelte_lora_vid_init,
                                    value=lora_vid3_val,
                                    label="LoRA 3"
                                )
                                lora_vid3_str = gr.Slider(
                                    minimum=0.0, maximum=1.5,
                                    value=s.get("lora_video3_str" if not is_minimax else "lora_video3_str_minimax", 1.0),
                                    step=0.05,
                                    label=f"{label_forza} 3"
                                )
                            with gr.Row(elem_classes=["studio-lora-actions"]):
                                btn_add_lora_vid = gr.Button(
                                    d.get("btn_add_lora", "Add LoRA"),
                                    size="sm",
                                    variant="secondary",
                                    scale=1
                                )
                                btn_rem_lora_vid = gr.Button(
                                    d.get("btn_rem_lora", "Remove LoRA"),
                                    size="sm",
                                    variant="secondary",
                                    scale=1
                                )

        # =====================================================================
        # 3. HIDDEN TRIGGER ELEMENTS
        # =====================================================================
        selettore_blocco_edit = gr.Textbox(visible=True, elem_classes=["nascondi-textbox"])
        hidden_timeline_trigger = gr.Textbox(visible=True, elem_classes=["nascondi-textbox"], elem_id="hidden-timeline-trigger")
        durata_drag_trigger = gr.Textbox(visible=True, elem_classes=["nascondi-textbox"], elem_id="durata-drag-trigger")

        return {
            "tab_el": tab_el,
            "dropdown_image_model_video": dropdown_image_model_video,
            "video_fps": video_fps,
            "video_durata_totale": video_durata_totale,
            "video_rapporto": video_rapporto,
            "video_risoluzione": video_risoluzione,
            "impostazioni_output_accordion": impostazioni_output_accordion,
            "accordion_parametri_vid": accordion_parametri_vid,
            "accordion_lora_vid": accordion_lora_vid,
            "btn_add_lora_vid": btn_add_lora_vid,
            "btn_rem_lora_vid": btn_rem_lora_vid,
            "row_lora_vid1": row_lora_vid1,
            "row_lora_vid2": row_lora_vid2,
            "row_lora_vid3": row_lora_vid3,
            
            "lora_vid1_name": lora_vid1_name,
            "lora_vid1_str": lora_vid1_str,
            "lora_vid2_name": lora_vid2_name,
            "lora_vid2_str": lora_vid2_str,
            "lora_vid3_name": lora_vid3_name,
            "lora_vid3_str": lora_vid3_str,

            "lora_video1_name": lora_vid1_name,
            "lora_video1_str": lora_vid1_str,
            "lora_video2_name": lora_vid2_name,
            "lora_video2_str": lora_vid2_str,
            "lora_video3_name": lora_vid3_name,
            "lora_video3_str": lora_vid3_str,

            "row_params_ltx_1": row_params_ltx_1,
            "row_params_ltx_2": row_params_ltx_2,
            "row_params_minimax_1": row_params_minimax_1,
            "row_params_minimax_2": row_params_minimax_2,
            "minimax_reference_note": minimax_reference_note,
            "video_steps_vid": video_steps_vid,
            "turbo_profile": turbo_profile,
            "video_denoise_vid": video_denoise_vid,
            "video_scheduler_vid": video_scheduler_vid,

            "colonna_immagine_sorgente": colonna_immagine_sorgente,

            "dropdown_model_video": dropdown_model_video,
            "scena_sec": scena_sec,
            "scena_tipo": scena_tipo,
            "scena_zoom": scena_zoom,
            "scena_mov": scena_mov,
            "scena_audio": scena_audio,
            "audio_descrizione": audio_descrizione,
            "video_cfg": video_cfg,
            "video_strength": video_strength,
            "video_compression": video_compression,
            "video_seed": video_seed,
            "video_seed_mode": video_seed_mode,
            "btn_add_timeline": btn_add_timeline,
            "btn_remove_last_timeline": btn_remove_last_timeline,
            "btn_clear_timeline": btn_clear_timeline,
            "tabella_regia_view": tabella_regia_view,
            "timeline_visuale": timeline_visuale,
            "btn_generate_video_prompt": btn_generate_video_prompt,
            "prompt_cinema_header": prompt_cinema_header,
            "output_prompt_video": output_prompt_video,
            "btn_send_comfy_vid": btn_send_comfy_vid,
            "monitor_player_header": monitor_player_header,
            "output_comfy_vid_status": output_comfy_vid_status,
            "btn_interrupt_vid": btn_interrupt_vid,
            "video_preview": video_preview,
            "dropdown_saved_video_prompts": dropdown_saved_video_prompts,
            "btn_save_video_prompt": btn_save_video_prompt,
            "btn_extend_video": btn_extend_video,
            "immagine_sorgente_i2v": immagine_sorgente_i2v,
            "selettore_blocco_edit": selettore_blocco_edit,
            "accordion_modifica_clip": accordion_modifica_clip,
            "riga_update_timeline": riga_update_timeline,
            "btn_update_timeline": btn_update_timeline,
            "hidden_timeline_trigger": hidden_timeline_trigger,
            "btn_cancel_timeline": btn_cancel_timeline,
            "sceneggiatura_prompt": sceneggiatura_prompt,
            "sceneggiatura_durata": sceneggiatura_durata,
            "btn_generate_auto_timeline": btn_generate_auto_timeline,
            "btn_improve_subject": btn_improve_subject,
            "btn_generate_dialogues": btn_generate_dialogues,
            "dropdown_sugg_screenplay": dropdown_sugg_screenplay,
            "dropdown_sugg_director": dropdown_sugg_director,
            "solo_testo_video": solo_testo_video,
            "video_copies": video_copies,
            "storyboard_video_gallery": storyboard_video_gallery,
            "hidden_video_gallery_trigger": hidden_video_gallery_trigger,
            "spia_modalita_video": spia_modalita_video,
            "colonna_top_timeline": colonna_top_timeline,
            "colonna_prompt_video_box": colonna_prompt_video_box,
            "colonna_destra_video_player": colonna_destra_video_player,
            "durata_drag_trigger": durata_drag_trigger
        }
