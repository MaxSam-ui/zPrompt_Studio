# core/log.py

import datetime
from collections import deque

# Maximum number of log entries kept in memory
MAX_LOG_ENTRIES = 1000

# Using a maxlen deque for O(1) efficiency on append and pop
_registri_log = deque(maxlen=MAX_LOG_ENTRIES)

def registra(messaggio, livello="INFO"):
    """Adds a message to the log history with timestamp, maintaining MAX_LOG_ENTRIES limit."""
    orario = datetime.datetime.now().strftime("%H:%M:%S")
    riga = f"[{orario}] [{livello}] {messaggio}"
    _registri_log.append(riga)
    try:
        print(riga)
    except (OSError, ValueError):
        # The UI log remains available even when a launcher closes its console.
        pass

def ottieni_tutti_i_log():
    """Returns all accumulated logs joined into a single text block."""
    if not _registri_log:
        return "No logs recorded yet. Start an action to display log data."
    return "\n".join(_registri_log)

def svuota_log():
    """Clears log history."""
    global _registri_log
    _registri_log.clear()
    return "Log history cleared."
