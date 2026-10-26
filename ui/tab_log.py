# ui/tab_log.py

import os
import json
from html import escape
import gradio as gr
from typing import Dict, Any

from core import log, lingua, config, sessione
from core.model_cache import get_cache_dir
from services.installation_check import collect_checks, render_checks

def ottieni_mappa_workflow_attivi() -> dict:
    workflows_dir = os.path.join(config.STUDIO_ROOT_DIR, "workflows")
    return {
        "Z-Image Turbo": config.WF_ZIMAGE_FILE,
        "Flux.2 Klein": os.path.join(workflows_dir, "flux2_klein_api.json"),
        "Krea-2 Turbo": config.WF_KREA2_FILE,
        "Krea-2 Edit": config.WF_KREA2_EDIT_FILE,
        "Qwen Image 2.1 Edit": os.path.join(workflows_dir, "qwen_image_2.1_edit_api.json"),
        "LTX-2.5 Video": config.WF_LTX_FILE,
        "MiniMax H3 Video": config.WF_MINIMAX_FILE
    }


def estrai_modelli_da_workflow_json(file_path: str) -> dict:
    modelli = {}
    if not os.path.exists(file_path):
        return modelli
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            wf = json.load(f)
        
        for node_id, node in wf.items():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs", {})
            
            if "unet_name" in inputs:
                modelli["UNET (Diffusion)"] = {"path": inputs["unet_name"], "cat": "unet"}
            elif "gguf_name" in inputs:
                modelli["UNET (GGUF)"] = {"path": inputs["gguf_name"], "cat": "unet"}
                
            if "vae_name" in inputs:
                title = node.get("_meta", {}).get("title", "VAE")
                label = f"VAE ({title})" if "audio" in title.lower() or "video" in title.lower() else "VAE"
                modelli[label] = {"path": inputs["vae_name"], "cat": "vae"}
                
            if "clip_name" in inputs:
                modelli["CLIP (Text Encoder)"] = {"path": inputs["clip_name"], "cat": "clip"}
            elif "clip_name1" in inputs or "clip_name2" in inputs:
                if "clip_name1" in inputs:
                    modelli["CLIP Primario"] = {"path": inputs["clip_name1"], "cat": "clip"}
                if "clip_name2" in inputs:
                    modelli["CLIP Secondario"] = {"path": inputs["clip_name2"], "cat": "clip"}
                    
            if "lora_name" in inputs:
                title = node.get("_meta", {}).get("title", "LoRA")
                modelli[f"LoRA ({title})"] = {"path": inputs["lora_name"], "cat": "lora"}
                
    except Exception as e:
        log.registra(f"Error during dynamic extraction of workflow '{file_path}': {e}", "WARNING")
        
    return modelli


def verifica_presenza_modello_multi_path(rel_path: str, categoria: str) -> tuple[bool, str]:
    models_base = os.path.join(config.COMFYUI_DIR, "ComfyUI", "models")
    path_pulito = rel_path.replace("\\", "/").strip("/")
    
    mappa_cartelle = {
        "unet": ["unet", "diffusion_models"],
        "clip": ["clip", "text_encoders"],
        "vae": ["vae"],
        "lora": ["loras", "lora"]
    }
    
    sotto_cartelle = mappa_cartelle.get(categoria, [categoria])
    
    path_senza_prefisso = path_pulito
    for prefisso in sotto_cartelle + ["unet", "diffusion_models", "clip", "text_encoders", "vae", "loras", "lora"]:
        if path_pulito.lower().startswith(f"{prefisso.lower()}/"):
            path_senza_prefisso = "/".join(path_pulito.split("/")[1:])
            break
            
    candidates = []
    for folder in sotto_cartelle:
        candidates.append(os.path.join(models_base, folder, path_senza_prefisso))
        candidates.append(os.path.join(models_base, folder, path_pulito))
        
    candidates.append(os.path.join(models_base, path_pulito))
    candidates.append(os.path.join(models_base, path_senza_prefisso))
    
    for path in candidates:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            rel_trovato = os.path.relpath(abs_path, models_base).replace("\\", "/")
            return True, rel_trovato
            
    return False, f"{sotto_cartelle[0]}/{path_senza_prefisso}"


