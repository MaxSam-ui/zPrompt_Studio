# generators/workflow.py

import json
import os
import random
from core import config, log
from core.workflow_registry import ottieni_parametri_avanzati_workflow

from generators.workflow_video import prepara_workflow_ltx_video, prepara_workflow_minimax_h3
from generators.metadata_extractor import estrai_info_da_immagine

NODO_UNET = "1"
NODO_CLIP = "2"
NODO_VAE = "3"
NODO_LATENTE = "4"
NODO_PROMPT = "5"
NODO_ZERO_OUT = "6"
NODO_SAMPLER = "7"
NODO_VAE_DECODE = "8"
NODO_SAVE_IMAGE = "9"


def valida_workflow(wf, tipo="zimage"):
    if tipo in ["krea2_edit", "krea2", "flux2"]:
        return []
    errori = []
    nodi_richiesti = [NODO_UNET, NODO_CLIP, NODO_VAE, NODO_PROMPT]
    for nodo in nodi_richiesti:
        if nodo not in wf:
            errori.append(f"Nodo standard mancante: {nodo}")
    if errori:
        for e in errori:
            log.registra(f"Workflow validation ERROR ({tipo}): {e}", "ERROR")
    return errori


def _imposta_risoluzione_standard(wf, larghezza, altezza, copie):
    node = wf.get(NODO_LATENTE)
    if node and "inputs" in node:
        node["inputs"]["width"] = int(larghezza)
        node["inputs"]["height"] = int(altezza)
        node["inputs"]["batch_size"] = int(copie)


def _imposta_prompt_standard(wf, testo):
    node = wf.get(NODO_PROMPT)
    if node and "inputs" in node:
        if "text" in node["inputs"]:
            node["inputs"]["text"] = testo
        elif "prompt" in node["inputs"]:
            node["inputs"]["prompt"] = testo


