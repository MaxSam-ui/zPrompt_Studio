# services/director_ai.py

import os
import re
import gradio as gr
from core import config, log, sessione, lingua
from services import local_vlm
from utils.media_base import norm_path_sicuro
from utils.vlm_status import VLMStatus
from utils.storyboard_video_context import scene_context


def _errore_vlm(chunk):
    return str(chunk).strip().startswith(("❌", "Errore", "Error", "⚠", "⏹", "🛑"))


def _stato_errore_vlm(chunk):
    testo = str(chunk).strip()
    return "❌ " + testo if testo.startswith(("Errore", "Error")) else testo


def _verifica_stop_regia():
    from services import comfyui_manager
    if comfyui_manager.vlm_interrotto:
        raise InterruptedError("Director operation stopped")


def _estrai_descrizione_frame_sicura(filepath, stato_gen=None, sys_prompt_vision="", model_vision=""):
    """
    Recupera la descrizione dettagliata in lingua inglese di un fotogramma da:
    1. Metadati PNG/EXIF
    2. File .txt adiacente
    3. Analisi visiva VLM rapida in background
    """
    _verifica_stop_regia()
    if not filepath or not os.path.exists(filepath):
        return ""

    # Cropped panels have a dedicated scene description. Embedded metadata
    # can still belong to the original full grid, especially after refinement.
    panel_txt = os.path.splitext(filepath)[0] + ".txt"
    if re.search(r'(?:panel|refined)', os.path.basename(filepath), re.I) and os.path.isfile(panel_txt):
        try:
            with open(panel_txt, encoding="utf-8") as source:
                description = scene_context(source.read())
            if description:
                return description
        except (OSError, UnicodeError):
            pass

    try:
        from generators.metadata_extractor import estrai_info_da_immagine
        from PIL import Image
        with Image.open(filepath) as im:
            prompt_meta, _ = estrai_info_da_immagine(im)
            if prompt_meta and prompt_meta.strip():
                log.registra(f"Director AI: Loaded visual prompt from PNG metadata ({filepath})")
                return scene_context(prompt_meta)
    except Exception as e:
        log.registra(f"Director AI: PNG metadata extraction warning: {e}", "WARNING")

    txt_path = os.path.splitext(filepath)[0] + ".txt"
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f_txt:
                c = f_txt.read().strip()
                if c:
                    log.registra(f"Director AI: Loaded visual prompt from adjacent txt ({txt_path})")
                    return scene_context(c)
        except Exception:
            pass

    try:
        from PIL import Image
        with Image.open(filepath) as im:
            desc_vlm = ""
            s_attiva = sessione.carica_ultima_sessione()
            default_vlm = s_attiva.get("modello_vlm", "huihui_ai/qwen3-vl-abliterated:8b")
            m_vlm = model_vision if (model_vision and model_vision.strip()) else default_vlm
            sys_p = sys_prompt_vision if (sys_prompt_vision and sys_prompt_vision.strip()) else "Describe this image in detail for a video generation baseline."
            
            for chunk in local_vlm.genera_prompt_immagine(
                im, sys_p, 
                "Focus on colors, subject physical traits, clothing, lighting, and background environment. Return one fluid paragraph in ENGLISH.", 
                m_vlm, 
                max_new_tokens=256
            ):
                _verifica_stop_regia()
                if _errore_vlm(chunk):
                    raise RuntimeError(str(chunk))
                if isinstance(chunk, VLMStatus):
                    continue
                desc_vlm = chunk
            if desc_vlm and desc_vlm.strip():
                return desc_vlm.strip()
    except Exception as e:
        log.registra(f"Director AI: VLM image description error: {e}", "WARNING")
        raise

    return ""


