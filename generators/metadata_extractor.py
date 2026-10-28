# generators/metadata_extractor.py

import json
from core import log


def _api_metadata(graph):
    """Follow active sampling/positive branches, independently of node IDs."""
    if not isinstance(graph, dict) or not graph or not all(isinstance(n, dict) and 'inputs' in n for n in graph.values()):
        return '', None

    def ancestors(start):
        pending, seen = list(start), set()
        while pending:
            key = pending.pop()
            if key in seen or key not in graph:
                continue
            seen.add(key)
            for value in graph[key]['inputs'].values():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    pending.append(value[0])
        return seen

    def linked(value):
        return [value[0]] if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) else []

    outputs = [k for k,n in graph.items() if n.get('class_type') in ('SaveImage', 'SaveVideo', 'VHS_VideoCombine')]
    if not outputs:
        return '', None
    prompts, seeds = set(), set()
    for key in ancestors(outputs):
        node = graph[key]; inputs = node['inputs']
        if node.get('class_type') not in ('KSampler','KSamplerAdvanced','SamplerCustomAdvanced','ClownsharKSampler_Beta'):
            continue
        positive = inputs.get('positive')
        guide = linked(inputs.get('guider'))
        if guide:
            positive = graph.get(guide[0], {}).get('inputs', {}).get('positive')
        for pkey in ancestors(linked(positive)):
            pnode = graph[pkey]
            if pnode.get('class_type') in ('CLIPTextEncode', 'TextEncodeQwenImage21', 'Krea2EditGroundedEncode'):
                text = pnode['inputs'].get('prompt', pnode['inputs'].get('text'))
                if isinstance(text, str) and text.strip(): prompts.add(text)
        seed = inputs.get('seed', inputs.get('noise_seed'))
        noise = linked(inputs.get('noise'))
        if noise: seed = graph.get(noise[0], {}).get('inputs', {}).get('noise_seed')
        if isinstance(seed, int): seeds.add(seed)
    return (next(iter(prompts)) if len(prompts)==1 else '', next(iter(seeds)) if len(seeds)==1 else None)


def _estrai_valore_sicuro_lista(dizionario, chiave):
    val = dizionario.get(chiave)
    if isinstance(val, list) and len(val) > 0:
        return val[0]
    return None


def estrai_info_da_immagine(im_pil):
    """Estrae il prompt e il seed originari incorporati nei metadati PNG/EXIF dell'immagine."""
    try:
        info = getattr(im_pil, "info", {})
        # ComfyUI stores the executed API graph separately from the editor graph.
        api = info.get('prompt')
        if api:
            try:
                api_prompt, api_seed = _api_metadata(json.loads(api) if isinstance(api, str) else api)
                if api_prompt:
                    return api_prompt, api_seed
            except (ValueError, TypeError):
                pass
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