def rileva_modelli_vlm_locali() -> list:
    hub_dir = get_cache_dir()
    if not os.path.exists(hub_dir):
        return []
    
    modelli_trovati = []
    try:
        for d in os.listdir(hub_dir):
            if d.startswith("models--"):
                parts = d.split("--")
                if len(parts) >= 3:
                    owner = parts[1]
                    name = "--".join(parts[2:])
                    name_parsed = f"{owner}/{name}"
                    
                    snapshots_dir = os.path.join(hub_dir, d, "snapshots")
                    if os.path.exists(snapshots_dir) and os.listdir(snapshots_dir):
                        modelli_trovati.append(name_parsed)
    except Exception:
        pass
    return sorted(list(set(modelli_trovati)))


def elenca_files_in_cartelle(nomi_cartelle: list, estensioni=(".safetensors", ".gguf", ".ckpt", ".pt")) -> list:
    models_base = os.path.join(config.COMFYUI_DIR, "ComfyUI", "models")
    files_trovati = []
    for cartella in nomi_cartelle:
        percorso_abs = os.path.join(models_base, cartella)
        if not os.path.exists(percorso_abs):
            continue
        try:
            for item in os.listdir(percorso_abs):
                item_path = os.path.join(percorso_abs, item)
                if os.path.isfile(item_path) and item.endswith(estensioni):
                    files_trovati.append(f"{cartella}/{item}")
                elif os.path.isdir(item_path):
                    for sub_item in os.listdir(item_path):
                        sub_item_path = os.path.join(item_path, sub_item)
                        if os.path.isfile(sub_item_path) and sub_item.endswith(estensioni):
                            files_trovati.append(f"{cartella}/{item}/{sub_item}")
        except Exception:
            continue
    return sorted(files_trovati)


