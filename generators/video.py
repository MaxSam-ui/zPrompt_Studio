from utils.progress_status import phase_progress
# generators/video.py

import os
import re
import time
import glob
import requests
import shutil
import gradio as gr
import random
import gc      
import torch   

from core import config, sessione, log, lingua, hardware, workflow_registry
from generators import workflow
from services import comfyui_manager, director_ai
from utils import timeline
from services.comfyui_manager import client_id
from utils.media_base import norm_path_sicuro
from utils.media_utils import _estrai_percorso_immagine_sicuro, calcola_stato_spia_video
from utils.websocket_monitor import stream_webhook_events, recupera_file_generato
from generators.image_utils import sposta_file_sicuro

from utils.ffmpeg_utils import (
    _ottieni_percorso_ffmpeg,
    estrai_ultimo_frame_ffmpeg,
    fondi_video_mp4_ffmpeg
)


def sanitizza_prompt_video(testo):
    """
    Rimuove completamente preamboli di analisi, note di autocorrezione, righe di separazione
    e frasi bloccanti della geometria per isolare il prompt di regia operativo.
    """
    if not testo or not isinstance(testo, str):
        return ""
    
    t = testo.strip()
    if t.startswith("Subject and scene: ") and "\n\n" in t:
        context, body = t.split("\n\n", 1)
        return context + "\n\n" + sanitizza_prompt_video(body)

    # Rimuove frasi di stabilizzazione rigida che congelano LTX 2.5
    t = re.sub(r'Stable geometry,?\s*clean edges,?\s*stable lines,?\s*no warping\.?', '', t, flags=re.IGNORECASE).strip()

    # 1. Cerca il punto di inizio della vera sceneggiatura
    pattern_inizio = r'(<clip1>|\[VISUAL\]|\*\*SECTION\s*1|\bSECTION\s*1|PREAMBLE:|\bCLIP\s*1:)'
    match_clip = re.search(pattern_inizio, t, re.IGNORECASE)
    if match_clip:
        t = t[match_clip.start():].strip()
    else:
        if any(kw in t.lower()[:300] for kw in ["compilation input analysis", "self-correction", "chronological timeline:"]):
            parti = re.split(r'\n\s*[\-\*]{3,}\s*\n', t)
            if len(parti) > 1:
                t = parti[-1].strip()

    t = re.sub(r'^\s*\*\*[^*]+OUTPUT:\*\*\s*\n?', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'^\s*\*\*[^*]+PROMPT:\*\*\s*\n?', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'\*\([^)]*Self-Correction[^)]*\)\*', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'\*?\*?Compilation Input Analysis:?\*?\*?.*?(?=\n\n|\n[A-Z<\[])', '', t, flags=re.DOTALL | re.IGNORECASE).strip()
    t = re.sub(r'\n{3,}', '\n\n', t).strip()
    
    return t


