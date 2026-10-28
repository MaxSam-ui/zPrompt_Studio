# generators/workflow_video.py

import json
import os
import random
import re
from core import config, log, sessione
from core.workflow_registry import ottieni_parametri_avanzati_workflow

NODO_UNET = "1"
NODO_CLIP = "2"
NODO_VAE = "3"
NODO_EMPTY_IMAGE = "4"
NODO_PROMPT = "5"
NODO_PROMPT_NEG = "6"
NODO_SAMPLER = "7"
NODO_VAE_DECODE = "8"
NODO_SAVE_VIDEO = "9"


def pulisci_tag_mismatch_ltx(prompt_testo: str) -> str:
    if not prompt_testo:
        return ""
    
    prompt_testo = re.sub(r'Stable geometry,?\s*clean edges,?\s*stable lines,?\s*no warping\.?', '', prompt_testo, flags=re.IGNORECASE)
    
    pattern_vuoti = r'\[(SPEECH|SOUNDS|VISUAL)\]\s*["\']?(?:None|none|Nessuno|nessuno|-)?["\']?\s*\[/\1\]'
    prompt_testo = re.sub(pattern_vuoti, '', prompt_testo, flags=re.IGNORECASE)
    
    prompt_testo = re.sub(r'\[SPEECH\]\s*\[/SPEECH\]', '', prompt_testo, flags=re.IGNORECASE)
    prompt_testo = re.sub(r'\[SOUNDS\]\s*\[/SOUNDS\]', '', prompt_testo, flags=re.IGNORECASE)
    
    return prompt_testo.strip()


def _applica_lora_cascata_ltx(wf, dati_lora):
    custom_lora_attivi = []
    for name, strength in dati_lora:
        if name and name not in ["-", "Nessuno", "None", "nessuno", "none"] and float(strength) > 0.0:
            nome_formattato = name.replace("/", "\\") if os.name == 'nt' else name.replace("\\", "/")
            custom_lora_attivi.append((nome_formattato, float(strength)))
            
    for extra_id in ["27_2", "27_3"]:
        if extra_id in wf:
            del wf[extra_id]
            
    base_model_source = ["21", 0] if "21" in wf else ["1", 0]

    if not custom_lora_attivi:
        if "27" in wf:
            del wf["27"]
        if "34" in wf:
            wf["34"]["inputs"]["model"] = base_model_source
        if "18" in wf and "model" in wf["18"]["inputs"]:
            wf["18"]["inputs"]["model"] = base_model_source
        if "45" in wf and "model" in wf["45"]["inputs"]:
            wf["45"]["inputs"]["model"] = base_model_source
        return

    ultimo_id = base_model_source
    for i, (name, strength) in enumerate(custom_lora_attivi):
        nodo_id = "27" if i == 0 else f"27_{i+1}"
        wf[nodo_id] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "lora_name": name,
                "strength_model": strength,
                "model": ultimo_id
            },
            "_meta": {"title": f"LTX Custom LoRA {i+1}: {name}"}
        }
        ultimo_id = [nodo_id, 0]
        
    if "34" in wf:
        wf["34"]["inputs"]["model"] = ultimo_id
    if "18" in wf and "model" in wf["18"]["inputs"]:
        wf["18"]["inputs"]["model"] = ultimo_id
    if "45" in wf and "model" in wf["45"]["inputs"]:
        wf["45"]["inputs"]["model"] = ultimo_id


