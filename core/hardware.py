# core/hardware.py

import os
import shutil
import requests
import subprocess
import threading
import time

from core import config
from core import log

try:
    import psutil
    _has_psutil = True
except ImportError:
    _has_psutil = False

_has_nvidia_smi = shutil.which("nvidia-smi") is not None
_ultimo_servizio_usato = None

_stato_risorse_cached = "Initializing resource monitor..."
_monitor_risorse_started = False
_monitor_risorse_lock = threading.Lock()


def _campiona_telemetria_istantanea():
    """Interroga istantaneamente psutil e nvidia-smi per restituire i valori reali di VRAM/RAM/CPU."""
    if _has_psutil:
        cpu_percent = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        ram_used_gb = ram.used / (1024 ** 3)
        ram_total_gb = ram.total / (1024 ** 3)
        ram_percent = ram.percent
        stato = f"🧠 CPU: {cpu_percent}% | 💾 RAM: {ram_used_gb:.0f}/{ram_total_gb:.0f}GB ({ram_percent}%)"
    else:
        stato = "🧠 CPU: N/A | 💾 RAM: N/A (psutil missing)"

    if _has_nvidia_smi:
        try:
            run_kwargs = {
                "capture_output": True,
                "text": True,
                "timeout": 2
            }
            if os.name == 'nt':
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                **run_kwargs
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    gpu_load = float(parts[0].strip())
                    used_mem = float(parts[1].strip()) / 1024.0
                    total_mem = float(parts[2].strip()) / 1024.0
                    vram_percent = (used_mem / total_mem) * 100 if total_mem > 0 else 0
                    stato += f" | ⚙️ GPU: {gpu_load:.0f}% | 🎮 VRAM: {used_mem:.0f}/{total_mem:.0f}GB ({vram_percent:.0f}%)"
        except Exception:
            pass
            
    return stato


def _monitora_risorse_loop():
    """Background loop to prevent nvidia-smi calls from blocking UI thread."""
    global _stato_risorse_cached
    while True:
        _stato_risorse_cached = _campiona_telemetria_istantanea()
        time.sleep(4.0)


def avvia_monitor_risorse_background():
    """Safely starts telemetry thread."""
    global _monitor_risorse_started
    with _monitor_risorse_lock:
        if not _monitor_risorse_started:
            t = threading.Thread(target=_monitora_risorse_loop, daemon=True)
            t.start()
            _monitor_risorse_started = True


def ottieni_stato_risorse():
    """Returns compact HTML status reading cached values instantly."""
    avvia_monitor_risorse_background()
    return _stato_risorse_cached


def aggiorna_e_campiona_stato_immediato():
    """Forza il campionamento sincrono e aggiorna la cache istantaneamente."""
    global _stato_risorse_cached
    _stato_risorse_cached = _campiona_telemetria_istantanea()
    return _stato_risorse_cached


def libera_modelli_comfyui(forzato=False):
    if config.KEEP_MODELS_WARM and not forzato:
        log.registra("[VRAM] Coexistence active: keeping ComfyUI models in memory.")
        return "✅ ComfyUI warm"

    try:
        resp = requests.post(config.COMFYUI_URL + "/free", json={"unload_models": True, "free_memory": True}, timeout=5)
        if resp.status_code == 200:
            log.registra("ComfyUI: Models successfully unloaded from VRAM.")
            return "✅ ComfyUI cleared"
        else:
            log.registra(f"ComfyUI /free responded with status {resp.status_code}", "WARNING")
            return f"⚠️ /free response {resp.status_code}"
    except Exception as e:
        log.registra(f"Unable to contact ComfyUI /free: {e}", "WARNING")
        return "⚠️ ComfyUI offline"


def libera_modelli_vlm():
    if config.KEEP_MODELS_WARM:
        log.registra("[VRAM] Coexistence active: keeping VLM models in memory.")
        return "✅ VLM warm"

    try:
        from services.local_vlm import libera_memoria_vlm
        libera_memoria_vlm()
        return "✅ Local models unallocated"
    except Exception as e:
        log.registra(f"Unable to free local VLM memory: {e}", "WARNING")
        return f"⚠️ VLM deallocation error: {e}"


