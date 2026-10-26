# events/eventi_sessione.py

import os
import time
import gradio as gr

from core import config, sessione, lingua, log, workflow_registry
from services import local_vlm

def salva_sys_prompt_dinamico(testo, solo_testo_flag):
    """Keep custom UI prompts in the session, never overwrite factory templates."""
    sessione.salva_sessione({"sys_prompt": testo})


_cache_elenchi = {}
CACHE_EXPIRATION_SECONDS = 10.0  

def _ottieni_da_cache_o_disco(chiave, generator_func):
    now = time.time()
    if chiave in _cache_elenchi:
        data_cache, timestamp = _cache_elenchi[chiave]
        if now - timestamp < CACHE_EXPIRATION_SECONDS:
            return data_cache
    
    nuovi_dati = generator_func()
    _cache_elenchi[chiave] = (nuovi_dati, now)
    return nuovi_dati


def sincronizza_prompt_edit_dinamico(testo, mode):
    """Synchronizes user changes in hidden field only if in Edit mode."""
    mode_str = str(mode).lower()
    if "edit" in mode_str or "modifica" in mode_str:
        return testo
    return gr.update()


def _salva_comp(comp, key_or_fn, inputs=None, outputs=None):
    """Helper difensivo: collega .release() se il componente è uno Slider, oppure .change() se è State/altro."""
    if comp is None:
        return
    
    if callable(key_or_fn):
        fn = key_or_fn
    else:
        fn = lambda v, k=key_or_fn: sessione.salva_sessione({k: v})
        
    if inputs is None:
        inputs = [comp]
        
    if hasattr(comp, "release"):
        comp.release(fn=fn, inputs=inputs, outputs=outputs)
    elif hasattr(comp, "change"):
        comp.change(fn=fn, inputs=inputs, outputs=outputs)


