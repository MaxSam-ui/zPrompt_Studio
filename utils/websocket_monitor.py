# utils/websocket_monitor.py

import json
import os
import time
import requests
import websocket
import glob
from core import config, log

def _history_event(history, prompt_id):
    entry = history.get(str(prompt_id))
    if not isinstance(entry, dict):
        return None
    status = entry.get('status') or {}
    if status.get('status_str') == 'error':
        return 'error'
    if status.get('completed') is True:
        return 'done'
    return None

def stream_webhook_events(prompt_id, ws_url, wf, timeout=600.0):
    """
    Generatore di eventi WebSocket robusto e affidabile.
    Intercetta 'executed_file' non appena il file è pronto su disco ed esegue
    lo streaming continuo della percentuale KSampler.
    Include controllo preventivo e polling di sicurezza su History API.
    """
    from services import comfyui_manager
    history_url = config.COMFYUI_URL + "/history/" + str(prompt_id)
    
    # 1. CONTROLLO PREVENTIVO IMMEDIATO: se ComfyUI ha già terminato il task prima dell'apertura del socket
    try:
        resp_check = requests.get(history_url, timeout=1.5)
        event = _history_event(resp_check.json(), prompt_id) if resp_check.status_code == 200 else None
        if event:
            log.registra(f"[WebSocket/HTTP] Prompt {prompt_id} already completed in ComfyUI history.")
            yield (event, None)
            return
    except Exception:
        pass

    ws = None
    has_started = False
    last_activity_time = time.time()
    last_history_poll_time = time.time()
    reconnect_attempts = 0
    max_reconnect_attempts = 3
    current_node = None

    def _tenta_connessione_ws():
        nonlocal ws
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        nuovo_ws = websocket.WebSocket()
        nuovo_ws.connect(ws_url, timeout=5.0)
        nuovo_ws.settimeout(1.0)
        ws = nuovo_ws

    try:
        try:
            _tenta_connessione_ws()
        except Exception as e_init:
            log.registra(f"[WebSocket] Initial connection failed ({e_init}), attempting immediate recovery...", "WARNING")

        while True:
            if not comfyui_manager.generazione_attiva and not comfyui_manager.batch_attivo:
                log.registra("[WebSocket] Manager interruption detected. Closing socket.")
                break

            # 2. POLLING PERIODICO DI SICUREZZA SU HISTORY OGNI 2.5s (Previene blocchi su task già finiti)
            now = time.time()
            if now - last_history_poll_time > 2.5:
                last_history_poll_time = now
                try:
                    resp = requests.get(history_url, timeout=1.0)
                    event = _history_event(resp.json(), prompt_id) if resp.status_code == 200 else None
                    if event:
                        log.registra(f"[WebSocket/HTTP] Prompt {prompt_id} completion detected through History API.")
                        yield (event, None)
                        break
                except Exception:
                    pass

            if time.time() - last_activity_time > timeout:
                log.registra(f"[WebSocket] Idle timeout ({timeout}s) reached without messages from ComfyUI.", "WARNING")
                yield ('timeout', None)
                break

            if ws is None:
                try:
                    _tenta_connessione_ws()
                    log.registra("[WebSocket] Connessione ripristinata con successo.")
                    reconnect_attempts = 0
                except Exception:
                    reconnect_attempts += 1
                    try:
                        resp = requests.get(history_url, timeout=2)
                        event = _history_event(resp.json(), prompt_id) if resp.status_code == 200 else None
                        if event:
                            log.registra(f"[WebSocket/HTTP] Prompt {prompt_id} completed successfully during fallback.")
                            yield (event, None)
                            break
                    except Exception:
                        pass
                    
                    if reconnect_attempts >= max_reconnect_attempts:
                        log.registra("[WebSocket] Reconnection attempt limit reached.", "WARNING")
                        yield ('error', None)
                        break
                    time.sleep(1.0)
                    continue

            try:
                out = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except (websocket.WebSocketConnectionClosedException, ConnectionResetError, BrokenPipeError) as e:
                log.registra(f"[WebSocket] Transient disconnection ({e}). Attempting recovery...", "WARNING")
                ws = None
                continue
            except Exception as e:
                log.registra(f"[WebSocket] Socket error ({e}). Attempting recovery...", "WARNING")
                ws = None
                continue

            if not out:
                continue

            last_activity_time = time.time()

            if isinstance(out, str):
                msg = json.loads(out)
                msg_type = msg.get('type')
                data = msg.get('data', {}) or {}
                msg_pid = data.get('prompt_id')

                if msg_pid and str(msg_pid) != str(prompt_id):
                    continue

                if msg_type == 'execution_start':
                    has_started = True
                    yield ('executing', 'Inizializzazione dei nodi')

                elif msg_type == 'progress':
                    value = data.get('value')
                    max_val = data.get('max')
                    percent = int((value / max_val) * 100) if max_val else 0
                    node_id = data.get('node', current_node)
                    node = wf.get(str(node_id), {}) if isinstance(wf, dict) else {}
                    phase = (node.get('_meta') or {}).get('title') or node.get('class_type')
                    yield ('progress', {'percent': percent, 'phase': phase})

                elif msg_type == 'executed':
                    node_output = data.get('output') or {}
                    if isinstance(node_output, dict):
                        media_list = (
                            (node_output.get('gifs') or []) +
                            (node_output.get('videos') or []) +
                            (node_output.get('images') or [])
                        )
                        for media_info in media_list:
                            if not isinstance(media_info, dict):
                                continue
                            subfolder = media_info.get('subfolder', '')
                            filename = media_info.get('filename')
                            if filename:
                                full_path = os.path.join(config.COMFYUI_OUTPUT_DIR, subfolder, filename) if subfolder else os.path.join(config.COMFYUI_OUTPUT_DIR, filename)
                                abs_p = os.path.abspath(full_path)
                                if os.path.exists(abs_p):
                                    yield ('executed_file', abs_p)
                                else:
                                    yield ('executed_info', abs_p)

                elif msg_type == 'executing':
                    node_id = data.get('node')
                    current_node = node_id
                    if node_id is None:
                        if has_started:
                            yield ('done', None)
                            break
                    else:
                        class_type = wf.get(str(node_id), {}).get('class_type', 'Nodo') if isinstance(wf, dict) else 'Nodo'
                        yield ('executing', class_type)

                elif msg_type == 'execution_interrupted':
                    log.registra("[WebSocket] Received 'execution_interrupted' event from ComfyUI.")
                    if getattr(comfyui_manager, "skip_richiesto", False):
                        comfyui_manager.skip_richiesto = False
                        yield ('skip', None)
                    elif not has_started:
                        yield ('stale_interrupt', None)
                    elif comfyui_manager.generazione_attiva or comfyui_manager.batch_attivo:
                        yield ('skip', None)
                    else:
                        break
                    break

                elif msg_type == 'execution_success':
                    yield ('done', None)
                    break

                elif msg_type == 'execution_error':
                    yield ('error', None)
                    break
    except GeneratorExit:
        log.registra("[WebSocket] Monitor stopped externally. Closing socket.")
    finally:
        if ws:
            try:
                ws.close()
            except Exception:
                pass


