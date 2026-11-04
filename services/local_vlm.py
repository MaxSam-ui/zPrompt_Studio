from utils.prompt_templates import compose_system
from utils.vlm_status import VLMStatus
from utils.model_chat import format_model_chat
# services/local_vlm.py

import os
import re
from PIL import Image
from threading import Thread
from services.model_load_progress import load_with_progress
from core.model_cache import get_cache_dir

from core import log, config, sessione
from transformers import TextIteratorStreamer, StoppingCriteriaList

from services.vlm_loader import (
    _carica_modello_se_necessario,
    _normalizza_nome_modello,
    _ottieni_tokenizer,
    _ottieni_testi_vlm,
    _e_processore_multimodale,
    _prepara_input_sicuro,
    libera_memoria_vlm,
    ottieni_modelli_disponibili,
    warm_up_vlm,
    InterruptCriteria
)


def genera_prompt_immagine(immagine_pil, sistema_prompt, suggerimenti_utente, modello_selezionato, timeout=None, max_new_tokens=1024):
    from services import comfyui_manager
    # Only visual tasks requesting English: subject/dialogue tasks can retain
    # their own output language. Repeat the contract after the source material.
    if re.search(r'\bEnglish\b', sistema_prompt or '', re.I):
        from utils.prompt_language import english_visual_request
        sistema_prompt, suggerimenti_utente = english_visual_request(
            sistema_prompt, suggerimenti_utente or 'Describe the image.')
    
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    nome_reale = _normalizza_nome_modello(modello_selezionato)
    
    d = _ottieni_testi_vlm()
    
    import services.vlm_loader as loader
    if loader._modello_corrente is None or loader._nome_modello_caricato != nome_reale:
        yield VLMStatus(d.get("vlm_loading", "..."))
    else:
        yield VLMStatus(d.get("vlm_ready_analisi", "..."))
    
    try:
        model, processor = yield from load_with_progress(_carica_modello_se_necessario, nome_reale, get_cache_dir(), d)
        comfyui_manager.generazione_attiva = True
        comfyui_manager.vlm_interrotto = False
        
        device = next(model.parameters()).device
        
        yield VLMStatus(d.get("vlm_elaborazione", "..."))
        
        is_multimodale = _e_processore_multimodale(processor)
        if immagine_pil is not None and not is_multimodale:
            log.registra("⚠️ ATTENZIONE: Il modello selezionato è testuale puro e non supporta l'analisi d'immagine. L'immagine verrà ignorata.")
            
        messages = []
        if sistema_prompt and sistema_prompt.strip():
            if is_multimodale:
                messages.append({"role": "system", "content": [{"type": "text", "text": sistema_prompt.strip()}]})
            else:
                messages.append({"role": "system", "content": sistema_prompt.strip()})
            
        if is_multimodale:
            content = []
            if isinstance(immagine_pil, Image.Image):
                content.append({"type": "image", "image": immagine_pil})
            content.append({"type": "text", "text": suggerimenti_utente if suggerimenti_utente else "Descrivi l'immagine."})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": suggerimenti_utente if suggerimenti_utente else "Descrivi l'immagine."})
        
        try:
            testo_formattato = format_model_chat(processor, messages, nome_reale)
        except Exception as ex_template:
            log.registra(f"VLM: apply_chat_template non supportato ({ex_template}). Uso fallback testuale standard.", "WARNING")
            testo_formattato = ""
            if sistema_prompt:
                testo_formattato += f"System: {sistema_prompt.strip()}\n\n"
            
            desc_default = "Descrivi l'immagine."
            testo_formattato += f"User: {suggerimenti_utente if suggerimenti_utente else desc_default}\nAssistant: "
        
        inputs = _prepara_input_sicuro(processor, testo_formattato, immagine_pil, device)
        
        tokenizer_reale = _ottieni_tokenizer(processor)
        streamer = TextIteratorStreamer(tokenizer_reale, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=int(max_new_tokens),
            do_sample=True,
            temperature=0.75,
            repetition_penalty=1.15,
            stopping_criteria=StoppingCriteriaList([InterruptCriteria()])
        )
        
        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        
        accumulato = ""
        for new_text in streamer:
            if not comfyui_manager.generazione_attiva:
                break
            accumulato += new_text
            yield accumulato
            
    except Exception as e:
        log.registra(f"PyTorch inference error: {e}", "ERROR")
        yield f"Errore durante l'analisi locale: {str(e)}"
    finally:
        comfyui_manager.generazione_attiva = False
        if 'thread' in locals() and thread.is_alive():
            thread.join(timeout=3.0)


