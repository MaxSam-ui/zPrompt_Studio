from time import perf_counter
# services/vlm_loader.py

import os
import json
import torch
import gc
from threading import Lock
from PIL import Image 

# Respect the cache selected when Hugging Face is initialized. Changing HF_HOME
# after importing Transformers gives diagnostics and subprocesses a different cache.
from core.model_cache import get_cache_dir

if not hasattr(torch, "float8_e8m0fnu"):
    setattr(torch, "float8_e8m0fnu", torch.float32)

from core import log, config, sessione, lingua, hardware
from transformers import AutoProcessor, AutoTokenizer, StoppingCriteria

class InterruptCriteria(StoppingCriteria):
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        from services import comfyui_manager
        return not comfyui_manager.generazione_attiva


PATH_CONFIG_MODELLI = os.path.join(os.path.dirname(__file__), "..", "config", "config_models.json")

DEFAULT_CONFIG = {
    "modelli_disponibili": [
        "huihui_ai/qwen3-vl-abliterated:4b",
        "huihui_ai/qwen3-vl-abliterated:8b",
        "huihui_ai/gemma-4-e2b-it-abliterated:latest",
        "huihui_ai/gemma-4-abliterated:latest",
        "fredrezones55/Gemma-4-Uncensored-HauhauCS-Aggressive:e4b"
    ],
    "mappature_modelli": {
        "llava:latest": "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated",
        "llava": "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated",
        "qwen2.5-vl": "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated",
        "gemma": "huihui-ai/Huihui-gemma-4-E4B-it-abliterated",
        "fredrezones55/gemma-4-uncensored-hauhaucs-aggressive:e4b": "HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive",
        "fredrezones55/gemma-4-uncensored-hauhaucs-aggressive": "HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive",
        "huihui_ai/qwen3-vl-abliterated:8b": "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated",
        "huihui_ai/qwen3-vl-abliterated": "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated",
        "huihui_ai/qwen3-vl-abliterated:4b": "huihui-ai/Huihui-Qwen3-VL-4B-Instruct-abliterated",
        "huihui_ai/gemma-4-e2b-it-abliterated:latest": "huihui-ai/Huihui-gemma-4-E2B-it-abliterated",
        "huihui_ai/gemma-4-e2b-it-abliterated": "huihui-ai/Huihui-gemma-4-E2B-it-abliterated",
        "huihui_ai/gemma-4-abliterated:latest": "huihui-ai/Huihui-gemma-4-E4B-it-abliterated",
        "huihui_ai/gemma-4-abliterated": "huihui-ai/Huihui-gemma-4-E4B-it-abliterated"
    }
}

_config_cache = None