def scrivi_sceneggiatura_automatica(prompt_img, model_vid, idea_utente, durata_totale, stato_gen=None, sys_prompt_vision="", model_vision="", solo_testo_video=None, timeline_corrente=None, audio_corrente=None):
    """
    Uses LLM to automatically generate a chronological camera blocking timeline.
    Pre-computes perfectly balanced mathematical time slices to prevent uneven clips.
    """
    prompt_img = scene_context(prompt_img)
    from services import comfyui_manager
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    
    s_attiva = sessione.carica_ultima_sessione()
    dl = lingua.LINGUE.get(s_attiva.get("lingua_selezionata", "IT"), lingua.LINGUE["IT"])
    precedenti = (timeline_corrente if timeline_corrente is not None else gr.update(),
                  prompt_img, audio_corrente if audio_corrente is not None else gr.update())
    if not idea_utente or not idea_utente.strip():
        comfyui_manager.generazione_attiva = False
        yield *precedenti, dl["director_missing_subject"]
        return

    try:
        is_t2v = bool(s_attiva.get("solo_testo_video_attivo", False) if solo_testo_video is None else solo_testo_video)

        filepath_start = None if is_t2v else ((stato_gen.get("percorso_immagine_selezionata") if stato_gen else None) or s_attiva.get("percorso_immagine_selezionata"))
        filepath_dest = None if is_t2v else ((stato_gen.get("percorso_immagine_destinazione") if stato_gen else None) or s_attiva.get("percorso_immagine_destinazione"))

        if is_t2v:
            prompt_img = ""
        elif not prompt_img or not prompt_img.strip():
            if filepath_start and os.path.exists(filepath_start):
                yield gr.update(), gr.update(), gr.update(), dl["director_analyzing_start"]
                prompt_img = _estrai_descrizione_frame_sicura(filepath_start, stato_gen, sys_prompt_vision, model_vision=model_vision or model_vid)
        
            if not prompt_img or not prompt_img.strip():
                prompt_img = "A high quality cinematic opening scene."

        desc_last_frame = ""
        has_last_frame = bool(
            not is_t2v and filepath_dest and os.path.exists(filepath_dest) and
            (not filepath_start or norm_path_sicuro(filepath_dest) != norm_path_sicuro(filepath_start))
        )
    
        if has_last_frame:
            yield gr.update(), gr.update(), gr.update(), dl["director_analyzing_end"]
            desc_last_frame = _estrai_descrizione_frame_sicura(filepath_dest, stato_gen, sys_prompt_vision, model_vision=model_vision or model_vid)
            log.registra(f"AI Screenwriter: Dual-frame interpolation active (Start: '{os.path.basename(filepath_start or '')}' -> End: '{os.path.basename(filepath_dest)}')")

        _verifica_stop_regia()

        from core.config import TIPI_INQUADRATURA, TIPI_ZOOM
        lista_inquadrature = ", ".join([f"'{i}'" for i in TIPI_INQUADRATURA])
        lista_zoom_str = ", ".join([f"'{z}'" for z in TIPI_ZOOM])
    
        dur_f = float(durata_totale)
        if not 0 < dur_f < float("inf"):
            raise ValueError("Invalid timeline duration")
        video_num_clips = max(1, int(dur_f) // 4)
        if int(dur_f) % 4 >= 2 and int(dur_f) > 4:
            video_num_clips += 1

        step = dur_f / float(video_num_clips)
        intervalli = []
        t_start = 0.0
        for k in range(video_num_clips):
            t_end = dur_f if k == video_num_clips - 1 else round(t_start + step, 1)
            intervalli.append(f"[{t_start:.1f}s - {t_end:.1f}s]")
            t_start = t_end

        intervalli_formattati = "\n".join([f"   Line {i+1}: {inv} Shot Type | Camera Motion | Concise Action | Foley Sound" for i, inv in enumerate(intervalli)])

        if not is_t2v and has_last_frame and desc_last_frame:
            frame_context = (
                f"STARTING FRAME 1 (SCENE START):\n"
                f"'{prompt_img}'\n\n"
                f"DESTINATION FRAME (SCENE END):\n"
                f"'{desc_last_frame}'\n\n"
                f"MANDATORY TRANSITION OBJECTIVE: Construct a logical progression starting from STARTING FRAME 1 and ending with the pose/setting of DESTINATION FRAME.\n"
            )
        elif not is_t2v and prompt_img and prompt_img.strip():
            frame_context = (
                f"STARTING FRAME 1 (SCENE START):\n"
                f"'{prompt_img}'\n\n"
            )
        else:
            frame_context = ""

        from utils.prompt_templates import SCENE_CONTRACT, render_template, system_template
        template_sceneggiatore = render_template(system_template("Screenwriter.txt",
            "Return exactly {video_num_clips} lines: {intervalli_formattati}. Idea: {idea_utente}. {frame_context} Shot types: {lista_inquadrature}. Camera moves: {lista_zoom}. End with [GLOBAL_AUDIO]."),
            durata=dur_f, video_num_clips=video_num_clips, idea_utente=idea_utente,
            frame_context=frame_context, prompt_img=prompt_img,
            intervalli_formattati=intervalli_formattati, primo_intervallo=intervalli[0],
            lista_inquadrature=lista_inquadrature, lista_zoom=lista_zoom_str) + "\n\n" + SCENE_CONTRACT

        accumulato = ""
        for chunk in local_vlm.genera_prompt_video_timeline(template_sceneggiatore, model_vid, timeout=120, preserve_content=True):
            if getattr(comfyui_manager, "vlm_interrotto", False):
                break
            if _errore_vlm(chunk):
                yield *precedenti, _stato_errore_vlm(chunk)
                return
            if isinstance(chunk, VLMStatus):
                yield gr.update(), gr.update(), gr.update(), str(chunk)
                continue
            accumulato = chunk
            timeline_pulita, audio_globale = _estrai_global_audio(accumulato)
            yield timeline_pulita, gr.update() if is_t2v else prompt_img, audio_globale, dl["script_writing_status"]
            
        if getattr(comfyui_manager, "vlm_interrotto", False):
            yield *precedenti, dl["msg_interruzione_idea"]
            return
        from utils import timeline
        timeline_pulita, audio_globale = _estrai_global_audio(accumulato)
        blocchi = timeline._parse_timeline(timeline_pulita)
        if len(blocchi) != video_num_clips or abs(sum(b["durata"] for b in blocchi) - dur_f) > 0.15:
            yield *precedenti, dl["director_invalid_timeline"]
            return
        yield timeline_pulita, gr.update() if is_t2v else prompt_img, audio_globale, dl["director_timeline_success"]
    except InterruptedError:
        yield *precedenti, dl["msg_interruzione_idea"]
    except Exception as e:
        log.registra(f"Screenplay generation error: {e}", "ERROR")
        yield *precedenti, dl["director_generation_error"].format(error=e)
    finally:
        comfyui_manager.generazione_attiva = False


def migliora_soggetto_con_vlm(soggetto_corrente, modello, stato_gen, prompt_img="", solo_testo_video=None):
    """
    Crea o migliora il soggetto cinematografico in lingua inglese,
    ancorando la scena in modo prioritario e assoluto all'immagine di partenza (Frame 1).
    """
    prompt_img = scene_context(prompt_img)
    from services import comfyui_manager
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True

    s_attiva = sessione.carica_ultima_sessione()
    is_t2v = bool(s_attiva.get("solo_testo_video_attivo", False) if solo_testo_video is None else solo_testo_video)
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))

    try:
        filepath_start = None if is_t2v else ((stato_gen.get("percorso_immagine_selezionata") if stato_gen else None) or s_attiva.get("percorso_immagine_selezionata"))
        filepath_dest = None if is_t2v else ((stato_gen.get("percorso_immagine_destinazione") if stato_gen else None) or s_attiva.get("percorso_immagine_destinazione"))

        desc_start = ""
        if not is_t2v:
            if prompt_img and prompt_img.strip():
                desc_start = prompt_img.strip()
            elif filepath_start and os.path.exists(filepath_start):
                yield gr.update(), dl["director_analyzing_start"]
                desc_start = _estrai_descrizione_frame_sicura(filepath_start, stato_gen, model_vision=modello)

        desc_last = ""
        if not is_t2v and filepath_dest and os.path.exists(filepath_dest) and (not filepath_start or norm_path_sicuro(filepath_dest) != norm_path_sicuro(filepath_start)):
            yield gr.update(), dl["director_analyzing_end"]
            desc_last = _estrai_descrizione_frame_sicura(filepath_dest, stato_gen, model_vision=modello)

        _verifica_stop_regia()

        testo_utente = (soggetto_corrente or "").strip()

        if not is_t2v and desc_start:
            dest_context = f"\nDESTINATION FRAME (SCENE CONCLUSION):\n'{desc_last.strip()}'\n" if desc_last else ""
        
            if not testo_utente:
                msg_avvio = dl.get("msg_creating_subject", "🪄 AI Writer: Creating cinematic subject from image...")
                yield gr.update(), msg_avvio
                prompt = (
                    f"You are an elite Hollywood cinematic director and visual storyteller.\n"
                    f"Analyze the following STARTING FRAME description representing the opening frame of the scene:\n\n"
                    f"STARTING FRAME DESCRIPTION:\n'{desc_start}'\n"
                    f"{dest_context}\n"
                    f"TASK: Create an engaging, active, and descriptive cinematic movie scene subject in ENGLISH (35-45 words) that organically begins from this EXACT visual composition.\n"
                    f"Describe the relevant subjects or objects, visible changes, environment and mood.\n\n"
                    f"MANDATORY RULES:\n"
                    f"1. Preserve the subjects, objects, visual medium and location described in the STARTING FRAME.\n"
                    f"2. Output ONLY the final refined movie subject paragraph in English, without conversational preamble, notes, or labels.\n\n"
                    f"CINEMATIC SUBJECT:"
                )
            else:
                msg_avvio = dl.get("msg_improving_subject", "🪄 AI Writer: Enhancing subject with visual frame...")
                yield gr.update(), msg_avvio
                prompt = (
                    f"You are an elite Hollywood cinematic director and visual storyteller.\n\n"
                    f"STARTING FRAME (VISUAL ANCHOR):\n'{desc_start}'\n"
                    f"{dest_context}\n"
                    f"USER DIRECTION / ACTION IDEA:\n'{testo_utente}'\n\n"
                    f"TASK: Fuse the USER DIRECTION into a coherent scene featuring the subjects or objects and setting seen in the STARTING FRAME (maximum 40-50 words in ENGLISH).\n\n"
                    f"MANDATORY RULES:\n"
                    f"1. The visual identity, character appearance, and location MUST come from the STARTING FRAME.\n"
                    f"2. The physical action and narrative flow MUST incorporate the USER DIRECTION.\n"
                    f"3. Output ONLY the final enhanced cinematic subject in English, without intros, labels, or chat.\n\n"
                    f"ENHANCED CINEMATIC SUBJECT:"
                )
        else:
            msg_avvio = dl.get("msg_creating_subject", "🪄 AI Writer: Writing cinematic subject...")
            yield gr.update(), msg_avvio
            prompt = (
                f"Write a concrete, filmable scene description in ENGLISH.\n"
                f"Refine the supplied idea without changing its meaning. Use only the words needed; no minimum length.\n"
                f"Preserve each subject's identity, action, speed, camera direction and requested sounds. "
                f"Do not invent scenery, people, props or events. Avoid metaphors and poetic personification. "
                f"A fixed camera does not make a moving subject stationary. Keep no-voice and no-music constraints explicit.\n"
                f"RAW IDEA:\n'{testo_utente if testo_utente else 'A dramatic cinematic movie opening scene'}'\n\n"
                f"MANDATORY RULE: Output ONLY the final refined movie subject paragraph in English, without preamble or notes.\n\n"
                f"CINEMATIC SUBJECT:"
            )

        from utils.prompt_templates import SCENE_CONTRACT
        prompt += "\n\n" + SCENE_CONTRACT
        accumulato = ""
        for chunk in local_vlm.genera_prompt_video_timeline(prompt, modello, timeout=60):
            if getattr(comfyui_manager, "vlm_interrotto", False):
                break
            if _errore_vlm(chunk):
                yield soggetto_corrente, _stato_errore_vlm(chunk)
                return
            if isinstance(chunk, VLMStatus):
                yield gr.update(), str(chunk)
                continue
            from utils.director_prompt import preserve_identity_tokens
            accumulato = preserve_identity_tokens(chunk, soggetto_corrente)
            msg_prog = dl.get("msg_improving_subject", "🪄 AI Writer at work...")
            yield accumulato.strip(), msg_prog
            
        if getattr(comfyui_manager, "vlm_interrotto", False):
            msg_stop = dl.get("msg_interruzione_idea", "⏹️ Interrupted.")
            yield soggetto_corrente, msg_stop
            return
            
        if not accumulato.strip():
            yield soggetto_corrente, dl["analysis_empty_result"]
            return
        msg_success = dl.get("msg_subject_success", "✅ Cinematic subject successfully compiled from image!")
        yield accumulato.strip(), msg_success
    except InterruptedError:
        yield soggetto_corrente, dl["msg_interruzione_idea"]
    except Exception as e:
        log.registra(f"Subject creation/refinement error: {e}", "ERROR")
        yield soggetto_corrente, dl["director_generation_error"].format(error=e)
    finally:
        comfyui_manager.generazione_attiva = False


