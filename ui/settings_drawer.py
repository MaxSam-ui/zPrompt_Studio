"""Optional side panels: original Gradio components stay mounted and bound."""
from contextlib import contextmanager
from pathlib import Path

import gradio as gr

from core import sessione


@contextmanager
def settings_drawer(d, name):
    gr.Button(d["drawer_open"], variant="secondary",
              elem_id=f"studio-settings-open-{name}", elem_classes=["studio-drawer-trigger"])
    with gr.Column(elem_id=f"studio-settings-{name}", elem_classes=["studio-settings-panel"]):
        with gr.Row(elem_classes=["studio-drawer-heading"]):
            gr.Markdown(d[f"drawer_title_{name}"], elem_id=f"studio-settings-title-{name}",
                        elem_classes=["studio-drawer-title"])
            gr.Button(d["drawer_close"], size="sm", scale=0, min_width=90,
                      elem_classes=["studio-drawer-close"])
        gr.Markdown(d["drawer_hint"], elem_classes=["studio-drawer-hint"])
        yield


def save_preference(enabled):
    sessione.salva_sessione({"settings_drawer_enabled": bool(enabled)})


def connect(demo, preference):
    script = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")
    demo.load(fn=None, inputs=[preference], outputs=None, js=script)
    preference.change(
        fn=save_preference, inputs=[preference], outputs=None, queue=False,
        js="(enabled) => { window.studioSettingsDrawer?.setEnabled(enabled); return [enabled]; }",
        show_progress="hidden",
    )
