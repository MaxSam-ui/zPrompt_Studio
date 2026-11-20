# core/workflow_registry.py

import os
import json
from typing import Dict, Any, List, Tuple
from core import config, log

PATH_WORKFLOW_PARAMS = os.path.join(config.STUDIO_ROOT_DIR, "config", "workflow_params.json")

DEFAULT_WORKFLOW_PARAMS = {
  "zimage": {
    "auraflow_shift": 5,
    "hires_base_max": 768,
    "hires_upscale_method": "nearest-exact",
    "default_cfg": 1.0
  },
  "flux2": {
    "default_cfg": 1.0
  },
  "krea2": {
    "enhancer": {
      "enabled": True,
      "strength": 1.5,
      "debug": False
    },
    "pass1_sampler": {
      "eta": 0.0,
      "steps_to_run": -1,
      "sampler_mode": "standard",
      "bongmath": True,
      "cfg": 1.0,
      "denoise": 1.0
    },
    "pass2_sampler": {
      "eta": 0.9,
      "steps_to_run": 2,
      "sampler_name": "exponential/res_2s",
      "scheduler": "bong_tangent",
      "denoise": 0.2,
      "cfg": 1.0,
      "sampler_mode": "standard",
      "bongmath": True
    }
  },
  "krea2_edit": {
    "resize": {
      "resize_type": "scale height",
      "scale_method": "area"
    },
    "tiled_vae": {
      "upscale": -1,
      "tile": False,
      "tile_size": 512,
      "overlap": 64,
      "temporal_size": 4096,
      "temporal_overlap": 64
    }
  },
  "ltx_video": {
    "stability_prefix": "",
    "fallback_negative_prompt": "unintended temporal flicker, accidental duplicate subjects, broken object continuity, compression artifacts, unintended watermark",
    "pass1_sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
    "pass2_sigmas": "0.85, 0.7250, 0.4219, 0.0",
    "preview_rate": 8,
    "feedforward": {
      "chunks": 1,
      "dim_threshold": 2048
    },
    "tiled_vae": {
      "tile_size": 1024,
      "overlap": 32,
      "temporal_size": 64,
      "temporal_overlap": 16
    },
    "guide_resize": {
      "scale_method": "lanczos",
      "crop": "center"
    },
    "video_format": {
      "bit_depth": 8,
      "device": "main_device"
    }
  },
  "minimax_h3": {
    "default_steps": 8,
    "default_denoise": 1.0,
    "default_scheduler": "beta",
    "video_format": {
      "bit_depth": 8
    }
  }
}


def ottieni_parametri_avanzati_workflow() -> Dict[str, Any]:
    """Legge il file da disco e ripristina la configurazione ottimizzata se non presente o corrotta."""
    if not os.path.exists(PATH_WORKFLOW_PARAMS):
        try:
            with open(PATH_WORKFLOW_PARAMS, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_WORKFLOW_PARAMS, f, indent=2, ensure_ascii=False)
            log.registra(f"Advanced parameters file created: {PATH_WORKFLOW_PARAMS}")
            return DEFAULT_WORKFLOW_PARAMS
        except Exception as e:
            log.registra(f"Unable to create workflow_params.json: {e}", "WARNING")
            return DEFAULT_WORKFLOW_PARAMS

    try:
        with open(PATH_WORKFLOW_PARAMS, "r", encoding="utf-8") as f:
            dati = json.load(f)
            if not dati or not isinstance(dati, dict):
                raise ValueError("File JSON vuoto o non valido")
            
            return dati
    except Exception as e:
        log.registra(f"Error reading workflow_params.json ({e}). Re-creating default configuration...", "WARNING")
        try:
            with open(PATH_WORKFLOW_PARAMS, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_WORKFLOW_PARAMS, f, indent=2, ensure_ascii=False)
            return DEFAULT_WORKFLOW_PARAMS
        except Exception:
            return DEFAULT_WORKFLOW_PARAMS