def genera_dialoghi_timeline(testo_timeline, soggetto, modello, stato_gen):
    from services import comfyui_manager
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True

    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))
    
    if not testo_timeline or not testo_timeline.strip():
        comfyui_manager.generazione_attiva = False
        yield gr.update(), dl["director_missing_timeline"]
        return

    prompt = (
        f"You are a master screenwriter specializing in short cinematic dialogues.\n"
        f"Below is a movie subject and its chronological camera blocking timeline.\n\n"
        f"SUBJECT:\n'{soggetto if soggetto else 'A cinematic scene'}'\n\n"
        f"TIMELINE:\n{testo_timeline}\n\n"
        f"Your task is to generate short, intense character dialogues for relevant clips where appropriate.\n"
        f"Generate dialogues ONLY for clips with speaking characters. Do not invent speakers for landscapes, objects or ordinary animals; respect explicit silence. If no dialogue applies, return no numbered entries.\n"
        f"Format your output EXACTLY as a list of clip numbers and their respective dialogue, like this:\n"
        f"1: \"Dialogue text here\"\n"
        f"3: \"Another dialogue text here\"\n\n"
        f"Rules:\n"
        f"1. Keep dialogues extremely short (maximum 4-7 words per clip).\n"
        f"2. Output ONLY the list of clip numbers and dialogues. Use the explicitly requested spoken language, otherwise English. Do not write intros, explanations, or code blocks."
    )
    
    try:
        accumulato = ""
        for chunk in local_vlm.genera_prompt_video_timeline(prompt, modello, timeout=90):
            if getattr(comfyui_manager, "vlm_interrotto", False):
                break
            if _errore_vlm(chunk):
                yield testo_timeline, _stato_errore_vlm(chunk)
                return
            if isinstance(chunk, VLMStatus):
                yield gr.update(), str(chunk)
                continue
            accumulato = chunk
            msg_dial_prog = dl.get("msg_generating_dialogues", "💬 AI Screenplay: Writing character dialogue...")
            yield gr.update(), msg_dial_prog
            
        if getattr(comfyui_manager, "vlm_interrotto", False):
            msg_stop = dl.get("msg_interruzione_idea", "⏹️ Interrupted.")
            yield testo_timeline, msg_stop
            return

        linee_dialogo = {}
        for line in accumulato.strip().split("\n"):
            line = line.strip()
            match = re.search(r'(?:clip\s*)?(\d+)\s*:\s*["\']?(.*?)["\']?\s*$', line, re.IGNORECASE)
            if match:
                try:
                    idx = int(match.group(1)) - 1
                    diag = match.group(2).strip().strip('"\'')
                    if diag:
                        linee_dialogo[idx] = diag
                except ValueError:
                    continue

        from utils import timeline
        blocchi = timeline._parse_timeline(testo_timeline)
        
        linee_dialogo = {idx: diag for idx, diag in linee_dialogo.items() if 0 <= idx < len(blocchi)}
        if not linee_dialogo:
            yield testo_timeline, dl["director_no_dialogues"]
            return
        for idx, diag in linee_dialogo.items():
            if 0 <= idx < len(blocchi):
                existing_mov = blocchi[idx]["mov"].strip()

                if f'"{diag}"' not in existing_mov:
                    prefissi = ["whispers", "says quietly", "speaks firmly", "murmurs"]
                    prefisso = prefissi[idx % len(prefissi)]
                    nuovo_mov = f"{existing_mov.rstrip('. ')}, {prefisso}: \"{diag}\"."
                    blocchi[idx]["mov"] = nuovo_mov

        nuovo_testo_timeline = timeline._build_timeline_text(blocchi)
        msg_success = dl.get("dialogue_success_msg", "✅ Dialogues successfully integrated into timeline!")
        yield nuovo_testo_timeline, msg_success

    except Exception as e:
        log.registra(f"Dialogue insertion error: {e}", "ERROR")
        yield testo_timeline, dl["director_generation_error"].format(error=e)
    finally:
        comfyui_manager.generazione_attiva = False


