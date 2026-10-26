# utils/media_base.py

import os
import re
from PIL import Image

def depura_nome_file_infinito(nome):
    """Risolve il bug di ricorsione dei nomi file lunghi pulendo e deduplicando le stringhe."""
    if not nome:
        return ""
    
    nome = os.path.splitext(nome)[0]
    nome = re.sub(r'__+', '_', nome)
    # Depura modelli, tag operativi e frame generati da video
    nome = re.sub(r'(?i)(_zimage|_flux2|_flux2k|_krea2_edit|_krea2|_refined|_resized|_panel_\d+|_trimmed|_clip|_grid|_inizio|_fine|_storyboard|_c\d+|_frame_esteso|frame_esteso|_frame|frame)+', '', nome)
    # Depura indici progressivi e timestamp (es. _0001 o _20260814_120000)
    nome = re.sub(r'_\d{4,8}(?:_\d{4,6})?', '', nome)
    
    parti = nome.split('_')
    parti_uniche = []
    for p in parti:
        if p and p not in parti_uniche:
            parti_uniche.append(p)
            
    nome_pulito = "_".join(parti_uniche).strip('_')
    
    if len(nome_pulito) > 35:
        nome_pulito = nome_pulito[:35].rstrip('_')
        
    return nome_pulito


def calcola_rapporto_vicino(w, h):
    ratios = {
        "16:9": 16/9,
        "9:16": 9/16,
        "4:3": 4/3,
        "3:4": 3/4,
        "1:1": 1.0
    }
    img_ratio = w / h
    closest_ratio = min(ratios.keys(), key=lambda k: abs(ratios[k] - img_ratio))
    return closest_ratio


def calcola_risoluzione_vicina(w, h):
    lato_corto_orig = min(w, h)
    scelte = {
        "256p": 256,
        "360p": 360,
        "480p": 480,
        "720p": 720,
        "1080p": 1080
    }
    closest_res = min(scelte.keys(), key=lambda k: abs(scelte[k] - lato_corto_orig))
    return closest_res


def leggi_dimensioni_immagine_sicura(immagine):
    if immagine is None:
        return None, None
        
    if hasattr(immagine, "size") and isinstance(immagine.size, tuple):
        return immagine.size[0], immagine.size[1]
        
    if hasattr(immagine, "shape") and isinstance(immagine.shape, tuple):
        if len(immagine.shape) >= 2:
            return immagine.shape[1], immagine.shape[0]
            
    if isinstance(immagine, dict):
        if "width" in immagine and "height" in immagine:
            return int(immagine["width"]), int(immagine["height"])
        path_temp = immagine.get("path") or immagine.get("name")
        if path_temp and os.path.exists(path_temp):
            try:
                with Image.open(path_temp) as im:
                    return im.size[0], im.size[1]
            except:
                pass
                
    if isinstance(immagine, str) and os.path.exists(immagine):
        try:
            with Image.open(immagine) as im:
                return im.size[0], im.size[1]
        except:
            pass
            
    return None, None


def _estrai_percorso_video_sicuro(video):
    if not video:
        return None
    if isinstance(video, str):
        return video
    if isinstance(video, dict):
        path = video.get("path") or video.get("name")
        if path:
            return path
        for k, v in video.items():
            if isinstance(v, dict):
                sub_path = _estrai_percorso_video_sicuro(v)
                if sub_path:
                    return sub_path
            elif k == "path" or k == "name":
                return v
    return None


def _estrai_percorso_immagine_sicuro(immagine):
    if not immagine:
        return None
    if isinstance(immagine, str):
        return immagine
    if isinstance(immagine, dict):
        return immagine.get("path") or immagine.get("name")
    if hasattr(immagine, "path"):
        return immagine.path
    if hasattr(immagine, "name"):
        return immagine.name
    return str(immagine)


def norm_path_sicuro(path):
    if not path:
        return ""
    p_norm = os.path.normpath(os.path.abspath(path))
    if os.name == 'nt':
        p_norm = p_norm.lower() 
    return p_norm