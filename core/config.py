# core/config.py

import os
import json
import glob

from core import log

STUDIO_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.abspath(os.path.join(STUDIO_ROOT_DIR, "settings.json"))

DEFAULT_SETTINGS = {
    "COMFYUI_DIR": "D:\\ComfyUI_windows_portable",
    "STUDIO_OUTPUT_DIR": "output",
    "VLM_CACHE_DIR": "",
    "SESSION_FILE": "session.json",
    "LORA_ZIMAGE_DIR_1": "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Z-Image1",
    "LORA_ZIMAGE_DIR_2": "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Z-Image2",
    "LORA_FLUX2_DIR": "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Flux-2",
    "LORA_KREA2_DIR": "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Krea-2",
    "LORA_LTX_DIR": "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\LTX-2.5",
    "LORA_MINIMAX_DIR": "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\MiniMax",
    "SUGGESTION_VISION_DIR": "suggestions/vision",
    "SUGGESTION_DIRECTION_DIR": "suggestions/direction",
    "SUGGESTION_SCREENPLAY_DIR": "suggestions/screenplay",
    "SUGGESTION_STORYBOARD_DIR": "suggestions/storyboard",
    "SUGGESTION_SEQUENCE_DIR": "suggestions/sequence",
    "COMFYUI_URL": "http://127.0.0.1:8188",
    "IMAGE_TIMEOUT": 360,
    "TEXT_TIMEOUT": 180,
    "STREAMING_TIMEOUT": 180,
    "COMFYUI_IMAGE_TIMEOUT": 600,
    "COMFYUI_VIDEO_TIMEOUT": 660,
    "COMFYUI_STARTUP_TIMEOUT": 180,
    "KEEP_MODELS_WARM": False,
    "COMFYUI_HIGHVRAM": False,
    "LTX_VIDEO_CFG": 3.0,
    "Z_IMAGE_CFG": 1.0,
    "HIRES_STEPS": 13,
    "HIRES_DENOISE": 0.32,
    "HIRES_SAMPLER": "dpmpp_2m_sde",
    "COMFYUI_ARGS": ["--disable-auto-launch"],
    "SHOT_TYPES": [
        "🧍 [Shot] Medium Shot",
        "👤 [Shot] Close-up",
        "👤 [Shot] Extreme Close-up",
        "🔍 [Shot] Macro Shot",
        "🚶 [Shot] Full Body Shot",
        "🗺️ [Shot] Wide Shot",
        "🌇 [Shot] Establishing Shot",
        "🚁 [Shot] Cinematic Drone Shot",
        "🔽 [Angle] Low Angle Shot",
        "🔼 [Angle] High Angle Shot",
        "🌀 [Angle] Dutch Angle Shot",
        "🦅 [Angle] Bird's Eye View",
        "🦅 [Angle] Aerial Drone Shot",
        "👁️ [POV] Point-of-View (POV) Shot",
        "👥 [Perspective] Over-the-Shoulder Shot",
        "📺 [Format] Cinematic 16:9 Widescreen",
        "📱 [Format] Cinematic 9:16 Portrait"
    ],
    "CAMERA_MOTIONS": [
        "⏹️ [Static] Static (No Zoom)",
        "💨 [Static] Subtle Camera Drift / Operator Breathing",
        "⏩ [Dolly] Slow Dolly Push-in",
        "⏪ [Dolly] Slow Dolly Pull-out",
        "↔️ [Dolly] Lateral Slider Move",
        "🔎 [Zoom] Slow Zoom-in",
        "🔍 [Zoom] Slow Zoom-out",
        "⚡ [Zoom] Fast Zoom-in",
        "🌪️ [Zoom] Fast Zoom-out",
        "🚀 [Zoom] Dynamic Dolly Zoom",
        "◀️ [Pan] Slow Pan Left",
        "▶️ [Pan] Slow Pan Right",
        "🔼 [Tilt] Slow Tilt Up",
        "🔽 [Tilt] Slow Tilt Down",
        "🏃 [Tracking] Tracking Follow Shot",
        "🎥 [Style] Snorricam / Bodycam Shot",
        "🎛️ [Style] Handheld Camera Shake"
    ]
}