MODELLI_IMMAGINE: Dict[str, Dict[str, Any]] = {
    "Z-Image Turbo": {
        "wf_filename": "z_image_turbo_api.json",
        "lora_dirs_func": config.ottieni_lora_zimage_dirs,
        "steps": {"default": 8, "min": 5, "max": 25},
        "samplers": ["dpmpp_2m_sde", "euler_ancestral", "euler", "heun", "dpmpp_2m", "uni_pc"],
        "schedulers": ["sgm_uniform", "karras", "exponential", "beta", "simple", "normal"],
        "default_sampler": "dpmpp_2m_sde",
        "default_scheduler": "sgm_uniform",
        "has_hires_fix": True,
        "session_prefix": "_zimage"
    },
    "Flux.2 Klein": {
        "wf_filename": "flux2_klein_api.json",
        "lora_dirs_func": lambda: [config.ottieni_lora_flux2_dir()],
        "steps": {"default": 4, "min": 1, "max": 10},
        "samplers": ["euler", "heun", "dpmpp_2m", "ddim", "uni_pc"],
        "schedulers": ["beta", "normal", "simple", "sgm_uniform", "karras"],
        "default_sampler": "euler",
        "default_scheduler": "beta",
        "has_hires_fix": False,
        "session_prefix": "_flux2"
    },
    "Krea-2 Turbo": {
        "wf_filename": "krea2_turbo_api.json",
        "lora_dirs_func": lambda: [config.ottieni_lora_krea2_dir()],
        "steps": {"default": 8, "min": 1, "max": 20},
        "samplers": ["linear/euler", "exponential/res_2s", "res_2s", "exponential/res_3s", "linear/heun_2s", "multistep/dpmpp_2m", "exponential/ddim", "euler"],
        "schedulers": ["simple", "bong_tangent", "normal", "sgm_uniform", "karras", "exponential", "beta"],
        "default_sampler": "linear/euler",
        "default_scheduler": "simple",
        "has_hires_fix": False,
        "session_prefix": "_krea2"
    }
}

def ottieni_config_modifica_immagine(nome_modello="Krea-2 Turbo") -> Dict[str, Any]:
    """Edit uses standard KSampler, not the Turbo workflow's RES4LYF sampler."""
    if nome_modello == "Qwen Image 2.1":
        return {"wf_filename": "qwen_image_2.1_edit_api.json", "session_prefix": "_qwen21_edit",
                "steps": {"default": 30, "min": 1, "max": 60},
                "samplers": ["euler", "heun", "dpmpp_2m"], "schedulers": ["simple", "normal", "beta"],
                "default_sampler": "euler", "default_scheduler": "simple", "has_hires_fix": False,
                "lora_dirs_func": lambda: [config.ottieni_lora_qwen21_dir()]}
    cfg = dict(MODELLI_IMMAGINE["Krea-2 Turbo"])
    cfg["samplers"] = ["euler", "euler_ancestral", "heun", "dpmpp_2m", "dpmpp_2m_sde", "ddim", "uni_pc", "lcm", "er_sde"]
    cfg["default_sampler"] = "euler"
    return cfg


MODELLI_VIDEO: Dict[str, Dict[str, Any]] = {
    "LTX-Video 2.5": {
        "wf_filename": "ltx2.5_api.json",
        "lora_dirs_func": lambda: [config.ottieni_lora_ltx_dir()],
        "fps_choices": ["16", "24", "30", "60"],
        "default_fps": "24",
        "aspect_ratios": ["16:9", "9:16", "4:3", "3:4", "1:1"],
        "default_aspect_ratio": "16:9",
        "resolutions": ["256p", "360p", "480p", "720p", "1080p"],
        "default_resolution": "480p",
        "cfg": {"default": 3.0, "min": 1.0, "max": 10.0},
        "strength": {"default": 0.90, "min": 0.0, "max": 1.0},
        "compression": {"default": 15, "min": 0, "max": 50},
        "session_prefix": "_ltx_video"
    },
    "MiniMax H3": {
        "wf_filename": "minimax_h3_api.json",
        "lora_dirs_func": lambda: [config.ottieni_lora_minimax_dir()],
        "fps_choices": ["16", "24", "30", "60"],
        "default_fps": "24",
        "aspect_ratios": ["16:9", "9:16", "4:3", "3:4", "1:1"],
        "default_aspect_ratio": "16:9",
        "resolutions": ["256p", "360p", "480p", "720p", "1080p"],
        "default_resolution": "480p",
        "steps": {"default": 4, "min": 1, "max": 20},
        "schedulers": ["simple", "normal", "sgm_uniform", "karras", "exponential", "beta", "bong_tangent"],
        "default_scheduler": "simple",
        "session_prefix": "_minimax_h3"
    }
}

def elenca_modelli_immagine() -> List[str]:
    return list(MODELLI_IMMAGINE.keys())

def ottieni_config_modello_immagine(nome_modello: str) -> Dict[str, Any]:
    if nome_modello == "Qwen Image 2.1":
        return ottieni_config_modifica_immagine(nome_modello)
    return MODELLI_IMMAGINE.get(nome_modello, MODELLI_IMMAGINE["Z-Image Turbo"])

def ottieni_choices_sampler_immagine(nome_modello: str) -> List[str]:
    cfg = ottieni_config_modello_immagine(nome_modello)
    return cfg.get("samplers", ["dpmpp_2m_sde", "euler"])

