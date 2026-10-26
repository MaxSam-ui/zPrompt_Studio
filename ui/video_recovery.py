"""Per-field checkpoints, captured before editing or starting an AI operation."""
import gradio as gr


def create_recovery_control(dictionary):
    return gr.Button(dictionary.get('video_restore_text', '↶ Restore previous text'),
                     size='sm', interactive=False, variant='secondary',
                     scale=0, min_width=32, elem_classes=['studio-restore-icon'])


def recovery_button(field, dictionary, compact=False, button=None):
    checkpoint = gr.State(None)
    if button is None:
        button = create_recovery_control(dictionary)

    def capture(value, previous):
        if value and value.strip():
            return value, gr.update(interactive=True)
        return previous, gr.update(interactive=previous is not None)

    def restore(previous):
        return (previous if previous is not None else gr.update()), None, gr.update(interactive=False)

    def capture_on_focus(value, previous):
        # Focusing an AI result must not replace the pre-operation checkpoint.
        if previous is not None:
            return previous, gr.update(interactive=True)
        return capture(value, previous)

    field.focus(capture_on_focus, [field, checkpoint], [checkpoint, button], show_progress='hidden')
    button.click(restore, [checkpoint], [field, checkpoint, button], show_progress='hidden')
    return field, checkpoint, button, capture


def connect_recovery(triggers, checkpoints):
    for trigger in triggers:
        for field, checkpoint, button, capture in checkpoints:
            trigger.click(capture, [field, checkpoint], [checkpoint, button],
                          queue=False, show_progress='hidden')