def affina_descrizione_immagine(descrizione_corrente, istruzioni_affinamento, sistema_prompt, modello_selezionato, immagine_pil=None, max_new_tokens=1536):
    from services import comfyui_manager
    
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True

    if not descrizione_corrente.strip():
        comfyui_manager.generazione_attiva = False
        yield "Nessuna descrizione precedente da raffinare. Esegui prima l'analisi."
        return

    nome_reale = _normalizza_nome_modello(modello_selezionato)
    log.registra(f"Native PyTorch refinement requested ({nome_reale})...")

    d = _ottieni_testi_vlm()
    
    import services.vlm_loader as loader
    if loader._modello_corrente is None or loader._nome_modello_caricato != nome_reale:
        yield VLMStatus(d.get("vlm_loading", "..."))
    else:
        yield VLMStatus(d.get("vlm_ready_affinamento", "..."))

    from utils.prompt_templates import system_template
    template_affina = system_template("Refine Prompt.txt")

    from utils.prompt_templates import render_template
    prompt_finale = render_template(template_affina,
        sistema_prompt=sistema_prompt or "Follow the requested output format.",
        descrizione_corrente=descrizione_corrente,
        istruzioni_affinamento=istruzioni_affinamento)

    from utils.prompt_language import english_visual_request
    sistema_prompt, prompt_finale = english_visual_request(sistema_prompt, prompt_finale)

    try:
        model, processor = yield from load_with_progress(_carica_modello_se_necessario, nome_reale, get_cache_dir(), d)
        comfyui_manager.generazione_attiva = True
        comfyui_manager.vlm_interrotto = False

        device = next(model.parameters()).device
        
        yield VLMStatus(d.get("vlm_affinamento", "..."))
        
        is_multimodale = _e_processore_multimodale(processor)
        if is_multimodale:
            messages = [
                {"role": "system", "content": [{"type": "text", "text": sistema_prompt}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_finale}
                    ]
                }
            ]
        else:
            messages = [
                {"role": "system", "content": sistema_prompt},
                {
                    "role": "user",
                    "content": prompt_finale
                }
            ]
        
        try:
            testo_formattato = format_model_chat(processor, messages, nome_reale)
        except Exception as ex_template:
            log.registra(f"VLM: apply_chat_template unsupported ({ex_template}). Using refinement fallback.", "WARNING")
            testo_formattato = f"System: {sistema_prompt if sistema_prompt else 'Sei un assistente utile.'}\n\nUser: {prompt_finale}\nAssistant: "
        
        inputs = _prepara_input_sicuro(processor, testo_formattato, immagine_pil, device)
        
        tokenizer_reale = _ottieni_tokenizer(processor)
        streamer = TextIteratorStreamer(tokenizer_reale, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=int(max_new_tokens),
            do_sample=True,
            temperature=0.75,
            repetition_penalty=1.15,
            stopping_criteria=StoppingCriteriaList([InterruptCriteria()])
        )
        
        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        
        accumulato = ""
        for new_text in streamer:
            if not comfyui_manager.generazione_attiva:
                break
            accumulato += new_text
            yield accumulato
            
    except Exception as e:
        log.registra(f"PyTorch refinement error: {e}", "ERROR")
        yield f"Errore durante l'affinamento locale: {str(e)}"
    finally:
        comfyui_manager.generazione_attiva = False
        if 'thread' in locals() and thread.is_alive():
            thread.join(timeout=3.0)


def genera_prompt_video_timeline(prompt_compilato, modello_selezionato, timeout=None, preserve_content=False):
    from services import comfyui_manager
    
    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True
    nome_reale = _normalizza_nome_modello(modello_selezionato)
    log.registra(f"Generazione timeline di regia nativa in corso ({nome_reale})...")
    
    d = _ottieni_testi_vlm()
    
    import services.vlm_loader as loader
    if loader._modello_corrente is None or loader._nome_modello_caricato != nome_reale:
        yield VLMStatus(d.get("vlm_loading", "..."))
    else:
        yield VLMStatus(d.get("vlm_ready_regia", "..."))
    
    try:
        model, processor = yield from load_with_progress(_carica_modello_se_necessario, nome_reale, get_cache_dir(), d)
        comfyui_manager.generazione_attiva = True
        comfyui_manager.vlm_interrotto = False

        device = next(model.parameters()).device
        
        yield VLMStatus(d.get("vlm_regia", "..."))
        
        is_multimodale = _e_processore_multimodale(processor)
        if is_multimodale:
            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt_compilato}]
                }
            ]
        else:
            messages = [
                {
                    "role": "user",
                    "content": prompt_compilato
                }
            ]
        
        try:
            testo_formattato = format_model_chat(processor, messages, nome_reale)
        except Exception as ex_template:
            log.registra(f"VLM: apply_chat_template non supportato ({ex_template}). Uso fallback per timeline.", "WARNING")
            testo_formattato = f"User: {prompt_compilato}\nAssistant: "
        
        inputs = _prepara_input_sicuro(processor, testo_formattato, None, device)
        
        tokenizer_reale = _ottieni_tokenizer(processor)
        streamer = TextIteratorStreamer(tokenizer_reale, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=1536, 
            do_sample=True,
            temperature=0.75,
            repetition_penalty=1.15,
            stopping_criteria=StoppingCriteriaList([InterruptCriteria()])
        )
        
        # Compilation translates/reformats an existing scene rather than inventing
        # one. Avoid sampling and repetition penalties that encourage synonyms
        # or new details instead of faithfully repeating supplied descriptions.
        if preserve_content:
            generation_kwargs.update(do_sample=False, repetition_penalty=1.0)
            generation_kwargs.pop('temperature', None)

        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        
        accumulato = ""
        for new_text in streamer:
            if not comfyui_manager.generazione_attiva:
                break
            accumulato += new_text
            yield accumulato
            
    except Exception as e:
        log.registra(f"PyTorch timeline error: {e}", "ERROR")
        yield f"Errore nella generazione locale della timeline: {str(e)}"
    finally:
        comfyui_manager.generazione_attiva = False
        if 'thread' in locals() and thread.is_alive():
            thread.join(timeout=3.0)


