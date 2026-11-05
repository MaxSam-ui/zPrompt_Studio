# utils/media_utils.py

import os
import time
import hashlib
from typing import List, Optional
import gradio as gr
from PIL import Image

from core import config, log, sessione, lingua

from utils.media_base import (
    depura_nome_file_infinito,
    calcola_rapporto_vicino,
    calcola_risoluzione_vicina,
    leggi_dimensioni_immagine_sicura,
    _estrai_percorso_video_sicuro,
    _estrai_percorso_immagine_sicuro,
    norm_path_sicuro
)

from utils.html_utils import (
    calcola_stato_spia_video, 
    compila_galleria_html, 
    compila_striscia_video_html,
    ottieni_lightbox_modal_html
)

from utils.image_processing import taglia_storyboard_pil


# =========================================================================
# UTILITY UNIFICATE SUBJECT & HASH (Deduplicazione Centrale)
# =========================================================================

def calcola_hash_prompt(prompt_text: str) -> str:
    """Calcola l'hash MD5 univoco normalizzato di una stringa prompt."""
    if not prompt_text:
        return "empty_prompt"
    p_norm = str(prompt_text).strip().lower()
    return hashlib.md5(p_norm.encode('utf-8')).hexdigest()


def salva_soggetto_scena(prompt_testo: str, soggetto_testo: str) -> bool:
    """Salva il soggetto cinematografico collegato al prompt in studio_output/subjects/{hash}.txt."""
    if not prompt_testo or not str(prompt_testo).strip() or not soggetto_testo or not str(soggetto_testo).strip():
        return False
    try:
        hash_p = calcola_hash_prompt(prompt_testo)
        subjects_dir = os.path.join(config.STUDIO_OUTPUT_DIR, "subjects")
        os.makedirs(subjects_dir, exist_ok=True)
        subj_path = os.path.join(subjects_dir, f"{hash_p}.txt")
        with open(subj_path, "w", encoding="utf-8") as f_sub:
            f_sub.write(soggetto_testo.strip())
        log.registra(f"Movie subject saved: {subj_path}")
        return True
    except Exception as e:
        log.registra(f"Unable to save subject file: {e}", "WARNING")
        return False


def recupera_soggetto_scena(prompt_testo: str) -> str:
    """Recupera il soggetto cinematografico archiviato per un dato prompt se presente."""
    if not prompt_testo or not str(prompt_testo).strip():
        return ""
    try:
        hash_p = calcola_hash_prompt(prompt_testo)
        subj_path = os.path.join(config.STUDIO_OUTPUT_DIR, "subjects", f"{hash_p}.txt")
        if os.path.exists(subj_path):
            with open(subj_path, "r", encoding="utf-8") as f_sub:
                return f_sub.read().strip()
    except Exception as e:
        log.registra(f"Error reading archived subject: {e}", "WARNING")
    return ""


def pulisci_lista_percorsi_galleria(lista_percorsi: List[str]) -> List[str]:
    """Rimuove duplicati e percorsi inesistenti preservando l'ordine di inserimento originale."""
    if not lista_percorsi:
        return []
    viste = set()
    risultato = []
    for p in lista_percorsi:
        if p and os.path.exists(p):
            norm_p = norm_path_sicuro(p)
            if norm_p not in viste:
                viste.add(norm_p)
                risultato.append(p)
    return risultato


# =========================================================================
# FUNZIONI DI SINCRONIZZAZIONE E GESTIONE MEDIA
# =========================================================================

