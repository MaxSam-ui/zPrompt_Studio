# core/lingua.py

import os
import json
import gradio as gr

import core.config as config
import core.sessione as sessione
import core.log as log

FOLDER_LANGUAGES = os.path.join(config.STUDIO_ROOT_DIR, "languages")

LINGUE = {}

def generation_mode_choices(d):
    """Translate display labels while preserving the values used by workflows."""
    return [(d.get(key, value), value) for key, value in (
        ("gen_mode_classic_label", "Classica (1 Immagine)"),
        ("gen_mode_storyboard_label", "Storyboard"),
        ("gen_mode_sequence_label", "Sequenza Immagini AI"),
        ("gen_mode_edit_label", "Modifica Immagine (Edit)"),
    )]

def _appiattisci_dizionario(d_in: dict) -> dict:
    """Ricorsivamente appiattisce un dizionario nidificato mantenendo le chiavi foglia."""
    items = {}
    for k, v in d_in.items():
        if isinstance(v, dict):
            items.update(_appiattisci_dizionario(v))
        else:
            items[k] = v
    return items


def carica_lingue_da_disco():
    """Scansiona la cartella languages/ e carica tutti i file .json presenti in RAM, appiattendoli."""
    global LINGUE
    LINGUE.clear()
    
    if not os.path.exists(FOLDER_LANGUAGES):
        try:
            os.makedirs(FOLDER_LANGUAGES, exist_ok=True)
            log.registra(f"Created languages directory in: {FOLDER_LANGUAGES}")
        except Exception as e:
            log.registra(f"Failed to create languages folder: {e}", "WARNING")
            return
    
    for file_name in os.listdir(FOLDER_LANGUAGES):
        if file_name.endswith(".json"):
            lang_key = os.path.splitext(file_name)[0].upper()  
            file_path = os.path.join(FOLDER_LANGUAGES, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    d_grezzo = json.load(f)
                    LINGUE[lang_key] = _appiattisci_dizionario(d_grezzo)
            except Exception as e:
                log.registra(f"Error loading language file {file_name}: {e}", "WARNING")

    if not LINGUE:
        log.registra("Languages directory empty or unreadable. Using minimum safety dictionaries.", "WARNING")
        LINGUE["IT"] = {"titolo": "zPrompt Studio", "nessuno": "Nessuno"}
        LINGUE["EN"] = {"titolo": "zPrompt Studio", "nessuno": "None"}


carica_lingue_da_disco()


def ottieni_dizionario_lingua(lang_code: str) -> dict:
    """Restituisce il dizionario della lingua con fallback automatico a cascata."""
    if not lang_code or not isinstance(lang_code, str):
        s_reale = sessione.carica_ultima_sessione()
        lang_code = s_reale.get("lingua_selezionata", "IT")

    d_base = LINGUE.get("IT", LINGUE.get("EN", {}))
    d_target = LINGUE.get(lang_code, {})

    return {**d_base, **d_target}


def traduce_tab_log(lang=None):
    d = ottieni_dizionario_lingua(lang)
    return [
        gr.update(value=f"# {d.get('titolo', 'zPrompt Studio')}"),
        gr.update(value=d.get("registri_sistema_header", "System Logs")),
        gr.update(value=d.get("btn_refresh_logs", "Refresh Logs")),
        gr.update(value=d.get("btn_clear_logs", "Clear Logs")),
        gr.update(label=d.get("box_log_terminale", "Console Logs")),
        gr.update(label=d.get("diagnostica_titolo", "🔍 Model Diagnostics & Status"))
    ]


def traduce_tab_analisi(is_solo_testo=None):
    s_reale = sessione.carica_ultima_sessione()
    lang = s_reale.get("lingua_selezionata", "IT")
    d = ottieni_dizionario_lingua(lang)
    solo_attivo = s_reale.get("solo_testo_attivo", False) if is_solo_testo is None else bool(is_solo_testo)
    btn_label_t1 = d.get("btn_genera_prompt_testo", "Generate Prompt") if solo_attivo else d.get("btn_analizza", "Analyze")

    return [
        gr.update(value=btn_label_t1),
        gr.update(value=d.get("risultato_analisi", "Result")),
        gr.update(label=d.get("modello_vision", "Vision Model"), info=d.get("modello_vision_info", "")),
        gr.update(label=d.get("preset_vision", "Vision Preset"), info=d.get("preset_vision_info", "")),
        gr.update(label=d.get("prompt_sistema", "System Prompt")),
        gr.update(label=d.get("istruzioni_extra", "Extra Instructions"), placeholder=d.get("placeholder_hints", "")),
        gr.update(value=d.get("llama_vision_titolo", "Vision")),
        gr.update(label=d.get("prompt_generato_label", "Prompt")),
        gr.update(label=d.get("solo_testo_checkbox_label", "Text only")),
        gr.update(label=d.get("vlm_max_tokens_label", "Max Prompt Tokens")),
        gr.update(placeholder=d.get("in_attesa", "Waiting..."))
    ]


def traduce_tab_rendering():
    s_reale = sessione.carica_ultima_sessione()
    lang = s_reale.get("lingua_selezionata", "IT")
    d = ottieni_dizionario_lingua(lang)

    mode_str = str(s_reale.get("generation_mode", "")).lower()
    is_edit_mode = "edit" in mode_str or "modifica" in mode_str
    is_seq_mode = "sequenza" in mode_str
    is_story_mode = "storyboard" in mode_str

    if is_edit_mode:
        btn_send_label = d.get("btn_genera_edit", "🎨 Apply Edit")
    elif is_seq_mode:
        btn_send_label = "📸 Genera Sequenza AI"
    elif is_story_mode:
        btn_send_label = d.get("btn_genera_griglia_storyboard", d.get("btn_genera_storyboard", "🎨 Genera Griglia Storyboard"))
    else:
        btn_send_label = d.get("btn_genera_img", "Generate Image")

    title_refine = d.get("edit_title", "🪄 Image Edit with AI") if is_edit_mode else d.get("raffina_titolo", "🪄 Refine Description with AI")
    label_refine = d.get("edit_instructions_label", "What do you want to change in the image?") if is_edit_mode else d.get("raffina_istruzioni_label", "Instructions")
    placeholder_refine = d.get("edit_placeholder", "e.g., Make the woman blonde...") if is_edit_mode else d.get("raffina_placeholder", "")
    label_forza = d.get("forza_lora", "Strength")
    txt_carica_img = d.get("source_edit_label", "Source Edit") if is_edit_mode else d.get("btn_carica_da_immagine", "Load from Image")

    lbl_sog1 = d.get("dd_soggetto_1_label", "Subject 1")
    lbl_sog2 = d.get("dd_soggetto_2_label", "Subject 2")
    lbl_sog3 = d.get("dd_soggetto_3_label", "Subject 3")
    lbl_sog4 = d.get("dd_soggetto_4_label", "Subject 4")
    lbl_sog5 = d.get("dd_soggetto_5_label", "Subject 5")

    return [
        gr.update(value=d.get("prompt_render_label", "✍️ Prompt to Send to ComfyUI")),
        gr.update(value=btn_send_label),
        gr.update(value=d.get("btn_salva_prompt", "Save Prompt")),
        gr.update(label=d.get("carica_prompt_salvato_label", "Load Saved Prompt")),
        gr.update(label=d.get("steps_label", "Steps")),
        gr.update(label=d.get("sampler_label", "Sampler")),
        gr.update(label=d.get("scheduler_label", "Scheduler")),
        gr.update(label=d.get("larghezza", "Width")),
        gr.update(label=d.get("altezza", "Height")),
        gr.update(label=d.get("batch_size", "Number of images"), info=d.get("batch_size_info", "How many images to generate with this prompt.")),
        gr.update(label=d.get("gestione_lora", "LoRA Management")),
        gr.update(label=d.get("impostazioni_ksampler", "KSampler Settings")),
        gr.update(label=d.get("dimensioni_copie", "Size and Copies")),
        gr.update(label=d.get("stato_galleria", "Gallery Status")),
        gr.update(value=title_refine),
        gr.update(label=label_refine, placeholder=placeholder_refine),
        gr.update(value=d.get("btn_optimize_instruction", "🪄 Optimize Instruction AI") if is_edit_mode else d.get("btn_raffina", "🪄 Refine Description")),
        gr.update(value=d.get("impostazioni_box_titolo", "Advanced Settings")),
        gr.update(label=txt_carica_img),
        gr.update(label=d.get("seed_visualizzato_label", "Used Seed")),
        gr.update(placeholder=d.get("in_attesa", "Waiting...")),
        gr.update(label=f"{label_forza} 1"),
        gr.update(label=f"{label_forza} 2"),
        gr.update(label=f"{label_forza} 3"),
        gr.update(label="Hi-Res Steps"),
        gr.update(label="Denoise"),
        gr.update(label=d.get("hires_scale_label", "Upscale Factor")),
        gr.update(label=d.get("modello_immagine_label", "🎨 Image Model")),
        gr.update(label=d.get("modalita_generazione_label", "🎬 Generation Mode"), choices=generation_mode_choices(d)),
        gr.update(label=d.get("preset_storyboard_label", "📋 Storyboard Direction Preset")),
        gr.update(label=d.get("numero_fotogrammi_label", "Number of Frames")),
        gr.update(label=d.get("box_catalogo_sequenza_label", "🎭 Cast & Scene Catalog")),
        gr.update(label=lbl_sog1),
        gr.update(label=lbl_sog2),
        gr.update(label=lbl_sog3),
        gr.update(label=lbl_sog4),
        gr.update(label=lbl_sog5),
        gr.update(value=d.get("btn_add_soggetto", "➕ Add Subject")),
        gr.update(value=d.get("btn_rem_soggetto", "➖ Remove Subject")),
        gr.update(label=d.get("dd_outfit_location_label", "Outfit & Location")),
        gr.update(value=d.get("btn_assembla_da_catalogo", "🪄 Assemble Idea from Catalog")),
        gr.update(value=d.get("btn_estrai_vlm_label", "🧠 Extract Assets")),
        gr.update(value=d.get("btn_save_ext_char_label", "💾 Save Character")),
        gr.update(value=d.get("btn_save_ext_outfit_label", "💾 Save Outfit")),
        gr.update(value=d.get("btn_save_ext_act_label", "💾 Save Action")),
        gr.update(label=d.get("dd_tipo_salvataggio_label", "Element Type")),
        gr.update(label=d.get("dd_seleziona_esistente_label", "Select Element to Edit")),
        gr.update(value=d.get("btn_salva_catalogo", "💾 Save Catalog")),
        gr.update(value=d.get("btn_elimina_catalogo", "🗑️ Delete Element")),
        gr.update(label=d.get("grounding_resolution_label", "🎯 Grounding Resolution"), info=d.get("grounding_resolution_info", "")),
        gr.update(label=d.get("processing_height_label", "Processing Height")),
        gr.update(label=d.get("seed_mode_label", "Seed Mode")),
        gr.update(label=d.get("image_seed_label", "Image Seed"), placeholder=d.get("seed_placeholder", "")),
        gr.update(label=d.get("identity_preservation_label", "Identity Preservation Strength")),
        gr.update(value=d.get("btn_add_lora", "Add LoRA")),
        gr.update(value=d.get("btn_rem_lora", "Remove LoRA")),
        gr.update(label=d["presets_sequence_label"]),
        gr.update(label=d.get("num_sequence_shots_label", "Number of Sequence Shots (2-5)")),
        gr.update(label=d.get("raffina_fotogrammi_label", "Refine frames (Refine Img2Img)")),
        gr.update(label=d.get("refine_denoise_label", "Refine Strength (Denoise)")),
        gr.update(value=d.get("btn_compila_storyboard_ai", "📖 Compile Storyboard AI"))
    ]


def traduce_tab_video():
    s_reale = sessione.carica_ultima_sessione()
    lang = s_reale.get("lingua_selezionata", "IT")
    d = ottieni_dizionario_lingua(lang)

    from utils.media_utils import calcola_stato_spia_video, compila_striscia_video_html, calcola_frames_tab_video
    from utils import timeline
    from utils.video_prompt_state import prompt_header

    html_spia = str(calcola_stato_spia_video(s_reale, None, s_reale.get("solo_testo_video_attivo", False)) or "")

    scena_salvata = s_reale.get("lista_scene_salvate", [])
    html_timeline = timeline.compila_timeline_html(scena_salvata)

    frames_sub = calcola_frames_tab_video(stato_gen=None, s_sessione=s_reale)
    is_storyboard = "storyboard" in str(s_reale.get("generation_mode", "")).lower()
    html_storyboard = compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)

    return [
        gr.update(value=d.get("btn_add_timeline", "Add Clip")),
        gr.update(value=d.get("btn_rem_timeline", "Remove Last")),
        gr.update(value=d.get("btn_clear_timeline", "Clear Timeline")),
        gr.update(value=d.get("btn_compila_regia", "Compile AI Direction")),
        gr.update(value=prompt_header(
            s_reale, scena_salvata, s_reale.get("output_prompt_video", ""),
            s_reale.get("audio_descrizione", ""), d)),
        gr.update(value=d.get("btn_genera_video", "Generate Video")),
        gr.update(label=d.get("monitor_player", "Player")),
        gr.update(label=d.get("modello_regista", "Director Model")),
        gr.update(label=d.get("inquadratura", "Shot Type")),
        gr.update(label=d.get("movimento", "Camera Motion")),
        gr.update(label=d.get("dettagli_spezzone", "Clip Details"), placeholder=d.get("placeholder_spezzone", "")),
        gr.update(label=d.get("gestione_lora_video_label", "🎛️ Video LoRA Management")),
        gr.update(label=d.get("formato_frame_rate_label", "📐 Format & Frame-Rate")),
        gr.update(label=d.get("fps_label", "Frame-rate (FPS)")),
        gr.update(label=d.get("rapporto_label", "Aspect Ratio")),
        gr.update(label=d.get("risoluzione_label", "Resolution")),
        gr.update(label=d.get("audio_descrizione_label", "Global Atmospheric Sound"), placeholder=d.get("audio_descrizione_placeholder", "")),
        gr.update(placeholder=d.get("in_attesa", "Waiting...")),
        gr.update(label=d.get("carica_prompt", "Load Prompt")),
        gr.update(value=d.get("btn_salva_prompt", "Save Prompt")),
        gr.update(value=d.get("btn_estendi_video", "Extend Video")),
        gr.update(label=d.get("selettore_blocco_edit_label", "✏️ Select Clip to Edit")),
        gr.update(value=d.get("btn_update_timeline_label", "🔄 Update")),
        gr.update(value=d.get("btn_cancel_timeline_label", "❌ Cancel")),
        gr.update(label=d.get("scena_audio_label", "Clip Audio"), placeholder=d.get("scena_audio_placeholder", "")),
        gr.update(label=d.get("video_strength_label", "Strength")),
        gr.update(label=d.get("video_compression_label", "Compression")),
        gr.update(label=d.get("video_seed_label", "Video Seed"), placeholder=d.get("video_seed_placeholder", "")),
        gr.update(label=d.get("selettore_director_label", "🎬 Director Style (Preset)")),
        gr.update(label=d.get("selettore_screenplay_label", "📋 Default Genre / Style")),
        gr.update(label=d.get("parameters_label", "🔮 Generation Parameters")),
        gr.update(value=html_spia),
        gr.update(value=d.get("btn_improve_subject", "🪄 Create / Enhance Subject")),
        gr.update(value=d.get("btn_generate_dialogues", "💬 Generate Dialogues")),
        gr.update(label=d.get("modifica_clip_label", "🎬 Clip Manager")),
        gr.update(label=d.get("sceneggiatura_prompt_label", "Movie Idea or Subject"), placeholder=d.get("sceneggiatura_prompt_placeholder", "")),
        gr.update(label=d.get("sceneggiatura_durata_label", "Duration (seconds)")),
        gr.update(value=d.get("btn_genera_auto_timeline_label", "🎬 Write Timeline")),
        gr.update(label=d.get("solo_testo_video_label", "Text only / T2V")),
        gr.update(label=d.get("video_copies_label", "Number of videos"), info=d.get("video_copies_info", "How many videos to generate with this prompt.")),
        gr.update(label=d.get("video_cfg_label", "CFG Scale")),
        gr.update(label=d.get("video_seed_mode_label", "Seed Mode")),
        gr.update(value=html_timeline),
        gr.update(value=html_storyboard)
    ]


