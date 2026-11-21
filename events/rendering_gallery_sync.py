# events/rendering_gallery_sync.py

import os
import shutil
import random
import gradio as gr
from utils.gallery_commands import deletion_index, remove_gallery_references

from core import sessione, log, lingua, config
from services import comfyui_manager
from utils.media_utils import (
    compila_galleria_html,
    compila_striscia_video_html,
    depura_nome_file_infinito,
    norm_path_sicuro,
    calcola_frames_tab_video,
    recupera_soggetto_scena,
    pulisci_lista_percorsi_galleria
)


MAX_GALLERY_HTML_DISPLAY = 100


def aggiorna_stato_visuale_seme(mode):
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    title_base = dl.get("impostazioni_ksampler", "KSampler Settings")
    if mode == "fixed":
        return gr.update(value="🔒"), gr.update(label=f"🎛️ {title_base} (fixed-seed)"), gr.update()
    sessione.salva_sessione({"img_seed": ""})
    return gr.update(value="🔓"), gr.update(label=f"🎛️ {title_base} (random)"), gr.update(value="")


def clicca_toggle_seme(seed_rilevato, mode_attuale, seed_target):
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    if mode_attuale == "randomize":
        seme_scelto = seed_rilevato if (seed_rilevato and seed_rilevato.isdigit()) else ""
        sessione.salva_sessione({"img_seed_mode": "fixed", "img_seed": seme_scelto})
        msg_lock = dl.get("seed_locked", "🔒 Seed locked in FIXED mode!")
        return gr.update(value="fixed"), gr.update(value=seme_scelto), msg_lock
    else:
        sessione.salva_sessione({"img_seed_mode": "randomize", "img_seed": ""})
        msg_unlock = dl.get("seed_unlocked", "🔓 Seed unlocked in RANDOM mode!")
        return gr.update(value="randomize"), gr.update(value=None), msg_unlock


def svuota_vista_galleria(stato_gen):
    if stato_gen is None:
        stato_gen = {}
    
    stato_gen["immagini_generate_cumulate"] = []
    stato_gen["lista_frame_storyboard_attivi"] = []
    stato_gen["seed_attuali_cumulati"] = []
    stato_gen["seed_attuali"] = []
    stato_gen["percorso_immagine_selezionata"] = None
    stato_gen["percorso_immagine_destinazione"] = None
    stato_gen["gallery_no_sync"] = True
    
    sessione.salva_sessione({
        "immagini_generate_cumulate": [],
        "lista_frame_storyboard_attivi": [],
        "seed_attuali_cumulati": [],
        "percorso_immagine_selezionata": None,
        "percorso_immagine_destinazione": None
    })
    
    nuovo_html = compila_galleria_html([], percorso_selezionato=None, percorso_destinazione=None)
    
    subjects_dir = os.path.join(config.STUDIO_OUTPUT_DIR, "subjects")
    if os.path.exists(subjects_dir):
        try:
            shutil.rmtree(subjects_dir)
            os.makedirs(subjects_dir, exist_ok=True)
        except Exception:
            pass
            
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    msg_clear = dl.get("gallery_cleared", "🧹 Gallery history cleared!")
    
    log.registra("Gallery: Cleared visual session history (classic and storyboard) and subjects archive.")
    return (
        gr.update(value=nuovo_html), 
        gr.update(value=nuovo_html), 
        gr.update(value=""),         
        stato_gen,                   
        gr.update(value=None),       
        msg_clear                    
    )


def svuota_vista_galleria_batch(stato_gen):
    if stato_gen is None:
        stato_gen = {}
    
    stato_gen["immagini_generate_batch"] = []
    stato_gen["percorso_immagine_selezionata"] = None
    stato_gen["percorso_immagine_destinazione"] = None
    
    sessione.salva_sessione({
        "immagini_generate_batch": [],
        "percorso_immagine_selezionata": None,
        "percorso_immagine_destinazione": None
    })
    
    nuovo_html = compila_galleria_html([], percorso_selezionato=None, percorso_destinazione=None)
    
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    msg_clear = dl.get("gallery_cleared", "🧹 Gallery history cleared!")
    label_base = dl.get("stato_galleria", "Gallery Status")
    
    log.registra("Batch Gallery: Cleared history of batch generated images.")
    return (
        stato_gen,
        gr.update(value=nuovo_html),
        msg_clear,
        gr.update(value=""),
        gr.update(label=f"{label_base} (0)")
    )