def calcola_frames_tab_video(stato_gen=None, s_sessione=None):
    """
    Restituisce la lista mirata di frame da visualizzare accanto al Frame 1 nel Tab Video:
    - Se modalità Storyboard: solo i fotogrammi successivi al primo (pannello 2, 3, 4...).
    - Altrimenti: esclusivamente la singola immagine impostata come Last Frame (L), se presente.
    """
    if stato_gen and stato_gen.get("is_extension"):
        return []
    if s_sessione is None:
        from core import sessione as core_sessione
        s_sessione = core_sessione.carica_ultima_sessione()
        
    gen_mode = str(s_sessione.get("generation_mode", "Classica (1 Immagine)")).lower()
    
    if "storyboard" in gen_mode:
        if stato_gen is not None and "lista_frame_storyboard_attivi" in stato_gen:
            frames_story = stato_gen["lista_frame_storyboard_attivi"]
        else:
            frames_story = s_sessione.get("lista_frame_storyboard_attivi", [])
            
        if frames_story and len(frames_story) > 1:
            return frames_story[1:]
        return []
    else:
        if stato_gen is not None and "percorso_immagine_destinazione" in stato_gen:
            last_frame = stato_gen["percorso_immagine_destinazione"]
        else:
            last_frame = s_sessione.get("percorso_immagine_destinazione")
            
        if last_frame and os.path.exists(last_frame):
            return [last_frame]
        return []


def gestore_analisi_adattivo(immagine, sys_prompt, user_hints, modello, solo_testo_flag, vlm_max_tokens=512):
    from services import comfyui_manager
    comfyui_manager.vlm_interrotto = False
    
    from services import local_vlm
    if solo_testo_flag:
        from utils.prompt_templates import build_vision_prompt
        active = sessione.carica_ultima_sessione()
        preset = active.get("suggerimento_vision_selezionato", "-")
        visual = build_vision_prompt(preset, False, int(vlm_max_tokens))
        textual = build_vision_prompt(preset, True, int(vlm_max_tokens))
        if not sys_prompt or sys_prompt.strip() == visual.strip():
            sys_prompt = textual
        log.registra("Text-only mode active: no image sent to VLM.")
        yield from local_vlm.genera_prompt_immagine(None, sys_prompt, user_hints, modello, max_new_tokens=int(vlm_max_tokens))
    else:
        if not immagine:
            s_attiva = sessione.carica_ultima_sessione()
            lang = s_attiva.get("lingua_selezionata", "IT")
            dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
            msg_err = dl.get("err_load_img_first", "⚠️ Please upload an image first before starting visual analysis.")
            yield msg_err
            return
            
        if isinstance(immagine, str) and os.path.exists(immagine):
            try:
                base_name = os.path.splitext(os.path.basename(immagine))[0]
                sessione.salva_sessione({"nome_immagine_sorgente": base_name})
                
                with Image.open(immagine) as im:
                    im_pil = im.convert("RGB")
                yield from local_vlm.genera_prompt_immagine(im_pil, sys_prompt, user_hints, modello, max_new_tokens=int(vlm_max_tokens))
            except Exception as e:
                log.registra(f"Error loading image for analysis: {e}", "ERROR")
                yield f"❌ Error loading image: {e}"
        else:
            yield from local_vlm.genera_prompt_immagine(immagine, sys_prompt, user_hints, modello, max_new_tokens=int(vlm_max_tokens))


def aggiorna_dopo_analisi(prompt_testo, immagine_pil):
    from services import comfyui_manager
    if getattr(comfyui_manager, "vlm_interrotto", False):
        log.registra("Post-analysis sync skipped: manual interruption detected.")
        return prompt_testo, log.ottieni_tutti_i_log(), gr.update(), gr.update(), gr.update(), gr.update()

    logs = log.ottieni_tutti_i_log()
    w_orig, h_orig = leggi_dimensioni_immagine_sicura(immagine_pil)
    
    sessione.salva_sessione({"prompt_to_send_img": prompt_testo})
    log.registra("Post-analysis sync: prompt saved to the session on disk.")
    
    if w_orig is None or h_orig is None:
        log.registra("Allineamento post-analisi saltato: tipo immagine non riconosciuto o nullo.")
        return prompt_testo, logs, gr.update(), gr.update(), gr.update(), gr.update()
        
    try:
        scelte_standard = [512, 768, 1024, 1280, 1536, 2048]
        w_vicino = str(min(scelte_standard, key=lambda x: abs(x - w_orig)))
        h_vicino = str(min(scelte_standard, key=lambda x: abs(x - h_orig)))
        
        ratio_vicino = calcola_rapporto_vicino(w_orig, h_orig)
        res_vicina = calcola_risoluzione_vicina(w_orig, h_orig)
        
        log.registra(f"Sincronizzazione post-analisi: immagine {w_orig}x{h_orig} mapped a img {w_vicino}x{h_vicino} e video {ratio_vicino} / {res_vicina}")
        return prompt_testo, logs, gr.update(value=w_vicino), gr.update(value=h_vicino), gr.update(value=ratio_vicino), gr.update(value=res_vicina)
    except Exception as e:
        log.registra(f"Post-analysis resolution calculation error: {e}", "WARNING")
        return prompt_testo, logs, gr.update(), gr.update(), gr.update(), gr.update()