def _applica_lora_cascata_minimax(wf, dati_lora):
    """
    Concatena eventuali LoRA custom selezionati dall'utente nell'interfaccia
    in cascata dopo il nodo 337 e prima del nodo 58 (SageAttention Patch).
    """
    custom_lora_attivi = []
    for name, strength in dati_lora:
        if name and name not in ["-", "Nessuno", "None", "nessuno", "none"] and float(strength) > 0.0:
            nome_formattato = name.replace("/", "\\") if os.name == 'nt' else name.replace("\\", "/")
            custom_lora_attivi.append((nome_formattato, float(strength)))

    punto_attacco_base = ["337", 0] if "337" in wf else (["336", 0] if "336" in wf else ["192", 0])

    # Rimuove nodi iniettati in precedenza
    for extra_id in ["custom_lora_1", "custom_lora_2", "custom_lora_3"]:
        if extra_id in wf:
            del wf[extra_id]

    if not custom_lora_attivi:
        if "58" in wf:
            wf["58"]["inputs"]["model"] = punto_attacco_base
        return

    ultimo_id = punto_attacco_base
    for i, (name, strength) in enumerate(custom_lora_attivi):
        nodo_id = f"custom_lora_{i+1}"
        wf[nodo_id] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "lora_name": name,
                "strength_model": strength,
                "model": ultimo_id
            },
            "_meta": {"title": f"MiniMax Custom LoRA {i+1}: {name}"}
        }
        ultimo_id = [nodo_id, 0]

    if "58" in wf:
        wf["58"]["inputs"]["model"] = ultimo_id