def estrai_asset_da_prompt(prompt_testo):
    """
    Scompone un prompt di analisi visiva in 3 blocchi HYPER-SINTETICI:
    1. CHARACTER (Personaggio)
    2. OUTFIT_LOCATION (Outfit & Ambiente)
    3. ACTION (Azione)
    utilizzando il modello VLM di sessione direttamente dalla casella di testo.
    """
    from services import comfyui_manager
    d = _ottieni_testi_vlm()

    testo_valido = (prompt_testo or "").strip()
    if not testo_valido:
        yield "", "", "", d.get("msg_prompt_vuoto", "⚠️ Inserisci o genera prima un prompt nella casella di testo da cui estrarre gli asset.")
        return

    comfyui_manager.vlm_interrotto = False
    comfyui_manager.generazione_attiva = True

    s_attiva = sessione.carica_ultima_sessione()
    modello_vlm = s_attiva.get("modello_vlm") or "huihui_ai/qwen3-vl-abliterated:4b"
    nome_reale = _normalizza_nome_modello(modello_vlm)

    sys_prompt = (
        compose_system('Extract_Catalog.txt')
    )

    istruzione_utente = f"Visual description to analyze: '{testo_valido}'"

    yield "", "", "", d.get("msg_estrazione_in_corso", "🧠 Estrazione asset con AI in corso...")

    accumulato = ""
    try:
        for chunk in genera_prompt_immagine(None, sys_prompt, istruzione_utente, nome_reale, max_new_tokens=512):
            if getattr(comfyui_manager, "vlm_interrotto", False):
                break
            if str(chunk).lstrip().startswith(("❌", "Errore", "Error", "⚠", "⏹", "🛑")):
                comfyui_manager.generazione_attiva = False
                yield "", "", "", "❌ " + str(chunk).lstrip("❌ ")
                return
            if chunk and not isinstance(chunk, VLMStatus):
                accumulato = chunk
                yield "", "", "", d.get("msg_scomposizione_in_corso", "🧠 Separazione asset in corso...")
    except Exception as e:
        log.registra(f"VLM asset extraction error: {e}", "ERROR")
        yield "", "", "", f"❌ Error: {str(e)}"
        comfyui_manager.generazione_attiva = False
        return

    comfyui_manager.generazione_attiva = False
    if comfyui_manager.vlm_interrotto:
        yield "", "", "", d.get("batch_status_interrupted", "⏹️ Interrupted.")
        return
    if not all(re.search(r'^' + key + r':', accumulato, re.I | re.M) for key in ("CHARACTER", "OUTFIT_LOCATION", "ACTION")):
        yield "", "", "", d.get("analysis_empty_result", "❌ No valid result.")
        return
    char_desc, outfit_desc, act_desc = "", "", ""
    if accumulato:
        m_c = re.search(r'^CHARACTER:[ \t]*([^\n]*)', accumulato, re.IGNORECASE | re.MULTILINE)
        m_o = re.search(r'^OUTFIT_LOCATION:[ \t]*([^\n]*)', accumulato, re.IGNORECASE | re.MULTILINE)
        m_a = re.search(r'^ACTION:[ \t]*([^\n]*)', accumulato, re.IGNORECASE | re.MULTILINE)

        if m_c: char_desc = m_c.group(1).strip()
        if m_o: outfit_desc = m_o.group(1).strip()
        if m_a: act_desc = m_a.group(1).strip()

    msg_done = d.get("msg_asset_estratti", "✅ Asset estratti con successo! Puoi salvarli nel catalogo.")
    yield char_desc, outfit_desc, act_desc, msg_done
