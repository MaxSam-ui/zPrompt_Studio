# services/catalog_manager.py

import os
import json
from core import config, log

PATH_CATALOG_DIR = config.SUGGESTION_SEQUENCE_DIR
PATH_DEFAULT_DIR = os.path.join(PATH_CATALOG_DIR, "default")

PATH_CHARACTERS = os.path.join(PATH_DEFAULT_DIR, "characters.json")
PATH_OUTFITS = os.path.join(PATH_DEFAULT_DIR, "outfits.json")
PATH_ACTIONS = os.path.join(PATH_DEFAULT_DIR, "actions.json")

DEFAULT_CHARACTERS = {
    "Elegant Protagonist": "An elegant 35-year-old protagonist with expressive hazel eyes, natural dark wavy hair, and a confident cinematic posture",
    "Noir Detective": "A rugged 40-year-old detective in a tailored charcoal trench coat, subtle stubble, intense focused gaze",
    "Sci-Fi Pilot": "A 28-year-old female pilot with sleek braided hair, athletic build, subtle cybernetic ear piece",
    "Adventurer Explorer": "A 35-year-old weathered explorer with rolled-up linen shirt, leather shoulder holster, and sun-tanned skin",
    "Vintage Gentleman": "A distinguished 55-year-old gentleman in a three-piece bespoke tweed suit, silver-streaked hair and refined grooming"
}

DEFAULT_OUTFITS = {
    "Cyberpunk Alley (Night Neon)": "dark tactical streetwear with glowing accents in a rainy neo-Tokyo alley, vibrant cyan and magenta neon reflections",
    "Sunset Terrace (Coastal View)": "flowing white linen resort wear on a cliffside Italian terrace overlooking the Mediterranean during golden hour",
    "Ancient Library (Warm Glow)": "vintage wool blazer and cashmere turtleneck in a grand mahogany library with amber desk lamps and dust motes in sunbeams",
    "Vintage Train Carriage (Orient Express)": "classic 1930s tailored evening attire inside an opulent velvet-and-brass train compartment at night"
}

DEFAULT_ACTIONS = {
    "1. Entrance & Observant Gaze": "Steps into the frame, pausing to observe the surroundings with an alert, analytical expression",
    "2. Examining the Clue": "Leans forward over the table to inspect an object closely, fingers gently tracing the edge",
    "3. Sudden Reaction & Turn": "Suddenly turns head towards a sudden sound off-camera, eyes narrowing with sharp tension",
    "4. Decisive Movement": "Stands up swiftly and moves forward through the room with determined, purposeful strides",
    "5. Intense Close-up Climax": "Dramatic extreme close-up facing the camera, catching rim lighting on facial features, a knowing expression"
}

def _inizializza_catalogo():
    os.makedirs(PATH_DEFAULT_DIR, exist_ok=True)
    if not os.path.exists(PATH_CHARACTERS):
        with open(PATH_CHARACTERS, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CHARACTERS, f, indent=4, ensure_ascii=False)
    if not os.path.exists(PATH_OUTFITS):
        with open(PATH_OUTFITS, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_OUTFITS, f, indent=4, ensure_ascii=False)
    if not os.path.exists(PATH_ACTIONS):
        with open(PATH_ACTIONS, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_ACTIONS, f, indent=4, ensure_ascii=False)

_inizializza_catalogo()


def _pulisci_nome_genere(genere):
    if not genere or not isinstance(genere, str):
        return None
    g_clean = os.path.splitext(os.path.basename(genere.strip()))[0].strip()
    if g_clean in ["-", "None", "Nessuno", "", "nessuno"]:
        return None
    return g_clean


def _trova_cartella_genere_case_insensitive(genere_clean):
    if not genere_clean or not os.path.exists(PATH_CATALOG_DIR):
        return None
        
    g_lower = genere_clean.lower()
    if g_lower in ["default", "- default preset -", "default preset"]:
        return PATH_DEFAULT_DIR
    
    try:
        subdirs = [d for d in os.listdir(PATH_CATALOG_DIR) if os.path.isdir(os.path.join(PATH_CATALOG_DIR, d))]
        
        for d in subdirs:
            if d.lower() == g_lower:
                return os.path.join(PATH_CATALOG_DIR, d)
                
    except Exception as e:
        log.registra(f"Error locating genre folder (case-insensitive): {e}", "WARNING")
        
    return None


def _ottieni_path_file(tipo, genere=None):
    tipo_lower = str(tipo).lower()
    
    if "personaggio" in tipo_lower or "character" in tipo_lower:
        filename = "characters.json"
        path_root = PATH_CHARACTERS
    elif "outfit" in tipo_lower or "location" in tipo_lower:
        filename = "outfits.json"
        path_root = PATH_OUTFITS
    else:
        filename = "actions.json"
        path_root = PATH_ACTIONS

    genere_clean = _pulisci_nome_genere(genere)
    if genere_clean:
        folder_match = _trova_cartella_genere_case_insensitive(genere_clean)
        if folder_match and folder_match != PATH_DEFAULT_DIR:
            path_genere = os.path.join(folder_match, filename)
            if os.path.exists(path_genere):
                return path_genere, path_root
            return path_genere, path_root

    return path_root, None