def genera_video_con_monitor_passo_comfy(
    clip_idx, num_clip_totali, durata_clip_corrente, v_durata_effettiva,
    prompt_clip_corrente, lv1_n, lv1_s, lv2_n, lv2_s, lv3_n, lv3_s,
    seed_pulito, percorso_inizio_passo, percorso_mid_passo, percorso_fine_passo,
    v_fps, v_rapporto, v_risoluzione, v_cfg, v_strength, v_compression, v_seed_mode,
    solo_testo_video, clip_generate_temporanee, file_temporanei_input_da_pulire,
    ws_url, client_id, dl, is_it, state_ref, m_video_attivo="LTX-Video 2.5",
    v_steps_vid=4, v_denoise_vid=1.0, v_scheduler_vid="simple"
):
    comfy_input_dir = os.path.abspath(os.path.join(config.COMFYUI_DIR, "ComfyUI", "input"))

    workflow_path = workflow_registry.risolvi_percorso_json_video(m_video_attivo)

    if m_video_attivo == "MiniMax H3":
        wf = workflow.prepara_workflow_minimax_h3(
            workflow_path, prompt_clip_corrente, lv1_n, lv1_s, lv2_n, lv2_s, lv3_n, lv3_s,
            seed_pulito, percorso_inizio_passo, percorso_mid_passo, percorso_fine_passo,
            v_fps, durata_clip_corrente, v_rapporto, v_risoluzione, v_cfg, v_strength, v_compression, v_seed_mode,
            solo_testo_video=solo_testo_video,
            steps=v_steps_vid, denoise=v_denoise_vid, scheduler=v_scheduler_vid
        )
    else:
        wf = workflow.prepara_workflow_ltx_video(
            workflow_path, prompt_clip_corrente, lv1_n, lv1_s, lv2_n, lv2_s, lv3_n, lv3_s,
            seed_pulito, percorso_inizio_passo, percorso_mid_passo, percorso_fine_passo,
            v_fps, durata_clip_corrente, v_rapporto, v_risoluzione, v_cfg, v_strength, v_compression, v_seed_mode,
            solo_testo_video=solo_testo_video
        )

    if wf is None: raise Exception("Null or unconfigurable video workflow.")

    clip_path_grezza = None

    for tentativo in range(2):
        try:
            resp = requests.post(config.COMFYUI_URL + "/prompt", json={"prompt": wf, "client_id": client_id}, timeout=10)
            if resp.status_code != 200:
                try:
                    err_data = resp.json()
                    dettaglio_err = err_data.get("error", {}).get("message", err_data.get("node_errors", str(resp.text)))
                except Exception:
                    dettaglio_err = resp.text
                log.registra(f"ComfyUI Error [{resp.status_code}]: {dettaglio_err}", "ERROR")
                yield gr.update(), f"❌ ComfyUI Error ({resp.status_code}): {dettaglio_err}", log.ottieni_tutti_i_log(), state_ref
                return
            p_id = resp.json()["prompt_id"]
            log.registra(f"Richiesta video inviata con successo a ComfyUI (Prompt ID: {p_id}).")
        except Exception as e:
            log.registra(f"ComfyUI connection error at clip {clip_idx+1}: {e}", "ERROR")
            msg_err_comm = dl.get("video_err_comfy_run", "❌ ComfyUI error on clip {clip_idx}.").format(clip_idx=clip_idx+1)
            yield gr.update(), msg_err_comm, log.ottieni_tutti_i_log(), state_ref
            return

        is_stale_interrupt = False
        for event_type, data in stream_webhook_events(p_id, ws_url, wf, timeout=float(config.TIMEOUT_COMFY_VIDEO)):
            if not comfyui_manager.generazione_attiva:
                yield gr.update(), dl.get("video_status_interrupted", "⏹️ Generation interrupted."), log.ottieni_tutti_i_log(), state_ref
                return
            if event_type == 'stale_interrupt':
                is_stale_interrupt = True
                break
            elif event_type == 'progress':
                msg_rendering = dl.get("video_status_rendering", "🎬 Rendering Video {clip_idx}/{num_clip_totali}: {data}...").replace("{data}%", "{data}").format(clip_idx=clip_idx+1, num_clip_totali=num_clip_totali, data=phase_progress(data))
                yield gr.update(), msg_rendering, log.ottieni_tutti_i_log(), state_ref
            elif event_type == 'executing':
                msg_processing = dl.get("video_status_processing", "⏳ Processing Video {clip_idx}/{num_clip_totali}: {data}...").format(clip_idx=clip_idx+1, num_clip_totali=num_clip_totali, data=data)
                yield gr.update(), msg_processing, log.ottieni_tutti_i_log(), state_ref
            elif event_type in ('executed_file', 'executed_info'):
                if data and os.path.exists(data) and os.path.splitext(data)[1].lower() in ('.mp4', '.webm', '.gif'):
                    clip_path_grezza = data
                    log.registra(f"[WebSocket] Video file captured directly from 'executed' event: {data}")
            elif event_type == 'done':
                break
            elif event_type == 'error':
                msg_err_gen = dl.get("video_err_comfy_run", "❌ ComfyUI error on clip {clip_idx}.").format(clip_idx=clip_idx+1)
                yield gr.update(), msg_err_gen, log.ottieni_tutti_i_log(), state_ref
                return
            elif event_type == 'timeout':
                msg_timeout = dl.get("video_status_timeout", "⏳ Timeout waiting for ComfyUI for clip {clip_idx}.").format(clip_idx=clip_idx+1)
                yield gr.update(), msg_timeout, log.ottieni_tutti_i_log(), state_ref
                return

        if is_stale_interrupt and tentativo == 0:
            log.registra(f"[Video Engine] Residual interruption detected for clip {clip_idx+1}. Retrying in 0.5s...")
            time.sleep(0.5)
            continue
        else:
            break

    if not comfyui_manager.generazione_attiva:
        yield gr.update(), dl.get("video_status_interrupted", "⏹️ Generation interrupted."), log.ottieni_tutti_i_log(), state_ref
        return

    if not clip_path_grezza or not os.path.exists(clip_path_grezza):
        clip_path_grezza = recupera_file_generato(p_id, extensions=('.mp4', '.webm', '.gif'))

    if not clip_path_grezza:
        msg_err_rec = dl.get("video_err_missing_file", "❌ Unable to find video file for clip {clip_idx}.").format(clip_idx=clip_idx+1)
        yield gr.update(), msg_err_rec, log.ottieni_tutti_i_log(), state_ref
        return

    if clip_path_grezza:
        clip_generate_temporanee.append(clip_path_grezza)