def compila_dashboard_modelli_html() -> str:
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    dl = lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))

    vlm_cache_dir = get_cache_dir()
    vlm_modelli = rileva_modelli_vlm_locali()
    vlm_presente = bool(vlm_modelli)
    
    vlm_list_html = ""
    if vlm_modelli:
        items = "".join([f'<li style="margin-bottom: 2px;"><code>{m}</code></li>' for m in vlm_modelli])
        titolo_vlm = dl.get("vlm_downloaded_title", "Locally downloaded VLM models:")
        vlm_list_html = f"""
        <div style="margin-top: 10px; border-top: 1px dashed rgba(59, 130, 246, 0.2); padding-top: 8px;">
            <strong style="color: #60a5fa; font-size: 0.85em;">📦 {titolo_vlm}</strong>
            <ul style="margin: 4px 0 0 0; padding-left: 18px; font-size: 0.8em; color: #cbd5e1; list-style-type: square;">
                {items}
            </ul>
        </div>
        """
    else:
        msg_no_vlm = dl.get("vlm_none_detected", "No completed VLM models detected in local cache.")
        vlm_list_html = f"""
        <div style="margin-top: 10px; border-top: 1px dashed rgba(239, 68, 68, 0.2); padding-top: 8px; font-size: 0.8em; color: #f87171; font-style: italic;">
            {msg_no_vlm}
        </div>
        """

    sub_vlm_cache = dl.get("vlm_cache_sub", "Local caching directory for VLM/LLM models")
    lbl_vlm_active = dl.get("status_active", "Active ✔") if vlm_presente else dl.get("status_empty", "Empty ❌")

    vlm_status_html = f"""
    <div style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 8px; padding: 12px 16px; margin-bottom: 20px;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 20px;">🧠</span>
                <div>
                    <strong style="color: #fff; font-size: 1.05em;">VLM Cache (Transformers / PyTorch)</strong>
                    <div style="font-size: 0.85em; color: #94a3b8; margin-top: 2px;">{sub_vlm_cache} ({escape(vlm_cache_dir)})</div>
                </div>
            </div>
            <span style="background: {'rgba(16, 185, 129, 0.15)' if vlm_presente else 'rgba(239, 68, 68, 0.15)'}; border: 1px solid {'#10b981' if vlm_presente else '#ef4444'}; color: {'#10b981' if vlm_presente else '#f87171'}; font-size: 0.78em; font-weight: 700; padding: 4px 10px; border-radius: 12px; text-transform: uppercase;">
                {lbl_vlm_active}
            </span>
        </div>
        {vlm_list_html}
    </div>
    """
    
    cards_html = ""
    mappa_wf = ottieni_mappa_workflow_attivi()
    msg_wf_not_found = dl.get("workflow_not_found", "Workflow file not found on disk:")
    
    for group_name, wf_path in mappa_wf.items():
        if not os.path.exists(wf_path):
            cards_html += f"""
            <div style="background: rgba(0, 0, 0, 0.15); border: 1px dashed rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 14px; display: flex; flex-direction: column;">
                <h4 style="margin: 0 0 10px 0; color: #f87171; font-size: 1.05em; font-weight: 700;">
                    ⚠️ {group_name}
                </h4>
                <div style="font-size: 0.8em; color: #94a3b8; font-style: italic;">
                    {msg_wf_not_found}<br>
                    <code style="font-size: 0.85em; color: #f87171; word-break: break-all;">{wf_path}</code>
                </div>
            </div>
            """
            continue
            
        modelli_dichiarati = estrai_modelli_da_workflow_json(wf_path)
        files_html = ""
        cartelle_da_scansionare = set()
        
        for role_name, info in modelli_dichiarati.items():
            relative_path = info["path"]
            categoria = info["cat"]
            
            esiste, percorso_reale_trovato = verifica_presenza_modello_multi_path(relative_path, categoria)
            
            status_color = "#10b981" if esiste else "#f87171"
            status_bg = "rgba(16, 185, 129, 0.1)" if esiste else "rgba(239, 68, 68, 0.1)"
            status_border = "rgba(16, 185, 129, 0.25)" if esiste else "rgba(239, 68, 68, 0.25)"
            status_label = dl.get("status_present", "Present ✔") if esiste else dl.get("status_missing", "Missing ❌")
            
            parti = percorso_reale_trovato.split("/")
            if len(parti) > 1:
                cartelle_da_scansionare.add("/".join(parti[:-1]))
                cartelle_da_scansionare.add(parti[0])
                if parti[0] == "unet":
                    cartelle_da_scansionare.add("diffusion_models")
                elif parti[0] == "clip":
                    cartelle_da_scansionare.add("text_encoders")
            
            files_html += f"""
            <div style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.03); display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;">
                <div style="max-width: 70%;">
                    <div style="font-weight: 700; font-size: 0.85em; color: #cbd5e1;">{role_name}</div>
                    <div style="font-size: 0.85em; color: #aeb8c8; margin-top: 3px; font-family: monospace; word-break: break-all;">ComfyUI/models/{percorso_reale_trovato}</div>
                </div>
                <span style="background: {status_bg}; border: 1px solid {status_border}; color: {status_color}; font-size: 0.72em; font-weight: 700; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; white-space: nowrap;">
                    {status_label}
                </span>
            </div>
            """
            
        modelli_rilevati = elenca_files_in_cartelle(list(cartelle_da_scansionare))
        esploratore_html = ""
        if modelli_rilevati:
            punti_lista = "".join([f'<div style="padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.02);">{m}</div>' for m in modelli_rilevati])
            txt_show = dl.get("show_all_files_detected", "Show all detected files in this category")
            esploratore_html = f"""
            <details style="margin-top: 12px; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 8px;">
                <summary style="cursor: pointer; font-size: 0.8em; color: #3b82f6; font-weight: 600; outline: none; user-select: none;">
                    📁 {txt_show} ({len(modelli_rilevati)})...
                </summary>
                <div style="margin-top: 6px; max-height: 120px; overflow-y: auto; font-family: monospace; font-size: 0.75em; color: #94a3b8; background: rgba(0,0,0,0.25); padding: 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.04);">
                    {punti_lista}
                </div>
            </details>
            """
        else:
            msg_no_files = dl.get("no_files_found", "No compatible files found in search directories.")
            esploratore_html = f"""
            <div style="margin-top: 10px; font-size: 0.75em; color: #64748b; font-style: italic;">
                {msg_no_files}
            </div>
            """
            
        cards_html += f"""
        <div style="background: rgba(0, 0, 0, 0.15); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 14px; display: flex; flex-direction: column;">
            <h4 style="margin: 0 0 10px 0; color: #3b82f6; font-size: 1.05em; font-weight: 700; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid rgba(59, 130, 246, 0.15); padding-bottom: 6px;">
                🎨 {group_name}
            </h4>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                {files_html}
            </div>
            {esploratore_html}
        </div>
        """
        
    dashboard_html = f"""
    <div style="font-family: inherit;">
        {vlm_status_html}
        <div class="studio-model-grid">
            {cards_html}
        </div>
    </div>
    """
    return dashboard_html