def _calcola_basi_hires(w_target, h_target, base_max=768):
    w_t = int(w_target)
    h_t = int(h_target)
    if w_t <= base_max and h_t <= base_max:
        return w_t, h_t, 1.0
    rapporto = w_t / h_t
    if w_t >= h_t:
        w_b = base_max
        h_b = int(base_max / rapporto)
    else:
        h_b = base_max
        w_b = int(base_max * rapporto)
    w_base = max(64, (w_b // 64) * 64)
    h_base = max(64, (h_b // 64) * 64)
    scala_finale = round(w_t / w_base, 4)
    return w_base, h_base, scala_finale


def _applica_lora_cascata(wf, dati_lora, tipo_modello="zimage"):
    nodi_lora = ["15", "16", "17"]
    lora_attivi = []
    for idx, nodo_id in enumerate(nodi_lora):
        if idx < len(dati_lora):
            name, strength = dati_lora[idx]
            # PROTEZIONE SICURA: Solo se 'name' è una stringa valida e non numerica/vuota
            if name and isinstance(name, str) and name.strip() not in ["-", "Nessuno", "None", "nessuno", "none"]:
                try:
                    val_strength = float(strength)
                except (ValueError, TypeError):
                    val_strength = 0.0
                if val_strength > 0.0:
                    nome_formattato = name.replace("/", "\\") if os.name == 'nt' else name.replace("\\", "/")
                    lora_attivi.append((nodo_id, nome_formattato, val_strength))
            
    for nodo_id in nodi_lora:
        if nodo_id in wf: 
            del wf[nodo_id]

    if not lora_attivi:
        if tipo_modello == "zimage":
            if "10" in wf: wf["10"]["inputs"]["model"] = [NODO_UNET, 0]
        elif tipo_modello == "flux2":
            if "13" in wf: wf["13"]["inputs"]["model"] = [NODO_UNET, 0]
            if NODO_PROMPT in wf: wf[NODO_PROMPT]["inputs"]["clip"] = [NODO_CLIP, 0]
        elif tipo_modello == "krea2":
            source_m = ["11", 0] if "11" in wf else [NODO_UNET, 0]
            if NODO_SAMPLER in wf: wf[NODO_SAMPLER]["inputs"]["model"] = source_m
            if "10" in wf: wf["10"]["inputs"]["model"] = source_m
            if NODO_PROMPT in wf: wf[NODO_PROMPT]["inputs"]["clip"] = [NODO_CLIP, 0]
        return

    primo_id, primo_nome, primo_forza = lora_attivi[0]
    
    if tipo_modello == "zimage":
        wf[primo_id] = {
            "class_type": "LoraLoaderModelOnly", 
            "inputs": {
                "lora_name": primo_nome, 
                "strength_model": primo_forza, 
                "model": [NODO_UNET, 0]
            }, 
            "_meta": {"title": f"LoRA 1: {primo_nome}"}
        }
    else:
        source_model = ["11", 0] if (tipo_modello == "krea2" and "11" in wf) else [NODO_UNET, 0]
        wf[primo_id] = {
            "class_type": "LoraLoader", 
            "inputs": {
                "lora_name": primo_nome, 
                "strength_model": primo_forza, 
                "strength_clip": primo_forza,
                "model": source_model,
                "clip": [NODO_CLIP, 0]
            }, 
            "_meta": {"title": f"LoRA 1: {primo_nome}"}
        }
    
    for i in range(1, len(lora_attivi)):
        nodo_id, name, strength = lora_attivi[i]
        precedente_id = lora_attivi[i-1][0]
        
        if tipo_modello == "zimage":
            wf[nodo_id] = {
                "class_type": "LoraLoaderModelOnly", 
                "inputs": {
                    "lora_name": name, 
                    "strength_model": strength, 
                    "model": [precedente_id, 0]
                }, 
                "_meta": {"title": f"LoRA {i+1}: {name}"}
            }
        else:
            wf[nodo_id] = {
                "class_type": "LoraLoader", 
                "inputs": {
                    "lora_name": name, 
                    "strength_model": strength, 
                    "strength_clip": strength,
                    "model": [precedente_id, 0],
                    "clip": [precedente_id, 1]
                }, 
                "_meta": {"title": f"LoRA {i+1}: {name}"}
            }
        
    ultimo_id = lora_attivi[-1][0]
    
    if tipo_modello == "zimage":
        if "10" in wf: wf["10"]["inputs"]["model"] = [ultimo_id, 0]
    elif tipo_modello == "flux2":
        if "13" in wf: wf["13"]["inputs"]["model"] = [ultimo_id, 0]
        if NODO_PROMPT in wf: wf[NODO_PROMPT]["inputs"]["clip"] = [ultimo_id, 1]
    elif tipo_modello == "krea2":
        if NODO_SAMPLER in wf: wf[NODO_SAMPLER]["inputs"]["model"] = [ultimo_id, 0]
        if "10" in wf: wf["10"]["inputs"]["model"] = [ultimo_id, 0]
        if NODO_PROMPT in wf: wf[NODO_PROMPT]["inputs"]["clip"] = [ultimo_id, 1]


def prepara_workflow_z_image(file_path, prompt_testo, l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
                              larghezza, altezza, copie, steps=25, sampler_name="dpmpp_2m_sde",
                              scheduler="sgm_uniform", hires_steps=13, hires_denoise=0.3, hires_scale=1.5,
                              seed_mode="randomize", custom_seed=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    if valida_workflow(wf, "zimage"): 
        return None
    
    p_adv = ottieni_parametri_avanzati_workflow().get("zimage", {})
    base_max = p_adv.get("hires_base_max", 768)
    upscale_method = p_adv.get("hires_upscale_method", "nearest-exact")
    shift_val = p_adv.get("auraflow_shift", 5)
    cfg_val = getattr(config, "Z_IMAGE_CFG", p_adv.get("default_cfg", 1.0))
    
    if float(hires_scale) <= 1.0:
        w_base, h_base, scala_proporzionale = int(larghezza), int(altezza), 1.0
    else:
        w_base, h_base, scala_proporzionale = _calcola_basi_hires(larghezza, altezza, base_max=base_max)

    _imposta_risoluzione_standard(wf, w_base, h_base, copie)
    _imposta_prompt_standard(wf, prompt_testo)
    
    nuovo_seed = int(str(custom_seed).strip()) if (seed_mode == "fixed" and custom_seed is not None) else random.randint(1000000000000, 9999999999999)

    if "10" in wf:
        wf["10"]["inputs"]["shift"] = shift_val
    
    if NODO_SAMPLER in wf:
        wf[NODO_SAMPLER]["inputs"]["steps"] = int(steps)
        wf[NODO_SAMPLER]["inputs"]["sampler_name"] = sampler_name
        wf[NODO_SAMPLER]["inputs"]["scheduler"] = scheduler
        wf[NODO_SAMPLER]["inputs"]["seed"] = nuovo_seed
        wf[NODO_SAMPLER]["inputs"]["cfg"] = cfg_val
        
    if "12" in wf:
        wf["12"]["inputs"]["steps"] = int(hires_steps)
        wf["12"]["inputs"]["sampler_name"] = sampler_name
        wf["12"]["inputs"]["scheduler"] = scheduler
        wf["12"]["inputs"]["denoise"] = hires_denoise
        wf["12"]["inputs"]["seed"] = nuovo_seed
        wf["12"]["inputs"]["cfg"] = cfg_val
        
    for node_id, node_info in wf.items():
        if isinstance(node_info, dict) and node_info.get("class_type") in ["LatentUpscaleBy", "ImageScaleBy", "LatentUpscale", "ImageScale"]:
            node_info["inputs"]["upscale_method"] = upscale_method
            # Explicit dimensions avoid aspect drift from latent rounding,
            # especially on wide storyboard canvases and portrait images.
            if node_info["class_type"].endswith("By"):
                node_info["class_type"] = node_info["class_type"][:-2]
            node_info["inputs"].pop("scale_by", None)
            node_info["inputs"].pop("scale_factor", None)
            node_info["inputs"].update(width=int(larghezza), height=int(altezza), crop="disabled")
    
    _applica_lora_cascata(wf, [(l1_n, l1_s), (l2_n, l2_s), (l3_n, l3_s)], tipo_modello="zimage")
    return wf


def prepara_workflow_img2img_z_image(file_path, input_image_filename, prompt_testo, steps=25, sampler_name="dpmpp_2m_sde",
                                     scheduler="sgm_uniform", denoise=0.35, seed=None,
                                     l1_n="-", l1_s=1.0, l2_n="-", l2_s=1.0, l3_n="-", l3_s=1.0,
                                     larghezza=1024, altezza=1024, scale_factor=1.0):
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    if valida_workflow(wf, "zimage"): return None

    p_adv = ottieni_parametri_avanzati_workflow().get("zimage", {})
    shift_val = p_adv.get("auraflow_shift", 5)
    cfg_val = getattr(config, "Z_IMAGE_CFG", p_adv.get("default_cfg", 1.0))
        
    wf["90"] = {"class_type": "LoadImage", "inputs": {"image": input_image_filename}, "_meta": {"title": "Refine Input Image"}}
    wf["91"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["90", 0], "vae": [NODO_VAE, 0]}, "_meta": {"title": "Refine VAE Encode"}}
    
    if NODO_SAMPLER in wf: del wf[NODO_SAMPLER]
    if NODO_LATENTE in wf: del wf[NODO_LATENTE]

    if "10" in wf:
        wf["10"]["inputs"]["shift"] = shift_val
    
    if "11" in wf:
        wf["11"]["inputs"]["samples"] = ["91", 0]
        if "scale_by" in wf["11"]["inputs"]:
            wf["11"]["inputs"]["scale_by"] = float(scale_factor)
        elif "scale_factor" in wf["11"]["inputs"]:
            wf["11"]["inputs"]["scale_factor"] = float(scale_factor)
            
    _imposta_prompt_standard(wf, prompt_testo)
    
    if "12" in wf:
        if "11" in wf:
            wf["12"]["inputs"]["latent_image"] = ["11", 0]
        else:
            wf["12"]["inputs"]["latent_image"] = ["91", 0]
            
        wf["12"]["inputs"]["denoise"] = float(denoise)
        wf["12"]["inputs"]["steps"] = int(steps)
        wf["12"]["inputs"]["sampler_name"] = sampler_name
        wf["12"]["inputs"]["scheduler"] = scheduler
            
        if seed is not None: wf["12"]["inputs"]["seed"] = int(seed)
        wf["12"]["inputs"]["cfg"] = cfg_val
    
    _applica_lora_cascata(wf, [(l1_n, l1_s), (l2_n, l2_s), (l3_n, l3_s)], tipo_modello="zimage")
    return wf


def prepara_workflow_flux2(file_path, prompt_testo, l1_n, l1_s, l2_n, l2_s, l3_n, l3_s, larghezza, altezza, copie, steps=4, sampler_name="euler", scheduler="sgm_uniform", hires_steps=13, hires_denoise=0.3, seed_mode="randomize", custom_seed=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    if valida_workflow(wf, "flux2"): return None

    p_adv = ottieni_parametri_avanzati_workflow().get("flux2", {})
    cfg_val = p_adv.get("default_cfg", 1.0)
    
    _imposta_risoluzione_standard(wf, larghezza, altezza, copie)
    _imposta_prompt_standard(wf, prompt_testo)

    if "13" in wf:
        wf["13"]["inputs"]["cfg"] = cfg_val
    
    if "10" in wf:
        wf["10"]["inputs"]["steps"] = int(steps)
        wf["10"]["inputs"]["width"] = int(larghezza)
        wf["10"]["inputs"]["height"] = int(altezza)
        
    nuovo_seed = int(str(custom_seed).strip()) if (seed_mode == "fixed" and custom_seed is not None) else random.randint(1000000000000, 9999999999999)
    if "11" in wf: wf["11"]["inputs"]["noise_seed"] = nuovo_seed
    
    if "12" in wf:
        nome_campionatore = "euler"
        if "uni" in sampler_name.lower(): nome_campionatore = "uni_pc"
        elif "ddim" in sampler_name.lower(): nome_campionatore = "ddim"
        elif "heun" in sampler_name.lower(): nome_campionatore = "heun"
        elif "dpm" in sampler_name.lower(): nome_campionatore = "dpmpp_2m"
        wf["12"]["inputs"]["sampler_name"] = nome_campionatore
        
    for node_id, node_data in wf.items():
        if isinstance(node_data, dict) and "inputs" in node_data:
            if "scheduler" in node_data["inputs"]:
                node_data["inputs"]["scheduler"] = scheduler
                
    _applica_lora_cascata(wf, [(l1_n, l1_s), (l2_n, l2_s), (l3_n, l3_s)], tipo_modello="flux2")
    return wf


def prepara_workflow_img2img_flux2(file_path, input_image_filename, prompt_testo, steps=4, sampler_name="euler",
                                   scheduler="sgm_uniform", denoise=0.35, seed=None,
                                   l1_n="-", l1_s=1.0, l2_n="-", l2_s=1.0, l3_n="-", l3_s=1.0,
                                   larghezza=1024, altezza=1024):
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    if valida_workflow(wf, "flux2"): return None

    p_adv = ottieni_parametri_avanzati_workflow().get("flux2", {})
    cfg_val = p_adv.get("default_cfg", 1.0)
    
    wf["90"] = {"class_type": "LoadImage", "inputs": {"image": input_image_filename}, "_meta": {"title": "Refine Input Image"}}
    wf["91"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["90", 0], "vae": [NODO_VAE, 0]}, "_meta": {"title": "Refine VAE Encode"}}
    
    if NODO_LATENTE in wf: del wf[NODO_LATENTE]
    _imposta_prompt_standard(wf, prompt_testo)
    
    if "10" in wf: 
        wf["10"] = {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": [NODO_UNET, 0],
                "scheduler": scheduler,
                "steps": int(steps),
                "denoise": float(denoise)
            },
            "_meta": {"title": "BasicScheduler (Img2Img)"}
        }
        
    if "13" in wf: wf["13"]["inputs"]["cfg"] = cfg_val
    if NODO_SAMPLER in wf: wf[NODO_SAMPLER]["inputs"]["latent_image"] = ["91", 0]
    if seed is not None and "11" in wf: wf["11"]["inputs"]["noise_seed"] = int(seed)
    
    if "12" in wf:
        nome_campionatore = "euler"
        if "uni" in sampler_name.lower(): nome_campionatore = "uni_pc"
        elif "ddim" in sampler_name.lower(): nome_campionatore = "ddim"
        elif "heun" in sampler_name.lower(): nome_campionatore = "heun"
        elif "dpm" in sampler_name.lower(): nome_campionatore = "dpmpp_2m"
        wf["12"]["inputs"]["sampler_name"] = nome_campionatore

    for node_id, node_data in wf.items():
        if isinstance(node_data, dict) and "inputs" in node_data:
            if "scheduler" in node_data["inputs"] and node_id != "10":
                node_data["inputs"]["scheduler"] = scheduler

    _applica_lora_cascata(wf, [(l1_n, l1_s), (l2_n, l2_s), (l3_n, l3_s)], tipo_modello="flux2")

    if "10" in wf and "13" in wf:
        wf["10"]["inputs"]["model"] = wf["13"]["inputs"]["model"]

    return wf


def prepara_workflow_krea2(file_path, prompt_testo, l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
                           larghezza, altezza, copie, steps=8, sampler_name="euler",
                           scheduler="normal", seed_mode="randomize", custom_seed=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    
    if valida_workflow(wf, "krea2"):
        return None

    p_adv = ottieni_parametri_avanzati_workflow().get("krea2", {})
    p_enh = p_adv.get("enhancer", {})
    p_pass1 = p_adv.get("pass1_sampler", {})
    p_pass2 = p_adv.get("pass2_sampler", {})
        
    nuovo_seed = int(str(custom_seed).strip()) if (seed_mode == "fixed" and custom_seed is not None) else random.randint(1000000000000, 9999999999999)

    _imposta_risoluzione_standard(wf, larghezza, altezza, copie)
    _imposta_prompt_standard(wf, prompt_testo)

    if "11" in wf:
        wf["11"]["inputs"]["enabled"] = p_enh.get("enabled", True)
        wf["11"]["inputs"]["strength"] = p_enh.get("strength", 1.5)
        wf["11"]["inputs"]["debug"] = p_enh.get("debug", False)

    if NODO_SAMPLER in wf:
        wf[NODO_SAMPLER]["inputs"]["steps"] = int(steps)
        wf[NODO_SAMPLER]["inputs"]["seed"] = nuovo_seed
        wf[NODO_SAMPLER]["inputs"]["sampler_name"] = sampler_name
        wf[NODO_SAMPLER]["inputs"]["scheduler"] = scheduler
        wf[NODO_SAMPLER]["inputs"]["eta"] = p_pass1.get("eta", 0.0)
        wf[NODO_SAMPLER]["inputs"]["steps_to_run"] = p_pass1.get("steps_to_run", -1)
        wf[NODO_SAMPLER]["inputs"]["sampler_mode"] = p_pass1.get("sampler_mode", "standard")
        wf[NODO_SAMPLER]["inputs"]["bongmath"] = p_pass1.get("bongmath", True)
        wf[NODO_SAMPLER]["inputs"]["cfg"] = p_pass1.get("cfg", 1.0)
        wf[NODO_SAMPLER]["inputs"]["denoise"] = p_pass1.get("denoise", 1.0)

    if "10" in wf:
        wf["10"]["inputs"]["steps"] = int(steps)
        wf["10"]["inputs"]["seed"] = nuovo_seed
        wf["10"]["inputs"]["eta"] = p_pass2.get("eta", 0.9)
        wf["10"]["inputs"]["steps_to_run"] = p_pass2.get("steps_to_run", 2)
        wf["10"]["inputs"]["sampler_name"] = p_pass2.get("sampler_name", "exponential/res_2s")
        wf["10"]["inputs"]["scheduler"] = p_pass2.get("scheduler", "bong_tangent")
        wf["10"]["inputs"]["denoise"] = p_pass2.get("denoise", 0.2)
        wf["10"]["inputs"]["cfg"] = p_pass2.get("cfg", 1.0)
        wf["10"]["inputs"]["sampler_mode"] = p_pass2.get("sampler_mode", "standard")
        wf["10"]["inputs"]["bongmath"] = p_pass2.get("bongmath", True)

    _applica_lora_cascata(wf, [(l1_n, l1_s), (l2_n, l2_s), (l3_n, l3_s)], tipo_modello="krea2")
    return wf


def prepara_workflow_img2img_krea2(file_path, input_image_filename, prompt_testo, steps=8, sampler_name="euler",
                                   scheduler="normal", denoise=0.35, seed=None,
                                   l1_n="-", l1_s=1.0, l2_n="-", l2_s=1.0, l3_n="-", l3_s=1.0,
                                   larghezza=1024, altezza=1024):
    """Workflow Refine per Krea-2 con disattivazione Enhancer per prevenire fireflies/punti luminosi."""
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)

    if valida_workflow(wf, "krea2"):
        return None

    p_adv = ottieni_parametri_avanzati_workflow().get("krea2", {})
    p_pass1 = p_adv.get("pass1_sampler", {})
    p_pass2 = p_adv.get("pass2_sampler", {})
        
    wf["90"] = {"class_type": "LoadImage", "inputs": {"image": input_image_filename}, "_meta": {"title": "Refine Input Image"}}
    wf["91"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["90", 0], "vae": [NODO_VAE, 0]}, "_meta": {"title": "Refine VAE Encode"}}
    
    if NODO_LATENTE in wf: del wf[NODO_LATENTE]
    _imposta_prompt_standard(wf, prompt_testo)

    # DISABILITATO NEL REFINE: Evita la sovra-amplificazione del rumore che crea i punti luminosi
    if "11" in wf:
        wf["11"]["inputs"]["enabled"] = False
        wf["11"]["inputs"]["strength"] = 1.0
        wf["11"]["inputs"]["debug"] = False
    
    if NODO_SAMPLER in wf:
        wf[NODO_SAMPLER]["inputs"]["latent_image"] = ["91", 0]
        wf[NODO_SAMPLER]["inputs"]["denoise"] = float(denoise)
        wf[NODO_SAMPLER]["inputs"]["steps"] = int(steps)
        if seed is not None: wf[NODO_SAMPLER]["inputs"]["seed"] = int(seed)
        wf[NODO_SAMPLER]["inputs"]["eta"] = p_pass1.get("eta", 0.0)
        wf[NODO_SAMPLER]["inputs"]["steps_to_run"] = p_pass1.get("steps_to_run", -1)
        wf[NODO_SAMPLER]["inputs"]["sampler_mode"] = p_pass1.get("sampler_mode", "standard")
        wf[NODO_SAMPLER]["inputs"]["bongmath"] = p_pass1.get("bongmath", True)
        wf[NODO_SAMPLER]["inputs"]["cfg"] = p_pass1.get("cfg", 1.0)
        
    if "10" in wf:
        wf["10"]["inputs"]["steps"] = int(steps)
        if seed is not None: wf["10"]["inputs"]["seed"] = int(seed)
        wf["10"]["inputs"]["eta"] = 0.0  # Azzerato nel Pass 2 per evitare rumore residuo puntiforme
        wf["10"]["inputs"]["steps_to_run"] = 2
        wf["10"]["inputs"]["sampler_name"] = p_pass2.get("sampler_name", "exponential/res_2s")
        wf["10"]["inputs"]["scheduler"] = p_pass2.get("scheduler", "bong_tangent")
        wf["10"]["inputs"]["denoise"] = min(float(denoise) * 0.5, 0.15)
        wf["10"]["inputs"]["cfg"] = p_pass2.get("cfg", 1.0)
        wf["10"]["inputs"]["sampler_mode"] = p_pass2.get("sampler_mode", "standard")
        wf["10"]["inputs"]["bongmath"] = p_pass2.get("bongmath", True)
        
    _applica_lora_cascata(wf, [(l1_n, l1_s), (l2_n, l2_s), (l3_n, l3_s)], tipo_modello="krea2")
    return wf


def prepara_workflow_krea2_edit(file_path, input_image_filename, prompt_testo, steps, sampler_name, scheduler, seed, grounding_px, height=1280, krea2_edit_lora_strength=0.75):
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
        
    if valida_workflow(wf, "krea2_edit"):
        return None

    p_adv = ottieni_parametri_avanzati_workflow().get("krea2_edit", {})
    p_res = p_adv.get("resize", {})
    p_tile = p_adv.get("tiled_vae", {})

    if "10" in wf:
        wf["10"]["inputs"]["image"] = input_image_filename
        
    if "15" in wf:
        wf["15"]["inputs"]["strength_model"] = float(krea2_edit_lora_strength)
        
    if "11" in wf:
        wf["11"]["inputs"]["resize_type.height"] = int(height)
        wf["11"]["inputs"]["resize_type"] = p_res.get("resize_type", "scale height")
        wf["11"]["inputs"]["scale_method"] = p_res.get("scale_method", "area")
        
    if NODO_PROMPT in wf:
        wf[NODO_PROMPT]["inputs"]["prompt"] = prompt_testo
        wf[NODO_PROMPT]["inputs"]["grounding_px"] = int(grounding_px)
        
    if "18" in wf:
        wf["18"]["inputs"]["prompt"] = prompt_testo
        wf["18"]["inputs"]["grounding_px"] = int(grounding_px)
        
    if NODO_SAMPLER in wf:
        wf[NODO_SAMPLER]["inputs"]["steps"] = int(steps)
        wf[NODO_SAMPLER]["inputs"]["sampler_name"] = sampler_name
        wf[NODO_SAMPLER]["inputs"]["scheduler"] = scheduler
        wf[NODO_SAMPLER]["inputs"]["seed"] = int(seed)
        wf[NODO_SAMPLER]["inputs"]["cfg"] = 1.0
        wf[NODO_SAMPLER]["inputs"]["denoise"] = 1.0

    if NODO_VAE_DECODE in wf:
        wf[NODO_VAE_DECODE]["inputs"]["upscale"] = p_tile.get("upscale", -1)
        wf[NODO_VAE_DECODE]["inputs"]["tile"] = p_tile.get("tile", False)
        wf[NODO_VAE_DECODE]["inputs"]["tile_size"] = p_tile.get("tile_size", 512)
        wf[NODO_VAE_DECODE]["inputs"]["overlap"] = p_tile.get("overlap", 64)
        wf[NODO_VAE_DECODE]["inputs"]["temporal_size"] = p_tile.get("temporal_size", 4096)
        wf[NODO_VAE_DECODE]["inputs"]["temporal_overlap"] = p_tile.get("temporal_overlap", 64)
        
    return wf


def prepara_workflow_qwen21_edit(file_path, input_filename, prompt, steps, sampler_name, scheduler, seed, loras=None):
    """Bind the cleaned Qwen edit graph without inheriting Krea parameters."""
    with open(file_path, encoding="utf-8") as handle:
        wf = json.load(handle)
    for key, expected in {"56": "LoadImage", "59": "TextEncodeQwenImage21", "61": "KSampler", "65": "SaveImage"}.items():
        if wf.get(key, {}).get("class_type") != expected:
            raise ValueError(f"Qwen Edit: incompatible node {key}; expected {expected}")
    if not prompt.strip():
        raise ValueError("Qwen Edit: empty edit instruction")
    if not 0 <= int(seed) <= 18446744073709551615:
        raise ValueError("Qwen Edit: invalid seed")
    wf["56"]["inputs"]["image"] = input_filename
    wf["59"]["inputs"]["prompt"] = prompt
    wf["61"]["inputs"].update(seed=int(seed), steps=int(steps), sampler_name=sampler_name, scheduler=scheduler)
    wf["65"]["inputs"]["filename_prefix"] = "zprompt_qwen21_edit"
    model = wf["61"]["inputs"]["model"]
    for name, strength in loras or []:
        if not name or name == "-" or float(strength) == 0:
            continue
        strength = float(strength)
        if not 0 <= strength <= 1.5:
            raise ValueError("Qwen Edit: invalid LoRA strength")
        node_id = str(max((int(k) for k in wf if k.isdigit()), default=0) + 1)
        wf[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": model, "lora_name": str(name).replace("\\", "/"), "strength_model": strength}}
        model = [node_id, 0]
    wf["61"]["inputs"]["model"] = model
    return wf