def _estrai_global_audio(testo):
    """
    Separa in modo pulito e infallibile la timeline dall'audio globale:
    1. Rimuove blocchi di pensiero <think>...</think> di Qwen3.
    2. Isola con certezza assoluta le righe della timeline con timestamp [start - end].
    3. Estrae la descrizione dell'audio globale.
    """
    if not testo:
        return "", ""

    testo_senza_think = re.sub(r'<think>[\s\S]*?</think>', '', testo, flags=re.IGNORECASE)
    testo_senza_think = re.sub(r'<think>[\s\S]*$', '', testo_senza_think, flags=re.IGNORECASE).strip()
    if not testo_senza_think:
        return "", ""

    pattern_tempo = re.compile(r'\[\s*\d+(?:\.\d+)?\s*s?\s*-\s*\d+(?:\.\d+)?\s*s?\s*\]')
    pattern_marker_audio = re.compile(
        r'(?:(?:\*\*|#{1,4}\s*)?\[?(?:GLOBAL[_\s\-]?(?:AUDIO|ATMOSPHERIC|SOUNDS?)(?:[_\s\-]?(?:ATMOSPHERE|SOUNDS?|DESCRIPTION|DIRECTIVE))?)\]?(?:\*\*|:|\s*-\s*)*|'
        r'(?:\*\*|#{1,4}\s*)?(?:Global\s*Audio|Global\s*Atmospheric\s*Sound|Audio\s*Globale|Atmosfera\s*Audio)(?:\*\*|:|\s*-\s*)*)',
        re.IGNORECASE
    )

    righe = testo_senza_think.split("\n")
    righe_timeline = []
    righe_audio = []
    in_sezione_audio = False

    for r in righe:
        r_strip = r.strip()
        if not r_strip:
            continue

        if pattern_tempo.search(r_strip):
            # Some models append GLOBAL_AUDIO to the last clip on the same
            # line. Separate it before parsing the clip's pipe fields.
            marker_inline = pattern_marker_audio.search(r_strip)
            if marker_inline:
                righe_timeline.append(r_strip[:marker_inline.start()].rstrip(' |'))
                r_strip = r_strip[marker_inline.start():]
            else:
                righe_timeline.append(r_strip)
                in_sezione_audio = False
                continue

        if pattern_marker_audio.search(r_strip):
            in_sezione_audio = True
            audio_inline = pattern_marker_audio.sub('', r_strip).strip()
            audio_inline = re.sub(r'^[\]\s*:*-*]+', '', audio_inline).strip()
            audio_inline = re.sub(r'[*`"]+', '', audio_inline).strip()
            if audio_inline and len(audio_inline) > 2:
                righe_audio.append(audio_inline)
            continue

        if in_sezione_audio:
            audio_clean = re.sub(r'^[\]\s*:*-*]+', '', r_strip).strip()
            audio_clean = re.sub(r'[*`"]+', '', audio_clean).strip()
            if audio_clean and not any(kw in audio_clean.lower() for kw in ["hope this", "let me know", "feel free", "note:"]):
                righe_audio.append(audio_clean)

    timeline_pulita = "\n".join(righe_timeline)
    audio_globale = " ".join(righe_audio).strip()

    if not audio_globale and righe_timeline:
        from utils import timeline
        blocchi = timeline._parse_timeline(timeline_pulita)
        suoni = [b.get("audio", "").strip().strip('"\'') for b in blocchi if b.get("audio")]
        suoni_unici = [s for s in suoni if s and len(s) > 2]
        if suoni_unici:
            audio_globale = ", ".join(dict.fromkeys(suoni_unici))

    return timeline_pulita, audio_globale