def allinea_video_a_generata(stato_gen):
    if stato_gen is None:
        stato_gen = {}
    filepath = stato_gen.get("percorso_immagine_selezionata")
    
    active_story = stato_gen.get("lista_frame_storyboard_attivi", [])
    classic_imgs = stato_gen.get("immagini_generate_cumulate", [])
    
    if not filepath or not os.path.exists(filepath):
        if active_story:
            filepath = active_story[0]
            stato_gen["percorso_immagine_selezionata"] = filepath
            log.registra("Video alignment: First active storyboard panel applied as I2V source.")
        elif classic_imgs:
            filepath = classic_imgs[-1]
            stato_gen["percorso_immagine_selezionata"] = filepath
            log.registra("Allineamento Video: Applicata ultima immagine classica generata come sorgente I2V.")
            
    if not filepath or not os.path.exists(filepath):
        log.registra("Video alignment: No valid source file found for transfer to the Video tab.", "WARNING")
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        
    try:
        sessione.salva_sessione({
            "percorso_immagine_selezionata": filepath,
            "solo_testo_video_attivo": False
        })
        
        s_reale = sessione.carica_ultima_sessione()
        frames_sub = calcola_frames_tab_video(stato_gen=stato_gen, s_sessione=s_reale)
        is_storyboard = "storyboard" in str(s_reale.get("generation_mode", "")).lower()
        html_video_strip = compila_striscia_video_html(frames_sub, is_storyboard=is_storyboard)

        with Image.open(filepath) as im:
            w, h = im.size
            ratio = calcola_rapporto_vicino(w, h)
            res = calcola_risoluzione_vicina(w, h)
            log.registra(f"Allineamento Video: immagine generata {w}x{h} trasferita al Tab Video ({ratio} / {res}).")
            
            return (
                gr.update(value=ratio), 
                gr.update(value=res), 
                gr.update(value=filepath, visible=True),
                gr.update(value=False),
                gr.update(visible=True),
                gr.update(value=html_video_strip)
            )
    except Exception as e:
        log.registra(f"Post-generation video alignment error: {e}", "WARNING")
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()


