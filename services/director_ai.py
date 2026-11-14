from utils.prompt_templates import compose_system
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
            default_vlm = s_attiva.get("modello_vlm", "huihui_ai/qwen3-vl-abliterated:4b")
            m_vlm = model_vision if (model_vision and model_vision.strip()) else default_vlm
            sys_p = sys_prompt_vision if (sys_prompt_vision and sys_prompt_vision.strip()) else compose_system("Frame_Analysis.txt")
            
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
                compose_system('Timeline_First_Last_Context.txt', prompt_img=prompt_img, desc_last_frame=desc_last_frame)
            )
        elif not is_t2v and prompt_img and prompt_img.strip():
            frame_context = (
                compose_system('Timeline_First_Context.txt', prompt_img=prompt_img)
            )
        else:
            frame_context = ""

        from utils.prompt_templates import scene_contract, render_template, system_template
        template_sceneggiatore = render_template(system_template("Screenwriter.txt"),
            durata=dur_f, video_num_clips=video_num_clips, idea_utente=idea_utente,
            frame_context=frame_context, prompt_img=prompt_img,
            intervalli_formattati=intervalli_formattati, primo_intervallo=intervalli[0],
            lista_inquadrature=lista_inquadrature, lista_zoom=lista_zoom_str) + "\n\n" + scene_contract()

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
                    compose_system('Subject_From_Frame.txt', desc_start=desc_start, dest_context=dest_context)
                )
            else:
                msg_avvio = dl.get("msg_improving_subject", "🪄 AI Writer: Enhancing subject with visual frame...")
                yield gr.update(), msg_avvio
                prompt = (
                    compose_system('Subject_Refine_Frame.txt', desc_start=desc_start, dest_context=dest_context, testo_utente=testo_utente)
                )
        else:
            msg_avvio = dl.get("msg_creating_subject", "🪄 AI Writer: Writing cinematic subject...")
            yield gr.update(), msg_avvio
            prompt = (
                compose_system('Subject_From_Text.txt', idea=testo_utente)
            )

        from utils.prompt_templates import scene_contract
        prompt += "\n\n" + scene_contract()
        accumulato = ""
        for chunk in local_vlm.genera_prompt_video_timeline(prompt, modello, timeout=60, preserve_content=True):
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
        from utils.video_constraints import preserve_video_constraints
        accumulato = preserve_video_constraints(accumulato, soggetto_corrente)
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
        compose_system('Timeline_Dialogue.txt', soggetto=soggetto or '', testo_timeline=testo_timeline)
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

        from utils.video_model_prompt import selected_video_frames
        filepath_start, filepath_dest, filepath_middle = selected_video_frames(stato_gen, s_attiva, is_t2v)
        storyboard_frames = (stato_gen or {}).get('lista_frame_storyboard_attivi', [])
        if (not is_t2v and not (stato_gen or {}).get('is_extension', False)
                and 'storyboard' in str(s_attiva.get('generation_mode', '')).lower()
                and len(storyboard_frames) >= 2):
            # The active storyboard drives the workflow, not an older gallery selection.
            prompt_img = ""
        if is_t2v:
            prompt_img = ""
        elif not prompt_img or not prompt_img.strip():
            if filepath_start and os.path.exists(filepath_start):
                yield gr.update(), gr.update(), dl["director_analyzing_start"]
                prompt_img = _estrai_descrizione_frame_sicura(filepath_start, stato_gen, sys_prompt_vision, model_vision)
            if not prompt_img or not prompt_img.strip():
                prompt_img = "A high quality cinematic opening scene."

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
                compose_system('Default_Director_Style.txt')
            )

        if not is_t2v and has_last_frame and desc_last_frame:
            frame_block = (
                compose_system('Video_First_Last_Context.txt', prompt_img=prompt_img, desc_last_frame=desc_last_frame)
            )
        elif not is_t2v and prompt_img and prompt_img.strip():
            frame_block = (
                compose_system('Video_First_Context.txt', prompt_img=prompt_img)
            )
        else:
            frame_block = ""

        if filepath_middle:
            if not os.path.exists(filepath_middle):
                raise ValueError("Intermediate storyboard frame not found.")
            yield gr.update(), gr.update(), dl["director_analyzing_start"]
            middle_description = _estrai_descrizione_frame_sicura(filepath_middle, stato_gen, sys_prompt_vision, model_vision)
            frame_block += "\n" + compose_system('Video_Middle_Context.txt', description=middle_description)

        if s_attiva.get("modello_video_attivo") == "MiniMax H3":
            from utils.video_model_prompt import minimax_compiler_instruction, minimax_sections, minimax_format, MINIMAX_SECTIONS, MINIMAX_BASE_SECTIONS
            from utils.director_prompt import align_director_prompt, preserve_identity_tokens
            from utils.video_preflight import validate_video_request
            from core import workflow_registry
            from core.workflow_profiles import load_minimax_profile
            import json
            workflow_path = workflow_registry.risolvi_percorso_json_video("MiniMax H3")
            with open(workflow_path, encoding='utf-8-sig') as handle:
                profile = load_minimax_profile(workflow_path, json.load(handle))
            prompt_format = minimax_format(profile)
            section_names = MINIMAX_BASE_SECTIONS if prompt_format == 'base' else MINIMAX_SECTIONS
            body_key = 'integrated_multimodal_description' if prompt_format == 'base' else 'detailed_description'
            references = 0 if is_t2v else int(bool(filepath_start)) + int(has_last_frame) + int(bool(filepath_middle))
            source = (f"AUTHORITATIVE SUBJECT:\n{soggetto}\n{frame_block}\n"
                      f"AUTHORITATIVE TIMELINE:\n{cronologia}{audio_section}")
            instruction = minimax_compiler_instruction(source, references, direct=True, format=prompt_format)
            instruction += ('\n\n' + compose_system('Video_Director_Style.txt', stile_regole_testo=stile_regole_testo))
            phase = dl["director_compiling_status"]
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
                yield structured, prompt_img if prompt_img else gr.update(), phase
            _verifica_stop_regia()
            yield gr.update(), gr.update(), dl["director_validating_status"]
            parts = minimax_sections(structured.strip(), format=prompt_format)
            if not parts:
                raise ValueError("MiniMax prompt: missing, empty or duplicated sections; previous prompt preserved.")
            aligned = align_director_prompt(parts[body_key], lista_scene)
            fallback = aligned is None
            if fallback:
                from utils.director_prompt import timeline_fallback_prompt
                # Do not guess which generated sentence belongs to which clip.
                # Recover the actual actions/camera/audio from the user's timeline.
                aligned = timeline_fallback_prompt(lista_scene, soggetto, frame_block, audio_descrizione)
                log.registra("MiniMax: model clip boundaries invalid; using original timeline without another LLM call.", "WARNING")
            from utils.video_constraints import preserve_video_constraints
            parts[body_key] = preserve_video_constraints(aligned, soggetto, audio_descrizione)
            candidate = '\n\n'.join(f'{key}:\n{parts[key]}' for key in section_names)
            error = validate_video_request(candidate, sum(float(scene[0]) for scene in lista_scene))
            if error:
                raise ValueError(error)
            if preserve_identity_tokens(candidate, source) != candidate:
                raise ValueError("MiniMax prompt: missing identity references; previous prompt preserved.")
            status = dl["director_compile_fallback"] if fallback else dl["director_compile_success"]
            yield candidate, gr.update() if is_t2v else prompt_img, status
            return

        from utils.prompt_templates import scene_contract, render_template, system_template
        template_master = render_template(system_template("Master_Director_Template.txt"),
            frame_context=frame_block, prompt_img=prompt_img, cronologia=cronologia,
            audio_section=audio_section, regole_estetiche_regista=stile_regole_testo) + "\n\n" + scene_contract()

        if soggetto:
            template_master += ('\n\n' + compose_system('Video_Subject_Context.txt', soggetto=soggetto))
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
                compose_system('Video_Timeline_Repair.txt', soggetto=soggetto, cronologia=cronologia, frame_block=frame_block, audio_section=audio_section, draft=accumulato.strip())
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
        from utils.video_constraints import preserve_video_constraints
        compiled = preserve_video_constraints(compiled, soggetto, audio_descrizione)
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