def carica_impostazioni():
    if not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_SETTINGS, f, indent=4)
            log.registra(f"File '{SETTINGS_FILE}' not found. Created default settings file with all parameters.")
            return DEFAULT_SETTINGS
        except Exception as e:
            log.registra(f"Unable to create default settings file: {e}", "WARNING")
            return DEFAULT_SETTINGS
            
    try:
        modificato = False
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            dati = json.load(f)
            
            if "VLM_URL" in dati:
                del dati["VLM_URL"]
                modificato = True
                
            mappa_migrazione = {
                "TIMEOUT_IMMAGINI": "IMAGE_TIMEOUT",
                "TIMEOUT_TESTO": "TEXT_TIMEOUT",
                "TIMEOUT_STREAMING": "STREAMING_TIMEOUT",
                "TIMEOUT_COMFY_IMMAGINE": "COMFYUI_IMAGE_TIMEOUT",
                "TIMEOUT_COMFY_VIDEO": "COMFYUI_VIDEO_TIMEOUT",
                "TIPI_INQUADRATURA": "SHOT_TYPES",
                "TIPI_ZOOM": "CAMERA_MOTIONS"
            }
            
            for vecchia, nuova in mappa_migrazione.items():
                if vecchia in dati:
                    dati[nuova] = dati[vecchia]
                    del dati[vecchia]
                    modificato = True
                    
            for k, v in DEFAULT_SETTINGS.items():
                if k not in dati:
                    dati[k] = v
                    modificato = True
        
        if modificato:
            try:
                with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(dati, f, indent=4)
                log.registra(f"Updated '{SETTINGS_FILE}' file with new parameters.")
            except Exception as e:
                log.registra(f"Unable to update settings file: {e}", "WARNING")
                
        return dati
    except Exception as e:
        log.registra(f"Error reading file '{SETTINGS_FILE}' ({e}). Using default settings.", "WARNING")
        return DEFAULT_SETTINGS

def _rendi_percorso_assoluto(percorso):
    if not percorso:
        return ""
    if os.path.isabs(percorso):
        return os.path.abspath(percorso)
    return os.path.abspath(os.path.join(STUDIO_ROOT_DIR, percorso))

_config = carica_impostazioni()

COMFYUI_URL = _config["COMFYUI_URL"]
COMFYUI_DIR = _config["COMFYUI_DIR"]

