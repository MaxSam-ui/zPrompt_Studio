"""Persist advanced-section visibility without changing generation settings."""
import gradio as gr
from core import sessione


def persistent_accordion(key, saved, *args, **kwargs):
    preference = 'ui_accordion_open_' + key
    kwargs['open'] = saved.get(preference) is True
    accordion = gr.Accordion(*args, **kwargs)
    # Both actions share one queue so quick toggles are saved in order.
    options = dict(inputs=None, outputs=None, show_progress='hidden',
                   trigger_mode='multiple', concurrency_limit=1,
                   concurrency_id='accordion-preference-' + key)
    accordion.expand(lambda: sessione.salva_sessione({preference: True}), **options)
    accordion.collapse(lambda: sessione.salva_sessione({preference: False}), **options)
    return accordion