def traduce_tab_batch():
    s_reale = sessione.carica_ultima_sessione()
    lang = s_reale.get("lingua_selezionata", "IT")
    d = ottieni_dizionario_lingua(lang)
    label_forza = d.get("forza_lora", "Strength")

    return [
        gr.update(label=d.get("carica_immagini_batch", "Load Batch Images")),
        gr.update(label=d.get("modello_vision", "Vision Model")),
        gr.update(label=d.get("prompt_sistema", "System Prompt")),
        gr.update(label=d.get("istruzioni_extra", "Extra Instructions"), placeholder=d.get("placeholder_hints", "")),
        gr.update(value=d.get("btn_avvia_batch", "Start Batch")),
        gr.update(label=d.get("stato_galleria", "Gallery Status")),
        gr.update(placeholder=d.get("in_attesa", "Waiting...")),
        gr.update(label=d.get("gestione_lora", "LoRA Management")),
        gr.update(label=d.get("dimensioni_copie", "Size and Copies")),
        gr.update(label=d.get("prompt_generato_batch_label", "📝 Current Generated Prompt")),
        gr.update(label=f"{label_forza} 1"),
        gr.update(label=f"{label_forza} 2"),
        gr.update(label=f"{label_forza} 3"),
        gr.update(label="Hi-Res Steps"),
        gr.update(label="Denoise"),
        gr.update(label=d.get("hires_scale_label", "Upscale Factor")),
        gr.update(label=d.get("batch_mode_label", "📁 Batch Mode")),
        gr.update(label=d.get("modello_immagine_label", "🎨 Image Model")),
        gr.update(label=d.get("preset_vision", "Vision Preset"), info=d.get("preset_vision_info", "")),
        gr.update(label=d.get("impostazioni_ksampler", "KSampler Settings")),
        gr.update(label=d.get("sampler_label", "Sampler")),
        gr.update(label=d.get("scheduler_label", "Scheduler")),
        gr.update(label=d.get("steps_label", "Steps")),
        gr.update(label=d.get("larghezza", "Width")),
        gr.update(label=d.get("altezza", "Height")),
        gr.update(label=d.get("batch_size", "Number of images"), info=d.get("batch_size_info", "How many images to generate with this prompt.")),
        gr.update(value=d.get("btn_add_lora", "Add LoRA")),
        gr.update(value=d.get("btn_rem_lora", "Remove LoRA"))
    ]


def traduce_interfaccia_globale(lang):
    """Esegue la traduzione simultanea e istantanea di TUTTI i tab dell'applicazione."""
    if not lang or not isinstance(lang, str):
        s_reale = sessione.carica_ultima_sessione()
        lang = s_reale.get("lingua_selezionata", "IT")

    carica_lingue_da_disco()
    sessione.salva_sessione({"lingua_selezionata": lang})
    log.registra(f"Language globally changed to {lang}. Translating entire UI instantly...")

    return (
        traduce_tab_log(lang) +
        traduce_tab_analisi() +
        traduce_tab_rendering() +
        traduce_tab_video() +
        traduce_tab_batch()
    )
