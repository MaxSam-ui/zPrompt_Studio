# core/suggestions.py

import os

# Elenco delle cartelle che compongono l'architettura dei preset
SUBFOLDERS = ["system", "vision", "storyboard", "direction", "screenplay", "sequence"]

def inizializza_suggerimenti(studio_root_dir, log_func=None):
    """
    Inizializza silenziosamente le cartelle dei suggerimenti sul disco.
    """
    for sub in SUBFOLDERS:
        base_dir = os.path.join(studio_root_dir, "suggestions", sub)
        os.makedirs(base_dir, exist_ok=True)
    os.makedirs(os.path.join(studio_root_dir, 'suggestions', 'system', 'custom'), exist_ok=True)