def crea_tab_log(d: Dict[str, str], s: Dict[str, Any]) -> Dict[str, Any]:
    with gr.Tab(d.get("tab_log", "Logs & Settings"), elem_id="tab-log") as tab_el:
        lingua_avvio = s.get("lingua_selezionata", "IT")

        with gr.Row(equal_height=False, elem_id="row-settings", elem_classes=["studio-workspace"]):
            with gr.Column(scale=8, min_width=340, elem_id="studio-logs", elem_classes=["analisi-col-box"]):
                registri_sistema_header = gr.Markdown(
                    d.get("registri_sistema_header", "System Logs"),
                    elem_classes=["studio-section-title"]
                )
                box_log_terminale = gr.Code(
                    value=log.ottieni_tutti_i_log(),
                    language="shell",
                    label=d.get("box_log_terminale", "Console Logs"),
                    lines=18,
                    interactive=False,
                    elem_id="studio-log-console",
                    elem_classes=["box-log-scorrimento"]
                )
                with gr.Row(elem_id="studio-log-actions"):
                    btn_refresh_logs = gr.Button(d.get("btn_refresh_logs", "Refresh Logs"), variant="secondary")
                    btn_clear_logs = gr.Button(d.get("btn_clear_logs", "Clear Logs"), variant="stop")

            with gr.Column(scale=4, min_width=260, elem_id="studio-preferences", elem_classes=["analisi-col-box"]):
                elenco_lingue_rilevate = list(lingua.LINGUE.keys()) if lingua.LINGUE else ["IT", "EN"]
                selettore_lingua = gr.Dropdown(
                    choices=elenco_lingue_rilevate,
                    value=lingua_avvio,
                    label=d.get("lingua_label", "Interface Language"),
                    allow_custom_value=False,
                )

        with gr.Accordion(d.get("diagnostica_titolo", "🔍 Model Diagnostics & Status (ComfyUI & VLM)"), open=False, elem_id="studio-diagnostics") as accordion_diagnostica:
            check_rows = gr.State([])
            btn_check_install = gr.Button('Verifica installazione' if lingua_avvio == 'IT' else 'Check installation', size='sm')
            install_report = gr.HTML('')
            def check_install(lang):
                rows = collect_checks()
                return rows, render_checks(rows, lang)
            btn_check_install.click(check_install, [selettore_lingua], [check_rows, install_report], concurrency_limit=1)
            selettore_lingua.change(
                lambda lang, rows: (gr.update(value='Verifica installazione' if lang == 'IT' else 'Check installation'), render_checks(rows, lang)),
                [selettore_lingua, check_rows], [btn_check_install, install_report], show_progress='hidden')
            vlm_cache_path = gr.Textbox(value=get_cache_dir(), label=d['vlm_cache_path'], info=d['vlm_cache_help'])
            btn_save_vlm_cache = gr.Button(d['vlm_cache_save'], size='sm')
            vlm_cache_status = gr.Markdown('')
            dashboard_modelli = gr.HTML(
                value=compila_dashboard_modelli_html(),
                elem_id="diagnostica-modelli-html"
            )

    return {
        "tab_el": tab_el,
        "vlm_cache_path": vlm_cache_path,
        "btn_save_vlm_cache": btn_save_vlm_cache,
        "vlm_cache_status": vlm_cache_status,
        "selettore_lingua": selettore_lingua,
        "registri_sistema_header": registri_sistema_header, 
        "box_log_terminale": box_log_terminale,
        "btn_refresh_logs": btn_refresh_logs,
        "btn_clear_logs": btn_clear_logs,
        "dashboard_modelli": dashboard_modelli,  
        "accordion_diagnostica": accordion_diagnostica
    }