def _carica_configurazione_modelli():
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not os.path.exists(PATH_CONFIG_MODELLI):
        try:
            with open(PATH_CONFIG_MODELLI, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            log.registra(f"Configuration file automatically created: {PATH_CONFIG_MODELLI}")
            _config_cache = DEFAULT_CONFIG
            return _config_cache
        except Exception as e:
            log.registra(f"Unable to create config_models.json: {e}", "WARNING")
            return DEFAULT_CONFIG
    
    try:
        with open(PATH_CONFIG_MODELLI, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
            return _config_cache
    except Exception as e:
        log.registra(f"Error reading config_models.json (fallback to internal configuration): {e}", "WARNING")
        return DEFAULT_CONFIG


_config_modelli = _carica_configurazione_modelli()

try:
    from transformers import AutoModelForImageTextToText as AutoModelForVLM
    log.registra("Loaded import standard: AutoModelForImageTextToText")
except ImportError:
    try:
        from transformers import AutoModelForVision2Seq as AutoModelForVLM
        log.registra("Loaded import standard (legacy): AutoModelForVision2Seq")
    except ImportError:
        from transformers import AutoModelForCausalLM as AutoModelForVLM
        log.registra("Loaded import standard (fallback): AutoModelForCausalLM")

try:
    from transformers import BitsAndBytesConfig
    _has_bnb = True
except ImportError:
    _has_bnb = False

_modello_corrente = None
_processor_corrente = None
_nome_modello_caricato = None
_loading_lock = Lock()


def _normalizza_nome_modello(nome):
    if not nome:
        return "huihui-ai/Huihui-Qwen3-VL-4B-Instruct-abliterated"
    
    config_corrente = _carica_configurazione_modelli()
    mappature = config_corrente.get("mappature_modelli", DEFAULT_CONFIG["mappature_modelli"])
    nome_chiave = nome.strip().lower()
    mappature_lower = {k.lower(): v for k, v in mappature.items()}
    
    if nome_chiave in mappature_lower:
        return mappature_lower[nome_chiave]
    
    if ":" in nome:
        senza_tag = nome.split(":")[0].strip().lower()
        if senza_tag in mappature_lower:
            return mappature_lower[senza_tag]
        
        if "huihui_ai" in senza_tag:
            tag = nome.split(":")[1].strip().lower()
            if "8b" in tag:
                return "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated"
            elif "4b" in tag:
                return "huihui-ai/Huihui-Qwen3-VL-4B-Instruct-abliterated"
            elif "2b" in tag:
                return "huihui-ai/Huihui-Qwen3-VL-2B-Thinking-abliterated"
            elif "30b" in tag or "32b" in tag:
                return "huihui-ai/Huihui-Qwen3-VL-30B-A3B-Instruct-abliterated"
            else:
                return "huihui-ai/Huihui-Qwen3-VL-8B-Instruct-abliterated"
                
        nome = nome.split(":")[0].strip()
        
    return nome


def _libera_memoria_globale():
    """Esegue una deallocazione forzata e totale rompendo gli hook di accelerate e svuotando i buffer PyTorch."""
    global _modello_corrente, _processor_corrente, _nome_modello_caricato
    log.registra("[VRAM] Starting deep PyTorch deallocation (VRAM + RAM)...")

    if _modello_corrente is not None:
        # 1. Rimuove forzatamente tutti gli hook iniettati da accelerate sui sottomoduli
        try:
            from accelerate.hooks import remove_hook_from_submodules
            remove_hook_from_submodules(_modello_corrente)
        except Exception:
            pass

        # 2. Rilascia parametri e buffer (fondamentale per la Vision Tower di Qwen-VL)
        try:
            for param in _modello_corrente.parameters():
                param.grad = None
                param.data = torch.empty(0, device="cpu")
            for buf in _modello_corrente.buffers():
                buf.data = torch.empty(0, device="cpu")
        except Exception:
            pass

        # 3. Sposta eventuali moduli residui su CPU
        try:
            _modello_corrente.to("cpu")
        except Exception:
            pass

        del _modello_corrente
        _modello_corrente = None

    if _processor_corrente is not None:
        del _processor_corrente
        _processor_corrente = None

    _nome_modello_caricato = None

    # 4. Esegue cicli multipli di garbage collection per spezzare riferimenti ciclici
    for _ in range(3):
        gc.collect()

    # 5. Svuota completamente la memoria e la cache allocata dal backend CUDA
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        torch.cuda.synchronize()
        log.registra("[VRAM] CUDA hardware cleanup completed successfully: VRAM and RAM 100% free.")


def libera_memoria_vlm():
    if config.KEEP_MODELS_WARM:
        log.registra("[VRAM] Coexistence active: avoiding local VLM/LLM model unload from PyTorch.")
        return

    with _loading_lock:
        _libera_memoria_globale()


def libera_memoria_vlm_forzata():
    with _loading_lock:
        _libera_memoria_globale()


def _carica_modello_se_necessario(nome_modello, progress=None):
    global _modello_corrente, _processor_corrente, _nome_modello_caricato
    
    nome_reale = _normalizza_nome_modello(nome_modello)
    
    from core import hardware
    started = perf_counter()
    hardware.prepara_vram("VLM")
    log.registra(f"VLM memory preparation: {perf_counter() - started:.2f}s")
    
    with _loading_lock:
        if _modello_corrente is not None and _nome_modello_caricato == nome_reale:
            return _modello_corrente, _processor_corrente
        
        log.registra(f"VLM loader lock acquired after {perf_counter() - started:.2f}s")
        cache_dir = get_cache_dir()
        log.registra(f"PyTorch initialization for {nome_reale}; cache: {cache_dir}")
        _libera_memoria_globale()
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if device == "cuda":
            torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            torch_dtype = torch.float32
        
        try:
            if progress:
                progress("vlm_cache_check")
            try:
                _processor_corrente = AutoProcessor.from_pretrained(nome_reale, trust_remote_code=True, cache_dir=cache_dir)
            except Exception as ex_proc:
                log.registra(f"AutoProcessor loading failed ({ex_proc}). Falling back to AutoTokenizer...", "WARNING")
                _processor_corrente = AutoTokenizer.from_pretrained(nome_reale, trust_remote_code=True, cache_dir=cache_dir)
            
            log.registra(f"VLM processor ready after {perf_counter() - started:.2f}s")
            weights_started = perf_counter()
            nome_reale_lower = nome_reale.lower()
            usa_4bit = any(dim in nome_reale_lower for dim in ["2b", "4b", "7b", "8b", "9b", "12b", "27b", "30b", "32b"])
            
            model_kwargs = {'cache_dir': cache_dir}
            if usa_4bit and _has_bnb and device == "cuda":
                log.registra(f"Large model detected. Enabling on-the-fly 4-bit compression for {nome_reale}...")
                quantizzazione_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch_dtype,
                    bnb_4bit_use_double_quant=True
                )
                model_kwargs["quantization_config"] = quantizzazione_config
                model_kwargs["attn_implementation"] = "sdpa"
                model_kwargs["low_cpu_mem_usage"] = True
            else:
                if usa_4bit and not _has_bnb:
                    log.registra(
                        "WARNING: Large model detected but 'bitsandbytes' is not installed or supported. "
                        "Model will be loaded in full precision.", 
                        "WARNING"
                    )
                model_kwargs["torch_dtype"] = torch_dtype
                model_kwargs["attn_implementation"] = "sdpa"
                model_kwargs["low_cpu_mem_usage"] = True
            
            try:
                if progress:
                    progress("vlm_weights_loading")
                _modello_corrente = AutoModelForVLM.from_pretrained(
                    nome_reale,
                    device_map="auto" if device == "cuda" else None,
                    trust_remote_code=True,
                    **model_kwargs
                )
            except Exception as ex_vlm:
                log.registra(f"AutoModelForVLM loading failed ({ex_vlm}). Attempting AutoModelForCausalLM fallback...", "WARNING")
                from transformers import AutoModelForCausalLM
                _modello_corrente = AutoModelForCausalLM.from_pretrained(
                    nome_reale,
                    device_map="auto" if device == "cuda" else None,
                    trust_remote_code=True,
                    **model_kwargs
                )
            
            log.registra(f"VLM weights loaded in {perf_counter() - weights_started:.2f}s; total {perf_counter() - started:.2f}s")
            _modello_corrente.eval()
            _nome_modello_caricato = nome_reale
            log.registra(f"Model {nome_reale} ready for inference.")
        except Exception as e:
            log.registra(f"Error in native loading of {nome_reale}: {e}", "ERROR")
            _modello_corrente = None
            _nome_modello_caricato = None
            _processor_corrente = None
            raise e
            
        return _modello_corrente, _processor_corrente


def ottieni_modelli_disponibili():
    global _config_modelli
    _config_modelli = _carica_configurazione_modelli()
    return _config_modelli.get("modelli_disponibili", DEFAULT_CONFIG["modelli_disponibili"])


def warm_up_vlm(modello="huihui-ai/Huihui-Qwen3-VL-4B-Instruct-abliterated"):
    if not modello or modello.strip().lower() in ["none", "nessuno", "-", ""]:
        log.registra("Warm-up skipped: no valid VLM/LLM model selected.")
        return
    try:
        nome_reale = _normalizza_nome_modello(modello)
        log.registra(f"PyTorch warm-up in progress for model: {nome_reale}...")
        _carica_modello_se_necessario(nome_reale)
        log.registra("Warm-up completed successfully.")
    except Exception as e:
        log.registra(f"Warm-up failed: {e}", "WARNING")


def _ottieni_tokenizer(processor):
    if hasattr(processor, "tokenizer"):
        return processor.tokenizer
    return processor


def _ottieni_testi_vlm():
    s_attiva = sessione.carica_ultima_sessione()
    lang = s_attiva.get("lingua_selezionata", "IT")
    return lingua.LINGUE.get(lang, lingua.LINGUE.get("IT", {}))


def _e_processore_multimodale(processor):
    """Rileva in modo universale se l'oggetto processor è in grado di elaborare immagini (Qwen-VL, Gemma 4, LLaVA, ecc.)."""
    if isinstance(processor, AutoTokenizer):
        return False
    return (
        hasattr(processor, "image_processor") or
        hasattr(processor, "feature_extractor") or
        "processor" in type(processor).__name__.lower()
    )


def _prepara_input_sicuro(processor, testo, immagine_pil, device):
    if _e_processore_multimodale(processor):
        processor_kwargs = {"text": [testo], "return_tensors": "pt"}
        if isinstance(immagine_pil, Image.Image):
            processor_kwargs["images"] = immagine_pil
        try:
            return processor(**processor_kwargs).to(device)
        except Exception as e:
            log.registra(f"Flexible processor call triggered for {type(processor).__name__}: {e}", "WARNING")
            if isinstance(immagine_pil, Image.Image):
                return processor(images=immagine_pil, text=testo, return_tensors="pt").to(device)
            return processor(text=testo, return_tensors="pt").to(device)
    else:
        return processor([testo], return_tensors="pt").to(device)