def gestisci_trigger_galleria_html(cmd, stato_gen):
    if not cmd or not cmd.strip() or stato_gen is None:
        return (
            gr.update(), stato_gen, gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        )

    s_sessione = sessione.carica_ultima_sessione()
    lang = s_sessione.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    generation_mode = s_sessione.get("generation_mode", "Classica (1 Immagine)")
    prompt_corrente = s_sessione.get("prompt_to_send_img", "")
    is_storyboard = "storyboard" in str(generation_mode).lower()

    if is_storyboard:
        immagini_generate = stato_gen.get("lista_frame_storyboard_attivi", [])
    else:
        immagini_generate = stato_gen.get("immagini_generate_cumulate", []) or stato_gen.get("lista_frame_storyboard_attivi", [])

    seed_attuali_cumulati = stato_gen.get("seed_attuali_cumulati", [])
    seed_attuali_singoli = stato_gen.get("seed_attuali", [])

    if cmd.startswith("SET_LAST_"):
        try:
            parti = cmd.split("_")
            idx = int(parti[2])
            if 0 <= idx < len(immagini_generate):
                percorso_cliccato = immagini_generate[idx]
                current_l = stato_gen.get("percorso_immagine_destinazione") or s_sessione.get("percorso_immagine_destinazione")
                
                if current_l and norm_path_sicuro(current_l) == norm_path_sicuro(percorso_cliccato):
                    stato_gen["percorso_immagine_destinazione"] = None
                    sessione.salva_sessione({"percorso_immagine_destinazione": None})
                    target_l = None
                    log.registra(f"Gallery: Toggled OFF Last Frame [L] idx {idx}: '{percorso_cliccato}'")
                else:
                    stato_gen["percorso_immagine_destinazione"] = percorso_cliccato
                    sessione.salva_sessione({"percorso_immagine_destinazione": percorso_cliccato})
                    target_l = percorso_cliccato
                    log.registra(f"Gallery: Set Last Frame [L] idx {idx}: '{percorso_cliccato}'")

                target_f = stato_gen.get("percorso_immagine_selezionata") or s_sessione.get("percorso_immagine_selezionata")
                img_i2v_update = gr.update()
                if target_l and target_f and norm_path_sicuro(target_f) == norm_path_sicuro(target_l):
                    target_f = None
                    stato_gen["percorso_immagine_selezionata"] = None
                    sessione.salva_sessione({"percorso_immagine_selezionata": None})
                    img_i2v_update = gr.update(value=None)

                s_aggiornata = sessione.carica_ultima_sessione()
                frames_sub = calcola_frames_tab_video(stato_gen, s_aggiornata)
                html_video_strip = compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)

                return (
                    gr.update(),
                    stato_gen,
                    img_i2v_update,
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(value=html_video_strip)
                )
        except Exception as e:
            log.registra(f"Error setting last frame: {e}", "WARNING")
            return (
                gr.update(), stato_gen, gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
            )

    if cmd.startswith("SELECT_") or cmd.startswith("SET_FIRST_"):
        try:
            parti = cmd.split("_")
            idx = int(parti[2] if cmd.startswith("SET_FIRST_") else parti[1])
            if 0 <= idx < len(immagini_generate):
                percorso_cliccato = immagini_generate[idx]
                stato_gen["percorso_immagine_selezionata"] = percorso_cliccato
                stato_gen["gallery_no_sync"] = True
                
                target_l = stato_gen.get("percorso_immagine_destinazione") or s_sessione.get("percorso_immagine_destinazione")
                if target_l and norm_path_sicuro(target_l) == norm_path_sicuro(percorso_cliccato):
                    target_l = None
                    stato_gen["percorso_immagine_destinazione"] = None
                    sessione.salva_sessione({"percorso_immagine_destinazione": None})

                seed_scelto = "Seed not available" if lang == "EN" else "Seed non disponibile"
                if idx < len(seed_attuali_cumulati) and seed_attuali_cumulati[idx] is not None:
                    seed_scelto = str(seed_attuali_cumulati[idx])
                elif idx < len(seed_attuali_singoli) and seed_attuali_singoli[idx] is not None:
                    seed_scelto = str(seed_attuali_singoli[idx])

                log.registra(f"Selected Frame 1 [F] idx {idx}: '{percorso_cliccato}' (Last Frame: '{target_l}')")

                prompt_scelto = None
                
                try:
                    from generators.metadata_extractor import estrai_info_da_immagine
                    from PIL import Image
                    with Image.open(percorso_cliccato) as im:
                        prompt_metadata, seed_metadata = estrai_info_da_immagine(im)
                        if prompt_metadata and prompt_metadata.strip():
                            prompt_scelto = prompt_metadata.strip()
                            if seed_metadata is not None:
                                seed_scelto = str(seed_metadata)
                                if stato_gen.get("seed_attuali_cumulati") and idx < len(stato_gen["seed_attuali_cumulati"]):
                                    stato_gen["seed_attuali_cumulati"][idx] = seed_metadata
                                if stato_gen.get("seed_attuali") and idx < len(stato_gen["seed_attuali"]):
                                    stato_gen["seed_attuali"][idx] = seed_metadata
                            log.registra(f"Prompt and Seed successfully loaded from PNG metadata: {percorso_cliccato}")
                except Exception as e:
                    log.registra(f"Error reading PNG metadata: {e}", "WARNING")

                if prompt_scelto is None:
                    txt_adiacente = os.path.splitext(percorso_cliccato)[0] + ".txt"
                    if os.path.exists(txt_adiacente):
                        try:
                            with open(txt_adiacente, "r", encoding="utf-8") as f_txt:
                                prompt_scelto = f_txt.read().strip()
                                log.registra(f"Prompt loaded from adjacent batch txt file: {txt_adiacente}")
                        except Exception as e:
                            log.registra(f"Error reading associated prompt txt: {e}", "WARNING")

                prompt_valido = prompt_scelto if prompt_scelto else prompt_corrente
                soggetto_scelto = ""
                if prompt_valido and "edit" not in str(generation_mode).lower() and "modifica" not in str(generation_mode).lower():
                    soggetto_scelto = recupera_soggetto_scena(prompt_valido)

                if prompt_scelto is None:
                    prompt_scelto = prompt_corrente
                    log.registra("No metadata found for selected image. Kept current prompt.", "WARNING")
                else:
                    sessione.salva_sessione({"prompt_to_send_img": prompt_scelto})

                if soggetto_scelto and soggetto_scelto.strip():
                    sessione.salva_sessione({"sceneggiatura_prompt": soggetto_scelto})

                base_name = os.path.splitext(os.path.basename(percorso_cliccato))[0]
                base_name_pulito = depura_nome_file_infinito(base_name)

                sessione.salva_sessione({
                    "percorso_immagine_selezionata": percorso_cliccato,
                    "nome_immagine_sorgente": base_name_pulito
                })

                is_num = seed_scelto.isdigit()
                
                s_aggiornata = sessione.carica_ultima_sessione()
                frames_sub = calcola_frames_tab_video(stato_gen, s_aggiornata)
                html_video_strip = compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)

                return (
                    gr.update(value=seed_scelto),
                    stato_gen,
                    gr.update(value=percorso_cliccato),
                    gr.update() if is_storyboard else gr.update(value=compila_galleria_html(immagini_generate, percorso_selezionato=percorso_cliccato)),
                    gr.update(value=compila_galleria_html(immagini_generate, percorso_selezionato=percorso_cliccato)) if is_storyboard else gr.update(),
                    gr.update(value="fixed" if is_num else "randomize"),
                    gr.update(value=seed_scelto if is_num else ""),
                    gr.update(value=prompt_scelto),
                    gr.update(value=soggetto_scelto) if soggetto_scelto and soggetto_scelto.strip() else gr.update(),
                    gr.update(value=html_video_strip)
                )
        except Exception as e:
            log.registra(f"Error during trigger selection: {e}", "WARNING")

    elif cmd.startswith("DELETE_"):
        if comfyui_manager.generazione_attiva or comfyui_manager.batch_attivo:
            msg_warning = dl.get("err_cannot_delete_during_generation", "⚠️ Generation in progress. Cannot delete elements from the gallery now.")
            gr.Warning(msg_warning)
            return (
                gr.update(), stato_gen, gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
            )

        try:
            idx = deletion_index(cmd, immagini_generate)
            if 0 <= idx < len(immagini_generate):
                percorso_elimina = immagini_generate[idx]
                if percorso_elimina and os.path.exists(percorso_elimina):
                    try:
                        os.remove(percorso_elimina)
                        log.registra(f"File physically removed via trigger: '{percorso_elimina}'")
                        txt_adiacente = os.path.splitext(percorso_elimina)[0] + ".txt"
                        if os.path.exists(txt_adiacente):
                            os.remove(txt_adiacente)
                    except Exception as e:
                        log.registra(f"Unable to remove file during trigger command: {e}", "WARNING")
                
                remove_gallery_references(immagini_generate, idx, seed_attuali_cumulati, seed_attuali_singoli)
                stato_gen["seed_attuali_cumulati"] = seed_attuali_cumulati
                stato_gen["seed_attuali"] = seed_attuali_singoli

                immagini_visibili = immagini_generate[-MAX_GALLERY_HTML_DISPLAY:] if len(immagini_generate) > MAX_GALLERY_HTML_DISPLAY else immagini_generate

                s_reale = sessione.carica_ultima_sessione()
                percorso_sel_corrente = stato_gen.get("percorso_immagine_selezionata") or s_reale.get("percorso_immagine_selezionata")
                if percorso_sel_corrente == percorso_elimina:
                    percorso_sel_corrente = None
                    stato_gen["percorso_immagine_selezionata"] = None
                    sessione.salva_sessione({"percorso_immagine_selezionata": None})

                percorso_dest_corrente = stato_gen.get("percorso_immagine_destinazione") or s_reale.get("percorso_immagine_destinazione")
                if percorso_dest_corrente == percorso_elimina:
                    percorso_dest_corrente = None
                    stato_gen["percorso_immagine_destinazione"] = None
                    sessione.salva_sessione({"percorso_immagine_destinazione": None})

                html_sincronizzato = compila_galleria_html(
                    immagini_visibili,
                    percorso_selezionato=percorso_sel_corrente,
                    percorso_destinazione=percorso_dest_corrente
                )

                if is_storyboard:
                    stato_gen["lista_frame_storyboard_attivi"] = immagini_generate
                    sessione.salva_sessione({"lista_frame_storyboard_attivi": immagini_generate})
                    gallery_img_up = gr.update()
                    gallery_story_up = gr.update(value=html_sincronizzato)
                else:
                    stato_gen["immagini_generate_cumulate"] = immagini_generate
                    sessione.salva_sessione({"immagini_generate_cumulate": immagini_generate})
                    gallery_img_up = gr.update(value=html_sincronizzato)
                    gallery_story_up = gr.update()

                stato_gen["gallery_no_sync"] = True

                s_aggiornata = sessione.carica_ultima_sessione()
                frames_sub = calcola_frames_tab_video(stato_gen, s_aggiornata)
                html_video_strip = compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)

                return (
                    gr.update(),                    
                    stato_gen,                      
                    gr.update(value=percorso_sel_corrente), 
                    gallery_img_up,                 
                    gallery_story_up,               
                    gr.update(),                    
                    gr.update(),                    
                    gr.update(),                    
                    gr.update(),                    
                    gr.update(value=html_video_strip)
                )
        except Exception as e:
            log.registra(f"Error during trigger deletion: {e}", "WARNING")

    return (
        gr.update(), stato_gen, gr.update(), gr.update(), gr.update(),
        gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    )