def ottieni_choices_scheduler_immagine(nome_modello: str) -> List[str]:
    cfg = ottieni_config_modello_immagine(nome_modello)
    return cfg.get("schedulers", ["sgm_uniform", "normal"])

def ottieni_steps_range_immagine(nome_modello: str) -> Dict[str, Any]:
    cfg = ottieni_config_modello_immagine(nome_modello)
    return cfg.get("steps", {"default": 8, "min": 1, "max": 20})

def ottieni_lora_disponibili_immagine(nome_modello: str) -> List[str]:
    cfg = ottieni_config_modello_immagine(nome_modello)
    dirs_func = cfg.get("lora_dirs_func")
    if dirs_func:
        cartelle = dirs_func()
        return ["-"] + config.elenca_lora(cartelle)
    return ["-"]

def risolvi_percorso_json_immagine(nome_modello: str) -> str:
    cfg = ottieni_config_modello_immagine(nome_modello)
    base_dir = os.path.dirname(config.WF_ZIMAGE_FILE)
    fn = cfg.get("wf_filename", "z_image_turbo_api.json")
    return os.path.abspath(os.path.join(base_dir, fn))

def elenca_modelli_video() -> List[str]:
    return list(MODELLI_VIDEO.keys())

def ottieni_config_modello_video(nome_modello: str) -> Dict[str, Any]:
    return MODELLI_VIDEO.get(nome_modello, MODELLI_VIDEO["LTX-Video 2.5"])

def ottieni_lora_disponibili_video(nome_modello: str = "LTX-Video 2.5") -> List[str]:
    cfg = ottieni_config_modello_video(nome_modello)
    dirs_func = cfg.get("lora_dirs_func")
    if dirs_func:
        cartelle = dirs_func()
        return ["-"] + config.elenca_lora(cartelle)
    return ["-"]

def risolvi_percorso_json_video(nome_modello: str = "LTX-Video 2.5") -> str:
    cfg = ottieni_config_modello_video(nome_modello)
    base_dir = os.path.dirname(config.WF_ZIMAGE_FILE)
    fn = cfg.get("wf_filename", "ltx2.5_api.json")
    return os.path.abspath(os.path.join(base_dir, fn))


# =========================================================================
# UTILITY UNIFICATE LORA (Deduplicazione Centrale)
# =========================================================================

def normalizza_lora_per_scelte(valore: Any, scelte: List[str]) -> str:
    """Normalizza un valore LoRA confrontandolo con l'elenco delle scelte disponibili (gestendo separatori di percorso)."""
    if not valore or str(valore).strip() in ["-", "Nessuno", "None", "nessuno", "none"]:
        return "-"
    if valore in scelte:
        return str(valore)
    val_norm = str(valore).replace("\\", "/")
    for s_choice in scelte:
        if str(s_choice).replace("\\", "/") == val_norm:
            return str(s_choice)
    return "-"


def valida_e_normalizza_lora_modello(nome: Any, modello_attivo: str) -> str:
    """Valida se il file LoRA esiste sul disco per il modello attivo e ne restituisce il nome normalizzato."""
    if not nome or str(nome).strip() in ["-", "Nessuno", "None", "nessuno", "none"]:
        return "-"
    scelte = ottieni_lora_disponibili_immagine(modello_attivo)
    val_norm = normalizza_lora_per_scelte(nome, scelte)
    if val_norm != "-":
        return val_norm
    log.registra(f"LoRA '{nome}' not found/compatible with {modello_attivo}. It will be ignored.", "WARNING")
    return "-"


def estrai_lora_effettivi(
    count: int,
    l1_n: Any, l1_s: Any,
    l2_n: Any, l2_s: Any,
    l3_n: Any, l3_s: Any,
    modello_attivo: str = None
) -> Tuple[str, float, str, float, str, float]:
    """Estrae i LoRA effettivi in base al contatore slot attivi (1..3) e ne valida facoltativamente la presenza."""
    l1_n_eff = str(l1_n) if (count >= 1 and l1_n) else "-"
    l1_s_eff = float(l1_s) if (count >= 1 and l1_s is not None) else 0.0
    l2_n_eff = str(l2_n) if (count >= 2 and l2_n) else "-"
    l2_s_eff = float(l2_s) if (count >= 2 and l2_s is not None) else 0.0
    l3_n_eff = str(l3_n) if (count == 3 and l3_n) else "-"
    l3_s_eff = float(l3_s) if (count == 3 and l3_s is not None) else 0.0

    if modello_attivo:
        l1_n_eff = valida_e_normalizza_lora_modello(l1_n_eff, modello_attivo)
        l2_n_eff = valida_e_normalizza_lora_modello(l2_n_eff, modello_attivo)
        l3_n_eff = valida_e_normalizza_lora_modello(l3_n_eff, modello_attivo)

    return l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff
