"""Stream installation diagnostics into the existing application log."""
from queue import Queue
from threading import Thread

import gradio as gr

from core import log
from services.installation_check import collect_checks


def installation_log_updates(lang):
    italian = lang == 'IT'
    label = 'Verifica installazione' if italian else 'Check installation'
    log.registra('Verifica installazione in corso…' if italian else 'Checking installation…')
    yield log.ottieni_tutti_i_log(), gr.update(interactive=False, value='…')
    messages = Queue()

    def run():
        try:
            collect_checks(on_result=messages.put)
        except Exception as exc:
            messages.put(('ERROR', 'Diagnostics', str(exc), str(exc)))
        finally:
            messages.put(None)

    worker = Thread(target=run, daemon=True)
    worker.start()
    errors = pending = 0
    while True:
        row = messages.get()
        if row is None:
            break
        status, name, it, en = row
        errors += status == 'ERROR'
        pending += status == 'CONFIG'
        log.registra(f'[{status}] {name}: {it if italian else en}')
        yield log.ottieni_tutti_i_log(), gr.update()
    worker.join()
    summary = (f'Verifica completata: {errors} errori, {pending} elementi da configurare/verificare.' if italian
               else f'Check completed: {errors} errors, {pending} items to configure/check.')
    log.registra(summary)
    yield log.ottieni_tutti_i_log(), gr.update(interactive=True, value=label)
