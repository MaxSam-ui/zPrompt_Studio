# services/comfyui_manager.py

import os
import shutil
import subprocess
import time
import threading
import atexit
import socket
import re
import requests
import uuid
import signal
from urllib.parse import urlparse

from core import config
from core import log
from services.owned_process import launch_owned_process, close_owned_job

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["TQDM_DISABLE"] = "1"

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

COMFYUI_DIR = config.COMFYUI_DIR

if os.name == 'nt':
    COMFYUI_EXE  = os.path.join(COMFYUI_DIR, "python_embeded", "python.exe")
else:
    venv_python = os.path.join(COMFYUI_DIR, "bin", "python")
    if os.path.exists(venv_python):
        COMFYUI_EXE = venv_python
    else:
        COMFYUI_EXE = "python3"

COMFYUI_MAIN = os.path.join(COMFYUI_DIR, "ComfyUI", "main.py")

COMFYUI_CMD  = [
    COMFYUI_EXE,
    "-s",
    COMFYUI_MAIN,
    "--listen", "127.0.0.1",
    "--port", "8188"
]

if os.name == 'nt':
    COMFYUI_CMD.append("--windows-standalone-build")

COMFYUI_CMD += config.COMFYUI_ARGS

if config.COMFYUI_HIGHVRAM:
    COMFYUI_CMD.append("--highvram")
    log.registra("✅ ComfyUI started with --highvram (models retained in VRAM).")
else:
    log.registra("ℹ️ ComfyUI started without --highvram (dynamic VRAM management).")

LOCK_FILE = config.COMFYUI_LOCK_FILE

client_id = str(uuid.uuid4())

comfyui_process = None
comfyui_ready   = False
startup_error = ""
_startup_lock   = threading.Lock()

_avvio_in_corso = False

generazione_attiva = False
batch_attivo = False
vlm_interrotto = False
skip_richiesto = False

progresso_comfyui = {
    "percentuale": 0,
    "attivo": False
}
_progress_lock = threading.Lock()

_comfyui_online_cached = False
_status_monitor_thread_started = False
_status_monitor_lock = threading.Lock()


def reset_progresso():
    with _progress_lock:
        progresso_comfyui["percentuale"] = 0
        progresso_comfyui["attivo"] = False


def get_progresso():
    with _progress_lock:
        if progresso_comfyui["attivo"]:
            return progresso_comfyui["percentuale"]
        return None


def _estrai_host_e_porta_da_url(url):
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8188
        return host, port
    except Exception:
        return "127.0.0.1", 8188


