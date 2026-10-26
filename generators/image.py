# generators/image.py

import os
import time
import gradio as gr
from core import config, sessione, log, lingua, hardware, workflow_registry
from services import comfyui_manager
from utils.media_utils import compila_galleria_html, norm_path_sicuro, pulisci_lista_percorsi_galleria
from generators.image_utils import get_ws_url, prepara_vlm_per_generazione, esegui_rendering_comfyui_edit
from generators.image_standard import genera_immagine_standard


def genera_immagine_con_monitor(
    count, m_vlm, sugg_v, sys_p, hints, prompt,
    l1_n, l1_s, l2_n, l2_s, l3_n, l3_s,
    w, h, copie,
    steps, sampler_name, scheduler,
    hires_steps, hires_denoise, hires_scale,
    stato_gen,
    modello_immagine_attivo="Z-Image Turbo",
    img_seed_mode="randomize",
    img_seed="",
    generation_mode="Classica (1 Immagine)",
    sugg_storyboard="-",
    storyboard_pannelli="1x3 (3 Pannelli)",
    attiva_refine_storyboard=True,
    refine_denoise=0.35,
    krea2_edit_grounding_px=768,
    sequenza_num_scatti=5,
    sugg_sequenza="-",
    refine_instructions="",
    krea2_edit_height=1280,
    krea2_edit_lora_strength=0.75
):
    l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff = workflow_registry.estrai_lora_effettivi(
        count, l1_n, l1_s, l2_n, l2_s, l3_n, l3_s, modello_attivo=modello_immagine_attivo
    )

    cfg_modello = workflow_registry.ottieni_config_modello_immagine(modello_immagine_attivo)
    suffisso = cfg_modello.get("session_prefix", "_zimage")
        
    sessione.salva_sessione({
        f"lora1_name{suffisso}": l1_n_eff,
        f"lora2_name{suffisso}": l2_n_eff,
        f"lora3_name{suffisso}": l3_n_eff
    })

    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))

    comfyui_manager.generazione_attiva = True
    
    try:
        mode_str = str(generation_mode).lower()
        if "edit" not in mode_str and "modifica" not in mode_str:
            stato_gen["percorso_immagine_selezionata"] = None
        
        immagini_generate = stato_gen.get("immagini_generate_cumulate", [])
        if not isinstance(immagini_generate, list):
            immagini_generate = []
            
        seed_attuali = stato_gen.get("seed_attuali_cumulati", [])
        if not isinstance(seed_attuali, list):
            seed_attuali = []

        immagini_generate[:] = pulisci_lista_percorsi_galleria(immagini_generate)
        stato_gen["immagini_generate_cumulate"] = immagini_generate
        stato_gen["seed_attuali_cumulati"] = seed_attuali
            
        comfyui_manager.reset_progresso()
        html_galleria_avvio = compila_galleria_html(immagini_generate)
        ws_url = get_ws_url()

        if "edit" in mode_str or "modifica" in mode_str:
            prepara_vlm_per_generazione()
            
            input_image_path = stato_gen.get("percorso_immagine_selezionata") or s_attiva.get("percorso_immagine_selezionata")
            if not input_image_path or not os.path.exists(input_image_path):
                msg_error = dl.get("err_no_source_img_edit", "⚠️ Please upload or select a source image in the gallery first before applying the edit!")
                yield msg_error, html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                return
                
            sessione.salva_sessione({"percorso_immagine_selezionata": input_image_path})
            
            edit_prompt_effettivo = (refine_instructions or "").strip()
            if not edit_prompt_effettivo:
                s_fresh = sessione.carica_ultima_sessione()
                edit_prompt_effettivo = (s_fresh.get("krea2_edit_instruction") or prompt or "").strip()
            if not edit_prompt_effettivo:
                edit_prompt_effettivo = "make high quality enhancements"
                
            edit_height_effettiva = int(krea2_edit_height if krea2_edit_height else 1280)
            edit_lora_effettivo = float(krea2_edit_lora_strength if krea2_edit_lora_strength is not None else 0.75)
            edit_grounding_effettivo = int(krea2_edit_grounding_px if krea2_edit_grounding_px else 768)

            if modello_immagine_attivo == "Qwen Image 2.1":
                log.registra(f"Qwen Image 2.1 Edit: '{edit_prompt_effettivo}' (LoRA: {[(n, s) for n, s in [(l1_n_eff, l1_s_eff), (l2_n_eff, l2_s_eff), (l3_n_eff, l3_s_eff)] if n != '-' and s != 0]})")
            else:
                log.registra(f"{modello_immagine_attivo} Edit: '{edit_prompt_effettivo}' ({edit_height_effettiva}px, LoRA: {edit_lora_effettivo}, Grounding: {edit_grounding_effettivo}px)")

            yield dl.get("img_sending_edit_queue", "🔌 Sending edit request to ComfyUI..."), html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
            
            edit_output = None
            for status_msg, is_done, final_path, seed_pulito in esegui_rendering_comfyui_edit(
                edit_prompt_effettivo, img_seed_mode, img_seed, steps, sampler_name, scheduler,
                edit_grounding_effettivo, input_image_path, ws_url, dl, sub_dir=config.STUDIO_IMG_SUBDIR,
                krea2_edit_lora_strength=edit_lora_effettivo,
                krea2_edit_height=edit_height_effettiva, modello_edit=modello_immagine_attivo,
                loras=[(l1_n_eff, l1_s_eff), (l2_n_eff, l2_s_eff), (l3_n_eff, l3_s_eff)]
            ):
                if is_done and final_path:
                    edit_output = final_path
                    immagini_generate.append(final_path)
                    seed_attuali.append(seed_pulito)
                    yield status_msg, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                else:
                    yield status_msg, compila_galleria_html(immagini_generate), gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                    
                if status_msg.startswith(("❌", "⏹", "⏭", "⚠")):
                    return

            if not edit_output:
                yield dl["status_edit_missing"], html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                return
            target_sel = edit_output
            stato_gen["percorso_immagine_selezionata"] = target_sel
            stato_gen["immagini_generate_cumulate"] = immagini_generate
            stato_gen["seed_attuali_cumulati"] = seed_attuali
            stato_gen["gallery_no_sync"] = True
            
            sessione.salva_sessione({
                "immagini_generate_cumulate": stato_gen.get("immagini_generate_cumulate", []),
                "seed_attuali_cumulati": stato_gen.get("seed_attuali_cumulati", []),
                "percorso_immagine_selezionata": stato_gen.get("percorso_immagine_selezionata", None)
            })
            
            html_fine_classica = compila_galleria_html(immagini_generate, percorso_selezionato=target_sel)
            msg_edit_done = dl.get("edit_success", "✅ Image edit completed successfully!")
            yield msg_edit_done, html_fine_classica, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
            return

        elif "storyboard" in mode_str:
            # FASE 1: GENERA SOLO L'ANTEPRIMA DELLA GRIGLIA
            from generators.image_storyboard import genera_solo_griglia_storyboard
            
            msg_story_init = dl.get("storyboard_writing_status", "⏳ FASE 1/2: Generazione Griglia Storyboard in corso...")
            yield msg_story_init, html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
            
            for result, html_temp, prompt_val, timeline_val in genera_solo_griglia_storyboard(
                prompt, m_vlm, sugg_storyboard, storyboard_pannelli,
                l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff,
                w, h,
                steps, sampler_name, scheduler,
                hires_steps, hires_denoise, hires_scale,
                stato_gen,
                modello_immagine_attivo,
                img_seed_mode,
                img_seed,
                html_galleria_avvio,
                ws_url,
                dl
            ):
                if result.startswith("❌") or result.startswith("⏹️"):
                    yield result, gr.update(), html_temp or html_galleria_avvio, log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                    return
                
                yield result, gr.update(), html_temp, log.ottieni_tutti_i_log(), stato_gen, prompt_val, timeline_val
            return

        elif "sequenza" in mode_str or "sequence" in mode_str:
            from generators.image_sequence import genera_sequenza_immagini
            prepara_vlm_per_generazione()
            
            yield from genera_sequenza_immagini(
                prompt,
                l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff,
                w, h,
                steps, sampler_name, scheduler,
                hires_steps, hires_denoise, hires_scale,
                stato_gen,
                modello_immagine_attivo,
                img_seed_mode,
                img_seed,
                immagini_generate,
                seed_attuali,
                html_galleria_avvio,
                ws_url,
                dl,
                num_scatti=sequenza_num_scatti,
                sugg_sequenza=sugg_sequenza
            )
            return

        else:
            prepara_vlm_per_generazione()
                
            msg_sending_q = dl.get("img_sending_queue", "🔌 Sending {copies} requests to ComfyUI queue...").format(copies=int(copie))
            yield msg_sending_q, html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
            
            for status_msg, html_current in genera_immagine_standard(
                prompt,
                l1_n_eff, l1_s_eff, l2_n_eff, l2_s_eff, l3_n_eff, l3_s_eff,
                w, h, copie,
                steps, sampler_name, scheduler,
                hires_steps, hires_denoise, hires_scale,
                stato_gen,
                modello_immagine_attivo,
                img_seed_mode,
                img_seed,
                immagini_generate,
                seed_attuali,
                html_galleria_avvio,
                ws_url,
                dl
            ):
                if status_msg.startswith("❌") or status_msg.startswith("⏹️"):
                    yield status_msg, html_current or html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
                    return
                
                yield status_msg, html_current, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()

            immagini_generate[:] = pulisci_lista_percorsi_galleria(immagini_generate)

            target_sel = immagini_generate[-1] if immagini_generate else None
            stato_gen["percorso_immagine_selezionata"] = target_sel
            stato_gen["immagini_generate_cumulate"] = immagini_generate
            stato_gen["seed_attuali_cumulati"] = seed_attuali
            stato_gen["gallery_no_sync"] = True
            
            sessione.salva_sessione({
                "immagini_generate_cumulate": stato_gen.get("immagini_generate_cumulate", []),
                "seed_attuali_cumulati": stato_gen.get("seed_attuali_cumulati", []),
                "percorso_immagine_selezionata": stato_gen.get("percorso_immagine_selezionata", None)
            })
            
            html_fine_classica = compila_galleria_html(immagini_generate, percorso_selezionato=target_sel)
            msg_successo = dl.get("prog_img_done", "📸 Generation complete! {num} images in gallery.").format(num=len(immagini_generate))
            yield msg_successo, html_fine_classica, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()

    except Exception as err_proc:
        import traceback
        log.registra(f"Error in image process: {err_proc}", "ERROR")
        log.registra(traceback.format_exc(), "ERROR")
        msg_err_proc = dl.get("story_err_process", "❌ Error during generation process: {err_proc}").format(err_proc=err_proc)
        yield msg_err_proc, html_galleria_avvio, gr.update(), log.ottieni_tutti_i_log(), stato_gen, gr.update(), gr.update()
        
    finally:
        comfyui_manager.generazione_attiva = False
