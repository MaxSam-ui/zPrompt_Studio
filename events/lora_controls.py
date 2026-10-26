"""Update the LoRA count and visible controls in the same queued response."""
from utils.lora_ui import lora_row_update


def bind_lora_controls(add_button, remove_button, count, rows, fields,
                       add, remove, concurrency_id):
    def update_rows(handler, value):
        result = list(handler(value))
        # Keep controls mounted while hidden. With visible=False Gradio lazily
        # mounts the row; its initial hidden state can override the first update.
        result[1] = lora_row_update(result[0] >= 2)
        result[2] = lora_row_update(result[0] >= 3)
        return tuple(result)

    def increment(value):
        return update_rows(add, value)

    def decrement(value):
        return update_rows(remove, value)

    shared = dict(concurrency_id=concurrency_id, concurrency_limit=1,
                  show_progress='hidden', queue=True)
    # A chained visibility callback can observe a different count or wait behind
    # another click. Return State and row updates together, including at limits.
    add_button.click(increment, [count], [count, *rows], trigger_mode='multiple', **shared)
    remove_button.click(decrement, [count], [count, *rows, *fields],
                        trigger_mode='multiple', **shared)