def _porta_in_uso(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def _monitora_stato_comfyui_loop():
    global _comfyui_online_cached
    host, porta = _estrai_host_e_porta_da_url(config.COMFYUI_URL)
    
    while True:
        port_active = _porta_in_uso(host, porta)
        if not port_active:
            _comfyui_online_cached = False
        else:
            try:
                r = requests.get(config.COMFYUI_URL + "/system_stats", timeout=1.5)
                _comfyui_online_cached = (r.status_code == 200)
            except Exception:
                _comfyui_online_cached = False
                
        time.sleep(3.0)


def avvia_monitor_stato_background():
    global _status_monitor_thread_started
    with _status_monitor_lock:
        if not _status_monitor_thread_started:
            t = threading.Thread(target=_monitora_stato_comfyui_loop, daemon=True)
            t.start()
            _status_monitor_thread_started = True


def is_comfyui_running():
    avvia_monitor_stato_background()
    if (generazione_attiva or batch_attivo) and _comfyui_online_cached:
        return True
    return _comfyui_online_cached


def _termina_comfyui_esistente():
    host, porta = _estrai_host_e_porta_da_url(config.COMFYUI_URL)
    if not _porta_in_uso(host, porta):
        return
    log.registra(f"Detected external ComfyUI on port {porta}. Attempting complete tree termination...")
    try:
        if os.name == 'nt':
            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                creationflags=CREATE_NO_WINDOW
            )
            target_port_str = f":{porta}"
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and parts[3] == "LISTENING":
                    local_addr = parts[1]
                    if local_addr.endswith(target_port_str):
                        pid = parts[-1]
                        if pid.isdigit():
                            log.registra(f"Terminating PID tree {pid} on port {porta}...")
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", pid], 
                                capture_output=True, 
                                creationflags=CREATE_NO_WINDOW
                            )
                            time.sleep(1)
                            return
        else:
            result = subprocess.run(
                ["lsof", "-t", f"-iTCP:{porta}", "-sTCP:LISTEN"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            pids = result.stdout.strip().split()
            killed_any = False
            for pid in pids:
                if pid.isdigit():
                    log.registra(f"Terminating PID {pid} on Unix...")
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                    killed_any = True
            if killed_any:
                time.sleep(1)
            return
    except Exception as e:
        log.registra(f"Unable to terminate existing ComfyUI: {e}", "WARNING")


def kill_existing_comfyui_instance():
    host, porta = _estrai_host_e_porta_da_url(config.COMFYUI_URL)
    if _porta_in_uso(host, porta):
        _termina_comfyui_esistente()
        for _ in range(15):
            if not _porta_in_uso(host, porta):
                break
            time.sleep(0.5)


def _pulisci_cartella_input():
    input_dir = os.path.join(COMFYUI_DIR, "ComfyUI", "input")
    if not os.path.exists(input_dir):
        return
    try:
        eliminati = 0
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(input_dir, filename)
                try:
                    os.remove(filepath)
                    eliminati += 1
                except Exception:
                    pass
        if eliminati > 0:
            log.registra(f"ComfyUI input cleanup: removed {eliminati} orphan files.")
    except Exception as e:
        log.registra(f"Error cleaning input folder: {e}", "WARNING")


def _esecuzione_effettiva_avvio():
    global comfyui_process, comfyui_ready, startup_error

    with _startup_lock:
        startup_error = ""

        host, porta = _estrai_host_e_porta_da_url(config.COMFYUI_URL)
        if _porta_in_uso(host, porta):
            try:
                response = requests.get(config.COMFYUI_URL + "/system_stats", timeout=5)
                response.raise_for_status()
                if "system" not in response.json():
                    raise ValueError("The port is not serving ComfyUI")
                comfyui_ready = True
                log.registra("Reusing the available ComfyUI service.")
            except Exception as error:
                startup_error = "comfy_error_port"
                log.registra(f"ComfyUI port is occupied but not ready: {error}", "WARNING")
            return

        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                pid = f.read().strip()
            try:
                import psutil
                if psutil.pid_exists(int(pid)):
                    log.registra(f"⚠️ Startup already in progress (PID {pid}). Waiting 5s...")
                    time.sleep(5)
                    if is_comfyui_running():
                        comfyui_ready = True
                        return
            except ImportError:
                log.registra("Lock file present but psutil not installed, ignoring.")
                try: os.remove(LOCK_FILE)
                except: pass

        if os.path.exists(LOCK_FILE):
            try: os.remove(LOCK_FILE)
            except: pass

        file_validi = False
        for _ in range(3):
            exe_exists = os.path.isfile(COMFYUI_EXE) or (shutil.which(COMFYUI_EXE) is not None)
            if exe_exists and os.path.isfile(COMFYUI_MAIN):
                file_validi = True
                break
            time.sleep(1)

        if not file_validi:
            startup_error = "comfy_error_folder" if not os.path.isdir(COMFYUI_DIR) else "comfy_error_install"
            log.registra(
                "ComfyUI cannot start: check COMFYUI_DIR in settings.json and restart Studio. "
                f"Expected Python: {COMFYUI_EXE}; expected main.py: {COMFYUI_MAIN}. "
                "Use the portable root containing both python_embeded and ComfyUI.",
                "ERROR",
            )
            return

        try:
            with open(LOCK_FILE, "w") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

        log.registra("🔧 Starting ComfyUI process...")

        comfyui_env = os.environ.copy()
        comfyui_env["PYTHONIOENCODING"] = "utf-8"
        comfyui_env["TQDM_DISABLE"] = "1"

        log_dir = os.path.join(config.STUDIO_OUTPUT_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        numba_cache = os.path.join(config.STUDIO_OUTPUT_DIR, ".cache", "numba")
        os.makedirs(numba_cache, exist_ok=True)
        comfyui_env.setdefault("NUMBA_CACHE_DIR", numba_cache)
        output_log_path = os.path.join(log_dir, f"comfyui-{time.time_ns()}.log")

        try:
            output_stream = open(output_log_path, "ab", buffering=0)
            popen_kwargs = {
                "cwd": COMFYUI_DIR,
                "stdout": output_stream,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "encoding": 'utf-8',
                "errors": 'replace',
                "bufsize": 1,
                "env": comfyui_env
            }
            if os.name == 'nt':
                popen_kwargs["creationflags"] = CREATE_NO_WINDOW

            comfyui_process = launch_owned_process(
                COMFYUI_CMD,
                **popen_kwargs
            )
            output_stream.close()
            log.registra(f"✅ ComfyUI process started (PID {comfyui_process.pid})")
        except Exception as e:
            startup_error = "comfy_error_start"
            if 'output_stream' in locals():
                output_stream.close()
            log.registra(f"❌ Startup ERROR: {e}", "ERROR")
            if os.name == 'nt' and os.path.exists(LOCK_FILE):
                try: os.remove(LOCK_FILE)
                except: pass
            return

        try:
            with open(LOCK_FILE, "w") as f:
                f.write(str(comfyui_process.pid))
        except Exception:
            pass

        def leggi_output():
            global progresso_comfyui
            process = comfyui_process
            with open(output_log_path, encoding="utf-8", errors="replace") as output_reader:
                while True:
                    linea = output_reader.readline()
                    if not linea:
                        if process.poll() is not None:
                            break
                        time.sleep(0.2)
                        continue
                    log.registra(f"[ComfyUI] {linea.rstrip()}")
                    match = re.search(r'\b(\d{1,3})%', linea)
                    if match:
                        percent = int(match.group(1))
                        with _progress_lock:
                            progresso_comfyui["percentuale"] = percent
                            progresso_comfyui["attivo"] = True
            with _progress_lock:
                progresso_comfyui["attivo"] = False

        threading.Thread(target=leggi_output, daemon=True).start()

        timeout_seconds = getattr(config, 'COMFYUI_STARTUP_TIMEOUT', 180)
        max_iterations = timeout_seconds // 2
        
        log.registra(f"⏳ Waiting for ComfyUI startup (timeout: {timeout_seconds}s)...")
        for _ in range(max_iterations):
            if is_comfyui_running():
                comfyui_ready = True
                log.registra("🎉 ComfyUI ready.")
                if os.path.exists(LOCK_FILE):
                    try: os.remove(LOCK_FILE)
                    except: pass
                return
            if comfyui_process.poll() is not None:
                break
            time.sleep(2)

        if comfyui_process.poll() is not None:
            startup_error = "comfy_error_start"
            log.registra(f"⚠️ ComfyUI terminated (code {comfyui_process.returncode})", "ERROR")
        else:
            startup_error = "comfy_error_timeout"
            log.registra(f"⚠️ ComfyUI non-responsive within {timeout_seconds}s.")
        if os.path.exists(LOCK_FILE):
            try: os.remove(LOCK_FILE)
            except: pass


def start_comfyui_background():
    global _avvio_in_corso
    with _startup_lock:
        if _avvio_in_corso:
            log.registra("ComfyUI bootstrap already active in background. Request ignored.", "WARNING")
            return
        _avvio_in_corso = True
        
    def thread_wrapper():
        global _avvio_in_corso, startup_error
        try:
            _esecuzione_effettiva_avvio()
        except Exception as error:
            startup_error = "comfy_error_start"
            log.registra(f"ComfyUI bootstrap failed: {error}", "ERROR")
        finally:
            with _startup_lock:
                _avvio_in_corso = False

    lancio_thread = threading.Thread(target=thread_wrapper, daemon=True)
    lancio_thread.start()


def stop_comfyui():
    """Stop only the backend launched by this application instance."""
    global comfyui_process, comfyui_ready
    process = comfyui_process
    if process is None:
        return
    # Closing the job also reaps descendants if the backend already exited.
    owned_job = getattr(process, "_studio_job", None)
    if owned_job is not None:
        close_owned_job(process)
    log.registra(f"Stopping owned ComfyUI process {process.pid}...")
    if os.name == 'nt' and owned_job is None and process.poll() is None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    elif os.name != "nt" and process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    comfyui_process = None
    comfyui_ready = False
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as lock:
                owns_lock = lock.read().strip() == str(process.pid)
            if owns_lock:
                os.remove(LOCK_FILE)
        except OSError:
            pass


def interrompi_comfyui():
    """
    Gestore unificato globale di stop:
    Interrompe istantaneamente qualsiasi processo attivo (ComfyUI o LLM/VLM)
    e svuota la coda di esecuzione.
    """
    global skip_richiesto, generazione_attiva, batch_attivo, vlm_interrotto
    generazione_attiva = False
    batch_attivo = False
    vlm_interrotto = True
    skip_richiesto = False

    try:
        url_interrupt = config.COMFYUI_URL + "/interrupt"
        requests.post(url_interrupt, timeout=5)
        
        url_clear = config.COMFYUI_URL + "/queue"
        requests.post(url_clear, json={"clear": True}, timeout=5)
        
        log.registra("[INTERRUPT] Unified stop command sent: VLM stopped and ComfyUI queue flushed.")
        return "⏹️ Interruption completed."
    except Exception as e:
        log.registra(f"Unable to contact ComfyUI for interrupt: {e}", "WARNING")
        return "⏹️ Interrupted (ComfyUI offline)."


def salta_generazione_corrente():
    """
    Sends interrupt signal to ComfyUI to skip ONLY the current generation.
    """
    global skip_richiesto
    try:
        skip_richiesto = True
        url_interrupt = config.COMFYUI_URL + "/interrupt"
        requests.post(url_interrupt, timeout=5)
        log.registra("[SKIP] Sent single interrupt command to ComfyUI to skip current generation.")
        return "⏭️ Current generation skipped."
    except Exception as e:
        skip_richiesto = False
        log.registra(f"Unable to contact ComfyUI for skip: {e}", "WARNING")
        return "⚠️ ComfyUI unreachable."


a_registrazione_uscita = False
if not a_registrazione_uscita:
    atexit.register(stop_comfyui)
    a_registrazione_uscita = True