def spezza_prompt_regia_in_tag_clip(p_video, durata_totale_int, video_num_clips=None):
    dizionario_clip = {}
    
    pattern_xml = re.compile(r'<clip[_\s]?(\d+)>(.*?)</clip[_\s]?\1>', re.DOTALL | re.IGNORECASE)
    matches_xml = pattern_xml.findall(p_video)
    
    for tag_num, contenuto in matches_xml:
        dizionario_clip[f"clip_{tag_num}"] = contenuto.strip()
        
    if not dizionario_clip:
        pattern_trunc = re.compile(r'<clip[_\s]?(\d+)>(.*?)(?=<clip[_\s]?\d+>|$)', re.DOTALL | re.IGNORECASE)
        matches_trunc = pattern_trunc.findall(p_video)
        for tag_num, contenuto in matches_trunc:
            contenuto_pulito = re.sub(r'</clip[_\s]?\d+>', '', contenuto, flags=re.IGNORECASE).strip()
            if contenuto_pulito:
                dizionario_clip[f"clip_{tag_num}"] = contenuto_pulito

    if not dizionario_clip:
        sezioni = re.split(r'(?:\[(?:CLIP|SPEZZONE|SCENA)\s*(\d+)\]|(?:\*\*|\*|\b)(?:CLIP|SPEZZONE|SCENA)\s*(\d+)(?:\*\*|\*|\b|:))', p_video, flags=re.IGNORECASE)
        if len(sezioni) > 1:
            i = 1
            while i < len(sezioni):
                num_clip_1 = sezioni[i]
                num_clip_2 = sezioni[i+1]
                contenuto = sezioni[i+2] if i+2 < len(sezioni) else ""
                
                num = num_clip_1 or num_clip_2
                if num and contenuto:
                    dizionario_clip[f"clip_{int(num)}"] = contenuto.strip()
                i += 3
                
    if not dizionario_clip:
        righe_num = re.findall(r'(?:^|\n)\s*(\d+)\s*[\.:-]\s*(.*?)(?=(?:\n\s*\d+\s*[\.:-])|$)', p_video, re.DOTALL)
        for num, contenuto in righe_num:
            dizionario_clip[f"clip_{num}"] = contenuto.strip()

    if video_num_clips is not None:
        num_clip_richieste = int(video_num_clips)
    else:
        num_clip_richieste = (durata_totale_int - 1) // 4 + 1
        
    if num_clip_richieste < 1:
        num_clip_richieste = 1
        
    for k in range(1, num_clip_richieste + 1):
        chiave_clip = f"clip_{k}"
        if chiave_clip not in dizionario_clip:
            dizionario_clip[chiave_clip] = p_video

    return dizionario_clip