def calcola_dimensioni_divisibili_ottimali(lato_corto_target, rapporto_target, ratio_is_w_over_h=True, multiple=32):
    if ratio_is_w_over_h:
        h_ideal = lato_corto_target
        w_ideal = int(h_ideal * rapporto_target)
    else:
        w_ideal = lato_corto_target
        h_ideal = int(w_ideal / rapporto_target)
        
    get_candidati = lambda val: [(val // multiple) * multiple - multiple, (val // multiple) * multiple, (val // multiple) * multiple + multiple]
    
    w_candidates = [c for c in get_candidati(w_ideal) if c > 0]
    h_candidates = [c for c in get_candidati(h_ideal) if c > 0]
    
    if not w_candidates: w_candidates = [768]
    if not h_candidates: h_candidates = [448]
    
    migliore_w, migliore_h = w_candidates[0], h_candidates[0]
    min_errore_ratio = float('inf')
    
    for w in w_candidates:
        for h in h_candidates:
            ratio_candidato = w / h
            errore = abs(ratio_candidato - rapporto_target)
            
            if errore < min_errore_ratio:
                min_errore_ratio = errore
                migliore_w = w
                migliore_h = h
            elif abs(errore - min_errore_ratio) < 1e-5:
                area_ideale = w_ideal * h_ideal
                area_corrente = w * h
                area_migliore = migliore_w * migliore_h
                if abs(area_corrente - area_ideale) < abs(area_migliore - area_ideale):
                    migliore_w = w
                    migliore_h = h
                
    return migliore_w, migliore_h


def calcola_parametri_temporali_e_risoluzione(v_fps, v_durata, v_risoluzione, v_rapporto, multiple=32):
    fps_int = int(v_fps)
    durata_float = float(v_durata)
    
    frame_teorici = int(durata_float * fps_int)
    
    n_blocks = round((frame_teorici - 1) / 8)
    if n_blocks < 1: 
        n_blocks = 1
    frame_totali = (n_blocks * 8) + 1
        
    lato_corto = {"256p":256,"360p":360,"480p":480,"720p":720,"1080p":1080}.get(v_risoluzione, 720)
    rapporto = {"16:9":16/9,"9:16":9/16,"4:3":4/3,"3:4":3/4,"1:1":1/1}.get(v_rapporto, 16/9)
    
    is_landscape = rapporto >= 1.0
    larghezza, altezza = calcola_dimensioni_divisibili_ottimali(lato_corto, rapporto, ratio_is_w_over_h=is_landscape, multiple=multiple)
    
    log.registra(f"Workflow Video: Dimensioni divisibili per {multiple}: {larghezza}x{altezza} (Target originale: {v_risoluzione} {v_rapporto})")
    
    return larghezza, altezza, frame_totali, fps_int


def prepara_workflow_ltx_video(
    file_path, prompt_video, lv1_n, lv1_s, lv2_n, lv2_s, lv3_n, lv3_s, 
    seed_immagine_base=None, percorso_immagine_origine=None, percorso_immagine_intermedia=None, percorso_immagine_destinazione=None,
    v_fps="24", v_durata=4.0, v_rapporto="16:9", v_risoluzione="720p",
    v_cfg=3.0, v_strength=0.90, v_compression=15, v_seed_mode="randomize",
    solo_testo_video=False
):
    with open(file_path, 'r', encoding='utf-8') as f: 
        wf = json.load(f)
        
    nodi_richiesti = [NODO_UNET, NODO_CLIP, NODO_VAE, NODO_PROMPT, NODO_PROMPT_NEG, NODO_SAMPLER, NODO_VAE_DECODE, NODO_SAVE_VIDEO]
    errori = []
    for nodo in nodi_richiesti:
        if nodo not in wf:
            errori.append(f"Nodo video mancante: {nodo}")
    if errors := errori:
        for e in errors:
            log.registra(f"Workflow validation ERROR: {e}", "ERROR")
        return None

    is_ltx25 = "45" in wf or "38" in wf or "36" in wf

    p_adv = ottieni_parametri_avanzati_workflow().get("ltx_video", {})
    p_tile = p_adv.get("tiled_vae", {})
    p_fmt = p_adv.get("video_format", {})

    prefisso_stabilita = p_adv.get("stability_prefix", "")

    # 1. CFG GUIDER (1.0 per LTX-2.5 Distilled)
    if is_ltx25:
        if "18" in wf and "video_cfg" in wf["18"]["inputs"]:
            wf["18"]["inputs"]["video_cfg"] = 1.0
            wf["18"]["inputs"]["audio_cfg"] = 1.0
        if "45" in wf and "video_cfg" in wf["45"]["inputs"]:
            wf["45"]["inputs"]["video_cfg"] = 1.0
            wf["45"]["inputs"]["audio_cfg"] = 1.0
    else:
        if "18" in wf:
            if "video_cfg" in wf["18"]["inputs"]:
                wf["18"]["inputs"]["video_cfg"] = float(v_cfg)
            elif "cfg" in wf["18"]["inputs"]:
                wf["18"]["inputs"]["cfg"] = float(v_cfg)

    if "22" in wf:
        wf["22"]["inputs"]["sampler_name"] = p_adv.get("pass1_sampler", wf["22"]["inputs"]["sampler_name"])
    if "43" in wf:
        wf["43"]["inputs"]["sampler_name"] = p_adv.get("pass2_sampler", wf["43"]["inputs"]["sampler_name"])

    if "24" in wf:
        wf["24"]["inputs"]["img_compression"] = int(v_compression)

    if is_ltx25:
        if "37" in wf:
            wf["37"]["inputs"]["strength"] = max(0.0, min(1.0, float(v_strength)))
        if "40" in wf:
            wf["40"]["inputs"]["strength"] = 1.0

    # 3. SIGMAS
    if "25" in wf:
        wf["25"]["inputs"]["sigmas"] = p_adv.get("pass1_sigmas", "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0")

    if "44" in wf:
        wf["44"]["inputs"]["sigmas"] = p_adv.get("pass2_sigmas", "0.85, 0.7250, 0.4219, 0.0")

    # 4. DECODIFICA VAE CONTINUA
    if NODO_VAE_DECODE in wf:
        if wf[NODO_VAE_DECODE].get("class_type") == "VAEDecodeTiled":
            wf[NODO_VAE_DECODE]["inputs"]["tile_size"] = p_tile.get("tile_size", 1024)
            wf[NODO_VAE_DECODE]["inputs"]["overlap"] = p_tile.get("overlap", 32)
            wf[NODO_VAE_DECODE]["inputs"]["temporal_size"] = p_tile.get("temporal_size", 512)
            wf[NODO_VAE_DECODE]["inputs"]["temporal_overlap"] = p_tile.get("temporal_overlap", 16)

    if "17" in wf:
        wf["17"]["inputs"]["bit_depth"] = p_fmt.get("bit_depth", 8)

    # 5. RISOLUZIONE E DURATA
    larghezza, altezza, frame_totali, fps_int = calcola_parametri_temporali_e_risoluzione(v_fps, v_durata, v_risoluzione, v_rapporto, multiple=64 if is_ltx25 else 32)
    
    if "48" in wf:
        wf["48"]["inputs"]["value"] = int(larghezza)
    if "49" in wf:
        wf["49"]["inputs"]["value"] = int(altezza)

    if "12" in wf and "50" not in wf:
        wf["12"]["inputs"]["width"] = int(larghezza) // 2 if is_ltx25 else int(larghezza)
        wf["12"]["inputs"]["height"] = int(altezza) // 2 if is_ltx25 else int(altezza)

    if NODO_EMPTY_IMAGE in wf and wf[NODO_EMPTY_IMAGE].get("class_type") == "EmptyImage":
        wf[NODO_EMPTY_IMAGE]["inputs"]["width"] = int(larghezza)
        wf[NODO_EMPTY_IMAGE]["inputs"]["height"] = int(altezza)
        
    if "14" in wf:
        wf["14"]["inputs"]["value"] = int(frame_totali)
            
    if "19" in wf:
        wf["19"]["inputs"]["value"] = float(fps_int)

    # 6. PROMPT TEXT
    from utils.video_model_prompt import ltx_prompt
    prompt_video_pulito = ltx_prompt(pulisci_tag_mismatch_ltx(prompt_video.strip()))
    
    if is_ltx25:
        prompt_con_ancore = prompt_video_pulito
    else:
        if "[VISUAL]" in prompt_video_pulito:
            prompt_con_ancore = prompt_video_pulito.replace("[VISUAL]", f"[VISUAL] {prefisso_stabilita}", 1)
        else:
            prompt_con_ancore = prompt_video_pulito if prompt_video_pulito.lower().startswith(prefisso_stabilita[:30].lower()) else prefisso_stabilita + prompt_video_pulito
    
    if NODO_PROMPT in wf: 
        wf[NODO_PROMPT]["inputs"]["text"] = prompt_con_ancore
    
    from utils.prompt_templates import system_template
    prompt_negativo = system_template('Negative Prompt.txt', allow_empty=True)

    if NODO_PROMPT_NEG in wf:
        wf[NODO_PROMPT_NEG]["inputs"]["text"] = prompt_negativo
    
    # 7. SEED
    seed_val = int(seed_immagine_base) if seed_immagine_base is not None else random.randint(1000000000000, 9999999999999)
    if "15" in wf: 
        wf["15"]["inputs"]["noise_seed"] = seed_val
    if "42" in wf:
        wf["42"]["inputs"]["noise_seed"] = seed_val

    # 8. GESTIONE START FRAME + LAST FRAME CON LTXVAddGuide
    is_t2v = solo_testo_video or not percorso_immagine_origine
    if "36" in wf:
        wf["36"]["inputs"]["value"] = bool(is_t2v)

    for extra_id in ["23_2", "33_2", "23_3", "33_3", "35_batch1", "35_batch2", "35_guide_mid", "35_guide_last"]:
        if extra_id in wf:
            del wf[extra_id]

    if is_t2v:
        wf["23"] = {
            "class_type": "EmptyImage",
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1,
                "color": 0
            },
            "_meta": {"title": "Empty Dummy Image (T2V)"}
        }
        if "24" in wf:
            wf["24"]["inputs"]["image"] = ["33", 0]
        if "13" in wf:
            wf["13"]["inputs"]["video_latent"] = ["37", 0]
        if "40" in wf:
            wf["40"]["inputs"]["latent"] = ["39", 0]
            wf["40"]["inputs"]["image"] = ["24", 0]
        if "41" in wf:
            wf["41"]["inputs"]["video_latent"] = ["40", 0] if "40" in wf else ["39", 0]
        if "18" in wf:
            wf["18"]["inputs"]["positive"] = ["11", 0]
            wf["18"]["inputs"]["negative"] = ["11", 1]
        if "45" in wf:
            wf["45"]["inputs"]["positive"] = ["11", 0]
            wf["45"]["inputs"]["negative"] = ["11", 1]
    else:
        if "23" in wf:
            wf["23"]["inputs"]["image"] = percorso_immagine_origine

        comfy_input_dir = os.path.join(config.COMFYUI_DIR, "ComfyUI", "input")
        
        def _esiste_in_input(p):
            if not p: return False
            return os.path.exists(p) or os.path.exists(os.path.join(comfy_input_dir, p))

        has_dest = _esiste_in_input(percorso_immagine_destinazione)
        has_mid = _esiste_in_input(percorso_immagine_intermedia)

        if "24" in wf:
            wf["24"]["inputs"]["image"] = ["33", 0]

        current_pos = ["11", 0]
        current_neg = ["11", 1]
        current_latent = ["37", 0]

        if has_dest:
            wf["23_2"] = {
                "class_type": "LoadImage",
                "inputs": {"image": percorso_immagine_destinazione},
                "_meta": {"title": "Load Last Frame Image"}
            }
            wf["33_2"] = {
                "class_type": "ResizeImageMaskNode",
                "inputs": {
                    "resize_type": "scale longer dimension",
                    "resize_type.longer_size": 1536,
                    "scale_method": "lanczos",
                    "input": ["23_2", 0]
                },
                "_meta": {"title": "Resize Last Frame"}
            }

            if has_mid:
                wf["23_3"] = {
                    "class_type": "LoadImage",
                    "inputs": {"image": percorso_immagine_intermedia},
                    "_meta": {"title": "Load Mid Frame Image"}
                }
                wf["33_3"] = {
                    "class_type": "ResizeImageMaskNode",
                    "inputs": {
                        "resize_type": "scale longer dimension",
                        "resize_type.longer_size": 1536,
                        "scale_method": "lanczos",
                        "input": ["23_3", 0]
                    },
                    "_meta": {"title": "Resize Mid Frame"}
                }

                mid_frame_index = int(frame_totali // 2)
                wf["35_guide_mid"] = {
                    "class_type": "LTXVAddGuide",
                    "inputs": {
                        "positive": current_pos,
                        "negative": current_neg,
                        "vae": ["3", 0],
                        "latent": current_latent,
                        "image": ["33_3", 0],
                        "frame_idx": mid_frame_index,
                        "strength": 0.9
                    },
                    "_meta": {"title": f"LTXV Add Guide (Mid Frame {mid_frame_index})"}
                }
                current_pos = ["35_guide_mid", 0]
                current_neg = ["35_guide_mid", 1]
                current_latent = ["35_guide_mid", 2]

            wf["35_guide_last"] = {
                "class_type": "LTXVAddGuide",
                "inputs": {
                    "positive": current_pos,
                    "negative": current_neg,
                    "vae": ["3", 0],
                    "latent": current_latent,
                    "image": ["33_2", 0],
                    "frame_idx": -1,
                    "strength": 1.0
                },
                "_meta": {"title": "LTXV Add Guide (Last Frame -1)"}
            }
            current_pos = ["35_guide_last", 0]
            current_neg = ["35_guide_last", 1]
            current_latent = ["35_guide_last", 2]

            if "13" in wf:
                wf["13"]["inputs"]["video_latent"] = current_latent
            if "18" in wf:
                wf["18"]["inputs"]["positive"] = current_pos
                wf["18"]["inputs"]["negative"] = current_neg
            if "39" in wf:
                wf["crop_story_guides"] = {
                    "class_type": "LTXVCropGuides",
                    "inputs": {
                        "positive": current_pos,
                        "negative": current_neg,
                        "latent": ["16", 0]
                    },
                    "_meta": {"title": "Remove storyboard reference frames"}
                }
                wf["39"]["inputs"]["samples"] = ["crop_story_guides", 2]
            if "45" in wf:
                wf["45"]["inputs"]["positive"] = ["11", 0]
                wf["45"]["inputs"]["negative"] = ["11", 1]

            if has_mid:
                log.registra(f"LTX-2.5: Injected Start Frame (idx 0), Mid Frame (idx {frame_totali // 2}) and Last Frame (idx -1) via LTXVAddGuide keyframe conditioning.")
            else:
                log.registra(f"LTX-2.5: Injected Start Frame (idx 0) and Last Frame (idx -1) via LTXVAddGuide keyframe conditioning.")
        else:
            if "13" in wf:
                wf["13"]["inputs"]["video_latent"] = ["37", 0]
            if "18" in wf:
                wf["18"]["inputs"]["positive"] = ["11", 0]
                wf["18"]["inputs"]["negative"] = ["11", 1]
            if "45" in wf:
                wf["45"]["inputs"]["positive"] = ["11", 0]
                wf["45"]["inputs"]["negative"] = ["11", 1]

        if "40" in wf:
            wf["40"]["inputs"]["latent"] = ["39", 0]
            wf["40"]["inputs"]["image"] = ["24", 0]
            wf["40"]["inputs"]["strength"] = 1.0
        if "41" in wf:
            wf["41"]["inputs"]["video_latent"] = ["40", 0] if "40" in wf else ["39", 0]

    # Apply temporal guides at refinement resolution too, then remove their
    # appended latent frames before video decoding. Audio stays separate.
    if is_ltx25 and not is_t2v and "35_guide_last" in wf:
        pos, neg, latent = ["11", 0], ["11", 1], ["40", 0]
        for original in ("35_guide_mid", "35_guide_last"):
            if original not in wf:
                continue
            guide_id = original + "_pass2"
            inputs = dict(wf[original]["inputs"])
            inputs.update(positive=pos, negative=neg, latent=latent)
            wf[guide_id] = {"class_type": "LTXVAddGuide", "inputs": inputs}
            pos, neg, latent = [guide_id, 0], [guide_id, 1], [guide_id, 2]
        wf["41"]["inputs"]["video_latent"] = latent
        wf["45"]["inputs"].update(positive=pos, negative=neg)
        wf["crop_story_guides_pass2"] = {
            "class_type": "LTXVCropGuides",
            "inputs": {"positive": pos, "negative": neg, "latent": ["47", 0]}}
        wf["8"]["inputs"]["samples"] = ["crop_story_guides_pass2", 2]

    _applica_lora_cascata_ltx(wf, [(lv1_n, lv1_s), (lv2_n, lv2_s), (lv3_n, lv3_s)])

    return wf


def valida_denoise_minimax(denoise):
    """Mantiene compatibilità con controlli di preflight."""
    try:
        value = float(denoise)
        if value == 1:
            return value
    except (TypeError, ValueError):
        pass
    from core import lingua
    lang = sessione.carica_ultima_sessione().get("lingua_selezionata", "IT")
    dl = lingua.ottieni_dizionario_lingua(lang)
    raise ValueError("MiniMax H3: Denoise deve essere 1 (generazione completa)." if lang == "IT" else
                     "MiniMax H3: Denoise must be 1 (full generation).")


def prepara_workflow_minimax_h3(
    file_path, prompt_video, lv1_n="-", lv1_s=1.0, lv2_n="-", lv2_s=1.0, lv3_n="-", lv3_s=1.0,
    seed_immagine_base=None, percorso_immagine_origine=None, percorso_immagine_intermedia=None, percorso_immagine_destinazione=None,
    v_fps="24", v_durata=5.0, v_rapporto="16:9", v_risoluzione="720p",
    v_cfg=3.0, v_strength=1.0, v_compression=15, v_seed_mode="randomize",
    solo_testo_video=False,
    steps=8, denoise=1.0, scheduler="beta"
):
    """
    Prepara il workflow MiniMax H3 Singularity (Reference-to-Video / Dual-Clock Sampler).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)

    if float(denoise) != 1.0:
        raise ValueError("MiniMax Dual-Clock supports full generation only: denoise must be 1.")

    p_adv = ottieni_parametri_avanzati_workflow().get("minimax_h3", {})
    p_fmt = p_adv.get("video_format", {})
    expected = {"263": "Text", "265": "MiniMaxH3ReferenceToVideo",
                "332": "MiniMaxH3DualClockSamplerT8", "256": "RandomNoise",
                "259": "PrimitiveFloat", "264": "VHS_VideoCombine"}
    for node_id, node_type in expected.items():
        if wf.get(node_id, {}).get("class_type") != node_type:
            raise ValueError(f"MiniMax workflow: expected {node_type} at node {node_id}; adapter must be updated.")

    # 1. Impostazione Prompt di Regia (nodo 263 di tipo Text)
    from utils.video_model_prompt import minimax_prompt
    prompt_video_pulito = minimax_prompt(prompt_video.strip())
    if "263" in wf:
        wf["263"]["inputs"]["text"] = prompt_video_pulito

    # 2. Impostazione Durata (nodo 259 - PrimitiveFloat)
    durata_float = float(v_durata)
    if "259" in wf:
        wf["259"]["inputs"]["value"] = durata_float

    # 3. Dual-Clock Sampler (nodo 332)
    if "332" in wf:
        wf["332"]["inputs"]["steps"] = int(steps)
        wf["332"]["inputs"]["scheduler"] = str(scheduler)
        if "sampler_name" in p_adv:
            wf["332"]["inputs"]["sampler_name"] = p_adv["sampler_name"]
        if "shift_video" in p_adv:
            wf["332"]["inputs"]["shift_video"] = p_adv["shift_video"]
        if "shift_audio" in p_adv:
            wf["332"]["inputs"]["shift_audio"] = p_adv["shift_audio"]

    # 4. Impostazione Seed (nodo 256)
    seed_val = int(seed_immagine_base) if seed_immagine_base is not None else random.randint(1000000000000, 9999999999999)
    if "256" in wf:
        wf["256"]["inputs"]["noise_seed"] = seed_val

    # 5. Dimensioni & Aspect Ratio (divisibili per 24 come da specifica del modello)
    lato_corto = {"256p": 256, "360p": 360, "480p": 480, "720p": 720, "1080p": 1080}.get(v_risoluzione, 720)
    rapporto = {"16:9": 16/9, "9:16": 9/16, "4:3": 4/3, "3:4": 3/4, "1:1": 1/1}.get(v_rapporto, 16/9)
    is_landscape = rapporto >= 1.0
    larghezza, altezza = calcola_dimensioni_divisibili_ottimali(lato_corto, rapporto, ratio_is_w_over_h=is_landscape, multiple=24)

    if "265" in wf:
        wf["265"]["inputs"]["width"] = int(larghezza)
        wf["265"]["inputs"]["height"] = int(altezza)

    # 6. Gestione Immagini di Riferimento (nodo 51 e nodo 265)
    comfy_input_dir = os.path.join(config.COMFYUI_DIR, "ComfyUI", "input")
    def _verifica_immagine_presente(percorso):
        if not percorso:
            return False
        return os.path.exists(percorso) or os.path.exists(os.path.join(comfy_input_dir, percorso))

    has_ref_img = _verifica_immagine_presente(percorso_immagine_origine)
    has_last_img = _verifica_immagine_presente(percorso_immagine_destinazione)
    if not solo_testo_video and percorso_immagine_origine and not has_ref_img:
        raise ValueError("MiniMax: reference image not found; refusing to switch silently to text-only.")
    if not solo_testo_video and percorso_immagine_destinazione and not has_last_img:
        raise ValueError("MiniMax: final reference image not found.")

    # Rebuild all reference slots from the current request, including workflows
    # saved with more than two references.
    for key in list(wf["265"]["inputs"]):
        if key.startswith("ref_images."):
            del wf["265"]["inputs"][key]

    # Pulizia preventiva slot aggiuntivi
    for extra_id in ["51_dest", "51_mid"]:
        if extra_id in wf:
            del wf[extra_id]

    if solo_testo_video or not has_ref_img:
        # Modalità Text-to-Video: rimuove il dizionario di riferimento da 265
        if "265" in wf:
            wf["265"]["inputs"].pop("ref_images.ref_image_0", None)
            wf["265"]["inputs"].pop("ref_images.ref_image_1", None)
        if "51" in wf:
            del wf["51"]
        log.registra("MiniMax H3 Singularity: T2V mode active (no reference image connected).")
    else:
        # Modalità Reference-to-Video
        wf["51"] = {"class_type": "LoadImage", "inputs": {"image": percorso_immagine_origine}}
        if "265" in wf:
            wf["265"]["inputs"]["ref_images.ref_image_0"] = ["51", 0]

        if has_last_img and percorso_immagine_destinazione != percorso_immagine_origine:
            wf["51_dest"] = {
                "class_type": "LoadImage",
                "inputs": {"image": percorso_immagine_destinazione},
                "_meta": {"title": "Load Second Reference Image"}
            }
            if "265" in wf:
                wf["265"]["inputs"]["ref_images.ref_image_1"] = ["51_dest", 0]
                log.registra(f"MiniMax H3 Singularity: Connessa seconda immagine di riferimento ({percorso_immagine_destinazione}).")

    if has_ref_img and not solo_testo_video and percorso_immagine_intermedia:
        if not _verifica_immagine_presente(percorso_immagine_intermedia):
            raise ValueError("MiniMax: intermediate reference image not found.")
        # Keep first/final reference numbering stable; append the storyboard's
        # intermediate reference rather than silently ignoring it.
        slot = 2 if "51_dest" in wf else 1
        wf["51_mid"] = {"class_type": "LoadImage", "inputs": {"image": percorso_immagine_intermedia}}
        wf["265"]["inputs"][f"ref_images.ref_image_{slot}"] = ["51_mid", 0]

    checkpoint = str(wf.get("192", {}).get("inputs", {}).get("unet_name", "")).replace("\\", "/").split("/")[-1].lower()
    # This exact Singularity checkpoint was exercised with first/last keyframes.
    # Keep unknown/custom Ref2VA checkpoints on their original reference path.
    use_keyframes = (checkpoint == "minimax-h3_singularity_ref2va_v1.3_int8.safetensors"
                     or "fl2va" in checkpoint)
    if use_keyframes and not solo_testo_video and (has_ref_img or has_last_img):
        source = wf["265"]["inputs"]
        inputs = {key: source[key] for key in ("prompt", "clip", "vae", "width", "height", "length")}
        # The native keyframe node uses a 32-pixel canvas grid.
        for axis in ("width", "height"):
            inputs[axis] = max(32, round(inputs[axis] / 32) * 32)
        if has_ref_img:
            inputs["first_frame"] = ["51", 0]
        if has_last_img:
            wf["51_dest"] = {"class_type": "LoadImage", "inputs": {"image": percorso_immagine_destinazione}}
            inputs["last_frame"] = ["51_dest", 0]
        wf["265"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": inputs}
        if "51_mid" in wf:
            frames = max(5, round(durata_float * 24))
            frames += (5 - frames % 17) % 17
            wf["265_mid_guide"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
                "positive": ["265", 0], "latent": ["265", 1], "vae": inputs["vae"],
                "image": ["51_mid", 0], "frame_idx": (frames - 1) // 2}}
            wf["223"]["inputs"]["conditioning"] = ["265_mid_guide", 0]
        log.registra("MiniMax: native first/last keyframe conditioning enabled.")

    if "265" in wf:
        reference_keys = [key for key in wf["265"]["inputs"] if key.startswith("ref_images.")]
        if "263" in wf and reference_keys:
            reference_text = " ".join(f"<Picture {i}> is visual reference {i}." for i in range(1, len(reference_keys) + 1))
            wf["263"]["inputs"]["text"] = wf["263"]["inputs"]["text"].replace(
                "summary:\n", "summary:\n" + reference_text + "\n", 1)

    # 7. Formato Video Output VHS (nodo 264)
    if "264" in wf:
        wf["264"]["inputs"]["frame_rate"] = 24
        if "crf" in p_fmt:
            wf["264"]["inputs"]["crf"] = p_fmt["crf"]
        if "pix_fmt" in p_fmt:
            wf["264"]["inputs"]["pix_fmt"] = p_fmt["pix_fmt"]

    # 8. Concatenazione LoRA
    _applica_lora_cascata_minimax(wf, [(lv1_n, lv1_s), (lv2_n, lv2_s), (lv3_n, lv3_s)])

    return wf
