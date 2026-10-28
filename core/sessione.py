# core/sessione.py

import json
import os
import copy
import threading
import tempfile
from core.config import (
    SESSION_FILE, 
    ottieni_lora_zimage_dirs, 
    ottieni_lora_flux2_dir, 
    ottieni_lora_krea2_dir,
    ottieni_lora_ltx_dir,
    ottieni_lora_minimax_dir,
    elenca_lora
)
from core import log

DEFAULTS = {
    "lora1_name_qwen21_edit": "-", "lora1_str_qwen21_edit": 1.0,
    "lora2_name_qwen21_edit": "-", "lora2_str_qwen21_edit": 1.0,
    "lora3_name_qwen21_edit": "-", "lora3_str_qwen21_edit": 1.0,
    "lingua_selezionata": "IT", 
    "modello_vlm": "", 
    "suggerimento_vision_selezionato": "-", 
    "sys_prompt": "",
    "user_hints": "",
    "prompt_to_send_img": "", 
    "lora_visibili_count": 1,
    "lora1_name": "-", "lora1_str": 1.0, 
    "lora2_name": "-", "lora2_str": 1.0, 
    "lora3_name": "-", "lora3_str": 1.0,
    "img_width": "1024", "img_height": "1024", "img_copies": 1,
    "steps": 8, 
    "sampler_name": "dpmpp_2m_sde",
    "scheduler": "sgm_uniform",
    "hires_steps": 6,
    "hires_denoise": 0.35,
    "hires_scale": 1.0,  
    "modello_video_attivo": "LTX-Video 2.5",
    "modello_vlm_video": "", "output_prompt_video": "",
    "lora_video_visibili_count": 1,
    "lora_video1_name": "-", "lora_video1_str": 1.0, 
    "lora_video2_name": "-", "lora_video2_str": 1.0, 
    "lora_video3_name": "-", "lora_video3_str": 1.0,
    "lora_video1_name_minimax": "-", "lora_video1_str_minimax": 1.0,
    "lora_video2_name_minimax": "-", "lora_video2_str_minimax": 1.0,
    "lora_video3_name_minimax": "-", "lora_video3_str_minimax": 1.0,
    "video_steps_minimax": 8,
    "video_denoise_minimax": 1.0,
    "video_scheduler_minimax": "beta",
    "lista_scene_salvate": "",
    "video_fps": "24", "video_durata_totale": 4.0,
    "video_rapporto": "16:9",
    "video_risoluzione": "480p",
    "audio_descrizione": "",
    "video_cfg": 1.0,
    "video_strength": 0.90,
    "video_compression": 5,
    "video_seed": "",
    "video_seed_mode": "randomize",
    "video_copies": 1,
    "video_num_clips": 3,
    "vlm_max_tokens": 512,
    "modello_vlm_batch": "",
    "suggerimento_vision_selezionato_batch": "-",
    "sys_prompt_batch": "",
    "user_hints_batch": "",
    "lora_batch1_name": "-", "lora_batch1_str": 1.0,
    "lora_batch2_name": "-", "lora_batch2_str": 1.0,
    "lora_batch3_name": "-", "lora_batch3_str": 1.0,
    "img_width_batch": "1024", "img_height_batch": "1024",
    "img_copies_batch": 1,
    "steps_batch": 8,
    "hires_scale_batch": 1.0,  
    "solo_testo_attivo": False,
    "solo_testo_video_attivo": False,
    "suggerimento_regia_selezionato": "-",
    "suggerimento_sceneggiatura_selezionato": "-",
    "sceneggiatura_prompt": "",
    "sceneggiatura_durata": 12,
    
    # SEQUENZA AI & CATALOG PERSISTENCE
    "suggerimento_sequenza_selezionato": "-",
    "sequenza_num_scatti": 5,
    "soggetti_visibili_count": 1,
    "azioni_visibili_count": 1,
    "dd_soggetto_1": "- Nessuno -",
    "dd_soggetto_2": "- Nessuno -",
    "dd_soggetto_3": "- Nessuno -",
    "dd_soggetto_4": "- Nessuno -",
    "dd_soggetto_5": "- Nessuno -",
    "dd_outfit_location": "- Default Preset -",
    "dd_azione_1": "- Nessuno -",
    "dd_azione_2": "- Nessuno -",
    "dd_azione_3": "- Nessuno -",
    "dd_azione_4": "- Nessuno -",
    "dd_azione_5": "- Nessuno -",

    # STORYBOARD PRESET & SETTINGS PARAMETERS
    "generation_mode": "Classica (1 Immagine)",
    "suggerimento_storyboard_selezionato": "-",
    "storyboard_pannelli": 3,
    "attiva_refine_storyboard": True,
    "refine_denoise": 0.35,

    # EDIT PRESET & SETTINGS PARAMETERS (KREA-2 EDIT)
    "krea2_edit_instruction": "",
    "krea2_edit_grounding_px": 768,
    "krea2_edit_lora_strength": 0.75,
    "krea2_edit_height": "1280",
    "steps_krea2_edit": 8,
    "sampler_krea2_edit": "euler",
    "scheduler_krea2_edit": "simple",
    
    # RENDERING ISOLATED PERSISTENCE PARAMETERS (Flux vs Z-Image vs Krea-2)
    "modello_immagine_attivo": "Z-Image Turbo",
    "lora1_name_zimage": "-", "lora1_str_zimage": 1.0,
    "lora2_name_zimage": "-", "lora2_str_zimage": 1.0,
    "lora3_name_zimage": "-", "lora3_str_zimage": 1.0,
    "lora1_name_flux2": "-", "lora1_str_flux2": 1.0,
    "lora2_name_flux2": "-", "lora2_str_flux2": 1.0,
    "lora3_name_flux2": "-", "lora3_str_flux2": 1.0,
    "lora1_name_krea2": "-", "lora1_str_krea2": 1.0,
    "lora2_name_krea2": "-", "lora2_str_krea2": 1.0,
    "lora3_name_krea2": "-", "lora3_str_krea2": 1.0,
    "steps_zimage": 8, "steps_flux2": 4, "steps_krea2": 8,
    "sampler_zimage": "dpmpp_2m_sde", "sampler_flux2": "euler", "sampler_krea2": "euler",
    "scheduler_flux2": "beta", "scheduler_krea2": "normal",
    "attiva_rebalance_krea2": False,

    # DUAL MODEL BATCH ISOLATED MEMORY PARAMETERS
    "modello_immagine_attivo_batch": "Z-Image Turbo",
    "lora_batch_visibili_count": 1,
    "steps_flux2_batch": 4, "steps_zimage_batch": 8, "steps_krea2_batch": 8,
    "sampler_flux2_batch": "euler", "sampler_zimage_batch": "dpmpp_2m_sde", "sampler_krea2_batch": "euler",
    "scheduler_batch": "sgm_uniform",
    "scheduler_flux2_batch": "beta",     
    "scheduler_zimage_batch": "sgm_uniform",
    "scheduler_krea2_batch": "normal", 
    "hires_steps_batch": 13,
    "hires_denoise_batch": 0.32,
    "lora1_name_zimage_batch": "-",
    "lora2_name_zimage_batch": "-",
    "lora3_name_zimage_batch": "-",
    "lora1_name_flux2_batch": "-",
    "lora2_name_flux2_batch": "-",
    "lora3_name_flux2_batch": "-",
    "lora1_name_krea2_batch": "-",
    "lora2_name_krea2_batch": "-",
    "lora3_name_krea2_batch": "-",
    "lora1_str_zimage_batch": 1.0,
    "lora2_str_zimage_batch": 1.0,
    "lora3_str_zimage_batch": 1.0,
    "lora1_str_flux2_batch": 1.0,
    "lora2_str_flux2_batch": 1.0,
    "lora3_str_flux2_batch": 1.0,
    "lora1_str_krea2_batch": 1.0,
    "lora2_str_krea2_batch": 1.0,
    "lora3_str_krea2_batch": 1.0,
    "attiva_rebalance_krea2_batch": False,

    "nome_immagine_sorgente": "",

    # GALLERY PERSISTENCE
    "immagini_generate_cumulate": [],
    "lista_frame_storyboard_attivi": [],
    "seed_attuali_cumulati": [],
    "percorso_immagine_selezionata": None,
    "percorso_immagine_destinazione": None,
    "immagini_generate_batch": []
}