def gestisci_trigger_galleria_video_html(cmd, stato_gen):
    """Gestisce la rimozione immediata al 1° click dei frame dalla striscia video."""
    if not cmd or not cmd.strip() or stato_gen is None:
        return stato_gen, gr.update(), gr.update()

    s_sessione = sessione.carica_ultima_sessione()
    gen_mode = str(s_sessione.get("generation_mode", "")).lower()
    is_storyboard = "storyboard" in gen_mode

    if cmd.startswith("REMOVE_"):
        try:
            parti = cmd.split("_")
            idx = int(parti[1])
            if is_storyboard:
                frames_story = stato_gen.get("lista_frame_storyboard_attivi", [])
                idx_reale = idx + 1
                if 0 <= idx_reale < len(frames_story):
                    rimosso = frames_story.pop(idx_reale)
                    stato_gen["lista_frame_storyboard_attivi"] = frames_story
                    sessione.salva_sessione({"lista_frame_storyboard_attivi": frames_story})
                    log.registra(f"Tab Video: Removed panel {idx_reale+1} from storyboard (file preserved on disk: '{rimosso}')")
            else:
                log.registra("Tab Video: Removed Last Frame from video sequence (file preserved on disk)")
                stato_gen["percorso_immagine_destinazione"] = None
                sessione.salva_sessione({"percorso_immagine_destinazione": None})

            s_aggiornata = sessione.carica_ultima_sessione()
            frames_sub = calcola_frames_tab_video(stato_gen, s_aggiornata)
            html_aggiornato = compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)
            return stato_gen, gr.update(), gr.update(value=html_aggiornato)
        except Exception as e:
            log.registra(f"Error removing frame from video strip: {e}", "WARNING")

    return stato_gen, gr.update(), gr.update()