def collega_funzioni_sessione(t1, t2, t3, t4, t5, num_lora_img, num_lora_vid, d):
    def rinfresca_lora_immagine():
        def scan():
            s_attiva = sessione.carica_ultima_sessione()
            modello = s_attiva.get("modello_immagine_attivo", "Z-Image Turbo")
            if modello == "Qwen Image 2.1":
                return workflow_registry.ottieni_lora_disponibili_immagine(modello)
            if modello == "Flux.2 Klein":
                choices = ["-"] + config.elenca_lora(config.ottieni_lora_flux2_dir())
            elif modello == "Krea-2 Turbo":
                choices = ["-"] + config.elenca_lora(config.ottieni_lora_krea2_dir())
            else:
                choices = ["-"] + config.elenca_lora(config.ottieni_lora_zimage_dirs())
            return choices
            
        s_attiva = sessione.carica_ultima_sessione()
        modello = s_attiva.get("modello_immagine_attivo", "Z-Image Turbo")
        return gr.update(choices=_ottieni_da_cache_o_disco(f"lora_img_{modello}", scan))

    def rinfresca_lora_immagine_batch():
        def scan():
            s_attiva = sessione.carica_ultima_sessione()
            modello = s_attiva.get("modello_immagine_attivo_batch", "Z-Image Turbo")
            if modello == "Flux.2 Klein":
                choices = ["-"] + config.elenca_lora(config.ottieni_lora_flux2_dir())
            elif modello == "Krea-2 Turbo":
                choices = ["-"] + config.elenca_lora(config.ottieni_lora_krea2_dir())
            else:
                choices = ["-"] + config.elenca_lora(config.ottieni_lora_zimage_dirs())
            return choices
            
        s_attiva = sessione.carica_ultima_sessione()
        modello = s_attiva.get("modello_immagine_attivo_batch", "Z-Image Turbo")
        return gr.update(choices=_ottieni_da_cache_o_disco(f"lora_batch_{modello}", scan))

    def rinfresca_lora_video():
        s_attiva = sessione.carica_ultima_sessione()
        modello_vid = s_attiva.get("modello_video_attivo", "LTX-Video 2.5")
        def scan():
            return workflow_registry.ottieni_lora_disponibili_video(modello_vid)
        return gr.update(choices=_ottieni_da_cache_o_disco(f"lora_video_{modello_vid}", scan))

    def rinfresca_modelli_vlm():
        def scan():
            nuovi = local_vlm.ottieni_modelli_disponibili()
            return nuovi if nuovi else ["-"]
        return gr.update(choices=_ottieni_da_cache_o_disco("modelli_vlm", scan))

    def rinfresca_suggerimenti_vision():
        def scan():
            s_list = config.elenca_suggerimenti(config.SUGGESTION_VISION_DIR)
            return ["-"] + (list(s_list) if s_list else [])
        return gr.update(choices=_ottieni_da_cache_o_disco("sugg_vision", scan))

    def rinfresca_suggerimenti_batch():
        def scan():
            s_list = config.elenca_suggerimenti(config.SUGGESTION_VISION_DIR)
            return ["-"] + (list(s_list) if s_list else [])
        return gr.update(choices=_ottieni_da_cache_o_disco("sugg_batch", scan))

    def rinfresca_suggerimenti_sceneggiatura():
        def scan():
            s_list = config.elenca_suggerimenti(config.SUGGESTION_SCREENPLAY_DIR)
            return ["-"] + (list(s_list) if s_list else [])
        return gr.update(choices=_ottieni_da_cache_o_disco("sugg_screenplay", scan))

    def rinfresca_suggerimenti_regia():
        def scan():
            s_list = config.elenca_suggerimenti(config.SUGGESTION_DIRECTION_DIR)
            return ["-"] + (list(s_list) if s_list else [])
        return gr.update(choices=_ottieni_da_cache_o_disco("sugg_regia", scan))

    def rinfresca_suggerimenti_storyboard():
        def scan():
            s_list = config.elenca_suggerimenti(config.SUGGESTION_STORYBOARD_DIR)
            return ["-"] + (list(s_list) if s_list else [])
        return gr.update(choices=_ottieni_da_cache_o_disco("sugg_storyboard", scan))

    # FOCUS AUTO-REFRESH SUI COMPONENTI
    if "lora1_name" in t2: t2["lora1_name"].focus(fn=rinfresca_lora_immagine, inputs=None, outputs=t2["lora1_name"])
    if "lora2_name" in t2: t2["lora2_name"].focus(fn=rinfresca_lora_immagine, inputs=None, outputs=t2["lora2_name"])
    if "lora3_name" in t2: t2["lora3_name"].focus(fn=rinfresca_lora_immagine, inputs=None, outputs=t2["lora3_name"])

    if "lora_vid1_name" in t3: t3["lora_vid1_name"].focus(fn=rinfresca_lora_video, inputs=None, outputs=t3["lora_vid1_name"])
    if "lora_vid2_name" in t3: t3["lora_vid2_name"].focus(fn=rinfresca_lora_video, inputs=None, outputs=t3["lora_vid2_name"])
    if "lora_vid3_name" in t3: t3["lora_vid3_name"].focus(fn=rinfresca_lora_video, inputs=None, outputs=t3["lora_vid3_name"])

    if "lora1_name" in t4: t4["lora1_name"].focus(fn=rinfresca_lora_immagine_batch, inputs=None, outputs=t4["lora1_name"])
    if "lora2_name" in t4: t4["lora2_name"].focus(fn=rinfresca_lora_immagine_batch, inputs=None, outputs=t4["lora2_name"])
    if "lora3_name" in t4: t4["lora3_name"].focus(fn=rinfresca_lora_immagine_batch, inputs=None, outputs=t4["lora3_name"])
    if "dropdown_model_batch" in t4: t4["dropdown_model_batch"].focus(fn=rinfresca_modelli_vlm, inputs=None, outputs=t4["dropdown_model_batch"])

    if "dropdown_sugg_vision" in t1: t1["dropdown_sugg_vision"].focus(fn=rinfresca_suggerimenti_vision, inputs=None, outputs=t1["dropdown_sugg_vision"])
    if "dropdown_sugg_batch" in t4: t4["dropdown_sugg_batch"].focus(fn=rinfresca_suggerimenti_batch, inputs=None, outputs=t4["dropdown_sugg_batch"])

    if "dropdown_sugg_screenplay" in t3: t3["dropdown_sugg_screenplay"].focus(fn=rinfresca_suggerimenti_sceneggiatura, inputs=None, outputs=t3["dropdown_sugg_screenplay"])
    if "dropdown_sugg_director" in t3: t3["dropdown_sugg_director"].focus(fn=rinfresca_suggerimenti_regia, inputs=None, outputs=t3["dropdown_sugg_director"])

    if "dropdown_model" in t1: t1["dropdown_model"].focus(fn=rinfresca_modelli_vlm, inputs=None, outputs=t1["dropdown_model"])
    if "dropdown_model_video" in t3: t3["dropdown_model_video"].focus(fn=rinfresca_modelli_vlm, inputs=None, outputs=t3["dropdown_model_video"])

    if "dropdown_sugg_storyboard" in t2: t2["dropdown_sugg_storyboard"].focus(fn=rinfresca_suggerimenti_storyboard, inputs=None, outputs=t2["dropdown_sugg_storyboard"])

    # TAB 1: ANALISI SESSION PERSISTENCE
    if "dropdown_model" in t1: t1["dropdown_model"].change(lambda v: sessione.salva_sessione({"modello_vlm": v}), inputs=[t1["dropdown_model"]])
    if "dropdown_sugg_vision" in t1: t1["dropdown_sugg_vision"].change(lambda v: sessione.salva_sessione({"suggerimento_vision_selezionato": v}), inputs=[t1["dropdown_sugg_vision"]])
    
    if "sys_prompt" in t1:
        t1["sys_prompt"].blur(
            fn=salva_sys_prompt_dinamico,
            inputs=[t1["sys_prompt"], t1["solo_testo_checkbox"]],
            outputs=None
        )
    if "user_hints" in t1: t1["user_hints"].blur(lambda v: sessione.salva_sessione({"user_hints": v}), inputs=[t1["user_hints"]])

    # TAB 2: RENDERING SESSION PERSISTENCE
    def salva_lora1_dinamico(nome, forza, modello):
        if modello == "Qwen Image 2.1":
            sessione.salva_sessione({"lora1_name_qwen21_edit": nome, "lora1_str_qwen21_edit": forza})
            return
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"lora1_name_flux2": nome, "lora1_str_flux2": forza, "lora1_name": nome, "lora1_str": forza})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"lora1_name_krea2": nome, "lora1_str_krea2": forza, "lora1_name": nome, "lora1_str": forza})
        else:
            sessione.salva_sessione({"lora1_name_zimage": nome, "lora1_str_zimage": forza, "lora1_name": nome, "lora1_str": forza})

    def salva_lora2_dinamico(nome, forza, modello):
        if modello == "Qwen Image 2.1":
            sessione.salva_sessione({"lora2_name_qwen21_edit": nome, "lora2_str_qwen21_edit": forza})
            return
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"lora2_name_flux2": nome, "lora2_str_flux2": forza, "lora2_name": nome, "lora2_str": forza})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"lora2_name_krea2": nome, "lora2_str_krea2": forza, "lora2_name": nome, "lora2_str": forza})
        else:
            sessione.salva_sessione({"lora2_name_zimage": nome, "lora2_str_zimage": forza, "lora2_name": nome, "lora2_str": forza})

    def salva_lora3_dinamico(nome, forza, modello):
        if modello == "Qwen Image 2.1":
            sessione.salva_sessione({"lora3_name_qwen21_edit": nome, "lora3_str_qwen21_edit": forza})
            return
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"lora3_name_flux2": nome, "lora3_str_flux2": forza, "lora3_name": nome, "lora3_str": forza})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"lora3_name_krea2": nome, "lora3_str_krea2": forza, "lora3_name": nome, "lora3_str": forza})
        else:
            sessione.salva_sessione({"lora3_name_zimage": nome, "lora3_str_zimage": forza, "lora3_name": nome, "lora3_str": forza})

    def salva_steps_dinamico(steps, modello, mode):
        mode_str = str(mode).lower()
        if "edit" in mode_str or "modifica" in mode_str:
            sessione.salva_sessione({("steps_qwen21_edit" if modello == "Qwen Image 2.1" else "steps_krea2_edit"): steps})
        elif modello == "Flux.2 Klein":
            sessione.salva_sessione({"steps_flux2": steps, "steps": steps})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"steps_krea2": steps, "steps": steps})
        else:
            sessione.salva_sessione({"steps_zimage": steps, "steps": steps})

    def salva_sampler_dinamico(sampler, modello, mode):
        mode_str = str(mode).lower()
        if "edit" in mode_str or "modifica" in mode_str:
            sessione.salva_sessione({("sampler_qwen21_edit" if modello == "Qwen Image 2.1" else "sampler_krea2_edit"): sampler})
        elif modello == "Flux.2 Klein":
            sessione.salva_sessione({"sampler_flux2": sampler, "sampler_name": sampler})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"sampler_krea2": sampler, "sampler_name": sampler})
        else:
            sessione.salva_sessione({"sampler_zimage": sampler, "sampler_name": sampler})

    def salva_scheduler_dinamico(scheduler, modello, mode):
        mode_str = str(mode).lower()
        if "edit" in mode_str or "modifica" in mode_str:
            sessione.salva_sessione({("scheduler_qwen21_edit" if modello == "Qwen Image 2.1" else "scheduler_krea2_edit"): scheduler})
        elif modello == "Flux.2 Klein":
            sessione.salva_sessione({"scheduler_flux2": scheduler, "scheduler": scheduler})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"scheduler_krea2": scheduler, "scheduler": scheduler})
        else:
            sessione.salva_sessione({"scheduler_zimage": scheduler, "scheduler": scheduler})

    def salva_istruzioni_dinamico(testo, mode):
        mode_str = str(mode).lower()
        if "edit" in mode_str or "modifica" in mode_str:
            sessione.salva_sessione({"krea2_edit_instruction": testo})
        else:
            sessione.salva_sessione({"refine_instructions": testo})

    if "lora1_name" in t2 and "lora1_str" in t2:
        t2["lora1_name"].change(fn=salva_lora1_dinamico, inputs=[t2["lora1_name"], t2["lora1_str"], t2["dropdown_image_model"]])
        _salva_comp(t2["lora1_str"], salva_lora1_dinamico, inputs=[t2["lora1_name"], t2["lora1_str"], t2["dropdown_image_model"]])

    if "lora2_name" in t2 and "lora2_str" in t2:
        t2["lora2_name"].change(fn=salva_lora2_dinamico, inputs=[t2["lora2_name"], t2["lora2_str"], t2["dropdown_image_model"]])
        _salva_comp(t2["lora2_str"], salva_lora2_dinamico, inputs=[t2["lora2_name"], t2["lora2_str"], t2["dropdown_image_model"]])

    if "lora3_name" in t2 and "lora3_str" in t2:
        t2["lora3_name"].change(fn=salva_lora3_dinamico, inputs=[t2["lora3_name"], t2["lora3_str"], t2["dropdown_image_model"]])
        _salva_comp(t2["lora3_str"], salva_lora3_dinamico, inputs=[t2["lora3_name"], t2["lora3_str"], t2["dropdown_image_model"]])

    if "steps_slider" in t2:
        _salva_comp(t2["steps_slider"], salva_steps_dinamico, inputs=[t2["steps_slider"], t2["dropdown_image_model"], t2["generation_mode"]])
    if "sampler_dropdown" in t2:
        t2["sampler_dropdown"].change(fn=salva_sampler_dinamico, inputs=[t2["sampler_dropdown"], t2["dropdown_image_model"], t2["generation_mode"]])
    if "scheduler_dropdown" in t2:
        t2["scheduler_dropdown"].change(fn=salva_scheduler_dinamico, inputs=[t2["scheduler_dropdown"], t2["dropdown_image_model"], t2["generation_mode"]])
    
    if "hires_steps_slider" in t2: _salva_comp(t2["hires_steps_slider"], "hires_steps")
    if "hires_denoise_slider" in t2: _salva_comp(t2["hires_denoise_slider"], "hires_denoise")
    if "hires_scale_slider" in t2: _salva_comp(t2["hires_scale_slider"], "hires_scale")

    if "img_width" in t2: t2["img_width"].change(lambda v: sessione.salva_sessione({"img_width": v}), inputs=[t2["img_width"]])
    if "img_height" in t2: t2["img_height"].change(lambda v: sessione.salva_sessione({"img_height": v}), inputs=[t2["img_height"]])
    if "img_copies" in t2: _salva_comp(t2["img_copies"], "img_copies")
    
    if "prompt_to_send_img" in t2: t2["prompt_to_send_img"].blur(lambda v: sessione.salva_sessione({"prompt_to_send_img": v}), inputs=[t2["prompt_to_send_img"]])

    if "img_seed_mode" in t2: t2["img_seed_mode"].change(lambda v: sessione.salva_sessione({"img_seed_mode": v}), inputs=[t2["img_seed_mode"]])
    if "img_seed" in t2: t2["img_seed"].blur(lambda v: sessione.salva_sessione({"img_seed": v}), inputs=[t2["img_seed"]])
    
    if "refine_instructions" in t2:
        t2["refine_instructions"].blur(fn=salva_istruzioni_dinamico, inputs=[t2["refine_instructions"], t2["generation_mode"]])
        t2["refine_instructions"].blur(fn=sincronizza_prompt_edit_dinamico, inputs=[t2["refine_instructions"], t2["generation_mode"]], outputs=[t2["prompt_to_send_img"]])

    # SALVATAGGIO SEQUENZA AI & CATALOGO IN SESSIONE
    if "dropdown_sugg_sequenza" in t2:
        t2["dropdown_sugg_sequenza"].change(lambda v: sessione.salva_sessione({"suggerimento_sequenza_selezionato": v}), inputs=[t2["dropdown_sugg_sequenza"]])
    if "selettore_sequenza_scatti" in t2:
        _salva_comp(t2["selettore_sequenza_scatti"], "sequenza_num_scatti")

    if "dd_outfit_location" in t2:
        t2["dd_outfit_location"].change(lambda v: sessione.salva_sessione({"dd_outfit_location": v}), inputs=[t2["dd_outfit_location"]])

    for i in range(1, 6):
        key_s = f"dd_soggetto_{i}"
        key_a = f"dd_azione_{i}"
        if key_s in t2:
            t2[key_s].change(lambda v, k=key_s: sessione.salva_sessione({k: v}), inputs=[t2[key_s]])
        if key_a in t2:
            t2[key_a].change(lambda v, k=key_a: sessione.salva_sessione({k: v}), inputs=[t2[key_a]])

    if "dropdown_sugg_storyboard" in t2:
        t2["dropdown_sugg_storyboard"].change(lambda v: sessione.salva_sessione({"suggerimento_storyboard_selezionato": v}), inputs=[t2["dropdown_sugg_storyboard"]])
    if "selettore_storyboard_pannelli" in t2: _salva_comp(t2["selettore_storyboard_pannelli"], "storyboard_pannelli")
    if "attiva_refine_storyboard" in t2: t2["attiva_refine_storyboard"].change(lambda v: sessione.salva_sessione({"attiva_refine_storyboard": v}), inputs=[t2["attiva_refine_storyboard"]])
    if "refine_denoise" in t2: _salva_comp(t2["refine_denoise"], "refine_denoise")
    
    # SALVATAGGIO PARAMETRI EDIT (KREA-2 EDIT)
    if "krea2_edit_grounding_px" in t2: _salva_comp(t2["krea2_edit_grounding_px"], "krea2_edit_grounding_px")
    if "krea2_edit_height" in t2: t2["krea2_edit_height"].change(lambda v: sessione.salva_sessione({"krea2_edit_height": v}), inputs=[t2["krea2_edit_height"]])
    if "krea2_edit_lora_strength" in t2: _salva_comp(t2["krea2_edit_lora_strength"], "krea2_edit_lora_strength")

    # TAB 3: VIDEO SESSION PERSISTENCE (Parametri format & Minimax)
    if "video_fps" in t3: t3["video_fps"].change(lambda v: sessione.salva_sessione({"video_fps": v}), inputs=[t3["video_fps"]])
    if "video_durata_totale" in t3: _salva_comp(t3["video_durata_totale"], "video_durata_totale")
    if "video_rapporto" in t3: t3["video_rapporto"].change(lambda v: sessione.salva_sessione({"video_rapporto": v}), inputs=[t3["video_rapporto"]])
    if "video_risoluzione" in t3: t3["video_risoluzione"].change(lambda v: sessione.salva_sessione({"video_risoluzione": v}), inputs=[t3["video_risoluzione"]])

    if "video_steps_vid" in t3: _salva_comp(t3["video_steps_vid"], "video_steps_minimax")
    if "video_denoise_vid" in t3: _salva_comp(t3["video_denoise_vid"], "video_denoise_minimax")
    if "video_scheduler_vid" in t3: t3["video_scheduler_vid"].change(lambda v: sessione.salva_sessione({"video_scheduler_minimax": v}), inputs=[t3["video_scheduler_vid"]])

    num_lora_img.change(lambda v: sessione.salva_sessione({"lora_visibili_count": v}), inputs=[num_lora_img])
    num_lora_vid.change(lambda v: sessione.salva_sessione({"lora_video_visibili_count": v}), inputs=[num_lora_vid])

    if "solo_testo_video" in t3: t3["solo_testo_video"].change(lambda v: sessione.salva_sessione({"solo_testo_video_attivo": v}), inputs=[t3["solo_testo_video"]])

    # TAB 4: BATCH SESSION PERSISTENCE
    def salva_lora1_dinamico_batch(nome, forza, modello):
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"lora1_name_flux2_batch": nome, "lora1_str_flux2_batch": forza, "lora_batch1_name": nome, "lora_batch1_str": forza})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"lora1_name_krea2_batch": nome, "lora1_str_krea2_batch": forza, "lora_batch1_name": nome, "lora_batch1_str": forza})
        else:
            sessione.salva_sessione({"lora1_name_zimage_batch": nome, "lora1_str_zimage_batch": forza, "lora_batch1_name": nome, "lora_batch1_str": forza})

    def salva_lora2_dinamico_batch(nome, forza, modello):
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"lora2_name_flux2_batch": nome, "lora2_str_flux2_batch": forza, "lora_batch2_name": nome, "lora_batch2_str": forza})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"lora2_name_krea2_batch": nome, "lora2_str_krea2_batch": forza, "lora_batch2_name": nome, "lora_batch2_str": forza})
        else:
            sessione.salva_sessione({"lora2_name_zimage_batch": nome, "lora2_str_zimage_batch": forza, "lora_batch2_name": nome, "lora_batch2_str": forza})

    def salva_lora3_dinamico_batch(nome, forza, modello):
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"lora3_name_flux2_batch": nome, "lora3_str_flux2_batch": forza, "lora_batch3_name": nome, "lora_batch3_str": forza})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"lora3_name_krea2_batch": nome, "lora3_str_krea2_batch": forza, "lora_batch3_name": nome, "lora_batch3_str": forza})
        else:
            sessione.salva_sessione({"lora3_name_zimage_batch": nome, "lora3_str_zimage_batch": forza, "lora_batch3_name": nome, "lora_batch3_str": forza})

    if "lora1_name" in t4 and "lora1_str" in t4:
        t4["lora1_name"].change(fn=salva_lora1_dinamico_batch, inputs=[t4["lora1_name"], t4["lora1_str"], t4["dropdown_image_model_batch"]])
        _salva_comp(t4["lora1_str"], salva_lora1_dinamico_batch, inputs=[t4["lora1_name"], t4["lora1_str"], t4["dropdown_image_model_batch"]])

    if "lora2_name" in t4 and "lora2_str" in t4:
        t4["lora2_name"].change(fn=salva_lora2_dinamico_batch, inputs=[t4["lora2_name"], t4["lora2_str"], t4["dropdown_image_model_batch"]])
        _salva_comp(t4["lora2_str"], salva_lora2_dinamico_batch, inputs=[t4["lora2_name"], t4["lora2_str"], t4["dropdown_image_model_batch"]])

    if "lora3_name" in t4 and "lora3_str" in t4:
        t4["lora3_name"].change(fn=salva_lora3_dinamico_batch, inputs=[t4["lora3_name"], t4["lora3_str"], t4["dropdown_image_model_batch"]])
        _salva_comp(t4["lora3_str"], salva_lora3_dinamico_batch, inputs=[t4["lora3_name"], t4["lora3_str"], t4["dropdown_image_model_batch"]])

    def salva_steps_dinamico_batch(steps, modello):
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"steps_flux2_batch": steps, "steps_batch": steps})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"steps_krea2_batch": steps, "steps_batch": steps})
        else:
            sessione.salva_sessione({"steps_zimage_batch": steps, "steps_batch": steps})

    def salva_sampler_dinamico_batch(sampler, modello):
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"sampler_flux2_batch": sampler, "sampler_batch": sampler})
        elif modello == "Krea-2 Turbo":
            sessione.salva_sessione({"sampler_krea2_batch": sampler, "sampler_batch": sampler})
        else:
            sessione.salva_sessione({"sampler_zimage_batch": sampler, "sampler_batch": sampler})

    def salva_scheduler_dinamico_batch(scheduler, modello):
        if modello == "Flux.2 Klein":
            sessione.salva_sessione({"scheduler_flux2_batch": scheduler, "scheduler_batch": scheduler})
        elif modello == "Krea-2 Turbo": 
            sessione.salva_sessione({"scheduler_krea2_batch": scheduler, "scheduler_batch": scheduler})
        else:
            sessione.salva_sessione({"scheduler_zimage_batch": scheduler, "scheduler_batch": scheduler})

    if "steps_slider" in t4: _salva_comp(t4["steps_slider"], salva_steps_dinamico_batch, inputs=[t4["steps_slider"], t4["dropdown_image_model_batch"]])
    if "sampler_dropdown" in t4: t4["sampler_dropdown"].change(fn=salva_sampler_dinamico_batch, inputs=[t4["sampler_dropdown"], t4["dropdown_image_model_batch"]])

    if "img_width" in t4: t4["img_width"].change(lambda v: sessione.salva_sessione({"img_width_batch": v}), inputs=[t4["img_width"]])
    if "img_height" in t4: t4["img_height"].change(lambda v: sessione.salva_sessione({"img_height_batch": v}), inputs=[t4["img_height"]])
    if "img_copies" in t4: _salva_comp(t4["img_copies"], "img_copies_batch")
    if "scheduler_dropdown" in t4: t4["scheduler_dropdown"].change(fn=salva_scheduler_dinamico_batch, inputs=[t4["scheduler_dropdown"], t4["dropdown_image_model_batch"]])
    
    if "hires_steps_slider" in t4: _salva_comp(t4["hires_steps_slider"], "hires_steps_batch")
    if "hires_denoise_slider" in t4: _salva_comp(t4["hires_denoise_slider"], "hires_denoise_batch")
    if "hires_scale_slider" in t4: _salva_comp(t4["hires_scale_slider"], "hires_scale_batch")

    if "batch_mode" in t4: t4["batch_mode"].change(lambda v: sessione.salva_sessione({"batch_mode": v}), inputs=[t4["batch_mode"]])
    if "dropdown_image_model_batch" in t4: t4["dropdown_image_model_batch"].change(lambda v: sessione.salva_sessione({"modello_immagine_attivo_batch": v}), inputs=[t4["dropdown_image_model_batch"]])