def prepara_vram(servizio_richiesto):
    global _ultimo_servizio_usato
    
    if config.KEEP_MODELS_WARM:
        log.registra(f"[VRAM] Coexistence active: keeping service {servizio_richiesto} warm without unloading others.")
        _ultimo_servizio_usato = servizio_richiesto
        return
        
    if _ultimo_servizio_usato == servizio_richiesto:
        log.registra(f"[VRAM] Same service requested ({servizio_richiesto}). Keeping cached models warm.")
        return
        
    log.registra(f"[VRAM] Service switch detected: from {_ultimo_servizio_usato} to {servizio_richiesto}. Optimizing VRAM...")
    
    if servizio_richiesto == "VLM":
        if _ultimo_servizio_usato in ["COMFY_IMG", "COMFY_VID"]:
            libera_modelli_comfyui()
            
    elif servizio_richiesto == "COMFY_IMG":
        libera_modelli_vlm()
        if _ultimo_servizio_usato == "COMFY_VID":
            libera_modelli_comfyui()
            
    elif servizio_richiesto == "COMFY_VID":
        libera_modelli_vlm()
        if _ultimo_servizio_usato == "COMFY_IMG":
            libera_modelli_comfyui()
            
    _ultimo_servizio_usato = servizio_richiesto


def libera_risorse_sistema():
    """
    Funzione del Pennello: scarica forzatamente ed esclusivamente il modello LLM/VLM
    da RAM e VRAM, senza toccare ComfyUI o i suoi modelli.
    """
    global _ultimo_servizio_usato
    from services import vlm_loader, comfyui_manager
    
    # 1. Interrompe eventuali generazioni VLM in corso
    comfyui_manager.vlm_interrotto = True
    
    # 2. Scaricamento forzato e profondo del solo VLM (rimozione hook accelerate + buffer CPU)
    try:
        vlm_loader.libera_memoria_vlm_forzata()
        msg_vlm = "✅ VLM unallocated"
    except Exception as e:
        log.registra(f"Unable to free local VLM memory: {e}", "WARNING")
        msg_vlm = "⚠️ VLM deallocation error"
    
    import gc
    gc.collect()
    
    # Se il servizio attivo registrato era il VLM, azzera il tracciamento
    if _ultimo_servizio_usato == "VLM":
        _ultimo_servizio_usato = None
    
    # 3. Campionamento istantaneo della telemetria reale
    stato = aggiorna_e_campiona_stato_immediato()
    return f"{msg_vlm} | {stato}"


def hard_reset_sistema():
    """
    Funzione del Tasto Rosso: Hard Reset totale del sistema.
    Arresta tutto, svuota le code e scarica sia ComfyUI sia il VLM.
    """
    global _ultimo_servizio_usato
    from services import comfyui_manager
    from services import vlm_loader
    
    # 1. Flag di stop immediato
    comfyui_manager.generazione_attiva = False
    comfyui_manager.batch_attivo = False
    comfyui_manager.vlm_interrotto = True
    
    # 2. Interruzione di ComfyUI e pulizia della coda
    try:
        comfyui_manager.interrompi_comfyui()
    except Exception as e:
        log.registra(f"[HARD RESET] Error interrupting ComfyUI: {e}", "WARNING")
        
    time.sleep(0.3)
    
    # 3. Scaricamento forzato del VLM
    try:
        vlm_loader.libera_memoria_vlm_forzata()
        msg_vlm = "✅ VLM models unallocated"
    except Exception as e:
        log.registra(f"[HARD RESET] Error unloading VLM: {e}", "WARNING")
        msg_vlm = "⚠️ VLM deallocation error"
        
    # 4. Scaricamento forzato di ComfyUI
    msg_comfy = libera_modelli_comfyui(forzato=True)
    
    # 5. Garbage collection di sistema
    import gc
    gc.collect()
    
    _ultimo_servizio_usato = None
    
    log.registra("[HARD RESET] System fully restored to idle state.")
    
    stato = aggiorna_e_campiona_stato_immediato()
    return stato


def suggerisci_highvram():
    """Suggests enabling --highvram based on detected VRAM."""
    if not _has_nvidia_smi:
        return
        
    try:
        run_kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": 2
        }
        if os.name == 'nt':
            run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            **run_kwargs
        )
        if result.returncode == 0 and result.stdout.strip():
            vram_total_mb = int(result.stdout.strip())
            vram_total_gb = vram_total_mb / 1024.0
            if vram_total_gb >= 20:
                log.registra(
                    f"💡 Suggestion: You have {vram_total_gb:.0f} GB of VRAM. "
                    f"If using 4-bit VLM, you can enable 'COMFYUI_HIGHVRAM': true "
                    f"in settings.json to increase performance."
                )
            else:
                log.registra(
                    f"💡 Suggestion: You have {vram_total_gb:.0f} GB of VRAM. "
                    f"Keep 'COMFYUI_HIGHVRAM': false to prevent OOM risks."
                )
    except Exception:
        pass