def gestisci_trigger_galleria_batch_html(cmd, stato_gen):
    if not cmd or not cmd.strip() or stato_gen is None:
        return stato_gen, gr.update(), gr.update(), gr.update(), gr.update()

    s_sessione = sessione.carica_ultima_sessione()
    lang = s_sessione.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    label_base = dl.get("stato_galleria", "Gallery Status")
    
    immagini_generate = list(stato_gen.get("immagini_generate_batch", []))

    if cmd.startswith("SELECT_"):
        try:
            parti = cmd.split("_")
            idx = int(parti[1])
            if 0 <= idx < len(immagini_generate):
                percorso_cliccato = immagini_generate[idx]
                stato_gen["percorso_immagine_selezionata"] = percorso_cliccato
                stato_gen["gallery_no_sync"] = True
                
                sessione.salva_sessione({"percorso_immagine_selezionata": percorso_cliccato})
                
                prompt_trovato = ""
                
                if os.path.exists(percorso_cliccato):
                    try:
                        from generators.metadata_extractor import estrai_info_da_immagine
                        from PIL import Image
                        with Image.open(percorso_cliccato) as im:
                            prompt_meta, _ = estrai_info_da_immagine(im)
                            if prompt_meta and prompt_meta.strip():
                                prompt_trovato = prompt_meta.strip()
                                log.registra(f"Batch prompt recovered from PNG metadata: {percorso_cliccato}")
                    except Exception as e:
                        log.registra(f"Error reading batch PNG metadata: {e}", "WARNING")
                
                if not prompt_trovato:
                    txt_adiacente = os.path.splitext(percorso_cliccato)[0] + ".txt"
                    if os.path.exists(txt_adiacente):
                        try:
                            with open(txt_adiacente, "r", encoding="utf-8") as f_txt:
                                prompt_trovato = f_txt.read().strip()
                        except Exception as e:
                            log.registra(f"Error reading adjacent batch txt prompt: {e}", "WARNING")

                if not prompt_trovato and os.path.exists(percorso_cliccato):
                    try:
                        dir_batch = os.path.dirname(percorso_cliccato)
                        nome_base = os.path.splitext(os.path.basename(percorso_cliccato))[0]
                        nome_pulito = depura_nome_file_infinito(nome_base)
                        txt_sorgente = os.path.join(dir_batch, f"{nome_pulito}.txt")
                        if os.path.exists(txt_sorgente):
                            with open(txt_sorgente, "r", encoding="utf-8") as f_src:
                                prompt_trovato = f_src.read().strip()
                                log.registra(f"Batch prompt recovered from Phase 1 batch txt file: {txt_sorgente}")
                    except Exception as e:
                        log.registra(f"Error reading Phase 1 batch txt prompt: {e}", "WARNING")

                log.registra(f"Selected Batch HTML image idx {idx}: '{percorso_cliccato}'")
                prompt_update = gr.update(value=prompt_trovato) if prompt_trovato else gr.update()
                return stato_gen, gr.update(value=compila_galleria_html(immagini_generate, percorso_selezionato=percorso_cliccato)), gr.update(), prompt_update, gr.update()
        except Exception as e:
            log.registra(f"Error during batch trigger selection: {e}", "WARNING")

    elif cmd.startswith("DELETE_"):
        if comfyui_manager.generazione_attiva or comfyui_manager.batch_attivo:
            msg_warning = dl.get("err_cannot_delete_during_generation", "⚠️ Generation in progress. Cannot delete elements from the gallery now.")
            gr.Warning(msg_warning)
            return stato_gen, gr.update(), gr.update(), gr.update(), gr.update()

        try:
            idx = deletion_index(cmd, immagini_generate)
            if 0 <= idx < len(immagini_generate):
                percorso_elimina = immagini_generate[idx]
                if percorso_elimina and os.path.exists(percorso_elimina):
                    try:
                        os.remove(percorso_elimina)
                        log.registra(f"Batch file physically removed via trigger: '{percorso_elimina}'")
                        txt_adiacente = os.path.splitext(percorso_elimina)[0] + ".txt"
                        if os.path.exists(txt_adiacente):
                            os.remove(txt_adiacente)
                    except Exception as e:
                        log.registra(f"Unable to remove batch file from disk: {e}", "WARNING")
                
                remove_gallery_references(immagini_generate, idx)
                
                # Salvataggio immediato della lista aggiornata nello stato e nella sessione
                stato_gen["immagini_generate_batch"] = immagini_generate
                sessione.salva_sessione({"immagini_generate_batch": immagini_generate})

                immagini_visibili = immagini_generate[-MAX_GALLERY_HTML_DISPLAY:] if len(immagini_generate) > MAX_GALLERY_HTML_DISPLAY else immagini_generate
                html_galleria = compila_galleria_html(immagini_visibili)
                label_aggiornata = gr.update(label=f"{label_base} ({len(immagini_generate)})")
                
                return stato_gen, gr.update(value=html_galleria), gr.update(), gr.update(), label_aggiornata
        except Exception as e:
            log.registra(f"Error during batch trigger deletion: {e}", "WARNING")

    return stato_gen, gr.update(), gr.update(), gr.update(), gr.update()