_session_lock = threading.Lock()

_session_cache = None
_session_cache_mtime = 0


def _normalizza_valori_lora(stato):
    def _file_validi_zimage():
        try:
            dirs = ottieni_lora_zimage_dirs()
            return elenca_lora(dirs)
        except Exception:
            return []
            
    def _file_validi_flux2():
        try:
            dir_flux = ottieni_lora_flux2_dir()
            return elenca_lora(dir_flux)
        except Exception:
            return []

    def _file_validi_krea2():
        try:
            dir_krea2 = ottieni_lora_krea2_dir()
            return elenca_lora(dir_krea2)
        except Exception:
            return []
    
    def _file_validi_ltx():
        try:
            dir_ltx = ottieni_lora_ltx_dir()
            return elenca_lora(dir_ltx)
        except Exception:
            return []

    def _file_validi_minimax():
        try:
            dir_mm = ottieni_lora_minimax_dir()
            return elenca_lora(dir_mm)
        except Exception:
            return []
    
    validi_zimage = _file_validi_zimage()
    validi_flux2  = _file_validi_flux2()
    validi_krea2  = _file_validi_krea2()
    validi_ltx    = _file_validi_ltx()
    validi_minimax = _file_validi_minimax()
    
    chiavi_lora_img = [
        "lora1_name", "lora2_name", "lora3_name",
        "lora1_name_zimage", "lora2_name_zimage", "lora3_name_zimage",
        "lora1_name_flux2", "lora2_name_flux2", "lora3_name_flux2",
        "lora1_name_krea2", "lora2_name_krea2", "lora3_name_krea2"
    ]
    chiavi_lora_batch = [
        "lora_batch1_name", "lora_batch2_name", "lora_batch3_name",
        "lora1_name_zimage_batch", "lora2_name_zimage_batch", "lora3_name_zimage_batch",
        "lora1_name_flux2_batch", "lora2_name_flux2_batch", "lora3_name_flux2_batch",
        "lora1_name_krea2_batch", "lora2_name_krea2_batch", "lora3_name_krea2_batch"
    ]
    chiavi_lora_video = [
        "lora_video1_name", "lora_video2_name", "lora_video3_name",
        "lora_video1_name_minimax", "lora_video2_name_minimax", "lora_video3_name_minimax"
    ]
    
    tutte_chiavi = chiavi_lora_img + chiavi_lora_batch + chiavi_lora_video
    
    lora_dirs_disponibili = False
    try:
        tutte_le_dir = ottieni_lora_zimage_dirs() + [ottieni_lora_flux2_dir(), ottieni_lora_krea2_dir(), ottieni_lora_ltx_dir(), ottieni_lora_minimax_dir()]
        lora_dirs_disponibili = any(os.path.exists(d) for d in tutte_le_dir if d)
    except Exception:
        pass
    
    for chiave in tutte_chiavi:
        valore = stato.get(chiave)
        if valore is not None and valore not in ["-", "Nessuno", "None", "nessuno", "none"]:
            valore_norm = str(valore).replace("\\", "/")
            if valore_norm in validi_zimage or valore_norm in validi_flux2 or valore_norm in validi_krea2 or valore_norm in validi_ltx or valore_norm in validi_minimax:
                stato[chiave] = valore_norm
                continue
            else:
                if lora_dirs_disponibili:
                    stato[chiave] = "-"
                    log.registra(f"Normalized LoRA value '{valore}' to '-' (file not found).")
                else:
                    stato[chiave] = valore_norm
    return stato