def ottieni_lora_zimage_dirs():
    dir1 = os.path.abspath(_config.get("LORA_ZIMAGE_DIR_1", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Z-Image1").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))
    dir2 = os.path.abspath(_config.get("LORA_ZIMAGE_DIR_2", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Z-Image2").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))
    return [dir1, dir2]

def ottieni_lora_flux2_dir():
    return os.path.abspath(_config.get("LORA_FLUX2_DIR", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Flux-2").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))

def ottieni_lora_krea2_dir():
    return os.path.abspath(_config.get("LORA_KREA2_DIR", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Krea-2").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))

def ottieni_lora_qwen21_dir():
    return os.path.abspath(_config.get("LORA_QWEN21_DIR", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\Qwen2.1").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))

def ottieni_lora_ltx_dir():
    return os.path.abspath(_config.get("LORA_LTX_DIR", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\LTX-2.5").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))

def ottieni_lora_minimax_dir():
    return os.path.abspath(_config.get("LORA_MINIMAX_DIR", "{COMFYUI_DIR}\\ComfyUI\\models\\loras\\MiniMax").format(COMFYUI_DIR=COMFYUI_DIR).replace("\\", os.sep))

SUGGESTION_VISION_DIR = _rendi_percorso_assoluto(_config.get("SUGGESTION_VISION_DIR", "suggestions/vision"))
SUGGESTION_DIRECTION_DIR = _rendi_percorso_assoluto(_config.get("SUGGESTION_DIRECTION_DIR", "suggestions/direction"))
SUGGESTION_SCREENPLAY_DIR = _rendi_percorso_assoluto(_config.get("SUGGESTION_SCREENPLAY_DIR", "suggestions/screenplay"))
SUGGESTION_STORYBOARD_DIR = _rendi_percorso_assoluto(_config.get("SUGGESTION_STORYBOARD_DIR", "suggestions/storyboard"))
SUGGESTION_SEQUENCE_DIR = _rendi_percorso_assoluto(_config.get("SUGGESTION_SEQUENCE_DIR", "suggestions/sequence"))
SUGGESTION_SYSTEM_DIR = _rendi_percorso_assoluto("suggestions/system")

STUDIO_OUTPUT_DIR = _rendi_percorso_assoluto(_config.get("STUDIO_OUTPUT_DIR", "output"))
COMFYUI_OUTPUT_DIR = os.path.abspath(os.path.join(COMFYUI_DIR, "ComfyUI", "output"))
STUDIO_IMG_SUBDIR = "images"
STUDIO_VIDEO_SUBDIR = "videos"
STUDIO_BATCH_SUBDIR = "batch"

SESSION_FILE = _rendi_percorso_assoluto(_config["SESSION_FILE"])

PROMPT_BASE_DIR = _rendi_percorso_assoluto("saved_prompt")
PROMPT_IMG_DIR  = os.path.join(PROMPT_BASE_DIR, "images")
PROMPT_VID_DIR  = os.path.join(PROMPT_BASE_DIR, "videos")

WF_ZIMAGE_FILE  = _rendi_percorso_assoluto("workflows/z_image_turbo_api.json")
WF_LTX_FILE     = _rendi_percorso_assoluto("workflows/ltx2.5_api.json")
WF_MINIMAX_FILE = _rendi_percorso_assoluto("workflows/minimax_h3_api.json")
WF_KREA2_FILE   = _rendi_percorso_assoluto("workflows/krea2_turbo_api.json")
WF_KREA2_EDIT_FILE = _rendi_percorso_assoluto("workflows/krea2_turbo_edit_api.json")

TIMEOUT_IMMAGINI = int(_config.get("IMAGE_TIMEOUT", 360))
TIMEOUT_TESTO = int(_config.get("TEXT_TIMEOUT", 180))
TIMEOUT_STREAMING = int(_config.get("STREAMING_TIMEOUT", 180))
TIMEOUT_COMFY_IMMAGINE = int(_config.get("COMFYUI_IMAGE_TIMEOUT", 600))
TIMEOUT_COMFY_VIDEO = int(_config.get("COMFYUI_VIDEO_TIMEOUT", 660))
COMFYUI_ARGS = _config.get("COMFYUI_ARGS", ["--disable-auto-launch"])
KEEP_MODELS_WARM = _config.get("KEEP_MODELS_WARM", False)
COMFYUI_STARTUP_TIMEOUT = int(_config.get("COMFYUI_STARTUP_TIMEOUT", 180))
COMFYUI_HIGHVRAM = _config.get("COMFYUI_HIGHVRAM", False)

IMG_OUTPUT_PATTERN = "z-image_*.png"
IMG_PREFIX = "z-image"
VIDEO_EXTENSIONS = ["*.mp4", "*.webm", "*.gif"]
TEXT_ONLY_FILENAME = "text_only.txt"
COMFYUI_LOCK_FILE = os.path.join(os.environ.get("TEMP", "."), "comfyui_startup.lock")

HIRES_STEPS = int(_config.get("HIRES_STEPS", 13))
HIRES_SAMPLER = str(_config.get("HIRES_SAMPLER", "dpmpp_2m_sde"))
HIRES_DENOISE = float(_config.get("HIRES_DENOISE", 0.32))
LTX_VIDEO_CFG = float(_config.get("LTX_VIDEO_CFG", 3.0))
Z_IMAGE_CFG = float(_config.get("Z_IMAGE_CFG", 1.0))
TIPI_INQUADRATURA = _config.get("SHOT_TYPES", DEFAULT_SETTINGS["SHOT_TYPES"])
TIPI_ZOOM = _config.get("CAMERA_MOTIONS", DEFAULT_SETTINGS["CAMERA_MOTIONS"])

def genera_nome_univoco(directory, prefisso, estensione):
    pattern = os.path.join(directory, f"{prefisso}_*.{estensione}")
    esistenti = glob.glob(pattern)
    max_num = 0
    for f in esistenti:
        nome_file = os.path.basename(f)
        parts = nome_file.rsplit('_', 1)
        if len(parts) == 2:
            num_part = parts[1].split('.')[0]
            if num_part.isdigit():
                max_num = max(max_num, int(num_part))
    nuovo_num = max_num + 1
    return f"{prefisso}_{nuovo_num:04d}.{estensione}"

def elenca_lora(cartella):
    estensioni = (".safetensors", ".ckpt")
    files = []
    cartelle = cartella if isinstance(cartella, list) else [cartella]

    for percorso in cartelle:
        if not percorso:
            continue
        percorso_pulito = os.path.abspath(percorso).rstrip("\\/")
        if not os.path.exists(percorso_pulito):
            continue
        try:
            nome_cartella = os.path.basename(percorso_pulito)
            trovati = [f for f in os.listdir(percorso_pulito) if f.lower().endswith(estensioni)]
            for f in trovati:
                files.append(f"{nome_cartella}/{f}")
        except PermissionError:
            continue
    return sorted(files)

def elenca_suggerimenti(cartella):
    if not os.path.exists(cartella):
        try:
            os.makedirs(cartella, exist_ok=True)
        except Exception:
            return []
    file_txt = [os.path.splitext(f)[0] for f in os.listdir(cartella) if f.endswith(".txt")]
    return sorted(file_txt) if file_txt else []

def leggi_contenuto_suggerimento(cartella, nome_file):
    if not nome_file or str(nome_file).strip() in {"-", "Vuoto", "None", "Nessuno", "- Nessuno -"}:
        return ""
    path_completo = os.path.join(cartella, f"{nome_file}.txt")
    if os.path.exists(path_completo):
        try:
            with open(path_completo, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""

def inizializza_prompt_sistema():
    os.makedirs(SUGGESTION_VISION_DIR, exist_ok=True)
    os.makedirs(SUGGESTION_DIRECTION_DIR, exist_ok=True)
    os.makedirs(SUGGESTION_SYSTEM_DIR, exist_ok=True)
    os.makedirs(SUGGESTION_SCREENPLAY_DIR, exist_ok=True)
    os.makedirs(SUGGESTION_STORYBOARD_DIR, exist_ok=True)
    os.makedirs(SUGGESTION_SEQUENCE_DIR, exist_ok=True)
    os.makedirs(PROMPT_IMG_DIR, exist_ok=True)
    os.makedirs(PROMPT_VID_DIR, exist_ok=True)
    os.makedirs(os.path.join(STUDIO_ROOT_DIR, "workflows"), exist_ok=True)

    if not os.path.exists(WF_ZIMAGE_FILE):
        log.registra(f"⚠️ WARNING: Missing workflow file '{WF_ZIMAGE_FILE}'!", "ERROR")
    if not os.path.exists(WF_LTX_FILE):
        log.registra(f"⚠️ WARNING: Missing workflow file '{WF_LTX_FILE}'!", "ERROR")
    if not os.path.exists(WF_MINIMAX_FILE):
        log.registra(f"⚠️ WARNING: Missing workflow file '{WF_MINIMAX_FILE}'!", "ERROR")
    if not os.path.exists(WF_KREA2_FILE):
        log.registra(f"⚠️ WARNING: Missing workflow file '{WF_KREA2_FILE}'!", "ERROR")

    try:
        from core.suggestions import inizializza_suggerimenti
        inizializza_suggerimenti(STUDIO_ROOT_DIR, log_func=None)
    except Exception as e:
        log.registra(f"Error during suggestions initialization: {e}", "WARNING")

inizializza_prompt_sistema()