def carica_catalogo(tipo, genere=None):
    if not tipo or not isinstance(tipo, str):
        return DEFAULT_CHARACTERS

    tipo_lower = tipo.lower()
    is_char = ("personaggio" in tipo_lower or "character" in tipo_lower)
    is_outfit = ("outfit" in tipo_lower or "location" in tipo_lower)
    default_fallback = DEFAULT_CHARACTERS if is_char else DEFAULT_OUTFITS if is_outfit else DEFAULT_ACTIONS

    path_principale, path_root = _ottieni_path_file(tipo, genere)

    if path_principale and os.path.exists(path_principale):
        try:
            with open(path_principale, "r", encoding="utf-8") as f:
                dati = json.load(f)
                if isinstance(dati, list):
                    dati = {f"Action {i+1}": item for i, item in enumerate(dati)}
                if isinstance(dati, dict):
                    return dati
        except Exception as e:
            log.registra(f"Error reading catalog {path_principale}: {e}", "WARNING")

    if path_root and os.path.exists(path_root) and path_principale != path_root:
        try:
            with open(path_root, "r", encoding="utf-8") as f_r:
                dati_r = json.load(f_r)
                if isinstance(dati_r, list):
                    dati_r = {f"Action {i+1}": item for i, item in enumerate(dati_r)}
                if isinstance(dati_r, dict):
                    return dati_r
        except Exception:
            pass

    return default_fallback


def salva_elemento_catalogo(tipo, nome_etichetta, descrizione_prompt, genere=None):
    if not nome_etichetta or not descrizione_prompt:
        return carica_catalogo(tipo, genere)
    
    tipo_str = str(tipo) if tipo else "Personaggio"
    tipo_lower = tipo_str.lower()
    genere_clean = _pulisci_nome_genere(genere)
    
    filename = "characters.json" if ("personaggio" in tipo_lower or "character" in tipo_lower) else "outfits.json" if ("outfit" in tipo_lower or "location" in tipo_lower) else "actions.json"

    if genere_clean and genere_clean.lower() not in ["default", "- default preset -", "default preset"]:
        folder_match = _trova_cartella_genere_case_insensitive(genere_clean)
        cartella_genere = folder_match if folder_match else os.path.join(PATH_CATALOG_DIR, genere_clean)
        os.makedirs(cartella_genere, exist_ok=True)
        path_file = os.path.join(cartella_genere, filename)
    else:
        path_file = PATH_CHARACTERS if ("personaggio" in tipo_lower or "character" in tipo_lower) else PATH_OUTFITS if ("outfit" in tipo_lower or "location" in tipo_lower) else PATH_ACTIONS

    dati = {}
    if os.path.exists(path_file):
        try:
            with open(path_file, "r", encoding="utf-8") as f:
                dati = json.load(f)
                if isinstance(dati, list):
                    dati = {f"Action {i+1}": item for i, item in enumerate(dati)}
        except Exception:
            dati = {}

    dati[nome_etichetta.strip()] = descrizione_prompt.strip()

    try:
        with open(path_file, "w", encoding="utf-8") as f:
            json.dump(dati, f, indent=4, ensure_ascii=False)
        log.registra(f"Catalog: Saved/updated '{nome_etichetta}' in {path_file}")
    except Exception as e:
        log.registra(f"Error saving catalog: {e}", "WARNING")
        
    return dati


def elimina_elemento_catalogo(tipo, nome_etichetta, genere=None):
    tipo_str = str(tipo) if tipo else "Personaggio"
    tipo_lower = tipo_str.lower()
    genere_clean = _pulisci_nome_genere(genere)
    
    filename = "characters.json" if ("personaggio" in tipo_lower or "character" in tipo_lower) else "outfits.json" if ("outfit" in tipo_lower or "location" in tipo_lower) else "actions.json"

    if genere_clean and genere_clean.lower() not in ["default", "- default preset -", "default preset"]:
        folder_match = _trova_cartella_genere_case_insensitive(genere_clean)
        cartella_genere = folder_match if folder_match else os.path.join(PATH_CATALOG_DIR, genere_clean)
        path_file = os.path.join(cartella_genere, filename)
    else:
        path_file = PATH_CHARACTERS if ("personaggio" in tipo_lower or "character" in tipo_lower) else PATH_OUTFITS if ("outfit" in tipo_lower or "location" in tipo_lower) else PATH_ACTIONS

    dati = {}
    if os.path.exists(path_file):
        try:
            with open(path_file, "r", encoding="utf-8") as f:
                dati = json.load(f)
                if isinstance(dati, list):
                    dati = {f"Action {i+1}": item for i, item in enumerate(dati)}
        except Exception:
            dati = {}

    nome_pulito = nome_etichetta.strip()
    if nome_pulito in dati:
        del dati[nome_pulito]
        try:
            with open(path_file, "w", encoding="utf-8") as f:
                json.dump(dati, f, indent=4, ensure_ascii=False)
            log.registra(f"Catalog: Deleted '{nome_pulito}' from {path_file}")
        except Exception as e:
            log.registra(f"Error deleting catalog: {e}", "WARNING")
            
    return dati