def _sanitizza_scelte_sessione(stato):
    try:
        from core import config
        controlli = {
            "suggerimento_vision_selezionato": config.SUGGESTION_VISION_DIR,
            "suggerimento_vision_selezionato_batch": config.SUGGESTION_VISION_DIR,
            "suggerimento_storyboard_selezionato": config.SUGGESTION_STORYBOARD_DIR,
            "suggerimento_regia_selezionato": config.SUGGESTION_DIRECTION_DIR,
            "suggerimento_sceneggiatura_selezionato": config.SUGGESTION_SCREENPLAY_DIR,
            "suggerimento_sequenza_selezionato": config.SUGGESTION_SEQUENCE_DIR,
        }
        modificato = False
        for chiave, cartella in controlli.items():
            valore = stato.get(chiave)
            if valore and valore not in ["-", "Nessuno", "None", "nessuno", "none"]:
                scelte_valide = config.elenca_suggerimenti(cartella)
                scelte_pure = [os.path.splitext(x)[0] for x in scelte_valide] + list(scelte_valide)
                valore_puro = os.path.splitext(valore)[0]
                if valore not in scelte_valide and valore_puro not in scelte_pure:
                    stato[chiave] = "-"
                    modificato = True
    except Exception as e:
        print(f"Error during preventive choices sanitization: {e}")
    return stato