def gestore_estensione_video(video_input, immagine_i2v, stato_gen):
    video_path = _estrai_percorso_video_sicuro(video_input)
    img_i2v_path = _estrai_percorso_immagine_sicuro(immagine_i2v)
    
    if stato_gen is None:
        stato_gen = {}
        
    is_manual_upload = stato_gen.get("immagine_caricata_manualmente", False)
    
    s_sessione = sessione.carica_ultima_sessione()
    lang = s_sessione.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    cumulate = stato_gen.get("immagini_generate_cumulate", [])
    if not isinstance(cumulate, list):
        cumulate = list(cumulate)
    
    if (is_manual_upload and img_i2v_path and os.path.exists(img_i2v_path)
            and video_path and os.path.exists(video_path)):
        stato_gen["clip_chain"] = [video_path]
        stato_gen["is_extension"] = True
        stato_gen["gallery_no_sync"] = True
        stato_gen["immagine_caricata_manualmente"] = False
        stato_gen["percorso_immagine_destinazione"] = None
        stato_gen["percorso_immagine_selezionata"] = img_i2v_path
        
        sessione.salva_sessione({
            "percorso_immagine_selezionata": img_i2v_path,
            "percorso_immagine_destinazione": None,
            "solo_testo_video_attivo": False
        })
        
        log.registra("Video extension: Manual junction frame uploaded. Last Frame reset and T2V disabled.")
        
        spia_html = calcola_stato_spia_video(s_sessione, stato_gen, False)
        msg_ok = dl.get("ext_manual_loaded", "📥 Manual connection loaded. Ready for extension!")
        
        frames_sub = calcola_frames_tab_video(stato_gen=stato_gen, s_sessione=s_sessione)
        html_video_strip = compila_striscia_video_html(frames_sub, is_storyboard=False)

        return (
            msg_ok,
            stato_gen,
            gr.update(), gr.update(),
            compila_galleria_html(cumulate, percorso_selezionato=img_i2v_path),
            gr.update(value=img_i2v_path),
            gr.update(value=spia_html),
            gr.update(value=False),
            gr.update(visible=True),
            gr.update(value=html_video_strip)
        )
    
    if not video_path or not os.path.exists(video_path):
        msg_err = dl.get("ext_err_no_video", "⚠️ No generated video to extend.")
        return (
            msg_err, stato_gen, gr.update(), gr.update(),
            compila_galleria_html(cumulate), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update()
        )
        
    try:
        local_img_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_IMG_SUBDIR)
        os.makedirs(local_img_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        nome_frame = f"frame_esteso_{timestamp}.png"
        dest_frame_path = os.path.abspath(os.path.join(local_img_dir, nome_frame))
        
        from utils.ffmpeg_utils import estrai_ultimo_frame_ffmpeg
        if not estrai_ultimo_frame_ffmpeg(video_path, dest_frame_path):
            msg_err_ext = dl.get("ext_err_extraction", "❌ Error during frame extraction from OpenCV/FFmpeg.")
            return (
                msg_err_ext, stato_gen, gr.update(), gr.update(),
                compila_galleria_html(cumulate), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update()
            )
        
        if dest_frame_path not in cumulate:
            cumulate.append(dest_frame_path)
            stato_gen["immagini_generate_cumulate"] = cumulate
            sessione.salva_sessione({"immagini_generate_cumulate": cumulate})

        stato_gen["percorso_immagine_selezionata"] = dest_frame_path
        stato_gen["percorso_immagine_destinazione"] = None
        stato_gen["gallery_no_sync"] = True
        
        stato_gen["clip_chain"] = [video_path]
        stato_gen["is_extension"] = True
        
        sessione.salva_sessione({
            "percorso_immagine_selezionata": dest_frame_path,
            "percorso_immagine_destinazione": None,
            "solo_testo_video_attivo": False
        })
        
        log.registra(f"Video extension: Last frame '{nome_frame}' extracted and set as Frame 1. Last Frame reset and T2V disabled.")
        
        html_galleria = compila_galleria_html(cumulate, percorso_selezionato=dest_frame_path)
        spia_html = calcola_stato_spia_video(s_sessione, stato_gen, False)
        msg_success = dl.get("ext_success_auto_loaded", "📥 Last frame ({nome_frame}) set. Extension chain active!").format(nome_frame=nome_frame)
        
        frames_sub = calcola_frames_tab_video(stato_gen=stato_gen, s_sessione=s_sessione)
        html_video_strip = compila_striscia_video_html(frames_sub, is_storyboard=False)

        return (
            msg_success, 
            stato_gen, 
            gr.update(), 
            gr.update(),
            html_galleria, 
            gr.update(value=dest_frame_path),
            gr.update(value=spia_html),
            gr.update(value=False),
            gr.update(visible=True),
            gr.update(value=html_video_strip)
        )
    except Exception as e:
        log.registra(f"Video extension extraction error: {e}", "ERROR")
        msg_fail = f"❌ Error during extraction: {e}"
        return (
            msg_fail, stato_gen, gr.update(), gr.update(),
            compila_galleria_html(cumulate), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update()
        )


def carica_da_immagine_upload(filepath, stato_gen):
    if not filepath or not os.path.exists(filepath):
        s_sessione = sessione.carica_ultima_sessione()
        lang = s_sessione.get("lingua_selezionata", "IT")
        dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
        msg_err_invalid = dl.get("err_invalid_file", "⚠️ No valid file provided.")
        return "", "", gr.update(visible=True), stato_gen, gr.update(), gr.update(), gr.update(), gr.update(), "randomize", "", msg_err_invalid, gr.update()
    try:
        from generators import workflow

        with Image.open(filepath) as im:
            prompt, seed = workflow.estrai_info_da_immagine(im)
            w_orig, h_orig = leggi_dimensioni_immagine_sicura(im)
        
        if stato_gen is None:
            stato_gen = {}
            
        stato_gen["gallery_no_sync"] = True
        
        s_sessione = sessione.carica_ultima_sessione()
        lang = s_sessione.get("lingua_selezionata", "IT")
        dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
        
        generation_mode = s_sessione.get("generation_mode", "Classica (1 Immagine)")
        
        if "storyboard" in str(generation_mode).lower():
            lista_key = "lista_frame_storyboard_attivi"
        else:
            lista_key = "immagini_generate_cumulate"
            
        existing_list = stato_gen.get(lista_key, [])
        if not isinstance(existing_list, list):
            existing_list = list(s_sessione.get(lista_key, []))
            
        filepath_norm = norm_path_sicuro(filepath)
        already_exists = False
        for img in existing_list:
            if img and norm_path_sicuro(img) == filepath_norm:
                already_exists = True
                break
                
        if not already_exists:
            existing_list.append(filepath)
            
        stato_gen[lista_key] = existing_list
        stato_gen["percorso_immagine_selezionata"] = filepath
        if seed is not None:
            stato_gen["seed_attuali"] = [seed]
        
        html_galleria = compila_galleria_html(existing_list, percorso_selezionato=filepath)
        
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        base_name_pulito = depura_nome_file_infinito(base_name)
        
        soggetto_recuperato = recupera_soggetto_scena(prompt) if prompt else ""

        sessione.salva_sessione({
            "prompt_to_send_img": prompt if prompt else "",
            **({"sceneggiatura_prompt": soggetto_recuperato} if soggetto_recuperato and soggetto_recuperato.strip() else {}),
            "img_seed": str(seed) if seed is not None else "",
            "img_seed_mode": "fixed" if seed is not None else "randomize",
            "nome_immagine_sorgente": base_name_pulito,
            "percorso_immagine_selezionata": filepath,
            lista_key: existing_list
        })
        
        if w_orig is not None and h_orig is not None:
            scelte_standard = [512, 768, 1024, 1280, 1536, 2048]
            w_vicino = str(min(scelte_standard, key=lambda x: abs(x - w_orig)))
            h_vicino = str(min(scelte_standard, key=lambda x: abs(x - h_orig)))
            
            ratio_vicino = calcola_rapporto_vicino(w_orig, h_orig)
            res_vicina = calcola_risoluzione_vicina(w_orig, h_orig)
            
            log.registra(f"Upload immagine: risoluzione nativa {w_orig}x{h_orig} mapped a img {w_vicino}x{h_vicino} e video {ratio_vicino} / {res_vicina}")
            w_update = gr.update(value=w_vicino)
            h_update = gr.update(value=h_vicino)
            ratio_update = gr.update(value=ratio_vicino)
            res_update = gr.update(value=res_vicina)
        else:
            w_update = gr.update()
            h_update = gr.update()
            ratio_update = gr.update()
            res_update = gr.update()
            
        msg_upload = dl.get("upload_success_meta", "📥 Image and metadata loaded successfully!") if seed is not None else dl.get("upload_success_nometa", "📥 Image loaded as source (no metadata detected).")
        return (
            prompt if prompt else "", 
            str(seed) if seed is not None else "", 
            gr.update(value=html_galleria, visible=True),
            stato_gen,
            w_update,
            h_update,
            ratio_update,
            res_update,
            "fixed" if seed is not None else "randomize",
            str(seed) if seed is not None else "",
            msg_upload,
            soggetto_recuperato if soggetto_recuperato and soggetto_recuperato.strip() else gr.update()
        )
    except Exception as e:
        log.registra(f"Image loading error: {e}")
        return "", "", gr.update(visible=True), stato_gen, gr.update(), gr.update(), gr.update(), gr.update(), "randomize", "", f"❌ Error loading image: {e}", gr.update()


def sync_immagine_sorgente_i2v(filepath, stato_gen):
    path_reale = _estrai_percorso_immagine_sicuro(filepath)
    
    p_up = gr.update()
    ratio_up = gr.update()
    res_up = gr.update()  
    g_img_up = gr.update()
    g_story_up = gr.update()
    seed_vis = ""
    seed_vid = ""
    w_up = gr.update()
    h_up = gr.update()
    
    if stato_gen is None:
        stato_gen = {}
        
    no_sync_attivo = stato_gen.get("gallery_no_sync", False) or stato_gen.get("is_extension", False)
    
    if no_sync_attivo:
        seed_mode_up = gr.update()
        seed_val_up = gr.update()
        ratio_up = gr.update()
        res_up = gr.update()
        stato_gen["gallery_no_sync"] = False 
    else:
        seed_mode_up = gr.update(value="randomize")
        seed_val_up = gr.update(value="")

    if not stato_gen.get("is_extension"):
        if "clip_chain" in stato_gen:
            stato_gen["clip_chain"] = []

    if not path_reale or not os.path.exists(path_reale):
        return p_up, ratio_up, res_up, g_img_up, g_story_up, seed_vis, seed_vid, stato_gen, w_up, h_up, seed_mode_up, seed_val_up
        
    try:
        from generators import workflow
        from PIL import Image

        with Image.open(path_reale) as im:
            prompt, seed = workflow.estrai_info_da_immagine(im)
            w_orig, h_orig = im.size
        
        if w_orig and h_orig and not no_sync_attivo:
            scelte_standard = [512, 768, 1024, 1280, 1536, 2048]
            w_vicino = str(min(scelte_standard, key=lambda x: abs(x - w_orig)))
            h_vicino = str(min(scelte_standard, key=lambda x: abs(x - h_orig)))
            
            w_up = gr.update(value=w_vicino)
            h_up = gr.update(value=h_vicino)
            
            ratio_vicino = calcola_rapporto_vicino(w_orig, h_orig)
            ratio_up = gr.update(value=ratio_vicino)
            res_vicina = calcola_risoluzione_vicina(w_orig, h_orig)
            res_up = gr.update(value=res_vicina)
            
        stato_gen["percorso_immagine_selezionata"] = path_reale
        s_sessione = sessione.carica_ultima_sessione()
        
        if not no_sync_attivo:
            prompt_val = prompt.strip() if (prompt and prompt.strip()) else ""
            p_up = gr.update(value=prompt_val)
            sessione.salva_sessione({"prompt_to_send_img": prompt_val})
                
            seed_str = str(seed) if seed is not None else ""
            seed_vis = seed_str if seed_str else ("Seed not available" if s_sessione.get("lingua_selezionata", "IT") == "EN" else "Seed non disponibile")
            seed_vid = seed_str
            
            if seed is not None:
                seed_mode_up = gr.update(value="fixed")
                seed_val_up = gr.update(value=seed_str)
                sessione.salva_sessione({
                    "img_seed": seed_str,
                    "img_seed_mode": "fixed"
                })
        else:
            seed_str = str(seed) if seed is not None else ""
            seed_vis = seed_str if seed_str else ("Seed not available" if s_sessione.get("lingua_selezionata", "IT") == "EN" else "Seed non disponibile")
            seed_vid = seed_str
        
        base_name = os.path.splitext(os.path.basename(path_reale))[0]
        base_name_pulito = depura_nome_file_infinito(base_name)
        
        sessione.salva_sessione({"nome_immagine_sorgente": base_name_pulito, "percorso_immagine_selezionata": path_reale})
        log.registra(f"I2V Sync: Linked frame '{base_name_pulito}' (Metadata prompt: {'Detected' if (prompt and prompt.strip()) else 'Absent/Reset'}).")
        
    except Exception as e:
        log.registra(f"I2V metadata sync error: {e}", "WARNING")
        
    return p_up, ratio_up, res_up, g_img_up, g_story_up, seed_vis, seed_vid, stato_gen, w_up, h_up, seed_mode_up, seed_val_up
