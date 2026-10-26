# generators/metadata_extractor.py

import json
from core import log


def _estrai_valore_sicuro_lista(dizionario, chiave):
    val = dizionario.get(chiave)
    if isinstance(val, list) and len(val) > 0:
        return val[0]
    return None


def estrai_info_da_immagine(im_pil):
    """Estrae il prompt e il seed originari incorporati nei metadati PNG/EXIF dell'immagine."""
    try:
        info = getattr(im_pil, "info", {})
        raw = info.get('workflow') or info.get('prompt')
        if not raw: 
            return "", None
            
        wf = json.loads(raw) if isinstance(raw, str) else raw
        prompt, seed = "", None
        
        if isinstance(wf, dict):
            # Controllo Z-Image Turbo (Nodo 45 per Prompt, 44 per Seed)
            if wf.get("59", {}).get("class_type") == "TextEncodeQwenImage21":
                prompt = wf["59"].get("inputs", {}).get("prompt", "")
                seed = wf.get("61", {}).get("inputs", {}).get("seed")
            elif "45" in wf:
                prompt = wf["45"].get("inputs", {}).get("text", "")
                if "44" in wf: 
                    seed = wf["44"].get("inputs", {}).get("seed")
            # Controllo Krea-2 Turbo Primary (Nodo 100 per Prompt, 102 per Seed)
            elif "100" in wf:
                prompt = wf["100"].get("inputs", {}).get("text", "")
                if "102" in wf:
                    seed = wf["102"].get("inputs", {}).get("seed")
            # Controllo Flux.2 Klein & Krea-2 Turbo Legacy (Nodo 5 per Prompt, 12 o 8 per Seed)
            elif "5" in wf:
                prompt = wf["5"].get("inputs", {}).get("value", "") or wf["5"].get("inputs", {}).get("text", "")
                if "12" in wf: 
                    seed = wf["12"].get("inputs", {}).get("noise_seed")
                elif "8" in wf: 
                    seed = wf["8"].get("inputs", {}).get("seed")
                    
            elif "nodes" in wf:
                for node in wf["nodes"]:
                    node_id = str(node.get("id"))
                    if node_id == "45": 
                        p_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if p_val is not None: prompt = str(p_val)
                    elif node_id == "44": 
                        s_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if s_val is not None: seed = s_val
                    elif node_id == "100":
                        p_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if p_val is not None: prompt = str(p_val)
                    elif node_id == "102":
                        s_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if s_val is not None: seed = s_val
                    elif node_id == "5": 
                        p_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if p_val is not None: prompt = str(p_val)
                    elif node_id == "12": 
                        s_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if s_val is not None: seed = s_val
                    elif node_id == "8":
                        s_val = _estrai_valore_sicuro_lista(node, "widgets_values")
                        if s_val is not None: seed = s_val
                        
        return prompt, seed
    except Exception as e:
        log.registra(f"Image metadata decoding error: {e}", "WARNING")
        return "", None