def ricarica_vista_galleria_batch(stato_gen):
    if stato_gen is None:
        stato_gen = {}
    
    s_attiva = sessione.carica_ultima_sessione()
    batch_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_BATCH_SUBDIR)
    
    file_disco = []
    if os.path.exists(batch_dir):
        try:
            for entry in os.scandir(batch_dir):
                if entry.is_file() and entry.name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    file_disco.append((os.path.abspath(entry.path), entry.stat().st_mtime))
            file_disco.sort(key=lambda x: x[1])
            file_disco = [f[0] for f in file_disco]
        except Exception as e:
            log.registra(f"Batch Gallery Refresh scan error: {e}", "WARNING")
            file_disco = []

    immagini_esistenti = pulisci_lista_percorsi_galleria(file_disco)
                
    stato_gen["immagini_generate_batch"] = immagini_esistenti
    sessione.salva_sessione({"immagini_generate_batch": immagini_esistenti})
    
    immagini_visibili = immagini_esistenti[-MAX_GALLERY_HTML_DISPLAY:] if len(immagini_esistenti) > MAX_GALLERY_HTML_DISPLAY else immagini_esistenti
    nuovo_html = compila_galleria_html(immagini_visibili)
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    label_base = dl.get("stato_galleria", "Gallery Status")
    
    msg_sync = f"🔄 Batch Gallery synchronized ({len(immagini_esistenti)} images)."
    log.registra(f"Batch Gallery: Synchronized history from disk ({len(immagini_esistenti)} images).")
    
    return (
        stato_gen,
        gr.update(value=nuovo_html),
        msg_sync,
        gr.update(),
        gr.update(label=f"{label_base} ({len(immagini_esistenti)})")
    )