def passa_timeline_a_gemma(prompt_img, model_vid, testo, audio_descrizione="", v_durata=4.0, stato_gen=None, sys_prompt_vision="", model_vision="", stile_regista="01_default_director", solo_testo_video=None, prompt_corrente=None, soggetto=None):
    """
    Compiles chronological camera timeline, audio descriptions, and Start/End frames into a master video prompt.
    Selects the final model format before generation; repairs invalid output once.
    """
    prompt_img = scene_context(prompt_img)
    from services import comfyui_manager
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True

    s_attiva = sessione.carica_ultima_sessione()
    dl = lingua.LINGUE.get(s_attiva.get("lingua_selezionata", "IT"), lingua.LINGUE["IT"])
    soggetto = str(soggetto if soggetto is not None else s_attiva.get("sceneggiatura_prompt", "") or "").strip()
    precedenti = (prompt_corrente if prompt_corrente is not None else gr.update(), prompt_img)
    from utils import timeline
    blocchi = timeline._parse_timeline(testo)
    if not blocchi:
        comfyui_manager.generazione_attiva = False
        yield *precedenti, dl["director_missing_timeline"]
        return

    try:
        is_t2v = bool(s_attiva.get("solo_testo_video_attivo", False) if solo_testo_video is None else solo_testo_video)

        filepath_start = None if is_t2v else ((stato_gen.get("percorso_immagine_selezionata") if stato_gen else None) or s_attiva.get("percorso_immagine_selezionata"))
        if is_t2v:
            prompt_img = ""
        elif not prompt_img or not prompt_img.strip():
            if filepath_start and os.path.exists(filepath_start):
                yield gr.update(), gr.update(), dl["director_analyzing_start"]
                prompt_img = _estrai_descrizione_frame_sicura(filepath_start, stato_gen, sys_prompt_vision, model_vision)
            if not prompt_img or not prompt_img.strip():
                prompt_img = "A high quality cinematic opening scene."

        filepath_dest = None if is_t2v else ((stato_gen.get("percorso_immagine_destinazione") if stato_gen else None) or s_attiva.get("percorso_immagine_destinazione"))
        desc_last_frame = ""
        has_last_frame = bool(
            not is_t2v and filepath_dest and os.path.exists(filepath_dest) and
            (not filepath_start or norm_path_sicuro(filepath_dest) != norm_path_sicuro(filepath_start))
        )
    
        if has_last_frame:
            yield gr.update(), gr.update(), dl["director_analyzing_end"]
            desc_last_frame = _estrai_descrizione_frame_sicura(filepath_dest, stato_gen, sys_prompt_vision, model_vision)
            log.registra(f"AI Director: Compiling master screenplay with Start and End frame anchoring.")

        _verifica_stop_regia()

        lista_scene = []
        for b in blocchi:
            tipo_pulito = timeline._pulisci_scelta_ui(b["tipo"])
            zoom_pulito = timeline._pulisci_scelta_ui(b["zoom"])
            lista_scene.append([b["durata"], tipo_pulito, zoom_pulito, b["mov"], b.get("audio", "")])
    
        cronologia = cronologia_regia_testo(lista_scene)
        audio_section = f"\nAUDIO ATMOSPHERE DESCRIPTION:\n'{audio_descrizione.strip()}'\n" if (audio_descrizione and audio_descrizione.strip()) else ""

        name_stile = stile_regista if stile_regista and stile_regista not in ["Nessuno", "None", "nessuno", "none", "-"] else "01_default_director"
        nome_stile_sicuro = os.path.basename(name_stile)
        path_stile_regista = os.path.join(config.SUGGESTION_DIRECTION_DIR, f"{nome_stile_sicuro}.txt")
        stile_regole_testo = ""
        if os.path.exists(path_stile_regista):
            try:
                with open(path_stile_regista, "r", encoding="utf-8") as f:
                    stile_regole_testo = f.read().strip()
                log.registra(f"Director Style loaded: '{nome_stile_sicuro}'")
            except Exception as e:
                log.registra(f"Error reading director style: {e}", "WARNING")
            
        if not stile_regole_testo:
            stile_regole_testo = (
                "- Focus on realistic physical actions, explicit spatial layout (left, right, foreground), and natural motion.\n"
                "- Describe fine materials, fabric textures, and edge details under dynamic light."
            )

        if not is_t2v and has_last_frame and desc_last_frame:
            frame_block = (
                f"STARTING FRAME 1 DESCRIPTION (SCENE START):\n"
                f"'{prompt_img}'\n\n"
                f"DESTINATION FRAME DESCRIPTION (SCENE CONCLUSION):\n"
                f"'{desc_last_frame}'\n\n"
                f"MANDATORY CONTINUITY & INTERPOLATION BRIDGE DIRECTIVE:\n"
                f"The screenplay MUST smoothly connect the initial composition and subject posture of STARTING FRAME 1 to the final pose, lighting, and framing of DESTINATION FRAME across the timed sequence.\n\n"
            )
        elif not is_t2v and prompt_img and prompt_img.strip():
            frame_block = (
                f"STARTING FRAME 1 DESCRIPTION:\n"
                f"'{prompt_img}'\n\n"
            )
        else:
            frame_block = ""

        if s_attiva.get("modello_video_attivo") == "MiniMax H3":
            from utils.video_model_prompt import minimax_compiler_instruction, minimax_sections, MINIMAX_SECTIONS
            from utils.director_prompt import align_director_prompt, preserve_identity_tokens
            from utils.video_preflight import validate_video_request
            references = 0 if is_t2v else int(bool(filepath_start)) + int(has_last_frame)
            source = (f"AUTHORITATIVE SUBJECT:\n{soggetto}\n{frame_block}"
                      f"AUTHORITATIVE TIMELINE:\n{cronologia}{audio_section}")
            instruction = minimax_compiler_instruction(source, references, direct=True)
            instruction += ("\nDIRECTOR STYLE (subordinate to supplied identities, actions and constraints):\n"
                            + stile_regole_testo)
            original_instruction = instruction
            # A valid model-specific result needs one call. Only invalid output
            # triggers one bounded repair, using the original scene as authority.
            for attempt in range(2):
                phase = dl["director_repairing_status"] if attempt else dl["director_compiling_status"]
                yield gr.update(), gr.update(), phase
                structured = ""
                for chunk in local_vlm.genera_prompt_video_timeline(instruction, model_vid, timeout=120, preserve_content=True):
                    _verifica_stop_regia()
                    if _errore_vlm(chunk):
                        yield *precedenti, _stato_errore_vlm(chunk)
                        return
                    if isinstance(chunk, VLMStatus):
                        yield gr.update(), gr.update(), str(chunk)
                        continue
                    structured = chunk
                    yield gr.update(), gr.update(), phase
                _verifica_stop_regia()
                yield gr.update(), gr.update(), dl["director_validating_status"]
                parts = minimax_sections(structured.strip())
                aligned = align_director_prompt(parts['detailed_description'], lista_scene) if parts else None
                if parts and aligned is not None:
                    parts['detailed_description'] = aligned
                    candidate = '\n\n'.join(f'{key}:\n{parts[key]}' for key in MINIMAX_SECTIONS)
                    if (not validate_video_request(candidate, sum(float(scene[0]) for scene in lista_scene))
                            and preserve_identity_tokens(candidate, source) == candidate):
                        yield candidate, gr.update() if is_t2v else prompt_img, dl["director_compile_success"]
                        return
                if attempt == 0:
                    log.registra("MiniMax direct prompt invalid; requesting one source-preserving repair.", "WARNING")
                    instruction = (original_instruction + "\nRepair the invalid draft below. Preserve the authoritative source, "
                                   "all literal identity tokens, all six sections, and exactly the supplied time intervals.\n"
                                   "INVALID DRAFT:\n" + structured)
            raise ValueError("MiniMax prompt: invalid structure, timeline or identity tokens; previous prompt preserved.")

        from utils.prompt_templates import SCENE_CONTRACT, render_template, system_template
        template_master = render_template(system_template("Master_Director_Template.txt",
            "Compile an English video prompt preserving this timeline and its camera directions: {cronologia}. {frame_context} {audio_section} Style: {regole_estetiche_regista}"),
            frame_context=frame_block, prompt_img=prompt_img, cronologia=cronologia,
            audio_section=audio_section, regole_estetiche_regista=stile_regole_testo) + "\n\n" + SCENE_CONTRACT

        if soggetto:
            template_master += ("\n\nAUTHORITATIVE SUBJECT AND CHARACTER DESCRIPTION:\n" + soggetto +
                "\nRetain the identities, literal names and model trigger tokens, appearance and wardrobe. "
                "The timeline controls action order and duration; reference frames, when present, control visible composition. "
                "Do not replace a named person with an anonymous generic person. "
                "Begin your output with 'Subject and scene: ' followed by a faithful English translation of this subject, "
                "including its appearance details and constraints. Keep literal names and trigger tokens unchanged. "
                "Then add a blank line and the timed direction spans. Do not copy non-English visual prose verbatim.")
        accumulato = ""
        for chunk in local_vlm.genera_prompt_video_timeline(template_master, model_vid, timeout=120, preserve_content=True):
            if getattr(comfyui_manager, "vlm_interrotto", False):
                break
            if _errore_vlm(chunk):
                yield *precedenti, _stato_errore_vlm(chunk)
                return
            if isinstance(chunk, VLMStatus):
                yield gr.update(), gr.update(), str(chunk)
                continue
            accumulato = chunk
            yield accumulato, gr.update() if is_t2v else prompt_img, dl["director_compiling_status"]
            
        if getattr(comfyui_manager, "vlm_interrotto", False):
            yield *precedenti, dl["msg_interruzione_idea"]
            return
        if not accumulato.strip():
            yield *precedenti, dl["analysis_empty_result"]
            return
        from utils.director_prompt import align_director_prompt
        yield gr.update(), gr.update(), dl["director_validating_status"]
        compiled = align_director_prompt(accumulato.strip(), lista_scene)
        if compiled is None:
            # One bounded repair pass: the original timeline remains authoritative.
            log.registra("Director output has invalid timecodes; requesting one timeline-preserving repair.", "WARNING")
            repair_prompt = (
                "Repair this English video direction prompt. Return only the corrected prompt.\n"
                "Use exactly one nonempty action span per interval below, in the same order. "
                "Copy each bracketed timecode literally. Do not merge, split or change durations. "
                "Preserve the supplied actions, shot types, camera moves and audio. "
                "The original timeline overrides conflicting details in the draft.\n"
                "If a subject is supplied, begin with 'Subject and scene: ' and its faithful English translation, "
                "preserving names, trigger tokens, appearance and constraints.\n"
                f"AUTHORITATIVE SUBJECT:\n{soggetto}\nAUTHORITATIVE TIMELINE:\n{cronologia}\n{frame_block}{audio_section}\n"
                f"DRAFT TO REPAIR:\n{accumulato.strip()}"
            )
            yield gr.update(), gr.update(), dl["director_repairing_status"]
            repaired = ""
            for chunk in local_vlm.genera_prompt_video_timeline(repair_prompt, model_vid, timeout=120, preserve_content=True):
                _verifica_stop_regia()
                if _errore_vlm(chunk):
                    yield *precedenti, _stato_errore_vlm(chunk)
                    return
                if isinstance(chunk, VLMStatus):
                    yield gr.update(), gr.update(), str(chunk)
                    continue
                repaired = chunk
                yield gr.update(), gr.update(), dl["director_repairing_status"]
            _verifica_stop_regia()
            compiled = align_director_prompt(repaired.strip(), lista_scene)
        fallback = compiled is None
        if fallback:
            from utils.director_prompt import timeline_fallback_prompt
            compiled = timeline_fallback_prompt(lista_scene, "", frame_block, audio_descrizione)
            log.registra("Director fallback: prompt assembled from the original timeline; incompatible model timing discarded.", "WARNING")
        from utils.director_prompt import finalize_director_subject
        compiled = finalize_director_subject(compiled, soggetto, fallback)
        status = dl["director_compile_fallback"] if fallback else dl["director_compile_success"]
        yield compiled, gr.update() if is_t2v else prompt_img, status
    except InterruptedError:
        yield *precedenti, dl["msg_interruzione_idea"]
    except Exception as e:
        log.registra(f"Timeline generation error: {e}", "ERROR")
        yield *precedenti, dl["director_generation_error"].format(error=e)
    finally:
        comfyui_manager.generazione_attiva = False


def cronologia_regia_testo(lista_scene):
    testo_cronologia = ""
    tempo_corrente = 0.0
    for riga in lista_scene:
        try:
            durata_blocco = float(riga[0])
            tipo = str(riga[1])
            zoom = str(riga[2])
            mov = str(riga[3]) if riga[3] else ""
            audio = str(riga[4]) if len(riga) > 4 and riga[4] else ""
            
            tempo_fine = tempo_corrente + durata_blocco
            audio_text = f", Sound: '{audio}'" if audio else ""
            testo_cronologia += f"- [{tempo_corrente:.1f}s - {tempo_fine:.1f}s] Shot Type: '{tipo}', Movement: '{zoom}', Details: '{mov}'{audio_text}\n"
            tempo_corrente = tempo_fine
        except Exception:
            continue
    return testo_cronologia
