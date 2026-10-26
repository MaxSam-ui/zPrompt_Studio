"""Keep LoRA rows mounted so Gradio does not discard their first show update."""
import gradio as gr


def lora_row_classes(shown):
    return ["studio-lora-row"] + ([] if shown else ["studio-lora-hidden"])


def lora_row_update(shown):
    return gr.update(visible=True, elem_classes=lora_row_classes(shown))