def genera_video_con_monitor(
    count_lora, m_vlm_vid, p_video,
    lv1_n, lv1_s, lv2_n, lv2_s, lv3_n, lv3_s,
    testo_timeline, v_fps, v_durata, v_rapporto, v_risoluzione,
    v_cfg, v_strength, v_compression, v_seed, v_seed_mode,
    seed_immagine_base=None, stato_gen=None, audio_descrizione="",
    immagine_sorgente_i2v=None, solo_testo_video=False, video_copies=1,
    m_video_attivo="LTX-Video 2.5",
    v_steps_vid=4, v_denoise_vid=1.0, v_scheduler_vid="simple"
):
    p_video = sanitizza_prompt_video(p_video)

    lv1_n_eff = lv1_n if count_lora >= 1 else "-"
    lv1_s_eff = lv1_s if count_lora >= 1 else 0.0
    lv2_n_eff = lv2_n if count_lora >= 2 else "-"
    lv2_s_eff = lv2_s if count_lora >= 2 else 0.0
    lv3_n_eff = lv3_n if count_lora == 3 else "-"
    lv3_s_eff = lv3_s if count_lora == 3 else 0.0

    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    is_it = (lang == "IT")

    from utils.video_preflight import validate_video_request
    # Validate against exactly the duration submitted to the workflow. The UI
    # duration state can lag behind a freshly edited/generated timeline.
    blocchi = timeline._parse_timeline(testo_timeline)
    v_durata_effettiva = sum(float(b["durata"]) for b in blocchi) if blocchi else v_durata
    validation_error = validate_video_request(p_video, v_durata_effettiva, english=not is_it)
    if validation_error:
        yield gr.update(), validation_error, log.ottieni_tutti_i_log(), stato_gen
        return

    lista_frames_storyboard = stato_gen.get("lista_frame_storyboard_attivi", []) if stato_gen else []
    generation_mode = s_attiva.get("generation_mode", "Classica (1 Immagine)")
    is_storyboard_active = (
        not (stato_gen or {}).get("is_extension", False) and
        ("storyboard" in str(generation_mode).lower()) and 
        bool(lista_frames_storyboard and len(lista_frames_storyboard) >= 2)
    )
    
    path_base = _estrai_percorso_immagine_sicuro(immagine_sorgente_i2v) or _estrai_percorso_immagine_sicuro(stato_gen.get("percorso_immagine_selezionata") if stato_gen else None)
    if not solo_testo_video and not is_storyboard_active:
        if not path_base or not os.path.exists(path_base):
            msg_err_img = dl.get("video_err_no_image", "❌ Image-to-Video mode active, but no source image selected. Upload a source image or enable 'Text only / T2V'.")
            yield gr.update(), msg_err_img, log.ottieni_tutti_i_log(), stato_gen
            return

    if m_video_attivo == "MiniMax H3":
        from generators.workflow_video import valida_denoise_minimax
        try:
            v_denoise_vid = valida_denoise_minimax(v_denoise_vid)
        except ValueError as exc:
            yield gr.update(), f"❌ {exc}", log.ottieni_tutti_i_log(), stato_gen
            return

    hardware.prepara_vram("COMFY_VID")
    comfyui_manager.generazione_attiva = True

    if not comfyui_manager.is_comfyui_running():
        comfyui_manager.generazione_attiva = False
        msg_err_online = dl.get("video_err_comfy_offline", "❌ ComfyUI is not ready or is offline. Wait for complete startup before generating.")
        yield gr.update(), msg_err_online, log.ottieni_tutti_i_log(), stato_gen
        return

    log.registra("=" * 60)
    log.registra(f"[DIAGNOSTICS] Selected video model: {m_video_attivo}")
    log.registra(f"[DIAGNOSTICS] Timeline text received from Gradio:\n'{testo_timeline}'")
    
    log.registra(f"[DIAGNOSTICA] Blocchi letti con successo: {len(blocchi)}")
    
    v_durata_effettiva = float(v_durata_effettiva)
    log.registra(f"[DIAGNOSTICA] Durata complessiva calcolata: {v_durata_effettiva:.1f} secondi.")
    log.registra("=" * 60)

    durata_totale_int = int(v_durata_effettiva)
    comfy_input_dir = os.path.abspath(os.path.join(config.COMFYUI_DIR, "ComfyUI", "input"))

    num_clip_totali = 1
    durata_clip_corrente = v_durata_effettiva
    video_num_clips = len(blocchi) if blocchi else 1

    get_clip_prompt = director_ai.spezza_prompt_regia_in_tag_clip(p_video, durata_totale_int, video_num_clips=video_num_clips)

    sessione.salva_sessione({
        "modello_video_attivo": m_video_attivo,
        "video_steps_minimax": v_steps_vid,
        "video_denoise_minimax": v_denoise_vid,
        "video_scheduler_minimax": v_scheduler_vid,
        "lora_video_visibili_count": count_lora, "modello_vlm_video": m_vlm_vid, "output_prompt_video": p_video,
        "video_fps": v_fps, "video_durata_totale": v_durata_effettiva, "video_rapporto": v_rapporto, "video_risoluzione": v_risoluzione,
        "video_cfg": v_cfg, "video_strength": v_strength, "video_compression": v_compression, "video_seed": v_seed, "video_seed_mode": v_seed_mode,
        "solo_testo_video_attivo": solo_testo_video, "video_copies": video_copies
    })

    totale_copie = max(1, int(video_copies))
    ultimo_video_generato = None
    file_temporanei_input_da_pulire = []

    try:
        for copia_idx in range(totale_copie):
            if not comfyui_manager.generazione_attiva: 
                break

            prefix_copia = f"[{dl.get('batch_size', 'Copy')} {copia_idx+1}/{totale_copie}] " if totale_copie > 1 else ""

            clip_generate_temporanee = []
            comfyui_manager.reset_progresso()
            ws_url = config.COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?clientId={client_id}"

            for clip_idx in range(num_clip_totali):
                if not comfyui_manager.generazione_attiva: 
                    break
                
                prompt_clip_corrente = p_video
                ha_tag_clip_espliciti = any(tag in (p_video or "").lower() for tag in ["<clip", "[clip", "[spezzone", "[scena"])

                if get_clip_prompt and len(get_clip_prompt) > 1 and ha_tag_clip_espliciti:
                    visual_blocks = []
                    speech_blocks = []
                    sounds_blocks = []
                    
                    chiavi_ordinate = sorted([k for k in get_clip_prompt.keys() if k.startswith("clip_") and k.split("_")[1].isdigit()], key=lambda x: int(x.split("_")[1]))
                    
                    for k in chiavi_ordinate:
                        testo_clip = get_clip_prompt[k]
                        
                        match_v = re.search(r'\[VISUAL\](.*?)\[/VISUAL\]', testo_clip, re.DOTALL | re.IGNORECASE)
                        if match_v:
                            visual_blocks.append(match_v.group(1).strip())
                        else:
                            visual_blocks.append(testo_clip.strip())
                            
                        match_sp = re.search(r'\[SPEECH\](.*?)\[/SPEECH\]', testo_clip, re.DOTALL | re.IGNORECASE)
                        if match_sp:
                            speech_blocks.append(match_sp.group(1).strip())
                            
                        match_s = re.search(r'\[SOUNDS\](.*?)\[/SOUNDS\]', testo_clip, re.DOTALL | re.IGNORECASE)
                        if match_s:
                            sounds_blocks.append(match_s.group(1).strip())
                    
                    visual_unito = " Then, ".join(visual_blocks)
                    if p_video.startswith("Subject and scene: ") and "\n\n" in p_video:
                        visual_unito = p_video.split("\n\n", 1)[0] + "\n" + visual_unito
                    speech_unito = " ".join(speech_blocks)
                    sounds_unito = " ".join(sounds_blocks)
                    
                    prompt_clip_corrente = f"[VISUAL] {visual_unito} [/VISUAL]"
                    if speech_unito:
                        prompt_clip_corrente += f"\n[SPEECH] {speech_unito} [/SPEECH]"
                    if sounds_unito:
                        prompt_clip_corrente += f"\n[SOUNDS] {sounds_unito} [/SOUNDS]"
                        
                    log.registra("[Video] Fusi i segmenti di regia in un unico prompt continuativo per la modalità Single-Stage.")
                else:
                    prompt_clip_corrente = p_video

                prompt_clip_corrente = re.sub(r'\[SPEECH\]\s*["\']?(?:None|none|Nessuno|nessuno)?["\']?\s*\[/SPEECH\]', '', prompt_clip_corrente, flags=re.IGNORECASE).strip()
                
                percorso_inizio_passo = None
                percorso_mid_passo = None
                percorso_fine_passo = None
                
                if is_storyboard_active and not solo_testo_video:
                    percorso_inizio = lista_frames_storyboard[0]
                    nome_inizio = f"storyboard_inizio_{copia_idx}.png"
                    shutil.copy2(percorso_inizio, os.path.join(comfy_input_dir, nome_inizio))
                    file_temporanei_input_da_pulire.append(os.path.join(comfy_input_dir, nome_inizio))
                    percorso_inizio_passo = nome_inizio
                    
                    if len(lista_frames_storyboard) >= 3:
                        percorso_mid = lista_frames_storyboard[len(lista_frames_storyboard)//2]
                        nome_mid = f"storyboard_mid_{copia_idx}.png"
                        shutil.copy2(percorso_mid, os.path.join(comfy_input_dir, nome_mid))
                        file_temporanei_input_da_pulire.append(os.path.join(comfy_input_dir, nome_mid))
                        percorso_mid_passo = nome_mid
                    
                    percorso_fine = lista_frames_storyboard[-1]
                    nome_fine = f"storyboard_fine_{copia_idx}.png"
                    shutil.copy2(percorso_fine, os.path.join(comfy_input_dir, nome_fine))
                    file_temporanei_input_da_pulire.append(os.path.join(comfy_input_dir, nome_fine))
                    percorso_fine_passo = nome_fine
                    
                    msg_status_story = prefix_copia + dl.get("video_status_storyboard", "🎬 Generating Storyboard with multiple guides ({durata_clip_corrente:.1f}s)...").format(
                        clip_idx=1,
                        num_clip_totali=1,
                        durata_clip_corrente=durata_clip_corrente
                    )
                    yield gr.update(), msg_status_story, log.ottieni_tutti_i_log(), stato_gen
                else:
                    msg_status_std = prefix_copia + dl.get("video_status_continuous", "🎬 Generating Continuous Video ({durata_clip_corrente:.1f}s)...").format(
                        durata_clip_corrente=durata_clip_corrente,
                        duration_clip_corrente=durata_clip_corrente
                    )
                    yield gr.update(), msg_status_std, log.ottieni_tutti_i_log(), stato_gen
                    
                    if not solo_testo_video:
                        # 1. Primo Frame (Iniziale)
                        if path_base and os.path.exists(path_base):
                            ext = os.path.splitext(path_base)[1] or ".png"
                            nome_inizio = f"initial_root_frame_{copia_idx}{ext}"
                            shutil.copy2(path_base, os.path.join(comfy_input_dir, nome_inizio))
                            file_temporanei_input_da_pulire.append(os.path.join(comfy_input_dir, nome_inizio))
                            percorso_inizio_passo = nome_inizio
                            
                            if stato_gen is not None:
                                stato_gen["sorgente_corrente_utilizzato"] = path_base

                        # 2. Ultimo Frame (Destinazione / Finale)
                        path_dest = _estrai_percorso_immagine_sicuro(stato_gen.get("percorso_immagine_destinazione") if stato_gen else None) or _estrai_percorso_immagine_sicuro(s_attiva.get("percorso_immagine_destinazione"))
                        # CORREZIONE: Controllo rigoroso di unicità - solo se path_dest è fisicamente diverso da path_base
                        if path_dest and os.path.exists(path_dest):
                            if not path_base or norm_path_sicuro(path_dest) != norm_path_sicuro(path_base):
                                ext_dest = os.path.splitext(path_dest)[1] or ".png"
                                nome_dest = f"dest_root_frame_{copia_idx}{ext_dest}"
                                shutil.copy2(path_dest, os.path.join(comfy_input_dir, nome_dest))
                                file_temporanei_input_da_pulire.append(os.path.join(comfy_input_dir, nome_dest))
                                percorso_fine_passo = nome_dest
                                log.registra(f"Video Engine: Assegnato Frame Finale ({nome_dest}) per interpolazione / FL2VA.")
                    else:
                        if stato_gen is not None:
                            stato_gen["sorgente_corrente_utilizzato"] = ""

                v_seed_str = str(v_seed).strip()
                if v_seed_mode == "fixed" and v_seed_str.isdigit():
                    seed_pulito = int(v_seed_str)
                else:
                    seed_pulito = random.randint(1000000000000, 9999999999999)

                yield from genera_video_con_monitor_passo_comfy(
                    clip_idx, num_clip_totali, durata_clip_corrente, v_durata_effettiva,
                    prompt_clip_corrente, lv1_n_eff, lv1_s_eff, lv2_n_eff, lv2_s_eff, lv3_n_eff, lv3_s_eff,
                    seed_pulito, percorso_inizio_passo, percorso_mid_passo, percorso_fine_passo,
                    v_fps, v_rapporto, v_risoluzione, v_cfg, v_strength, v_compression, v_seed_mode,
                    solo_testo_video, clip_generate_temporanee, file_temporanei_input_da_pulire,
                    ws_url, client_id, dl, is_it, state_ref=stato_gen, m_video_attivo=m_video_attivo,
                    v_steps_vid=v_steps_vid, v_denoise_vid=v_denoise_vid, v_scheduler_vid=v_scheduler_vid
                )

            if clip_generate_temporanee:
                local_dir = os.path.join(config.STUDIO_OUTPUT_DIR, config.STUDIO_VIDEO_SUBDIR)
                os.makedirs(local_dir, exist_ok=True)
                prefisso_file = "minimax_short_film" if m_video_attivo == "MiniMax H3" else "ltx_short_film"
                suff_copia = f"_c{copia_idx+1}" if totale_copie > 1 else ""
                nuovo_nome = config.genera_nome_univoco(local_dir, f"{prefisso_file}{suff_copia}", "mp4")
                dest_path_finale = os.path.abspath(os.path.join(local_dir, nuovo_nome))
                yield gr.update(), ("⏳ Saving and preparing the final video…" if not is_it else "⏳ Salvataggio e preparazione del video finale…"), log.ottieni_tutti_i_log(), stato_gen

                if len(clip_generate_temporanee) > 1:
                    msg_concat = dl.get("video_status_ffmpeg_merge", "🎬 Compiling and merging storyboard segments in progress (FFmpeg)...")
                    yield gr.update(), msg_concat, log.ottieni_tutti_i_log(), stato_gen
                    
                    if fondi_video_mp4_ffmpeg(clip_generate_temporanee, dest_path_finale, durata_clip=durata_clip_corrente):
                        if stato_gen:
                            stato_gen["ultimo_video_generato_path"] = dest_path_finale
                            sessione.salva_sessione({"ultimo_video_generato_path": dest_path_finale})
                        
                        for c_temp in clip_generate_temporanee:
                            try: os.remove(c_temp)
                            except: pass

                        msg_done_film = prefix_copia + dl.get("video_status_done_film", "✅ Short film of {durata:.1f}s successfully generated!").format(durata=v_durata_effettiva)
                        ultimo_video_generato = dest_path_finale
                        yield dest_path_finale, msg_done_film, log.ottieni_tutti_i_log(), stato_gen
                else:
                    log.registra("Spostamento diretto del video generato senza ricodificare la coda...")
                    taglio_ok = sposta_file_sicuro(clip_generate_temporanee[0], dest_path_finale)
                    
                    if taglio_ok:
                        if stato_gen and stato_gen.get("is_extension"):
                            if "clip_chain" not in stato_gen:
                                stato_gen["clip_chain"] = []
                                
                            stato_gen["clip_chain"].append(dest_path_finale)
                            
                            prefisso_fuso = "minimax_film_fuso" if m_video_attivo == "MiniMax H3" else "ltx_film_fuso"
                            nuovo_nome_fuso = config.genera_nome_univoco(local_dir, f"{prefisso_fuso}{suff_copia}", "mp4")
                            dest_path_fuso = os.path.abspath(os.path.join(local_dir, nuovo_nome_fuso))
                            
                            log.registra(f"Extension: Detected {len(stato_gen['clip_chain'])} segments. Starting automatic merge...")
                            
                            if fondi_video_mp4_ffmpeg(stato_gen["clip_chain"], dest_path_fuso, durata_clip=None):
                                stato_gen["ultimo_video_generato_path"] = dest_path_fuso
                                sessione.salva_sessione({"ultimo_video_generato_path": dest_path_fuso})
                                
                                stato_gen["clip_chain"] = [dest_path_fuso]
                                stato_gen["is_extension"] = False 
                                
                                msg_done_ext = prefix_copia + dl.get("video_status_done_extended", "✅ Short film successfully extended and merged! New overall duration recorded.")
                                ultimo_video_generato = dest_path_fuso
                                yield dest_path_fuso, msg_done_ext, log.ottieni_tutti_i_log(), stato_gen
                        else:
                            if stato_gen:
                                stato_gen["ultimo_video_generato_path"] = dest_path_finale
                                stato_gen["clip_chain"] = [dest_path_finale] 
                                stato_gen["is_extension"] = False
                                sessione.salva_sessione({"ultimo_video_generato_path": dest_path_finale})
                                
                            msg_done_std = prefix_copia + dl.get("video_status_done_continuous", "✅ Continuous video of {durata:.1f}s successfully generated!").format(durata=v_durata_effettiva)
                            ultimo_video_generato = dest_path_finale
                            yield dest_path_finale, msg_done_std, log.ottieni_tutti_i_log(), stato_gen

        if ultimo_video_generato:
            return

        if not comfyui_manager.generazione_attiva:
            return

        msg_err_gen_total = dl.get("video_err_generation_failed", "❌ Error during video clip generation.")
        yield gr.update(), msg_err_gen_total, log.ottieni_tutti_i_log(), stato_gen

    except Exception as e:
        import traceback
        log.registra(f"Monitored video generation error: {e}", "ERROR")
        log.registra(traceback.format_exc(), "ERROR")
        yield gr.update(), f"❌ Error: {e}", log.ottieni_tutti_i_log(), stato_gen

    finally:
        comfyui_manager.generazione_attiva = False
        for f_pulire in file_temporanei_input_da_pulire:
            if os.path.exists(f_pulire):
                try: os.remove(f_pulire)
                except: pass