def carica_ultima_sessione():
    global _session_cache, _session_cache_mtime
    with _session_lock:
        if os.path.exists(SESSION_FILE):
            try:
                mtime = os.path.getmtime(SESSION_FILE)
                if _session_cache is not None and _session_cache_mtime == mtime:
                    return copy.deepcopy(_session_cache)

                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    dati = json.load(f)
                    stato = {**DEFAULTS, **dati}
                    stato = _normalizza_valori_lora(stato)
                    stato = _sanitizza_scelte_sessione(stato)
                    
                    immagini_salvate = stato.get("immagini_generate_cumulate", [])
                    seed_salvati = stato.get("seed_attuali_cumulati", [])
                    
                    stato["immagini_generate_cumulate"] = immagini_salvate
                    stato["seed_attuali_cumulati"] = seed_salvati
                    stato["seed_attuali"] = seed_salvati
                    
                    stato["immagini_generate_batch"] = stato.get("immagini_generate_batch", [])
                    stato["lista_frame_storyboard_attivi"] = stato.get("lista_frame_storyboard_attivi", [])
                    
                    percorso_sel = stato.get("percorso_immagine_selezionata")
                    stato["percorso_immagine_selezionata"] = percorso_sel
                    stato["percorso_immagine_destinazione"] = stato.get("percorso_immagine_destinazione", None)
                        
                    _session_cache = copy.deepcopy(stato)
                    _session_cache_mtime = os.path.getmtime(SESSION_FILE)
                    return stato
            except Exception as e:
                print(f"Error loading session: {e}")
                return copy.deepcopy(DEFAULTS)
        return copy.deepcopy(DEFAULTS)


def salva_sessione(nuovi_dati):
    global _session_cache, _session_cache_mtime
    if not nuovi_dati or not isinstance(nuovi_dati, dict):
        return
        
    with _session_lock:
        if _session_cache is None:
            if os.path.exists(SESSION_FILE):
                try:
                    with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                        _session_cache = {**DEFAULTS, **json.load(f)}
                except Exception:
                    _session_cache = copy.deepcopy(DEFAULTS)
            else:
                _session_cache = copy.deepcopy(DEFAULTS)
        
        nuova_cache = copy.deepcopy(_session_cache)
        nuova_cache.update(copy.deepcopy(nuovi_dati))
        
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=os.path.dirname(os.path.abspath(SESSION_FILE)),
                                             delete=False) as f:
                temp_path = f.name
                json.dump(nuova_cache, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, SESSION_FILE)
            _session_cache = nuova_cache
            _session_cache_mtime = os.path.getmtime(SESSION_FILE)
        except Exception as e:
            print(f"Error saving session: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