def recupera_file_generato(prompt_id, output_dir=None, extensions=None):
    if output_dir is None:
        output_dir = config.COMFYUI_OUTPUT_DIR
    history_url = config.COMFYUI_URL + "/history/" + str(prompt_id)
    
    for tentativo in range(15):
        from services import comfyui_manager
        if not comfyui_manager.generazione_attiva and not comfyui_manager.batch_attivo:
            log.registra("[History API] Polling annullato per avvenuta interruzione manuale dei processi.")
            return None

        try:
            response = requests.get(history_url, timeout=3)
            response.raise_for_status()
            data = response.json()
            prompt_data = data.get(str(prompt_id), {})
            
            if prompt_data:
                outputs = prompt_data.get('outputs') or {}
                if isinstance(outputs, dict):
                    for node_output in outputs.values():
                        if not isinstance(node_output, dict):
                            continue
                        media_list = (
                            (node_output.get('gifs') or []) + 
                            (node_output.get('videos') or []) + 
                            (node_output.get('images') or [])
                        )
                        for media_info in media_list:
                            if not isinstance(media_info, dict):
                                continue
                            subfolder = media_info.get('subfolder', '')
                            filename = media_info.get('filename')
                            if filename and (extensions is None or os.path.splitext(filename)[1].lower() in extensions):
                                full_path = os.path.join(output_dir, subfolder, filename) if subfolder else os.path.join(output_dir, filename)
                                if os.path.exists(path := os.path.abspath(full_path)):
                                    return path
        except Exception:
            pass
            
        time.sleep(1.5)
        
    return None
